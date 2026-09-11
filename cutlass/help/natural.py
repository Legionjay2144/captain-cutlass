"""
Captain Cutlass — Natural Command Help

Authoritative lightweight command-discovery layer.

This module does not execute commands and does not call AI.
It maps natural gameplay/help requests to commands that
actually exist in Captain Cutlass.
"""

import difflib
import re


COMMAND_HELP = {
    # ---------------------------------------------------------
    # General
    # ---------------------------------------------------------
    "help": {
        "command": "!c help",
        "description": "open Captain Cutlass help",
        "terms": (
            "help",
            "commands",
            "command list",
            "what can you do",
            "what can i do",
            "how do i play",
        ),
    },

    # ---------------------------------------------------------
    # Crew / economy
    # ---------------------------------------------------------
    "earn_doubloons": {
        "command": "!c explore",
        "description": (
            "earn Doubloons through exploration, islands, combat, "
            "achievements, treasure, and crew contributions"
        ),
        "terms": (
            "earn doubloons",
            "earn some doubloons",
            "earn more doubloons",
            "make doubloons",
            "make some doubloons",
            "make more doubloons",
            "get doubloons",
            "get some doubloons",
            "get more doubloons",
            "earn money",
            "earn some money",
            "earn more money",
            "make money",
            "make some money",
            "make more money",
            "get money",
            "get some money",
            "get more money",
            "how to earn doubloons",
            "how to make doubloons",
            "how to get doubloons",
        ),
    },

    "balance": {
        "command": "!c balance",
        "description": "view your Doubloon balance",
        "terms": (
            "balance",
            "doubloons",
            "my doubloons",
            "money",
            "coins",
            "how much money",
            "how many doubloons",
        ),
    },
    "achievements": {
        "command": "!c achievements",
        "description": "view your achievements",
        "terms": (
            "achievement",
            "achievements",
            "awards",
            "what achievements",
        ),
    },
    "leaderboard": {
        "command": "!c leaderboard",
        "description": "view the Doubloon leaderboard",
        "terms": (
            "leaderboard",
            "richest",
            "most doubloons",
            "top doubloons",
        ),
    },
    "profile": {
        "command": "!c profile",
        "description": "view your crew profile",
        "terms": (
            "profile",
            "my profile",
            "crew profile",
        ),
    },
    "stats": {
        "command": "!c stats",
        "description": "view your crew statistics",
        "terms": (
            "stats",
            "statistics",
            "my stats",
        ),
    },
    "crew": {
        "command": "!c crew",
        "description": "view the top crewmates",
        "terms": (
            "crew",
            "top crew",
            "top crewmates",
        ),
    },
    "memory": {
        "command": "!c memory",
        "description": "view the Captain's memories of you",
        "terms": (
            "memory",
            "memories",
            "my memories",
            "what do you remember about me",
        ),
    },
    "relationship": {
        "command": "!c relationship",
        "description": "view your relationship with the Captain",
        "terms": (
            "relationship",
            "our relationship",
            "relationship status",
        ),
    },
    "birthday": {
        "command": "!c birthday",
        "description": "view your recorded birthday",
        "terms": (
            "birthday",
            "my birthday",
            "when is my birthday",
        ),
    },
    "birthdays": {
        "command": "!c birthdays",
        "description": "view crew birthdays",
        "terms": (
            "crew birthdays",
            "birthdays",
            "whose birthday",
        ),
    },
    "forgetme": {
        "command": "!c forgetme",
        "description": "remove stored memories about you",
        "terms": (
            "forget me",
            "forget everything about me",
            "delete my memories",
            "remove my memories",
        ),
    },
    "creator": {
        "command": "!c creator",
        "description": "view creator recognition",
        "terms": (
            "creator",
            "who created you",
            "who made you",
        ),
    },

    # ---------------------------------------------------------
    # Crew work
    # ---------------------------------------------------------
    "jobs": {
        "command": "!c jobs",
        "description": "view the crew job board",
        "terms": (
            "jobs",
            "job board",
            "crew jobs",
            "available work",
            "what jobs are available",
        ),
    },
    "work": {
        "command": "!c work <job>",
        "description": "take a crew shift or view your work ledger",
        "terms": (
            "work",
            "crew work",
            "take a shift",
            "work a job",
            "work ledger",
            "job shift",
        ),
    },

    # ---------------------------------------------------------
    # Living Ship
    # ---------------------------------------------------------
    "ship": {
        "command": "!c ship",
        "description": "view Living Ship status",
        "terms": (
            "ship",
            "ship status",
            "living ship",
            "hull",
            "ship health",
            "how is the ship",
        ),
    },
    "repair": {
        "command": "!c repair",
        "description": "repair the Living Ship",
        "terms": (
            "repair",
            "repair ship",
            "fix ship",
            "fix the ship",
            "fix our ship",
            "heal ship",
            "restore hull",
        ),
    },
    "treasury": {
        "command": "!c treasury",
        "description": "view the Living Ship treasury",
        "terms": (
            "treasury",
            "ship money",
            "ship doubloons",
            "ship treasury",
        ),
    },
    "donate": {
        "command": "!c ship donate <amount>",
        "description": "donate Doubloons to the Living Ship",
        "terms": (
            "donate",
            "donate doubloons",
            "give ship money",
            "give doubloons to ship",
            "contribute",
            "contribution",
        ),
    },
    "upgrades": {
        "command": "!c upgrades",
        "description": "view Living Ship upgrades",
        "terms": (
            "upgrade",
            "upgrades",
            "ship upgrades",
            "improve ship",
        ),
    },
    "ship_history": {
        "command": "!c ship history",
        "description": "view the Living Ship's recorded history",
        "terms": (
            "ship history",
            "ship's history",
            "vessel history",
        ),
    },
    "ship_captures": {
        "command": "!c ship captures",
        "description": "view captured vessels",
        "terms": (
            "captured ships",
            "captured vessels",
            "ship captures",
            "prize ledger",
        ),
    },
    "capture_sell": {
        "command": "!c ship capture sell <id>",
        "description": "sell a captured vessel",
        "terms": (
            "sell captured ship",
            "sell captured vessel",
            "sell a captured vessel",
            "sell a prize ship",
        ),
    },
    "capture_salvage": {
        "command": "!c ship capture salvage <id>",
        "description": "salvage a captured vessel for parts",
        "terms": (
            "salvage captured ship",
            "salvage captured vessel",
            "salvage a captured vessel",
            "salvage a prize ship",
        ),
    },

    # ---------------------------------------------------------
    # Voyages / world
    # ---------------------------------------------------------
    "destinations": {
        "command": "!c destinations",
        "description": "view charted voyage destinations",
        "terms": (
            "destination",
            "destinations",
            "where can we sail",
            "where can we go",
            "where can i sail",
            "routes",
            "voyage routes",
        ),
    },
    "voyage": {
        "command": "!c voyage start <number>",
        "description": "start a voyage to a charted destination",
        "terms": (
            "voyage",
            "start voyage",
            "start a voyage",
            "set sail",
            "sail somewhere",
            "travel to island",
            "go to island",
        ),
    },
    "voyage_status": {
        "command": "!c voyage status",
        "description": "view the current voyage",
        "terms": (
            "voyage status",
            "current voyage",
            "are we sailing",
            "where are we sailing",
        ),
    },
    "explore": {
        "command": "!c explore",
        "description": "scout surrounding waters",
        "terms": (
            "explore",
            "scout",
            "scouting",
            "discover island",
            "find island",
            "find islands",
            "discoveries",
        ),
    },
    "island": {
        "command": "!c island",
        "description": "inspect the island at the ship's location",
        "terms": (
            "island",
            "current island",
            "where are we",
            "what island",
            "inspect island",
        ),
    },
    "island_explore": {
        "command": "!c island explore",
        "description": "explore the island where the ship is anchored",
        "terms": (
            "island explore",
            "explore island",
            "explore the island",
            "search island",
            "search the island",
        ),
    },
    "world": {
        "command": "!c world",
        "description": "view Pirate World status",
        "terms": (
            "world",
            "pirate world",
            "world status",
        ),
    },
    "world_findings": {
        "command": "!c world findings",
        "description": (
            "view unique findings uncovered "
            "across the Pirate World"
        ),
        "terms": (
            "world findings",
            "findings",
            "special discoveries",
            "unique discoveries",
            "found landmarks",
            "found ruins",
            "found wrecks",
        ),
    },
    "world_locations": {
        "command": "!c world locations",
        "description": "view discovered world locations",
        "terms": (
            "world locations",
            "discovered locations",
            "known locations",
        ),
    },
    "world_history": {
        "command": "!c world history",
        "description": "view Pirate World discovery history",
        "terms": (
            "world history",
            "discovery history",
            "world discoveries history",
        ),
    },

    "world_events": {
        "command": "!c world events",
        "description": (
            "view the active Living World Event "
            "and its regional effects"
        ),
        "terms": (
            "world events",
            "world event",
            "active event",
            "current event",
            "living world event",
            "regional event",
            "sea conditions",
        ),
    },

    "world_map": {
        "command": "!c world map",
        "description": "view the discovered Pirate World map",
        "terms": (
            "map",
            "world map",
            "show map",
            "pirate map",
        ),
    },

    # ---------------------------------------------------------
    # Lore, parrot, and recorded history
    # ---------------------------------------------------------
    "parrot": {
        "command": "!c parrot",
        "description": "view the parrot's status",
        "terms": (
            "parrot",
            "parrot status",
            "bird status",
        ),
    },
    "parrot_talk": {
        "command": "!c parrot talk <message>",
        "description": "talk directly to the parrot",
        "terms": (
            "talk to the parrot",
            "speak to the parrot",
            "parrot talk",
        ),
    },
    "parrot_relationship": {
        "command": "!c parrot relationship",
        "description": "view your relationship with the parrot",
        "terms": (
            "parrot relationship",
            "relationship with the parrot",
        ),
    },
    "parrot_memories": {
        "command": "!c parrot memories",
        "description": "view the parrot's memories of you",
        "terms": (
            "parrot memories",
            "parrot memory",
        ),
    },
    "parrot_jokes": {
        "command": "!c parrot jokes",
        "description": "view running parrot jokes",
        "terms": (
            "parrot jokes",
            "running parrot jokes",
        ),
    },
    "parrot_history": {
        "command": "!c parrot history",
        "description": "view Captain and parrot history",
        "terms": (
            "parrot history",
            "captain parrot history",
            "parrot banter history",
        ),
    },
    "lore": {
        "command": "!c lore",
        "description": "view Captain Cutlass lore",
        "terms": (
            "lore",
            "captain lore",
            "cutlass lore",
        ),
    },
    "canon": {
        "command": "!c canon",
        "description": "view Captain Core Canon",
        "terms": (
            "canon",
            "captain canon",
            "core canon",
        ),
    },
    "serverlore": {
        "command": "!c serverlore",
        "description": "view server lore",
        "terms": (
            "server lore",
            "our lore",
        ),
    },
    "quote": {
        "command": "!c quote",
        "description": "hear a random Captain quote",
        "terms": (
            "quote",
            "captain quote",
            "random quote",
        ),
    },
    "wisdom": {
        "command": "!c wisdom",
        "description": "hear pirate wisdom",
        "terms": (
            "wisdom",
            "pirate wisdom",
        ),
    },
    "journal": {
        "command": "!c journal",
        "description": "view the Captain's Journal",
        "terms": (
            "journal",
            "captain's journal",
        ),
    },
    "timeline": {
        "command": "!c timeline",
        "description": "view the ship timeline",
        "terms": (
            "timeline",
            "ship timeline",
        ),
    },
    "treasure_clue": {
        "command": "!c treasure clue",
        "description": "view the current treasure clue",
        "terms": (
            "treasure clue",
            "current clue",
            "clue",
        ),
    },
    "savequote": {
        "command": "!c savequote",
        "description": "save a Captain quote from a replied message",
        "terms": (
            "save a quote",
            "save quote",
            "remember this quote",
        ),
    },
    "chronicle": {
        "command": "!c chronicle latest",
        "description": "view the latest weekly chronicle",
        "terms": (
            "chronicle",
            "latest chronicle",
            "weekly chronicle",
        ),
    },

    # ---------------------------------------------------------
    # Combat
    # ---------------------------------------------------------
    "attack": {
        "command": "!c attack",
        "description": "attack the active encounter",
        "terms": (
            "attack",
            "fight",
            "hit enemy",
            "shoot enemy",
            "fire cannons",
            "combat attack",
        ),
    },
    "defend": {
        "command": "!c defend",
        "description": "take a defensive combat action",
        "terms": (
            "defend",
            "defense",
            "protect ship",
            "brace in combat",
        ),
    },
    "board": {
        "command": "!c board",
        "description": "board a weakened naval enemy",
        "terms": (
            "board",
            "boarding",
            "capture ship",
            "capture enemy ship",
            "take enemy ship",
        ),
    },
    "flee": {
        "command": "!c flee",
        "description": "attempt to escape a naval battle",
        "terms": (
            "flee",
            "escape",
            "run away",
            "leave battle",
            "escape battle",
        ),
    },
    "battle": {
        "command": "!c battle",
        "description": "view the current naval battle",
        "terms": (
            "battle",
            "battle status",
            "naval battle",
            "enemy ship",
        ),
    },
    "monster": {
        "command": "!c monster",
        "description": "view the current sea monster encounter",
        "terms": (
            "monster",
            "sea monster",
            "kraken",
            "monster status",
        ),
    },
    "boss": {
        "command": "!c boss",
        "description": "view the current boss encounter",
        "terms": (
            "boss",
            "boss fight",
            "boss status",
            "legendary boss",
        ),
    },

    # ---------------------------------------------------------
    # Combat abilities
    # ---------------------------------------------------------
    "abilities": {
        "command": "!c abilities",
        "description": "view ship combat abilities and cooldowns",
        "terms": (
            "ability",
            "abilities",
            "combat abilities",
            "cooldown",
            "cooldowns",
            "special ability",
            "special abilities",
        ),
    },
    "broadside": {
        "command": "!c ability full broadside",
        "description": "arm Full Broadside for +50% outgoing attack damage",
        "terms": (
            "full broadside",
            "broadside",
            "more damage",
            "damage ability",
        ),
    },
    "brace": {
        "command": "!c ability brace for impact",
        "description": "arm Brace for Impact to reduce the next incoming hit",
        "terms": (
            "brace for impact",
            "brace",
            "reduce damage",
            "damage reduction",
        ),
    },
    "emergency_repairs": {
        "command": "!c ability emergency repairs",
        "description": "restore 10% max hull during combat",
        "terms": (
            "emergency repairs",
            "emergency repair",
            "heal in combat",
            "repair in combat",
        ),
    },
    "rally": {
        "command": "!c ability rally the crew",
        "description": "boost outgoing damage and reduce incoming damage",
        "terms": (
            "rally the crew",
            "rally",
            "crew rally",
        ),
    },
}


