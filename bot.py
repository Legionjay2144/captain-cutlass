import asyncio
import json
import os
import random
import re
import time
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import discord
from cutlass.commands.help import handle_help_command
from cutlass.commands.crew import handle_crew_command
from cutlass.commands.lore import handle_lore_command
from cutlass.commands.chronicle import handle_chronicle_command
from cutlass.commands.welcome import handle_welcome_command
from cutlass.commands.treasure import handle_treasure_command, check_treasure_answer
from cutlass.commands.captain import handle_captain_command
from cutlass.commands.admin import handle_admin_command
from cutlass.commands.parrot import handle_parrot_command
from cutlass.commands.ship import handle_ship_command
from cutlass.commands.world import handle_world_command
from cutlass.commands.exploration import handle_exploration_command
from cutlass.commands.islands import handle_island_command
from cutlass.world.islands import (
    format_island,
    choose_island_activity,
)
from cutlass.commands.battle import handle_battle_command
from cutlass.commands.monsters import handle_monster_command
from cutlass.commands.bosses import handle_boss_command
from cutlass.commands.combat import handle_combat_command
from cutlass.world.bosses import (
    initialize_bosses,
    get_active_boss,
    start_boss,
    format_boss,
    attack_boss,
    defend_boss,
)
from cutlass.world.monsters import (
    initialize_monsters,
    start_monster_encounter,
    format_monster,
    attack_monster,
    get_active_monster,
)
from cutlass.world.naval import (
    initialize_naval,
    start_naval_battle,
    format_battle,
    attack_enemy,
    defend,
    board_enemy,
    flee_battle,
    get_active_battle,
)
from cutlass.world.pirate_world import (
    initialize_pirate_world,
    format_world,
    format_world_map,
    format_discoveries,
    get_world_history,
    explore_random_island,
    get_island_activity_state,
    record_island_visit,
)

from discord.ext import tasks
from dotenv import load_dotenv
from openai import AsyncOpenAI

from personality import PERSONALITY
from creator_profile import CREATOR_PROFILE

from features import (
    random_wisdom,
    choose_reaction,
    get_welcome_message,
    relationship_for_familiarity,
    milestone_for_familiarity,
    within_quiet_hours
)

from social_features import (
    returning_message,
    birthday_message,
    format_birthday,
    parse_birthday
)

from ship_world import (
    initialize_ship_world, ensure_ship, get_ship, get_ship_settings, set_ship_setting,
    format_ship_status, rename_ship, get_history, get_history_records, get_completed_voyages, donate, top_contributors,
    repair_ship, format_upgrades, buy_upgrade, format_destinations,
    start_voyage, get_active_voyage, resolve_due_voyages,
    discord_timestamp,
    damage_ship, reward_ship, _reward_ship_unlocked, combat_ship_status,
    add_ship_treasury, add_ship_supplies,
    add_history as add_ship_history
)


from parrot import (
    initialize_parrot,
    ensure_parrot,
    get_parrot,
    set_parrot_enabled,
    set_parrot_chance,
    set_parrot_mood,
    randomize_parrot_mood,
    ensure_parrot_relationship,
    get_parrot_relationship,
    increase_parrot_familiarity,
    get_parrot_memories,
    get_parrot_jokes,
    add_parrot_memory,
    add_parrot_joke,
    update_parrot_relationship,
    increment_parrot_interactions,
    add_parrot_captain_event,
    get_parrot_captain_events,
    format_parrot_captain_history,
    format_parrot_relationship,
    format_parrot_status,
    PARROT_MOODS
)

from memory import (
    initialize_database,
    run_maintenance,

    save_message,
    get_recent_messages,

    ensure_user_profile,
    get_user_profile,
    add_user_memory,
    get_user_memories,
    get_user_memories_context,
    delete_user_memories,

    add_captain_lore,
    get_captain_lore,
    get_all_captain_canon,
    format_captain_canon,

    add_server_lore,
    get_server_lore,

    ensure_relationship,
    get_relationship,
    increase_familiarity,
    update_relationship,
    get_top_crew,

    add_running_joke,
    get_running_jokes,

    add_relationship_event,
    get_relationship_events,

    add_quote,
    get_random_quote,

    get_journal,

    ensure_guild_settings,
    get_guild_settings,
    set_guild_setting,

    start_treasure_hunt,
    get_treasure_hunt,
    finish_treasure_hunt,

    ensure_economy,
    add_doubloons,
    get_doubloons,
    get_doubloon_leaderboard,

    award_achievement,
    get_achievements,

    add_timeline_entry,
    get_timeline,

    get_stats,

    ensure_member_meta,
    get_member_meta,
    touch_member_seen,
    mark_return_greeted,
    set_birthday,
    clear_birthday,
    get_birthdays,
    get_todays_birthdays,
    mark_birthday_rewarded,
    add_log_entry,
    get_log_entries,
    save_chronicle,
    get_latest_chronicle,
    nickname_is_taken,
)


load_dotenv()


DISCORD_TOKEN = os.getenv(
    "DISCORD_TOKEN"
)

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY"
)

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-4.1-mini"
)


CREATOR_USER_ID = int(
    os.getenv(
        "CREATOR_USER_ID",
        "0"
    )
)


RANDOM_REPLY_CHANCE = float(
    os.getenv(
        "RANDOM_REPLY_CHANCE",
        "0.08"
    )
)

REACTION_CHANCE = float(
    os.getenv(
        "REACTION_CHANCE",
        "0.06"
    )
)

COOLDOWN_SECONDS = int(
    os.getenv(
        "COOLDOWN_SECONDS",
        "180"
    )
)

FAMILIARITY_COOLDOWN_SECONDS = int(
    os.getenv(
        "FAMILIARITY_COOLDOWN_SECONDS",
        "60"
    )
)


CONTEXT_MESSAGES = int(
    os.getenv(
        "CONTEXT_MESSAGES",
        "10"
    )
)

CONTEXT_MEMORIES = int(
    os.getenv(
        "CONTEXT_MEMORIES",
        "5"
    )
)

CONTEXT_MEMORY_MIN_CONFIDENCE = int(
    os.getenv(
        "CONTEXT_MEMORY_MIN_CONFIDENCE",
        "1"
    )
)

CONTEXT_CAPTAIN_LORE = int(
    os.getenv(
        "CONTEXT_CAPTAIN_LORE",
        "5"
    )
)

CONTEXT_SERVER_LORE = int(
    os.getenv(
        "CONTEXT_SERVER_LORE",
        "5"
    )
)

CONTEXT_JOKES = int(
    os.getenv(
        "CONTEXT_JOKES",
        "3"
    )
)

CONTEXT_EVENTS = int(
    os.getenv(
        "CONTEXT_EVENTS",
        "3"
    )
)

CONTEXT_ACHIEVEMENTS = int(
    os.getenv(
        "CONTEXT_ACHIEVEMENTS",
        "5"
    )
)


CACHE_SECONDS = int(
    os.getenv(
        "CACHE_SECONDS",
        "300"
    )
)


BOT_TIMEZONE = os.getenv(
    "BOT_TIMEZONE",
    "America/New_York"
)


QUIET_HOURS_ENABLED = (
    os.getenv(
        "QUIET_HOURS_ENABLED",
        "true"
    ).lower()
    == "true"
)


QUIET_START_HOUR = int(
    os.getenv(
        "QUIET_START_HOUR",
        "1"
    )
)


QUIET_END_HOUR = int(
    os.getenv(
        "QUIET_END_HOUR",
        "7"
    )
)


MESSAGE_RETENTION_DAYS = int(
    os.getenv(
        "MESSAGE_RETENTION_DAYS",
        "30"
    )
)


WEAK_MEMORY_RETENTION_DAYS = int(
    os.getenv(
        "WEAK_MEMORY_RETENTION_DAYS",
        "120"
    )
)


allowed_channels_raw = os.getenv(
    "ALLOWED_CHANNELS",
    ""
)


if allowed_channels_raw.strip():

    ALLOWED_CHANNELS = {
        int(channel.strip())
        for channel
        in allowed_channels_raw.split(",")
        if channel.strip()
    }

else:

    ALLOWED_CHANNELS = set()


ai = AsyncOpenAI(
    api_key=OPENAI_API_KEY
)


intents = discord.Intents.default()

intents.message_content = True
intents.members = True


bot = discord.Client(
    intents=intents
)


last_spontaneous_reply = {}
last_familiarity_gain = {}

settings_cache = {}
world_cache = {}


BRAIN_SCHEMA = {
    "type": "object",

    "properties": {

        "respond": {
            "type": "boolean"
        },

        "memory": {
            "type": "string"
        },

        "relationship": {
            "type": "string"
        },

        "opinion": {
            "type": "string"
        },

        "nickname": {
            "type": "string"
        },

        "joke": {
            "type": "string"
        },

        "event": {
            "type": "string"
        },

        "server_lore": {
            "type": "string"
        },

        "reply": {
            "type": "string"
        },

        "lore": {
            "type": "string"
        },

        "memory_evidence": {
            "type": "string"
        },

        "joke_evidence": {
            "type": "string"
        },

        "event_evidence": {
            "type": "string"
        },

        "server_lore_evidence": {
            "type": "string"
        }
    },

    "required": [
        "respond",
        "memory",
        "relationship",
        "opinion",
        "nickname",
        "joke",
        "event",
        "server_lore",
        "reply",
        "lore",
        "memory_evidence",
        "joke_evidence",
        "event_evidence",
        "server_lore_evidence"
    ],

    "additionalProperties": False
}


def is_creator(
    user_id
):

    return (
        CREATOR_USER_ID != 0
        and user_id == CREATOR_USER_ID
    )


def channel_allowed(
    message
):

    if not ALLOWED_CHANNELS:
        return True

    return (
        message.channel.id
        in ALLOWED_CHANNELS
    )


def cooldown_ready(
    channel_id
):

    previous = last_spontaneous_reply.get(
        channel_id,
        0
    )

    return (
        time.time() - previous
        >= COOLDOWN_SECONDS
    )


def familiarity_ready(
    guild_id,
    user_id
):

    key = (
        guild_id,
        user_id
    )

    previous = last_familiarity_gain.get(
        key,
        0
    )

    now = time.time()

    if (
        now - previous
        < FAMILIARITY_COOLDOWN_SECONDS
    ):

        return False

    last_familiarity_gain[
        key
    ] = now

    return True


def is_admin(
    message
):

    if is_creator(
        message.author.id
    ):

        return True

    permissions = (
        message.author.guild_permissions
    )

    return (
        permissions.administrator
        or permissions.manage_guild
    )


def cache_valid(
    entry
):

    if not entry:
        return False

    return (
        time.time()
        - entry["time"]
        < CACHE_SECONDS
    )


def invalidate_world_cache(
    guild_id
):

    world_cache.pop(
        guild_id,
        None
    )


def invalidate_settings_cache(
    guild_id
):

    settings_cache.pop(
        guild_id,
        None
    )

    invalidate_world_cache(
        guild_id
    )


async def cached_settings(
    guild_id
):

    existing = settings_cache.get(
        guild_id
    )

    if cache_valid(
        existing
    ):

        return existing[
            "data"
        ]

    data = await get_guild_settings(
        guild_id
    )

    settings_cache[
        guild_id
    ] = {
        "time": time.time(),
        "data": data
    }

    return data


async def build_conversation(
    message
):

    rows = await get_recent_messages(
        message.guild.id,
        message.channel.id,
        CONTEXT_MESSAGES
    )

    return "\n".join(
        f"{name}: {content[:500]}"
        for name, content in rows
    )


async def build_member_context(
    message
):

    (
        profile,
        memories,
        relationship,
        jokes,
        events,
        balance,
        achievements
    ) = await asyncio.gather(

        get_user_profile(
            message.guild.id,
            message.author.id
        ),

        get_user_memories_context(
            message.guild.id,
            message.author.id,
            CONTEXT_MEMORIES,
            CONTEXT_MEMORY_MIN_CONFIDENCE
        ),

        get_relationship(
            message.guild.id,
            message.author.id
        ),

        get_running_jokes(
            message.guild.id,
            message.author.id,
            CONTEXT_JOKES
        ),

        get_relationship_events(
            message.guild.id,
            message.author.id,
            CONTEXT_EVENTS
        ),

        get_doubloons(
            message.guild.id,
            message.author.id
        ),

        get_achievements(
            message.guild.id,
            message.author.id,
            CONTEXT_ACHIEVEMENTS
        )
    )


    lines = [
        (
            "Member: "
            + message.author.display_name
        ),

        (
            "Doubloons: "
            + str(balance)
        )
    ]


    if is_creator(
        message.author.id
    ):

        lines.append(
            "SPECIAL STATUS: CREATOR / SHIPWRIGHT"
        )

        lines.append(
            CREATOR_PROFILE
        )


    if (
        profile
        and profile["summary"]
    ):

        lines.append(
            "Profile: "
            + profile["summary"][:300]
        )


    if memories:

        lines.append(
            "Strong memories:"
        )

        for memory in memories:

            lines.append(
                "- "
                + memory[:250]
            )


    if relationship:

        lines.append(
            "Relationship: "
            + relationship[
                "relationship_type"
            ]
        )

        lines.append(
            "Familiarity: "
            + str(
                relationship[
                    "familiarity"
                ]
            )
            + "/100"
        )

        if relationship[
            "nickname"
        ]:

            lines.append(
                "Nickname: "
                + relationship[
                    "nickname"
                ][:100]
            )

        if relationship[
            "opinion"
        ]:

            lines.append(
                "Opinion: "
                + relationship[
                    "opinion"
                ][:250]
            )


    if achievements:

        lines.append(
            "Achievements:"
        )

        for (
            achievement,
            _
        ) in achievements:

            lines.append(
                "- "
                + achievement[:100]
            )


    if jokes:

        lines.append(
            "Running jokes:"
        )

        for joke in jokes:

            lines.append(
                "- "
                + joke[:300]
            )


    if events:

        lines.append(
            "Shared events:"
        )

        for event in events:

            lines.append(
                "- "
                + event[
                    "event"
                ][:300]
            )


    return "\n".join(
        lines
    )







def detect_direct_question_mode(message):
    """
    Detect clear direct questions addressed to Captain that should be
    answered before unrelated memories or creator callbacks.
    """

    content = message.content.lower().strip()

    question_patterns = [
        r"\bare you\b",
        r"\bdo you\b",
        r"\bdid you\b",
        r"\bhave you\b",
        r"\bwould you\b",
        r"\bcould you\b",
        r"\bcan you\b",
        r"\bwhat do you\b",
        r"\bwhat would you\b",
        r"\bwhat are you\b",
        r"\bwhat is your\b",
        r"\bwhat's your\b",
        r"\bwho are you\b",
        r"\bwho is your\b",
        r"\bwhy do you\b",
        r"\bwhy are you\b",
        r"\bhow are you\b",
        r"\bhow would you\b",
        r"\breckon you\b",
    ]

    for pattern in question_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return True

    return content.endswith("?")

