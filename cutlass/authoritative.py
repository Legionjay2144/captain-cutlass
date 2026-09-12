import asyncio
import time

from cutlass.context_builders import (
    HISTORY_TOPIC_RULES,
    _history_records_for_topic,
    classify_history_topic,
)
from memory import get_captain_lore, get_recent_messages, get_server_lore
from ship_world import get_completed_voyages, get_history_records
from cutlass.world.pirate_world import format_discoveries



FOLLOWUP_ONLY_PATTERNS = (
    "what happened after that",
    "after that",
    "then what",
    "what happened next",
    "did anyone earn anything from it",
    "did anyone earn anything",
    "what did we earn from it",
    "what did we get from it",
    "what was the reward",
    "what rewards did we get",
)

BOT_NAME_MARKERS = (
    "captain-cutlass",
    "captain cutlass",
)


async def infer_recent_history_topic(message):
    recent = await get_recent_messages(message.guild.id, message.channel.id, 12)
    current_content = str(message.content or "").strip().lower()

    for username, content in reversed(recent):
        lowered_content = str(content or "").strip().lower()
        lowered_username = str(username or "").strip().lower()

        if not lowered_content:
            continue

        if lowered_content == current_content:
            continue

        if any(marker in lowered_username for marker in BOT_NAME_MARKERS):
            continue

        if any(pattern in lowered_content for pattern in FOLLOWUP_ONLY_PATTERNS):
            continue

        topic = classify_history_topic(lowered_content)
        if topic:
            return topic

    for username, content in reversed(recent):
        lowered_content = str(content or "").strip().lower()
        lowered_username = str(username or "").strip().lower()

        if lowered_content == current_content:
            continue

        if not any(marker in lowered_username for marker in BOT_NAME_MARKERS):
            continue

        if lowered_content.startswith("our latest battle:"):
            return "battle"
        if lowered_content.startswith("our latest recorded voyage:"):
            return "voyage"
        if lowered_content.startswith("our latest sea monster encounter:"):
            return "monster"
        if lowered_content.startswith("our latest boss encounter:"):
            return "boss"
        if lowered_content.startswith("our latest exploration:"):
            return "exploration"
        if lowered_content.startswith("our latest crew repair work:"):
            return "repair"

    return None


async def build_world_context(
    guild_id,
    *,
    world_cache,
    cache_valid,
    cached_settings,
    context_captain_lore,
    context_server_lore,
):
    existing = world_cache.get(guild_id)
    if cache_valid(existing):
        return existing["data"]

    settings = await cached_settings(guild_id)

    captain_lore, server_lore = await asyncio.gather(
        get_captain_lore(context_captain_lore),
        get_server_lore(guild_id, context_server_lore),
    )

    lines = [f"Mood: {settings['mood']}"]

    if settings["event_mode"]:
        lines.append("Roleplay event mode: active")

    if captain_lore:
        lines.append("FICTIONAL CAPTAIN SELF-LORE:")
        lines.append(
            "These are Captain Cutlass's narrative memories and stories. "
            "They may establish fictional details about Captain's past, but they are NOT evidence of real Discord members, guild membership, server roles, relationships, permissions, or server history."
        )
        lines.append(
            "A person named in self-lore is a lore character only unless live Discord state independently verifies a real member. Never tag, mention, identify, or describe someone as a real Discord member from self-lore alone."
        )

        for item in captain_lore:
            provenance = item.get("provenance", "legacy_self_lore")
            lines.append(
                "- ["
                + provenance.upper()
                + "] "
                + item["lore"][:400]
            )

    if server_lore:
        lines.append("Established server lore:")
        for item in server_lore:
            lines.append("- " + item[:400])

    result = "\n".join(lines)
    world_cache[guild_id] = {
        "time": time.time(),
        "data": result,
    }
    return result