# -------------------------------------------------------------
# Natural/contextual help intent priority
#
# Explicit requested actions must beat broad gameplay language.
#
# Examples:
#   "flee from this fight" -> flee, not attack
#   "board them in this battle" -> board, not battle status
#   "defend during the fight" -> defend, not attack
#   "emergency repairs" -> ability, not normal repair
#
# Phrase length is only a secondary tie-breaker.
# -------------------------------------------------------------

HELP_INTENT_PRIORITY = {
    # Highly specific combat abilities.
    "emergency_repairs": 500,
    "broadside": 500,
    "brace": 500,
    "rally": 500,

    # Explicit tactical actions.
    "board": 400,
    "defend": 400,
    "flee": 400,

    # Explicit ship/economy/world actions.
    "earn_doubloons": 450,
    "donate": 400,
    "repair": 400,
    "island_explore": 400,
    "destinations": 400,
    "voyage": 400,
    "jobs": 400,
    "work": 400,
    "savequote": 400,

    # Explicit generic combat action.
    "attack": 300,

    # Broad/status concepts should never outrank an action.
    "battle": 100,
    "monster": 100,
    "boss": 100,
    "ship": 100,
    "island": 100,
    "world": 100,
}


def help_intent_priority(key):
    return HELP_INTENT_PRIORITY.get(
        key,
        200
    )