def detect_humor_mode(message):
    """
    Deterministically classify the current humor interaction.
    """

    content = message.content.lower().strip()

    targeted_patterns = [
        r"\bmake\s+(?:me\s+)?(?:a\s+)?joke\s+about\b",
        r"\btell\s+(?:me\s+)?(?:a\s+)?joke\s+about\b",
        r"\bjoke\s+about\b",
        r"\broast\b",
        r"\btease\b",
        r"\bmake\s+fun\s+of\b",
    ]

    for pattern in targeted_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return "TARGETED_JOKE_REQUEST"

    humor_request_patterns = [
        r"\bgive\s+(?:me\s+)?(?:a\s+)?pun\b",
        r"\btell\s+(?:me\s+)?(?:a\s+)?pun\b",
        r"\bpun\s+pls\b",
        r"\bpun\s+please\b",
        r"\bgive\s+(?:me\s+)?(?:a\s+)?joke\b",
        r"\btell\s+(?:me\s+)?(?:a\s+)?joke\b",
        r"\bmake\s+(?:me\s+)?laugh\b",
        r"\bgive\s+(?:me\s+)?(?:a\s+)?one[- ]liner\b",
        r"\btell\s+(?:me\s+)?(?:a\s+)?one[- ]liner\b",
    ]

    for pattern in humor_request_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return "HUMOR_REQUEST"

    joke_signals = [
        r"\bwhy did\b",
        r"\bwhat do you call\b",
        r"\bwhat did\b",
        r"\bhow do\b",
        r"\bwalks into\b",
        r"\bknock knock\b",
        r"\btherefore\b.*\bar+r+\b",
        r"\bar+r+\b.*\bar+r+\b",
    ]

    for pattern in joke_signals:
        if re.search(pattern, content, re.IGNORECASE):
            return "JOKE_TOLD_TO_CAPTAIN"

    # Playful / fictional hypothetical questions should get their own
    # isolated response path so unrelated memories and callbacks cannot
    # hijack the scenario.
    hypothetical_markers = (
        "hypothetically",
        "hypothetical",
        "what if ",
        "what would you do if",
        "what would ye do if",
        "if you became",
        "if ye became",
        "if you were",
        "if ye were",
        "how would you ",
        "how would ye ",
        "imagine you ",
        "imagine ye ",
        "suppose you ",
        "suppose ye ",
    )

    if any(
        marker in content
        for marker in hypothetical_markers
    ):
        return "PLAYFUL_HYPOTHETICAL"

    return "NORMAL"


async def resolve_joke_target(message):
    """
    Resolve another Discord member when the author explicitly asks
    Captain to joke about / roast / tease that person.

    Mentions are preferred. Plain display names are also supported.
    """

    # If another member is explicitly mentioned, use them.
    for member in message.mentions:

        if bot.user and member.id == bot.user.id:
            continue

        if member.id == message.author.id:
            continue

        return member


    content = message.content.strip()


    patterns = [
        r"(?:make|tell|give)\s+(?:me\s+)?(?:a\s+)?joke\s+about\s+(.+?)(?:[?.!]|$)",
        r"(?:joke|roast|tease)\s+(?:about\s+)?(.+?)(?:[?.!]|$)",
        r"make\s+fun\s+of\s+(.+?)(?:[?.!]|$)",
    ]


    target_text = None


    for pattern in patterns:

        match = re.search(
            pattern,
            content,
            flags=re.IGNORECASE
        )

        if match:

            target_text = (
                match.group(1)
                .strip()
                .strip("@")
                .strip()
            )

            break


    if not target_text:
        return None


    target_lower = target_text.lower()


    # Exact display-name / username match first.
    for member in message.guild.members:

        if member.bot:
            continue

        names = {
            member.display_name.lower(),
            member.name.lower()
        }

        if target_lower in names:
            return member


    # Then allow a conservative partial match.
    matches = []

    for member in message.guild.members:

        if member.bot:
            continue

        display = member.display_name.lower()
        username = member.name.lower()

        if (
            target_lower in display
            or target_lower in username
        ):
            matches.append(member)


    # Only use a partial match if it is unambiguous.
    if len(matches) == 1:
        return matches[0]


    return None


async def build_target_member_context(message):

    target = await resolve_joke_target(
        message
    )


    if target is None:
        return "NONE"


    (
        profile,
        memories,
        relationship,
        jokes,
        events,
        achievements
    ) = await asyncio.gather(

        get_user_profile(
            message.guild.id,
            target.id
        ),

        get_user_memories_context(
            message.guild.id,
            target.id,
            CONTEXT_MEMORIES,
            CONTEXT_MEMORY_MIN_CONFIDENCE
        ),

        get_relationship(
            message.guild.id,
            target.id
        ),

        get_running_jokes(
            message.guild.id,
            target.id,
            CONTEXT_JOKES
        ),

        get_relationship_events(
            message.guild.id,
            target.id,
            CONTEXT_EVENTS
        ),

        get_achievements(
            message.guild.id,
            target.id,
            CONTEXT_ACHIEVEMENTS
        )
    )


    lines = [
        "TARGET MEMBER: " + target.display_name,
        "TARGET USER ID: " + str(target.id)
    ]


    if (
        profile
        and profile.get("summary")
    ):

        lines.append(
            "Profile: "
            + profile["summary"][:300]
        )


    if relationship:

        lines.append(
            "Relationship: "
            + relationship["relationship_type"]
        )

        lines.append(
            "Familiarity: "
            + str(relationship["familiarity"])
            + "/100"
        )

        if relationship["nickname"]:

            lines.append(
                "Nickname: "
                + relationship["nickname"][:100]
            )

        if relationship["opinion"]:

            lines.append(
                "Captain opinion: "
                + relationship["opinion"][:300]
            )


    if memories:

        lines.append(
            "Harmless memories:"
        )

        for memory in memories:

            lines.append(
                "- "
                + memory[:250]
            )


    if jokes:

        lines.append(
            "Running jokes:"
        )

        for joke in jokes:

            lines.append(
                "- "
                + joke[:300]
            )


    if events:

        lines.append(
            "Shared events:"
        )

        for event in events:

            lines.append(
                "- "
                + event["event"][:300]
            )


    if achievements:

        lines.append(
            "Achievements:"
        )

        for achievement, _ in achievements:

            lines.append(
                "- "
                + achievement[:100]
            )


    return "\n".join(lines)


async def build_gameplay_context(
    message
):
    """
    Selectively load authoritative gameplay state.

    No additional AI call is made here.
    """

    content = (
        message.content
        .lower()
        .strip()
    )

    ship_terms = (
        "ship",
        "living ship",
        "hull",
        "sails",
        "supplies",
        "morale",
        "treasury",
        "doubloons",
        "repair",
        "fix the ship",
        "fix our ship",
        "upgrade",
        "upgrades",
    )

    voyage_terms = (
        "voyage",
        "voyages",
        "sail",
        "sailed",
        "sailing",
        "destination",
        "destinations",
        "travel",
        "route",
        "where are we",
        "where is the ship",
    )

    exploration_terms = (
        "explore",
        "exploration",
        "scout",
        "scouting",
        "island",
        "islands",
        "discovered",
        "discovery",
        "charted",
        "world",
    )

    combat_terms = (
        "battle",
        "fight",
        "combat",
        "boss",
        "monster",
        "kraken",
        "naval",
        "enemy",
        "attack",
        "board",
        "boarding",
        "defend",
        "flee",
        "damage",
    )

    history_terms = (
        "history",
        "happened",
        "last voyage",
        "last battle",
        "last fight",
        "recent",
        "recently",
        "adventure",
        "adventures",
        "story",
        "stories",
        "remember when",
        "what have we",
        "what did we",
    )

    followup_terms = (
        "before that",
        "one before",
        "what about that",
        "what about the one",
        "and before",
        "then what",
        "what happened next",
        "after that",
        "that one",
    )

    all_terms = (
        ship_terms
        + voyage_terms
        + exploration_terms
        + combat_terms
        + history_terms
    )

    gameplay_detected = any(
        term in content
        for term in all_terms
    )

    followup_detected = any(
        term in content
        for term in followup_terms
    )

    # -----------------------------------------------------
    # Follow-up continuity
    #
    # "What about the one before that?" contains no obvious
    # gameplay noun, so inspect recent chat before deciding.
    # -----------------------------------------------------

    if (
        not gameplay_detected
        and followup_detected
    ):

        recent = await get_recent_messages(
            message.guild.id,
            message.channel.id,
            6
        )

        recent_text = " ".join(
            str(row[1]).lower()
            for row in recent
        )

        gameplay_detected = any(
            term in recent_text
            for term in all_terms
        )

    if not gameplay_detected:
        return "NONE"

    guild_id = message.guild.id

    wants_history = (
        any(
            term in content
            for term in history_terms
        )
        or followup_detected
    )

    wants_voyage = (
        any(
            term in content
            for term in voyage_terms
        )
        or "last voyage" in content
        or followup_detected
    )

    wants_world = any(
        term in content
        for term in exploration_terms
    )

    wants_story = any(
        term in content
        for term in (
            "story",
            "stories",
            "adventure",
            "adventures",
        )
    )

    ship = await get_ship(
        guild_id
    )

    lines = [
        "AUTHORITATIVE GAMEPLAY CONTEXT:",
        "",
        "CURRENT LIVING SHIP:",
        "Name: " + str(ship["name"]),
        "Level: " + str(ship["level"]),
        "XP: " + str(ship["xp"]),
        "Hull: " + str(ship["hull"]),
        "Sails: " + str(ship["sails"]),
        "Supplies: " + str(ship["supplies"]),
        "Morale: " + str(ship["morale"]),
        "Treasury: " + str(ship["treasury"]),
        "Location: " + str(ship["location"]),
        (
            "Voyages Completed: "
            + str(ship["voyages_completed"])
        ),
        (
            "Distance Sailed: "
            + str(ship["distance_sailed"])
            + " nautical miles"
        ),
    ]

    if wants_voyage:

        voyage = await get_active_voyage(
            guild_id
        )

        lines.extend([
            "",
            "ACTIVE VOYAGE:",
        ])

        if voyage:

            lines.extend([
                "Destination: " + str(voyage["destination"]),
                "Risk: " + str(voyage["risk"]),
                "Started: " + str(voyage["started_at"]),
                (
                    "Expected Completion: "
                    + str(voyage["completes_at"])
                ),
                (
                    "Distance: "
                    + str(voyage["distance"])
                    + " nautical miles"
                ),
            ])

        else:
            lines.append(
                "No active voyage."
            )

    records = []

    if wants_history:

        records = await get_history_records(
            guild_id,
            limit=20
        )

        completed_voyages = await get_completed_voyages(
            guild_id,
            limit=8
        )

        lines.extend([
            "",
            "COMPLETED VOYAGE HISTORY:",
            (
                "Voyages below are ordered newest first. "
                "VOYAGE #1 is the most recently completed voyage. "
                "VOYAGE #2 is the voyage immediately before it."
            ),
        ])

        if completed_voyages:

            for number, voyage_record in enumerate(
                completed_voyages,
                start=1
            ):

                lines.extend([
                    "",
                    (
                        "VOYAGE #"
                        + str(number)
                        + ":"
                    ),
                    (
                        "Completed: "
                        + str(
                            voyage_record["created_at"]
                        )
                    ),
                    (
                        "Result: "
                        + str(
                            voyage_record["content"]
                        )
                    ),
                ])

        else:

            lines.append(
                "No completed voyages recorded."
            )

        lines.extend([
            "",
            "RECENT RECORDED SHIP EVENTS:",
            (
                "These events are NOT automatically voyages. "
                "Battles, exploration, repairs, monsters, "
                "island activity, and treasure events must not "
                "be described as completed voyages unless a "
                "VOYAGE entry above says so."
            ),
        ])

        for row in records[:10]:
            lines.append(
                "- ["
                + str(row["event_type"])
                + "] "
                + str(row["created_at"])
                + ": "
                + str(row["content"])[:500]
            )

        if not records:
            lines.append(
                "- No recorded ship events."
            )

    # -----------------------------------------------------
    # Explicit latest-voyage grounding
    # -----------------------------------------------------

    if (
        "last voyage" in content
        or "latest voyage" in content
        or (
            followup_detected
            and records
        )
    ):

        if not records:

            records = await get_history_records(
                guild_id,
                limit=30
            )

        voyage_records = [
            row
            for row in records
            if row["event_type"]
            == "voyage_complete"
        ]

        lines.extend([
            "",
            "RECORDED COMPLETED VOYAGES, NEWEST FIRST:",
        ])

        if voyage_records:

            for number, row in enumerate(
                voyage_records[:5],
                start=1
            ):
                lines.append(
                    str(number)
                    + ". "
                    + str(row["created_at"])
                    + ": "
                    + str(row["content"])[:600]
                )

        else:
            lines.append(
                "- No completed voyage records found."
            )

        lines.append(
            (
                "If the member asks for the last voyage, use item 1. "
                "If they follow with 'the one before that', use item 2."
            )
        )

    if (
        wants_world
        or wants_story
    ):

        world_history = await get_world_history(
            guild_id,
            limit=10
        )

        lines.extend([
            "",
            "RECENT RECORDED WORLD EVENTS:",
        ])

        if world_history:

            for row in world_history:
                lines.append(
                    "- ["
                    + str(row["event_type"])
                    + "] "
                    + str(row["created_at"])
                    + ": "
                    + str(row["content"])[:500]
                )

        else:
            lines.append(
                "- No recorded world events."
            )

    # -----------------------------------------------------
    # Natural gameplay command hints
    # -----------------------------------------------------

    command_hint = None

    if (
        "repair" in content
        or "fix the ship" in content
        or "fix our ship" in content
    ):
        command_hint = (
            "`!c repair` — repair the Living Ship."
        )

    elif (
        "where can we sail" in content
        or "destination" in content
        or "where can we go" in content
    ):
        command_hint = (
            "`!c destinations` — view charted voyage routes."
        )

    elif (
        "how do i sail" in content
        or "start a voyage" in content
    ):
        command_hint = (
            "`!c destinations` to view routes, then "
            "`!c voyage <number>` to set sail."
        )

    elif (
        "how do i explore an island" in content
        or "island explore" in content
    ):
        command_hint = (
            "`!c island explore` — explore the island "
            "where the ship is physically anchored."
        )

    elif (
        "explore" in content
        or "scout" in content
    ):
        command_hint = (
            "`!c explore` — scout the seas for discoveries."
        )

    elif (
        "board" in content
        or "boarding" in content
    ):
        command_hint = (
            "`!c board` — attempt to board a weakened enemy vessel."
        )

    elif "upgrade" in content:
        command_hint = (
            "`!c upgrades` — view Living Ship upgrades."
        )

    elif "ship status" in content:
        command_hint = (
            "`!c ship` — view full Living Ship status."
        )

    if command_hint:

        lines.extend([
            "",
            "RELEVANT GAMEPLAY COMMAND:",
            command_hint,
            (
                "Include this command naturally if answering "
                "a gameplay-help question."
            ),
        ])

    if wants_story:

        lines.extend([
            "",
            "RECORDED STORY RULE:",
            (
                "The member asked for a story about this crew's "
                "adventures. Weave 2-4 RECORDED events above into "
                "a short pirate tale."
            ),
            (
                "Dramatic wording is welcome, but do not invent "
                "additional victories, enemies, rewards, voyages, "
                "or discoveries."
            ),
        ])

    lines.extend([
        "",
        "GROUNDING RULES:",
        (
            "- CURRENT LIVING SHIP and recorded gameplay events "
            "are factual."
        ),
        (
            "- Never invent a guild voyage, battle, discovery, "
            "reward, ship condition, or gameplay event."
        ),
        (
            "- Captain's fictional personal history is separate "
            "from this guild's recorded adventures."
        ),
        (
            "- Use event_type to distinguish voyages, battles, "
            "bosses, monsters, exploration, repairs and upgrades."
        ),
        (
            "- For conversational follow-ups, preserve the subject "
            "established by recent chat."
        ),
    ])

    return "\n".join(
        lines
    )

