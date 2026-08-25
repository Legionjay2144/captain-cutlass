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
from cutlass.commands.parrot import handle_parrot_command

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
    format_ship_status, rename_ship, get_history, donate, top_contributors,
    repair_ship, format_upgrades, buy_upgrade, format_destinations,
    start_voyage, get_active_voyage, resolve_due_voyages,
    discord_timestamp
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
    get_latest_chronicle
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
        "lore"
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
    humor_mode,
    direct_question_mode,
    captain_mood="neutral",
    force_reply=False,
    story_mode=False,
    punbattle_mode=False
):

    if direct_question_mode:

        canon_rows = await get_all_captain_canon()

        current_ship = await get_ship(
            message.guild.id
        )

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

DIRECT QUESTION:
{message.content[:1200]}

Answer the question directly and in character.

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


    if await handle_help_command(
        message,
        command,
        get_parrot=get_parrot,
        get_ship=get_ship
    ):
        return True


    if command == "!cutlass welcome status":

        settings = await cached_settings(
            message.guild.id
        )

        channel_id = settings[
            "welcome_channel_id"
        ]

        channel = (
            message.guild.get_channel(
                channel_id
            )
            if channel_id
            else None
        )

        channel_text = (
            channel.mention
            if channel
            else "Not configured"
        )

        enabled_text = (
            "Enabled"
            if settings[
                "welcome_enabled"
            ]
            else "Disabled"
        )

        await message.reply(
            (
                "**Welcome System**\n"
                "Status: "
                + enabled_text
                + "\nChannel: "
                + channel_text
            ),
            mention_author=False
        )

        return True


    if command == "!cutlass welcome on":

        if not is_admin(
            message
        ):

            await message.reply(
                "Only the Admiralty may configure welcomes.",
                mention_author=False
            )

            return True


        settings = await cached_settings(
            message.guild.id
        )


        if not settings[
            "welcome_channel_id"
        ]:

            await message.reply(
                (
                    "Set a welcome channel first with "
                    "`!cutlass welcome channel #channel`."
                ),
                mention_author=False
            )

            return True


        await set_guild_setting(
            message.guild.id,
            "welcome_enabled",
            1
        )


        invalidate_settings_cache(
            message.guild.id
        )


        await message.reply(
            "Welcome messages are now enabled for this ship.",
            mention_author=False
        )

        return True


    if command == "!cutlass welcome off":

        if not is_admin(
            message
        ):

            await message.reply(
                "Only the Admiralty may configure welcomes.",
                mention_author=False
            )

            return True


        await set_guild_setting(
            message.guild.id,
            "welcome_enabled",
            0
        )


        invalidate_settings_cache(
            message.guild.id
        )


        await message.reply(
            "Welcome messages are now disabled for this ship.",
            mention_author=False
        )

        return True


    if command.startswith(
        "!cutlass welcome channel"
    ):

        if not is_admin(
            message
        ):

            await message.reply(
                "Only the Admiralty may configure welcomes.",
                mention_author=False
            )

            return True


        channel = None


        if message.channel_mentions:

            channel = message.channel_mentions[
                0
            ]


        else:

            parts = content.split()

            if len(parts) >= 4:

                raw = parts[
                    3
                ]

                raw = (
                    raw
                    .replace("<#", "")
                    .replace(">", "")
                )

                try:

                    channel_id = int(
                        raw
                    )

                    channel = (
                        message.guild.get_channel(
                            channel_id
                        )
                    )

                except ValueError:

                    channel = None


        if channel is None:

            await message.reply(
                (
                    "Use: `!cutlass welcome channel #welcome`"
                ),
                mention_author=False
            )

            return True


        await set_guild_setting(
            message.guild.id,
            "welcome_channel_id",
            channel.id
        )


        invalidate_settings_cache(
            message.guild.id
        )


        await message.reply(
            (
                "Welcome channel set to "
                + channel.mention
                + "."
            ),
            mention_author=False
        )

        return True


    if command == "!cutlass testwelcome":

        if not is_admin(
            message
        ):

            await message.reply(
                "Only the Admiralty may summon imaginary new crewmates.",
                mention_author=False
            )

            return True


        settings = await cached_settings(
            message.guild.id
        )


        mood = settings.get(
            "mood",
            "cheerful"
        )


        greeting = get_welcome_message(
            message.author.mention,
            mood
        )


        await message.reply(
            greeting,
            mention_author=False
        )


        return True


    if command == "!cutlass profile":
        meta, relationship, memories, jokes, events, balance, achievements = await asyncio.gather(
            get_member_meta(message.guild.id, message.author.id),
            get_relationship(message.guild.id, message.author.id),
            get_user_memories_context(message.guild.id, message.author.id, 5, 1),
            get_running_jokes(message.guild.id, message.author.id, 3),
            get_relationship_events(message.guild.id, message.author.id, 3),
            get_doubloons(message.guild.id, message.author.id),
            get_achievements(message.guild.id, message.author.id, 5)
        )
        lines = ["**CREW PROFILE - " + message.author.display_name + "**"]
        if relationship:
            lines += ["Relationship: **" + relationship["relationship_type"] + "**", "Familiarity: **" + str(relationship["familiarity"]) + "/100**"]
            if relationship.get("nickname"):
                lines.append("Captain's nickname: **" + relationship["nickname"] + "**")
            if relationship.get("opinion"):
                lines.append("Captain's opinion: " + relationship["opinion"][:250])
        lines.append("Doubloons: **" + str(balance) + "**")
        if meta and meta.get("birthday_month") and meta.get("birthday_day"):
            lines.append("Birthday: **" + format_birthday(meta["birthday_month"], meta["birthday_day"]) + "**")
        if meta:
            lines.append("First seen: " + str(meta.get("first_seen") or "Unknown"))
            lines.append("Last seen: " + str(meta.get("last_seen") or "Unknown"))
        if achievements:
            lines.append("Achievements: " + ", ".join(a[0] for a in achievements))
        if memories:
            lines.append("Memories: " + str(len(memories)) + " loaded")
        if jokes:
            lines.append("Running jokes: " + str(len(jokes)))
        if events:
            lines.append("Recent shared events: " + str(len(events)))
        await message.reply("\n".join(lines)[:1900], mention_author=False)
        return True

    if command == "!cutlass birthday":
        meta = await get_member_meta(message.guild.id, message.author.id)
        if meta and meta.get("birthday_month") and meta.get("birthday_day"):
            text = "I have yer birthday marked as **" + format_birthday(meta["birthday_month"], meta["birthday_day"]) + "**."
        else:
            text = "I don't have yer birthday yet. Use `!cutlass birthday set August 23`."
        await message.reply(text, mention_author=False)
        return True

    if command.startswith("!cutlass birthday set "):
        raw = content[len("!cutlass birthday set "):].strip()
        try:
            month, day = parse_birthday(raw)
        except ValueError as error:
            await message.reply(str(error), mention_author=False)
            return True
        await set_birthday(message.guild.id, message.author.id, message.author.display_name, month, day)
        await message.reply("Aye! Birthday marked as **" + format_birthday(month, day) + "**. No year needed aboard this ship.", mention_author=False)
        return True

    if command == "!cutlass birthday clear":
        await clear_birthday(message.guild.id, message.author.id)
        await message.reply("Birthday cleared from me ledger.", mention_author=False)
        return True

    if command == "!cutlass birthdays":
        rows = await get_birthdays(message.guild.id)
        if not rows:
            await message.reply("No birthdays be written in the crew ledger yet.", mention_author=False)
            return True
        lines = ["**CREW BIRTHDAYS**"]
        for user_id, username, month, day in rows[:30]:
            lines.append("- " + str(username or user_id) + " - " + format_birthday(month, day))
        await message.reply("\n".join(lines)[:1900], mention_author=False)
        return True

    if command == "!cutlass returners status":
        settings = await cached_settings(message.guild.id)
        await message.reply("**Returning Crewmates**\nStatus: " + ("Enabled" if settings.get("returning_enabled") else "Disabled") + "\nAbsence threshold: " + str(settings.get("returning_days", 14)) + " days", mention_author=False)
        return True

    if command in ("!cutlass returners on", "!cutlass returners off"):
        if not is_admin(message):
            await message.reply("Only the Admiralty may configure returning crewmates.", mention_author=False)
            return True
        enabled = command.endswith(" on")
        await set_guild_setting(message.guild.id, "returning_enabled", 1 if enabled else 0)
        invalidate_settings_cache(message.guild.id)
        await message.reply("Returning crewmate greetings are now " + ("enabled." if enabled else "disabled."), mention_author=False)
        return True

    if command.startswith("!cutlass returners days "):
        if not is_admin(message):
            return True
        try:
            days = int(content.split()[-1])
            if days < 1 or days > 365:
                raise ValueError
        except ValueError:
            await message.reply("Choose between 1 and 365 days.", mention_author=False)
            return True
        await set_guild_setting(message.guild.id, "returning_days", days)
        invalidate_settings_cache(message.guild.id)
        await message.reply("I'll call a crewmate returning after **" + str(days) + " days** away.", mention_author=False)
        return True

    if command == "!cutlass log status":
        settings = await cached_settings(message.guild.id)
        channel = message.guild.get_channel(settings.get("chronicle_channel_id", 0))
        await message.reply("**Captain's Log**\nStatus: " + ("Enabled" if settings.get("chronicle_enabled") else "Disabled") + "\nChannel: " + (channel.mention if channel else "Not configured") + "\nWeekly chronicles: " + ("Enabled" if settings.get("chronicle_enabled") else "Disabled"), mention_author=False)
        return True

    if command.startswith("!cutlass log channel"):
        if not is_admin(message):
            await message.reply("Only the Admiralty may move the Captain's Log.", mention_author=False)
            return True
        channel = message.channel_mentions[0] if message.channel_mentions else None
        if channel is None:
            await message.reply("Use: `!cutlass log channel #captains-log`", mention_author=False)
            return True
        await set_guild_setting(message.guild.id, "chronicle_channel_id", channel.id)
        invalidate_settings_cache(message.guild.id)
        await message.reply("Captain's Log set to " + channel.mention + ".", mention_author=False)
        return True

    if command in ("!cutlass log on", "!cutlass log off"):
        if not is_admin(message):
            return True
        enabled = command.endswith(" on")
        if enabled:
            settings = await cached_settings(message.guild.id)
            if not settings.get("chronicle_channel_id"):
                await message.reply("Set the channel first with `!cutlass log channel #captains-log`.", mention_author=False)
                return True
        await set_guild_setting(message.guild.id, "chronicle_enabled", 1 if enabled else 0)
        invalidate_settings_cache(message.guild.id)
        await message.reply("Captain's Log is now " + ("enabled." if enabled else "disabled."), mention_author=False)
        return True

    if command == "!cutlass chronicle latest":
        row = await get_latest_chronicle(message.guild.id)
        await message.reply((row[0] if row else "No chronicle has been written yet.")[:1900], mention_author=False)
        return True

    if command == "!cutlass chronicle now":
        if not is_admin(message):
            return True
        chronicle, error = await generate_chronicle(message.guild)
        await message.reply("Chronicle posted to the Captain's Log." if chronicle else error, mention_author=False)
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
        generate_parrot_reply=generate_parrot_reply,
        increment_parrot_interactions=increment_parrot_interactions,
        increase_parrot_familiarity=increase_parrot_familiarity
    ):
        return True


    # Ship World and voyages. Configuration commands may be used anywhere;
    # gameplay is routed to the configured Ship World channel.
    if command.startswith("!cutlass ship") or command.startswith("!cutlass voyage"):
        settings = await get_ship_settings(message.guild.id)
        ship_channel = message.guild.get_channel(settings.get("channel_id", 0))

        if command.startswith("!cutlass ship channel"):
            if not is_admin(message):
                await message.reply("Only the Admiralty may set the Ship World channel.", mention_author=False)
                return True
            channel = message.channel_mentions[0] if message.channel_mentions else None
            if channel is None:
                await message.reply("Use: `!cutlass ship channel #ship-world`", mention_author=False)
                return True
            await set_ship_setting(message.guild.id, "channel_id", channel.id)
            await message.reply("Ship World set to " + channel.mention + ".", mention_author=False)
            return True

        if command in ("!cutlass ship on", "!cutlass ship off"):
            if not is_admin(message):
                await message.reply("Only the Admiralty may configure Ship World.", mention_author=False)
                return True
            enabled = command.endswith(" on")
            if enabled and not settings.get("channel_id"):
                await message.reply("Set the channel first with `!cutlass ship channel #ship-world`.", mention_author=False)
                return True
            await set_ship_setting(message.guild.id, "enabled", 1 if enabled else 0)
            await message.reply("Ship World is now " + ("enabled." if enabled else "disabled."), mention_author=False)
            return True

        if command == "!cutlass ship status":
            state = "Enabled" if settings.get("enabled") else "Disabled"
            await message.reply("**SHIP WORLD**\nStatus: " + state + "\nChannel: " + (ship_channel.mention if ship_channel else "Not configured"), mention_author=False)
            return True

        if not settings.get("enabled"):
            await message.reply("Ship World is disabled on this server.", mention_author=False)
            return True
        if ship_channel is None:
            await message.reply("The Ship World channel is not configured.", mention_author=False)
            return True
        if message.channel.id != ship_channel.id:
            await message.reply("All ship business belongs in " + ship_channel.mention + ".", mention_author=False)
            return True

        if command in ("!cutlass ship", "!cutlass ship world"):
            await message.reply(await format_ship_status(message.guild.id), mention_author=False)
            return True

        if command.startswith("!cutlass ship name "):
            if not is_admin(message):
                await message.reply("Only the Admiralty may rename the ship.", mention_author=False)
                return True
            try:
                name = await rename_ship(message.guild.id, content[len("!cutlass ship name "):])
            except ValueError as error:
                await message.reply(str(error), mention_author=False)
                return True
            await message.reply("Strike the old name from the ledger. She is now **" + name + "**.", mention_author=False)
            await post_captains_log(message.guild, "**SHIP WORLD**\nThe server ship was renamed **" + name + "**.", "ship")
            return True

        if command == "!cutlass ship history":
            rows = await get_history(message.guild.id, 12)
            if not rows:
                await message.reply("The ship's history is still a blank page.", mention_author=False)
            else:
                await message.reply(("**SHIP HISTORY**\n" + "\n".join("- " + row[0] for row in rows))[:1900], mention_author=False)
            return True

        if command == "!cutlass ship treasury":
            ship_text = await format_ship_status(message.guild.id)
            contributors = await top_contributors(message.guild.id)
            treasury_line = next((line for line in ship_text.splitlines() if line.startswith("Treasury:")), "Treasury: **0 doubloons**")
            text = "**SHIP TREASURY**\n" + treasury_line.replace("Treasury: ", "")
            if contributors:
                text += "\n\n**Top Contributors**\n" + "\n".join(str(i) + ". " + str(name or "Unknown") + " - " + str(amount) for i, (name, amount) in enumerate(contributors, 1))
            await message.reply(text, mention_author=False)
            return True

        if command.startswith("!cutlass ship donate "):
            try:
                amount = int(content.split()[-1])
            except ValueError:
                await message.reply("Use: `!cutlass ship donate 100`", mention_author=False)
                return True
            ok, text = await donate(message.guild.id, message.author.id, message.author.display_name, amount, get_doubloons, add_doubloons)
            await message.reply(text, mention_author=False)
            if ok:
                await post_captains_log(message.guild, "**SHIP TREASURY**\n" + text, "ship")
            return True

        if command == "!cutlass ship repair":
            if not is_admin(message):
                await message.reply("Only the Admiralty may authorize treasury repairs.", mention_author=False)
                return True
            ok, text = await repair_ship(message.guild.id)
            await message.reply(text, mention_author=False)
            if ok:
                await post_captains_log(message.guild, "**SHIP REPAIRS**\n" + text, "ship")
            return True

        if command == "!cutlass ship upgrades":
            await message.reply(await format_upgrades(message.guild.id), mention_author=False)
            return True

        if command.startswith("!cutlass ship upgrade "):
            if not is_admin(message):
                await message.reply("Only the Admiralty may purchase ship upgrades.", mention_author=False)
                return True
            ok, text = await buy_upgrade(message.guild.id, content[len("!cutlass ship upgrade "):])
            await message.reply(text, mention_author=False)
            if ok:
                await post_captains_log(message.guild, "**SHIP UPGRADE**\n" + text, "ship")
            return True

        if command in ("!cutlass voyage", "!cutlass voyage destinations"):
            await message.reply(format_destinations(), mention_author=False)
            return True

        if command == "!cutlass voyage status":
            voyage = await get_active_voyage(message.guild.id)
            if not voyage:
                await message.reply("The ship is currently anchored. No voyage is active.", mention_author=False)
            else:
                await message.reply("**CURRENT VOYAGE**\nDestination: **" + voyage["destination"] + "**\nRisk: **" + voyage["risk"] + "**\nExpected completion: **" + discord_timestamp(voyage["completes_at"]) + "**", mention_author=False)
            return True

        if command.startswith("!cutlass voyage start "):
            if not is_admin(message):
                await message.reply("Only the Admiralty may order the ship to sail.", mention_author=False)
                return True
            try:
                destination = int(content.split()[-1])
            except ValueError:
                await message.reply("Use: `!cutlass voyage start 1`", mention_author=False)
                return True
            ok, result = await start_voyage(message.guild.id, destination)
            if not ok:
                await message.reply(result, mention_author=False)
                return True
            text = ("**VOYAGE BEGUN**\nDestination: **" + result["name"] + "**\nRisk: **" + result["risk"] + "**\nSupplies used: **" + str(result["supplies"]) + "**\nExpected completion: **" + discord_timestamp(result["completes_at"]) + "**")
            await message.reply(text, mention_author=False)
            await post_captains_log(message.guild, text, "voyage")
            return True

        await message.reply("Unknown Ship World command. Use `!cutlass help`.", mention_author=False)
        return True


    if command == "!cutlass creator":

        if is_creator(
            message.author.id
        ):

            await message.reply(
                (
                    "Aye, Shipwright. Ye be the scallywag "
                    "responsible for dragging this old pirate aboard."
                ),
                mention_author=False
            )

        else:

            await message.reply(
                (
                    "Nay. Me creator be somewhere aboard, "
                    "probably adding another container."
                ),
                mention_author=False
            )

        return True


    if command == "!cutlass memory":

        memories = await get_user_memories(
            message.guild.id,
            message.author.id,
            20
        )

        text = (
            "Me memory chest be empty for ye so far."
        )

        if memories:

            text = (
                "**Memory chest:**\n"
                + "\n".join(
                    "- "
                    + memory
                    for memory in memories
                )
            )


        await message.reply(
            text,
            mention_author=False
        )

        return True


    if command == "!cutlass relationship":

        (
            relationship,
            jokes,
            events
        ) = await asyncio.gather(

            get_relationship(
                message.guild.id,
                message.author.id
            ),

            get_running_jokes(
                message.guild.id,
                message.author.id,
                5
            ),

            get_relationship_events(
                message.guild.id,
                message.author.id,
                5
            )
        )


        if not relationship:

            await message.reply(
                "We have not sailed enough seas yet.",
                mention_author=False
            )

            return True


        text = (
            "**Relationship:** "
            + relationship[
                "relationship_type"
            ]
            + "\n**Familiarity:** "
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

            text += (
                "\n**Nickname:** "
                + relationship[
                    "nickname"
                ]
            )


        if relationship[
            "opinion"
        ]:

            text += (
                "\n**Opinion:** "
                + relationship[
                    "opinion"
                ]
            )


        if jokes:

            text += (
                "\n\n**Running jokes:**"
            )

            for joke in jokes:

                text += (
                    "\n- "
                    + joke
                )


        if events:

            text += (
                "\n\n**Shared events:**"
            )

            for event in events:

                text += (
                    "\n- "
                    + event[
                        "event"
                    ]
                )


        await message.reply(
            text,
            mention_author=False
        )

        return True


    if command == "!cutlass lore":

        lore = await get_captain_lore(
            15
        )

        text = (
            "Me legendary career has not been documented yet."
        )

        if lore:

            text = (
                "**Tales from me questionable past:**\n"
                + "\n".join(
                    "- "
                    + item[
                        "lore"
                    ]
                    for item in lore
                )
            )


        await message.reply(
            text,
            mention_author=False
        )

        return True


    if command == "!cutlass canon":

        text = await format_captain_canon()

        await message.reply(
            text[:1900],
            mention_author=False
        )

        return True


    if command == "!cutlass serverlore":

        lore = await get_server_lore(
            message.guild.id,
            15
        )

        text = (
            "This ship has not accumulated enough questionable history yet."
        )

        if lore:

            text = (
                "**Ship lore:**\n"
                + "\n".join(
                    "- "
                    + item
                    for item in lore
                )
            )


        await message.reply(
            text,
            mention_author=False
        )

        return True


    if command == "!cutlass stats":

        stats = await get_stats(
            message.guild.id
        )

        text = (
            "**Captain Cutlass Stats**\n"
            "Crew profiles: "
            + str(stats["members"])
            + "\nMemories: "
            + str(stats["memories"])
            + "\nRunning jokes: "
            + str(stats["jokes"])
            + "\nShared events: "
            + str(stats["events"])
            + "\nCaptain lore: "
            + str(stats["captain_lore"])
            + "\nServer lore: "
            + str(stats["server_lore"])
            + "\nSaved quotes: "
            + str(stats["quotes"])
            + "\nAchievements: "
            + str(stats["achievements"])
            + "\nTimeline entries: "
            + str(stats["timeline"])
            + "\nTotal doubloons: "
            + str(stats["doubloons"])
        )


        await message.reply(
            text,
            mention_author=False
        )

        return True


    if command == "!cutlass crew":

        crew = await get_top_crew(
            message.guild.id,
            10
        )


        if not crew:

            await message.reply(
                "No crew rankings yet.",
                mention_author=False
            )

            return True


        lines = []


        for number, row in enumerate(
            crew,
            start=1
        ):

            display = (
                row[1]
                if row[1]
                else row[0]
            )


            lines.append(
                (
                    str(number)
                    + ". "
                    + str(display)
                    + " - "
                    + str(row[2])
                    + " ("
                    + str(row[3])
                    + "/100)"
                )
            )


        await message.reply(
            (
                "**Captain's Top Crewmates**\n"
                + "\n".join(
                    lines
                )
            ),
            mention_author=False
        )

        return True


    if command == "!cutlass balance":

        balance = await get_doubloons(
            message.guild.id,
            message.author.id
        )


        await message.reply(
            (
                "Ye currently have **"
                + str(balance)
                + " doubloons**."
            ),
            mention_author=False
        )

        return True


    if command == "!cutlass achievements":

        achievements = await get_achievements(
            message.guild.id,
            message.author.id
        )


        if not achievements:

            await message.reply(
                "Ye have not earned any achievements yet.",
                mention_author=False
            )

            return True


        text = (
            "**Yer achievements:**"
        )


        for (
            achievement,
            description
        ) in achievements:

            text += (
                "\n- **"
                + achievement
                + "**"
            )

            if description:

                text += (
                    " - "
                    + description
                )


        await message.reply(
            text,
            mention_author=False
        )

        return True


    if command == "!cutlass leaderboard":

        crew = await get_doubloon_leaderboard(
            message.guild.id,
            10
        )


        if not crew:

            await message.reply(
                "The treasury ledger be empty.",
                mention_author=False
            )

            return True


        lines = []


        for number, row in enumerate(
            crew,
            start=1
        ):

            username = (
                row[0]
                or "Unknown Crewmate"
            )

            display = (
                row[1]
                if row[1]
                else username
            )

            lines.append(
                (
                    str(number)
                    + ". "
                    + str(display)
                    + " - "
                    + str(row[2])
                    + " doubloons"
                )
            )


        await message.reply(
            (
                "**Doubloon Leaderboard**\n"
                + "\n".join(
                    lines
                )
            ),
            mention_author=False
        )

        return True


    if command == "!cutlass wisdom":

        await message.reply(
            random_wisdom(),
            mention_author=False
        )

        return True


    if command == "!cutlass quote":

        quote = await get_random_quote(
            message.guild.id
        )


        await message.reply(
            (
                quote
                if quote
                else "Me quote book be suspiciously empty."
            ),
            mention_author=False
        )

        return True


    if command == "!cutlass savequote":

        return await handle_quote_save(
            message
        )


    if command == "!cutlass journal":

        entries = await get_journal(
            message.guild.id,
            5
        )


        if not entries:

            await message.reply(
                "Me journal pages are blank.",
                mention_author=False
            )

            return True


        text = (
            "**Captain's Journal**"
        )


        for (
            entry,
            date
        ) in entries:

            text += (
                "\n\n**"
                + str(date)
                + "**\n"
                + entry
            )


        await message.reply(
            text,
            mention_author=False
        )

        return True


    if command == "!cutlass timeline":

        entries = await get_timeline(
            message.guild.id,
            10
        )


        if not entries:

            await message.reply(
                "The ship's timeline be empty.",
                mention_author=False
            )

            return True


        text = (
            "**Captain's Timeline**"
        )


        for (
            entry,
            date
        ) in entries:

            text += (
                "\n\n**"
                + str(date)
                + "**\n"
                + entry
            )


        await message.reply(
            text,
            mention_author=False
        )

        return True


    if command == "!cutlass mood":

        settings = await cached_settings(
            message.guild.id
        )


        await message.reply(
            (
                "Current mood: **"
                + settings[
                    "mood"
                ]
                + "**"
            ),
            mention_author=False
        )

        return True


    if command == "!cutlass forgetme":

        await delete_user_memories(
            message.guild.id,
            message.author.id
        )


        await message.reply(
            "Yer personal memory chest has been tossed overboard.",
            mention_author=False
        )

        return True


    if command == "!cutlass treasure clue":

        hunt = await get_treasure_hunt(
            message.guild.id
        )


        if (
            not hunt
            or not hunt[
                "active"
            ]
        ):

            await message.reply(
                "There be no active treasure hunt.",
                mention_author=False
            )

            return True


        await message.reply(
            (
                "Treasure clue: "
                + hunt[
                    "clue"
                ]
            ),
            mention_author=False
        )

        return True


    if command.startswith(
        "!cutlass quiet "
    ):

        if not is_admin(
            message
        ):

            await message.reply(
                "Only the Admiralty may silence the captain.",
                mention_author=False
            )

            return True


        value = command.split()[
            -1
        ]


        if value not in (
            "on",
            "off"
        ):

            return True


        await set_guild_setting(
            message.guild.id,
            "quiet",
            (
                1
                if value == "on"
                else 0
            )
        )


        invalidate_settings_cache(
            message.guild.id
        )


        await message.reply(
            (
                "Captain is now quiet."
                if value == "on"
                else "Captain is back on deck."
            ),
            mention_author=False
        )

        return True


    if command.startswith(
        "!cutlass mood "
    ):

        if not is_admin(
            message
        ):

            await message.reply(
                "Only the Admiralty may adjust me temperament.",
                mention_author=False
            )

            return True


        parts = content.split(
            " ",
            2
        )


        if len(
            parts
        ) < 3:

            return True


        mood = parts[
            2
        ].strip()[:50]


        await set_guild_setting(
            message.guild.id,
            "mood",
            mood
        )


        invalidate_settings_cache(
            message.guild.id
        )


        await message.reply(
            (
                "Captain's mood is now **"
                + mood
                + "**."
            ),
            mention_author=False
        )

        return True


    if command.startswith(
        "!cutlass event "
    ):

        if not is_admin(
            message
        ):

            return True


        value = command.split()[
            -1
        ]


        if value not in (
            "on",
            "off"
        ):

            return True


        await set_guild_setting(
            message.guild.id,
            "event_mode",
            (
                1
                if value == "on"
                else 0
            )
        )


        invalidate_settings_cache(
            message.guild.id
        )


        await message.reply(
            (
                "Roleplay event mode activated."
                if value == "on"
                else "Roleplay event mode disabled."
            ),
            mention_author=False
        )

        return True


    if command.startswith(
        "!cutlass treasure start "
    ):

        if not is_admin(
            message
        ):

            return True


        payload = content[
            len(
                "!cutlass treasure start "
            ):
        ]


        if "|" not in payload:

            await message.reply(
                (
                    "Use: `!cutlass treasure start "
                    "ANSWER | CLUE`"
                ),
                mention_author=False
            )

            return True


        answer, clue = payload.split(
            "|",
            1
        )


        await start_treasure_hunt(
            message.guild.id,
            answer.strip(),
            clue.strip()
        )


        await message.reply(
            (
                "A new treasure hunt has begun. "
                "May the cleverest scallywag find it."
            ),
            mention_author=False
        )

        return True


    return False


async def check_treasure_answer(
    message
):

    hunt = await get_treasure_hunt(
        message.guild.id
    )


    if (
        not hunt
        or not hunt[
            "active"
        ]
    ):

        return False


    if (
        message.content
        .lower()
        .strip()
        != hunt[
            "answer"
        ]
    ):

        return False


    await finish_treasure_hunt(
        message.guild.id,
        message.author.id,
        message.author.display_name
    )


    await add_doubloons(
        message.guild.id,
        message.author.id,
        100
    )


    await award_achievement(
        message.guild.id,
        message.author.id,
        "Treasure Hunter",
        "Won a Captain Cutlass treasure hunt."
    )


    await add_relationship_event(
        message.guild.id,
        message.author.id,
        "Won one of Captain Cutlass's treasure hunts.",
        importance=8
    )


    await add_timeline_entry(
        message.guild.id,
        (
            message.author.display_name
            + " won one of Captain Cutlass's treasure hunts."
        ),
        importance=8
    )


    await message.reply(
        (
            "Treasure found! "
            + message.author.display_name
            + " has claimed the booty and earned 100 doubloons!"
        ),
        mention_author=False
    )

    await post_captains_log(
        message.guild,
        "**TREASURE HUNT**\n" + message.author.mention + " found the treasure, earned **100 doubloons**, and claimed the **Treasure Hunter** achievement.",
        "treasure"
    )


    return True


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


@bot.event
async def on_ready():

    global _initialized


    if not _initialized:

        await initialize_database()
        await initialize_ship_world()
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
            == "!cutlass story"
        )


        punbattle_mode = (
            content_lower
            == "!cutlass punbattle"
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
            message
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
            world_context
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