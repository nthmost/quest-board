"""SQLAlchemy models. Re-exports Base and all entity classes."""

from app.models.api_key import ApiKey
from app.models.base import Base
from app.models.character import Character
from app.models.character_class import CharacterClass
from app.models.npc_quest_giver import NpcQuestGiver
from app.models.quest import Quest
from app.models.quest_boost import QuestBoost
from app.models.quest_claim import QuestClaim
from app.models.taxonomy import Guild, Location
from app.models.user import User
from app.models.xp_transaction import XpTransaction

__all__ = [
    "ApiKey",
    "Base",
    "Character",
    "CharacterClass",
    "Guild",
    "Location",
    "NpcQuestGiver",
    "Quest",
    "QuestBoost",
    "QuestClaim",
    "User",
    "XpTransaction",
]