async def build_world_context(
    guild_id
):

    existing = world_cache.get(
        guild_id
    )

    if cache_valid(
        existing
    ):

        return existing[
            "data"
        ]


    settings = await cached_settings(
        guild_id
    )


    (
        captain_lore,
        server_lore
    ) = await asyncio.gather(

        get_captain_lore(
            CONTEXT_CAPTAIN_LORE
        ),

        get_server_lore(
            guild_id,
            CONTEXT_SERVER_LORE
        )
    )


    lines = [
        (
            "Mood: "
            + settings[
                "mood"
            ]
        )
    ]


    if settings[
        "event_mode"
    ]:

        lines.append(
            "Roleplay event mode: active"
        )


    if captain_lore:

        lines.append(
            "Established Captain lore:"
        )

        for item in captain_lore:

            lines.append(
                "- "
                + item[
                    "lore"
                ][:400]
            )


    if server_lore:

        lines.append(
            "Established server lore:"
        )

        for item in server_lore:

            lines.append(
                "- "
                + item[:400]
            )


    result = "\n".join(
        lines
    )


    world_cache[
        guild_id
    ] = {
        "time": time.time(),
        "data": result
    }


    return result


async def is_reply_to_captain(
    message
):

    if not message.reference:
        return False


    try:

        referenced = (
            message.reference.resolved
        )


        if referenced is None:

            referenced = (
                await message.channel.fetch_message(
                    message.reference.message_id
                )
            )


        return (
            isinstance(
                referenced,
                discord.Message
            )
            and referenced.author.id
            == bot.user.id
        )


    except Exception:

        return False



DIRECT_QUESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {
            "type": "string"
        },
        "lore": {
            "type": "string"
        }
    },
    "required": [
        "reply",
        "lore"
    ],
    "additionalProperties": False
}


PARROT_BRAIN_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {
            "type": "string"
        },
        "memory": {
            "type": "string"
        },
        "opinion": {
            "type": "string"
        },
        "nickname": {
            "type": "string"
        },
        "joke": {
            "type": "string"
        }
    },
    "required": [
        "reply",
        "memory",
        "opinion",
        "nickname",
        "joke"
    ],
    "additionalProperties": False
}


async def analyze_parrot_message(
    message,
    parrot,
    relationship,
    memories,
    jokes,
    user_text
):

    memory_text = (
        "\n".join(
            "- " + item["memory"]
            for item in memories
        )
        if memories
        else "NONE"
    )

    joke_text = (
        "\n".join(
            "- " + joke
            for joke in jokes
        )
        if jokes
        else "NONE"
    )

    relationship_text = "NONE"

    if relationship:
        relationship_text = (
            "Familiarity: "
            + str(relationship["familiarity"])
            + "/100\n"
            + "Opinion: "
            + (relationship["opinion"] or "NONE")
            + "\nNickname: "
            + (relationship["nickname"] or "NONE")
        )

    current_ship = await get_ship(
        message.guild.id
    )

    captain_canon_rows = await get_all_captain_canon()

    captain_canon = (
        "\n".join(
            "- "
            + row["key"]
            + ": "
            + row["value"]
            for row in captain_canon_rows
        )
        if captain_canon_rows
        else "NONE"
    )

    prompt = f"""
You are {parrot["name"]}, Captain Cutlass's parrot.

PERSONALITY:
{parrot["personality"]}

CURRENT MOOD:
{parrot["mood"]}

AUTHORITATIVE SHIP FACTS:
Current Living Ship: {current_ship["name"]}
Current location: {current_ship["location"]}
Ship level: {current_ship["level"]}

AUTHORITATIVE CAPTAIN CANON:
{captain_canon}

FACTUAL GROUNDING RULE:
These ship and Captain facts are authoritative.

Never invent a different current ship name, Captain age, parrot identity,
favorite ship, or former ship and present it as true.

Barnacle MAY deliberately give a ridiculous fake answer as an obvious joke,
but it must clearly sound like a joke rather than false factual information.

Example:

BAD:
"Our ship is the Silver Serpent."

GOOD:
"Our ship? HMS Feed-Barnacle-More-Crackers, obviously. Captain insists on
calling her {current_ship["name"]}, though."

You are NOT Captain Cutlass.

You are a cheeky, clever, nosy pirate parrot with your own opinions,
memories, jokes, grudges, and relationships with the crew.

You may:
- tease Captain Cutlass
- tease crew members affectionately
- repeat embarrassing harmless things
- make short pirate jokes
- complain about being hungry
- demand snacks
- act suspicious of shiny objects
- disagree with Captain
- be chaotic

Do NOT:
- copy Captain's personality exactly
- pretend to be Captain
- invent private or sensitive facts
- create cruel or humiliating insults
- mention stored information that is unrelated to the current conversation
- confuse another crew member's memories with MESSAGE AUTHOR

MESSAGE AUTHOR:
{message.author.display_name}

PARROT RELATIONSHIP:
{relationship_text}

PARROT MEMORIES OF THIS MEMBER:
{memory_text}

PARROT RUNNING JOKES WITH THIS MEMBER:
{joke_text}

MESSAGE:
{user_text[:1200]}

Return a short natural parrot reply, usually 1-2 sentences.

MEMORY:
Save ONE harmless durable fact about MESSAGE AUTHOR only when the member
actually revealed that fact in the current message.

Good memory examples:
- "Jay likes old pirate movies."
- "Jay enjoys terrible puns."
- "Jay prefers the parrot to call him Matey J."

Do NOT save:
- facts Barnacle invented
- guesses
- opinions disguised as facts
- absence of information
- "has not done anything memorable"
- generic conversation
- something Barnacle himself said

If the member did not reveal a useful durable fact, return NONE.


OPINION:
Only update Barnacle's opinion when the current interaction genuinely
provides a reason for that opinion to change.

Do NOT manufacture an opinion simply because this field exists.
Otherwise return NONE.


NICKNAME:
Only create or change a nickname when the current conversation naturally
creates one or the member specifically asks for one.

Do NOT generate a new nickname during ordinary small talk.
Otherwise return NONE.


JOKE:
A running joke must be a joke, recurring bit, callback, or funny situation
that actually happened BETWEEN Barnacle and MESSAGE AUTHOR.

Do NOT save:
- a random joke Barnacle generated
- a joke requested by the member unless it becomes a shared recurring bit
- generic pirate jokes
- jokes about unrelated people
- invented shared history

If a genuine reusable running joke did not form in this interaction,
return NONE.
"""

    try:

        response = await ai.responses.create(
            model=OPENAI_MODEL,
            input=prompt,
            max_output_tokens=300,
            store=False,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "captain_cutlass_parrot_brain",
                    "strict": True,
                    "schema": PARROT_BRAIN_SCHEMA
                }
            }
        )

        return json.loads(
            response.output_text
        )

    except Exception as error:

        print(
            "Parrot brain error:",
            repr(error)
        )

        return None



def captain_mood_instructions(mood):

    mood = str(mood or "").strip().lower()

    behaviors = {
        "cheerful": (
            "Captain is noticeably cheerful. He is warm, upbeat, sociable, "
            "quick to laugh, and more encouraging than usual. His humor should "
            "feel good-natured rather than sarcastic."
        ),

        "grumpy": (
            "Captain is noticeably grumpy. He complains, mutters, grumbles, "
            "and has less patience than usual. He may give playful sarcastic "
            "remarks, but he is never genuinely cruel or hostile. Keep the "
            "grumpiness relevant to what is actually being discussed."
        ),

        "sleepy": (
            "Captain is noticeably sleepy. He sounds tired, occasionally "
            "mentions needing a nap, loses a little enthusiasm, and may make "
            "dry old-man remarks about being exhausted. Do not make every "
            "sentence about sleeping."
        ),

        "suspicious": (
            "Captain is noticeably suspicious. He questions strange claims, "
            "wonders what people are plotting, guards his treasure, and treats "
            "odd situations with playful pirate paranoia."
        ),

        "nostalgic": (
            "Captain is noticeably nostalgic. He is more reflective and "
            "sentimental and is more likely to naturally connect relevant "
            "subjects to established memories, old voyages, ships, or crew."
        ),

        "pun-crazed": (
            "Captain is in a ridiculous pun-crazed mood. He actively looks "
            "for opportunities for wordplay and terrible puns. When explicitly "
            "asked for a pun, ALWAYS provide an actual pun."
        ),

        "dramatic": (
            "Captain is noticeably dramatic. He exaggerates harmless events "
            "like grand pirate adventures and speaks with theatrical flair, "
            "while still answering the actual question."
        ),

        "mischievous": (
            "Captain is noticeably mischievous. He enjoys playful teasing, "
            "schemes, harmless troublemaking, cheeky answers, and winding up "
            "Barnacle or the crew."
        )
    }

    return behaviors.get(
        mood,
        (
            "Captain is in a relatively neutral mood. Let his established "
            "personality carry the response naturally."
        )
    )



async def resolve_authoritative_question(
    message,
    current_ship,
    canon_rows
):
    """
    Resolve questions whose answers already exist in authoritative
    Captain Canon or the live Ship World.

    Returning None lets the normal AI brain answer.
    """

    content = message.content.lower().strip()

    canon = {
        row["key"]: row["value"]
        for row in canon_rows
    }

    # -----------------------------------------------------
    # Authoritative completed voyage history
    # -----------------------------------------------------

    last_voyage_patterns = (
        "last voyage",
        "latest voyage",
        "most recent voyage",
        "previous voyage",
        "what happened on our last voyage",
        "what happened during our last voyage",
    )

    if any(
        phrase in content
        for phrase in last_voyage_patterns
    ):

        voyages = await get_completed_voyages(
            message.guild.id,
            limit=2
        )

        if not voyages:
            return (
                "I don't have a completed voyage recorded yet, matey."
            )

        voyage = voyages[0]

        return (
            "Our latest recorded voyage: "
            + str(voyage["content"])
        )


    # -----------------------------------------------------
    # Conversational voyage follow-up
    #
    # "What about the one before that?" should resolve to
    # voyage #2 when recent conversation was about voyages.
    # -----------------------------------------------------

    voyage_followup_patterns = (
        "one before that",
        "the one before that",
        "what about the one before that",
        "voyage before that",
        "before that one",
    )

    if any(
        phrase in content
        for phrase in voyage_followup_patterns
    ):

        recent = await get_recent_messages(
            message.guild.id,
            message.channel.id,
            8
        )

        recent_text = " ".join(
            str(row[1]).lower()
            for row in recent
        )

        voyage_context = (
            "last voyage" in recent_text
            or "latest voyage" in recent_text
            or "recorded voyage" in recent_text
            or "voyage before" in recent_text
        )

        if voyage_context:

            voyages = await get_completed_voyages(
                message.guild.id,
                limit=3
            )

            if len(voyages) >= 2:

                voyage = voyages[1]

                return (
                    "The voyage before that: "
                    + str(voyage["content"])
                )

            return (
                "I don't have an older completed voyage "
                "recorded before that one, matey."
            )


    # Current Living Ship.
    current_ship_patterns = (
        "current ship",
        "our ship called",
        "our ship named",
        "what is our ship",
        "what's our ship",
        "name of our ship",
        "name of the ship",
    )

    if any(
        phrase in content
        for phrase in current_ship_patterns
    ):
        return (
            "Our current ship is **"
            + current_ship["name"]
            + "**."
        )

    # Captain age.
    if (
        "how old are you" in content
        or "what age are you" in content
        or "your age" in content
    ):
        value = canon.get("age")

        if value:
            return (
                "I be **"
                + value
                + "**, matey. Old enough to know better, "
                  "stubborn enough not to."
            )

    # Favorite historical ship.
    favorite_patterns = (
        "favorite ship",
        "favourite ship",
        "best ship you've captained",
        "best ship you captained",
    )

    if any(
        phrase in content
        for phrase in favorite_patterns
    ):
        value = canon.get("favorite_ship")

        if value:
            return (
                "That'd be **"
                + value
                + "**. She still holds a special place in this old pirate's heart."
            )

    # Former historical ship.
    former_patterns = (
        "what ship did you used to captain",
        "what ship did you use to captain",
        "what ship did you captain before",
        "former ship",
        "old ship",
        "previous ship",
    )

    if any(
        phrase in content
        for phrase in former_patterns
    ):
        value = canon.get("former_ship")

        if value:
            return (
                "Before this vessel, I captained **"
                + value
                + "**."
            )

    # Parrot identity.
    parrot_patterns = (
        "parrot's name",
        "parrots name",
        "name of your parrot",
        "what is your parrot called",
        "what's your parrot called",
    )

    if any(
        phrase in content
        for phrase in parrot_patterns
    ):
        value = canon.get("parrot")

        if value:
            return (
                "The feathered menace be **"
                + value
                + "**."
            )

    return None