# -------------------------------------------------------------
# Shared explicit natural-help intent phrases
#
# Both direct questions and contextual follow-ups use this table.
# Keeping one authoritative mapping prevents the two resolvers
# from drifting apart as gameplay commands evolve.
# -------------------------------------------------------------

HELP_ACTION_INTENTS = (
    # Specific combat abilities.
    ("emergency repairs", "emergency_repairs"),
    ("emergency repair", "emergency_repairs"),
    ("brace for impact", "brace"),
    ("full broadside", "broadside"),
    ("rally the crew", "rally"),

    # Specific exploration actions.
    ("explore the island", "island_explore"),
    ("explore island", "island_explore"),
    ("search the island", "island_explore"),
    ("search island", "island_explore"),

    # Navigation / voyage actions.
    ("where can we sail", "destinations"),
    ("where can i sail", "destinations"),
    ("where we can sail", "destinations"),
    ("where i can sail", "destinations"),
    ("where can we go", "destinations"),
    ("where can i go", "destinations"),
    ("where we can go", "destinations"),
    ("where i can go", "destinations"),
    ("places we can sail", "destinations"),
    ("places i can sail", "destinations"),
    ("places can we sail", "destinations"),
    ("places can i sail", "destinations"),
    ("voyage routes", "destinations"),
    ("start a voyage", "voyage"),
    ("start voyage", "voyage"),
    ("set sail", "voyage"),

    # Crew work actions.
    ("job board", "jobs"),
    ("crew jobs", "jobs"),
    ("available work", "jobs"),
    ("crew work", "work"),
    ("take a shift", "work"),
    ("take a crew shift", "work"),
    ("work a job", "work"),

    # Explicit quote action.
    ("save a quote", "savequote"),
    ("save quote", "savequote"),
    ("saves a quote", "savequote"),
    ("saving a quote", "savequote"),

    # Explicit tactical actions.
    ("boarding", "board"),
    ("board", "board"),
    ("defend", "defend"),
    ("flee", "flee"),
    ("escape", "flee"),
    ("attack", "attack"),

    # Doubloon earning intent.
    ("earn some doubloons", "earn_doubloons"),
    ("earn more doubloons", "earn_doubloons"),
    ("earn doubloons", "earn_doubloons"),
    ("make some doubloons", "earn_doubloons"),
    ("make more doubloons", "earn_doubloons"),
    ("make doubloons", "earn_doubloons"),
    ("get some doubloons", "earn_doubloons"),
    ("get more doubloons", "earn_doubloons"),
    ("get doubloons", "earn_doubloons"),
    ("earn some money", "earn_doubloons"),
    ("earn more money", "earn_doubloons"),
    ("earn money", "earn_doubloons"),
    ("make some money", "earn_doubloons"),
    ("make more money", "earn_doubloons"),
    ("make money", "earn_doubloons"),
    ("get some money", "earn_doubloons"),
    ("get more money", "earn_doubloons"),
    ("get money", "earn_doubloons"),

    # Ship / economy actions.
    ("donate", "donate"),
    ("contribute", "donate"),
    ("repair", "repair"),
    ("fix", "repair"),

    # Broad fallback action.
    ("fight", "attack"),
)


