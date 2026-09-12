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
from cutlass.commands.crew_read import handle_crew_read_command
from cutlass.commands.history_import import handle_history_import_command
from cutlass.commands.lore import handle_lore_command
from cutlass.commands.chronicle import handle_chronicle_command
from cutlass.commands.welcome import handle_welcome_command
from cutlass.commands.treasure import handle_treasure_command, check_treasure_answer
from cutlass.commands.captain import handle_captain_command
from cutlass.commands.admin import handle_admin_command
from cutlass.commands.parrot import handle_parrot_command
from cutlass.commands.work import handle_work_command
from cutlass.commands.ship import handle_ship_command
from cutlass.commands.world import handle_world_command
from cutlass.commands.exploration import handle_exploration_command
from cutlass.commands.islands import handle_island_command
from cutlass.world.islands import (
    format_island,
    choose_island_activity,
    resolve_island_key,
)
from cutlass.commands.battle import handle_battle_command
from cutlass.commands.monsters import handle_monster_command
from cutlass.commands.bosses import handle_boss_command
from cutlass.commands.combat import handle_combat_command
from cutlass.help.natural import (
    command_suggestions,
)
from cutlass.command_router import (
    PUNBATTLE_COMMANDS,
    SHORT_COMMAND_ALIASES,
    STORY_COMMANDS,
)
from cutlass.commands.tickle import (
    handle_tickle_command,
    perform_tickle,
    is_natural_tickle_message,
)
from cutlass.message_assessment_ai import assess_messages_async
from cutlass.intent import (
    detect_direct_question_mode,
    detect_humor_mode,
    is_member_profile_request,
)
from cutlass.context_builders import (
    build_conversation,
    build_gameplay_context,
    build_member_context,
    build_target_member_context,
    resolve_joke_target,
)
from cutlass.authoritative import (
    build_world_context,
    resolve_authoritative_question,
)
from cutlass.help_grounding import (
    format_authoritative_command_reply,
    resolve_authoritative_command_help,
)
from cutlass.world.bosses import (
    BOSSES,
    initialize_bosses,
    get_active_boss,
    force_withdraw_boss,
    start_boss,
    format_boss,
    attack_boss,
    defend_boss,
)
from cutlass.world.monsters import (
    MONSTERS,
    initialize_monsters,
    start_monster_encounter,
    format_monster,
    attack_monster,
    get_active_monster,
    force_withdraw_monster,
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
    force_withdraw_battle,
)
from cutlass.world.pirate_world import (
    initialize_pirate_world,
    format_world,
    format_world_map,
    format_discoveries,
    format_world_findings,
    format_world_events,
    get_world_history,
    add_world_history,
    get_active_world_event,
    activate_world_event,
    end_world_event,
    discover_world_finding,
    explore_random_island,
    count_world_discoveries,
    count_hidden_discoveries,
    count_world_findings,
    get_island_activity_state,
    record_island_visit,
    get_completed_island_activities,
    complete_island_activity,
)

from discord.ext import tasks
from dotenv import load_dotenv

from cutlass.ai_provider import (
    build_ai_gateway,
    format_ai_status,
)

from personality import PERSONALITY
from creator_profile import CREATOR_NAME

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
    repair_ship, format_upgrades, buy_upgrade, format_captured_ships, resolve_captured_ship, format_destinations,
    start_voyage, get_active_voyage, resolve_due_voyages,
    discord_timestamp,
    damage_ship, reward_ship, _reward_ship_unlocked, combat_ship_status,
    get_ship_operational_status,
    add_ship_treasury, add_ship_supplies,
    apply_exploration_outcome,
    add_history as add_ship_history,
    record_captured_ship
)
from cutlass.world.crew_work import initialize_crew_work


ISLAND_BOSS_KEYS = frozenset(BOSSES)
ISLAND_MONSTER_KEYS = frozenset(MONSTERS)


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
    save_message_assessment,
    get_recent_messages,

    ensure_user_profile,
    get_user_profile,
    update_user_identity,
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
    get_import_progress,
    upsert_import_progress,
    list_import_progress,
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
    get_tickle_count,
    increment_tickle_count,
)


load_dotenv()


DISCORD_TOKEN = os.getenv(
    "DISCORD_TOKEN"
)

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-5-nano"
)

OPENAI_RESPONSE_OPTIONS = (
    {"reasoning": {"effort": os.getenv("OPENAI_REASONING_EFFORT", "minimal")}}
    if OPENAI_MODEL.startswith("gpt-5")
    else {}
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
        "30"
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


ai = build_ai_gateway()


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

        "gender": {
            "type": "string"
        },

        "gender_evidence": {
            "type": "string"
        },

        "pronouns": {
            "type": "string"
        },

        "pronouns_evidence": {
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
        "gender",
        "gender_evidence",
        "pronouns",
        "pronouns_evidence",
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


def conversation_channel_allowed(
    message,
    settings
):

    channel_id = int(
        settings.get(
            "conversation_channel_id",
            0
        )
        or 0
    )

    return (
        channel_id == 0
        or message.channel.id == channel_id
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


async def assess_saved_human_message(message, message_id):
    if not message_id:
        return

    try:
        assessments = await assess_messages_async([
            {
                "id": message_id,
                "content": message.content,
            }
        ])
        assessment = assessments.get(int(message_id))
        await save_message_assessment(
            message_id,
            message.guild.id,
            message.channel.id,
            message.author.id,
            message.author.display_name,
            assessment,
        )
    except Exception:
        return


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


# Conversation and history topic rules live in cutlass.context_builders.

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
            **OPENAI_RESPONSE_OPTIONS,
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



async def build_plain_conversation_fallback(
    message,
    conversation,
    member_context,
    world_context,
    gameplay_context,
    captain_mood="neutral",
    force_reply=False
):
    prompt = f"""{PERSONALITY}

Captain Cutlass needs to answer a Discord message.
The strict structured brain failed, so give a plain text reply only.

MOOD:
{captain_mood_instructions(captain_mood)}

RECENT CONVERSATION:
{conversation}

MEMBER CONTEXT:
{member_context}

WORLD CONTEXT:
{world_context}

GAMEPLAY CONTEXT:
{gameplay_context}

MEMBER MESSAGE:
{message.content[:1200]}

Rules:
- Reply directly to the member's latest message.
- Keep it concise, usually 1-2 sentences.
- Stay in Captain Cutlass's pirate voice.
- Do not invent commands, private facts, genders, pronouns, or gameplay records.
- Return only the reply text.
"""
    try:
        response = await ai.responses.create(
            model=OPENAI_MODEL,
            input=prompt,
            max_output_tokens=300,
            store=False,
            **OPENAI_RESPONSE_OPTIONS
        )
        reply = response.output_text.strip()
        if reply:
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
                "reply": reply,
                "suppress_parrot_banter": True
            }
    except Exception as error:
        print("Plain conversation fallback error:", repr(error))

    if force_reply:
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
            "reply": "Aye, I hear ye, matey. Me fancy brain hit a reef, but I’m still aboard.",
            "suppress_parrot_banter": True
        }

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

    greeting_text = re.sub(
        rf"<@!?{bot.user.id if bot.user else 0}>",
        "",
        message.content,
    ).strip().lower()
    greeting_text = re.sub(r"[^a-z\s']+", " ", greeting_text)
    greeting_text = re.sub(r"\s+", " ", greeting_text).strip()

    if force_reply and greeting_text in {
        "hi",
        "hello",
        "hey",
        "ahoy",
        "yo",
        "sup",
        "hiya",
        "good morning",
        "good evening",
    }:
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
            "reply": f"Ahoy, {message.author.display_name}!",
            "suppress_parrot_banter": True
        }

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

    creator_self_knowledge_request = (
        is_creator(message.author.id)
        and any(
            phrase in content_lower
            for phrase in (
                "what do you know about me",
                "what do you know about jay",
                "tell me about me",
                "who am i",
                "describe me",
            )
        )
    )

    if creator_self_knowledge_request:
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
            "reply": (
                "You're Jay, my creator and shipwright—the one who brought me aboard, "
                "keeps me maintained, and keeps shaping this pirate world. I know ye like "
                "practical builds, persistent systems, pirate humor, and improving what already works."
            ),
            "suppress_parrot_banter": True,
        }

    creator_self_roast_request = (
        is_creator(message.author.id)
        and any(
            phrase in content_lower
            for phrase in (
                "roast me",
                "tease me",
                "make fun of me",
            )
        )
    )

    if creator_self_roast_request:
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
            "reply": (
                "Jay, ye call it one small tweak the way a pirate calls a cannonball "
                "a light snack—useful, dramatic, and somehow heavier than promised."
            ),
            "suppress_parrot_banter": True,
        }

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
                store=False,
                **OPENAI_RESPONSE_OPTIONS
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