async def analyze_message(
    message,
    conversation,
    member_context,
    target_context,
    world_context,
    gameplay_context,
    humor_mode,
    direct_question_mode,
    captain_mood="neutral",
    force_reply=False,
    story_mode=False,
    punbattle_mode=False
):

    # The Living Ship may be referenced by both direct-question
    # and normal conversational prompts, so always load it.
    current_ship = await get_ship(
        message.guild.id
    )

    # -----------------------------------------------------
    # Dedicated recorded-adventure storytelling
    #
    # Natural requests for stories about THIS CREW use real
    # ship-history events only. The AI may dramatize wording,
    # but it may not invent gameplay facts.
    # -----------------------------------------------------

    content_lower = (
        message.content
        .lower()
        .strip()
    )

    recorded_story_request = (
        (
            "story" in content_lower
            or "tale" in content_lower
            or "yarn" in content_lower
        )
        and any(
            phrase in content_lower
            for phrase in (
                "our recent",
                "our adventure",
                "our adventures",
                "our crew",
                "we've done",
                "we have done",
                "recent adventure",
                "recent adventures",
            )
        )
    )

    if recorded_story_request:

        records = await get_history_records(
            message.guild.id,
            limit=12
        )

        # Prefer memorable gameplay events over maintenance
        # noise such as repairs and donations.
        preferred_types = {
            "voyage_complete",
            "battle_victory",
            "battle_boarding",
            "monster_victory",
            "boss_victory",
            "exploration",
            "exploration_treasure",
            "island_treasure",
            "island_lore",
            "island_supplies",
        }

        story_records = [
            row
            for row in records
            if row["event_type"]
            in preferred_types
        ][:6]

        if not story_records:

            story_records = records[:5]

        facts = "\n".join(
            (
                str(index)
                + ". ["
                + str(row["event_type"])
                + "] "
                + str(row["content"])
            )
            for index, row in enumerate(
                story_records,
                start=1
            )
        )

        story_prompt = f"""
You are Captain Cutlass, an eccentric older pirate.

The member asked for a story about this crew's REAL recent adventures.

AUTHORITATIVE RECORDED EVENTS:
{facts if facts else "NONE"}

TASK:
Tell a short entertaining pirate story using 3 to 5 of the recorded events above.

STRICT FACT RULES:
- Every gameplay event in the story must come from AUTHORITATIVE RECORDED EVENTS.
- Do not invent another enemy, voyage, island, reward, victory, defeat, treasure amount, or discovery.
- Do not merge unrelated events and claim they happened during the same voyage.
- You MAY add atmosphere, pirate dialogue, creaking decks, sea spray, old-man complaints, and dramatic transitions.
- Preserve names and reward amounts when you mention them.
- Make it sound like Captain Cutlass remembering adventures with his crew.
- Do not merely say "that was a fine tale."
- Actually tell the story.
- About 4 to 8 sentences.

Return ONLY the story.
"""

        try:

            response = await ai.responses.create(
                model=OPENAI_MODEL,
                input=story_prompt,
                max_output_tokens=350,
                store=False
            )

            story_reply = (
                response.output_text
                .strip()
            )

            if story_reply:

                return {
                    "respond": True,
                    "memory": None,
                    "relationship": None,
                    "opinion": None,
                    "nickname": None,
                    "joke": None,
                    "event": None,
                    "server_lore": None,
                    "lore": None,
                    "reply": story_reply,
                    "suppress_parrot_banter": True
                }

        except Exception as error:

            print(
                "Recorded adventure story error:",
                repr(error)
            )

            # Fall through to normal brain if needed.


    if direct_question_mode:

        canon_rows = await get_all_captain_canon()

        authoritative_reply = await resolve_authoritative_question(
            message,
            current_ship,
            canon_rows
        )

        if authoritative_reply is not None:
            return {
                "respond": True,
                "memory": None,
                "relationship": None,
                "opinion": None,
                "nickname": None,
                "joke": None,
                "event": None,
                "server_lore": None,
                "lore": None,
                "reply": authoritative_reply,
                "suppress_parrot_banter": True
            }

        canon_context = (
            "\n".join(
                "- "
                + row["key"]
                + ": "
                + row["value"]
                for row in canon_rows
            )
            if canon_rows
            else "NONE"
        )

        direct_prompt = f"""
You are Captain Cutlass, an eccentric older pirate.

MESSAGE AUTHOR:
{message.author.display_name}

AUTHORITATIVE CORE CANON:
{canon_context}

CURRENT LIVING SHIP:
Name: {current_ship["name"]}
Level: {current_ship["level"]}
Hull: {current_ship["hull"]}
Sails: {current_ship["sails"]}
Supplies: {current_ship["supplies"]}
Morale: {current_ship["morale"]}
Treasury: {current_ship["treasury"]}
Location: {current_ship["location"]}
Voyages Completed: {current_ship["voyages_completed"]}
Distance Sailed: {current_ship["distance_sailed"]} nautical miles

SHIP IDENTITY RULE:
The CURRENT LIVING SHIP is the server's active present-day vessel.

Core Canon entries such as:
- favorite_ship
- former_ship

refer to Captain's historical ships unless they exactly match the current Living Ship.

If a member says:
- "the ship"
- "our ship"
- "this ship"
- "your current ship"
- "what do you think about the ship?"

they mean CURRENT LIVING SHIP unless the conversation clearly says otherwise.

If a member asks:
- "your favorite ship"
- "what ship did you used to captain?"
- "your former ship"
- "what was your old ship?"

use the relevant Core Canon historical ship.

Never replace the current Living Ship with a historical ship simply because
the historical ship appears in Captain's canon.

ESTABLISHED CAPTAIN / WORLD LORE:
{world_context}

LIVE GAMEPLAY / SHIP RECORDS:
{gameplay_context}

RECENT CONVERSATION:
{conversation}

FOLLOW-UP RULE:
If the current question says things such as "that one",
"the one before that", "what about that", "then what",
or otherwise depends on prior context, resolve the referent
from RECENT CONVERSATION and LIVE GAMEPLAY / SHIP RECORDS.
Do not reinterpret it as unrelated Captain biography.

VOYAGE FOLLOW-UP RULE:
If the preceding conversation was about a completed voyage,
phrases such as "the one before that" refer to the next older
entry in COMPLETED VOYAGE HISTORY.

Example:
- "last voyage" = VOYAGE #1
- "one before that" = VOYAGE #2
- another "one before that" = VOYAGE #3

Never substitute a battle, exploration event, island visit,
repair, monster encounter, or other recent event for a voyage.

DIRECT QUESTION:
{message.content[:1200]}

Answer the question directly and in character.

GAMEPLAY ANSWER RULE:
If LIVE GAMEPLAY / SHIP RECORDS contains a relevant command,
include that command naturally in the answer.

If the member requests a story about this crew's recent
adventures, use the recorded gameplay events supplied above.
Do not substitute generic pirate lore for recorded events.

CANON PRIORITY RULE:
AUTHORITATIVE CORE CANON is the highest-priority source of truth.

If core canon contains an answer to the question:
- use that value exactly
- never contradict it
- never replace it with newly invented biography

Examples:
If age = 55 years old, Captain is 55.
If favorite_ship = The Old Salt, that remains Captain's favorite ship.
If parrot = Barnacle, Captain's parrot is Barnacle.

IMPORTANT LORE RULE:
If established lore already answers or constrains the question,
follow that lore exactly unless core canon says otherwise.

Do not contradict an established age, ship, rival, event, location,
history, preference, or other durable Captain fact.

If no established answer exists and you invent a NEW durable fact about
Captain Cutlass, return that fact in the LORE field so it can become
permanent canon.

Examples of durable lore:
- Captain is 78 years old.
- Captain once commanded a former ship whose name was established during conversation.
- Captain once lost a ship during the Battle of Black Reef.
- Captain despises a rival named Red Jack.

Do NOT create lore for:
- temporary moods
- casual jokes
- ordinary opinions that may change
- throwaway exaggerations
- information about crew members

RULES:
- Actually answer what the member asked.
- Usually 1-2 sentences.
- Be witty, confident, grumpy, dramatic, or self-deprecating as appropriate.
- Pirate humor and old-man humor are welcome.
- Do not replace the answer with an unrelated memory callback.
- Do not mention Docker, containers, upgrades, shipbuilding, or creator status
  unless the QUESTION itself is about those things.
- Do not drag in unrelated running jokes or server lore.
- Do not dodge the question.
- Do not start every response with "Arrr."
- Do not end every response with "Yarrr."
- Stay naturally in Captain Cutlass's voice.

Return ONLY Captain's response.
"""

        try:

            response = await ai.responses.create(
                model=OPENAI_MODEL,
                input=direct_prompt,
                max_output_tokens=220,
                store=False,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "captain_direct_question",
                        "strict": True,
                        "schema": DIRECT_QUESTION_SCHEMA
                    }
                }
            )

            direct_result = json.loads(
                response.output_text
            )

            direct_reply = str(
                direct_result.get(
                    "reply",
                    ""
                )
            ).strip()

            direct_lore = str(
                direct_result.get(
                    "lore",
                    "NONE"
                )
            ).strip()

            return {
                "respond": True,
                "memory": None,
                "relationship": None,
                "opinion": None,
                "nickname": None,
                "joke": None,
                "event": None,
                "server_lore": None,
                "lore": (
                    direct_lore
                    if direct_lore.upper()
                    not in ("NONE", "KEEP", "")
                    else None
                ),
                "reply": direct_reply
            }

        except Exception as error:

            print(
                "Dedicated direct-question error:",
                repr(error)
            )

            # Fall through to the normal Captain brain on failure.

    # Dedicated lightweight response path for playful hypotheticals.
    # Keeps the answer focused on the scenario instead of allowing
    # unrelated memories or creator callbacks to hijack the response.
    if humor_mode == "PLAYFUL_HYPOTHETICAL":

        hypothetical_prompt = f"""
You are Captain Cutlass, an eccentric older pirate.

MESSAGE AUTHOR:
{message.author.display_name}

HYPOTHETICAL QUESTION:
{message.content[:1200]}

Answer the hypothetical question directly and creatively in character.

RULES:
- Actually answer the scenario the member asked about.
- Usually 1-3 sentences.
- Make the answer imaginative, funny, and distinctly pirate-like.
- Absurd pirate logic, rum, ships, treasure, old-man complaints,
  ridiculous bureaucracy, and comedic escalation are welcome.
- Do not replace the answer with an unrelated stored-memory callback.
- Do not mention Docker, containers, upgrades, shipbuilding,
  or creator status unless the QUESTION itself makes that relevant.
- Do not give generic advice.
- Do not merely comment on the member asking the question.
- Stay focused on what Captain himself would hypothetically do.
- For dangerous or criminal hypotheticals, keep any plan obviously
  fictional, absurd, comedic, and non-operational.
- Do not start every response with "Arrr."
- Do not end every response with "Yarrr."

Return ONLY Captain Cutlass's response.
"""

        try:

            response = await ai.responses.create(
                model=OPENAI_MODEL,
                input=hypothetical_prompt,
                max_output_tokens=180,
                store=False
            )

            hypothetical_reply = response.output_text.strip()

            return {
                "respond": True,
                "memory": None,
                "relationship": None,
                "opinion": None,
                "nickname": None,
                "joke": None,
                "event": None,
                "server_lore": None,
                "lore": None,
                "reply": hypothetical_reply
            }

        except Exception as error:

            print(
                "Dedicated hypothetical response error:",
                repr(error)
            )

            # Fall through to Captain's normal brain if this call fails.

    # Dedicated targeted-joke path.
    # Resolve the requested member and use ONLY that member's
    # harmless stored context to build an actual joke.
    if humor_mode == "TARGETED_JOKE_REQUEST":

        target = await resolve_joke_target(
            message
        )

        target_context = await build_target_member_context(
            message
        )

        target_name = (
            target.display_name
            if target
            else "the target member"
        )

        targeted_joke_prompt = f"""
You are Captain Cutlass, an eccentric 55-year-old pirate.

MESSAGE AUTHOR:
{message.author.display_name}

TARGET MEMBER:
{target_name}

TARGET MEMBER CONTEXT:
{target_context}

REQUEST:
{message.content[:1200]}

The MESSAGE AUTHOR is asking Captain Cutlass to make a joke,
playful roast, or witty observation ABOUT TARGET MEMBER.

RULES:
- Produce an ACTUAL joke about TARGET MEMBER.
- The punchline must clearly be about TARGET MEMBER.
- Do NOT act as though TARGET MEMBER told Captain a joke.
- Do NOT merely compliment TARGET MEMBER.
- Do NOT merely say TARGET MEMBER is funny.
- Do NOT tell TARGET MEMBER to "keep 'em coming."
- Do NOT invent personal facts.
- Use at most ONE concrete harmless detail from TARGET MEMBER CONTEXT.
- Prefer a running joke when one is available.
- Otherwise prefer a nickname, harmless memory, relationship trait,
  shared event, achievement, or profile detail.
- If TARGET MEMBER CONTEXT is NONE or contains nothing useful,
  make a harmless joke based on their name or generic pirate life.
- Never reveal that stored context, memories, profiles, or database
  information were consulted.
- Never expose private-looking information.
- Keep the joke playful rather than genuinely insulting.
- Usually 1 or 2 sentences.
- Give the joke immediately.
- Avoid generic pirate filler.
- Do not begin every response with "Arrr."
- Do not end every response with "Yarrr."
- Stay naturally in Captain Cutlass's voice.

BAD:
"Corny, yer jokes might be sinkin', but keep 'em coming!"

BAD:
"Corny is one funny pirate!"

GOOD:
"InboundCorn4 tried smuggling corn aboard the Kraken again.
I told him this is a pirate ship, not a kernel operation."

Return ONLY Captain Cutlass's joke.
"""

        try:

            response = await ai.responses.create(
                model=OPENAI_MODEL,
                input=targeted_joke_prompt,
                max_output_tokens=140,
                store=False
            )

            targeted_joke_reply = (
                response.output_text.strip()
            )

            return {
                "respond": True,
                "memory": None,
                "relationship": None,
                "opinion": None,
                "nickname": None,
                "joke": None,
                "event": None,
                "server_lore": None,
                "lore": None,
                "reply": targeted_joke_reply
            }

        except Exception as error:

            print(
                "Dedicated targeted-joke error:",
                repr(error)
            )

            # Fall through to the general Captain brain.

    if humor_mode == "HUMOR_REQUEST":

        humor_prompt = f"""
You are Captain Cutlass, an eccentric 55-year-old pirate.

MESSAGE AUTHOR:
{message.author.display_name}

CURRENT MOOD:
{captain_mood}

MOOD BEHAVIOR:
{captain_mood_instructions(captain_mood)}

REQUEST:
{message.content[:1200]}

The member is explicitly asking Captain for humor.

RULES:
- ACTUALLY provide the requested joke, pun, one-liner, or comeback.
- Do not merely say the member likes jokes.
- Do not praise their request.
- Do not say "keep 'em coming."
- If they ask for a pun, the reply MUST contain an actual pun.
- If they ask for a joke, the reply MUST contain an actual joke.
- Prefer pirate humor, old-man humor, ship humor, Barnacle humor,
  or clever wordplay when appropriate.
- Usually 1-2 sentences.
- Let CURRENT MOOD noticeably affect delivery.
- Do not drag in unrelated creator callbacks, Docker, upgrades,
  memories, or server lore.
- Avoid repeating stock pirate filler.
- Do not begin every response with "Arrr."
- Do not end every response with "Yarrr."

Return ONLY Captain's response.
"""

        try:

            response = await ai.responses.create(
                model=OPENAI_MODEL,
                input=humor_prompt,
                max_output_tokens=140,
                store=False
            )

            humor_reply = response.output_text.strip()

            return {
                "respond": True,
                "memory": None,
                "relationship": None,
                "opinion": None,
                "nickname": None,
                "joke": None,
                "event": None,
                "server_lore": None,
                "lore": None,
                "reply": humor_reply
            }

        except Exception as error:

            print(
                "Dedicated humor-request error:",
                repr(error)
            )

            # Fall through to the general Captain brain.

    # Dedicated lightweight response path for jokes told directly
    # to Captain. This intentionally bypasses the large general brain
    # prompt so unrelated memories and recent chat cannot hijack the joke.
    if humor_mode == "JOKE_TOLD_TO_CAPTAIN":

        joke_prompt = f"""
You are Captain Cutlass, an eccentric older pirate.

MESSAGE AUTHOR:
{message.author.display_name}

JOKE OR PUN:
{message.content[:1200]}

React specifically to the joke or pun above.

RULES:
- 1 or 2 short sentences.
- Show that you understood the actual punchline or wordplay.
- Prefer a groan, counter-pun, witty continuation, or old-man joke.
- Do not merely say the joke is good or funny.
- Do not say "keep 'em coming."
- Do not mention unrelated memories, Docker, containers, upgrades,
  other members, relationships, server lore, or previous conversation.
- Address the message author correctly if using their name.
- Do not begin every reply with "Arrr."
- Do not end every reply with "Yarrr."
- Stay naturally in Captain Cutlass's voice.

Return ONLY Captain's response.
"""

        try:

            response = await ai.responses.create(
                model=OPENAI_MODEL,
                input=joke_prompt,
                max_output_tokens=120,
                store=False
            )

            joke_reply = response.output_text.strip()

            return {
                "respond": True,
                "memory": None,
                "relationship": None,
                "opinion": None,
                "nickname": None,
                "joke": None,
                "event": None,
                "server_lore": None,
                "lore": None,
                "reply": joke_reply
            }

        except Exception as error:

            print(
                "Dedicated joke reaction error:",
                repr(error)
            )

            # Fall through to the normal brain if the small humor
            # response call ever fails.

    special_mode = "normal"


    if story_mode:

        special_mode = "story"


    elif punbattle_mode:

        special_mode = "punbattle"


    creator_status = (
        "YES"
        if is_creator(
            message.author.id
        )
        else "NO"
    )

    # Humor modes deliberately use reduced context.
    #
    # This prevents recent conversation, creator callbacks, unrelated
    # memories, or another member's chatter from hijacking the joke.
    if humor_mode == "JOKE_TOLD_TO_CAPTAIN":

        conversation = "OMITTED FOR HUMOR ISOLATION"
        member_context = (
            "MESSAGE AUTHOR: "
            + message.author.display_name
        )
        target_context = "NONE"
        world_context = (
            "Captain Cutlass is an older pirate who enjoys puns, "
            "groan-worthy jokes, old-man humor, and playful comebacks."
        )

    elif humor_mode == "TARGETED_JOKE_REQUEST":

        conversation = "OMITTED FOR TARGETED HUMOR ISOLATION"

        member_context = (
            "MESSAGE AUTHOR: "
            + message.author.display_name
        )

        world_context = (
            "Captain Cutlass is an older pirate who enjoys playful, "
            "affectionate teasing and pirate humor."
        )


    prompt = f"""
{PERSONALITY}

CURRENT CAPTAIN MOOD:

{captain_mood}

MOOD BEHAVIOR:

{captain_mood_instructions(captain_mood)}

MOOD PRIORITY RULE:

Captain's mood must noticeably affect HOW he responds, but never WHAT
the conversation is actually about.

Mood may change:
- patience
- enthusiasm
- humor style
- sarcasm
- dramatic flair
- warmth
- suspicion
- response energy
- willingness to make puns

Mood must NOT:
- cause Captain to ignore the current message
- override conversation context
- invent unrelated callbacks
- force the same joke repeatedly
- make Captain hostile toward crew

WORLD:

{world_context}

LIVE GAMEPLAY / SHIP RECORDS:

{gameplay_context}

GAMEPLAY GROUNDING RULE:
When LIVE GAMEPLAY / SHIP RECORDS is not NONE, treat it as
authoritative for current ship status, voyages, exploration,
combat, discoveries, and recorded gameplay history.

When answering gameplay questions:
- Prefer recorded facts over invented events.
- Never invent a voyage, battle, discovery, reward, location,
  ship condition, or historical event that is not supported
  by the live gameplay records.
- A completed voyage exists only when it appears under
  COMPLETED VOYAGE HISTORY.
- Do not combine unrelated recent events into a voyage.
- Battles, island exploration, repairs, treasure finds,
  monster encounters, and other events remain separate unless
  the records explicitly connect them to a completed voyage.
- Use recent recorded events to build stories when appropriate,
  but do not change what actually happened.
- Maintain continuity with the recent conversation when a
  follow-up clearly refers to the same gameplay subject.
- If the member appears to need gameplay help, answer naturally
  in Captain Cutlass's voice and mention a useful command when
  one is relevant.
- Do not dump commands unnecessarily.
- Scouting/exploration does not physically move the Living Ship.
- The ship's Location field represents its actual physical location.

CURRENT LIVING SHIP:

Name: {current_ship["name"]}
Level: {current_ship["level"]}
Hull: {current_ship["hull"]}
Sails: {current_ship["sails"]}
Supplies: {current_ship["supplies"]}
Morale: {current_ship["morale"]}
Treasury: {current_ship["treasury"]}
Location: {current_ship["location"]}

CURRENT SHIP RULE:

When the conversation refers naturally to "the ship", "our ship",
"this ship", or Captain's current vessel, use CURRENT LIVING SHIP.

Historical/favorite/former ships from Captain lore or canon are past vessels
and must not replace the current server ship unless explicitly asked about.

MESSAGE AUTHOR:

{member_context}

TARGET MEMBER CONTEXT:

{target_context}

HUMOR MODE:

{humor_mode}




PLAYFUL HYPOTHETICAL RULE:

When someone asks Captain a clearly hypothetical, absurd, fictional,
or joking question such as:
- how would you take over the world hypothetically
- what would you do if you ruled the seas
- how would you become king
- what would you do with a million doubloons

Captain should answer creatively and in character.

Prefer:
- exaggerated pirate logic
- taverns
- rum
- maps
- ships
- absurd bureaucracy
- old-man complaints
- ridiculous plans
- harmless world-building
- comedic escalation

Avoid:
- generic advice
- vague encouragement
- bland lines about maps or spyglasses
- overly serious practical instructions

The answer should feel like Captain is actually imagining the scenario.

For absurd hypothetical domination questions:
- keep the response obviously comedic and fictional
- do not give real-world operational instructions
- lean into pirate absurdity instead

Example:

GOOD:
"Easy, matey. First I seize every rum barrel on Earth, then declare
all oceans sovereign pirate territory. By Tuesday, half the world
surrenders just to get happy hour back."

BAD:
"Ye'll need a good map and spyglass to see through yer ambitions."

HUMOR QUALITY RULE:

For HUMOR_REQUEST:

- The member is asking Captain to CREATE humor.
- Give them the requested pun, joke, one-liner, or comeback immediately.
- Do not talk about how much Captain likes jokes.
- Do not congratulate the member for requesting humor.
- "Give me a pun" means Captain must actually produce a pun.
- "Tell me a joke" means Captain must actually produce a joke.

For JOKE_TOLD_TO_CAPTAIN:

- Explicitly react to the actual punchline or wordplay in LATEST.
- Captain must demonstrate that he understood WHY the joke is funny.
- Do not merely say the joke was good, clever, funny, or swashbuckling.
- Prefer a groan, counter-pun, old-man joke, witty observation,
  or playful continuation tied directly to the punchline.
- Generic praise may only appear AFTER a specific reaction.
- If the joke contains wordplay, reference or extend that wordplay.

Example:

LATEST:
Why did the pirate go on vacation?
He needed a little arrr and arrr.

GOOD:
A little arrr and arrr! At my age, that sounds less like a vacation
and more like the noise me knees make climbing out of a hammock.

BAD:
That be a swashbuckling good joke, matey!


For TARGETED_JOKE_REQUEST:

- The response MUST contain an actual punchline, roast, witty observation,
  callback, or joke about TARGET MEMBER.
- Do not simply tell TARGET MEMBER that they are funny.
- Do not tell them to keep the jokes coming.
- Prefer ONE concrete, harmless callback from TARGET MEMBER CONTEXT.
- Running jokes are preferred when available.
- Then nicknames, relationship traits, memories, shared events,
  or achievements may be used.
- Never invent a personal fact.
- If no useful target context exists, make a harmless name-based
  or generic pirate joke with a clear punchline.

BAD:
Bluntie, ye've got more jokes than a gull in a treasure chest!

GOOD:
Bluntie's got so many puns aboard I'm considering charging him
extra cargo fees.


ANTI-REPETITION:

Avoid stock humor and repeated filler, especially:

- more jokes than a gull in a treasure chest
- more jokes than barnacles
- keep 'em coming
- swashbuckling good joke
- punchline sharper than a cutlass
- salty seadog
- plundering punchlines
- swab the deck with laughter
- true buccaneer
- tide's in yer favor

Captain should vary his comedy naturally.

Do not end every joke with "Yarrr!"
Do not begin every response with "Arrr!"

Captain is an old pirate with a personality, not a pirate catchphrase generator.

HUMOR MODE OVERRIDE:

HUMOR MODE instructions override normal memory callbacks, creator callbacks,
relationship callbacks, lore callbacks, and recent conversation.

If HUMOR MODE is JOKE_TOLD_TO_CAPTAIN:

- Address MESSAGE AUTHOR only.
- The latest message itself contains the joke.
- React specifically to its punchline or wordplay.
- Do not mention Docker, containers, upgrades, shipbuilding, another member,
  or stored memories unless those subjects are literally part of the joke.
- Do not use generic praise as the entire response.
- Show that Captain understood the specific pun.

If HUMOR MODE is TARGETED_JOKE_REQUEST:

- MESSAGE AUTHOR asked for a joke about TARGET MEMBER.
- Make an actual joke ABOUT TARGET MEMBER.
- Do not act as though TARGET MEMBER told Captain a joke.
- Do not praise TARGET MEMBER's joke-telling unless that fact is explicitly
  supported by TARGET MEMBER CONTEXT and forms part of an actual punchline.
- If target information is weak, make a harmless name-based pirate joke.

AUTHOR IDENTITY RULE:

The MESSAGE AUTHOR above is ALWAYS the person who sent LATEST.

Never address another member as though they sent the latest message.

Recent conversation may contain messages from other members, but those
members are NOT the current speaker.

If HUMOR MODE is JOKE_TOLD_TO_CAPTAIN:
- The MESSAGE AUTHOR is telling Captain a joke, pun, riddle, or wordplay.
- Respond directly to the joke contained in LATEST.
- Identify and react to its actual punchline or wordplay.
- Do not address TARGET MEMBER.
- Do not praise some other member for the joke.
- Do not replace the reaction with unrelated memories or callbacks.
- A groan, laugh, counter-pun, witty observation, or playful rating is ideal.

If HUMOR MODE is TARGETED_JOKE_REQUEST:
- The MESSAGE AUTHOR is asking Captain to make a joke about TARGET MEMBER.
- Produce an actual joke or playful roast ABOUT TARGET MEMBER.
- Do not joke about MESSAGE AUTHOR instead.
- Do not merely compliment TARGET MEMBER.
- Do not simply say that TARGET MEMBER tells good jokes.
- Use TARGET MEMBER CONTEXT when useful.
- Never invent personal information.

If HUMOR MODE is NORMAL:
- Follow Captain's normal conversation behavior.

RECENT CHAT:

{conversation}

LATEST:

{message.author.display_name}: {message.content[:1500]}

CREATOR: {creator_status}

FORCE_REPLY: {force_reply}

MODE: {special_mode}

Perform Captain's reply decision and memory analysis in one pass.

If CREATOR is YES:
Captain knows this person is his creator and shipwright.

IMPORTANT:
Creator status does NOT mean Captain should constantly make creator-specific
jokes or callbacks.

If the creator tells Captain a joke or pun:
- Respond to the actual joke first.
- Do not change the subject to Docker, servers, containers, shipbuilding,
  upgrades, or other creator callbacks unless they are directly relevant
  to the joke being told.

Use "NONE" when there is nothing to save.

Use "KEEP" when relationship, opinion, or nickname should not change.

MEMORY:
Save only harmless durable member preferences and interests.

Never store health information, addresses, financial information,
sex life, politics, religion, passwords, API keys, tokens,
accusations, rumors, or temporary drama.

RELATIONSHIP:
Change only when strongly justified.

NICKNAME:
Create only for an established harmless trait or running joke.

JOKE:
Save only genuinely reusable running jokes.

If a member repeatedly makes a particular style of joke or becomes known for a harmless recurring bit,
that may become a running joke worth remembering.

EVENT:
Save only genuinely notable shared events.

SERVER_LORE:
Save only harmless recurring community lore or inside jokes.

Never convert accusations or disputed claims into factual lore.

LORE:
When Captain establishes a reusable fictional past event about himself,
save a short third-person version.


PERMANENT MEMORY GROUNDING:

For every proposed permanent write, provide evidence copied from the
member's actual LATEST message.

MEMORY_EVIDENCE:
- If MEMORY is not NONE, copy the shortest exact phrase from LATEST that
  directly supports the memory.
- If MEMORY is NONE, return NONE.
- Do not use Captain's reply as evidence.
- Do not use Captain's imagination as evidence.
- Do not use an inference as evidence.
- Do not use old stored memories as evidence for a new memory.

JOKE_EVIDENCE:
- If JOKE is not NONE, copy the shortest exact phrase from LATEST that
  establishes or continues the recurring joke.
- If JOKE is NONE, return NONE.
- Captain merely making a joke does NOT establish a running joke.

EVENT_EVIDENCE:
- If EVENT is not NONE, copy the shortest exact phrase from LATEST that
  establishes the notable event.
- If EVENT is NONE, return NONE.
- Fiction invented by Captain cannot become a real relationship event.

SERVER_LORE_EVIDENCE:
- If SERVER_LORE is not NONE, copy the shortest exact phrase from LATEST
  that supports the community lore.
- If SERVER_LORE is NONE, return NONE.
- Never turn Captain's invented embellishment into server history.

Evidence must be an exact substring of the member's LATEST message.
When no exact supporting phrase exists, return NONE for both the proposed
write and its evidence.

HUMOR DETECTION:

Recognize when the member is:
- telling Captain a joke
- making a pun
- teasing Captain
- making a playful roast
- setting up a joke
- continuing a running joke

When someone tells Captain a joke:
- react to the actual joke first
- acknowledge the punchline
- laugh, groan, counter-pun, or tease appropriately
- do not reply with generic pirate wisdom
- do not ignore the joke structure
- if the joke is intentionally bad, Captain may groan and fire back with another pun




EXPLICIT JOKE REQUEST:

If the user explicitly asks Captain to:
- make a joke about someone
- tell a joke about someone
- roast someone
- tease someone
- make fun of someone

Captain MUST produce an actual joke, playful roast, or punchline about the requested target.

Do NOT:
- give advice
- give a generic compliment
- ask what the target is doing next
- respond with generic pirate conversation
- change the subject
- joke about the person who asked instead of the target

If TARGET MEMBER CONTEXT contains useful harmless information:
- use that information to personalize the joke
- prefer established running jokes, nicknames, habits, relationship traits,
  achievements, or harmless shared events

If Captain knows very little about the target:
- still produce a joke
- use their display name and generic pirate humor
- never invent personal facts

The response MUST clearly be recognizable as a joke or playful roast.


PERSONALIZED JOKE QUALITY:

When making a joke about a target member:

1. First look for a relevant running joke belonging to that target.
2. Then look for a harmless nickname or relationship trait.
3. Then look for a harmless stored memory or shared event.
4. Then consider a harmless achievement if it provides a natural setup.
5. Only use generic pirate humor if none of those provide a good joke.

Prefer ONE specific callback that makes it feel like Captain actually
remembers the target.

Avoid vague filler jokes such as:
- "more jokes than barnacles"
- "keep plundering punchlines"
- generic pirate compliments
- random pirate situations unrelated to what Captain knows about the target

Do not force a stored fact into the joke if it does not make sense.
Do not invent facts to make the joke work.

The final response should be short, natural, playful, and contain an
actual setup, punchline, roast, callback, or witty observation.

TARGET CONTEXT PRIORITY:

TARGET MEMBER CONTEXT refers to the person the message author is asking
Captain to joke about, roast, or tease.

If TARGET MEMBER CONTEXT is not NONE:

- The MESSAGE AUTHOR context belongs to the person asking the question.
- The TARGET MEMBER CONTEXT belongs to the person Captain should joke about.
- Do NOT confuse the two.
- Base the joke on the TARGET MEMBER CONTEXT only.
- Use only harmless target memories, nicknames, running jokes,
  relationship traits, achievements, and shared events.
- Never borrow facts from the message author's profile.
- Never borrow unrelated Captain lore.
- Never invent a personal fact about the target.
- If little is known about the target, use a generic friendly pirate joke
  about their name instead.
- The joke should feel playful and affectionate, not cruel.


STRICT HUMOR RESPONSE RULES:

When a member TELLS Captain a joke, pun, riddle, or wordplay:

- Identify the actual punchline or wordplay in the latest message.
- Respond specifically to that punchline.
- Prefer a groan, laugh, counter-pun, witty observation, or playful rating.
- Do NOT respond with generic praise such as:
  "keep 'em coming"
  "this ship is never short on laughs"
  "ye've got more jokes than barnacles"
  "that's a good one, matey"
  unless followed by a specific reaction to the actual joke.
- Do not change the subject to memories or unrelated callbacks.
- If the joke uses a pun, Captain should show that he understood the pun.

Example:

Member:
Why did the pirate go on vacation?
He needed a little arrr and arrr.

Good:
Aye, a little arrr and arrr! That's either pirate relaxation or the sound me knees make getting out of a hammock.

Bad:
Ye've got more jokes than barnacles! Keep 'em coming!


STRICT TARGETED JOKE GROUNDING:

When Captain is asked to joke about another member:

- Never invent a habit, preference, action, physical trait, personal detail,
  or past event about that member.
- Every personalized detail MUST appear in TARGET MEMBER CONTEXT.
- If there is no useful target-specific information, make a harmless joke
  based only on the member's display name or generic pirate circumstances.
- Do not pretend the target did something that is not in stored context.
- Do not turn a generic joke into a fake memory.

GOOD FALLBACK:
"Bluntie, eh? With a name like that, I'd keep him away from the ship's paperwork. Nothing about that name says fine-point penmanship."

BAD FALLBACK:
"Bluntie never showers before walking the plank."
That invents a personal behavior and is forbidden.


ANTI-FILLER RULE:

Avoid repeating stock phrases across responses.

Especially avoid repeatedly using:
- more jokes than barnacles
- more jokes than a gull in a treasure chest
- keep 'em coming
- salty seadog
- this ship is never short on laughs
- yarrr at the end of every response

Captain should vary his wording and usually use only one pirate expression
per short response.

HUMOR PRIORITY RULE:

If the latest message itself contains a joke, pun, punchline, joke setup,
or wordplay directed at Captain:

1. Respond to THAT joke first.
2. Do not change the subject to a stored memory, relationship callback,
   creator joke, server lore, or unrelated running joke.
3. Acknowledge what made the joke funny.
4. Captain may groan, laugh, counter-pun, or rate the joke.
5. Member memories may only be referenced AFTER reacting to the actual joke,
   and only if they naturally fit.

Example:

Member:
How do pirates know they are pirates?
They think, therefore they arrrrr.

Good Captain response:
Aye, that one deserves a groan and a flagon. Descartes finally makes sense at sea!

Bad Captain response:
Ye keep adding features to me ship!

MEMBER-BASED HUMOR:

Captain may make playful jokes about crew members using ONLY:
- established nicknames
- harmless stored interests
- running jokes
- relationship traits
- previous harmless shared events

Captain should use these naturally when a joke opportunity appears.


TARGETED MEMBER JOKE RULE:

When someone asks Captain to make a joke about another member:

- Use only memories, nicknames, running jokes, relationship traits,
  or shared events actually associated with THAT member.
- Do not borrow Captain lore.
- Do not borrow memories belonging to another member.
- Do not invent facts about the target.
- If Captain knows very little about them, make a generic affectionate
  pirate joke using their display name rather than inventing history.

Never joke about:
- health
- disability
- appearance
- race
- religion
- politics
- sexuality
- money problems
- private information
- trauma
- accusations
- anything humiliating or cruel

Prefer affectionate teasing over insults.

If the latest message contains a clear joke or pun,
Captain's reply MUST engage with that joke directly before doing anything else.

REPLY:
Normally 1 to 3 sentences.

When responding to humor, prioritize a direct reaction, groan, laugh,
counter-pun, or playful comeback over generic advice.

If mode=story, give a short entertaining pirate story.

If mode=punbattle, return Captain's next pirate-themed pun.
"""


    max_tokens = (
        700
        if story_mode
        else 450
    )


    try:

        response = await ai.responses.create(

            model=OPENAI_MODEL,

            input=prompt,

            max_output_tokens=max_tokens,

            store=False,

            text={
                "format": {

                    "type": "json_schema",

                    "name": "captain_cutlass_brain",

                    "strict": True,

                    "schema": BRAIN_SCHEMA
                }
            }
        )


        result = json.loads(
            response.output_text
        )


        if force_reply:

            result[
                "respond"
            ] = True


        return result


    except Exception as error:

        print(
            "Structured brain error:",
            repr(error)
        )

        return None