def resolve_explicit_help_intent(normalized):
    """
    Resolve the highest-priority explicit gameplay action.

    Priority wins first. Phrase length is the tie-breaker.
    """

    matches = [
        (phrase, key)
        for phrase, key in HELP_ACTION_INTENTS
        if phrase in normalized
    ]

    matches.sort(
        key=lambda row: (
            help_intent_priority(row[1]),
            len(row[0]),
        ),
        reverse=True,
    )

    for phrase, key in matches:
        entry = COMMAND_HELP.get(key)

        if entry is not None:
            return {
                "key": key,
                "command": entry["command"],
                "description": entry["description"],
            }

    return None


def normalize_help_text(text):
    text = str(text or "").lower()

    text = re.sub(
        r"<@!?\d+>",
        " ",
        text,
    )

    text = re.sub(
        r"[^a-z0-9\s!]",
        " ",
        text,
    )

    return " ".join(
        text.split()
    )


def _looks_like_help_request(text):
    """
    Avoid hijacking ordinary conversation merely because it
    happens to contain a gameplay noun.
    """

    patterns = (
        r"\bhow\s+(?:do|can|would|should)\s+i\b",
        r"\bhow\s+(?:do|can|would|should)\s+we\b",
        r"\bwhat\s+command\b",
        r"\bwhich\s+command\b",
        r"\bwhat\s+do\s+i\s+type\b",
        r"\bwhat\s+should\s+i\s+type\b",
        r"\bhow\s+does\b",
        r"\bhow\s+do\s+abilities\b",
        r"\bhelp\b",
        r"\bcommands?\b",
        r"\bwhat\s+can\s+i\s+do\b",
        r"\bwhat\s+can\s+we\s+do\b",
        r"\bwhat\s+(?:achievements?|awards?|stats|statistics|profile|memories|birthday|relationship)\b",
        r"\bmy\s+(?:achievements?|awards?|stats|statistics|profile|memories|birthday|relationship)\b",
        r"\b(?:ship\s+history|world\s+history|discovery\s+history|ship\s+timeline|latest\s+chronicle|weekly\s+chronicle)\b",
        r"\bwhat\s+happened\s+in\s+(?:ship|world)\s+history\b",
        r"\bwhat\s+is\s+our\s+ship\s+history\b",
        r"\bwhere\s+can\s+(?:i|we)\b",
        r"\bwhat\s+.+\s+are\s+available\b",
        r"\bshow\s+(?:me\s+)?(?:the\s+)?",
        r"\blist\s+(?:the\s+)?",
        r"\bhow\s+do\s+i\s+get\b",
        r"\bhow\s+do\s+we\s+get\b",
        r"\bhow\s+do\s+i\s+earn\b",
        r"\bhow\s+do\s+we\s+earn\b",
        r"\bhow\s+many\b",
        r"\bhow\s+much\b",
    )

    return any(
        re.search(pattern, text)
        for pattern in patterns
    )


