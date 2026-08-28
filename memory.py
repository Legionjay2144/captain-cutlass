import asyncio
import re

import aiosqlite


DATABASE = "/app/data/captain.db"

_db = None
_write_lock = asyncio.Lock()


async def get_db():

    global _db

    if _db is None:

        _db = await aiosqlite.connect(
            DATABASE
        )

        await _db.execute(
            "PRAGMA journal_mode=WAL"
        )

        await _db.execute(
            "PRAGMA synchronous=NORMAL"
        )

        await _db.execute(
            "PRAGMA busy_timeout=5000"
        )

        await _db.execute(
            "PRAGMA temp_store=MEMORY"
        )

        await _db.commit()

    return _db


async def column_exists(
    db,
    table,
    column
):

    cursor = await db.execute(
        f"PRAGMA table_info({table})"
    )

    rows = await cursor.fetchall()

    return any(
        row[1] == column
        for row in rows
    )


def normalize_memory(
    memory
):
    """
    Convert memories, jokes, and events into a stable
    comparison form.

    The goal is NOT to rewrite stored text. This is used
    only for duplicate detection.
    """

    value = str(
        memory or ""
    ).lower().strip()

    # -----------------------------------------------------
    # Phrase normalization
    # -----------------------------------------------------

    replacements = {
        "really likes": "likes",
        "really loves": "likes",
        "is fond of": "likes",
        "enjoys": "likes",
        "loves": "likes",
        "favourite": "favorite",

        "terrible": "bad",
        "awful": "bad",
        "horrible": "bad",

        "jokes": "joke",
        "puns": "pun",

        "threatened a mutiny": "mutiny",
        "threatening mutiny": "mutiny",
        "called for a mutiny": "mutiny",
        "called for mutiny": "mutiny",

        "called for a punbattle": "punbattle",
        "called for punbattle": "punbattle",

        "took a midnight nap": "midnight nap",
        "had a midnight nap": "midnight nap",
    }

    for old, new in replacements.items():
        value = value.replace(
            old,
            new
        )

    # Remove punctuation.
    value = re.sub(
        r"[^a-z0-9 ]+",
        " ",
        value
    )

    # -----------------------------------------------------
    # Remove low-information filler words
    # -----------------------------------------------------

    stop_words = {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "for",
        "of",
        "to",
        "in",
        "on",
        "at",
        "with",
        "while",
        "that",
        "this",
        "those",
        "these",
        "was",
        "were",
        "is",
        "are",
        "be",
        "been",
        "being",
        "once",
        "just",
        "really",
        "still",
        "some",
        "more",
        "very",
        "his",
        "her",
        "their",
        "they",
        "he",
        "she",
        "it",
        "me",
        "my",
        "our",
        "your",
        "you",
        "yer",
        "ye",
        "keeps",
        "keep",
        "known",
        "got",
        "has",
        "had",
        "have",
        "did",
        "does",
        "do",
        "off",
        "even",
    }

    words = []

    for word in value.split():

        if word in stop_words:
            continue

        # Tiny bit of safe plural normalization.
        if (
            len(word) > 4
            and word.endswith("s")
            and not word.endswith("ss")
        ):
            word = word[:-1]

        words.append(
            word
        )

    return " ".join(
        words
    ).strip()


def memory_similarity(
    first,
    second
):
    """
    Compare two pieces of stored context using normalized
    meaningful vocabulary.

    Returns 0.0 to 1.0.
    """

    first_norm = normalize_memory(
        first
    )

    second_norm = normalize_memory(
        second
    )

    if not first_norm or not second_norm:
        return 0.0

    if first_norm == second_norm:
        return 1.0

    first_words = set(
        first_norm.split()
    )

    second_words = set(
        second_norm.split()
    )

    if not first_words or not second_words:
        return 0.0

    shared = (
        first_words
        & second_words
    )

    dice_score = (
        2.0
        * len(shared)
        / (
            len(first_words)
            + len(second_words)
        )
    )

    # If the smaller concept is almost entirely contained
    # within the longer one, treat that as strong evidence
    # of a paraphrased duplicate.
    smaller = min(
        len(first_words),
        len(second_words)
    )

    containment = (
        len(shared) / smaller
        if smaller
        else 0.0
    )

    if containment >= 0.85:
        return max(
            dice_score,
            0.82
        )

    return dice_score


def is_near_duplicate(
    first,
    second,
    threshold=0.72
):
    return (
        memory_similarity(
            first,
            second
        )
        >= threshold
    )


def memory_numbers(
    value
):
    """
    Extract explicit numeric facts from stored context.

    Used to prevent facts such as familiarity 25/100 and
    familiarity 50/100 from being collapsed together merely
    because their surrounding wording is similar.
    """

    return {
        int(number)
        for number in re.findall(
            r"\\b\\d+\\b",
            str(value or "")
        )
    }


def has_conflicting_numbers(
    first,
    second
):
    first_numbers = memory_numbers(
        first
    )

    second_numbers = memory_numbers(
        second
    )

    return bool(
        first_numbers
        and second_numbers
        and first_numbers != second_numbers
    )


def is_safe_duplicate(
    first,
    second,
    threshold=0.90
):
    """
    Conservative duplicate detection for durable memory.

    Exact normalized matches are duplicates.

    Near-matches are accepted only at a high threshold and
    only when explicit numeric facts do not disagree.
    """

    first_normalized = normalize_memory(
        first
    )

    second_normalized = normalize_memory(
        second
    )

    if (
        not first_normalized
        or not second_normalized
    ):
        return False

    if (
        first_normalized
        == second_normalized
    ):
        return True

    if has_conflicting_numbers(
        first,
        second
    ):
        return False

    return (
        memory_similarity(
            first,
            second
        )
        >= float(threshold)
    )