async def resolve_authoritative_question(message, current_ship, canon_rows):
    """
    Resolve questions whose answers already exist in authoritative
    Captain Canon or the live Ship World.
    """

    content = message.content.lower().strip()
    canon = {row["key"]: row["value"] for row in canon_rows}

    last_voyage_patterns = (
        "last voyage",
        "latest voyage",
        "most recent voyage",
        "previous voyage",
        "what happened on our last voyage",
        "what happened during our last voyage",
    )
    if any(phrase in content for phrase in last_voyage_patterns):
        voyages = await get_completed_voyages(message.guild.id, limit=2)
        if not voyages:
            return "I don't have a completed voyage recorded yet, matey."
        return "Our latest recorded voyage: " + str(voyages[0]["content"])

    discovery_patterns = (
        "what discoveries have we made",
        "what have we discovered",
        "show discoveries",
        "our discoveries",
        "world discoveries",
        "discovered islands",
        "known discoveries",
    )
    if any(phrase in content for phrase in discovery_patterns):
        return await format_discoveries(message.guild.id)

    damaged_ship_patterns = (
        "what do i do if the ship is damaged",
        "what do we do if the ship is damaged",
        "ship is damaged",
        "ship gets damaged",
        "fix the ship",
        "repair the ship",
        "repair our ship",
        "damaged hull",
    )
    if any(phrase in content for phrase in damaged_ship_patterns):
        return (
            "If the Living Ship is damaged, use `!c repair` for a paid full repair. "
            "Use `!c ship` to check hull and `!c jobs` for maintenance work when the ship is recovering."
        )

    reward_followup_patterns = (
        "did anyone earn anything from it",
        "did anyone earn anything",
        "what did we earn from it",
        "what did we get from it",
        "what was the reward",
        "what rewards did we get",
    )
    if any(phrase in content for phrase in reward_followup_patterns):
        recent_topic = await infer_recent_history_topic(message)

        if recent_topic == "voyage":
            voyages = await get_completed_voyages(message.guild.id, limit=1)
            if voyages:
                return "The latest recorded voyage reward entry: " + str(voyages[0]["content"])

        if recent_topic in HISTORY_TOPIC_RULES:
            records = await get_history_records(message.guild.id, limit=20)
            topic_records = _history_records_for_topic(records, recent_topic)
            if topic_records:
                return (
                    "The latest recorded "
                    + HISTORY_TOPIC_RULES[recent_topic]["label"]
                    + " entry: "
                    + str(topic_records[0]["content"])
                )

        return "I don't have a recorded reward for that recent topic, matey."

    after_followup_patterns = (
        "what happened after that",
        "after that",
        "then what",
        "what happened next",
    )
    if any(phrase in content for phrase in after_followup_patterns):
        recent_topic = await infer_recent_history_topic(message)

        if recent_topic == "voyage":
            voyages = await get_completed_voyages(message.guild.id, limit=1)
            if voyages:
                return "The latest recorded voyage entry is still: " + str(voyages[0]["content"])

        if recent_topic in HISTORY_TOPIC_RULES:
            records = await get_history_records(message.guild.id, limit=20)
            topic_records = _history_records_for_topic(records, recent_topic)
            if topic_records:
                return (
                    "The latest recorded "
                    + HISTORY_TOPIC_RULES[recent_topic]["label"]
                    + " entry is still: "
                    + str(topic_records[0]["content"])
                )

        return "I don't have a clear recorded event after that topic, matey."

    history_followup_patterns = (
        "one before that",
        "the one before that",
        "what about the one before that",
        "voyage before that",
        "before that one",
    )
    if any(phrase in content for phrase in history_followup_patterns):
        recent_topic = await infer_recent_history_topic(message)

        if recent_topic == "voyage":
            voyages = await get_completed_voyages(message.guild.id, limit=3)
            if len(voyages) >= 2:
                return "The voyage before that: " + str(voyages[1]["content"])
            return "I don't have an older completed voyage recorded before that one, matey."

        if recent_topic in HISTORY_TOPIC_RULES:
            records = await get_history_records(message.guild.id, limit=20)
            topic_records = _history_records_for_topic(records, recent_topic)
            if len(topic_records) >= 2:
                return (
                    "The "
                    + HISTORY_TOPIC_RULES[recent_topic]["label"]
                    + " before that: "
                    + str(topic_records[1]["content"])
                )
            if topic_records:
                return (
                    "I only have one "
                    + HISTORY_TOPIC_RULES[recent_topic]["label"]
                    + " recorded, matey."
                )

    history_topic_queries = (
        (
            "battle",
            (
                "last battle",
                "latest battle",
                "most recent battle",
                "previous battle",
                "what happened on our last battle",
                "what happened during our last battle",
                "what happened in our last battle",
                "last fight",
                "latest fight",
                "most recent fight",
            ),
            "Our latest battle: ",
        ),
        (
            "monster",
            (
                "last monster",
                "latest monster",
                "most recent monster",
                "previous monster",
                "what happened on our last monster",
                "what happened during our last monster",
                "last sea monster",
            ),
            "Our latest sea monster encounter: ",
        ),
        (
            "boss",
            (
                "last boss",
                "latest boss",
                "most recent boss",
                "previous boss",
                "what happened on our last boss",
                "what happened during our last boss",
                "last boss fight",
            ),
            "Our latest boss encounter: ",
        ),
        (
            "repair",
            (
                "last repair",
                "latest repair",
                "most recent repair",
                "previous repair",
                "last crew work",
                "latest crew work",
                "last maintenance",
                "latest maintenance",
                "what happened on our last repair",
                "what happened during our last repair",
            ),
            "Our latest crew repair work: ",
        ),
        (
            "exploration",
            (
                "last exploration",
                "latest exploration",
                "most recent exploration",
                "previous exploration",
                "last island",
                "latest island",
                "what happened on our last exploration",
                "what happened during our last exploration",
            ),
            "Our latest exploration: ",
        ),
    )

    for topic_key, phrases, prefix in history_topic_queries:
        if any(phrase in content for phrase in phrases):
            records = await get_history_records(message.guild.id, limit=20)
            topic_records = _history_records_for_topic(records, topic_key)
            if topic_records:
                return prefix + str(topic_records[0]["content"])
            return (
                "I don't have a recorded "
                + HISTORY_TOPIC_RULES[topic_key]["label"]
                + " yet, matey."
            )

    current_ship_patterns = (
        "current ship",
        "our ship called",
        "our ship named",
        "what is our ship",
        "what's our ship",
        "name of our ship",
        "name of the ship",
    )
    if any(phrase in content for phrase in current_ship_patterns):
        return "Our current ship is **" + current_ship["name"] + "**."

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
                + "**, matey. Old enough to know better, stubborn enough not to."
            )

    favorite_patterns = (
        "favorite ship",
        "favourite ship",
        "best ship you've captained",
        "best ship you captained",
    )
    if any(phrase in content for phrase in favorite_patterns):
        value = canon.get("favorite_ship")
        if value:
            return (
                "That'd be **"
                + value
                + "**. She still holds a special place in this old pirate's heart."
            )

    former_patterns = (
        "what ship did you used to captain",
        "what ship did you use to captain",
        "what ship did you captain before",
        "former ship",
        "old ship",
        "previous ship",
    )
    if any(phrase in content for phrase in former_patterns):
        value = canon.get("former_ship")
        if value:
            return "Before this vessel, I captained **" + value + "**."

    parrot_patterns = (
        "parrot's name",
        "parrots name",
        "name of your parrot",
        "what is your parrot called",
        "what's your parrot called",
    )
    if any(phrase in content for phrase in parrot_patterns):
        value = canon.get("parrot")
        if value:
            return "The feathered menace be **" + value + "**."

    return None
