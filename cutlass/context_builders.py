import asyncio
import re

import discord

from creator_profile import CREATOR_NAME, CREATOR_PROFILE
from memory import get_recent_messages
from ship_world import get_active_voyage, get_completed_voyages, get_history_records, get_ship
from cutlass.world.pirate_world import get_world_history
from cutlass.commands.crew_read import build_member_crew_read


CONVERSATION_TOPIC_RULES = (
    (
        "voyage",
        "voyage / sailing",
        (
            "voyage",
            "voyages",
            "sail",
            "sailing",
            "set sail",
            "destination",
            "route",
            "current voyage",
            "where are we sailing",
        ),
    ),
    (
        "battle",
        "naval battle",
        (
            "battle",
            "battles",
            "fight",
            "fighting",
            "combat",
            "enemy ship",
            "attack",
            "board",
            "defend",
            "flee",
        ),
    ),
    (
        "monster",
        "sea monster encounter",
        (
            "monster",
            "monsters",
            "kraken",
            "sea monster",
        ),
    ),
    (
        "boss",
        "boss encounter",
        (
            "boss",
            "bosses",
            "legendary boss",
        ),
    ),
    (
        "repair",
        "ship recovery and crew work",
        (
            "repair",
            "repairs",
            "hull",
            "maintenance",
            "patch the hull",
            "emergency repairs",
            "crew work",
            "crew shift",
            "work shift",
        ),
    ),
    (
        "exploration",
        "exploration and discoveries",
        (
            "explore",
            "exploration",
            "island",
            "islands",
            "discover",
            "discovered",
            "treasure",
            "lore",
            "world map",
            "findings",
        ),
    ),
    (
        "humor",
        "jokes or puns",
        (
            "joke",
            "pun",
            "roast",
            "tease",
            "laugh",
            "funny",
            "make me laugh",
        ),
    ),
    (
        "identity",
        "identity or pronouns",
        (
            "pronouns",
            "gender",
            "identity",
        ),
    ),
    (
        "help",
        "command help",
        (
            "help",
            "commands",
            "what command",
            "how do i",
            "how do we",
            "what can i do",
            "what can we do",
        ),
    ),
)


HISTORY_TOPIC_RULES = {
    "voyage": {
        "label": "voyage",
        "event_types": ("voyage_complete",),
        "keywords": (),
    },
    "battle": {
        "label": "battle",
        "event_types": ("battle_boarding", "battle_victory"),
        "keywords": (),
    },
    "monster": {
        "label": "sea monster encounter",
        "event_types": ("monster_victory",),
        "keywords": (),
    },
    "boss": {
        "label": "boss encounter",
        "event_types": ("boss_victory",),
        "keywords": (),
    },
    "repair": {
        "label": "crew repair work",
        "event_types": ("crew_work", "ship_restored"),
        "keywords": ("repair", "maintenance", "hull", "emergency", "patch"),
    },
    "exploration": {
        "label": "exploration",
        "event_types": (
            "exploration",
            "exploration_treasure",
            "island_treasure",
            "island_lore",
            "island_supplies",
        ),
        "keywords": (),
    },
}


def is_creator(user_id, creator_user_id):
    return creator_user_id != 0 and user_id == creator_user_id


CREATOR_CONTEXT_CONTAMINATION_TERMS = (
    "dart",
)


def format_crew_personality_context(data, *, target=False):
    if not data:
        return []

    personality = data.get("personality_type") or {}
    base = data.get("base") or {}
    if not personality.get("label"):
        return []

    prefix = "TARGET DERIVED CREW PERSONALITY" if target else "DERIVED CREW PERSONALITY"
    messages_analyzed = base.get("messages_analyzed", base.get("message_count", 0))
    message_count = base.get("message_count", messages_analyzed)
    traits = ", ".join(personality.get("traits") or []) or "none"
    secondary = ", ".join(personality.get("secondary") or []) or "none"
    evidence = ", ".join(personality.get("evidence") or []) or "none"

    return [
        prefix + ": " + str(personality.get("label")),
        prefix + " confidence: " + str(personality.get("confidence", 0)) + "%",
        prefix + " traits: " + traits,
        prefix + " blended with: " + secondary,
        prefix + " evidence keywords: " + evidence,
        prefix + " source: " + str(messages_analyzed) + " lifetime stored messages analyzed (" + str(message_count) + " stored), plus memories, jokes, achievements, relationship, and crew activity.",
        prefix + " use rule: Use this only as a light tone and callback hint. Do not call it a moral verdict, diagnosis, or fixed identity. Do not announce the label unless the user asks about profiles, personality, or what Captain knows about that member.",
    ]