FOLLOWUP_HELP_PATTERNS = (
    "how do i do that",
    "how do we do that",
    "how do i do it",
    "how do we do it",
    "what command was that",
    "what command do i use",
    "which command was that",
    "how does that work",
    "how do i use that",
    "how do we use that",
    "what about that",
)


def is_contextual_help_followup(text):
    """
    Detect short natural help follow-ups that depend on the
    immediately preceding gameplay topic.
    """

    normalized = normalize_help_text(text)

    if not normalized:
        return False

    return any(
        phrase in normalized
        for phrase in FOLLOWUP_HELP_PATTERNS
    )


def find_contextual_command_help(text, recent_messages):
    """
    Resolve a natural help follow-up against recent conversation.

    The current message must look like a contextual follow-up.
    Recent messages are searched newest-first for the first real
    authoritative command topic.

    This does not invent syntax and does not call AI.
    """

    if not is_contextual_help_followup(text):
        return None

    recent_messages = list(
        recent_messages or []
    )

    for recent in recent_messages:

        if isinstance(recent, (tuple, list)):
            # Existing conversation rows commonly store message
            # content in position 1.
            if len(recent) >= 2:
                recent = recent[1]
            elif recent:
                recent = recent[0]
            else:
                continue

        recent_text = str(
            recent or ""
        ).strip()

        if not recent_text:
            continue

        # First try explicit natural-help wording.
        result = find_natural_command_help(
            recent_text
        )

        if result:
            return result

        # Then identify the gameplay topic even if the original
        # message was ordinary conversation rather than a help
        # request.
        normalized = normalize_help_text(
            recent_text
        )

        # -----------------------------------------------------
        # Contextual action / intent priority
        #
        # Explicit actions must beat generic nouns:
        #
        #   "flee this battle" -> flee, not battle status
        #   "board that ship" -> board, not battle status
        #   "donate doubloons" -> donate, not balance
        #
        # Specific navigation language is also resolved before
        # broad fallback matching.
        # -----------------------------------------------------

        explicit_intent = resolve_explicit_help_intent(
            normalized
        )

        if explicit_intent:
            return explicit_intent

        # -----------------------------------------------------
        # Generic topic fallback
        # -----------------------------------------------------

        matches = []

        for key, entry in COMMAND_HELP.items():

            best_term = None

            for term in entry["terms"]:

                normalized_term = normalize_help_text(
                    term
                )

                if (
                    normalized_term
                    and normalized_term in normalized
                ):
                    if (
                        best_term is None
                        or len(normalized_term) > len(best_term)
                    ):
                        best_term = normalized_term

            if best_term is not None:
                matches.append(
                    (
                        len(best_term),
                        key,
                        entry,
                    )
                )

        if matches:

            matches.sort(
                key=lambda row: row[0],
                reverse=True,
            )

            key = matches[0][1]
            entry = matches[0][2]

            return {
                "key": key,
                "command": entry["command"],
                "description": entry["description"],
            }

    return None