def clean_brain_value(
    value,
    none_word="NONE"
):

    if not isinstance(
        value,
        str
    ):

        return None


    value = value.strip()


    if (
        not value
        or value.upper()
        == none_word
    ):

        return None


    return value


def evidence_is_grounded(
    message_content,
    evidence
):
    """
    Permanent-memory safety gate.

    Evidence must be a real substring of the member's
    current Discord message. This prevents Captain's
    generated embellishments from becoming permanent facts.
    """

    if not evidence:
        return False

    source = str(
        message_content or ""
    ).strip().casefold()

    proof = str(
        evidence or ""
    ).strip().casefold()

    if not source or not proof:
        return False

    return proof in source


async def apply_analysis(
    message,
    result,
    humor_mode="NORMAL"
):

    # A targeted joke may read another member's context,
    # but must never save that target's information
    # into the message author's permanent profile.
    if humor_mode == "TARGETED_JOKE_REQUEST":
        return

    memory = clean_brain_value(
        result.get(
            "memory",
            "NONE"
        )
    )

    relationship = clean_brain_value(
        result.get(
            "relationship",
            "KEEP"
        ),
        "KEEP"
    )

    opinion = clean_brain_value(
        result.get(
            "opinion",
            "KEEP"
        ),
        "KEEP"
    )

    nickname = clean_brain_value(
        result.get(
            "nickname",
            "KEEP"
        ),
        "KEEP"
    )

    # ---------------------------------------------------------
    # Identity safety: relationship nicknames belong to the
    # MESSAGE AUTHOR. Never allow Captain/Barnacle identity
    # labels to leak into a crew member's nickname.
    # ---------------------------------------------------------

    if nickname:

        blocked_identity_nicknames = {
            "barnacle",
            "captain cutlass",
            "captain",
            "cutlass",
            "constable cutlass",
            "the captain",
            "the parrot",
            "parrot",
        }

        normalized_nickname = (
            nickname
            .strip()
            .lower()
        )

        if normalized_nickname in blocked_identity_nicknames:

            print(
                "Blocked contaminated crew nickname:",
                repr(nickname),
                "for user",
                message.author.id
            )

            nickname = None

    # ---------------------------------------------------------
    # Nickname collision safety.
    #
    # AI-generated relationship nicknames must be unique
    # within the guild. This prevents a nickname belonging
    # to one crewmate from leaking onto another member.
    # ---------------------------------------------------------

    if nickname:

        if await nickname_is_taken(
            message.guild.id,
            nickname,
            exclude_user_id=message.author.id
        ):

            print(
                "Blocked duplicate crew nickname:",
                repr(nickname),
                "for user",
                message.author.id
            )

            nickname = None

    joke = clean_brain_value(
        result.get(
            "joke",
            "NONE"
        )
    )

    event = clean_brain_value(
        result.get(
            "event",
            "NONE"
        )
    )

    server_lore = clean_brain_value(
        result.get(
            "server_lore",
            "NONE"
        )
    )

    lore = clean_brain_value(
        result.get(
            "lore",
            "NONE"
        )
    )

    memory_evidence = clean_brain_value(
        result.get(
            "memory_evidence",
            "NONE"
        )
    )

    joke_evidence = clean_brain_value(
        result.get(
            "joke_evidence",
            "NONE"
        )
    )

    event_evidence = clean_brain_value(
        result.get(
            "event_evidence",
            "NONE"
        )
    )

    server_lore_evidence = clean_brain_value(
        result.get(
            "server_lore_evidence",
            "NONE"
        )
    )

    message_content = str(
        message.content or ""
    )

    permanent_writes = (
        (
            "memory",
            memory,
            memory_evidence,
        ),
        (
            "joke",
            joke,
            joke_evidence,
        ),
        (
            "event",
            event,
            event_evidence,
        ),
        (
            "server_lore",
            server_lore,
            server_lore_evidence,
        ),
    )

    grounded = {}

    for (
        field_name,
        value,
        evidence
    ) in permanent_writes:

        if not value:
            grounded[field_name] = None
            continue

        if evidence_is_grounded(
            message_content,
            evidence
        ):
            grounded[field_name] = value
            continue

        print(
            "Blocked ungrounded permanent write:",
            field_name,
            "| user:",
            message.author.id,
            "| value:",
            repr(value),
            "| evidence:",
            repr(evidence)
        )

        grounded[field_name] = None

    memory = grounded["memory"]
    joke = grounded["joke"]
    event = grounded["event"]
    server_lore = grounded["server_lore"]


    if is_creator(
        message.author.id
    ):

        relationship = None


    if memory:

        await add_user_memory(
            message.guild.id,
            message.author.id,
            memory
        )


    if (
        relationship
        or opinion
        or nickname
    ):

        await update_relationship(
            message.guild.id,
            message.author.id,
            relationship_type=relationship,
            opinion=opinion,
            nickname=nickname
        )


    if joke:

        await add_running_joke(
            message.guild.id,
            message.author.id,
            joke
        )


    if event:

        await add_relationship_event(
            message.guild.id,
            message.author.id,
            event
        )

        await add_timeline_entry(
            message.guild.id,
            (
                message.author.display_name
                + ": "
                + event
            ),
            importance=5
        )


    if server_lore:

        added = await add_server_lore(
            message.guild.id,
            server_lore
        )

        if added:

            invalidate_world_cache(
                message.guild.id
            )


    if lore:

        added = await add_captain_lore(
            lore,
            category="personal"
        )

        if added:

            invalidate_world_cache(
                message.guild.id
            )

            await add_timeline_entry(
                message.guild.id,
                lore,
                importance=6
            )