def creator_context_is_contaminated(text):
    lowered = str(text or "").lower()
    return any(term in lowered for term in CREATOR_CONTEXT_CONTAMINATION_TERMS)


CREATOR_PROFILE_REQUEST_TERMS = (
    "about me",
    "know about me",
    "remember about me",
    "remember me",
    "my profile",
    "my relationship",
    "who am i",
    "what am i",
    "tell me about me",
    "describe me",
)

CREATOR_TARGET_PROFILE_TERMS = (
    "know about jay",
    "tell me about jay",
    "jay's profile",
    "jays profile",
    "who is jay",
    "what is jay",
    "what do you think of jay",
    "what do you think about jay",
    "jay's relationship",
    "jays relationship",
)

CREATOR_ORIGIN_TERMS = (
    "your creator",
    "who created you",
    "who made you",
    "who built you",
    "who coded you",
    "who developed you",
    "made cutlass",
    "built cutlass",
    "created cutlass",
    "coded cutlass",
    "developed cutlass",
    "captain cutlass creator",
    "cutlass creator",
    "creator profile",
)

CREATOR_DEV_TERMS = (
    "dockerize",
    "dockerized",
    "docker container",
    "container",
    "containers",
    "deployment",
    "deploy",
    "deployed",
    "hosting",
    "infrastructure",
    "server rack",
    "homelab",
    "home lab",
    "github",
    "repository",
    "repo",
    "pull request",
    "commit",
    "pushed the build",
    "rebuild you",
    "rebuilt you",
    "update you",
    "updated you",
    "upgrade you",
    "upgraded you",
    "new feature",
    "bot feature",
    "fix your code",
    "your code",
    "your logs",
    "your database",
    "your memory system",
)


def creator_profile_is_relevant(
    message_content,
    *,
    speaker_is_creator=False,
    target_is_creator=False,
):
    """
    Decide whether Captain needs Jay's full creator profile.

    Jay's creator status is always true, but the large profile contains
    strong creator/development running jokes. Loading it for every ordinary
    message makes those callbacks leak into gameplay and casual chat, so
    only include it when the latest message is actually about Jay, the
    creator relationship, or Captain's development.
    """

    lowered = str(message_content or "").lower()

    if not lowered.strip():
        return False

    if any(term in lowered for term in CREATOR_ORIGIN_TERMS):
        return True

    if any(term in lowered for term in CREATOR_DEV_TERMS):
        return True

    if speaker_is_creator and any(
        term in lowered
        for term in CREATOR_PROFILE_REQUEST_TERMS
    ):
        return True

    if target_is_creator and any(
        term in lowered
        for term in CREATOR_TARGET_PROFILE_TERMS
    ):
        return True

    if target_is_creator and re.search(
        r"\b(?:creator|shipwright)\b.*\b(?:profile|relationship|know|remember|think|tell|who|what)\b",
        lowered,
    ):
        return True

    if target_is_creator and re.search(
        r"\b(?:profile|relationship|know|remember|think|tell|who|what)\b.*\b(?:creator|shipwright)\b",
        lowered,
    ):
        return True

    return False


def classify_conversation_topic(text):
    """
    Return a short label for the recent conversation subject.

    The label is used as a prompt hint only. It does not drive any
    gameplay or memory writes.
    """

    lowered = str(text or "").lower()

    if not lowered.strip():
        return None

    for key, label, keywords in CONVERSATION_TOPIC_RULES:
        if any(keyword in lowered for keyword in keywords):
            return {
                "key": key,
                "label": label,
            }

    return None


