import os
import random

import aiosqlite


DB_PATH = os.getenv(
    "DATABASE_PATH",
    "/app/data/captain.db"
)


DEFAULT_PARROT_NAME = "Barnacle"

PARROT_MOODS = (
    "Cheerful",
    "Grumpy",
    "Hungry",
    "Mischievous",
    "Sleepy",
    "Suspicious",
    "Excited",
    "Jealous"
)


async def _db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def initialize_parrot():
    db = await _db()

    try:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS parrots (
            guild_id INTEGER PRIMARY KEY,
            name TEXT DEFAULT 'Barnacle',
            enabled INTEGER DEFAULT 1,
            mood TEXT DEFAULT 'Mischievous',
            personality TEXT DEFAULT 'Cheeky, clever, chaotic, nosy, and fond of embarrassing Captain Cutlass.',
            participation_chance INTEGER DEFAULT 5,
            interactions INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS parrot_captain_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            event_type TEXT DEFAULT 'banter',
            captain_line TEXT DEFAULT '',
            parrot_line TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            importance INTEGER DEFAULT 5,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_parrot_captain_events_guild
        ON parrot_captain_events(guild_id, id DESC);

        CREATE TABLE IF NOT EXISTS parrot_relationships (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT DEFAULT '',
            familiarity INTEGER DEFAULT 0,
            opinion TEXT DEFAULT '',
            nickname TEXT DEFAULT '',
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (guild_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS parrot_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            memory TEXT NOT NULL,
            confidence INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS parrot_running_jokes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            joke TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_parrot_memories_user
        ON parrot_memories(guild_id, user_id);

        CREATE INDEX IF NOT EXISTS idx_parrot_jokes_user
        ON parrot_running_jokes(guild_id, user_id);
        """)

        await db.execute(
            """
            UPDATE parrots
            SET name = 'Barnacle'
            WHERE name != 'Barnacle'
            """
        )

        await db.commit()

    finally:
        await db.close()


async def ensure_parrot(guild_id):
    db = await _db()

    try:
        await db.execute(
            """
            INSERT OR IGNORE INTO parrots (guild_id)
            VALUES (?)
            """,
            (guild_id,)
        )

        await db.commit()

    finally:
        await db.close()


async def get_parrot(guild_id):
    await ensure_parrot(guild_id)

    db = await _db()

    try:
        row = await (
            await db.execute(
                """
                SELECT *
                FROM parrots
                WHERE guild_id = ?
                """,
                (guild_id,)
            )
        ).fetchone()

        parrot = dict(row)

        # Barnacle is permanent canon.
        parrot["name"] = "Barnacle"

        return parrot

    finally:
        await db.close()



async def set_parrot_enabled(guild_id, enabled):
    await ensure_parrot(guild_id)

    db = await _db()

    try:
        await db.execute(
            """
            UPDATE parrots
            SET enabled = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
            """,
            (
                1 if enabled else 0,
                guild_id
            )
        )

        await db.commit()

    finally:
        await db.close()


async def set_parrot_chance(guild_id, chance):
    await ensure_parrot(guild_id)

    chance = int(chance)

    if chance < 0 or chance > 100:
        raise ValueError(
            "Participation chance must be between 0 and 100."
        )

    db = await _db()

    try:
        await db.execute(
            """
            UPDATE parrots
            SET participation_chance = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
            """,
            (
                chance,
                guild_id
            )
        )

        await db.commit()

    finally:
        await db.close()

    return chance


async def set_parrot_mood(guild_id, mood):
    await ensure_parrot(guild_id)

    matches = {
        value.lower(): value
        for value in PARROT_MOODS
    }

    selected = matches.get(
        str(mood).strip().lower()
    )

    if selected is None:
        raise ValueError(
            "Unknown parrot mood."
        )

    db = await _db()

    try:
        await db.execute(
            """
            UPDATE parrots
            SET mood = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
            """,
            (
                selected,
                guild_id
            )
        )

        await db.commit()

    finally:
        await db.close()

    return selected


async def randomize_parrot_mood(guild_id):
    mood = random.choice(
        PARROT_MOODS
    )

    await set_parrot_mood(
        guild_id,
        mood
    )

    return mood


async def ensure_parrot_relationship(
    guild_id,
    user_id,
    username
):
    db = await _db()

    try:
        await db.execute(
            """
            INSERT OR IGNORE INTO parrot_relationships (
                guild_id,
                user_id,
                username
            )
            VALUES (?, ?, ?)
            """,
            (
                guild_id,
                user_id,
                username
            )
        )

        await db.execute(
            """
            UPDATE parrot_relationships
            SET username = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
              AND user_id = ?
            """,
            (
                username,
                guild_id,
                user_id
            )
        )

        await db.commit()

    finally:
        await db.close()


async def get_parrot_relationship(
    guild_id,
    user_id
):
    db = await _db()

    try:
        row = await (
            await db.execute(
                """
                SELECT *
                FROM parrot_relationships
                WHERE guild_id = ?
                  AND user_id = ?
                """,
                (
                    guild_id,
                    user_id
                )
            )
        ).fetchone()

        return (
            dict(row)
            if row
            else None
        )

    finally:
        await db.close()


async def increase_parrot_familiarity(
    guild_id,
    user_id,
    username,
    amount=1
):
    await ensure_parrot_relationship(
        guild_id,
        user_id,
        username
    )

    db = await _db()

    try:
        await db.execute(
            """
            UPDATE parrot_relationships
            SET familiarity = familiarity + ?,
                username = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
              AND user_id = ?
            """,
            (
                amount,
                username,
                guild_id,
                user_id
            )
        )

        await db.commit()

    finally:
        await db.close()


async def get_parrot_memories(
    guild_id,
    user_id,
    limit=10
):
    db = await _db()

    try:
        rows = await (
            await db.execute(
                """
                SELECT memory, confidence
                FROM parrot_memories
                WHERE guild_id = ?
                  AND user_id = ?
                ORDER BY confidence DESC,
                         updated_at DESC
                LIMIT ?
                """,
                (
                    guild_id,
                    user_id,
                    limit
                )
            )
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        await db.close()


async def get_parrot_jokes(
    guild_id,
    user_id,
    limit=10
):
    db = await _db()

    try:
        rows = await (
            await db.execute(
                """
                SELECT joke
                FROM parrot_running_jokes
                WHERE guild_id = ?
                  AND user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (
                    guild_id,
                    user_id,
                    limit
                )
            )
        ).fetchall()

        return [
            row["joke"]
            for row in rows
        ]

    finally:
        await db.close()


async def format_parrot_status(guild_id):
    parrot = await get_parrot(
        guild_id
    )

    state = (
        "Aboard"
        if parrot["enabled"]
        else "Ashore"
    )

    return "\n".join([
        f"**{parrot['name']}**",
        f"Status: **{state}**",
        f"Mood: **{parrot['mood']}**",
        (
            "Participation Chance: "
            f"**{parrot['participation_chance']}%**"
        ),
        (
            "Crew Interactions: "
            f"**{parrot['interactions']}**"
        ),
        "",
        f"*{parrot['personality']}*"
    ])


async def update_parrot_relationship(
    guild_id,
    user_id,
    username,
    opinion=None,
    nickname=None
):
    await ensure_parrot_relationship(
        guild_id,
        user_id,
        username
    )

    db = await _db()

    try:
        if opinion is not None:
            await db.execute(
                """
                UPDATE parrot_relationships
                SET opinion = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
                  AND user_id = ?
                """,
                (
                    opinion,
                    guild_id,
                    user_id
                )
            )

        if nickname is not None:
            await db.execute(
                """
                UPDATE parrot_relationships
                SET nickname = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
                  AND user_id = ?
                """,
                (
                    nickname,
                    guild_id,
                    user_id
                )
            )

        await db.commit()

    finally:
        await db.close()


async def add_parrot_memory(
    guild_id,
    user_id,
    memory
):
    memory = str(memory).strip()

    if not memory:
        return False

    db = await _db()

    try:
        existing = await (
            await db.execute(
                """
                SELECT id
                FROM parrot_memories
                WHERE guild_id = ?
                  AND user_id = ?
                  AND lower(memory) = lower(?)
                LIMIT 1
                """,
                (
                    guild_id,
                    user_id,
                    memory
                )
            )
        ).fetchone()

        if existing:
            await db.execute(
                """
                UPDATE parrot_memories
                SET confidence = confidence + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (existing["id"],)
            )

            await db.commit()
            return False

        await db.execute(
            """
            INSERT INTO parrot_memories (
                guild_id,
                user_id,
                memory
            )
            VALUES (?, ?, ?)
            """,
            (
                guild_id,
                user_id,
                memory
            )
        )

        await db.commit()
        return True

    finally:
        await db.close()


async def add_parrot_joke(
    guild_id,
    user_id,
    joke
):
    joke = str(joke).strip()

    if not joke:
        return False

    db = await _db()

    try:
        existing = await (
            await db.execute(
                """
                SELECT id
                FROM parrot_running_jokes
                WHERE guild_id = ?
                  AND user_id = ?
                  AND lower(joke) = lower(?)
                LIMIT 1
                """,
                (
                    guild_id,
                    user_id,
                    joke
                )
            )
        ).fetchone()

        if existing:
            return False

        await db.execute(
            """
            INSERT INTO parrot_running_jokes (
                guild_id,
                user_id,
                joke
            )
            VALUES (?, ?, ?)
            """,
            (
                guild_id,
                user_id,
                joke
            )
        )

        await db.commit()
        return True

    finally:
        await db.close()


async def increment_parrot_interactions(
    guild_id,
    amount=1
):
    await ensure_parrot(guild_id)

    db = await _db()

    try:
        await db.execute(
            """
            UPDATE parrots
            SET interactions = interactions + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
            """,
            (
                amount,
                guild_id
            )
        )

        await db.commit()

    finally:
        await db.close()


async def format_parrot_relationship(
    guild_id,
    user_id,
    username
):
    await ensure_parrot_relationship(
        guild_id,
        user_id,
        username
    )

    parrot = await get_parrot(
        guild_id
    )

    relationship = await get_parrot_relationship(
        guild_id,
        user_id
    )

    memories = await get_parrot_memories(
        guild_id,
        user_id,
        5
    )

    jokes = await get_parrot_jokes(
        guild_id,
        user_id,
        5
    )

    familiarity = int(
        relationship["familiarity"]
    )

    if familiarity >= 100:
        tier = "Favorite Perch"
    elif familiarity >= 75:
        tier = "Trusted Snack Supplier"
    elif familiarity >= 50:
        tier = "Feathered Friend"
    elif familiarity >= 25:
        tier = "Known Crewmate"
    else:
        tier = "Suspicious Human"

    nickname = (
        relationship["nickname"]
        or "NONE"
    )

    opinion = (
        relationship["opinion"]
        or "Barnacle hasn't made up his mind yet."
    )

    return "\n".join([
        f"**{parrot['name']} & {username}**",
        f"Relationship: **{tier}**",
        f"Familiarity: **{familiarity}/100**",
        f"Parrot nickname: **{nickname}**",
        f"Parrot opinion: {opinion}",
        f"Memories: **{len(memories)} loaded**",
        f"Running jokes: **{len(jokes)}**"
    ])



# =========================================================
# CAPTAIN <-> PARROT SHARED HISTORY
# =========================================================

async def add_parrot_captain_event(
    guild_id,
    captain_line,
    parrot_line,
    summary="",
    event_type="banter",
    importance=5
):
    captain_line = str(captain_line).strip()
    parrot_line = str(parrot_line).strip()
    summary = str(summary).strip()

    if not captain_line or not parrot_line:
        return False

    db = await _db()

    try:
        # Avoid exact duplicate exchanges.
        existing = await (
            await db.execute(
                """
                SELECT id
                FROM parrot_captain_events
                WHERE guild_id = ?
                  AND lower(captain_line) = lower(?)
                  AND lower(parrot_line) = lower(?)
                LIMIT 1
                """,
                (
                    guild_id,
                    captain_line,
                    parrot_line
                )
            )
        ).fetchone()

        if existing:
            return False

        await db.execute(
            """
            INSERT INTO parrot_captain_events (
                guild_id,
                event_type,
                captain_line,
                parrot_line,
                summary,
                importance
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                event_type,
                captain_line[:1000],
                parrot_line[:1000],
                summary[:500],
                int(importance)
            )
        )

        await db.commit()

        return True

    finally:
        await db.close()


async def get_parrot_captain_events(
    guild_id,
    limit=10
):
    db = await _db()

    try:
        rows = await (
            await db.execute(
                """
                SELECT
                    id,
                    event_type,
                    captain_line,
                    parrot_line,
                    summary,
                    importance,
                    created_at
                FROM parrot_captain_events
                WHERE guild_id = ?
                ORDER BY importance DESC,
                         id DESC
                LIMIT ?
                """,
                (
                    guild_id,
                    int(limit)
                )
            )
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        await db.close()


async def format_parrot_captain_history(
    guild_id,
    limit=10
):
    parrot = await get_parrot(
        guild_id
    )

    events = await get_parrot_captain_events(
        guild_id,
        limit
    )

    if not events:
        return (
            "**Captain Cutlass & "
            + parrot["name"]
            + "**\n"
            + "No memorable arguments have been recorded yet."
        )

    lines = [
        "**Captain Cutlass & "
        + parrot["name"]
        + " — Shared History**"
    ]

    for event in events:
        summary = event["summary"]

        if summary:
            lines.append(
                "• " + summary
            )
        else:
            lines.append(
                "• Captain: "
                + event["captain_line"][:180]
                + " | "
                + parrot["name"]
                + ": "
                + event["parrot_line"][:180]
            )

    return "\n".join(lines)