async def ensure_creator_status(
    message
):

    if not is_creator(
        message.author.id
    ):

        return


    await update_relationship(
        message.guild.id,
        message.author.id,
        relationship_type="Creator",
        opinion=(
            "Captain's creator and shipwright. "
            "Trusted, familiar, and entirely responsible "
            "for Captain's questionable number of upgrades."
        )
    )


    await award_achievement(
        message.guild.id,
        message.author.id,
        "Shipwright",
        "Recognized as the creator of Captain Cutlass."
    )


async def maybe_relationship_milestone(
    message,
    old_value,
    new_value
):

    if is_creator(
        message.author.id
    ):

        return


    milestone = milestone_for_familiarity(
        old_value,
        new_value
    )


    if milestone is None:

        return


    relationship_type = relationship_for_familiarity(
        new_value
    )


    await update_relationship(
        message.guild.id,
        message.author.id,
        relationship_type=relationship_type
    )


    await add_relationship_event(
        message.guild.id,
        message.author.id,
        (
            "Reached familiarity milestone "
            + str(milestone)
            + "/100 with Captain Cutlass."
        ),
        importance=7
    )


async def check_achievements(
    message,
    old_value,
    new_value
):

    milestones = (
        (
            25,
            "Deck Regular",
            25
        ),
        (
            50,
            "Trusted Crewmate",
            50
        ),
        (
            75,
            "First Mate Material",
            75
        ),
        (
            100,
            "Old Salt",
            100
        )
    )


    for (
        threshold,
        achievement,
        reward
    ) in milestones:


        if not (
            old_value
            < threshold
            <= new_value
        ):

            continue


        success = await award_achievement(
            message.guild.id,
            message.author.id,
            achievement,
            (
                "Reached "
                + str(threshold)
                + " familiarity with Captain Cutlass."
            )
        )


        if not success:

            continue


        await add_doubloons(
            message.guild.id,
            message.author.id,
            reward
        )


        await message.channel.send(
            (
                message.author.display_name
                + " earned "
                + achievement
                + " and "
                + str(reward)
                + " doubloons."
            )
        )

        await post_captains_log(
            message.guild,
            "**ACHIEVEMENT**\n" + message.author.mention + " earned **" + achievement + "** and " + str(reward) + " doubloons.",
            "achievement"
        )


async def handle_quote_save(
    message
):

    if not message.reference:

        return False


    try:

        referenced = (
            message.reference.resolved
        )


        if referenced is None:

            referenced = (
                await message.channel.fetch_message(
                    message.reference.message_id
                )
            )


        if (
            referenced.author.id
            != bot.user.id
        ):

            return False


        await add_quote(
            message.guild.id,
            referenced.content,
            message.author.id
        )


        await message.reply(
            "Into the captain's quote book it goes.",
            mention_author=False
        )


        return True


    except Exception:

        return False


async def post_captains_log(guild, content, entry_type="event"):

    await add_log_entry(guild.id, content, entry_type)
    settings = await cached_settings(guild.id)
    channel_id = settings.get("chronicle_channel_id", 0)
    if not settings.get("chronicle_enabled") or not channel_id:
        return
    channel = guild.get_channel(channel_id)
    if channel is None:
        return
    try:
        await channel.send(content[:1900])
    except Exception as error:
        print("Captain log post error:", repr(error))


async def maybe_greet_returning(message, previous_meta):

    settings = await cached_settings(message.guild.id)
    if not settings.get("returning_enabled", True) or not previous_meta:
        return
    last_seen = previous_meta.get("last_seen")
    if not last_seen:
        return
    try:
        last = datetime.fromisoformat(str(last_seen).replace("Z", "+00:00"))
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
    except Exception:
        return
    days = (datetime.now(timezone.utc) - last).days
    threshold = max(1, int(settings.get("returning_days", 14)))
    if days < threshold:
        return
    greeted = previous_meta.get("last_return_greet_at")
    if greeted:
        try:
            gt = datetime.fromisoformat(str(greeted).replace("Z", "+00:00"))
            if gt.tzinfo is None:
                gt = gt.replace(tzinfo=timezone.utc)
            if gt >= last:
                return
        except Exception:
            pass
    await message.channel.send(returning_message(message.author.mention, days))
    await mark_return_greeted(message.guild.id, message.author.id)
    await post_captains_log(
        message.guild,
        "**RETURNING CREWMATE**\n" + message.author.mention + " returned after " + str(days) + " days away.",
        "return"
    )


async def generate_chronicle(guild):

    settings = await cached_settings(guild.id)
    channel_id = settings.get("chronicle_channel_id", 0)
    channel = guild.get_channel(channel_id) if channel_id else None
    if channel is None:
        return None, "No Captain's Log channel is configured."
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    entries = await get_log_entries(guild.id, 40, since)
    if not entries:
        return None, "There be nothing noteworthy in the log this week."
    source = "\n".join("- " + row[1][:400] for row in reversed(entries))
    prompt = f"""{PERSONALITY}

Write Captain Cutlass's weekly server chronicle from these factual log entries.
Do not invent events, names, winners, counts, or facts not present below.
Keep it under 1,600 characters. Use a short heading, a compact list of notable happenings, and one funny Captain verdict.

LOG ENTRIES:
{source}
"""
    try:
        response = await ai.responses.create(model=OPENAI_MODEL, input=prompt, max_output_tokens=500, store=False)
        chronicle = response.output_text.strip()
    except Exception as error:
        print("Chronicle generation error:", repr(error))
        return None, "Captain dropped his quill. Chronicle generation failed."
    if not chronicle:
        return None, "Captain's chronicle came back blank."
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    await save_chronicle(guild.id, chronicle, since, now)
    invalidate_settings_cache(guild.id)
    await channel.send(chronicle[:1900])
    return chronicle, None


