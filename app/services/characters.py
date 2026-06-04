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


def set_active(db: Session, user_id: int, character_id: int) -> None:
    """Mark a character as the user's active one. Owner-scoped."""
    char = db.execute(
        select(Character).where(
            Character.id == character_id,
            Character.user_id == user_id,
            Character.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if char is None:
        raise CharacterError("Character not found.")
    user = db.execute(select(User).where(User.id == user_id)).scalar_one()
    user.active_character_id = char.id
    db.commit()


def _set_active_if_unset(db: Session, user_id: int, character_id: int) -> None:
    """If this is the user's first character, mark it active automatically."""
    user = db.execute(select(User).where(User.id == user_id)).scalar_one()
    if user.active_character_id is None:
        user.active_character_id = character_id


def soft_delete(db: Session, user_id: int, character_id: int) -> Character:
    """Mark a character deleted. Owner-scoped; raises if not owned by this user.

    If the deleted character was active, transfer active to the oldest
    remaining character or clear it if none remain.
    """
    character = db.execute(
        select(Character).where(
            Character.id == character_id,
            Character.user_id == user_id,
            Character.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if character is None:
        raise CharacterError("Character not found.")
    character.deleted_at = func.now()
    db.flush()
    _reassign_active_after_delete(db, user_id, character.id)
    db.commit()
    db.refresh(character)
    return character


def _reassign_active_after_delete(db: Session, user_id: int, deleted_id: int) -> None:
    user = db.execute(select(User).where(User.id == user_id)).scalar_one()
    if user.active_character_id != deleted_id:
        return
    fallback = db.execute(
        select(Character.id)
        .where(Character.user_id == user_id, Character.deleted_at.is_(None))
        .order_by(Character.created_at.asc())
        .limit(1)
    ).scalar_one_or_none()
    user.active_character_id = fallback


def max_characters_per_user() -> int:
    return int(load_economy().get("demo", {}).get("max_characters_per_user", 4))


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
