import os
import random

import aiosqlite


DB_PATH = os.getenv(
    "DATABASE_PATH",
    "/app/data/captain.db"
)


# ---------------------------------------------------------
# World definitions
# ---------------------------------------------------------

REGIONS = {
    "shattered_coast": {
        "name": "The Shattered Coast",
        "danger": "Low",
        "description": (
            "Broken islands, smugglers, forgotten coves, "
            "and relatively forgiving waters."
        ),
    },

    "blackwater_reach": {
        "name": "Blackwater Reach",
        "danger": "Medium",
        "description": (
            "Dark currents, pirate hunting grounds, "
            "abandoned forts, and dangerous reefs."
        ),
    },

    "devils_expanse": {
        "name": "The Devil's Expanse",
        "danger": "Extreme",
        "description": (
            "Violent seas where monsters, ghost stories, "
            "and legendary pirate crews are said to roam."
        ),
    },
}


ISLANDS = {
    "blacktooth_cove": {
        "name": "Blacktooth Cove",
        "region": "shattered_coast",
        "danger": "Low",
        "description": (
            "A crooked little harbor filled with smugglers, "
            "taverns, and suspicious merchants."
        ),
    },

    "skullfin_island": {
        "name": "Skullfin Island",
        "region": "blackwater_reach",
        "danger": "Medium",
        "description": (
            "A jungle-covered island dotted with ruins, "
            "caves, and the bones of unfortunate explorers."
        ),
    },

    "devils_maw": {
        "name": "Devil's Maw",
        "region": "devils_expanse",
        "danger": "Extreme",
        "description": (
            "A volcanic island surrounded by brutal waters "
            "and tales of creatures large enough to swallow ships."
        ),
    },

    "whispering_key": {
        "name": "Whispering Key",
        "region": "shattered_coast",
        "danger": "Low",
        "description": (
            "A quiet island where strange stone markers "
            "point toward something buried beneath the palms."
        ),
    },

    "deadmans_rest": {
        "name": "Deadman's Rest",
        "region": "blackwater_reach",
        "danger": "High",
        "description": (
            "An abandoned pirate settlement where lanterns "
            "are sometimes seen despite nobody living there."
        ),
    },

    "siren_reef": {
        "name": "Siren's Reef",
        "region": "devils_expanse",
        "danger": "Extreme",
        "description": (
            "Jagged coral, shipwrecks, and enough sailor tales "
            "to make even Captain Cutlass check the horizon twice."
        ),
    },
}


async def _db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


# ---------------------------------------------------------
# Initialization
# ---------------------------------------------------------