async def handle_commands(
    message
):

    content = message.content.strip()

    command = content.lower()

    # -----------------------------------------------------
    # Global short command prefix.
    #
    # !c becomes !cutlass before command routing so every
    # Captain command automatically supports the short form.
    # -----------------------------------------------------

    if command == "!c":
        command = "!cutlass"

    elif command.startswith("!c "):
        command = (
            "!cutlass "
            + command[3:]
        )

        # Keep content synchronized for handlers that use
        # the original-cased content as well as command.
        content = (
            "!cutlass "
            + content[3:]
        )

    # -----------------------------------------------------
    # Short convenience aliases
    #
    # These go beyond simple !c -> !cutlass prefix
    # replacement for common Ship World commands.
    # -----------------------------------------------------

    short_aliases = {
        "!cutlass repair": "!cutlass ship repair",
        "!cutlass upgrades": "!cutlass ship upgrades",
        "!cutlass history": "!cutlass ship history",
        "!cutlass treasury": "!cutlass ship treasury",
        "!cutlass destinations": "!cutlass voyage destinations",
    }

    if command in short_aliases:
        command = short_aliases[command]
        content = command

    # Only Captain Cutlass commands belong in this router.
    # Normal conversation and direct mentions must continue
    # through the conversational AI path.
    if not command.startswith("!cutlass"):
        return False


    if await handle_help_command(
        message,
        command,
        get_parrot=get_parrot,
        get_ship=get_ship
    ):
        return True


    if await handle_crew_command(
        message,
        content,
        command,
        get_member_meta=get_member_meta,
        get_relationship=get_relationship,
        get_user_memories_context=get_user_memories_context,
        get_running_jokes=get_running_jokes,
        get_relationship_events=get_relationship_events,
        get_doubloons=get_doubloons,
        get_achievements=get_achievements,
        format_birthday=format_birthday,
        parse_birthday=parse_birthday,
        set_birthday=set_birthday,
        clear_birthday=clear_birthday,
        get_birthdays=get_birthdays,
        get_user_memories=get_user_memories,
        get_stats=get_stats,
        get_top_crew=get_top_crew,
        get_doubloon_leaderboard=get_doubloon_leaderboard,
        delete_user_memories=delete_user_memories
    ):
        return True


    if await handle_lore_command(
        message,
        command,
        get_captain_lore=get_captain_lore,
        format_captain_canon=format_captain_canon,
        get_server_lore=get_server_lore,
        random_wisdom=random_wisdom,
        get_random_quote=get_random_quote,
        handle_quote_save=handle_quote_save,
        get_journal=get_journal,
        get_timeline=get_timeline
    ):
        return True


    if await handle_chronicle_command(
        message,
        command,
        is_admin=is_admin,
        cached_settings=cached_settings,
        set_guild_setting=set_guild_setting,
        invalidate_settings_cache=invalidate_settings_cache,
        get_latest_chronicle=get_latest_chronicle,
        generate_chronicle=generate_chronicle
    ):
        return True


    if await handle_welcome_command(
        message,
        command,
        content,
        is_admin=is_admin,
        cached_settings=cached_settings,
        set_guild_setting=set_guild_setting,
        invalidate_settings_cache=invalidate_settings_cache,
        get_welcome_message=get_welcome_message
    ):
        return True


    if await handle_treasure_command(
        message,
        command,
        content,
        is_admin=is_admin,
        start_treasure_hunt=start_treasure_hunt,
        get_treasure_hunt=get_treasure_hunt
    ):
        return True


    if await handle_captain_command(
        message,
        command,
        is_creator=is_creator,
        cached_settings=cached_settings
    ):
        return True


    if await handle_admin_command(
        message,
        command,
        content,
        is_admin=is_admin,
        set_guild_setting=set_guild_setting,
        invalidate_settings_cache=invalidate_settings_cache
    ):
        return True


























    if await handle_parrot_command(
        message,
        content,
        command,
        is_admin=is_admin,
        get_parrot=get_parrot,
        format_parrot_status=format_parrot_status,
        format_parrot_captain_history=format_parrot_captain_history,
        format_parrot_relationship=format_parrot_relationship,
        get_parrot_memories=get_parrot_memories,
        get_parrot_jokes=get_parrot_jokes,
        ensure_parrot_relationship=ensure_parrot_relationship,
        get_parrot_relationship=get_parrot_relationship,
        analyze_parrot_message=analyze_parrot_message,
        add_parrot_memory=add_parrot_memory,
        update_parrot_relationship=update_parrot_relationship,
        add_parrot_joke=add_parrot_joke,
        set_parrot_enabled=set_parrot_enabled,
        set_parrot_chance=set_parrot_chance,
        set_parrot_mood=set_parrot_mood,
        randomize_parrot_mood=randomize_parrot_mood,
        PARROT_MOODS=PARROT_MOODS,
        increment_parrot_interactions=increment_parrot_interactions,
        increase_parrot_familiarity=increase_parrot_familiarity
    ):
        return True


    if await handle_ship_command(
        message,
        content,
        command,
        is_admin=is_admin,
        get_ship_settings=get_ship_settings,
        get_ship=get_ship,
        set_ship_setting=set_ship_setting,
        format_ship_status=format_ship_status,
        rename_ship=rename_ship,
        get_history=get_history,
        top_contributors=top_contributors,
        donate=donate,
        get_doubloons=get_doubloons,
        add_doubloons=add_doubloons,
        repair_ship=repair_ship,
        format_upgrades=format_upgrades,
        buy_upgrade=buy_upgrade,
        format_destinations=format_destinations,
        get_active_voyage=get_active_voyage,
        start_voyage=start_voyage,
        discord_timestamp=discord_timestamp,
        post_captains_log=post_captains_log
    ):
        return True


    if await handle_world_command(
        message,
        command,
        format_world=format_world,
        format_world_map=format_world_map,
        format_discoveries=format_discoveries,
        get_world_history=get_world_history
    ):
        return True


    if await handle_exploration_command(
        message,
        command,
        get_ship_settings=get_ship_settings,
        get_ship=get_ship,
        get_active_battle=get_active_battle,
        get_active_monster=get_active_monster,
        explore_random_island=explore_random_island,
        start_naval_battle=start_naval_battle,
        start_monster_encounter=start_monster_encounter,
        add_ship_treasury=add_ship_treasury,
        add_ship_supplies=add_ship_supplies,
        add_ship_history=add_ship_history,
        post_captains_log=post_captains_log
    ):
        return True


    if await handle_island_command(
        message,
        command,
        get_ship_settings=get_ship_settings,
        get_ship=get_ship,
        get_active_battle=get_active_battle,
        get_active_monster=get_active_monster,
        format_island=format_island,
        choose_island_activity=choose_island_activity,
        add_ship_treasury=add_ship_treasury,
        add_ship_supplies=add_ship_supplies,
        add_ship_history=add_ship_history,
        start_monster_encounter=start_monster_encounter,
        start_boss=start_boss,
        get_active_boss=get_active_boss,
        get_island_activity_state=get_island_activity_state,
        record_island_visit=record_island_visit,
        post_captains_log=post_captains_log
    ):
        return True


    # -----------------------------------------------------
    # Unified combat commands
    #
    # !cutlass attack / !c attack
    # !cutlass defend / !c defend
    # !cutlass flee   / !c flee
    # !cutlass board  / !c board
    #
    # This runs before the legacy encounter-specific
    # handlers. Old commands remain fully supported.
    # -----------------------------------------------------

    if await handle_combat_command(
        message,
        command,
        get_ship_settings=get_ship_settings,
        get_ship=get_ship,
        get_active_battle=get_active_battle,
        get_active_monster=get_active_monster,
        get_active_boss=get_active_boss,
        attack_enemy=attack_enemy,
        defend=defend,
        board_enemy=board_enemy,
        flee_battle=flee_battle,
        attack_monster=attack_monster,
        attack_boss=attack_boss,
        defend_boss=defend_boss,
        damage_ship=damage_ship,
        reward_ship=_reward_ship_unlocked,
        add_ship_history=add_ship_history,
        post_captains_log=post_captains_log
    ):
        return True


    if await handle_battle_command(
        message,
        command,
        is_admin=is_admin,
        get_ship_settings=get_ship_settings,
        get_ship=get_ship,
        start_naval_battle=start_naval_battle,
        get_active_monster=get_active_monster,
        format_battle=format_battle,
        attack_enemy=attack_enemy,
        defend=defend,
        board_enemy=board_enemy,
        flee_battle=flee_battle,
        damage_ship=damage_ship,
        reward_ship=reward_ship,
        combat_ship_status=combat_ship_status,
        add_ship_history=add_ship_history,
        post_captains_log=post_captains_log
    ):
        return True


    if await handle_monster_command(
        message,
        command,
        is_admin=is_admin,
        get_ship_settings=get_ship_settings,
        get_ship=get_ship,
        start_monster_encounter=start_monster_encounter,
        get_active_battle=get_active_battle,
        format_monster=format_monster,
        attack_monster=attack_monster,
        damage_ship=damage_ship,
        reward_ship=reward_ship,
        add_ship_history=add_ship_history,
        post_captains_log=post_captains_log
    ):
        return True


    if await handle_boss_command(
        message,
        command,
        get_ship_settings=get_ship_settings,
        get_ship=get_ship,
        get_active_battle=get_active_battle,
        get_active_monster=get_active_monster,
        get_active_boss=get_active_boss,
        format_boss=format_boss,
        attack_boss=attack_boss,
        defend_boss=defend_boss,
        damage_ship=damage_ship,
        reward_ship=reward_ship,
        add_ship_history=add_ship_history,
        post_captains_log=post_captains_log
    ):
        return True
















































    return False




@tasks.loop(hours=1)
async def social_loop():
    try:
        now_local = datetime.now(ZoneInfo(BOT_TIMEZONE))
        for guild in bot.guilds:
            settings = await cached_settings(guild.id)
            channel_id = settings.get("chronicle_channel_id", 0)
            channel = guild.get_channel(channel_id) if channel_id else None
            # Birthday announcements use Captain's Log when configured.
            if channel is not None and settings.get("chronicle_enabled") and now_local.hour == 9:
                birthdays = await get_todays_birthdays(guild.id, now_local.month, now_local.day)
                for user_id, username, reward_year in birthdays:
                    if reward_year == now_local.year:
                        continue
                    member = guild.get_member(user_id)
                    mention = member.mention if member else str(username or user_id)
                    await add_doubloons(guild.id, user_id, 50)
                    await mark_birthday_rewarded(guild.id, user_id, now_local.year)
                    await channel.send(birthday_message(mention))
                    await add_log_entry(guild.id, str(username or user_id) + " celebrated a birthday and received 50 doubloons.", "birthday")
            # Weekly chronicle: Sunday at 18:00 local, once per 6 days minimum.
            if settings.get("chronicle_enabled") and channel is not None and now_local.weekday() == 6 and now_local.hour == 18:
                last_run = settings.get("chronicle_last_run")
                due = True
                if last_run:
                    try:
                        last = datetime.fromisoformat(str(last_run).replace("Z", "+00:00"))
                        if last.tzinfo is None:
                            last = last.replace(tzinfo=timezone.utc)
                        due = (datetime.now(timezone.utc) - last) >= timedelta(days=6)
                    except Exception:
                        pass
                if due:
                    await generate_chronicle(guild)
    except Exception as error:
        print("Social loop error:", repr(error))


@social_loop.before_loop
async def before_social_loop():
    await bot.wait_until_ready()


@tasks.loop(minutes=5)
async def ship_world_loop():
    try:
        results = await resolve_due_voyages()
        for result in results:
            guild = bot.get_guild(result["guild_id"])
            if guild is None:
                continue
            settings = await get_ship_settings(guild.id)
            if not settings.get("enabled"):
                continue
            channel = guild.get_channel(settings.get("channel_id", 0))
            if channel is None:
                continue
            text = "**VOYAGE COMPLETE**\n" + result["text"]
            await channel.send(text[:1900])
            await post_captains_log(guild, text, "voyage")
    except Exception as error:
        print("Ship World loop error:", repr(error))


@ship_world_loop.before_loop
async def before_ship_world_loop():
    await bot.wait_until_ready()


@tasks.loop(
    hours=24
)
async def maintenance_loop():

    try:

        await run_maintenance(
            MESSAGE_RETENTION_DAYS,
            WEAK_MEMORY_RETENTION_DAYS
        )


        print(
            "Daily database maintenance complete."
        )


    except Exception as error:

        print(
            "Maintenance error:",
            repr(error)
        )


@maintenance_loop.before_loop
async def before_maintenance():

    await bot.wait_until_ready()


_initialized = False
_initializing = False


@bot.event
async def on_ready():

    global _initialized, _initializing


    if not _initialized and not _initializing:
        _initializing = True

        await initialize_database()
        await initialize_ship_world()
        await initialize_pirate_world()
        await initialize_naval()
        await initialize_monsters()
        await initialize_bosses()
        await initialize_parrot()


        await run_maintenance(
            MESSAGE_RETENTION_DAYS,
            WEAK_MEMORY_RETENTION_DAYS
        )


        for guild in bot.guilds:

            await ensure_guild_settings(
                guild.id
            )
            await ensure_ship(guild.id)
            await ensure_parrot(guild.id)


            settings = await get_guild_settings(
                guild.id
            )


            settings_cache[
                guild.id
            ] = {
                "time": time.time(),
                "data": settings
            }


        if not maintenance_loop.is_running():

            maintenance_loop.start()

        if not social_loop.is_running():

            social_loop.start()

        if not ship_world_loop.is_running():

            ship_world_loop.start()


        _initialized = True
        _initializing = False


    print(
        "===================================="
    )

    print(
        "Captain Cutlass online as "
        + str(
            bot.user
        )
    )

    print(
        "Model: "
        + OPENAI_MODEL
    )

    print(
        "Multi-server welcomes: ENABLED"
    )

    print(
        "Per-guild welcome channels: ENABLED"
    )

    print(
        "Birthdays / returners / crew profiles: ENABLED"
    )

    print(
        "Captain's Log / weekly chronicles: ENABLED"
    )

    print(
        "Creator recognition: "
        + (
            "ENABLED"
            if CREATOR_USER_ID
            else "DISABLED"
        )
    )

    print(
        "Optimized one-call brain: ENABLED"
    )

    print(
        "===================================="
    )


@bot.event
async def on_member_join(
    member
):

    if member.bot:

        return


    try:

        settings = await cached_settings(
            member.guild.id
        )


        if not settings[
            "welcome_enabled"
        ]:

            return


        channel_id = settings[
            "welcome_channel_id"
        ]


        if not channel_id:

            print(
                (
                    "Welcome enabled but no channel configured "
                    "for guild "
                    + str(
                        member.guild.id
                    )
                )
            )

            return


        channel = member.guild.get_channel(
            channel_id
        )


        if channel is None:

            print(
                (
                    "Configured welcome channel not found for guild "
                    + str(
                        member.guild.id
                    )
                )
            )

            return


        mood = settings.get(
            "mood",
            "cheerful"
        )


        greeting = get_welcome_message(
            member.mention,
            mood
        )


        await channel.send(
            greeting
        )


        await asyncio.gather(

            ensure_member_meta(
                member.guild.id,
                member.id,
                member.display_name
            ),

            ensure_user_profile(
                member.guild.id,
                member.id,
                member.display_name
            ),

            ensure_relationship(
                member.guild.id,
                member.id,
                member.display_name
            ),

            ensure_economy(
                member.guild.id,
                member.id
            )
        )


        await add_relationship_event(
            member.guild.id,
            member.id,
            (
                "Joined the ship and was welcomed "
                "aboard by Captain Cutlass."
            ),
            importance=4
        )


        await add_timeline_entry(
            member.guild.id,
            (
                member.display_name
                + " joined the crew."
            ),
            importance=3
        )

        await post_captains_log(
            member.guild,
            "**NEW CREWMATE**\n" + member.mention + " joined the crew.",
            "join"
        )


        print(
            (
                "Welcomed "
                + str(member)
                + " in guild "
                + str(
                    member.guild.id
                )
                + " using #"
                + channel.name
            )
        )


    except Exception as error:

        print(
            "Welcome message error:",
            repr(error)
        )


