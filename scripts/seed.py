"""Seed development data: guilds, locations, a few users, a handful of quests.

Run after `alembic upgrade head` to populate an empty DB:
    DATABASE_URL=postgresql+psycopg://... python scripts/seed.py
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Guild, Location, Quest, User  # noqa: F401


def main() -> None:
    with SessionLocal() as db:
        _seed_guilds(db)
        _seed_locations(db)
        _seed_users(db)
        db.commit()
        _seed_quests(db)
        db.commit()
        print("seeded.")


def _seed_guilds(db: Session) -> None:
    for slug, name, desc in _guild_data():
        if _exists(db, Guild, slug):
            continue
        db.add(Guild(slug=slug, name=name, description=desc))


def _guild_data() -> list[tuple[str, str, str]]:
    return [
        ("metaguild", "Metaguild",
         "Default guild for unaffiliated quests."),
        ("facilities", "Facilities",
         "Keep the space functioning: cleaning, repair, supplies."),
        ("woodshop", "Woodshop", "Saws, sanders, lumber, sawdust."),
        ("rack", "Rack",
         "Digital infrastructure: servers, networking, the metal rack itself."),
        ("treasurer", "Treasurer",
         "Stewards of the books, donations, and reimbursements."),
        ("safety", "Safety",
         "Emergencies, training, and not-burning-the-place-down."),
        ("electronics", "Electronics",
         "Soldering irons, scopes, and the bench you broke last time."),
        ("sewing", "Sewing", "Fabric, machines, mending, costumes."),
        ("spacebridge", "Spacebridge",
         "High-altitude ballooning: payloads, materials testing, helium fills, recovery."),
        ("writing", "Writing", "Wiki pages, signage, blog posts, the zine."),
        ("gaming", "Gaming",
         "Tabletop, video, LARPs, board games on the church table."),
        ("rubber-ducky", "Rubber Ducky",
         "Debugging companions and quiet listeners."),
        ("philosophy", "Philosophy",
         "Hackerspace ethics, Tuesday discussions, hard problems."),
        ("3d-printing", "3D Printing",
         "Printers, filament, bed-leveling rituals."),
        ("laser-cutter", "Laser Cutter",
         "Vector files, focus, fume extraction."),
        ("ai-ml", "AI/ML", "Models, datasets, and Hilarious Confabulations."),
        ("secretary", "Secretary",
         "Meeting notes, minute-taking, the calendar."),
    ]


def _seed_locations(db: Session) -> None:
    for slug, name, kind, desc in _location_data():
        if _exists(db, Location, slug):
            continue
        db.add(Location(slug=slug, name=name, kind=kind, description=desc))


def _location_data() -> list[tuple[str, str, str, str]]:
    return [
        # Downstairs
        ("hackitorium", "Hackitorium", "physical", "Downstairs main floor."),
        ("stage", "Stage", "physical", "Downstairs inside the Hackitorium."),
        ("electronics-lab", "Electronics Lab", "physical", ""),
        ("music-room", "Music Room", "physical", ""),
        ("patio", "Patio", "physical", ""),
        ("front-of-house", "Front of House", "physical", "Where the laser cutter lives."),
        ("3d-printshop", "3D Printshop", "physical", ""),
        ("woodshop", "Woodshop", "physical", ""),
        ("metalshop", "Metalshop", "physical", "Barely used."),
        ("downstairs-bathroom", "Downstairs Bathroom", "physical", ""),
        ("downstairs-lockers", "Downstairs Lockers", "physical", ""),
        ("forbidden-alley", "Forbidden Alley", "physical",
         "Downstairs behind the 3D Printshop."),
        # Upstairs
        ("rna-lounge", "RNA Lounge", "physical", "Upstairs hackitorium."),
        ("library", "Library", "physical", "Upstairs hallway."),
        ("flaschentaschen-lounge", "Flaschentaschen Lounge", "physical",
         "Flaschentaschen, chairs, and the gaming hoard."),
        ("sewing-room", "Sewing Room", "physical", ""),
        ("upstairs-bathroom", "Upstairs Bathroom", "physical", ""),
        ("upstairs-lockers", "Upstairs Lockers", "physical", ""),
        # Stairwells
        ("front-stairwell", "Front Stairwell", "physical", ""),
        ("back-stairwell", "Back Stairwell", "physical", ""),
        # Online
        ("discord", "Noisebridge Discord", "online", ""),
        ("meetup", "Meetup", "online", ""),
    ]


def _seed_users(db: Session) -> None:
    """Test wiki identities. Economy lives on Character now."""
    for username in ("alice", "bob", "charlie"):
        if _user_exists(db, username):
            continue
        db.add(User(wiki_username=username))


def _seed_quests(db: Session) -> None:
    facilities = _guild_id(db, "facilities")
    metaguild = _guild_id(db, "metaguild")
    bathroom = _location_id(db, "upstairs-bathroom")
    hackitorium = _location_id(db, "hackitorium")
    discord = _location_id(db, "discord")
    alice = _user_id(db, "alice")
    bob = _user_id(db, "bob")
    for q in _quest_data(facilities, metaguild, bathroom, hackitorium, discord, alice, bob):
        if _quest_exists(db, q.title):
            continue
        db.add(q)


def _quest_exists(db: Session, title: str) -> bool:
    return (
        db.execute(select(Quest).where(Quest.title == title)).scalar_one_or_none()
        is not None
    )


def _quest_data(
    facilities: int, metaguild: int, bathroom: int, hackitorium: int, discord: int,
    alice: int, bob: int,
) -> list[Quest]:
    soon = datetime.now(UTC) + timedelta(days=3)
    return [
        Quest(
            creator_user_id=alice, guild_id=facilities, location_id=bathroom,
            title="Repair upstairs bathroom toilet paper holder",
            description="The TP holder has come loose from the wall again.",
            skills=["basic-tools", "wall-anchors"], xp=10, creator_bonus_xp=5,
            posting_fee_charged=3, posting_fee_destination="burn",
            urgency="normal", due_date=soon, party_min=1, party_max=1, status="open",
        ),
        Quest(
            creator_user_id=bob, guild_id=facilities, location_id=hackitorium,
            title="Sweep the Hackitorium floor",
            description=(
                "Weekly sweep of the downstairs main floor. "
                "Move the chairs first if you can manage it."
            ),
            skills=["cleaning"], xp=8, creator_bonus_xp=5,
            posting_fee_charged=3, posting_fee_destination="burn",
            urgency="low", party_min=1, status="open",
        ),
        Quest(
            creator_user_id=alice, guild_id=metaguild, location_id=discord,
            title="Welcome new Discord members from this week",
            description="Reply to intros in #introductions, point them at #orientation.",
            skills=["communication"], xp=5, creator_bonus_xp=5,
            posting_fee_charged=3, posting_fee_destination="burn",
            urgency="normal", party_min=1, party_max=3, status="open",
        ),
    ]


def _exists(db: Session, model, slug: str) -> bool:
    return db.execute(select(model).where(model.slug == slug)).scalar_one_or_none() is not None


def _user_exists(db: Session, username: str) -> bool:
    return (
        db.execute(select(User).where(User.wiki_username == username)).scalar_one_or_none()
        is not None
    )


def _guild_id(db: Session, slug: str) -> int:
    return db.execute(select(Guild.id).where(Guild.slug == slug)).scalar_one()


def _location_id(db: Session, slug: str) -> int:
    return db.execute(select(Location.id).where(Location.slug == slug)).scalar_one()


def _user_id(db: Session, username: str) -> int:
    return db.execute(select(User.id).where(User.wiki_username == username)).scalar_one()


if __name__ == "__main__":
    main()