async def initialize_pirate_world():

    db = await _db()

    try:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS world_regions (
            region_key TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            danger TEXT DEFAULT 'Low',
            description TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS world_locations (
            location_key TEXT PRIMARY KEY,
            region_key TEXT NOT NULL,
            name TEXT NOT NULL,
            location_type TEXT DEFAULT 'island',
            danger TEXT DEFAULT 'Low',
            description TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS world_discoveries (
            guild_id INTEGER NOT NULL,
            location_key TEXT NOT NULL,
            discovered_by INTEGER DEFAULT 0,
            discovered_by_name TEXT DEFAULT '',
            discovered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            visits INTEGER DEFAULT 1,
            PRIMARY KEY (guild_id, location_key)
        );

        CREATE TABLE IF NOT EXISTS island_activity_state (
            guild_id INTEGER NOT NULL,
            location_key TEXT NOT NULL,
            visits INTEGER DEFAULT 0,
            last_explored_at DATETIME,
            PRIMARY KEY (guild_id, location_key)
        );

        CREATE TABLE IF NOT EXISTS world_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            event_type TEXT DEFAULT 'world',
            content TEXT NOT NULL,
            importance INTEGER DEFAULT 5,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_world_history_guild
        ON world_history(guild_id, id DESC);

        CREATE INDEX IF NOT EXISTS idx_world_discoveries_guild
        ON world_discoveries(guild_id, discovered_at DESC);
        """)

        for key, region in REGIONS.items():

            await db.execute("""
                INSERT INTO world_regions (
                    region_key,
                    name,
                    danger,
                    description
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(region_key)
                DO UPDATE SET
                    name = excluded.name,
                    danger = excluded.danger,
                    description = excluded.description
            """, (
                key,
                region["name"],
                region["danger"],
                region["description"],
            ))

        for key, island in ISLANDS.items():

            await db.execute("""
                INSERT INTO world_locations (
                    location_key,
                    region_key,
                    name,
                    location_type,
                    danger,
                    description
                )
                VALUES (?, ?, ?, 'island', ?, ?)
                ON CONFLICT(location_key)
                DO UPDATE SET
                    region_key = excluded.region_key,
                    name = excluded.name,
                    danger = excluded.danger,
                    description = excluded.description
            """, (
                key,
                island["region"],
                island["name"],
                island["danger"],
                island["description"],
            ))

        await db.commit()

    finally:
        await db.close()


# ---------------------------------------------------------
# History
# ---------------------------------------------------------

async def add_world_history(
    guild_id,
    content,
    event_type="world",
    importance=5
):

    db = await _db()

    try:
        await db.execute("""
            INSERT INTO world_history (
                guild_id,
                event_type,
                content,
                importance
            )
            VALUES (?, ?, ?, ?)
        """, (
            guild_id,
            event_type,
            content,
            importance,
        ))

        await db.commit()

    finally:
        await db.close()


async def get_world_history(
    guild_id,
    limit=15
):

    db = await _db()

    try:
        cursor = await db.execute("""
            SELECT
                event_type,
                content,
                created_at
            FROM world_history
            WHERE guild_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (
            guild_id,
            limit,
        ))

        return await cursor.fetchall()

    finally:
        await db.close()


# ---------------------------------------------------------
# Discoveries
# ---------------------------------------------------------

async def discover_location(
    guild_id,
    location_key,
    user_id,
    username
):

    if location_key not in ISLANDS:
        return False, "Unknown location."

    db = await _db()

    try:
        cursor = await db.execute("""
            SELECT visits
            FROM world_discoveries
            WHERE guild_id = ?
              AND location_key = ?
        """, (
            guild_id,
            location_key,
        ))

        existing = await cursor.fetchone()

        if existing:

            await db.execute("""
                UPDATE world_discoveries
                SET visits = visits + 1
                WHERE guild_id = ?
                  AND location_key = ?
            """, (
                guild_id,
                location_key,
            ))

            await db.commit()

            return False, "already_discovered"

        await db.execute("""
            INSERT INTO world_discoveries (
                guild_id,
                location_key,
                discovered_by,
                discovered_by_name
            )
            VALUES (?, ?, ?, ?)
        """, (
            guild_id,
            location_key,
            user_id,
            username,
        ))

        await db.commit()

        island = ISLANDS[location_key]

        await add_world_history(
            guild_id,
            (
                username
                + " discovered "
                + island["name"]
                + " in "
                + REGIONS[island["region"]]["name"]
                + "."
            ),
            "discovery",
            7
        )

        return True, island

    finally:
        await db.close()


async def get_discovered_locations(
    guild_id
):

    db = await _db()

    try:
        cursor = await db.execute("""
            SELECT
                location_key,
                discovered_by_name,
                discovered_at,
                visits
            FROM world_discoveries
            WHERE guild_id = ?
            ORDER BY discovered_at
        """, (
            guild_id,
        ))

        return await cursor.fetchall()

    finally:
        await db.close()


# ---------------------------------------------------------
# Exploration
# ---------------------------------------------------------

async def explore_random_island(
    guild_id,
    user_id,
    username
):
    """
    Scout the surrounding seas.

    Exploration represents scouting and charting rather
    than physically moving the Living Ship.

    New islands are discovered gradually. Treasure,
    supplies, island lore, and island-specific encounters
    belong to physical island exploration after arrival.
    """

    discovered = await get_discovered_locations(
        guild_id
    )

    discovered_keys = {
        row["location_key"]
        for row in discovered
    }

    undiscovered = [
        key
        for key in ISLANDS
        if key not in discovered_keys
    ]

    # -----------------------------------------------------
    # Discovery roll
    #
    # Only 25% of scouting attempts reveal a new island.
    # This prevents the entire world from being discovered
    # after only a handful of explore commands.
    # -----------------------------------------------------

    discover_new = (
        bool(undiscovered)
        and random.randint(1, 100) <= 25
    )

    if discover_new:

        location_key = random.choice(
            undiscovered
        )

        is_new, _ = await discover_location(
            guild_id,
            location_key,
            user_id,
            username
        )

    else:

        is_new = False

        # Scout somewhere already charted. Blacktooth Cove
        # acts as the crew's starting known waters before
        # the first true discovery has been made.
        known_keys = list(
            discovered_keys
        )

        if not known_keys:
            known_keys = [
                "blacktooth_cove"
            ]

        location_key = random.choice(
            known_keys
        )

    island = ISLANDS[
        location_key
    ]

    region = REGIONS[
        island["region"]
    ]

    # -----------------------------------------------------
    # Scouting encounters
    #
    # Scouting happens from the ship at sea. Physical
    # island rewards are intentionally excluded here.
    # -----------------------------------------------------

    encounter_roll = random.randint(
        1,
        100
    )

    if encounter_roll <= 10:

        encounter_type = "naval"

        encounter = (
            "Lookouts spotted unfamiliar sails "
            "moving through the surrounding waters."
        )

    elif encounter_roll <= 15:

        encounter_type = "monster"

        encounter = (
            "Something enormous moved beneath "
            "the scouting vessel."
        )

    else:

        encounter_type = "quiet"

        if is_new:
            encounter = (
                "The crew charted the island from offshore "
                "and marked it on the ship's maps."
            )
        else:
            encounter = (
                "The crew charted currents, reefs, and "
                "landmarks but found nothing immediately dangerous."
            )

    return {
        "new": is_new,
        "key": location_key,
        "name": island["name"],
        "region": region["name"],
        "danger": island["danger"],
        "description": island["description"],
        "encounter_type": encounter_type,
        "encounter": encounter,
    }


# ---------------------------------------------------------
# Island revisit progression
# ---------------------------------------------------------

async def get_island_activity_state(
    guild_id,
    location_key
):
    db = await _db()

    try:
        row = await (
            await db.execute(
                """
                SELECT
                    visits,
                    last_explored_at
                FROM island_activity_state
                WHERE guild_id = ?
                  AND location_key = ?
                """,
                (
                    guild_id,
                    location_key,
                )
            )
        ).fetchone()

        if not row:
            return {
                "visits": 0,
                "last_explored_at": None,
            }

        return {
            "visits": int(row["visits"]),
            "last_explored_at": row["last_explored_at"],
        }

    finally:
        await db.close()


async def record_island_visit(
    guild_id,
    location_key,
    cooldown_seconds=30 * 60
):
    """
    Atomically claim one physical island exploration.

    Exactly one caller may advance the visit counter during
    a cooldown window. Race losers receive the current state
    without incrementing visits or resetting the cooldown.
    """

    cooldown_seconds = max(
        0,
        int(cooldown_seconds)
    )

    db = await _db()

    try:
        await db.execute(
            "BEGIN IMMEDIATE"
        )

        row = await (
            await db.execute(
                """
                SELECT
                    visits,
                    last_explored_at,
                    CAST(
                        (
                            julianday('now')
                            - julianday(last_explored_at)
                        ) * 86400
                        AS INTEGER
                    ) AS elapsed_seconds
                FROM island_activity_state
                WHERE guild_id = ?
                  AND location_key = ?
                """,
                (
                    guild_id,
                    location_key,
                )
            )
        ).fetchone()

        if row:
            elapsed = (
                int(row["elapsed_seconds"])
                if row["elapsed_seconds"] is not None
                else cooldown_seconds
            )

            if elapsed < cooldown_seconds:
                await db.rollback()

                return {
                    "claimed": False,
                    "visits": int(row["visits"]),
                    "last_explored_at": row[
                        "last_explored_at"
                    ],
                    "remaining_seconds": max(
                        1,
                        cooldown_seconds - elapsed
                    ),
                }

            visits = int(row["visits"]) + 1

            await db.execute(
                """
                UPDATE island_activity_state
                SET visits = ?,
                    last_explored_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
                  AND location_key = ?
                """,
                (
                    visits,
                    guild_id,
                    location_key,
                )
            )

        else:
            visits = 1

            await db.execute(
                """
                INSERT INTO island_activity_state (
                    guild_id,
                    location_key,
                    visits,
                    last_explored_at
                )
                VALUES (?, ?, 1, CURRENT_TIMESTAMP)
                """,
                (
                    guild_id,
                    location_key,
                )
            )

        await db.commit()

        return {
            "claimed": True,
            "visits": visits,
            "last_explored_at": None,
            "remaining_seconds": 0,
        }

    except Exception:
        try:
            await db.rollback()
        except Exception:
            pass

        raise

    finally:
        await db.close()


# ---------------------------------------------------------
# Formatting
# ---------------------------------------------------------

async def format_world(
    guild_id
):

    discoveries = await get_discovered_locations(
        guild_id
    )

    return (
        "**PIRATE WORLD**\n"
        "Known Regions: **"
        + str(len(REGIONS))
        + "**\n"
        "Known Islands: **"
        + str(len(ISLANDS))
        + "**\n"
        "Crew Discoveries: **"
        + str(len(discoveries))
        + "/"
        + str(len(ISLANDS))
        + "**\n\n"
        "Use `!cutlass world map` to view the seas."
    )


async def format_world_map(
    guild_id
):

    discoveries = await get_discovered_locations(
        guild_id
    )

    discovered_keys = {
        row["location_key"]
        for row in discoveries
    }

    lines = [
        "**PIRATE WORLD MAP**"
    ]

    for region_key, region in REGIONS.items():

        lines.append(
            "\n**"
            + region["name"]
            + "**"
            + " — "
            + region["danger"]
        )

        for island_key, island in ISLANDS.items():

            if island["region"] != region_key:
                continue

            marker = (
                "✓"
                if island_key in discovered_keys
                else "?"
            )

            lines.append(
                marker
                + " "
                + (
                    island["name"]
                    if island_key in discovered_keys
                    else "Undiscovered Island"
                )
            )

    return "\n".join(lines)[:1900]


async def format_discoveries(
    guild_id
):

    rows = await get_discovered_locations(
        guild_id
    )

    if not rows:
        return (
            "**WORLD DISCOVERIES**\n"
            "The crew hasn't discovered any islands yet."
        )

    lines = [
        "**WORLD DISCOVERIES**"
    ]

    for row in rows:

        island = ISLANDS.get(
            row["location_key"]
        )

        if not island:
            continue

        lines.append(
            "• "
            + island["name"]
            + " — discovered by "
            + (
                row["discovered_by_name"]
                or "Unknown"
            )
            + " • Visits: "
            + str(row["visits"])
        )

    return "\n".join(lines)[:1900]