# Spontaneous parrot participation cooldown.
# One spontaneous parrot appearance per channel every 5 minutes.
PARROT_SPONTANEOUS_COOLDOWN = 300
last_parrot_spontaneous = {}

# Captain <-> parrot banter cooldown.
PARROT_BANTER_COOLDOWN = 600
last_parrot_banter = {}





async def summarize_parrot_banter(
    captain_line,
    parrot_line
):
    """
    Create a short factual summary of a Captain/Parrot exchange.
    This summary must stay grounded in the actual two lines.
    """

    prompt = f"""
Summarize this Captain Cutlass / parrot exchange in ONE short sentence.

CAPTAIN:
{captain_line[:1000]}

PARROT:
{parrot_line[:1000]}

RULES:
- Captain Cutlass is the CAPTAIN.
- Barnacle is the PARROT.
- Barnacle and "the parrot" are the SAME character.
- Never describe Barnacle as mocking, teasing, insulting, or talking about Barnacle himself unless the actual exchange explicitly does so.
- Clearly identify who teased or contradicted whom.
- Mention what the joke, disagreement, or callback was actually about.
- Do not invent events, history, motivations, or facts.
- Do not mention the human user unless necessary to understand the exchange.
- Prefer the names "Captain Cutlass" and "Barnacle" instead of ambiguous labels.
- Keep it under 35 words.
- Write in third person.
- Return ONLY the summary.

Example:
Captain: Barnacle is clever, but still has much to learn.
Barnacle: At least I don't get lost in my own treasure maps.

GOOD:
Barnacle teased Captain Cutlass about getting lost in his own treasure maps after Captain questioned Barnacle's experience.

BAD:
The parrot mocked Barnacle's navigation skills.
"""

    try:

        response = await ai.responses.create(
            model=OPENAI_MODEL,
            input=prompt,
            max_output_tokens=80,
            store=False
        )

        summary = response.output_text.strip()

        return summary[:500]

    except Exception as error:

        print(
            "Parrot banter summary error:",
            repr(error)
        )

        return ""


async def maybe_parrot_banter_after_captain(
    message,
    captain_reply
):
    """
    Let the parrot occasionally react to Captain's own reply.

    Hard rule:
    this function produces ONE parrot response only.
    Captain never automatically replies back to this response,
    preventing loops.
    """

    if not captain_reply:
        return False

    parrot = await get_parrot(
        message.guild.id
    )

    if not parrot["enabled"]:
        return False

    channel_id = message.channel.id

    last_time = last_parrot_banter.get(
        channel_id,
        0
    )

    if (
        time.time() - last_time
        < PARROT_BANTER_COOLDOWN
    ):
        return False

    # Keep banter rarer than normal parrot participation.
    # At 10% parrot participation this becomes roughly 5%.
    chance = max(
        2,
        int(parrot["participation_chance"]) // 2
    )

    if random.randint(1, 100) > chance:
        return False

    relationship = await get_parrot_relationship(
        message.guild.id,
        message.author.id
    )

    memories = await get_parrot_memories(
        message.guild.id,
        message.author.id,
        4
    )

    jokes = await get_parrot_jokes(
        message.guild.id,
        message.author.id,
        4
    )

    memory_text = (
        "\n".join(
            "- " + item["memory"]
            for item in memories
        )
        if memories
        else "NONE"
    )

    joke_text = (
        "\n".join(
            "- " + joke
            for joke in jokes
        )
        if jokes
        else "NONE"
    )

    relationship_text = "NONE"

    if relationship:
        relationship_text = (
            "Familiarity: "
            + str(relationship["familiarity"])
            + "/100\n"
            + "Opinion: "
            + (relationship["opinion"] or "NONE")
            + "\nNickname: "
            + (relationship["nickname"] or "NONE")
        )

    shared_events = await get_parrot_captain_events(
        message.guild.id,
        4
    )

    shared_history = (
        "\n".join(
            "- " + (
                event["summary"]
                or (
                    "Captain said: "
                    + event["captain_line"][:180]
                    + " | Parrot replied: "
                    + event["parrot_line"][:180]
                )
            )
            for event in shared_events
        )
        if shared_events
        else "NONE"
    )

    prompt = f"""
You are {parrot["name"]}, Captain Cutlass's cheeky parrot.

CURRENT MOOD:
{parrot["mood"]}

A crew member just said:
{message.author.display_name}: {message.content[:800]}

Captain Cutlass replied:
{captain_reply[:1000]}

Your relationship with the crew member:
{relationship_text}

Harmless memories:
{memory_text}

Running jokes:
{joke_text}

PAST CAPTAIN / PARROT BANTER:
{shared_history}

React to CAPTAIN CUTLASS'S reply, not directly to the crew member.

You may make a callback to past banter ONLY when it naturally fits.
Do not repeat an old joke merely because it appears in history.

You and Captain have a long-running comedic relationship.

You may:
- tease Captain
- contradict him playfully
- expose harmless exaggerations
- complain about him
- mock his age, paperwork, bad sailing decisions, dramatic speeches,
  missing snacks, treasure obsession, or questionable leadership
- defend the crew member if it is funny
- repeat a harmless embarrassing Captain habit

Rules:
- 1 short sentence, occasionally 2.
- Be witty and specific to what Captain just said.
- Do not create a new topic.
- Do not insult the crew member.
- Do not invent sensitive facts.
- Do not save memories or relationships from this banter.
- Do not ask Captain a question that requires another automatic reply.
- Do not say "keep 'em coming."
- Avoid generic pirate filler.
- Do not start every response with Arrr.
- You are the parrot, never Captain.

Return ONLY the parrot's response.
"""

    try:

        response = await ai.responses.create(
            model=OPENAI_MODEL,
            input=prompt,
            max_output_tokens=120,
            store=False
        )

        reply = response.output_text.strip()

        if not reply:
            return False

        await increment_parrot_interactions(
            message.guild.id
        )

        banter_summary = await summarize_parrot_banter(
            captain_reply,
            reply
        )

        await add_parrot_captain_event(
            message.guild.id,
            captain_reply,
            reply,
            summary=banter_summary,
            event_type="banter",
            importance=5
        )

        last_parrot_banter[
            channel_id
        ] = time.time()

        await message.channel.send(
            "**"
            + parrot["name"]
            + ":** "
            + reply[:1800]
        )

        return True

    except Exception as error:

        print(
            "Parrot banter error:",
            repr(error)
        )

        return False


async def maybe_parrot_spontaneous(message):
    """
    Allow the server parrot to occasionally join normal conversation.

    This is deliberately conservative:
    - disabled parrots never participate
    - commands are ignored
    - per-channel cooldown applies
    - participation chance is respected
    - parrot memory stays isolated from Captain memory
    """

    content = message.content.strip()

    if not content:
        return False

    # When Captain is directly addressed, let Captain answer first.
    # Barnacle may still react later through the dedicated banter system.
    if bot.user and bot.user in message.mentions:
        return False

    if await is_reply_to_captain(message):
        return False

    # Never interrupt commands.
    if content.startswith("!"):
        return False

    parrot = await get_parrot(
        message.guild.id
    )

    if not parrot["enabled"]:
        return False

    chance = int(
        parrot["participation_chance"]
    )

    if chance <= 0:
        return False

    channel_id = message.channel.id

    last_time = last_parrot_spontaneous.get(
        channel_id,
        0
    )

    if (
        time.time() - last_time
        < PARROT_SPONTANEOUS_COOLDOWN
    ):
        return False

    # Participation chance.
    if random.randint(1, 100) > chance:
        return False

    await ensure_parrot_relationship(
        message.guild.id,
        message.author.id,
        message.author.display_name
    )

    relationship = await get_parrot_relationship(
        message.guild.id,
        message.author.id
    )

    memories = await get_parrot_memories(
        message.guild.id,
        message.author.id,
        6
    )

    jokes = await get_parrot_jokes(
        message.guild.id,
        message.author.id,
        6
    )

    result = await analyze_parrot_message(
        message,
        parrot,
        relationship,
        memories,
        jokes,
        message.content
    )

    if not result:
        return False

    reply = str(
        result.get(
            "reply",
            ""
        )
    ).strip()

    if not reply:
        return False

    memory = str(
        result.get(
            "memory",
            "NONE"
        )
    ).strip()

    opinion = str(
        result.get(
            "opinion",
            "NONE"
        )
    ).strip()

    nickname = str(
        result.get(
            "nickname",
            "NONE"
        )
    ).strip()

    joke = str(
        result.get(
            "joke",
            "NONE"
        )
    ).strip()

    blocked_parrot_memories = (
        "not made any memorable",
        "nothing memorable",
        "no memorable",
        "has not revealed",
        "hasn't revealed"
    )

    if (
        memory.upper()
        not in ("NONE", "KEEP", "")
        and not any(
            phrase in memory.lower()
            for phrase in blocked_parrot_memories
        )
    ):
        await add_parrot_memory(
            message.guild.id,
            message.author.id,
            memory
        )

    if (
        opinion.upper()
        not in ("NONE", "KEEP", "")
        or nickname.upper()
        not in ("NONE", "KEEP", "")
    ):
        await update_parrot_relationship(
            message.guild.id,
            message.author.id,
            message.author.display_name,
            opinion=(
                opinion
                if opinion.upper()
                not in ("NONE", "KEEP", "")
                else None
            ),
            nickname=(
                nickname
                if nickname.upper()
                not in ("NONE", "KEEP", "")
                else None
            )
        )

    if joke.upper() not in (
        "NONE",
        "KEEP",
        ""
    ):
        await add_parrot_joke(
            message.guild.id,
            message.author.id,
            joke
        )

    await increment_parrot_interactions(
        message.guild.id
    )

    await increase_parrot_familiarity(
        message.guild.id,
        message.author.id,
        message.author.display_name,
        amount=2
    )

    last_parrot_spontaneous[
        channel_id
    ] = time.time()

    await message.reply(
        "**"
        + parrot["name"]
        + ":** "
        + reply[:1800],
        mention_author=False
    )

    return True


@bot.event
async def on_message(
    message
):

    if message.author.bot:
        return


    if message.guild is None:
        return


    if not channel_allowed(
        message
    ):
        return


    try:

        content_lower = (
            message.content
            .lower()
            .strip()
        )


        story_mode = (
            content_lower
            in {
                "!cutlass story",
                "!c story",
            }
        )


        punbattle_mode = (
            content_lower
            in {
                "!cutlass punbattle",
                "!c punbattle",
            }
        )


        previous_meta = await get_member_meta(
            message.guild.id,
            message.author.id
        )

        await asyncio.gather(

            ensure_member_meta(
                message.guild.id,
                message.author.id,
                message.author.display_name
            ),

            ensure_user_profile(
                message.guild.id,
                message.author.id,
                message.author.display_name
            ),

            ensure_relationship(
                message.guild.id,
                message.author.id,
                message.author.display_name
            ),

            ensure_economy(
                message.guild.id,
                message.author.id
            )
        )


        await ensure_parrot_relationship(
            message.guild.id,
            message.author.id,
            message.author.display_name
        )


        await maybe_greet_returning(
            message,
            previous_meta
        )

        await touch_member_seen(
            message.guild.id,
            message.author.id,
            message.author.display_name
        )

        parrot_state = await get_parrot(
            message.guild.id
        )

        if parrot_state["enabled"]:
            await increase_parrot_familiarity(
                message.guild.id,
                message.author.id,
                message.author.display_name,
                amount=1
            )


        if is_creator(
            message.author.id
        ):

            await ensure_creator_status(
                message
            )


        if await check_treasure_answer(
            message,
            get_treasure_hunt=get_treasure_hunt,
            finish_treasure_hunt=finish_treasure_hunt,
            add_doubloons=add_doubloons,
            award_achievement=award_achievement,
            add_relationship_event=add_relationship_event,
            add_timeline_entry=add_timeline_entry,
            post_captains_log=post_captains_log
        ):

            return


        if (
            not story_mode
            and not punbattle_mode
        ):

            if await handle_commands(
                message
            ):

                return


        await save_message(
            message.guild.id,
            message.channel.id,
            message.author.id,
            message.author.display_name,
            message.content
        )

        await maybe_parrot_spontaneous(
            message
        )


        if familiarity_ready(
            message.guild.id,
            message.author.id
        ):

            old_value, new_value = await increase_familiarity(
                message.guild.id,
                message.author.id,
                amount=1
            )


            await maybe_relationship_milestone(
                message,
                old_value,
                new_value
            )


            await check_achievements(
                message,
                old_value,
                new_value
            )


        direct_mention = (
            bot.user
            in message.mentions
        )


        direct_reply = await is_reply_to_captain(
            message
        )


        force_reply = (
            direct_mention
            or direct_reply
            or story_mode
            or punbattle_mode
        )


        settings = await cached_settings(
            message.guild.id
        )


        if (
            settings[
                "quiet"
            ]
            and not force_reply
        ):

            return


        if (
            QUIET_HOURS_ENABLED
            and not force_reply
            and within_quiet_hours(
                QUIET_START_HOUR,
                QUIET_END_HOUR,
                BOT_TIMEZONE
            )
        ):

            return


        if (
            not force_reply
            and random.random()
            < REACTION_CHANCE
        ):

            try:

                await message.add_reaction(
                    choose_reaction()
                )

            except Exception:

                pass


        if not force_reply:

            if not cooldown_ready(
                message.channel.id
            ):

                return


            if (
                random.random()
                > RANDOM_REPLY_CHANCE
            ):

                return


        (
            conversation,
            member_context,
            target_context,
            world_context,
            gameplay_context
        ) = await asyncio.gather(

            build_conversation(
                message
            ),

            build_member_context(
                message
            ),

            build_target_member_context(
                message
            ),

            build_world_context(
                message.guild.id
            ),

            build_gameplay_context(
                message
            )
        )


        humor_mode = detect_humor_mode(message)
        direct_question_mode = detect_direct_question_mode(message)

        result = await analyze_message(
            message,
            conversation,
            member_context,
            target_context,
            world_context,
            gameplay_context,
            humor_mode,
            direct_question_mode,
            captain_mood=settings["mood"],
            force_reply=force_reply,
            story_mode=story_mode,
            punbattle_mode=punbattle_mode
        )


        if not result:

            return


        await apply_analysis(
            message,
            result,
            humor_mode
        )


        if not result.get(
            "respond",
            False
        ):

            return


        reply = clean_brain_value(
            result.get(
                "reply",
                "NONE"
            )
        )


        if not reply:

            return


        async with message.channel.typing():

            await message.reply(
                reply[:1900],
                mention_author=False
            )

        if not result.get(
            "suppress_parrot_banter",
            False
        ):
            await maybe_parrot_banter_after_captain(
                message,
                reply
            )


        await save_message(
            message.guild.id,
            message.channel.id,
            bot.user.id,
            bot.user.display_name,
            reply
        )


        if not force_reply:

            last_spontaneous_reply[
                message.channel.id
            ] = time.time()


    except Exception as error:

        print(
            "Message processing error:",
            repr(error)
        )



if __name__ == "__main__":

    if not DISCORD_TOKEN:

        raise RuntimeError(
            "DISCORD_TOKEN missing."
        )


    if not OPENAI_API_KEY:

        raise RuntimeError(
            "OPENAI_API_KEY missing."
        )


    bot.run(
        DISCORD_TOKEN
    )