def find_natural_command_help(text):
    """
    Return the best authoritative command-help entry for a
    natural-language help request.

    Returns None when the message does not look like help.
    """

    normalized = normalize_help_text(text)

    if not normalized:
        return None

    if not _looks_like_help_request(normalized):
        return None

    # -----------------------------------------------------
    # Explicit action intent
    #
    # When a member asks "how do I board an enemy ship?"
    # the requested ACTION must beat broader nouns such as
    # "enemy ship" or "battle".
    # -----------------------------------------------------

    explicit_intent = resolve_explicit_help_intent(
        normalized
    )

    if explicit_intent:
        return explicit_intent

    # More specific phrases win when no explicit action intent
    # was found.
    matches = []

    for key, entry in COMMAND_HELP.items():

        best_term = None

        for term in entry["terms"]:
            normalized_term = normalize_help_text(term)

            if normalized_term in normalized:
                if (
                    best_term is None
                    or len(normalized_term) > len(best_term)
                ):
                    best_term = normalized_term

        if best_term is not None:
            matches.append(
                (
                    len(best_term),
                    key,
                    entry,
                )
            )

    if not matches:
        return None

    matches.sort(
        key=lambda row: row[0],
        reverse=True,
    )

    key = matches[0][1]
    entry = matches[0][2]

    return {
        "key": key,
        "command": entry["command"],
        "description": entry["description"],
    }


