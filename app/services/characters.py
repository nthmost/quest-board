"""Character CRUD + welcome-grant ledger logic."""

from __future__ import annotations

import random

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import load_economy
from app.models import Character, CharacterClass, Guild, User, XpTransaction


class CharacterError(ValueError):
    """Raised for user-facing validation failures during character creation."""


def list_for_user(db: Session, user_id: int, include_deleted: bool = False) -> list[Character]:
    stmt = select(Character).where(Character.user_id == user_id)
    if not include_deleted:
        stmt = stmt.where(Character.deleted_at.is_(None))
    stmt = stmt.order_by(Character.created_at.asc())
    return list(db.execute(stmt).scalars().all())


def list_classes(db: Session) -> list[CharacterClass]:
    stmt = select(CharacterClass).order_by(CharacterClass.name)
    return list(db.execute(stmt).scalars().all())


def list_guilds(db: Session) -> list[Guild]:
    stmt = select(Guild).order_by(Guild.name)
    return list(db.execute(stmt).scalars().all())


def create_character(
    db: Session, user_id: int, name: str, class_slug: str,
    primary_guild_id: int | None,
) -> Character:
    """Validate, insert, fire welcome grant. All in one transaction."""
    name = (name or "").strip()
    _validate_name(name)
    _validate_class(db, class_slug)
    _validate_under_cap(db, user_id)
    _reject_duplicate_name(db, user_id, name)

    character = Character(
        user_id=user_id,
        name=name,
        class_slug=class_slug,
        primary_guild_id=primary_guild_id,
        flavor_seed=random.randint(0, 2**31 - 1),
    )
    db.add(character)
    db.flush()  # get character.id without committing
    _fire_welcome_grant(db, character)
    _set_active_if_unset(db, user_id, character.id)
    db.commit()
    db.refresh(character)
    return character


def create_default_profile(db: Session, user_id: int, handle: str) -> Character:
    """Auto-create the single backing profile at signup.

    Named by the person's handle; assigned a random class (optional flavor the
    person can change later on their profile). Folds the old separate
    'create a character' step into signup.
    """
    classes = list_classes(db)
    if not classes:
        raise CharacterError("No character classes are configured.")
    class_slug = random.choice(classes).slug
    return create_character(db, user_id, handle, class_slug, None)


def get_active_character(db: Session, user_id: int) -> Character | None:
    """The user's active (and, now, only) profile, or None for legacy rows."""
    user = db.execute(select(User).where(User.id == user_id)).scalar_one()
    if user.active_character_id is None:
        return db.execute(
            select(Character)
            .where(Character.user_id == user_id, Character.deleted_at.is_(None))
            .order_by(Character.created_at.asc())
            .limit(1)
        ).scalar_one_or_none()
    return db.execute(
        select(Character).where(Character.id == user.active_character_id)
    ).scalar_one_or_none()


def rename_active(db: Session, user_id: int, new_name: str) -> None:
    """Rename the user's profile so its display name tracks their handle."""
    new_name = (new_name or "").strip()
    _validate_name(new_name)
    char = get_active_character(db, user_id)
    if char is not None:
        char.name = new_name
        db.commit()


def set_class(db: Session, user_id: int, class_slug: str) -> None:
    """Change the profile's (optional) class. Owner-scoped; validates existence."""
    _validate_class(db, class_slug)
    char = get_active_character(db, user_id)
    if char is not None:
        char.class_slug = class_slug
        db.commit()


def _set_active_if_unset(db: Session, user_id: int, character_id: int) -> None:
    """If this is the user's first profile, mark it active automatically."""
    user = db.execute(select(User).where(User.id == user_id)).scalar_one()
    if user.active_character_id is None:
        user.active_character_id = character_id


def max_characters_per_user() -> int:
    # One character per account is the product default — multi-character was a
    # demo-era idea that was cut. Instances can still raise this via
    # economy.yaml `demo.max_characters_per_user` if they ever want it back.
    return int(load_economy().get("demo", {}).get("max_characters_per_user", 1))


def _validate_name(name: str) -> None:
    if not name:
        raise CharacterError("Name is required.")
    if len(name) > 64:
        raise CharacterError("Name is too long (max 64 characters).")


def _validate_class(db: Session, class_slug: str) -> None:
    exists = db.execute(
        select(CharacterClass).where(CharacterClass.slug == class_slug)
    ).scalar_one_or_none()
    if exists is None:
        raise CharacterError(f"Unknown class: {class_slug!r}.")


def _validate_under_cap(db: Session, user_id: int) -> None:
    count_q = (
        select(func.count())
        .select_from(Character)
        .where(Character.user_id == user_id, Character.deleted_at.is_(None))
    )
    if int(db.execute(count_q).scalar_one()) >= max_characters_per_user():
        cap = max_characters_per_user()
        raise CharacterError(f"You already have the maximum of {cap} characters.")


def _reject_duplicate_name(db: Session, user_id: int, name: str) -> None:
    dupe = db.execute(
        select(Character).where(
            Character.user_id == user_id,
            Character.name == name,
            Character.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if dupe is not None:
        raise CharacterError(f"You already have a character named {name!r}.")


def _fire_welcome_grant(db: Session, character: Character) -> None:
    """If welcome_grant is enabled in YAML, mint XP onto the new character."""
    grant = load_economy().get("xp", {}).get("welcome_grant", {})
    if not grant.get("enabled"):
        return
    amount = int(grant.get("amount", 0) or 0)
    if amount <= 0:
        return
    db.add(XpTransaction(
        character_id=character.id,
        amount=amount,
        reason="welcome_grant",
        memo=grant.get("memo") or "welcome to Noisebridge Quests",
    ))
    character.xp_balance = amount