async def initialize_database():

    db = await get_db()

    async with _write_lock:

        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                channel_id INTEGER,
                user_id INTEGER,
                username TEXT,
                content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                summary TEXT DEFAULT '',
                gender TEXT,
                pronouns TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, user_id)
            )
        """)

        # Explicit identity fields.
        # NULL means unknown and must be treated as gender-neutral.
        if not await column_exists(
            db,
            "user_profiles",
            "gender"
        ):
            await db.execute(
                "ALTER TABLE user_profiles ADD COLUMN gender TEXT"
            )

        if not await column_exists(
            db,
            "user_profiles",
            "pronouns"
        ):
            await db.execute(
                "ALTER TABLE user_profiles ADD COLUMN pronouns TEXT"
            )

        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                memory TEXT NOT NULL,
                confidence INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        if not await column_exists(
            db,
            "user_memories",
            "confidence"
        ):

            await db.execute("""
                ALTER TABLE user_memories
                ADD COLUMN confidence INTEGER DEFAULT 1
            """)

        if not await column_exists(
            db,
            "user_memories",
            "updated_at"
        ):

            await db.execute("""
                ALTER TABLE user_memories
                ADD COLUMN updated_at DATETIME
            """)

            await db.execute("""
                UPDATE user_memories
                SET updated_at = CURRENT_TIMESTAMP
                WHERE updated_at IS NULL
            """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS captain_canon (
                canon_key TEXT PRIMARY KEY,
                canon_value TEXT NOT NULL,
                source TEXT DEFAULT 'captain',
                importance INTEGER DEFAULT 10,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS captain_lore (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lore TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                importance INTEGER DEFAULT 5,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS server_lore (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                lore TEXT NOT NULL,
                importance INTEGER DEFAULT 5,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                nickname TEXT DEFAULT '',
                relationship_type TEXT DEFAULT 'New Crewmate',
                familiarity INTEGER DEFAULT 0,
                opinion TEXT DEFAULT '',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, user_id)
            )
        """)


        await db.execute("""
            CREATE TABLE IF NOT EXISTS tickle_stats (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                tickle_count INTEGER DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS running_jokes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joke TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS relationship_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                event TEXT NOT NULL,
                importance INTEGER DEFAULT 5,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS captain_quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                quote TEXT NOT NULL,
                saved_by INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS captain_journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                entry TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                mood TEXT DEFAULT 'cheerful',
                quiet INTEGER DEFAULT 0,
                event_mode INTEGER DEFAULT 0,
                welcome_enabled INTEGER DEFAULT 0,
                welcome_channel_id INTEGER DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Upgrade older guild_settings tables.

        if not await column_exists(
            db,
            "guild_settings",
            "welcome_enabled"
        ):

            await db.execute("""
                ALTER TABLE guild_settings
                ADD COLUMN welcome_enabled INTEGER DEFAULT 0
            """)

        if not await column_exists(
            db,
            "guild_settings",
            "welcome_channel_id"
        ):

            await db.execute("""
                ALTER TABLE guild_settings
                ADD COLUMN welcome_channel_id INTEGER DEFAULT 0
            """)

        # Social features: birthdays, returning crew, and chronicles.
        await db.execute("""
            CREATE TABLE IF NOT EXISTS member_meta (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT DEFAULT '',
                first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_return_greet_at DATETIME,
                birthday_month INTEGER,
                birthday_day INTEGER,
                birthday_reward_year INTEGER,
                PRIMARY KEY (guild_id, user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS server_chronicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                period_start DATETIME,
                period_end DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS captain_log_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                entry_type TEXT DEFAULT 'event',
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        for column, definition in (
            ("returning_enabled", "INTEGER DEFAULT 1"),
            ("returning_days", "INTEGER DEFAULT 14"),
            ("chronicle_enabled", "INTEGER DEFAULT 0"),
            ("chronicle_channel_id", "INTEGER DEFAULT 0"),
            ("chronicle_last_run", "DATETIME")
        ):
            if not await column_exists(db, "guild_settings", column):
                await db.execute(
                    f"ALTER TABLE guild_settings ADD COLUMN {column} {definition}"
                )

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_member_meta_birthday
            ON member_meta (guild_id, birthday_month, birthday_day)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_log_entries_guild
            ON captain_log_entries (guild_id, id DESC)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_chronicles_guild
            ON server_chronicles (guild_id, id DESC)
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS treasure_hunts (
                guild_id INTEGER PRIMARY KEY,
                active INTEGER DEFAULT 0,
                answer TEXT DEFAULT '',
                clue TEXT DEFAULT '',
                winner_id INTEGER,
                winner_name TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS economy (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                doubloons INTEGER DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                achievement TEXT NOT NULL,
                description TEXT DEFAULT '',
                awarded_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS captain_timeline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                entry TEXT NOT NULL,
                importance INTEGER DEFAULT 5,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_channel
            ON messages (
                guild_id,
                channel_id,
                id DESC
            )
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_time
            ON messages (
                timestamp
            )
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_user
            ON user_memories (
                guild_id,
                user_id,
                confidence DESC
            )
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_relationship_events
            ON relationship_events (
                guild_id,
                user_id,
                importance DESC
            )
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_running_jokes
            ON running_jokes (
                guild_id,
                user_id,
                id DESC
            )
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_server_lore
            ON server_lore (
                guild_id,
                importance DESC
            )
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_timeline
            ON captain_timeline (
                guild_id,
                importance DESC,
                id DESC
            )
        """)

        # -------------------------------------------------
        # Achievement uniqueness
        #
        # Existing databases may contain duplicate legacy
        # achievements, so remove duplicates before creating
        # the unique case-insensitive identity index.
        # -------------------------------------------------

        await db.execute("""
            DELETE FROM achievements
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM achievements
                GROUP BY
                    guild_id,
                    user_id,
                    LOWER(achievement)
            )
        """)

        await db.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                idx_achievements_unique
            ON achievements (
                guild_id,
                user_id,
                LOWER(achievement)
            )
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_achievements
            ON achievements (
                guild_id,
                user_id
            )
        """)

        await db.commit()


async def save_message(
    guild_id,
    channel_id,
    user_id,
    username,
    content
):

    if not content:
        return

    content = content[:4000]

    db = await get_db()

    async with _write_lock:

        await db.execute("""
            INSERT INTO messages (
                guild_id,
                channel_id,
                user_id,
                username,
                content
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            guild_id,
            channel_id,
            user_id,
            username,
            content
        ))

        await db.commit()


async def get_recent_messages(
    guild_id,
    channel_id,
    limit=10
):

    db = await get_db()

    cursor = await db.execute("""
        SELECT username, content
        FROM messages
        WHERE guild_id = ?
        AND channel_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (
        guild_id,
        channel_id,
        limit
    ))

    rows = await cursor.fetchall()

    rows.reverse()

    return rows


async def ensure_user_profile(
    guild_id,
    user_id,
    username
):

    db = await get_db()

    async with _write_lock:

        await db.execute("""
            INSERT INTO user_profiles (
                guild_id,
                user_id,
                username
            )
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id)
            DO UPDATE SET
                username = excluded.username,
                updated_at = CURRENT_TIMESTAMP
        """, (
            guild_id,
            user_id,
            username
        ))

        await db.commit()


async def get_user_profile(
    guild_id,
    user_id
):

    db = await get_db()

    cursor = await db.execute("""
        SELECT username, summary, gender, pronouns
        FROM user_profiles
        WHERE guild_id = ?
        AND user_id = ?
        LIMIT 1
    """, (
        guild_id,
        user_id
    ))

    row = await cursor.fetchone()

    if not row:
        return None

    return {
        "username": row[0],
        "summary": row[1] or "",
        "gender": row[2],
        "pronouns": row[3]
    }


# ---------------------------------------------------------
# Explicit user identity
#
# Identity information may ONLY come from an explicit
# statement by the user. Never infer gender or pronouns
# from names, avatars, writing style, roles, or context.
#
# _IDENTITY_UNSET = leave the existing value unchanged.
# None = explicitly clear the stored value.
# ---------------------------------------------------------

_IDENTITY_UNSET = object()


async def update_user_identity(
    guild_id,
    user_id,
    *,
    gender=_IDENTITY_UNSET,
    pronouns=_IDENTITY_UNSET
):

    if (
        gender is _IDENTITY_UNSET
        and pronouns is _IDENTITY_UNSET
    ):
        return

    db = await get_db()

    updates = []
    values = []

    if gender is not _IDENTITY_UNSET:

        if gender is None:
            clean_gender = None
        else:
            clean_gender = str(
                gender
            ).strip()[:100] or None

        updates.append("gender = ?")
        values.append(clean_gender)

    if pronouns is not _IDENTITY_UNSET:

        if pronouns is None:
            clean_pronouns = None
        else:
            clean_pronouns = str(
                pronouns
            ).strip()[:100] or None

        updates.append("pronouns = ?")
        values.append(clean_pronouns)

    updates.append(
        "updated_at = CURRENT_TIMESTAMP"
    )

    values.extend([
        guild_id,
        user_id
    ])

    async with _write_lock:

        await db.execute(
            f"""
            UPDATE user_profiles
            SET {", ".join(updates)}
            WHERE guild_id = ?
            AND user_id = ?
            """,
            values
        )

        await db.commit()


async def add_user_memory(
    guild_id,
    user_id,
    memory
):

    memory = memory.strip()[:300]

    if not memory:
        return

    key = normalize_memory(
        memory
    )

    db = await get_db()

    cursor = await db.execute("""
        SELECT id, memory
        FROM user_memories
        WHERE guild_id = ?
        AND user_id = ?
        ORDER BY confidence DESC
        LIMIT 50
    """, (
        guild_id,
        user_id
    ))

    rows = await cursor.fetchall()

    existing_id = None

    for row in rows:

        existing_memory = row[1]

        if is_safe_duplicate(
            existing_memory,
            memory,
            threshold=0.90
        ):
            existing_id = row[0]
            break

    async with _write_lock:

        if existing_id is not None:

            await db.execute("""
                UPDATE user_memories
                SET confidence = MIN(
                        confidence + 1,
                        10
                    ),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                existing_id,
            ))

        else:

            await db.execute("""
                INSERT INTO user_memories (
                    guild_id,
                    user_id,
                    memory,
                    confidence
                )
                VALUES (?, ?, ?, 1)
            """, (
                guild_id,
                user_id,
                memory
            ))

        await db.commit()


async def get_user_memories(
    guild_id,
    user_id,
    limit=20
):

    db = await get_db()

    cursor = await db.execute("""
        SELECT memory, confidence
        FROM user_memories
        WHERE guild_id = ?
        AND user_id = ?
        ORDER BY confidence DESC, id DESC
        LIMIT ?
    """, (
        guild_id,
        user_id,
        limit
    ))

    rows = await cursor.fetchall()

    return [
        f"{row[0]} (confidence {row[1]}/10)"
        for row in rows
    ]


async def get_user_memories_context(
    guild_id,
    user_id,
    limit=5,
    min_confidence=1
):

    db = await get_db()

    cursor = await db.execute("""
        SELECT memory
        FROM user_memories
        WHERE guild_id = ?
        AND user_id = ?
        AND confidence >= ?
        ORDER BY confidence DESC, id DESC
        LIMIT ?
    """, (
        guild_id,
        user_id,
        min_confidence,
        limit
    ))

    rows = await cursor.fetchall()

    return [
        row[0]
        for row in rows
    ]


async def delete_user_memories(
    guild_id,
    user_id
):

    db = await get_db()

    async with _write_lock:

        await db.execute("""
            DELETE FROM user_memories
            WHERE guild_id = ?
            AND user_id = ?
        """, (
            guild_id,
            user_id
        ))

        await db.execute("""
            UPDATE user_profiles
            SET summary = ''
            WHERE guild_id = ?
            AND user_id = ?
        """, (
            guild_id,
            user_id
        ))

        await db.commit()


async def add_captain_lore(
    lore,
    category="personal",
    importance=5
):
    # -----------------------------------------------------
    # Living Ship identity guard
    #
    # IMPORTANT:
    # Check the ORIGINAL text before normalize_memory().
    # Normalization removes words such as "our", which can
    # otherwise hide statements like:
    #
    #   "Our ship is The Old Salt."
    #
    # Current Living Ship identity belongs exclusively to
    # live Ship World state.
    # -----------------------------------------------------

    raw_lore = str(
        lore or ""
    ).strip()

    if not raw_lore:
        return False

    lore_lower = raw_lore.lower()

    current_ship_claims = (
        "current ship",
        "current vessel",
        "living ship",
        "our ship is",
        "our vessel is",
        "the crew's ship is",
        "the crews ship is",
        "captain's current ship",
        "captains current ship",
        "captain cutlass's current ship",
        "captain cutlass current ship",
        "our current ship",
        "our current vessel",
    )

    if any(
        phrase in lore_lower
        for phrase in current_ship_claims
    ):
        return False

    # Only normalize AFTER authority checks.
    lore = normalize_memory(
        raw_lore
    )

    if not lore:
        return False

    db = await get_db()

    async with _write_lock:

        rows = await (
            await db.execute("""
                SELECT id, lore
                FROM captain_lore
                ORDER BY importance DESC, id DESC
                LIMIT 250
            """)
        ).fetchall()

        def normalize_compare(value):
            value = value.lower().strip()

            number_words = {
                "zero": "0",
                "one": "1",
                "two": "2",
                "three": "3",
                "four": "4",
                "five": "5",
                "six": "6",
                "seven": "7",
                "eight": "8",
                "nine": "9",
                "ten": "10",
                "eleven": "11",
                "twelve": "12",
                "thirteen": "13",
                "fourteen": "14",
                "fifteen": "15",
                "sixteen": "16",
                "seventeen": "17",
                "eighteen": "18",
                "nineteen": "19",
                "twenty": "20",
                "thirty": "30",
                "forty": "40",
                "fifty": "50",
                "sixty": "60",
                "seventy": "70",
                "eighty": "80",
                "ninety": "90"
            }

            # Normalize hyphenated number words first.
            value = value.replace("-", " ")

            words = value.split()
            converted = []
            i = 0

            while i < len(words):
                word = words[i]

                if (
                    word in number_words
                    and i + 1 < len(words)
                    and words[i + 1] in number_words
                ):
                    first = int(number_words[word])
                    second = int(number_words[words[i + 1]])

                    if first >= 20 and second < 10:
                        converted.append(
                            str(first + second)
                        )
                        i += 2
                        continue

                converted.append(
                    number_words.get(
                        word,
                        word
                    )
                )
                i += 1

            value = " ".join(converted)

            value = re.sub(
                r"[^a-z0-9\s]",
                " ",
                value
            )

            # Reduce a few common wording differences.
            replacements = {
                "captain cutlass": "captain",
                "once captained": "captained",
                "was once captained by captain": "captained by captain",
                "was famous for": "known for",
                "rough seas": "rough waters",
                "swift maneuvers": "swift",
                "years of age": "years old"
            }

            for old_phrase, new_phrase in replacements.items():
                value = value.replace(
                    old_phrase,
                    new_phrase
                )

            value = re.sub(
                r"\s+",
                " ",
                value
            )

            return value.strip()

        incoming = normalize_compare(
            lore
        )

        incoming_words = set(
            incoming.split()
        )

        for row in rows:

            existing = normalize_compare(
                row[1]
            )

            if not existing:
                continue

            # Exact normalized duplicate.
            if incoming == existing:
                return False

            existing_words = set(
                existing.split()
            )

            if not incoming_words or not existing_words:
                continue

            overlap = len(
                incoming_words
                & existing_words
            )

            union = len(
                incoming_words
                | existing_words
            )

            similarity = (
                overlap / union
                if union
                else 0
            )

            # Catch rewritten versions of the same lore.
            if similarity >= 0.65:
                return False

            # Catch cases where one version is largely contained
            # inside another but has extra decorative wording.
            shorter = min(
                len(incoming_words),
                len(existing_words)
            )

            if shorter >= 5:

                containment = (
                    overlap / shorter
                )

                if containment >= 0.78:
                    return False

        await db.execute("""
            INSERT INTO captain_lore (
                lore,
                category,
                importance
            )
            VALUES (?, ?, ?)
        """, (
            lore,
            category,
            importance
        ))

        await db.commit()

    return True

async def get_captain_lore(
    limit=5
):

    db = await get_db()

    cursor = await db.execute("""
        SELECT lore, category, importance
        FROM captain_lore
        ORDER BY importance DESC, id DESC
        LIMIT ?
    """, (
        limit,
    ))

    rows = await cursor.fetchall()

    return [
        {
            "lore": row[0],
            "category": row[1],
            "importance": row[2]
        }
        for row in rows
    ]


async def add_server_lore(
    guild_id,
    lore,
    importance=5
):

    lore = lore.strip()[:500]

    if not lore:
        return False

    db = await get_db()

    cursor = await db.execute("""
        SELECT id
        FROM server_lore
        WHERE guild_id = ?
        AND LOWER(lore) = LOWER(?)
        LIMIT 1
    """, (
        guild_id,
        lore
    ))

    if await cursor.fetchone():
        return False

    async with _write_lock:

        await db.execute("""
            INSERT INTO server_lore (
                guild_id,
                lore,
                importance
            )
            VALUES (?, ?, ?)
        """, (
            guild_id,
            lore,
            importance
        ))

        await db.commit()

    return True


async def get_server_lore(
    guild_id,
    limit=5
):

    db = await get_db()

    cursor = await db.execute("""
        SELECT lore
        FROM server_lore
        WHERE guild_id = ?
        ORDER BY importance DESC, id DESC
        LIMIT ?
    """, (
        guild_id,
        limit
    ))

    rows = await cursor.fetchall()

    return [
        row[0]
        for row in rows
    ]


async def ensure_relationship(
    guild_id,
    user_id,
    username
):

    db = await get_db()

    async with _write_lock:

        await db.execute("""
            INSERT INTO relationships (
                guild_id,
                user_id,
                username
            )
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id)
            DO UPDATE SET
                username = excluded.username
        """, (
            guild_id,
            user_id,
            username
        ))

        await db.commit()


async def get_relationship(
    guild_id,
    user_id
):

    db = await get_db()

    cursor = await db.execute("""
        SELECT
            username,
            nickname,
            relationship_type,
            familiarity,
            opinion
        FROM relationships
        WHERE guild_id = ?
        AND user_id = ?
        LIMIT 1
    """, (
        guild_id,
        user_id
    ))

    row = await cursor.fetchone()

    if not row:
        return None

    return {
        "username": row[0],
        "nickname": row[1] or "",
        "relationship_type": row[2] or "New Crewmate",
        "familiarity": row[3] or 0,
        "opinion": row[4] or ""
    }


async def increase_familiarity(
    guild_id,
    user_id,
    amount=1
):

    relationship = await get_relationship(
        guild_id,
        user_id
    )

    old_value = (
        relationship["familiarity"]
        if relationship
        else 0
    )

    new_value = min(
        old_value + amount,
        100
    )

    db = await get_db()

    async with _write_lock:

        await db.execute("""
            UPDATE relationships
            SET familiarity = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
            AND user_id = ?
        """, (
            new_value,
            guild_id,
            user_id
        ))

        await db.commit()

    return old_value, new_value


async def nickname_is_taken(
    guild_id,
    nickname,
    exclude_user_id=None
):
    """
    Return True when another member in the same guild
    already owns this relationship nickname.

    Comparison is case-insensitive and ignores surrounding
    whitespace.
    """

    nickname = str(
        nickname or ""
    ).strip()

    if not nickname:
        return False

    db = await get_db()

    if exclude_user_id is None:

        cursor = await db.execute("""
            SELECT 1
            FROM relationships
            WHERE guild_id = ?
              AND TRIM(LOWER(COALESCE(nickname, '')))
                  = TRIM(LOWER(?))
            LIMIT 1
        """, (
            guild_id,
            nickname,
        ))

    else:

        cursor = await db.execute("""
            SELECT 1
            FROM relationships
            WHERE guild_id = ?
              AND user_id != ?
              AND TRIM(LOWER(COALESCE(nickname, '')))
                  = TRIM(LOWER(?))
            LIMIT 1
        """, (
            guild_id,
            exclude_user_id,
            nickname,
        ))

    row = await cursor.fetchone()

    return row is not None



async def update_relationship(
    guild_id,
    user_id,
    relationship_type=None,
    opinion=None,
    nickname=None
):

    db = await get_db()

    async with _write_lock:

        if relationship_type is not None:

            await db.execute("""
                UPDATE relationships
                SET relationship_type = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
                AND user_id = ?
            """, (
                relationship_type[:100],
                guild_id,
                user_id
            ))

        if opinion is not None:

            await db.execute("""
                UPDATE relationships
                SET opinion = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
                AND user_id = ?
            """, (
                opinion[:300],
                guild_id,
                user_id
            ))

        if nickname is not None:

            await db.execute("""
                UPDATE relationships
                SET nickname = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
                AND user_id = ?
            """, (
                nickname[:100],
                guild_id,
                user_id
            ))

        await db.commit()


async def get_top_crew(
    guild_id,
    limit=10
):

    db = await get_db()

    cursor = await db.execute("""
        SELECT
            username,
            nickname,
            relationship_type,
            familiarity
        FROM relationships
        WHERE guild_id = ?
        ORDER BY familiarity DESC
        LIMIT ?
    """, (
        guild_id,
        limit
    ))

    return await cursor.fetchall()


async def add_running_joke(
    guild_id,
    user_id,
    joke
):

    joke = joke.strip()[:400]

    if not joke:
        return False

    db = await get_db()

    cursor = await db.execute("""
        SELECT id, joke
        FROM running_jokes
        WHERE guild_id = ?
        AND user_id = ?
        ORDER BY id DESC
        LIMIT 30
    """, (
        guild_id,
        user_id
    ))

    rows = await cursor.fetchall()

    for row in rows:

        existing_joke = row[1]

        if is_safe_duplicate(
            existing_joke,
            joke,
            threshold=0.90
        ):
            return False

    async with _write_lock:

        await db.execute("""
            INSERT INTO running_jokes (
                guild_id,
                user_id,
                joke
            )
            VALUES (?, ?, ?)
        """, (
            guild_id,
            user_id,
            joke
        ))

        await db.execute("""
            DELETE FROM running_jokes
            WHERE guild_id = ?
            AND user_id = ?
            AND id NOT IN (
                SELECT id
                FROM running_jokes
                WHERE guild_id = ?
                AND user_id = ?
                ORDER BY id DESC
                LIMIT 20
            )
        """, (
            guild_id,
            user_id,
            guild_id,
            user_id
        ))

        await db.commit()

    return True


async def get_running_jokes(
    guild_id,
    user_id,
    limit=3
):

    db = await get_db()

    cursor = await db.execute("""
        SELECT joke
        FROM running_jokes
        WHERE guild_id = ?
        AND user_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (
        guild_id,
        user_id,
        limit
    ))

    rows = await cursor.fetchall()

    return [
        row[0]
        for row in rows
    ]


async def add_relationship_event(
    guild_id,
    user_id,
    event,
    importance=5
):

    event = event.strip()[:500]

    if not event:
        return

    db = await get_db()

    cursor = await db.execute("""
        SELECT id, event
        FROM relationship_events
        WHERE guild_id = ?
        AND user_id = ?
        ORDER BY id DESC
        LIMIT 40
    """, (
        guild_id,
        user_id
    ))

    rows = await cursor.fetchall()

    for row in rows:

        existing_event = row[1]

        if is_safe_duplicate(
            existing_event,
            event,
            threshold=0.90
        ):
            return False

    async with _write_lock:

        await db.execute("""
            INSERT INTO relationship_events (
                guild_id,
                user_id,
                event,
                importance
            )
            VALUES (?, ?, ?, ?)
        """, (
            guild_id,
            user_id,
            event,
            importance
        ))

        await db.execute("""
            DELETE FROM relationship_events
            WHERE guild_id = ?
            AND user_id = ?
            AND id NOT IN (
                SELECT id
                FROM relationship_events
                WHERE guild_id = ?
                AND user_id = ?
                ORDER BY importance DESC, id DESC
                LIMIT 30
            )
        """, (
            guild_id,
            user_id,
            guild_id,
            user_id
        ))

        await db.commit()

    return True


async def get_relationship_events(
    guild_id,
    user_id,
    limit=3
):

    db = await get_db()

    cursor = await db.execute("""
        SELECT event, importance
        FROM relationship_events
        WHERE guild_id = ?
        AND user_id = ?
        ORDER BY importance DESC, id DESC
        LIMIT ?
    """, (
        guild_id,
        user_id,
        limit
    ))

    rows = await cursor.fetchall()

    return [
        {
            "event": row[0],
            "importance": row[1]
        }
        for row in rows
    ]


async def add_quote(
    guild_id,
    quote,
    saved_by
):

    quote = quote.strip()[:1800]

    if not quote:
        return

    db = await get_db()

    async with _write_lock:

        await db.execute("""
            INSERT INTO captain_quotes (
                guild_id,
                quote,
                saved_by
            )
            VALUES (?, ?, ?)
        """, (
            guild_id,
            quote,
            saved_by
        ))

        await db.commit()


async def get_random_quote(
    guild_id
):

    db = await get_db()

    cursor = await db.execute("""
        SELECT quote
        FROM captain_quotes
        WHERE guild_id = ?
        ORDER BY RANDOM()
        LIMIT 1
    """, (
        guild_id,
    ))

    row = await cursor.fetchone()

    return (
        row[0]
        if row
        else None
    )


async def add_journal_entry(
    guild_id,
    entry
):

    entry = entry.strip()[:1800]

    if not entry:
        return

    db = await get_db()

    async with _write_lock:

        await db.execute("""
            INSERT INTO captain_journal (
                guild_id,
                entry
            )
            VALUES (?, ?)
        """, (
            guild_id,
            entry
        ))

        await db.commit()


async def get_journal(
    guild_id,
    limit=5
):

    db = await get_db()

    cursor = await db.execute("""
        SELECT entry, created_at
        FROM captain_journal
        WHERE guild_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (
        guild_id,
        limit
    ))

    return await cursor.fetchall()


async def ensure_guild_settings(
    guild_id
):

    db = await get_db()

    async with _write_lock:

        await db.execute("""
            INSERT OR IGNORE INTO guild_settings (
                guild_id
            )
            VALUES (?)
        """, (
            guild_id,
        ))

        await db.commit()


async def get_guild_settings(
    guild_id
):

    await ensure_guild_settings(
        guild_id
    )

    db = await get_db()

    cursor = await db.execute("""
        SELECT
            mood,
            quiet,
            event_mode,
            welcome_enabled,
            welcome_channel_id,
            returning_enabled,
            returning_days,
            chronicle_enabled,
            chronicle_channel_id,
            chronicle_last_run
        FROM guild_settings
        WHERE guild_id = ?
    """, (
        guild_id,
    ))

    row = await cursor.fetchone()

    return {
        "mood": (
            row[0]
            if row
            else "cheerful"
        ),
        "quiet": (
            bool(row[1])
            if row
            else False
        ),
        "event_mode": (
            bool(row[2])
            if row
            else False
        ),
        "welcome_enabled": (
            bool(row[3])
            if row
            else False
        ),
        "welcome_channel_id": (int(row[4] or 0) if row else 0),
        "returning_enabled": (bool(row[5]) if row else True),
        "returning_days": (int(row[6] or 14) if row else 14),
        "chronicle_enabled": (bool(row[7]) if row else False),
        "chronicle_channel_id": (int(row[8] or 0) if row else 0),
        "chronicle_last_run": (row[9] if row else None)
    }


async def set_guild_setting(
    guild_id,
    field,
    value
):

    allowed = {
        "mood",
        "quiet",
        "event_mode",
        "welcome_enabled",
        "welcome_channel_id",
        "returning_enabled",
        "returning_days",
        "chronicle_enabled",
        "chronicle_channel_id",
        "chronicle_last_run"
    }

    if field not in allowed:
        return

    await ensure_guild_settings(
        guild_id
    )

    db = await get_db()

    async with _write_lock:

        await db.execute(
            f"""
            UPDATE guild_settings
            SET {field} = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
            """,
            (
                value,
                guild_id
            )
        )

        await db.commit()


async def ensure_economy(
    guild_id,
    user_id
):

    db = await get_db()

    async with _write_lock:

        await db.execute("""
            INSERT OR IGNORE INTO economy (
                guild_id,
                user_id,
                doubloons
            )
            VALUES (?, ?, 0)
        """, (
            guild_id,
            user_id
        ))

        await db.commit()


async def add_doubloons(
    guild_id,
    user_id,
    amount
):

    await ensure_economy(
        guild_id,
        user_id
    )

    db = await get_db()

    async with _write_lock:

        await db.execute("""
            UPDATE economy
            SET doubloons = MAX(
                    doubloons + ?,
                    0
                ),
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
            AND user_id = ?
        """, (
            int(amount),
            guild_id,
            user_id
        ))

        await db.commit()


async def get_doubloons(
    guild_id,
    user_id
):

    await ensure_economy(
        guild_id,
        user_id
    )

    db = await get_db()

    cursor = await db.execute("""
        SELECT doubloons
        FROM economy
        WHERE guild_id = ?
        AND user_id = ?
    """, (
        guild_id,
        user_id
    ))

    row = await cursor.fetchone()

    return (
        row[0]
        if row
        else 0
    )


async def get_doubloon_leaderboard(
    guild_id,
    limit=10
):

    db = await get_db()

    cursor = await db.execute("""
        SELECT
            relationships.username,
            relationships.nickname,
            economy.doubloons
        FROM economy
        LEFT JOIN relationships
            ON relationships.guild_id = economy.guild_id
            AND relationships.user_id = economy.user_id
        WHERE economy.guild_id = ?
        ORDER BY economy.doubloons DESC
        LIMIT ?
    """, (
        guild_id,
        limit
    ))

    return await cursor.fetchall()


async def award_achievement(
    guild_id,
    user_id,
    achievement,
    description=""
):

    achievement = str(achievement).strip()[:100]
    description = str(description).strip()[:500]

    if not achievement:
        return False

    db = await get_db()

    async with _write_lock:

        cursor = await db.execute(
            """
            INSERT OR IGNORE INTO achievements (
                guild_id,
                user_id,
                achievement,
                description
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                guild_id,
                user_id,
                achievement,
                description,
            )
        )

        await db.commit()

        return cursor.rowcount == 1


async def get_achievements(
    guild_id,
    user_id,
    limit=None
):

    db = await get_db()

    if limit is None:

        cursor = await db.execute("""
            SELECT achievement, description
            FROM achievements
            WHERE guild_id = ?
            AND user_id = ?
            ORDER BY id ASC
        """, (
            guild_id,
            user_id
        ))

    else:

        cursor = await db.execute("""
            SELECT achievement, description
            FROM achievements
            WHERE guild_id = ?
            AND user_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (
            guild_id,
            user_id,
            limit
        ))

    return await cursor.fetchall()


async def add_timeline_entry(
    guild_id,
    entry,
    importance=5
):

    entry = entry.strip()[:1000]

    if not entry:
        return False

    db = await get_db()

    cursor = await db.execute("""
        SELECT id
        FROM captain_timeline
        WHERE guild_id = ?
        AND LOWER(entry) = LOWER(?)
        LIMIT 1
    """, (
        guild_id,
        entry
    ))

    if await cursor.fetchone():
        return False

    async with _write_lock:

        await db.execute("""
            INSERT INTO captain_timeline (
                guild_id,
                entry,
                importance
            )
            VALUES (?, ?, ?)
        """, (
            guild_id,
            entry,
            importance
        ))

        await db.commit()

    return True


async def get_timeline(
    guild_id,
    limit=10
):

    db = await get_db()

    cursor = await db.execute("""
        SELECT entry, created_at
        FROM captain_timeline
        WHERE guild_id = ?
        ORDER BY importance DESC, id DESC
        LIMIT ?
    """, (
        guild_id,
        limit
    ))

    return await cursor.fetchall()


async def start_treasure_hunt(
    guild_id,
    answer,
    clue
):

    db = await get_db()

    async with _write_lock:

        await db.execute("""
            INSERT INTO treasure_hunts (
                guild_id,
                active,
                answer,
                clue,
                winner_id,
                winner_name
            )
            VALUES (?, 1, ?, ?, NULL, NULL)
            ON CONFLICT(guild_id)
            DO UPDATE SET
                active = 1,
                answer = excluded.answer,
                clue = excluded.clue,
                winner_id = NULL,
                winner_name = NULL,
                updated_at = CURRENT_TIMESTAMP
        """, (
            guild_id,
            answer.lower().strip()[:200],
            clue.strip()[:1000]
        ))

        await db.commit()


async def get_treasure_hunt(
    guild_id
):

    db = await get_db()

    cursor = await db.execute("""
        SELECT
            active,
            answer,
            clue,
            winner_id,
            winner_name
        FROM treasure_hunts
        WHERE guild_id = ?
    """, (
        guild_id,
    ))

    row = await cursor.fetchone()

    if not row:
        return None

    return {
        "active": bool(row[0]),
        "answer": row[1],
        "clue": row[2],
        "winner_id": row[3],
        "winner_name": row[4]
    }


async def finish_treasure_hunt(
    guild_id,
    winner_id,
    winner_name
):

    db = await get_db()

    async with _write_lock:

        await db.execute("""
            UPDATE treasure_hunts
            SET active = 0,
                winner_id = ?,
                winner_name = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
        """, (
            winner_id,
            winner_name,
            guild_id
        ))

        await db.commit()


async def get_stats(
    guild_id
):

    db = await get_db()

    result = {}

    queries = {
        "members": """
            SELECT COUNT(*)
            FROM relationships
            WHERE guild_id = ?
        """,
        "memories": """
            SELECT COUNT(*)
            FROM user_memories
            WHERE guild_id = ?
        """,
        "jokes": """
            SELECT COUNT(*)
            FROM running_jokes
            WHERE guild_id = ?
        """,
        "events": """
            SELECT COUNT(*)
            FROM relationship_events
            WHERE guild_id = ?
        """,
        "server_lore": """
            SELECT COUNT(*)
            FROM server_lore
            WHERE guild_id = ?
        """,
        "quotes": """
            SELECT COUNT(*)
            FROM captain_quotes
            WHERE guild_id = ?
        """,
        "achievements": """
            SELECT COUNT(*)
            FROM achievements
            WHERE guild_id = ?
        """,
        "timeline": """
            SELECT COUNT(*)
            FROM captain_timeline
            WHERE guild_id = ?
        """,
        "doubloons": """
            SELECT COALESCE(
                SUM(doubloons),
                0
            )
            FROM economy
            WHERE guild_id = ?
        """
    }

    for key, query in queries.items():

        cursor = await db.execute(
            query,
            (
                guild_id,
            )
        )

        row = await cursor.fetchone()

        result[key] = (
            row[0]
            if row
            else 0
        )

    cursor = await db.execute("""
        SELECT COUNT(*)
        FROM captain_lore
    """)

    row = await cursor.fetchone()

    result["captain_lore"] = (
        row[0]
        if row
        else 0
    )

    return result


async def run_maintenance(
    message_retention_days=30,
    weak_memory_days=120
):

    db = await get_db()

    async with _write_lock:

        await db.execute("""
            DELETE FROM messages
            WHERE datetime(timestamp) <
                datetime(
                    'now',
                    ?
                )
        """, (
            f"-{int(message_retention_days)} days",
        ))

        await db.execute("""
            UPDATE user_memories
            SET confidence = MAX(
                    confidence - 1,
                    1
                )
            WHERE confidence > 1
            AND updated_at IS NOT NULL
            AND datetime(updated_at) <
                datetime('now', '-30 days')
        """)

        await db.execute("""
            DELETE FROM user_memories
            WHERE confidence <= 1
            AND updated_at IS NOT NULL
            AND datetime(updated_at) <
                datetime(
                    'now',
                    ?
                )
        """, (
            f"-{int(weak_memory_days)} days",
        ))

        await db.execute("""
            DELETE FROM messages
            WHERE id NOT IN (
                SELECT id
                FROM messages
                ORDER BY id DESC
                LIMIT 25000
            )
        """)

        await db.execute(
            "PRAGMA optimize"
        )

        await db.commit()

async def ensure_member_meta(guild_id, user_id, username):
    db = await get_db()
    async with _write_lock:
        await db.execute("""
            INSERT INTO member_meta (guild_id, user_id, username)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET username = excluded.username
        """, (guild_id, user_id, username))
        await db.commit()


async def get_member_meta(guild_id, user_id):
    db = await get_db()
    cursor = await db.execute("""
        SELECT username, first_seen, last_seen, last_return_greet_at,
               birthday_month, birthday_day, birthday_reward_year
        FROM member_meta WHERE guild_id = ? AND user_id = ? LIMIT 1
    """, (guild_id, user_id))
    row = await cursor.fetchone()
    if not row:
        return None
    return {
        "username": row[0], "first_seen": row[1], "last_seen": row[2],
        "last_return_greet_at": row[3], "birthday_month": row[4],
        "birthday_day": row[5], "birthday_reward_year": row[6]
    }


async def touch_member_seen(guild_id, user_id, username):
    await ensure_member_meta(guild_id, user_id, username)
    db = await get_db()
    async with _write_lock:
        await db.execute("""
            UPDATE member_meta SET username = ?, last_seen = CURRENT_TIMESTAMP
            WHERE guild_id = ? AND user_id = ?
        """, (username, guild_id, user_id))
        await db.commit()


async def mark_return_greeted(guild_id, user_id):
    db = await get_db()
    async with _write_lock:
        await db.execute("""
            UPDATE member_meta SET last_return_greet_at = CURRENT_TIMESTAMP
            WHERE guild_id = ? AND user_id = ?
        """, (guild_id, user_id))
        await db.commit()


async def set_birthday(guild_id, user_id, username, month, day):
    await ensure_member_meta(guild_id, user_id, username)
    db = await get_db()
    async with _write_lock:
        await db.execute("""
            UPDATE member_meta SET birthday_month = ?, birthday_day = ?
            WHERE guild_id = ? AND user_id = ?
        """, (month, day, guild_id, user_id))
        await db.commit()


async def clear_birthday(guild_id, user_id):
    db = await get_db()
    async with _write_lock:
        await db.execute("""
            UPDATE member_meta SET birthday_month = NULL, birthday_day = NULL
            WHERE guild_id = ? AND user_id = ?
        """, (guild_id, user_id))
        await db.commit()


async def get_birthdays(guild_id):
    db = await get_db()
    cursor = await db.execute("""
        SELECT user_id, username, birthday_month, birthday_day
        FROM member_meta
        WHERE guild_id = ? AND birthday_month IS NOT NULL AND birthday_day IS NOT NULL
        ORDER BY birthday_month, birthday_day, username
    """, (guild_id,))
    return await cursor.fetchall()


async def get_todays_birthdays(guild_id, month, day):
    db = await get_db()
    cursor = await db.execute("""
        SELECT user_id, username, birthday_reward_year
        FROM member_meta
        WHERE guild_id = ? AND birthday_month = ? AND birthday_day = ?
    """, (guild_id, month, day))
    return await cursor.fetchall()


async def mark_birthday_rewarded(guild_id, user_id, year):
    db = await get_db()
    async with _write_lock:
        await db.execute("""
            UPDATE member_meta SET birthday_reward_year = ?
            WHERE guild_id = ? AND user_id = ?
        """, (year, guild_id, user_id))
        await db.commit()


async def add_log_entry(guild_id, content, entry_type="event"):
    content = content.strip()[:1800]
    if not content:
        return
    db = await get_db()
    async with _write_lock:
        await db.execute("""
            INSERT INTO captain_log_entries (guild_id, entry_type, content)
            VALUES (?, ?, ?)
        """, (guild_id, entry_type[:50], content))
        await db.commit()


async def get_log_entries(guild_id, limit=25, since=None):
    db = await get_db()
    if since:
        cursor = await db.execute("""
            SELECT entry_type, content, created_at FROM captain_log_entries
            WHERE guild_id = ? AND datetime(created_at) >= datetime(?)
            ORDER BY id DESC LIMIT ?
        """, (guild_id, since, limit))
    else:
        cursor = await db.execute("""
            SELECT entry_type, content, created_at FROM captain_log_entries
            WHERE guild_id = ? ORDER BY id DESC LIMIT ?
        """, (guild_id, limit))
    return await cursor.fetchall()


async def save_chronicle(guild_id, content, period_start=None, period_end=None):
    db = await get_db()
    async with _write_lock:
        await db.execute("""
            INSERT INTO server_chronicles (guild_id, content, period_start, period_end)
            VALUES (?, ?, ?, ?)
        """, (guild_id, content[:4000], period_start, period_end))
        await db.execute("""
            UPDATE guild_settings SET chronicle_last_run = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
        """, (guild_id,))
        await db.commit()


async def get_latest_chronicle(guild_id):
    db = await get_db()
    cursor = await db.execute("""
        SELECT content, created_at FROM server_chronicles
        WHERE guild_id = ? ORDER BY id DESC LIMIT 1
    """, (guild_id,))
    return await cursor.fetchone()


# =========================================================
# CAPTAIN CANON
# =========================================================

CANON_KEYS = {
    "age",
    "favorite_ship",
    "birthplace",
    "home_port",
    "favorite_drink",
    "favorite_food",
    "favorite_shanty",
    "greatest_rival",
    "parrot",
    "former_ship",
}


async def set_captain_canon(
    canon_key,
    canon_value,
    source="captain",
    importance=10,
    overwrite=False
):
    canon_key = str(canon_key).strip().lower()
    canon_value = str(canon_value).strip()

    if not canon_key or not canon_value:
        return False

    if canon_key not in CANON_KEYS:
        return False

    db = await get_db()

    async with _write_lock:

        existing = await (
            await db.execute("""
                SELECT canon_value
                FROM captain_canon
                WHERE canon_key = ?
            """, (
                canon_key,
            ))
        ).fetchone()

        if existing and not overwrite:
            return False

        await db.execute("""
            INSERT INTO captain_canon (
                canon_key,
                canon_value,
                source,
                importance,
                updated_at
            )
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)

            ON CONFLICT(canon_key)
            DO UPDATE SET
                canon_value = excluded.canon_value,
                source = excluded.source,
                importance = excluded.importance,
                updated_at = CURRENT_TIMESTAMP
        """, (
            canon_key,
            canon_value,
            source,
            importance
        ))

        await db.commit()

    return True


async def get_captain_canon(
    canon_key
):
    canon_key = str(
        canon_key
    ).strip().lower()

    db = await get_db()

    row = await (
        await db.execute("""
            SELECT canon_key,
                   canon_value,
                   source,
                   importance
            FROM captain_canon
            WHERE canon_key = ?
        """, (
            canon_key,
        ))
    ).fetchone()

    if not row:
        return None

    return {
        "key": row[0],
        "value": row[1],
        "source": row[2],
        "importance": row[3]
    }


async def get_all_captain_canon():
    db = await get_db()

    rows = await (
        await db.execute("""
            SELECT canon_key,
                   canon_value,
                   source,
                   importance
            FROM captain_canon
            ORDER BY importance DESC,
                     canon_key
        """)
    ).fetchall()

    return [
        {
            "key": row[0],
            "value": row[1],
            "source": row[2],
            "importance": row[3]
        }
        for row in rows
    ]


async def format_captain_canon():
    rows = await get_all_captain_canon()

    if not rows:
        return "No core Captain canon has been established yet."

    lines = [
        "**Captain Cutlass — Core Canon**"
    ]

    labels = {
        "age": "Age",
        "favorite_ship": "Favorite Ship",
        "birthplace": "Birthplace",
        "home_port": "Home Port",
        "favorite_drink": "Favorite Drink",
        "favorite_food": "Favorite Food",
        "favorite_shanty": "Favorite Shanty",
        "greatest_rival": "Greatest Rival",
        "parrot": "Parrot",
        "former_ship": "Former Ship",
    }

    for row in rows:
        lines.append(
            labels.get(
                row["key"],
                row["key"].replace("_", " ").title()
            )
            + ": **"
            + row["value"]
            + "**"
        )

    return "\n".join(lines)


# ============================================================
# Captain Cutlass tickle statistics
# ============================================================

async def get_tickle_count(
    guild_id,
    user_id
):
    """
    Return the member's persistent lifetime Captain tickle count.
    """

    db = await get_db()

    cursor = await db.execute(
        """
        SELECT tickle_count
        FROM tickle_stats
        WHERE guild_id = ?
          AND user_id = ?
        """,
        (
            int(guild_id),
            int(user_id)
        )
    )

    row = await cursor.fetchone()

    if not row:
        return 0

    return int(row[0] or 0)


async def increment_tickle_count(
    guild_id,
    user_id
):
    """
    Atomically increment and return a member's lifetime tickle count.

    The existing global database write lock prevents simultaneous
    tickles from losing or duplicating counter updates.
    """

    db = await get_db()

    guild_id = int(guild_id)
    user_id = int(user_id)

    async with _write_lock:

        await db.execute(
            """
            INSERT OR IGNORE INTO tickle_stats (
                guild_id,
                user_id,
                tickle_count
            )
            VALUES (?, ?, 0)
            """,
            (
                guild_id,
                user_id
            )
        )

        await db.execute(
            """
            UPDATE tickle_stats
            SET tickle_count = tickle_count + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
              AND user_id = ?
            """,
            (
                guild_id,
                user_id
            )
        )

        cursor = await db.execute(
            """
            SELECT tickle_count
            FROM tickle_stats
            WHERE guild_id = ?
              AND user_id = ?
            """,
            (
                guild_id,
                user_id
            )
        )

        row = await cursor.fetchone()

        await db.commit()

    return int(row[0] or 0)