AUTHORITATIVE MEMBER CONTEXT:
{member_context}

MEMBER IDENTITY RULES:
- The identity in AUTHORITATIVE MEMBER CONTEXT is the only authoritative
  stored identity for the message author.
- Never infer gender or pronouns.
- Gender and pronouns are separate facts.
- A known gender does NOT establish pronouns.
- If pronouns are UNKNOWN, use gender-neutral pronouns and wording.
- If gender is UNKNOWN, use gender-neutral terms.
- Only the member's own explicit statements may establish or change their
  gender or pronouns.
- Claims made by another member about this person's gender, pronouns,
  sexuality, or other personal identity are NOT authoritative.
- Never treat a third-party identity claim as an established fact.

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

CAPTAIN / WORLD CONTEXT:
{world_context}

SELF-LORE PROVENANCE RULE:
- FICTIONAL CAPTAIN SELF-LORE is narrative canon about Captain Cutlass.
- SELF_LORE and LEGACY_SELF_LORE may be used for fictional stories,
  adventures, historical flavor, old rivals, old ships, scars, taverns,
  rumors, preferences, and other narrative details about Captain.
- Self-lore is NOT authoritative evidence about Discord reality.
- A name appearing in self-lore does NOT prove that person is or was a
  real Discord member.
- Self-lore cannot establish guild membership, server roles, officer
  positions, first mates, moderators, relationships with real members,
  Discord usernames, mentions, tags, permissions, or server history.
- Never claim a lore character is a real Discord member unless live
  Discord/member context independently establishes that identity.
- Never tag or mention a person merely because their name appears in
  self-lore.
- If asked who a self-lore character is and no independent Discord
  evidence establishes them as a real member, describe them as a
  fictional character from Captain's self-lore.
- If a real Discord member happens to share a lore character's name,
  treat them as separate identities unless an authoritative source
  explicitly links them.

SOURCE AUTHORITY:
1. Live Discord/member state and deterministic system state.
2. AUTHORITATIVE CORE CANON for Captain's controlled biography.
3. Recorded gameplay/system records for actual Ship World events.
4. Grounded server/member facts supported by their authoritative stores.
5. Captain self-lore for fictional narrative continuity only.

Lower-authority self-lore must never override a higher-authority source.

UNKNOWN PERSON IDENTITY RULE:
- If asked who a named person is, do not invent an identity for them.
- If live Discord/member context verifies that person, use only the
  verified member context supplied to you.
- If the name exists only in Captain self-lore, describe them only as
  a fictional self-lore character.
- If neither authoritative context nor self-lore identifies the name,
  say Captain does not know who they are or has no verified information
  about them.
- Do not invent their gender, pronouns, guild membership, Discord role,
  relationship, occupation, history, personality, or other identity facts.
- A name alone is never evidence of gender or pronouns.
- Pirate banter may decorate the wording of an unknown answer, but must
  not invent facts about the unknown person.

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

If no established answer exists and you invent a NEW durable fictional
detail about Captain Cutlass, return that fact in the LORE field so it
can become reusable Captain self-lore.

New LORE is FICTIONAL SELF-LORE, not a verified Discord or server fact.

Examples of acceptable durable self-lore:
- Captain once lost a ship during the fictional Battle of Black Reef.
- Captain bears a scar from an old fictional sea battle.
- Captain once drank at a fictional tavern called The Crooked Anchor.
- Captain despises a fictional pirate rival named Red Jack.
- Captain once searched for a legendary fictional treasure.

A named character invented in LORE is a FICTIONAL LORE CHARACTER.
Their existence in lore never establishes a corresponding Discord member.

Do NOT create self-lore for:
- temporary moods
- casual jokes
- ordinary opinions that may change
- throwaway exaggerations
- factual information about real crew members
- Discord membership or usernames
- Discord roles, ranks, permissions, or officer positions
- claims that a fictional character is a real server member
- claims that a fictional character is "not AI", "real", "verified",
  "official", or otherwise proven to exist in Discord