def command_suggestions(raw_command, limit=3):
    """
    Suggest real Captain commands for an unknown !c / !cutlass
    command without inventing new commands.
    """

    normalized = normalize_help_text(raw_command)

    normalized = re.sub(
        r"^!(?:c|cutlass)\s*",
        "",
        normalized,
    ).strip()

    if not normalized:
        return []

    candidates = []

    for entry in COMMAND_HELP.values():
        command = entry["command"]

        short = re.sub(
            r"^!c\s*",
            "",
            command.lower(),
        )

        short = re.sub(
            r"\s*<[^>]+>",
            "",
            short,
        ).strip()

        candidates.append(
            (
                short,
                command,
                entry["description"],
            )
        )

    candidate_names = sorted(
        {
            row[0]
            for row in candidates
            if row[0]
        }
    )

    close = difflib.get_close_matches(
        normalized,
        candidate_names,
        n=max(1, int(limit)),
        cutoff=0.35,
    )

    results = []

    for name in close:

        for candidate_name, command, description in candidates:

            if candidate_name != name:
                continue

            item = {
                "command": command,
                "description": description,
            }

            if item not in results:
                results.append(item)

            break

    return results[:limit]


def format_natural_help(result):
    if not result:
        return None

    return (
        "Aye — use **`"
        + result["command"]
        + "`** to "
        + result["description"]
        + "."
    )