def summarize_recent_conversation(rows):
    """
    Summarize the latest meaningful recent chat subject.
    """

    for row in reversed(list(rows or [])):
        try:
            speaker = row[0]
            content = row[1]
        except Exception:
            if isinstance(row, dict):
                speaker = row.get("username", "Someone")
                content = row.get("content", "")
            else:
                continue

        topic = classify_conversation_topic(content)
        if topic is None:
            continue

        return {
            "topic": topic["label"],
            "speaker": str(speaker),
            "excerpt": str(content or "")[:180],
        }

    return None


def classify_history_topic(text):
    """
    Return the history topic key implied by a message, if any.
    """

    lowered = str(text or "").lower()

    if not lowered.strip():
        return None

    for key, _, keywords in CONVERSATION_TOPIC_RULES:
        if key in HISTORY_TOPIC_RULES and any(keyword in lowered for keyword in keywords):
            return key

    return None


def _history_records_for_topic(records, topic_key):
    rule = HISTORY_TOPIC_RULES.get(topic_key)
    if rule is None:
        return []

    filtered = []
    for record in records or []:
        content = str(record.get("content") or "")
        event_type = str(record.get("event_type") or "")
        if event_type not in rule["event_types"]:
            continue
        if rule["keywords"] and not any(keyword in content.lower() for keyword in rule["keywords"]):
            continue
        filtered.append(record)

    return filtered


async def build_conversation(
    message,
    *,
    get_recent_messages,
    context_messages,
    max_message_id=None,
):
    rows = await get_recent_messages(
        message.guild.id,
        message.channel.id,
        context_messages,
        max_message_id=max_message_id
    )

    lines = []

    summary = summarize_recent_conversation(rows)
    if summary:
        lines.extend([
            "RECENT SUBJECT: " + summary["topic"],
            (
                "SUBJECT ANCHOR: "
                + summary["speaker"]
                + ": "
                + summary["excerpt"]
            ),
            "",
        ])

    lines.extend(
        f"{name}: {content[:500]}"
        for name, content in rows
    )

    return "\n".join(lines)