RULES:
- Actually answer what the member asked.
- Usually 1-2 sentences.
- Be witty, confident, grumpy, dramatic, or self-deprecating as appropriate.
- Pirate humor and old-man humor are welcome.
- Do not replace the answer with an unrelated memory callback.
- Do not mention unrelated creator, technical, upgrade, or shipbuilding callbacks
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
                **OPENAI_RESPONSE_OPTIONS,
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
- Do not mention unrelated creator, technical, upgrade, or shipbuilding callbacks
  unless the QUESTION itself makes that relevant.
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
                store=False,
                **OPENAI_RESPONSE_OPTIONS
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
            message,
            bot.user.id if bot.user else None
        )

        target_context = await build_target_member_context(
            message,
            bot_user_id=bot.user.id if bot.user else None,
            creator_user_id=CREATOR_USER_ID,
            get_user_profile=get_user_profile,
            get_user_memories_context=get_user_memories_context,
            get_relationship=get_relationship,
            get_running_jokes=get_running_jokes,
            get_relationship_events=get_relationship_events,
            get_achievements=get_achievements,
            context_memories=CONTEXT_MEMORIES,
            context_memory_min_confidence=CONTEXT_MEMORY_MIN_CONFIDENCE,
            context_jokes=CONTEXT_JOKES,
            context_events=CONTEXT_EVENTS,
            context_achievements=CONTEXT_ACHIEVEMENTS
        )

        target_name = (
            target.display_name
            if target
            else "the target member"
        )

        targeted_joke_prompt = f"""
You are Captain Cutlass, an eccentric older pirate.

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
                store=False,
                **OPENAI_RESPONSE_OPTIONS
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
You are Captain Cutlass, an eccentric older pirate.

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
- Do not drag in unrelated creator, technical, upgrade, memory,
  or server-lore callbacks.
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
                store=False,
                **OPENAI_RESPONSE_OPTIONS
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
- Do not mention unrelated memories, creator/technical callbacks,
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
                store=False,
                **OPENAI_RESPONSE_OPTIONS
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

CREW PERSONALITY USE RULE:

If MESSAGE AUTHOR or TARGET MEMBER CONTEXT includes a derived crew
personality type, use it only as a subtle style and callback hint.
It may affect warmth, clarity, playful banter, or practical phrasing.
Do not announce the personality label unless the user asks about
profiles, personality, or what Captain knows about that member.
Do not treat the label as a moral verdict, diagnosis, private trait,
or permanent identity. The latest message, explicit memories, pronouns,
creator rules, and gameplay records outrank the derived personality type.

TARGET MEMBER INTENT:

{"PROFILE_REQUEST" if is_member_profile_request(message, bot.user.id if bot.user else None) else "REFERENCE_ONLY"}

TARGET MEMBER INTENT RULE:

A Discord member appearing in TARGET MEMBER CONTEXT does NOT
automatically mean the user asked Captain to describe that person.

If TARGET MEMBER INTENT is REFERENCE_ONLY:
- Treat the target member as a participant or subject referenced by
  the current message.
- Answer the actual question or statement in MESSAGE.
- Do NOT replace the answer with the target's profile, relationship,
  familiarity, memories, achievements, or a generic description.
- Use target-member facts only when directly relevant to answering
  the actual question.
- A sentence such as "Can @Member keep the treasures?" is asking
  whether that member may keep the treasures. Answer that question.
- A sentence such as "Should @Member attack the monster?" is asking
  about the proposed action. Answer that question.
- A sentence such as "Is @Member coming with us?" is asking about
  the situation, not asking for a member biography.

If TARGET MEMBER INTENT is PROFILE_REQUEST:
- The user explicitly asked what Captain knows, remembers, or thinks
  about that member.
- TARGET MEMBER CONTEXT may be used to answer that request.
- Never invent missing personal facts.

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
- Do not mention unrelated creator/technical callbacks, another member,
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

If CREATOR is YES:
- The message author is Jay, Captain's creator and shipwright.
- If Captain addresses the creator directly, use Jay or a title from
  CREATOR PROFILE.
- Never invent a different personal name for the creator.

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
- Do not change the subject to creator or technical callbacks unless they
  are directly relevant to the joke being told.

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

LORE is Captain's FICTIONAL SELF-LORE.
It may preserve invented adventures and fictional characters for
narrative continuity, but it is never evidence of Discord reality.

Never use LORE to establish:
- a real Discord member
- guild membership
- Discord roles or ranks
- first mates or officers
- usernames, mentions, or tags
- permissions
- real-member relationships
- factual server history

A person invented in LORE remains a fictional lore character unless
live Discord state independently verifies a real member. Even when a
real member shares the same name, do not assume they are the same
person without authoritative evidence.


EXPLICIT USER IDENTITY:

Captain must treat every member as gender-neutral unless that member has
explicitly stated their own gender or pronouns.

GENDER:
- Return KEEP unless MESSAGE AUTHOR explicitly states their OWN gender.
- Never infer gender from username, display name, avatar, roles, writing style,
  personality, relationships, memories, jokes, or conversation context.
- A statement about another person's gender does NOT count.
- If MESSAGE AUTHOR explicitly states their gender, return exactly what they
  stated in GENDER.
- If MESSAGE AUTHOR explicitly asks to remove/forget their stored gender,
  return CLEAR.
- Otherwise return KEEP.

GENDER_EVIDENCE:
- When GENDER contains an explicit value, copy the shortest exact phrase from
  LATEST that explicitly states MESSAGE AUTHOR's own gender.
- When GENDER is CLEAR, copy the shortest exact phrase requesting removal.
- When GENDER is KEEP, return NONE.
- Evidence must come from LATEST only.

PRONOUNS:
- Return KEEP unless MESSAGE AUTHOR explicitly states their OWN pronouns.
- Never infer pronouns from gender, name, avatar, roles, writing style,
  personality, relationships, memories, jokes, or context.
- Gender does NOT automatically determine pronouns.
- If MESSAGE AUTHOR explicitly states their pronouns, return exactly what they
  stated in PRONOUNS.
- If MESSAGE AUTHOR explicitly asks to remove/forget stored pronouns,
  return CLEAR.
- Otherwise return KEEP.

PRONOUNS_EVIDENCE:
- When PRONOUNS contains an explicit value, copy the shortest exact phrase from
  LATEST that explicitly states MESSAGE AUTHOR's own pronouns.
- When PRONOUNS is CLEAR, copy the shortest exact phrase requesting removal.
- When PRONOUNS is KEEP, return NONE.
- Evidence must come from LATEST only.

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

            **OPENAI_RESPONSE_OPTIONS,

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

        return await build_plain_conversation_fallback(
            message,
            conversation,
            member_context,
            world_context,
            gameplay_context,
            captain_mood=captain_mood,
            force_reply=force_reply
        )


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


_CREATOR_GREETING_ADDRESS_RE = re.compile(
    r"""
    ^
    (?P<leading>\s*)
    (?P<salutation>(?:ahoy|arrr|aye|hello|hey|hail|greetings|well\s+met))
    (?P<punctuation>[\s,;:-]+)
    (?P<name>[A-Za-z][A-Za-z'’\-]{1,32})
    (?P<suffix>[^\n]*)
    $
    """,
    re.IGNORECASE | re.VERBOSE,
)


_CREATOR_BARE_ADDRESS_RE = re.compile(
    r"""
    ^
    (?P<leading>\s*)
    (?P<name>[A-Z][A-Za-z'’\-]{1,32})
    (?P<suffix>[,!.?]\s*.*)
    $
    """,
    re.DOTALL | re.VERBOSE,
)


def normalize_creator_address_reply(
    message,
    reply
):
    """
    Replace a hallucinated creator address with the canonical
    creator name when the message author is the creator.
    """

    if not reply:
        return reply

    reply = re.sub(
        r"[\s\u201d\u2019\"',]+$",
        "",
        reply.strip()
    )

    if not is_creator(
        message.author.id
    ):
        return reply

    reply = re.sub(
        r"\bDart\b",
        CREATOR_NAME,
        reply,
        flags=re.IGNORECASE,
    )

    reply = re.sub(
        rf"\b{re.escape(CREATOR_NAME)}(?:\s*,\s*{re.escape(CREATOR_NAME)})+\b",
        CREATOR_NAME,
        reply,
        flags=re.IGNORECASE,
    )

    reply = re.sub(
        rf"^({re.escape(CREATOR_NAME)})(?:\s*,\s*)+(?=with\b|ye\b|you\b|yer\b|your\b)",
        CREATOR_NAME + ", ",
        reply,
        flags=re.IGNORECASE,
    )

    reply = re.sub(
        rf"\b{re.escape(CREATOR_NAME)}\s*,\s*(?:matey|mate|shipwright)\s*,\s*",
        CREATOR_NAME + ", ",
        reply,
        count=1,
        flags=re.IGNORECASE,
    )

    allowed = {
        CREATOR_NAME.casefold(),
        "captain",
        "shipwright",
        "matey",
        "crew",
        "ahoy",
        "aye",
    }

    match = _CREATOR_GREETING_ADDRESS_RE.match(
        reply
    )

    if (
        match
        and match.group(
            "name"
        ).casefold() not in allowed
    ):
        return (
            match.group("leading")
            + match.group("salutation")
            + match.group("punctuation")
            + CREATOR_NAME
            + match.group("suffix")
        )

    match = _CREATOR_BARE_ADDRESS_RE.match(
        reply
    )

    if (
        match
        and match.group(
            "name"
        ).casefold() not in allowed
    ):
        return (
            match.group("leading")
            + CREATOR_NAME
            + match.group("suffix")
        )

    reply = re.sub(
        rf"\b({re.escape(CREATOR_NAME)})\s+back\s+at\s+(?:ye|you),?\s+{re.escape(CREATOR_NAME)}\b",
        rf"\1",
        reply,
        flags=re.IGNORECASE,
    )

    reply = re.sub(
        rf"\b({re.escape(CREATOR_NAME)})\b(?:[^.!?]{{0,24}}\b{re.escape(CREATOR_NAME)}\b)+",
        rf"\1",
        reply,
        count=1,
        flags=re.IGNORECASE,
    )

    return reply


def normalize_member_evidence(
    message,
    evidence
):
    """
    Remove an accidental author-name prefix added by the AI.

    Example:
        bluntie_clause: hello there
    becomes:
        hello there

    Only the CURRENT message author's exact username or
    display name may be stripped.
    """

    if not evidence:
        return evidence

    value = str(evidence).strip()

    possible_names = {
        str(message.author.name or "").strip(),
        str(message.author.display_name or "").strip()
    }

    for name in possible_names:

        if not name:
            continue

        prefix = name + ":"

        if value.casefold().startswith(
            prefix.casefold()
        ):
            return value[len(prefix):].strip()

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


def explicit_identity_evidence_is_valid(
    message_content,
    evidence,
    identity_type
):
    """
    Conservative safety gate for permanent identity writes.

    Identity must be explicitly self-stated in the current
    message. Never infer identity from names, avatars,
    behavior, relationships, or surrounding context.
    """

    if not evidence_is_grounded(
        message_content,
        evidence
    ):
        return False

    proof = str(
        evidence or ""
    ).strip().casefold()

    if not proof:
        return False

    removal_phrases = (
        "forget my gender",
        "remove my gender",
        "clear my gender",
        "don't remember my gender",
        "do not remember my gender",
        "forget my pronouns",
        "remove my pronouns",
        "clear my pronouns",
        "don't remember my pronouns",
        "do not remember my pronouns"
    )

    if identity_type == "gender":

        if any(
            phrase in proof
            for phrase in removal_phrases
            if "gender" in phrase
        ):
            return True

        explicit_gender_patterns = (
            "i am a man",
            "i'm a man",
            "im a man",
            "i am a woman",
            "i'm a woman",
            "im a woman",
            "i am male",
            "i'm male",
            "im male",
            "i am female",
            "i'm female",
            "im female",
            "i identify as a man",
            "i identify as a woman",
            "i identify as male",
            "i identify as female",
            "i am nonbinary",
            "i'm nonbinary",
            "im nonbinary",
            "i am non-binary",
            "i'm non-binary",
            "im non-binary",
            "i am genderfluid",
            "i'm genderfluid",
            "im genderfluid",
            "i am agender",
            "i'm agender",
            "im agender",
            "my gender is "
        )

        return any(
            phrase in proof
            for phrase in explicit_gender_patterns
        )

    if identity_type == "pronouns":

        if any(
            phrase in proof
            for phrase in removal_phrases
            if "pronouns" in phrase
        ):
            return True

        explicit_pronoun_patterns = (
            "my pronouns are ",
            "my pronouns are:",
            "my pronouns ",
            "i use he/him",
            "i use she/her",
            "i use they/them",
            "i use he / him",
            "i use she / her",
            "i use they / them",
            "please use he/him",
            "please use she/her",
            "please use they/them",
            "refer to me as he/him",
            "refer to me as she/her",
            "refer to me as they/them"
        )

        return any(
            phrase in proof
            for phrase in explicit_pronoun_patterns
        )

    return False


def member_identity_text_is_allowed(
    text,
    profile
):
    """
    Prevent permanent member-specific text from inventing
    gender or pronouns.

    Unknown pronouns = no he/him/she/her assumptions.
    Explicit pronouns permit only that explicit set.
    Unknown gender = no man/woman/boy/girl labels.
    """

    if not text:
        return True

    value = str(text).casefold()

    import re

    gender = (
        str(profile.get("gender") or "")
        .strip()
        .casefold()
        if profile
        else ""
    )

    pronouns = (
        str(profile.get("pronouns") or "")
        .strip()
        .casefold()
        if profile
        else ""
    )

    has_he = bool(
        re.search(
            r"\b(?:he|him|his|himself)\b",
            value
        )
    )

    has_she = bool(
        re.search(
            r"\b(?:she|her|hers|herself)\b",
            value
        )
    )

    has_they = bool(
        re.search(
            r"\b(?:they|them|their|theirs|themself|themselves)\b",
            value
        )
    )

    # ---------------------------------------------
    # Pronouns
    # ---------------------------------------------

    if not pronouns:

        if has_he or has_she:
            return False

    elif pronouns in (
        "he/him",
        "he / him"
    ):

        if has_she:
            return False

    elif pronouns in (
        "she/her",
        "she / her"
    ):

        if has_he:
            return False

    elif pronouns in (
        "they/them",
        "they / them"
    ):

        if has_he or has_she:
            return False

    else:
        # Custom or unfamiliar explicitly supplied pronouns.
        # Do not assume binary pronouns are permitted.
        if has_he or has_she:
            return False

    # ---------------------------------------------
    # Gendered member labels
    # ---------------------------------------------

    has_man = bool(
        re.search(r"\bman\b", value)
    )

    has_woman = bool(
        re.search(r"\bwoman\b", value)
    )

    has_boy = bool(
        re.search(r"\bboy\b", value)
    )

    has_girl = bool(
        re.search(r"\bgirl\b", value)
    )

    if not gender:

        if (
            has_man
            or has_woman
            or has_boy
            or has_girl
        ):
            return False

    elif gender in ("man", "male"):

        if has_woman or has_girl:
            return False

    elif gender in ("woman", "female"):

        if has_man or has_boy:
            return False

    else:
        # For nonbinary/custom genders, do not invent
        # binary gender labels.
        if (
            has_man
            or has_woman
            or has_boy
            or has_girl
        ):
            return False

    return True



def is_identity_management_message(message_content):
    """
    Return True only when the member is actually managing their OWN
    identity terms.

    This intentionally does not activate for:
      - third-party identity statements
      - ordinary questions about identity
      - malformed pronoun syntax
      - fictional/hypothetical identity discussion
    """

    content = str(message_content or "").strip()
    lowered = content.lower()

    if not lowered:
        return False

    # --------------------------------------------------------
    # Explicit valid first-person pronoun declarations
    # --------------------------------------------------------

    pronoun_declaration_patterns = [
        r"\bmy\s+pronouns\s+are\s+"
        r"(?:he\s*/\s*him|she\s*/\s*her|they\s*/\s*them)"
        r"(?:[.!]|$)",

        r"\bi\s+use\s+"
        r"(?:he\s*/\s*him|she\s*/\s*her|they\s*/\s*them)"
        r"(?:\s+pronouns?)?(?:[.!]|$)",

        r"\bplease\s+use\s+"
        r"(?:he\s*/\s*him|she\s*/\s*her|they\s*/\s*them)"
        r"\s+(?:for\s+me|pronouns?)\b",
    ]

    for pattern in pronoun_declaration_patterns:
        if re.search(
            pattern,
            lowered,
            re.IGNORECASE
        ):
            return True

    # --------------------------------------------------------
    # Explicit first-person gender declarations
    # --------------------------------------------------------

    gender_declaration_patterns = [
        r"\bi\s+am\s+(?:a\s+)?"
        r"(?:man|woman|boy|girl|male|female)"
        r"(?:[.!]|$)",

        r"\bi['’]m\s+(?:a\s+)?"
        r"(?:man|woman|boy|girl|male|female)"
        r"(?:[.!]|$)",

        r"\bmy\s+gender\s+is\s+"
        r"(?:man|woman|male|female)"
        r"(?:[.!]|$)",
    ]

    for pattern in gender_declaration_patterns:
        if re.search(
            pattern,
            lowered,
            re.IGNORECASE
        ):
            return True

    # --------------------------------------------------------
    # Explicit removal / forgetting
    # --------------------------------------------------------

    removal_patterns = [
        r"\bforget\s+my\s+pronouns\b",
        r"\bclear\s+my\s+pronouns\b",
        r"\bremove\s+my\s+pronouns\b",
        r"\bforget\s+my\s+gender\b",
        r"\bclear\s+my\s+gender\b",
        r"\bremove\s+my\s+gender\b",
    ]

    for pattern in removal_patterns:
        if re.search(
            pattern,
            lowered,
            re.IGNORECASE
        ):
            return True

    # --------------------------------------------------------
    # Explicit corrections / objections
    #
    # These activate safety but DO NOT imply replacement identity.
    # --------------------------------------------------------

    correction_patterns = [
        r"\bdon['’]?t\s+call\s+me\s+(?:a\s+)?"
        r"(?:man|woman|boy|girl|male|female)\b",

        r"\bdo\s+not\s+call\s+me\s+(?:a\s+)?"
        r"(?:man|woman|boy|girl|male|female)\b",

        r"\bstop\s+calling\s+me\s+(?:a\s+)?"
        r"(?:man|woman|boy|girl|male|female)\b",

        r"\bdon['’]?t\s+use\s+"
        r"(?:he\s*/\s*him|she\s*/\s*her|they\s*/\s*them)"
        r"\s+(?:for\s+me|on\s+me)\b",

        r"\bdo\s+not\s+use\s+"
        r"(?:he\s*/\s*him|she\s*/\s*her|they\s*/\s*them)"
        r"\s+(?:for\s+me|on\s+me)\b",
    ]

    for pattern in correction_patterns:
        if re.search(
            pattern,
            lowered,
            re.IGNORECASE
        ):
            return True

    return False



def extract_explicit_user_identity(message_content):
    """
    Deterministically extract ONLY explicit first-person
    gender/pronoun statements from the current Discord message.

    Never infer identity.
    """

    import re

    source = str(
        message_content or ""
    ).strip()

    lowered = source.casefold()

    result = {}


    # -----------------------------------------------------
    # Explicit gender clearing
    # -----------------------------------------------------

    gender_clear_patterns = (
        r"\bforget my gender\b",
        r"\bremove my gender\b",
        r"\bclear my gender\b",
        r"\bdon['’]?t remember my gender\b",
        r"\bdo not remember my gender\b",
    )

    if any(
        re.search(pattern, lowered)
        for pattern in gender_clear_patterns
    ):
        result["gender"] = None


    # -----------------------------------------------------
    # Explicit gender statements
    # -----------------------------------------------------

    gender_patterns = (
        (
            r"\bi(?:\s+am|['’]?m)\s+(?:a\s+)?man\b",
            "man"
        ),
        (
            r"\bi(?:\s+am|['’]?m)\s+(?:a\s+)?woman\b",
            "woman"
        ),
        (
            r"\bi(?:\s+am|['’]?m)\s+male\b",
            "male"
        ),
        (
            r"\bi(?:\s+am|['’]?m)\s+female\b",
            "female"
        ),
        (
            r"\bi(?:\s+am|['’]?m)\s+non[- ]?binary\b",
            "nonbinary"
        ),
        (
            r"\bi(?:\s+am|['’]?m)\s+agender\b",
            "agender"
        ),
        (
            r"\bi(?:\s+am|['’]?m)\s+gender[- ]?fluid\b",
            "genderfluid"
        ),
    )

    for pattern, value in gender_patterns:

        if re.search(
            pattern,
            lowered
        ):
            result["gender"] = value
            break


    # "My gender is ..."
    gender_match = re.search(
        r"\bmy gender is\s+"
        r"(man|woman|male|female|non[- ]?binary|agender|gender[- ]?fluid)\b",
        lowered
    )

    if gender_match:

        value = gender_match.group(1)

        value = (
            value
            .replace("non-binary", "nonbinary")
            .replace("non binary", "nonbinary")
            .replace("gender-fluid", "genderfluid")
            .replace("gender fluid", "genderfluid")
        )

        result["gender"] = value


    # -----------------------------------------------------
    # Explicit pronoun clearing
    # -----------------------------------------------------

    pronoun_clear_patterns = (
        r"\bforget my pronouns\b",
        r"\bremove my pronouns\b",
        r"\bclear my pronouns\b",
        r"\bdon['’]?t remember my pronouns\b",
        r"\bdo not remember my pronouns\b",
    )

    if any(
        re.search(pattern, lowered)
        for pattern in pronoun_clear_patterns
    ):
        result["pronouns"] = None


    # -----------------------------------------------------
    # Explicit pronoun statements
    # -----------------------------------------------------

    pronoun_patterns = (
        (
            r"\bmy pronouns are\s+he\s*/\s*him\b",
            "he/him"
        ),
        (
            r"\bmy pronouns are\s+she\s*/\s*her\b",
            "she/her"
        ),
        (
            r"\bmy pronouns are\s+they\s*/\s*them\b",
            "they/them"
        ),
        (
            r"\bi use\s+he\s*/\s*him\s+pronouns?\b",
            "he/him"
        ),
        (
            r"\bi use\s+she\s*/\s*her\s+pronouns?\b",
            "she/her"
        ),
        (
            r"\bi use\s+they\s*/\s*them\s+pronouns?\b",
            "they/them"
        ),
        (
            r"\bplease use\s+he\s*/\s*him\s+(?:for me|pronouns?)\b",
            "he/him"
        ),
        (
            r"\bplease use\s+she\s*/\s*her\s+(?:for me|pronouns?)\b",
            "she/her"
        ),
        (
            r"\bplease use\s+they\s*/\s*them\s+(?:for me|pronouns?)\b",
            "they/them"
        ),
    )

    for pattern, value in pronoun_patterns:

        if re.search(
            pattern,
            lowered
        ):
            result["pronouns"] = value
            break


    return result


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

    gender = clean_brain_value(
        result.get(
            "gender",
            "KEEP"
        ),
        "KEEP"
    )

    gender_evidence = clean_brain_value(
        result.get(
            "gender_evidence",
            "NONE"
        )
    )

    pronouns = clean_brain_value(
        result.get(
            "pronouns",
            "KEEP"
        ),
        "KEEP"
    )

    pronouns_evidence = clean_brain_value(
        result.get(
            "pronouns_evidence",
            "NONE"
        )
    )


    memory_evidence = normalize_member_evidence(
        message,
        memory_evidence
    )

    joke_evidence = normalize_member_evidence(
        message,
        joke_evidence
    )

    event_evidence = normalize_member_evidence(
        message,
        event_evidence
    )

    server_lore_evidence = normalize_member_evidence(
        message,
        server_lore_evidence
    )

    gender_evidence = normalize_member_evidence(
        message,
        gender_evidence
    )

    pronouns_evidence = normalize_member_evidence(
        message,
        pronouns_evidence
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


    identity_updates = {}

    # -----------------------------------------------------
    # Authoritative explicit identity extraction
    #
    # The Discord message itself is authoritative.
    # AI identity fields are secondary only.
    # -----------------------------------------------------

    explicit_identity = extract_explicit_user_identity(
        message_content
    )

    # -----------------------------------------------------
    # Identity-management messages belong ONLY in the
    # authoritative identity profile.
    #
    # Do not also turn them into memories, jokes, opinions,
    # nicknames, events, or server lore.
    # -----------------------------------------------------

    identity_management_message = (
        bool(explicit_identity)
        or is_identity_management_message(
            message_content
        )
    )

    if identity_management_message:

        memory = None
        opinion = None
        nickname = None
        joke = None
        event = None
        server_lore = None


    # -----------------------------------------------------
    # Third-party target write protection
    #
    # apply_analysis() writes member-specific fields using
    # message.author.id. If the conversation is actually
    # about another member, those generated facts must NOT
    # be stored on the author.
    # -----------------------------------------------------

    analysis_target = await resolve_joke_target(
        message,
        bot.user.id if bot.user else None
    )

    if (
        analysis_target is not None
        and analysis_target.id != message.author.id
    ):

        if any((
            memory,
            opinion,
            nickname,
            joke,
            event
        )):
            print(
                "Suppressed third-party member writes | author:",
                message.author.id,
                "| target:",
                analysis_target.id
            )

        memory = None
        opinion = None
        nickname = None
        joke = None
        event = None

    if "gender" in explicit_identity:
        identity_updates["gender"] = (
            explicit_identity["gender"]
        )

    if "pronouns" in explicit_identity:
        identity_updates["pronouns"] = (
            explicit_identity["pronouns"]
        )


    # -----------------------------------------------------
    # Identity is deterministic only.
    #
    # AI-generated gender/pronoun fields are ignored.
    # Only literal first-person statements from the member
    # may change stored identity.
    # -----------------------------------------------------


    if identity_updates:

        await update_user_identity(
            message.guild.id,
            message.author.id,
            **identity_updates
        )


    # Reload authoritative identity after any explicit
    # identity change made by this message.
    identity_profile = await get_user_profile(
        message.guild.id,
        message.author.id
    )

    member_specific_fields = {
        "memory": memory,
        "opinion": opinion,
        "nickname": nickname,
        "joke": joke,
        "event": event
    }

    for field_name, field_value in member_specific_fields.items():

        if not field_value:
            continue

        if member_identity_text_is_allowed(
            field_value,
            identity_profile
        ):
            continue

        print(
            "Blocked identity-assuming permanent write:",
            field_name,
            "| user:",
            message.author.id,
            "| value:",
            repr(field_value)
        )

        if field_name == "memory":
            memory = None

        elif field_name == "opinion":
            opinion = None

        elif field_name == "nickname":
            nickname = None

        elif field_name == "joke":
            joke = None

        elif field_name == "event":
            event = None


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

            # Captain self-lore is fictional narrative continuity.
            # Do not copy it into captain_timeline, which records
            # grounded ship/server events.


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
        response = await ai.responses.create(model=OPENAI_MODEL, input=prompt, max_output_tokens=500, store=False, **OPENAI_RESPONSE_OPTIONS)
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
        # Bare !c is the natural entry point into Captain's
        # command system rather than an unknown command.
        command = "!cutlass help"
        content = "!cutlass help"

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

    if command in SHORT_COMMAND_ALIASES:
        command = SHORT_COMMAND_ALIASES[command]
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
        get_ship=get_ship,
        is_admin=is_admin
    ):
        return True


    if await handle_crew_read_command(
        message,
        content,
        command,
        is_admin=is_admin,
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


    if await handle_work_command(
        message,
        content,
        command,
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


    if await handle_history_import_command(
        message,
        content,
        command,
        is_admin=is_admin,
        save_message=save_message,
        save_message_assessment=save_message_assessment,
        ensure_user_profile=ensure_user_profile,
        ensure_relationship=ensure_relationship,
        touch_member_seen=touch_member_seen,
        get_relationship=get_relationship,
        increase_familiarity=increase_familiarity,
        update_relationship=update_relationship,
        add_relationship_event=add_relationship_event,
        get_import_progress=get_import_progress,
        upsert_import_progress=upsert_import_progress,
        list_import_progress=list_import_progress,
    ):
        return True


    if await handle_admin_command(
        message,
        command,
        content,
        is_admin=is_admin,
        set_guild_setting=set_guild_setting,
        invalidate_settings_cache=invalidate_settings_cache,
        get_ai_status=lambda: ai,
        format_ai_status=format_ai_status,
        cached_settings=cached_settings
    ):
        return True


























    # -----------------------------------------------------
    # Captain tickle interaction
    #
    # This is intentionally handled outside the AI/gameplay systems.
    # -----------------------------------------------------

    if await handle_tickle_command(
        message,
        command,
        get_tickle_count=get_tickle_count,
        increment_tickle_count=increment_tickle_count,
        get_relationship=get_relationship,
        is_creator=is_creator
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
        invalidate_settings_cache=invalidate_settings_cache,
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
        format_captured_ships=format_captured_ships,
        resolve_captured_ship=resolve_captured_ship,
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
        format_world_findings=format_world_findings,
        format_world_events=format_world_events,
        get_world_history=get_world_history
    ):
        return True


    if await handle_exploration_command(
        message,
        command,
        get_ship_settings=get_ship_settings,
        award_achievement=award_achievement,
        get_ship=get_ship,
        get_ship_operational_status=get_ship_operational_status,
        get_active_battle=get_active_battle,
        get_active_monster=get_active_monster,
        get_active_boss=get_active_boss,
        explore_random_island=explore_random_island,
        count_world_discoveries=count_world_discoveries,
        count_hidden_discoveries=count_hidden_discoveries,
        count_world_findings=count_world_findings,
        start_naval_battle=start_naval_battle,
        start_monster_encounter=start_monster_encounter,
        add_ship_treasury=add_ship_treasury,
        add_ship_supplies=add_ship_supplies,
        apply_exploration_outcome=apply_exploration_outcome,
        add_ship_history=add_ship_history,
        discover_world_finding=discover_world_finding,
        add_world_history=add_world_history,
        post_captains_log=post_captains_log
    ):
        return True


    if await handle_island_command(
        message,
        command,
        get_ship_settings=get_ship_settings,
        get_ship=get_ship,
        get_ship_operational_status=get_ship_operational_status,
        get_active_battle=get_active_battle,
        get_active_monster=get_active_monster,
        format_island=format_island,
        choose_island_activity=choose_island_activity,
        resolve_island_key=resolve_island_key,
        add_ship_treasury=add_ship_treasury,
        add_ship_supplies=add_ship_supplies,
        add_ship_history=add_ship_history,
        start_monster_encounter=start_monster_encounter,
        start_boss=start_boss,
        get_active_boss=get_active_boss,
        get_island_activity_state=get_island_activity_state,
        record_island_visit=record_island_visit,
        get_completed_island_activities=get_completed_island_activities,
        complete_island_activity=complete_island_activity,
        valid_boss_keys=ISLAND_BOSS_KEYS,
        valid_monster_keys=ISLAND_MONSTER_KEYS,
        add_world_history=add_world_history,
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
        get_ship_operational_status=get_ship_operational_status,
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
        post_captains_log=post_captains_log,
        force_withdraw_battle=force_withdraw_battle,
        force_withdraw_monster=force_withdraw_monster,
        force_withdraw_boss=force_withdraw_boss,
    ):
        return True


    if await handle_battle_command(
        message,
        command,
        is_admin=is_admin,
        get_ship_settings=get_ship_settings,
        get_ship=get_ship,
        get_ship_operational_status=get_ship_operational_status,
        start_naval_battle=start_naval_battle,
        get_active_monster=get_active_monster,
        format_battle=format_battle,
        attack_enemy=attack_enemy,
        defend=defend,
        board_enemy=board_enemy,
        flee_battle=flee_battle,
        damage_ship=damage_ship,
        reward_ship=reward_ship,
        record_captured_ship=record_captured_ship,
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
















































    # -----------------------------------------------------
    # Priority 6A unknown-command fallback
    #
    # At this point the message definitely began with
    # !cutlass but no real handler accepted it.
    #
    # Suggest only commands from the authoritative Crew-safe
    # command catalog. Admiralty/configuration commands are
    # intentionally not surfaced here.
    # -----------------------------------------------------

    suggestions = command_suggestions(
        command,
        limit=3,
    )

    if suggestions:

        if len(suggestions) == 1:
            reply = (
                "Arrr, I don't recognize that command. "
                "Did ye mean **`"
                + suggestions[0]["command"]
                + "`**? "
                + suggestions[0]["description"]
                + "."
            )

        else:
            lines = [
                "Arrr, I don't recognize that command. "
                "Closest things aboard be:"
            ]

            for suggestion in suggestions:
                lines.append(
                    "• **`"
                    + suggestion["command"]
                    + "`** — "
                    + suggestion["description"]
                )

            reply = "\n".join(lines)

        await message.reply(
            reply,
            mention_author=False,
        )

        return True

    await message.reply(
        "Arrr, that command isn't in me charts. "
        "Try **`!c help`** and I'll point ye in the right direction.",
        mention_author=False,
    )

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
        await initialize_crew_work()
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
                guild.id,
                guild.name
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
        format_ai_status(ai)
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
            store=False,
            **OPENAI_RESPONSE_OPTIONS
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
            store=False,
            **OPENAI_RESPONSE_OPTIONS
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
            + reply[:1800],
            allowed_mentions=discord.AllowedMentions.none()
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
        mention_author=False,
        allowed_mentions=discord.AllowedMentions.none()
    )

    return True


def message_contains_third_party_identity_claim(
    message_content
):
    """
    Detect common third-party identity claims.

    These claims are never authoritative for another member.
    """

    import re

    text = str(
        message_content or ""
    ).casefold()

    patterns = (
        r"\bis (?:a )?(?:man|woman|boy|girl|male|female)\b",
        r"\bis (?:gay|straight|bisexual|bi|lesbian|trans|transgender)\b",
        r"\buses (?:he/him|she/her|they/them)\b",
        r"\bpronouns are (?:he/him|she/her|they/them)\b",
        r"\bcall (?:him|her|them)\b",
    )

    return any(
        re.search(pattern, text)
        for pattern in patterns
    )


def reply_contains_binary_pronouns(
    reply
):
    import re

    text = str(
        reply or ""
    )

    # Pronoun-set labels are not themselves references to
    # somebody in the sentence.
    text = re.sub(
        r"\b(?:he\s*/\s*him|she\s*/\s*her|they\s*/\s*them)\b",
        "",
        text,
        flags=re.I
    )

    return bool(
        re.search(
            r"\b(?:he|him|his|himself|she|her|hers|herself)\b",
            text,
            re.I
        )
    )


def profile_allows_binary_reply_pronouns(
    profile,
    reply
):
    """
    Check whether binary pronouns appearing in a reply are
    compatible with explicitly stored pronouns.

    Gender alone never establishes pronouns.
    """

    import re

    if not reply:
        return True

    pronouns = (
        str(
            (profile or {}).get(
                "pronouns"
            )
            or ""
        )
        .strip()
        .casefold()
    )

    text = str(
        reply
    ).casefold()

    # Ignore literal pronoun-set labels such as "he/him".
    # They are not equivalent to referring to somebody as he.
    text = re.sub(
        r"\b(?:he\s*/\s*him|she\s*/\s*her|they\s*/\s*them)\b",
        "",
        text,
        flags=re.I
    )

    has_he = bool(
        re.search(
            r"\b(?:he|him|his|himself)\b",
            text
        )
    )

    has_she = bool(
        re.search(
            r"\b(?:she|her|hers|herself)\b",
            text
        )
    )

    if not pronouns:
        return not (
            has_he
            or has_she
        )

    if pronouns in (
        "he/him",
        "he / him"
    ):
        return not has_she

    if pronouns in (
        "she/her",
        "she / her"
    ):
        return not has_he

    if pronouns in (
        "they/them",
        "they / them"
    ):
        return not (
            has_he
            or has_she
        )

    # Unknown/custom explicit pronoun sets must not silently
    # authorize binary pronouns.
    return not (
        has_he
        or has_she
    )


async def enforce_reply_identity_safety(
    message,
    reply
):
    """
    Final identity safety boundary before Captain's reply
    reaches Discord.

    Prompt rules remain the first defense. This function is
    the last defense.
    """

    if not reply:
        return reply

    author_profile = await get_user_profile(
        message.guild.id,
        message.author.id
    )

    target = await resolve_joke_target(
        message,
        bot.user.id if bot.user else None
    )

    target_profile = None

    if (
        target is not None
        and target.id != message.author.id
    ):
        target_profile = await get_user_profile(
            message.guild.id,
            target.id
        )

    # -----------------------------------------------------
    # Third-party identity claims
    # -----------------------------------------------------

    if (
        target is not None
        and target.id != message.author.id
        and message_contains_third_party_identity_claim(
            message.content
        )
    ):
        return (
            "Aye, I don't take another crewmate's word as proof of "
            + target.display_name
            + "'s identity, matey. If they want me to remember "
            "something about themselves, they can tell me directly."
        )

    # -----------------------------------------------------
    # Determine whether a rewrite is required.
    # -----------------------------------------------------

    unsafe = False

    if reply_contains_binary_pronouns(
        reply
    ):

        if (
            target_profile is not None
            and not profile_allows_binary_reply_pronouns(
                target_profile,
                reply
            )
        ):
            unsafe = True

        elif (
            target is None
            and is_identity_management_message(
                message.content
            )
            and not profile_allows_binary_reply_pronouns(
                author_profile,
                reply
            )
        ):
            unsafe = True

    if not unsafe:
        return reply

    # -----------------------------------------------------
    # Rewrite only when the generated reply risks assuming
    # a member's pronouns.
    # -----------------------------------------------------

    author_gender = (
        (author_profile or {}).get("gender")
        or "UNKNOWN"
    )

    author_pronouns = (
        (author_profile or {}).get("pronouns")
        or "UNKNOWN"
    )

    if target is not None:

        target_gender = (
            (target_profile or {}).get("gender")
            or "UNKNOWN"
        )

        target_pronouns = (
            (target_profile or {}).get("pronouns")
            or "UNKNOWN"
        )

        target_identity = (
            "Target member: "
            + target.display_name
            + "\nTarget gender: "
            + target_gender
            + "\nTarget pronouns: "
            + target_pronouns
        )

    else:

        target_identity = (
            "Target member: NONE"
        )

    safety_prompt = f"""
You are correcting a Captain Cutlass Discord reply.

ORIGINAL MEMBER MESSAGE:
{message.content[:1200]}

MESSAGE AUTHOR:
{message.author.display_name}

Author gender: {author_gender}
Author pronouns: {author_pronouns}

{target_identity}

ORIGINAL CAPTAIN REPLY:
{reply[:1800]}

IDENTITY RULES:
- Preserve the original meaning and useful answer.
- Preserve Captain Cutlass's pirate personality.
- Do not invent anyone's gender, pronouns, sexuality, or identity.
- Gender does not imply pronouns.
- UNKNOWN pronouns require gender-neutral wording.
- Use the member's name, ye/yer, matey, crewmate, or they/them when appropriate.
- Only use he/him or she/her for a member when those exact pronouns are explicitly authoritative above.
- Do not treat third-party claims about another person's identity as fact.
- Do not mention these rules.
- Return ONLY the corrected reply.
"""

    try:

        response = await ai.responses.create(
            model=OPENAI_MODEL,
            input=safety_prompt,
            max_output_tokens=350,
            store=False,
            **OPENAI_RESPONSE_OPTIONS
        )

        corrected = (
            response.output_text
            .strip()
        )

        if corrected:

            corrected_safe = True

            if (
                target_profile is not None
                and not profile_allows_binary_reply_pronouns(
                    target_profile,
                    corrected
                )
            ):
                corrected_safe = False

            elif (
                target is None
                and not profile_allows_binary_reply_pronouns(
                    author_profile,
                    corrected
                )
            ):
                corrected_safe = False

            if corrected_safe:

                print(
                    "Rewrote identity-risky Captain reply | author:",
                    message.author.id,
                    "| target:",
                    (
                        target.id
                        if target is not None
                        else None
                    )
                )

                return corrected

            print(
                "Rejected unsafe identity rewrite | author:",
                message.author.id,
                "| target:",
                (
                    target.id
                    if target is not None
                    else None
                ),
                "| corrected:",
                repr(corrected)
            )

    except Exception as error:

        print(
            "Identity reply rewrite error:",
            repr(error)
        )

    # -----------------------------------------------------
    # Deterministic neutral fallback
    #
    # If the AI fails to produce a safe rewrite, still give
    # the member a useful answer instead of a generic warning.
    # -----------------------------------------------------

    if target is not None:

        relationship = await get_relationship(
            message.guild.id,
            target.id
        )

        target_name = target.display_name

        if (
            relationship
            and relationship.get("nickname")
        ):
            target_name = relationship["nickname"]

        familiarity = 0

        if relationship:
            familiarity = int(
                relationship.get(
                    "familiarity",
                    0
                )
                or 0
            )

        if familiarity >= 75:

            return (
                "Aye, "
                + target_name
                + " be a well-known crewmate around these decks. "
                "Plenty of history with this old captain, plenty of "
                "banter, and enough mischief to keep the watch busy, matey."
            )

        if familiarity >= 40:

            return (
                "Aye, "
                + target_name
                + " be a familiar crewmate around here. "
                "We've shared enough laughs and adventures to keep "
                "this old pirate entertained, matey."
            )

        return (
            "Aye, "
            + target_name
            + " be one of the crew, and I'm still learnin' "
            "what sort of trouble follows that name around the ship, matey."
        )

    # No separate target exists. Use a neutral direct-response fallback.
    return (
        "Aye, matey. I heard ye. I'll stick to what ye actually told "
        "me and won't go inventin' anything about yer identity."
    )


@bot.event
async def on_guild_join(guild):
    await ensure_guild_settings(guild.id, guild.name)
    await ensure_ship(guild.id)
    await ensure_parrot(guild.id)
    invalidate_settings_cache(guild.id)


@bot.event
async def on_message(
    message
):

    if message.author.bot:
        return


    if message.guild is None:
        return


    await ensure_guild_settings(
        message.guild.id,
        message.guild.name
    )


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


        story_mode = content_lower in STORY_COMMANDS


        punbattle_mode = content_lower in PUNBATTLE_COMMANDS


        settings = await cached_settings(
            message.guild.id
        )


        conversation_allowed = conversation_channel_allowed(
            message,
            settings
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


        if conversation_allowed:
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


        if not conversation_allowed:
            stored_message_id = await save_message(
                message.guild.id,
                message.channel.id,
                message.author.id,
                message.author.display_name,
                message.content,
                discord_message_id=message.id,
                timestamp=message.created_at.isoformat()
            )
            asyncio.create_task(
                assess_saved_human_message(
                    message,
                    stored_message_id
                )
            )
            return


        # -------------------------------------------------
        # Natural Captain tickle interaction.
        #
        # Commands were already handled above. Clear conversational
        # tickle actions are intercepted here BEFORE random reply
        # cooldowns and BEFORE the AI brain so tickling can never be
        # misrouted as gameplay, identity management, or ordinary AI.
        # -------------------------------------------------

        if is_natural_tickle_message(
            message.content
        ):
            await perform_tickle(
                message,
                get_tickle_count=get_tickle_count,
                increment_tickle_count=increment_tickle_count,
                get_relationship=get_relationship,
                is_creator=is_creator
            )
            return


        conversation_message_id = await save_message(
            message.guild.id,
            message.channel.id,
            message.author.id,
            message.author.display_name,
            message.content,
            discord_message_id=message.id,
            timestamp=message.created_at.isoformat()
        )
        asyncio.create_task(
            assess_saved_human_message(
                message,
                conversation_message_id
            )
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


        # -----------------------------------------------------
        # Deterministic natural command help
        #
        # Resolve directly from the authoritative command catalog
        # before building AI/world context. Natural command help
        # never needs an AI call.
        # -----------------------------------------------------

        authoritative_help = (
            await resolve_authoritative_command_help(
                message,
                bot_user_display_name=bot.user.display_name if bot.user else None,
                bot_user_name=bot.user.name if bot.user else None
            )
        )

        if authoritative_help:

            help_reply = (
                format_authoritative_command_reply(
                    authoritative_help["command"],
                    authoritative_help["description"],
                )
            )

            async with message.channel.typing():

                await message.reply(
                    help_reply[:1900],
                    mention_author=False
                )

            await save_message(
                message.guild.id,
                message.channel.id,
                bot.user.id,
                bot.user.display_name,
                help_reply
            )

            if not force_reply:

                last_spontaneous_reply[
                    message.channel.id
                ] = time.time()

            return


        (
            conversation,
            member_context,
            target_context,
            world_context,
            gameplay_context
        ) = await asyncio.gather(

            build_conversation(
                message,
                get_recent_messages=get_recent_messages,
                context_messages=CONTEXT_MESSAGES,
                max_message_id=conversation_message_id
            ),

            build_member_context(
                message,
                get_user_profile=get_user_profile,
                get_user_memories_context=get_user_memories_context,
                get_relationship=get_relationship,
                get_running_jokes=get_running_jokes,
                get_relationship_events=get_relationship_events,
                get_doubloons=get_doubloons,
                get_achievements=get_achievements,
                context_memories=CONTEXT_MEMORIES,
                context_memory_min_confidence=CONTEXT_MEMORY_MIN_CONFIDENCE,
                context_jokes=CONTEXT_JOKES,
                context_events=CONTEXT_EVENTS,
                context_achievements=CONTEXT_ACHIEVEMENTS,
                creator_user_id=CREATOR_USER_ID
            ),

            build_target_member_context(
                message,
                bot_user_id=bot.user.id if bot.user else None,
                creator_user_id=CREATOR_USER_ID,
                get_user_profile=get_user_profile,
                get_user_memories_context=get_user_memories_context,
                get_relationship=get_relationship,
                get_running_jokes=get_running_jokes,
                get_relationship_events=get_relationship_events,
                get_achievements=get_achievements,
                context_memories=CONTEXT_MEMORIES,
                context_memory_min_confidence=CONTEXT_MEMORY_MIN_CONFIDENCE,
                context_jokes=CONTEXT_JOKES,
                context_events=CONTEXT_EVENTS,
                context_achievements=CONTEXT_ACHIEVEMENTS
            ),

            build_world_context(
                message.guild.id,
                world_cache=world_cache,
                cache_valid=cache_valid,
                cached_settings=cached_settings,
                context_captain_lore=CONTEXT_CAPTAIN_LORE,
                context_server_lore=CONTEXT_SERVER_LORE
            ),

            build_gameplay_context(
                message
            )
        )


        humor_mode = detect_humor_mode(message)

        # Humor-specific routing takes precedence over the broad
        # direct-question detector. A joke, pun, roast request,
        # absurd hypothetical, or "who would win" question must
        # reach its dedicated conversational handler rather than
        # being swallowed by generic question/gameplay routing.
        direct_question_mode = (
            detect_direct_question_mode(message)
            and humor_mode == "NORMAL"
        )

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


        reply = await enforce_reply_identity_safety(
            message,
            reply
        )


        reply = normalize_creator_address_reply(
            message,
            reply
        )


        if not reply:

            return


        async with message.channel.typing():

            await message.reply(
                reply[:1900],
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none()
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


    ai_status = ai.describe()
    has_openai_key = bool(os.getenv("OPENAI_API_KEY"))
    has_local_endpoint = bool(os.getenv("LOCAL_AI_BASE_URL"))

    if (
        ai_status["provider"] == "openai"
        and not has_openai_key
        and not (ai_status["fallback_provider"] == "local" and has_local_endpoint)
    ):
        raise RuntimeError(
            "OPENAI_API_KEY missing."
        )

    if (
        ai_status["provider"] == "local"
        and not has_local_endpoint
        and not (ai_status["fallback_provider"] == "openai" and has_openai_key)
    ):
        raise RuntimeError(
            "LOCAL_AI_BASE_URL missing."
        )


    bot.run(
        DISCORD_TOKEN
    )