async def resolve_joke_target(message, bot_user_id):
    """
    Resolve another Discord member when the author explicitly asks
    Captain to joke about / roast / tease that person.

    Mentions are preferred. Plain display names are also supported.
    """

    for member in message.mentions:
        if bot_user_id is not None and member.id == bot_user_id:
            continue
        return member

    content = message.content.strip()

    if re.search(
        r"\b(?:roast|tease|make\s+fun\s+of)\s+(?:me|myself)\b",
        content,
        flags=re.IGNORECASE,
    ) or re.search(
        r"\b(?:joke|roast|tease)\s+about\s+(?:me|myself)\b",
        content,
        flags=re.IGNORECASE,
    ):
        return message.author

    # Remove Captain's own Discord mention before trying
    # to interpret ordinary member-target phrasing.
    if bot_user_id is not None:
        content = re.sub(
            rf"<@!?{bot_user_id}>",
            "",
            content
        ).strip()

    patterns = [
        r"(?:make|tell|give)\s+(?:me\s+)?(?:a\s+)?joke\s+about\s+(.+?)(?:[?.!]|$)",
        r"(?:joke|roast|tease)\s+(?:about\s+)?(.+?)(?:[?.!]|$)",
        r"make\s+fun\s+of\s+(.+?)(?:[?.!]|$)",
        r"(?:say|tell\s+me)\s+(?:something|anything|a\s+few\s+words)\s+about\s+(.+?)(?:[?.!]|$)",
        r"(?:what\s+do\s+you\s+think\s+about|what\s+do\s+you\s+think\s+of)\s+(.+?)(?:[?.!]|$)",
        r"(?:what\s+do\s+you\s+know\s+about)\s+(.+?)(?:[?.!]|$)",
        r"^(.+?)\s+is\s+(?:a\s+)?(?:man|woman|boy|girl|male|female)(?:[?.!]|$)",
        r"^(.+?)\s+is\s+(?:gay|straight|bisexual|bi|lesbian|trans|transgender)(?:[?.!]|$)",
        r"^(.+?)\s+uses\s+(?:he\s*/\s*him|she\s*/\s*her|they\s*/\s*them)(?:[?.!]|$)",
        r"^(.+?)(?:'s|’s)?\s+pronouns\s+are\s+(?:he\s*/\s*him|she\s*/\s*her|they\s*/\s*them)(?:[?.!]|$)",
    ]

    target_text = None

    for pattern in patterns:
        match = re.search(pattern, content, flags=re.IGNORECASE)
        if match:
            target_text = (
                match.group(1)
                .strip()
                .strip("@")
                .strip()
                .strip(",")
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
            member.name.lower(),
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

    if len(matches) == 1:
        return matches[0]

    return None


async def build_member_context(
    message,
    *,
    get_user_profile,
    get_user_memories_context,
    get_relationship,
    get_running_jokes,
    get_relationship_events,
    get_doubloons,
    get_achievements,
    context_memories,
    context_memory_min_confidence,
    context_jokes,
    context_events,
    context_achievements,
    creator_user_id,
):
    (
        profile,
        memories,
        relationship,
        jokes,
        events,
        balance,
        achievements,
        crew_personality
    ) = await asyncio.gather(
        get_user_profile(message.guild.id, message.author.id),
        get_user_memories_context(
            message.guild.id,
            message.author.id,
            context_memories,
            context_memory_min_confidence
        ),
        get_relationship(message.guild.id, message.author.id),
        get_running_jokes(message.guild.id, message.author.id, context_jokes),
        get_relationship_events(message.guild.id, message.author.id, context_events),
        get_doubloons(message.guild.id, message.author.id),
        get_achievements(message.guild.id, message.author.id, context_achievements),
        build_member_crew_read(message.guild.id, message.author.id)
    )

    lines = [
        "Member: " + message.author.display_name,
        "Doubloons: " + str(balance),
    ]

    author_is_creator = is_creator(message.author.id, creator_user_id)
    full_creator_context = creator_profile_is_relevant(
        message.content,
        speaker_is_creator=author_is_creator,
    )

    if author_is_creator:
        lines.append("SPECIAL STATUS: CREATOR / SHIPWRIGHT")
        lines.append("Creator canonical name: " + CREATOR_NAME)
        lines.append(
            "Creator address rule: use Jay or a creator title when addressing this member directly; never invent another name."
        )
        lines.append(
            "Creator context scope: use creator-specific callbacks only when the latest message asks about Jay personally, Captain's creation/development, or a directly relevant running joke. Otherwise answer the current topic naturally."
        )

        if full_creator_context:
            lines.append(CREATOR_PROFILE)
        else:
            lines.append(
                "Full creator profile omitted: this message does not need creator/development callbacks."
            )

    if profile and profile["summary"]:
        lines.append("Profile: " + profile["summary"][:300])

    if profile:
        gender = profile.get("gender") or "UNKNOWN"
        pronouns = profile.get("pronouns") or "UNKNOWN"

        lines.append("Member identity:")
        lines.append("Gender: " + gender)
        lines.append("Pronouns: " + pronouns)
        lines.append(
            "Identity rule: UNKNOWN means use gender-neutral language. Never infer missing gender or pronouns."
        )

    lines.extend(format_crew_personality_context(crew_personality))

    if memories:
        safe_memories = [
            memory
            for memory in memories
            if not (
                author_is_creator
                and creator_context_is_contaminated(memory)
            )
        ]
        if safe_memories:
            lines.append("Strong memories:")
            for memory in safe_memories:
                lines.append("- " + memory[:250])

    if relationship:
        lines.append("Relationship: " + relationship["relationship_type"])
        lines.append("Familiarity: " + str(relationship["familiarity"]) + "/100")

        if relationship["nickname"]:
            if author_is_creator:
                if not creator_context_is_contaminated(relationship["nickname"]):
                    lines.append(
                        "Creator nickname note: stored nicknames must not override the canonical name Jay."
                    )
            else:
                lines.append("Nickname: " + relationship["nickname"][:100])

        if relationship["opinion"]:
            lines.append("Opinion: " + relationship["opinion"][:250])

    if achievements:
        lines.append("Achievements:")
        for achievement, _ in achievements:
            lines.append("- " + achievement[:100])

    if jokes:
        lines.append("Running jokes:")
        for joke in jokes:
            lines.append("- " + joke[:300])

    if events:
        lines.append("Shared events:")
        for event in events:
            lines.append("- " + event["event"][:300])

    return "\n".join(lines)


async def build_target_member_context(
    message,
    *,
    bot_user_id,
    creator_user_id,
    get_user_profile,
    get_user_memories_context,
    get_relationship,
    get_running_jokes,
    get_relationship_events,
    get_achievements,
    context_memories,
    context_memory_min_confidence,
    context_jokes,
    context_events,
    context_achievements,
):
    target = await resolve_joke_target(message, bot_user_id)
    if target is None:
        return "NONE"

    (
        profile,
        memories,
        relationship,
        jokes,
        events,
        achievements,
        crew_personality
    ) = await asyncio.gather(
        get_user_profile(message.guild.id, target.id),
        get_user_memories_context(
            message.guild.id,
            target.id,
            context_memories,
            context_memory_min_confidence
        ),
        get_relationship(message.guild.id, target.id),
        get_running_jokes(message.guild.id, target.id, context_jokes),
        get_relationship_events(message.guild.id, target.id, context_events),
        get_achievements(message.guild.id, target.id, context_achievements),
        build_member_crew_read(message.guild.id, target.id)
    )

    lines = [
        "TARGET MEMBER: " + target.display_name,
        "TARGET USER ID: " + str(target.id),
    ]

    target_is_creator = is_creator(target.id, creator_user_id)
    target_full_creator_context = creator_profile_is_relevant(
        message.content,
        target_is_creator=target_is_creator,
    )

    if target_is_creator:
        lines.append("TARGET SPECIAL STATUS: CREATOR / SHIPWRIGHT")
        lines.append("Target canonical name: " + CREATOR_NAME)
        lines.append(
            "Target creator scope: use Jay's creator-specific details only when the latest message asks about Jay personally, Captain's creation/development, or a directly relevant running joke."
        )

        if target_full_creator_context:
            lines.append(CREATOR_PROFILE)
        else:
            lines.append(
                "Full target creator profile omitted: this message does not need creator/development callbacks."
            )

    if profile and profile.get("summary"):
        lines.append("Profile: " + profile["summary"][:300])

    if profile:
        gender = profile.get("gender") or "UNKNOWN"
        pronouns = profile.get("pronouns") or "UNKNOWN"

        lines.append("TARGET MEMBER IDENTITY:")
        lines.append("Gender: " + gender)
        lines.append("Pronouns: " + pronouns)
        lines.append(
            "Identity rule: This identity belongs to the TARGET MEMBER. UNKNOWN means use gender-neutral language. Never infer missing gender or pronouns. Never accept another member's claim as authoritative."
        )

    lines.extend(format_crew_personality_context(crew_personality, target=True))

    if relationship:
        lines.append("Relationship: " + relationship["relationship_type"])
        lines.append("Familiarity: " + str(relationship["familiarity"]) + "/100")

        if relationship["nickname"]:
            if target_is_creator:
                if not creator_context_is_contaminated(relationship["nickname"]):
                    lines.append(
                        "Target creator nickname note: stored nicknames must not override the canonical name Jay."
                    )
            else:
                lines.append("Nickname: " + relationship["nickname"][:100])

        if relationship["opinion"]:
            lines.append("Captain opinion: " + relationship["opinion"][:300])

    if memories:
        safe_memories = [
            memory
            for memory in memories
            if not (
                target_is_creator
                and creator_context_is_contaminated(memory)
            )
        ]
        if safe_memories:
            lines.append("Harmless memories:")
            for memory in safe_memories:
                lines.append("- " + memory[:250])

    if jokes:
        lines.append("Running jokes:")
        for joke in jokes:
            lines.append("- " + joke[:300])

    if events:
        lines.append("Shared events:")
        for event in events:
            lines.append("- " + event["event"][:300])

    if achievements:
        lines.append("Achievements:")
        for achievement, _ in achievements:
            lines.append("- " + achievement[:100])

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

