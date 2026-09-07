import os
import random
from datetime import datetime, timezone, timedelta

import aiosqlite

DB_PATH = os.getenv("DATABASE_PATH", "/app/data/captain.db")

from cutlass.world.locks import get_guild_lock
DESTINATIONS = {
    "blacktooth_cove": {
        "name": "Blacktooth Cove",
        "risk": "Low",
        "min_level": 1,
        "hours": 2,
        "supplies": 10,
        "reward": (100, 180),
        "xp": 100,
        "miles": 85,
    },

    "whispering_key": {
        "name": "Whispering Key",
        "risk": "Low",
        "min_level": 1,
        "hours": 3,
        "supplies": 12,
        "reward": (140, 260),
        "xp": 130,
        "miles": 120,
    },

    "skullfin_island": {
        "name": "Skullfin Island",
        "risk": "Medium",
        "min_level": 2,
        "hours": 6,
        "supplies": 25,
        "reward": (250, 450),
        "xp": 225,
        "miles": 240,
    },

    "deadmans_rest": {
        "name": "Deadman's Rest",
        "risk": "High",
        "min_level": 3,
        "hours": 8,
        "supplies": 30,
        "reward": (400, 700),
        "xp": 325,
        "miles": 330,
    },

    "sirens_reef": {
        "name": "Siren's Reef",
        "risk": "Extreme",
        "min_level": 4,
        "hours": 10,
        "supplies": 35,
        "reward": (550, 900),
        "xp": 425,
        "miles": 420,
    },

    "devils_maw": {
        "name": "Devil's Maw",
        "risk": "Extreme",
        "min_level": 4,
        "hours": 12,
        "supplies": 40,
        "reward": (700, 1200),
        "xp": 500,
        "miles": 510,
    },
}

UPGRADES = {
    "reinforced hull": {
        "label": "Reinforced Hull",
        "cost": 1000,
        "max_level": 3,
        "min_level": 1,
        "bonus": "+20 hull cap per level",
    },
    "improved sails": {
        "label": "Improved Sails",
        "cost": 750,
        "max_level": 3,
        "min_level": 1,
        "bonus": "-5% voyage time per level",
    },
    "expanded hold": {
        "label": "Expanded Hold",
        "cost": 800,
        "max_level": 3,
        "min_level": 2,
        "bonus": "+25 supply cap per level",
    },
    "improved galley": {
        "label": "Improved Galley",
        "cost": 600,
        "max_level": 3,
        "min_level": 3,
        "bonus": "-5% voyage supply cost per level",
    },
    "crows nest": {
        "label": "Crow's Nest",
        "cost": 900,
        "max_level": 3,
        "min_level": 4,
        "bonus": "+5% voyage treasure and XP per level",
    },
    "hardened keel": {
        "label": "Hardened Keel",
        "cost": 1200,
        "max_level": 2,
        "min_level": 5,
        "bonus": "+35 hull cap per level",
    },
}


SHIP_LEVEL_MILESTONES = {
    2: {
        "label": "First Rigging",
        "achievement": "First Rigging",
        "description": "The Living Ship reached Level 2.",
    },
    4: {
        "label": "Deepwater Runner",
        "achievement": "Deepwater Runner",
        "description": "The Living Ship reached Level 4.",
    },
    6: {
        "label": "Veteran Hull",
        "achievement": "Veteran Hull",
        "description": "The Living Ship reached Level 6.",
    },
    8: {
        "label": "Flagship",
        "achievement": "Flagship",
        "description": "The Living Ship reached Level 8.",
    },
    10: {
        "label": "Living Legend",
        "achievement": "Living Legend",
        "description": "The Living Ship reached Level 10.",
    },
}


CAPTURE_MILESTONES = {
    1: {
        "label": "First Prize",
        "achievement": "First Prize",
        "description": "Captured the first enemy vessel.",
    },
    5: {
        "label": "Prize Fleet",
        "achievement": "Prize Fleet",
        "description": "Captured five enemy vessels.",
    },
    10: {
        "label": "Boarding Legend",
        "achievement": "Boarding Legend",
        "description": "Captured ten enemy vessels.",
    },
}


# =========================================================
# Disabled Ship Recovery
# =========================================================

PASSIVE_RECOVERY_INTERVAL_SECONDS = 600
PASSIVE_RECOVERY_HULL_PER_INTERVAL = 1
OPERATIONAL_HULL_PERCENT = 0.10


def _now():
    return datetime.now(timezone.utc)


def _ts(dt=None):
    return (dt or _now()).strftime("%Y-%m-%d %H:%M:%S")


async def _db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db



# =========================================================
# SHIP COMBAT ABILITIES
# =========================================================

SHIP_COMBAT_ABILITIES = {

    "brace": {
        "name": "Brace for Impact",
        "cooldown": 3,
        "description": (
            "Reduce the next incoming combat hit by 50%."
        ),
    },

    "broadside": {
        "name": "Full Broadside",
        "cooldown": 3,
        "description": (
            "Increase the next outgoing combat attack by 50%."
        ),
    },

    "repairs": {
        "name": "Emergency Repairs",
        "cooldown": 4,
        "description": (
            "Restore 10% of maximum hull during combat."
        ),
    },

    "rally": {
        "name": "Rally the Crew",
        "cooldown": 4,
        "description": (
            "Increase the next outgoing attack by 25% "
            "and reduce the next incoming hit by 25%."
        ),
    },
}


SHIP_ABILITY_ALIASES = {
    "brace": "brace",
    "brace for impact": "brace",
    "broadside": "broadside",
    "full broadside": "broadside",
    "repairs": "repairs",
    "repair": "repairs",
    "emergency repairs": "repairs",
    "rally": "rally",
    "rally the crew": "rally",
}


def normalize_ship_ability(raw_name):

    key = " ".join(
        str(
            raw_name or ""
        ).lower().split()
    )

    return SHIP_ABILITY_ALIASES.get(
        key
    )


def get_ship_ability_info(raw_name):

    key = normalize_ship_ability(
        raw_name
    )

    if not key:
        return None

    info = dict(
        SHIP_COMBAT_ABILITIES[key]
    )

    info["key"] = key

    return info


def apply_ship_outgoing_ability(
    damage,
    *,
    broadside=False,
    rally=False,
):

    damage = max(
        0,
        int(damage)
    )

    multiplier = 1.0

    if broadside:
        multiplier *= 1.50

    if rally:
        multiplier *= 1.25

    if damage <= 0:
        return 0

    return max(
        1,
        round(
            damage * multiplier
        )
    )


def apply_ship_incoming_ability(
    damage,
    *,
    brace=False,
    rally=False,
):

    damage = max(
        0,
        int(damage)
    )

    multiplier = 1.0

    if brace:
        multiplier *= 0.50

    if rally:
        multiplier *= 0.75

    if damage <= 0:
        return 0

    return max(
        1,
        round(
            damage * multiplier
        )
    )


async def initialize_ship_world():
    db = await _db()
    try:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS ship_settings (
            guild_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0,
            channel_id INTEGER DEFAULT 0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS ships (
            guild_id INTEGER PRIMARY KEY,
            name TEXT DEFAULT 'The Rusty Kraken',
            level INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0,
            hull INTEGER DEFAULT 100,
            sails INTEGER DEFAULT 100,
            supplies INTEGER DEFAULT 100,
            morale INTEGER DEFAULT 100,
            treasury INTEGER DEFAULT 0,
            location TEXT DEFAULT 'Port Cutlass',
            voyages_completed INTEGER DEFAULT 0,
            distance_sailed INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS ship_upgrades (
            guild_id INTEGER NOT NULL,
            upgrade_key TEXT NOT NULL,
            level INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, upgrade_key)
        );
        CREATE TABLE IF NOT EXISTS ship_voyages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            destination TEXT NOT NULL,
            risk TEXT NOT NULL,
            supplies_cost INTEGER NOT NULL,
            reward_min INTEGER NOT NULL,
            reward_max INTEGER NOT NULL,
            xp_reward INTEGER NOT NULL,
            distance INTEGER NOT NULL,
            started_at DATETIME NOT NULL,
            completes_at DATETIME NOT NULL,
            status TEXT DEFAULT 'active',
            result TEXT DEFAULT '',
            completed_at DATETIME
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_ship_active_voyage
        ON ship_voyages(guild_id) WHERE status = 'active';
        CREATE TABLE IF NOT EXISTS ship_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            event_type TEXT DEFAULT 'event',
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS ship_contributions (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT DEFAULT '',
            amount INTEGER DEFAULT 0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (guild_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS ship_contribution_rewards (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            milestone INTEGER NOT NULL,
            reward INTEGER NOT NULL,
            claimed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            paid_at DATETIME DEFAULT NULL,
            PRIMARY KEY (
                guild_id,
                user_id,
                milestone
            )
        );

        CREATE TABLE IF NOT EXISTS ship_combat_abilities (
            guild_id INTEGER NOT NULL,
            ability_key TEXT NOT NULL,
            cooldown_turns INTEGER DEFAULT 0,
            active INTEGER DEFAULT 0,
            activated_by INTEGER DEFAULT 0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (guild_id, ability_key)
        );
        CREATE TABLE IF NOT EXISTS captured_ships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            enemy_name TEXT NOT NULL,
            captured_by INTEGER DEFAULT 0,
            captured_by_name TEXT DEFAULT '',
            reward INTEGER DEFAULT 0,
            xp_reward INTEGER DEFAULT 0,
            status TEXT DEFAULT 'held',
            resolution_value INTEGER DEFAULT 0,
            resolution_supplies INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_captured_ships_guild_status
        ON captured_ships(guild_id, status, id DESC);
        """)

        # -------------------------------------------------
        # Contribution reward paid_at migration
        # -------------------------------------------------

        reward_columns = await (
            await db.execute(
                """
                PRAGMA table_info(
                    ship_contribution_rewards
                )
                """
            )
        ).fetchall()

        reward_column_names = {
            row["name"]
            for row in reward_columns
        }

        if "paid_at" not in reward_column_names:
            await db.execute(
                """
                ALTER TABLE ship_contribution_rewards
                ADD COLUMN paid_at DATETIME DEFAULT NULL
                """
            )

        # -------------------------------------------------
        # Disabled ship passive-recovery migration
        # -------------------------------------------------

        columns = await (
            await db.execute(
                "PRAGMA table_info(ships)"
            )
        ).fetchall()

        column_names = {
            row["name"]
            for row in columns
        }

        if "recovery_started_at" not in column_names:
            await db.execute(
                """
                ALTER TABLE ships
                ADD COLUMN recovery_started_at DATETIME
                """
            )

        if "recovery_last_at" not in column_names:
            await db.execute(
                """
                ALTER TABLE ships
                ADD COLUMN recovery_last_at DATETIME
                """
            )

        await db.commit()
    finally:
        await db.close()


async def ensure_ship(guild_id):
    db = await _db()
    try:
        await db.execute("INSERT OR IGNORE INTO ship_settings (guild_id) VALUES (?)", (guild_id,))
        await db.execute("INSERT OR IGNORE INTO ships (guild_id) VALUES (?)", (guild_id,))
        await db.commit()
    finally:
        await db.close()


async def get_ship_settings(guild_id):
    await ensure_ship(guild_id)
    db = await _db()
    try:
        row = await (await db.execute("SELECT enabled, channel_id FROM ship_settings WHERE guild_id = ?", (guild_id,))).fetchone()
        return {"enabled": bool(row["enabled"]), "channel_id": int(row["channel_id"] or 0)}
    finally:
        await db.close()


async def set_ship_setting(guild_id, field, value):
    if field not in {"enabled", "channel_id"}:
        raise ValueError("Invalid ship setting")
    await ensure_ship(guild_id)
    db = await _db()
    try:
        await db.execute(f"UPDATE ship_settings SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE guild_id = ?", (value, guild_id))
        await db.commit()
    finally:
        await db.close()


async def _get_ship_raw(guild_id):
    await ensure_ship(guild_id)

    db = await _db()

    try:

        row = await (
            await db.execute(
                """
                SELECT *
                FROM ships
                WHERE guild_id = ?
                """,
                (guild_id,)
            )
        ).fetchone()

        return dict(row)

    finally:
        await db.close()


async def apply_passive_recovery(guild_id):
    """
    Atomically apply passive hull recovery earned through
    elapsed real time for one guild.
    """

    async with get_guild_lock(guild_id):
        return await _apply_passive_recovery_unlocked(
            guild_id
        )


async def get_ship(guild_id):
    """
    Return the Living Ship after applying any passive
    disabled-ship recovery earned through elapsed real time.
    """

    await ensure_ship(guild_id)

    await apply_passive_recovery(
        guild_id
    )

    return await _get_ship_raw(
        guild_id
    )


async def get_upgrade_levels(guild_id):
    db = await _db()
    try:
        rows = await (await db.execute("SELECT upgrade_key, level FROM ship_upgrades WHERE guild_id = ?", (guild_id,))).fetchall()
        return {r["upgrade_key"]: int(r["level"]) for r in rows}
    finally:
        await db.close()


def ship_caps(upgrades):
    return {
        "hull": (
            100
            + 20 * upgrades.get("reinforced hull", 0)
            + 35 * upgrades.get("hardened keel", 0)
        ),
        "supplies": 100 + 25 * upgrades.get("expanded hold", 0),
    }


def _ship_milestone(level):
    return SHIP_LEVEL_MILESTONES.get(
        int(level)
    )


def _next_ship_milestone(level):
    current = int(level)

    for milestone_level in sorted(
        SHIP_LEVEL_MILESTONES
    ):
        if milestone_level > current:
            return (
                milestone_level,
                SHIP_LEVEL_MILESTONES[milestone_level]
            )

    return None, None


def _capture_sale_value(capture):
    reward = int(
        capture.get(
            "reward",
            0
        )
    )

    xp_reward = int(
        capture.get(
            "xp_reward",
            0
        )
    )

    return max(
        100,
        reward // 2 + xp_reward // 2
    )


def _capture_salvage_value(capture):
    reward = int(
        capture.get(
            "reward",
            0
        )
    )

    xp_reward = int(
        capture.get(
            "xp_reward",
            0
        )
    )

    return max(
        50,
        reward // 4 + xp_reward // 4
    )


def _capture_salvage_supplies(capture):
    reward = int(
        capture.get(
            "reward",
            0
        )
    )

    xp_reward = int(
        capture.get(
            "xp_reward",
            0
        )
    )

    return max(
        10,
        reward // 25 + xp_reward // 6
    )


async def _award_achievement_if_possible(
    guild_id,
    user_id,
    achievement,
    description=""
):
    if not user_id:
        return False

    try:
        from memory import award_achievement
    except Exception:
        return False

    try:
        return await award_achievement(
            guild_id,
            user_id,
            achievement,
            description
        )
    except Exception:
        return False


def operational_hull_threshold(max_hull):
    """
    Hull required before a disabled ship becomes operational.

    Passive recovery stops at this threshold.
    """

    return max(
        1,
        int(
            (int(max_hull) * OPERATIONAL_HULL_PERCENT)
            + 0.999999
        )
    )


def _parse_db_timestamp(value):

    if not value:
        return None

    try:

        dt = datetime.strptime(
            str(value),
            "%Y-%m-%d %H:%M:%S"
        )

        return dt.replace(
            tzinfo=timezone.utc
        )

    except (TypeError, ValueError):
        return None


async def _apply_passive_recovery_unlocked(guild_id):
    """
    Apply passive hull recovery earned through elapsed real time.

    Recovery:
      - costs no treasury
      - survives restarts and downtime
      - cannot over-heal
      - stops at the operational threshold
    """

    await ensure_ship(guild_id)

    upgrades = await get_upgrade_levels(
        guild_id
    )

    max_hull = int(
        ship_caps(upgrades)["hull"]
    )

    threshold = operational_hull_threshold(
        max_hull
    )

    now = _now()

    db = await _db()

    try:

        row = await (
            await db.execute(
                """
                SELECT
                    hull,
                    recovery_started_at,
                    recovery_last_at
                FROM ships
                WHERE guild_id = ?
                """,
                (guild_id,)
            )
        ).fetchone()

        if not row:
            return {
                "recovered": 0,
                "hull": 0,
                "threshold": threshold,
                "recovering": False,
                "restored": False,
            }

        hull = max(
            0,
            int(row["hull"])
        )

        recovery_started = _parse_db_timestamp(
            row["recovery_started_at"]
        )

        recovery_last = _parse_db_timestamp(
            row["recovery_last_at"]
        )

        # Already operational.
        if hull >= threshold:

            if recovery_started or recovery_last:

                await db.execute(
                    """
                    UPDATE ships
                    SET recovery_started_at = NULL,
                        recovery_last_at = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE guild_id = ?
                    """,
                    (guild_id,)
                )

                await db.commit()

            return {
                "recovered": 0,
                "hull": hull,
                "threshold": threshold,
                "recovering": False,
                "restored": False,
            }

        # Below threshold with no clock means recovery begins now.
        if recovery_started is None:

            recovery_started = now

            await db.execute(
                """
                UPDATE ships
                SET recovery_started_at = ?,
                    recovery_last_at = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
                """,
                (
                    _ts(now),
                    _ts(now),
                    guild_id,
                )
            )

            await db.commit()

            return {
                "recovered": 0,
                "hull": hull,
                "threshold": threshold,
                "recovering": True,
                "restored": False,
            }

        if recovery_last is None:
            recovery_last = recovery_started

        elapsed = max(
            0,
            int(
                (
                    now - recovery_last
                ).total_seconds()
            )
        )

        intervals = (
            elapsed
            // PASSIVE_RECOVERY_INTERVAL_SECONDS
        )

        if intervals < 1:

            return {
                "recovered": 0,
                "hull": hull,
                "threshold": threshold,
                "recovering": True,
                "restored": False,
            }

        possible_recovery = (
            intervals
            * PASSIVE_RECOVERY_HULL_PER_INTERVAL
        )

        recovered = min(
            possible_recovery,
            threshold - hull
        )

        new_hull = min(
            threshold,
            hull + recovered
        )

        intervals_used = (
            recovered
            + PASSIVE_RECOVERY_HULL_PER_INTERVAL
            - 1
        ) // PASSIVE_RECOVERY_HULL_PER_INTERVAL

        new_last = (
            recovery_last
            + timedelta(
                seconds=(
                    intervals_used
                    * PASSIVE_RECOVERY_INTERVAL_SECONDS
                )
            )
        )

        restored = new_hull >= threshold

        await db.execute(
            """
            UPDATE ships
            SET hull = ?,
                recovery_last_at = ?,
                recovery_started_at = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
            """,
            (
                new_hull,
                None if restored else _ts(new_last),
                None if restored else _ts(recovery_started),
                guild_id,
            )
        )

        await db.commit()

        result = {
            "recovered": recovered,
            "hull": new_hull,
            "threshold": threshold,
            "recovering": not restored,
            "restored": restored,
        }

    finally:
        await db.close()


    if restored:

        await add_history(
            guild_id,
            (
                "The Living Ship completed **passive emergency recovery** "
                "and returned to **operational status** at **"
                + str(new_hull)
                + "/"
                + str(max_hull)
                + " hull**."
            ),
            "ship_restored"
        )

    return result


async def get_ship_operational_status(guild_id, ship=None):
    """
    Return authoritative Living Ship operational state.

    A ship below the configured operational hull threshold
    remains disabled even when passive recovery has raised
    hull above zero.
    """

    if ship is None:
        ship = await get_ship(
            guild_id
        )

    upgrades = await get_upgrade_levels(
        guild_id
    )

    max_hull = int(
        ship_caps(upgrades)["hull"]
    )

    threshold = operational_hull_threshold(
        max_hull
    )

    hull = max(
        0,
        int(ship["hull"])
    )

    operational = (
        hull >= threshold
    )

    return {
        "operational": operational,
        "disabled": not operational,
        "recovering": not operational,
        "hull": hull,
        "max_hull": max_hull,
        "threshold": threshold,
        "needed": max(
            0,
            threshold - hull
        ),
    }


def xp_needed(level):
    return 500 * max(1, level)


async def add_history(guild_id, content, event_type="event"):
    db = await _db()
    try:
        await db.execute("INSERT INTO ship_history (guild_id, event_type, content) VALUES (?, ?, ?)", (guild_id, event_type, content))
        await db.commit()
    finally:
        await db.close()


async def get_history(guild_id, limit=12):
    db = await _db()
    try:
        rows = await (await db.execute("SELECT content, created_at FROM ship_history WHERE guild_id = ? ORDER BY id DESC LIMIT ?", (guild_id, limit))).fetchall()
        return [(r["content"], r["created_at"]) for r in rows]
    finally:
        await db.close()


async def get_history_records(
    guild_id,
    limit=20
):
    """
    Return recent Living Ship history with event types intact.
    Intended for authoritative conversational grounding.
    """

    db = await _db()

    try:
        rows = await (
            await db.execute(
                """
                SELECT
                    event_type,
                    content,
                    created_at
                FROM ship_history
                WHERE guild_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (
                    guild_id,
                    int(limit),
                )
            )
        ).fetchall()

        return [
            {
                "event_type": row["event_type"],
                "content": row["content"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    finally:
        await db.close()


async def get_captured_ships(
    guild_id,
    *,
    status="held",
    limit=12
):
    db = await _db()

    try:
        params = [guild_id]
        where = "guild_id = ?"

        if status:
            where += " AND status = ?"
            params.append(status)

        params.append(int(limit))

        rows = await (
            await db.execute(
                f"""
                SELECT
                    id,
                    enemy_name,
                    captured_by,
                    captured_by_name,
                    reward,
                    xp_reward,
                    status,
                    resolution_value,
                    resolution_supplies,
                    notes,
                    created_at,
                    updated_at
                FROM captured_ships
                WHERE {where}
                ORDER BY id DESC
                LIMIT ?
                """,
                tuple(params)
            )
        ).fetchall()

        return [
            {
                "id": row["id"],
                "enemy_name": row["enemy_name"],
                "captured_by": row["captured_by"],
                "captured_by_name": row["captured_by_name"],
                "reward": row["reward"],
                "xp_reward": row["xp_reward"],
                "status": row["status"],
                "resolution_value": row["resolution_value"],
                "resolution_supplies": row["resolution_supplies"],
                "notes": row["notes"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    finally:
        await db.close()


async def count_captured_ships(
    guild_id,
    *,
    status=None
):
    db = await _db()

    try:
        params = [guild_id]
        where = "guild_id = ?"

        if status:
            where += " AND status = ?"
            params.append(status)

        row = await (
            await db.execute(
                f"""
                SELECT COUNT(*) AS total
                FROM captured_ships
                WHERE {where}
                """,
                tuple(params)
            )
        ).fetchone()

        return int(
            row["total"]
            if row
            else 0
        )

    finally:
        await db.close()


async def format_captured_ships(
    guild_id,
    limit=8
):
    captures = await get_captured_ships(
        guild_id,
        status="held",
        limit=limit
    )

    lines = [
        "**CAPTURED SHIPS**"
    ]

    if not captures:
        lines.extend([
            "No captured vessels are being held.",
            "",
            "Board a weakened enemy ship to add one to the prize ledger.",
        ])
        return "\n".join(lines)

    for capture in captures:
        sale_value = _capture_sale_value(
            capture
        )

        salvage_value = _capture_salvage_value(
            capture
        )

        salvage_supplies = _capture_salvage_supplies(
            capture
        )

        captured_by = (
            capture["captured_by_name"]
            or (
                "User "
                + str(capture["captured_by"])
                if capture["captured_by"]
                else "Unknown crew"
            )
        )

        lines.extend([
            "",
            (
                "**"
                + str(capture["id"])
                + ". "
                + str(capture["enemy_name"])
                + "**"
            ),
            "Captured by: " + captured_by,
            (
                "Sell value: **"
                + str(sale_value)
                + " doubloons**"
            ),
            (
                "Salvage yield: **"
                + str(salvage_value)
                + " doubloons** and **"
                + str(salvage_supplies)
                + " supplies**"
            ),
            (
                "Use `!cutlass ship capture sell "
                + str(capture["id"])
                + "` or `!cutlass ship capture salvage "
                + str(capture["id"])
                + "`."
            ),
        ])

    lines.extend([
        "",
        "Captured vessels stay on the ledger until they are sold or salvaged.",
    ])

    return "\n".join(lines)


async def record_captured_ship(
    guild_id,
    enemy_name,
    *,
    captured_by_user_id=0,
    captured_by_name="",
    reward=0,
    xp_reward=0,
    notes="",
    award_user_id=None,
):
    await ensure_ship(
        guild_id
    )

    enemy_name = str(
        enemy_name or "Unknown Vessel"
    ).strip()[:160]

    captured_by_name = str(
        captured_by_name or ""
    ).strip()[:120]

    reward = max(
        0,
        int(reward)
    )

    xp_reward = max(
        0,
        int(xp_reward)
    )

    notes = str(
        notes or ""
    ).strip()[:500]

    db = await _db()

    try:
        cursor = await db.execute(
            """
            INSERT INTO captured_ships (
                guild_id,
                enemy_name,
                captured_by,
                captured_by_name,
                reward,
                xp_reward,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                enemy_name,
                int(captured_by_user_id or 0),
                captured_by_name,
                reward,
                xp_reward,
                notes,
            )
        )

        capture_id = cursor.lastrowid

        await db.commit()

    finally:
        await db.close()

    total_captures = await count_captured_ships(
        guild_id
    )

    milestone_text = ""

    if total_captures in CAPTURE_MILESTONES:
        milestone = CAPTURE_MILESTONES[
            total_captures
        ]

        await add_history(
            guild_id,
            (
                "Captured vessel milestone reached: "
                + milestone["label"]
                + " — "
                + milestone["description"]
            ),
            "capture_milestone"
        )

        await _award_achievement_if_possible(
            guild_id,
            award_user_id,
            milestone["achievement"],
            milestone["description"]
        )

        milestone_text = (
            "Captured vessel milestone reached: "
            + milestone["label"]
            + "."
        )

    await add_history(
        guild_id,
        (
            "Enemy vessel captured: **"
            + enemy_name
            + "**"
            + (
                " by "
                + captured_by_name
                if captured_by_name
                else ""
            )
            + "."
        ),
        "capture"
    )

    capture = await get_captured_ship(
        guild_id,
        capture_id
    )

    if capture is None:
        return None

    capture["total_captures"] = total_captures
    capture["milestone_text"] = milestone_text

    return capture


async def get_captured_ship(
    guild_id,
    capture_id
):
    db = await _db()

    milestones = []

    try:
        row = await (
            await db.execute(
                """
                SELECT
                    id,
                    enemy_name,
                    captured_by,
                    captured_by_name,
                    reward,
                    xp_reward,
                    status,
                    resolution_value,
                    resolution_supplies,
                    notes,
                    created_at,
                    updated_at
                FROM captured_ships
                WHERE guild_id = ?
                  AND id = ?
                """,
                (
                    guild_id,
                    int(capture_id),
                )
            )
        ).fetchone()

        if row is None:
            return None

        return {
            "id": row["id"],
            "enemy_name": row["enemy_name"],
            "captured_by": row["captured_by"],
            "captured_by_name": row["captured_by_name"],
            "reward": row["reward"],
            "xp_reward": row["xp_reward"],
            "status": row["status"],
            "resolution_value": row["resolution_value"],
            "resolution_supplies": row["resolution_supplies"],
            "notes": row["notes"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    finally:
        await db.close()


async def resolve_captured_ship(
    guild_id,
    capture_id,
    action
):
    action = " ".join(
        str(action or "").lower().split()
    )

    if action not in {
        "sell",
        "salvage",
    }:
        return False, "Use `sell` or `salvage` when resolving a captured ship."

    async with get_guild_lock(
        guild_id
    ):
        await ensure_ship(
            guild_id
        )

        capture = await get_captured_ship(
            guild_id,
            capture_id
        )

        if not capture:
            return False, "That captured vessel could not be found."

        if capture["status"] != "held":
            return False, "That captured vessel has already been resolved."

        upgrades = await get_upgrade_levels(
            guild_id
        )

        max_supplies = int(
            ship_caps(
                upgrades
            )["supplies"]
        )

        if action == "sell":
            payout = _capture_sale_value(
                capture
            )

            db = await _db()

            try:
                await db.execute(
                    """
                    UPDATE ships
                    SET treasury = treasury + ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE guild_id = ?
                    """,
                    (
                        payout,
                        guild_id,
                    )
                )

                await db.execute(
                    """
                    UPDATE captured_ships
                    SET status = 'sold',
                        resolution_value = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE guild_id = ?
                      AND id = ?
                    """,
                    (
                        payout,
                        guild_id,
                        int(capture_id),
                    )
                )

                await db.commit()

            finally:
                await db.close()

            text = (
                "Sold captured vessel **"
                + capture["enemy_name"]
                + "** for **"
                + str(payout)
                + " doubloons**."
            )

            await add_history(
                guild_id,
                text,
                "capture_sell"
            )

            return True, text

        payout = _capture_salvage_value(
            capture
        )

        supplies = _capture_salvage_supplies(
            capture
        )

        db = await _db()

        try:
            await db.execute(
                """
                UPDATE ships
                SET treasury = treasury + ?,
                    supplies = MIN(?, supplies + ?),
                    updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
                """,
                (
                    payout,
                    max_supplies,
                    supplies,
                    guild_id,
                )
            )

            await db.execute(
                """
                UPDATE captured_ships
                SET status = 'salvaged',
                    resolution_value = ?,
                    resolution_supplies = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
                  AND id = ?
                """,
                (
                    payout,
                    supplies,
                    guild_id,
                    int(capture_id),
                )
            )

            await db.commit()

        finally:
            await db.close()

        text = (
            "Salvaged captured vessel **"
            + capture["enemy_name"]
            + "** for **"
            + str(payout)
            + " doubloons** and **"
            + str(supplies)
            + " supplies**."
        )

        await add_history(
            guild_id,
            text,
            "capture_salvage"
        )

        return True, text


async def get_completed_voyages(
    guild_id,
    limit=8
):
    """
    Return completed voyages newest first.

    This intentionally excludes battles, exploration,
    repairs, island activity, and other ship events.
    """

    db = await _db()

    try:

        rows = await (
            await db.execute(
                """
                SELECT
                    id,
                    content,
                    created_at
                FROM ship_history
                WHERE guild_id = ?
                  AND event_type = 'voyage_complete'
                ORDER BY id DESC
                LIMIT ?
                """,
                (
                    guild_id,
                    int(limit),
                )
            )
        ).fetchall()

        return [
            {
                "id": row["id"],
                "content": row["content"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    finally:
        await db.close()


async def rename_ship(guild_id, name):
    name = " ".join(name.split()).strip()[:60]
    if len(name) < 2:
        raise ValueError("Ship name is too short.")
    await ensure_ship(guild_id)
    db = await _db()
    try:
        await db.execute("UPDATE ships SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE guild_id = ?", (name, guild_id))
        await db.commit()
    finally:
        await db.close()
    await add_history(guild_id, f"The ship was renamed **{name}**.", "rename")
    return name


SHIP_CONTRIBUTION_MILESTONES = (
    (100, 25),
    (250, 50),
    (500, 100),
    (1000, 200),
    (2500, 400),
    (5000, 750),
    (10000, 1250),
)


def contribution_milestones_crossed(
    previous_total,
    new_total,
):
    """
    Return contribution milestones crossed between
    two cumulative contribution totals.

    Each result is:
        {
            "milestone": int,
            "reward": int,
        }
    """

    previous_total = max(
        0,
        int(previous_total)
    )

    new_total = max(
        0,
        int(new_total)
    )

    return [
        {
            "milestone": milestone,
            "reward": reward,
        }
        for milestone, reward
        in SHIP_CONTRIBUTION_MILESTONES
        if (
            previous_total < milestone
            <= new_total
        )
    ]


async def donate(
    guild_id,
    user_id,
    username,
    amount,
    get_balance,
    change_balance
):
    async with get_guild_lock(guild_id):

        amount = int(amount)

        if amount < 1:
            return (
                False,
                "Donation must be at least 1 doubloon."
            )

        # Re-read the player's balance while holding the
        # guild lock so two simultaneous donations cannot
        # both spend the same balance.
        balance = await get_balance(
            guild_id,
            user_id
        )

        if balance < amount:
            return (
                False,
                "Ye only have **"
                + str(balance)
                + " doubloons**."
            )

        await change_balance(
            guild_id,
            user_id,
            -amount
        )

        db = await _db()

        try:
            await db.execute(
                """
                UPDATE ships
                SET treasury = treasury + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
                """,
                (
                    amount,
                    guild_id,
                )
            )

            contribution_row = await (
                await db.execute(
                    """
                    SELECT amount
                    FROM ship_contributions
                    WHERE guild_id = ?
                      AND user_id = ?
                    """,
                    (
                        guild_id,
                        user_id,
                    )
                )
            ).fetchone()

            previous_contribution = (
                int(
                    contribution_row["amount"]
                )
                if contribution_row
                else 0
            )

            await db.execute(
                """
                INSERT INTO ship_contributions (
                    guild_id,
                    user_id,
                    username,
                    amount
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id)
                DO UPDATE SET
                    username = excluded.username,
                    amount = amount + excluded.amount,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    guild_id,
                    user_id,
                    username,
                    amount,
                )
            )

            new_contribution = (
                previous_contribution
                + amount
            )

            await db.commit()

        finally:
            await db.close()

        await add_history(
            guild_id,
            (
                "**"
                + username
                + "** donated **"
                + str(amount)
                + " doubloons** to the ship treasury."
            ),
            "donation"
        )

        await claim_contribution_milestones(
            guild_id,
            user_id,
            previous_contribution,
            new_contribution,
        )

        pending_milestones = (
            await get_pending_contribution_rewards(
                guild_id,
                user_id,
            )
        )

        paid_milestones = []
        pending_reward_total = 0

        if pending_milestones:

            pending_reward_total = sum(
                int(item["reward"])
                for item in pending_milestones
            )

            try:
                await change_balance(
                    guild_id,
                    user_id,
                    pending_reward_total,
                )

                await mark_contribution_rewards_paid(
                    guild_id,
                    user_id,
                    pending_milestones,
                )

                paid_milestones = (
                    pending_milestones
                )

                pending_reward_total = 0

            except Exception as exc:
                print(
                    "Contribution milestone payout "
                    "deferred:",
                    repr(exc),
                )

        return (
            True,
            "**"
            + username
            + "** donated **"
            + str(amount)
            + " doubloons** to the ship treasury.",
            paid_milestones,
            pending_reward_total,
        )


async def claim_contribution_milestones(
    guild_id,
    user_id,
    previous_total,
    new_total,
):
    """
    Atomically claim newly crossed contribution milestones.

    The PRIMARY KEY prevents a milestone from being claimed
    more than once for the same guild/member.

    Returns only milestones successfully claimed now.
    """

    candidates = contribution_milestones_crossed(
        previous_total,
        new_total,
    )

    if not candidates:
        return []

    db = await _db()

    claimed = []

    try:

        for item in candidates:

            cursor = await db.execute(
                """
                INSERT OR IGNORE INTO ship_contribution_rewards (
                    guild_id,
                    user_id,
                    milestone,
                    reward
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    guild_id,
                    user_id,
                    item["milestone"],
                    item["reward"],
                )
            )

            if cursor.rowcount == 1:
                claimed.append(
                    dict(item)
                )

        await db.commit()

        return claimed

    finally:
        await db.close()


async def get_contribution_rewards(
    guild_id,
    user_id,
):
    """
    Return contribution milestones already claimed by a
    guild member.
    """

    db = await _db()

    try:
        rows = await (
            await db.execute(
                """
                SELECT
                    milestone,
                    reward,
                    claimed_at
                FROM ship_contribution_rewards
                WHERE guild_id = ?
                  AND user_id = ?
                ORDER BY milestone
                """,
                (
                    guild_id,
                    user_id,
                )
            )
        ).fetchall()

        return [
            {
                "milestone": int(
                    row["milestone"]
                ),
                "reward": int(
                    row["reward"]
                ),
                "claimed_at": row[
                    "claimed_at"
                ],
            }
            for row in rows
        ]

    finally:
        await db.close()


async def get_pending_contribution_rewards(
    guild_id,
    user_id,
):
    """
    Return milestone rewards which have been earned but
    have not yet been successfully credited to the member.
    """

    db = await _db()

    try:
        rows = await (
            await db.execute(
                """
                SELECT
                    milestone,
                    reward
                FROM ship_contribution_rewards
                WHERE guild_id = ?
                  AND user_id = ?
                  AND paid_at IS NULL
                ORDER BY milestone
                """,
                (
                    guild_id,
                    user_id,
                )
            )
        ).fetchall()

        return [
            {
                "milestone": int(
                    row["milestone"]
                ),
                "reward": int(
                    row["reward"]
                ),
            }
            for row in rows
        ]

    finally:
        await db.close()


async def mark_contribution_rewards_paid(
    guild_id,
    user_id,
    milestones,
):
    """
    Mark successfully credited milestone rewards paid.
    """

    milestone_values = sorted(
        {
            int(item["milestone"])
            for item in milestones
        }
    )

    if not milestone_values:
        return 0

    placeholders = ",".join(
        "?"
        for _ in milestone_values
    )

    db = await _db()

    try:
        cursor = await db.execute(
            f"""
            UPDATE ship_contribution_rewards
            SET paid_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
              AND user_id = ?
              AND paid_at IS NULL
              AND milestone IN ({placeholders})
            """,
            (
                guild_id,
                user_id,
                *milestone_values,
            )
        )

        await db.commit()

        return max(
            0,
            int(cursor.rowcount)
        )

    finally:
        await db.close()


async def top_contributors(guild_id, limit=5):
    db = await _db()
    try:
        rows = await (await db.execute("SELECT username, amount FROM ship_contributions WHERE guild_id = ? ORDER BY amount DESC LIMIT ?", (guild_id, limit))).fetchall()
        return [(r["username"], int(r["amount"])) for r in rows]
    finally:
        await db.close()


async def repair_ship(guild_id):
    """
    Repair the Living Ship.

    Normal repair:
      - 25% of maximum hull
      - 25 sails

    Disabled emergency repair:
      - 35% of maximum hull
      - 25 sails
      - 50% higher repair cost

    Repair cost scales with Living Ship level.
    """

    async with get_guild_lock(guild_id):

        ship = await get_ship(guild_id)

        upgrades = await get_upgrade_levels(
            guild_id
        )

        max_hull = int(
            ship_caps(upgrades)["hull"]
        )

        current_hull = int(
            ship["hull"]
        )

        current_sails = int(
            ship["sails"]
        )

        level = max(
            1,
            int(ship["level"])
        )

        treasury = int(
            ship["treasury"]
        )

        if (
            current_hull >= max_hull
            and current_sails >= 100
        ):
            return (
                False,
                "The ship is already in fighting shape."
            )

        disabled = current_hull <= 0

        operational_threshold = operational_hull_threshold(
            max_hull
        )

        was_recovering = (
            current_hull < operational_threshold
        )

        # Base repair cost scales with ship level.
        cost = 100 + (
            (level - 1) * 25
        )

        # A completely disabled ship requires
        # a more expensive emergency repair.
        if disabled:
            cost = round(
                cost * 1.50
            )

        if treasury < cost:
            if disabled:
                return (
                    False,
                    "**EMERGENCY REPAIRS REQUIRED**\n"
                    "The ship is disabled at **0 hull**.\n"
                    "Emergency repairs cost **"
                    + str(cost)
                    + " doubloons** from the ship treasury."
                )

            return (
                False,
                "Repairs cost **"
                + str(cost)
                + " doubloons** from the ship treasury."
            )

        # Disabled ships receive a larger hull repair
        # so they can reasonably return to combat.
        hull_percent = (
            0.35
            if disabled
            else 0.25
        )

        hull_restore = max(
            1,
            int(
                (max_hull * hull_percent)
                + 0.999999
            )
        )

        # Do not report repair points that cannot
        # actually be applied.
        hull_restored = min(
            hull_restore,
            max_hull - current_hull
        )

        sails_restored = min(
            25,
            100 - current_sails
        )

        new_hull = min(
            max_hull,
            current_hull + hull_restored
        )

        new_sails = min(
            100,
            current_sails + sails_restored
        )

        db = await _db()

        try:
            became_operational = (
                was_recovering
                and new_hull >= operational_threshold
            )

            await db.execute(
                """
                UPDATE ships
                SET treasury = treasury - ?,
                    hull = ?,
                    sails = ?,
                    recovery_started_at = CASE
                        WHEN ? THEN NULL
                        ELSE recovery_started_at
                    END,
                    recovery_last_at = CASE
                        WHEN ? THEN NULL
                        ELSE recovery_last_at
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
                """,
                (
                    cost,
                    new_hull,
                    new_sails,
                    became_operational,
                    became_operational,
                    guild_id,
                )
            )

            await db.commit()

        finally:
            await db.close()

        if (
            was_recovering
            and new_hull >= operational_threshold
        ):
            await add_history(
                guild_id,
                (
                    "Paid repairs restored the Living Ship "
                    "to **operational status** at **"
                    + str(new_hull)
                    + "/"
                    + str(max_hull)
                    + " hull**."
                ),
                "ship_restored"
            )

        if disabled:
            title = "**EMERGENCY REPAIRS COMPLETE**"
        else:
            title = "**REPAIRS COMPLETE**"

        text = (
            title
            + "\n"
            "Hull: **"
            + str(current_hull)
            + " → "
            + str(new_hull)
            + "/"
            + str(max_hull)
            + "**"
        )

        if sails_restored > 0:
            text += (
                "\nSails: **"
                + str(current_sails)
                + " → "
                + str(new_sails)
                + "/100**"
            )

        text += (
            "\nTreasury: **-"
            + str(cost)
            + " doubloons**"
        )

        if disabled:
            text += (
                "\n\nThe Living Ship is seaworthy again "
                "and may return to combat."
            )

        await add_history(
            guild_id,
            text,
            "repair"
        )

        return True, text

async def buy_upgrade(guild_id, raw_key):
    key = raw_key.lower().strip().replace("crow's", "crows")

    async with get_guild_lock(guild_id):
        if key not in UPGRADES:
            return False, "Unknown upgrade. Use `!cutlass ship upgrades`."
        ship = await get_ship(guild_id)
        levels = await get_upgrade_levels(guild_id)
        current = levels.get(key, 0)
        info = UPGRADES[key]
        minimum_level = int(
            info.get(
                "min_level",
                1
            )
        )

        if int(ship["level"]) < minimum_level:
            return (
                False,
                (
                    "**UPGRADE LOCKED**\n"
                    + info["label"]
                    + " requires Living Ship **Level "
                    + str(minimum_level)
                    + "**.\n"
                    "Current ship level: **"
                    + str(ship["level"])
                    + "**."
                )
            )

        if current >= info["max_level"]:
            return False, f"**{info['label']}** is already max level."
        cost = info["cost"] * (current + 1)
        if ship["treasury"] < cost:
            return False, f"That upgrade costs **{cost} doubloons** from the ship treasury."
        new_level = current + 1
        db = await _db()
        try:
            await db.execute(
                "UPDATE ships SET treasury=treasury-?, updated_at=CURRENT_TIMESTAMP WHERE guild_id=?",
                (
                    cost,
                    guild_id
                )
            )

            await db.execute(
                """INSERT INTO ship_upgrades (guild_id, upgrade_key, level) VALUES (?, ?, ?)
                ON CONFLICT(guild_id, upgrade_key) DO UPDATE SET level=excluded.level""",
                (
                    guild_id,
                    key,
                    new_level
                )
            )
            if key == "reinforced hull":
                await db.execute("UPDATE ships SET hull=hull+20 WHERE guild_id=?", (guild_id,))
            elif key == "expanded hold":
                await db.execute("UPDATE ships SET supplies=supplies+25 WHERE guild_id=?", (guild_id,))
            elif key == "hardened keel":
                await db.execute("UPDATE ships SET hull=hull+35 WHERE guild_id=?", (guild_id,))
            elif key == "improved galley":
                await db.execute("UPDATE ships SET supplies=supplies+10 WHERE guild_id=?", (guild_id,))
            elif key == "crows nest":
                await db.execute("UPDATE ships SET morale=MIN(100, morale+5) WHERE guild_id=?", (guild_id,))
            await db.commit()
        finally:
            await db.close()

        text = (
            "**"
            + info["label"]
            + " "
            + str(new_level)
            + "** installed for **"
            + str(cost)
            + " doubloons**."
        )

        await add_history(guild_id, text, "upgrade")
        return True, text

async def get_available_destinations(guild_id):
    """
    Return charted voyage destinations for a guild.

    Blacktooth Cove is always known.
    Other destinations require discovery.

    Discovered destinations remain visible even when the
    Living Ship has not yet reached the required level.
    """

    ship = await get_ship(
        guild_id
    )

    ship_level = int(
        ship["level"]
    )

    db = await _db()

    try:
        rows = await (
            await db.execute(
                """
                SELECT location_key
                FROM world_discoveries
                WHERE guild_id = ?
                """,
                (guild_id,)
            )
        ).fetchall()

    finally:
        await db.close()

    discovered = {
        row["location_key"]
        for row in rows
    }

    available = []

    for key, info in DESTINATIONS.items():

        if (
            key == "blacktooth_cove"
            or key in discovered
        ):
            minimum_level = int(
                info.get(
                    "min_level",
                    1
                )
            )

            available.append(
                {
                    "key": key,
                    **info,
                    "unlocked": (
                        ship_level
                        >= minimum_level
                    ),
                    "ship_level": ship_level,
                }
            )

    return available


async def get_active_voyage(guild_id):
    db = await _db()
    try:
        row = await (await db.execute("SELECT * FROM ship_voyages WHERE guild_id=? AND status='active' ORDER BY id DESC LIMIT 1", (guild_id,))).fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def start_voyage(
    guild_id,
    destination_number
):
    async with get_guild_lock(guild_id):

        await ensure_ship(guild_id)

        if await get_active_voyage(guild_id):
            return (
                False,
                "The ship is already on a voyage."
            )

        destinations = await get_available_destinations(
            guild_id
        )

        try:
            destination_index = (
                int(destination_number)
                - 1
            )
        except (TypeError, ValueError):
            destination_index = -1

        if (
            destination_index < 0
            or destination_index >= len(destinations)
        ):
            return (
                False,
                "That voyage destination is not available. "
                "Use `!c destinations` to view currently charted routes."
            )

        info = destinations[
            destination_index
        ]

        ship = await get_ship(
            guild_id
        )

        minimum_level = int(
            info.get(
                "min_level",
                1
            )
        )

        if int(ship["level"]) < minimum_level:
            return (
                False,
                "**ROUTE LOCKED**\n"
                + info["name"]
                + " requires Living Ship **Level "
                + str(minimum_level)
                + "**.\n"
                "Current ship level: **"
                + str(ship["level"])
                + "**."
            )

        operational = await get_ship_operational_status(
            guild_id,
            ship=ship
        )

        if not operational["operational"]:
            return (
                False,
                "**SHIP DISABLED / RECOVERING**\n"
                "The Living Ship cannot begin a voyage until it reaches "
                "**"
                + str(operational["threshold"])
                + "/"
                + str(operational["max_hull"])
                + " hull**.\n"
                "Current hull: **"
                + str(operational["hull"])
                + "/"
                + str(operational["max_hull"])
                + "**.\n"
                "Needed to sail: **+"
                + str(operational["needed"])
                + " hull**.\n"
                "Passive recovery continues automatically, or use "
                "`!c repair` for faster paid repairs."
            )

        if ship["supplies"] < info["supplies"]:
            return (
                False,
                "Not enough supplies. This voyage needs **"
                + str(info["supplies"])
                + "**."
            )

        levels = await get_upgrade_levels(
            guild_id
        )

        improved_sails = levels.get(
            "improved sails",
            0
        )

        improved_galley = levels.get(
            "improved galley",
            0
        )

        crow_nest = levels.get(
            "crows nest",
            0
        )

        speed = (
            1.0
            - 0.05 * improved_sails
        )

        supply_discount = max(
            0.75,
            1.0 - 0.05 * improved_galley
        )

        reward_boost = (
            1.0
            + 0.05 * crow_nest
        )

        supply_cost = max(
            1,
            round(
                info["supplies"]
                * supply_discount
            )
        )

        reward_min = max(
            1,
            round(
                info["reward"][0]
                * reward_boost
            )
        )

        reward_max = max(
            reward_min,
            round(
                info["reward"][1]
                * reward_boost
            )
        )

        xp_reward = max(
            1,
            round(
                info["xp"]
                * (
                    1.0
                    + 0.05 * crow_nest
                )
            )
        )

        duration = timedelta(
            hours=(
                info["hours"]
                * max(
                    0.75,
                    speed
                )
            )
        )

        started = _now()
        completes = started + duration

        db = await _db()

        try:
            await db.execute(
                """
                UPDATE ships
                SET supplies = supplies - ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
                """,
                (
                    supply_cost,
                    guild_id,
                )
            )

            await db.execute(
                """
                INSERT INTO ship_voyages (
                    guild_id,
                    destination,
                    risk,
                    supplies_cost,
                    reward_min,
                    reward_max,
                    xp_reward,
                    distance,
                    started_at,
                    completes_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    guild_id,
                    info["name"],
                    info["risk"],
                    supply_cost,
                    reward_min,
                    reward_max,
                    xp_reward,
                    info["miles"],
                    _ts(started),
                    _ts(completes),
                )
            )

            await db.commit()

        finally:
            await db.close()

        await add_history(
            guild_id,
            (
            "Voyage begun for **"
            + info["name"]
            + "** ("
            + info["risk"]
            + " risk)."
            ),
            "voyage_start"
        )

        return (
            True,
            {
                **info,
                "supplies": supply_cost,
                "reward": (
                    reward_min,
                    reward_max
                ),
                "xp": xp_reward,
                "completes_at": _ts(
                    completes
                ),
            }
        )


async def resolve_due_voyages():
    db = await _db()
    try:
        rows = await (await db.execute("SELECT * FROM ship_voyages WHERE status='active' AND datetime(completes_at) <= datetime('now') ORDER BY id")).fetchall()
    finally:
        await db.close()
    results = []
    for row in rows:
        result = await resolve_voyage(int(row["id"]))
        if result:
            results.append(result)
    return results


async def resolve_voyage(voyage_id):

    # First discover which guild owns the voyage.
    db = await _db()

    try:
        initial = await (
            await db.execute(
                """
                SELECT guild_id
                FROM ship_voyages
                WHERE id = ?
                """,
                (voyage_id,)
            )
        ).fetchone()

    finally:
        await db.close()

    if not initial:
        return None

    guild_id = int(
        initial["guild_id"]
    )

    # Serialize the entire completion transaction for
    # this guild. Once the lock is acquired we MUST
    # re-read status='active' so another resolver cannot
    # pay the same voyage twice.
    async with get_guild_lock(guild_id):

        db = await _db()

        try:
            row = await (
                await db.execute(
                    """
                    SELECT *
                    FROM ship_voyages
                    WHERE id = ?
                      AND status = 'active'
                    """,
                    (voyage_id,)
                )
            ).fetchone()

            if not row:
                return None

            levels_rows = await (
                await db.execute(
                    """
                    SELECT upgrade_key, level
                    FROM ship_upgrades
                    WHERE guild_id = ?
                    """,
                    (guild_id,)
                )
            ).fetchall()

            levels = {
                r["upgrade_key"]: int(
                    r["level"]
                )
                for r in levels_rows
            }

            reward = random.randint(
                int(row["reward_min"]),
                int(row["reward_max"])
            )

            lookout_bonus = (
                levels.get(
                    "crows nest",
                    0
                )
                * 0.05
            )

            galley = levels.get(
                "improved galley",
                0
            )

            roll = random.random()

            risk = row["risk"]

            damage_chance = {
                "Low": .15,
                "Medium": .35,
                "Extreme": .60,
            }.get(
                risk,
                .25
            )

            damage_chance = max(
                .05,
                damage_chance
                - lookout_bonus
            )

            hull_damage = 0
            sails_damage = 0
            morale_change = 0

            event = (
                "Calm seas carried the crew "
                "safely to port."
            )

            if roll < damage_chance:

                base = {
                    "Low": (3, 8),
                    "Medium": (6, 15),
                    "Extreme": (12, 28),
                }.get(
                    risk,
                    (5, 12)
                )

                hull_damage = random.randint(
                    *base
                )

                sails_damage = random.randint(
                    max(
                        1,
                        base[0] - 2
                    ),
                    max(
                        2,
                        base[1] - 3
                    )
                )

                morale_change = -max(
                    1,
                    random.randint(
                        2,
                        8
                    )
                    - galley * 2
                )

                event = (
                    "Rough seas battered the ship "
                    "before landfall."
                )

            elif (
                random.random()
                < .25 + lookout_bonus
            ):

                bonus = random.randint(
                    25,
                    100
                )

                reward += bonus

                event = (
                    "The lookout spotted floating cargo "
                    "worth **"
                    + str(bonus)
                    + " extra doubloons**."
                )

            ship = await (
                await db.execute(
                    """
                    SELECT level, xp
                    FROM ships
                    WHERE guild_id = ?
                    """,
                    (guild_id,)
                )
            ).fetchone()

            level = int(
                ship["level"]
            )

            xp = (
                int(ship["xp"])
                + int(row["xp_reward"])
            )

            levels_gained = 0

            while xp >= xp_needed(level):
                xp -= xp_needed(level)
                level += 1
                levels_gained += 1

            await db.execute(
                """
                UPDATE ships
                SET treasury = treasury + ?,
                    hull = MAX(0, hull - ?),
                    sails = MAX(0, sails - ?),
                    morale = MAX(
                        0,
                        MIN(
                            100,
                            morale + ?
                        )
                    ),
                    xp = ?,
                    level = ?,
                    location = ?,
                    voyages_completed =
                        voyages_completed + 1,
                    distance_sailed =
                        distance_sailed + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
                """,
                (
                    reward,
                    hull_damage,
                    sails_damage,
                    morale_change,
                    xp,
                    level,
                    row["destination"],
                    int(row["distance"]),
                    guild_id,
                )
            )

            result_text = (
                "Arrived at **"
                + row["destination"]
                + "**. Treasury **+"
                + str(reward)
                + "**. XP **+"
                + str(row["xp_reward"])
                + "**. "
                + event
            )

            if hull_damage or sails_damage:
                result_text += (
                    " Hull **-"
                    + str(hull_damage)
                    + "**, Sails **-"
                    + str(sails_damage)
                    + "**."
                )

            if levels_gained:
                result_text += (
                    " Ship reached **Level "
                    + str(level)
                    + "**!"
                )

            await db.execute(
                """
                UPDATE ship_voyages
                SET status = 'completed',
                    result = ?,
                    completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                  AND status = 'active'
                """,
                (
                    result_text,
                    voyage_id,
                )
            )

            await db.execute(
                """
                INSERT INTO ship_history (
                    guild_id,
                    event_type,
                    content
                )
                VALUES (?, ?, ?)
                """,
                (
                    guild_id,
                    "voyage_complete",
                    result_text,
                )
            )

            await db.commit()

            return {
                "guild_id": guild_id,
                "destination": row[
                    "destination"
                ],
                "text": result_text,
            }

        finally:
            await db.close()



def discord_timestamp(timestamp_text):
    try:
        dt = datetime.strptime(
            timestamp_text,
            "%Y-%m-%d %H:%M:%S"
        )

        dt = dt.replace(
            tzinfo=timezone.utc
        )

        unix = int(
            dt.timestamp()
        )

        return (
            f"<t:{unix}:f> "
            f"(<t:{unix}:R>)"
        )

    except Exception:
        return timestamp_text + " UTC"


async def format_ship_status(guild_id):

    ship = await get_ship(
        guild_id
    )

    captured_held = await count_captured_ships(
        guild_id,
        status="held"
    )

    levels = await get_upgrade_levels(
        guild_id
    )

    caps = ship_caps(
        levels
    )

    voyage = await get_active_voyage(
        guild_id
    )

    max_hull = int(
        caps["hull"]
    )

    hull = int(
        ship["hull"]
    )

    threshold = operational_hull_threshold(
        max_hull
    )

    recovering = (
        hull < threshold
    )

    if recovering:
        status = "DISABLED / RECOVERING"
    elif voyage:
        status = "At Sea"
    else:
        status = "Anchored"

    lines = [
        f"**{ship['name']}**",
        f"Level: **{ship['level']}** | XP: **{ship['xp']}/{xp_needed(ship['level'])}**",
        f"Status: **{status}**",
        (
            f"Location: **En route to {voyage['destination']}**"
            if voyage
            else f"Location: **{ship['location']}**"
        ),
        "",
        f"Hull: **{hull}/{max_hull}**",
        f"Sails: **{ship['sails']}/100**",
        f"Supplies: **{ship['supplies']}/{caps['supplies']}**",
        f"Morale: **{ship['morale']}/100**",
        f"Treasury: **{ship['treasury']} doubloons**",
        f"Captured Ships: **{captured_held} held**",
    ]

    milestone = _ship_milestone(
        ship["level"]
    )

    if milestone:
        lines.extend([
            "",
            (
                "**SHIP MILESTONE REACHED** — "
                + milestone["label"]
            ),
            milestone["description"],
        ])
    else:
        next_level, next_milestone = _next_ship_milestone(
            ship["level"]
        )

        if next_milestone:
            lines.extend([
                "",
                (
                    "Next Milestone: Level "
                    + str(next_level)
                    + " — "
                    + next_milestone["label"]
                ),
            ])

    if recovering:

        remaining = max(
            0,
            threshold - hull
        )

        intervals_remaining = (
            remaining
            + PASSIVE_RECOVERY_HULL_PER_INTERVAL
            - 1
        ) // PASSIVE_RECOVERY_HULL_PER_INTERVAL

        seconds_remaining = (
            intervals_remaining
            * PASSIVE_RECOVERY_INTERVAL_SECONDS
        )

        hours, remainder = divmod(
            seconds_remaining,
            3600
        )

        minutes = (
            remainder // 60
        )

        if hours and minutes:
            eta_text = (
                f"{hours}h {minutes}m"
            )

        elif hours:
            eta_text = (
                f"{hours}h"
            )

        else:
            eta_text = (
                f"{minutes}m"
            )

        lines.extend([
            "",
            "**PASSIVE EMERGENCY RECOVERY**",
            (
                "Operational Hull: **"
                + str(threshold)
                + "/"
                + str(max_hull)
                + "**"
            ),
            (
                "Recovery Rate: **+"
                + str(
                    PASSIVE_RECOVERY_HULL_PER_INTERVAL
                )
                + " hull every "
                + str(
                    PASSIVE_RECOVERY_INTERVAL_SECONDS // 60
                )
                + " minutes**"
            ),
            (
                "Estimated Time Until Operational: **"
                + eta_text
                + "**"
            ),
            (
                "Passive recovery costs **0 doubloons**."
            ),
            (
                "Use `!c repair` for faster paid repairs."
            ),
        ])

    lines.extend([
        "",
        f"Voyages Completed: **{ship['voyages_completed']}**",
        f"Distance Sailed: **{ship['distance_sailed']} nautical miles**",
    ])

    if voyage:

        lines.extend([
            "",
            f"Current Voyage: **{voyage['destination']}**",
            (
                "Expected Completion: **"
                + discord_timestamp(
                    voyage["completes_at"]
                )
                + "**"
            )
        ])

    return "\n".join(
        lines
    )


async def format_destinations(guild_id):

    destinations = await get_available_destinations(
        guild_id
    )

    lines = [
        "**AVAILABLE VOYAGES**",
        "",
        "Only charted islands can be reached by voyage.",
    ]

    for number, destination in enumerate(
        destinations,
        start=1
    ):

        lines.extend([
            "",
            "**"
            + str(number)
            + ". "
            + destination["name"]
            + "**",

            "Risk: "
            + destination["risk"]
            + " | Duration: "
            + str(destination["hours"])
            + "h | Supplies: "
            + str(destination["supplies"]),

            (
                "Required Ship Level: "
                + str(
                    destination.get(
                        "min_level",
                        1
                    )
                )
                + (
                    " | **UNLOCKED**"
                    if destination["unlocked"]
                    else " | **LOCKED**"
                )
            ),

            "Reward: "
            + str(destination["reward"][0])
            + "-"
            + str(destination["reward"][1])
            + " doubloons | XP: "
            + str(destination["xp"]),
        ])

    lines.extend([
        "",
        "Use `!c voyage <number>` to set sail.",
        "Use `!c explore` to scout for new islands.",
    ])

    return "\n".join(
        lines
    )


async def format_upgrades(guild_id):
    levels = await get_upgrade_levels(guild_id)
    lines = ["**SHIP UPGRADES**"]
    for key, info in UPGRADES.items():
        level = levels.get(key, 0)
        min_level = int(
            info.get(
                "min_level",
                1
            )
        )

        if level >= info["max_level"]:
            cost = "MAX"
        else:
            cost = f"{info['cost'] * (level + 1)} doubloons"

        if level == 0 and min_level > 1:
            unlock = f"Unlocks at ship level {min_level}"
        else:
            unlock = f"Unlocks at ship level {min_level}"

        lines.extend([
            (
                "- **"
                + info["label"]
                + "** "
                + str(level)
                + "/"
                + str(info["max_level"])
                + " - "
                + cost
            ),
            "  " + unlock,
            "  " + info.get("bonus", ""),
        ])

    lines += ["", "Use `!cutlass ship upgrade <name>`." ]
    return "\n".join(lines)


# =========================================================
# Living Ship Combat API
# =========================================================

async def _damage_ship_unlocked(guild_id, amount):
    """
    Apply real combat damage to the Living Ship.

    Hull can never fall below zero.

    When damage reduces the ship to zero hull, passive
    recovery begins automatically.
    """

    await ensure_ship(guild_id)

    amount = max(
        0,
        int(amount)
    )

    db = await _db()

    became_disabled = False

    try:

        row = await (
            await db.execute(
                """
                SELECT hull
                FROM ships
                WHERE guild_id = ?
                """,
                (guild_id,)
            )
        ).fetchone()

        old_hull = max(
            0,
            int(row["hull"])
        )

        new_hull = max(
            0,
            old_hull - amount
        )

        became_disabled = (
            old_hull > 0
            and new_hull <= 0
        )

        if became_disabled:

            now_text = _ts()

            await db.execute(
                """
                UPDATE ships
                SET hull = 0,
                    recovery_started_at = ?,
                    recovery_last_at = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
                """,
                (
                    now_text,
                    now_text,
                    guild_id,
                )
            )

        else:

            await db.execute(
                """
                UPDATE ships
                SET hull = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
                """,
                (
                    new_hull,
                    guild_id,
                )
            )

        await db.commit()

    finally:
        await db.close()

    if became_disabled:

        await add_history(
            guild_id,
            (
                "The Living Ship was **DISABLED** at "
                "**0 hull**. Emergency passive repairs "
                "have begun."
            ),
            "ship_disabled"
        )

    return await get_ship(
        guild_id
    )

async def damage_ship(guild_id, amount):
    """
    Apply serialized combat damage to the Living Ship.

    The complete hull read/modify/write operation is
    protected by the shared guild Ship World lock.
    """
    async with get_guild_lock(guild_id):
        return await _damage_ship_unlocked(
            guild_id,
            amount
        )




async def _reward_ship_unlocked(
    guild_id,
    doubloons=0,
    xp_reward=0,
    achievement_user_id=None
):
    """
    Award the Living Ship treasury and XP.

    Handles multiple level-ups automatically.
    Returns reward and updated ship information.
    """

    await ensure_ship(guild_id)

    doubloons = max(0, int(doubloons))
    xp_reward = max(0, int(xp_reward))

    db = await _db()

    milestones = []

    try:
        row = await (
            await db.execute(
                """
                SELECT level, xp
                FROM ships
                WHERE guild_id = ?
                """,
                (guild_id,)
            )
        ).fetchone()

        level = int(row["level"])
        xp = int(row["xp"]) + xp_reward
        starting_level = level

        levels_gained = 0

        while xp >= xp_needed(level):
            xp -= xp_needed(level)
            level += 1
            levels_gained += 1

        for milestone_level in sorted(
            SHIP_LEVEL_MILESTONES
        ):
            if starting_level < milestone_level <= level:
                milestone = dict(
                    SHIP_LEVEL_MILESTONES[
                        milestone_level
                    ]
                )
                milestone["level"] = milestone_level
                milestones.append(
                    milestone
                )

        await db.execute(
            """
            UPDATE ships
            SET treasury = treasury + ?,
                xp = ?,
                level = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
            """,
            (
                doubloons,
                xp,
                level,
                guild_id
            )
        )

        await db.commit()

    finally:
        await db.close()

    ship = await get_ship(guild_id)

    milestone_lines = []

    for milestone in milestones:
        milestone_lines.append(
            (
                "Reached ship milestone **Level "
                + str(milestone["level"])
                + " — "
                + milestone["label"]
                + "**."
            )
        )

        await add_history(
            guild_id,
            (
                "Living Ship milestone reached: "
                + milestone["label"]
                + " (Level "
                + str(milestone["level"])
                + "). "
                + milestone["description"]
            ),
            "milestone"
        )

        await _award_achievement_if_possible(
            guild_id,
            achievement_user_id,
            milestone["achievement"],
            milestone["description"]
        )

    milestone_text = (
        "\n".join(milestone_lines)
        if milestone_lines
        else ""
    )

    return {
        "doubloons": doubloons,
        "xp": xp_reward,
        "levels_gained": levels_gained,
        "level": level,
        "ship": ship,
        "milestones": milestones,
        "milestone_text": milestone_text,
    }



async def reward_ship(
    guild_id,
    doubloons=0,
    xp_reward=0,
    achievement_user_id=None
):
    async with get_guild_lock(guild_id):
        return await _reward_ship_unlocked(
            guild_id,
            doubloons=doubloons,
            xp_reward=xp_reward,
            achievement_user_id=achievement_user_id
        )




async def ensure_ship_combat_abilities(
    guild_id
):

    await ensure_ship(
        guild_id
    )

    db = await _db()

    try:

        for ability_key in SHIP_COMBAT_ABILITIES:

            await db.execute(
                """
                INSERT OR IGNORE INTO ship_combat_abilities (
                    guild_id,
                    ability_key
                )
                VALUES (?, ?)
                """,
                (
                    guild_id,
                    ability_key,
                )
            )

        await db.commit()

    finally:
        await db.close()


async def get_ship_combat_abilities(
    guild_id
):

    await ensure_ship_combat_abilities(
        guild_id
    )

    db = await _db()

    try:

        rows = await (
            await db.execute(
                """
                SELECT
                    ability_key,
                    cooldown_turns,
                    active,
                    activated_by
                FROM ship_combat_abilities
                WHERE guild_id = ?
                """,
                (
                    guild_id,
                )
            )
        ).fetchall()

        result = {}

        for row in rows:

            key = row["ability_key"]

            if key not in SHIP_COMBAT_ABILITIES:
                continue

            result[key] = {
                "key": key,
                "name": (
                    SHIP_COMBAT_ABILITIES[
                        key
                    ]["name"]
                ),
                "cooldown_turns": max(
                    0,
                    int(
                        row[
                            "cooldown_turns"
                        ]
                    )
                ),
                "active": bool(
                    row["active"]
                ),
                "activated_by": int(
                    row["activated_by"]
                    or 0
                ),
            }

        return result

    finally:
        await db.close()


async def activate_ship_combat_ability(
    guild_id,
    raw_name,
    *,
    user_id=0,
):

    key = normalize_ship_ability(
        raw_name
    )

    if not key:

        return (
            False,
            "Unknown ship combat ability.",
            None,
        )

    await ensure_ship_combat_abilities(
        guild_id
    )

    info = SHIP_COMBAT_ABILITIES[
        key
    ]

    db = await _db()

    try:

        row = await (
            await db.execute(
                """
                SELECT
                    cooldown_turns,
                    active
                FROM ship_combat_abilities
                WHERE guild_id = ?
                  AND ability_key = ?
                """,
                (
                    guild_id,
                    key,
                )
            )
        ).fetchone()

        cooldown = max(
            0,
            int(
                row["cooldown_turns"]
            )
        )

        active = bool(
            row["active"]
        )

        if active:

            return (
                False,
                "**"
                + info["name"]
                + "** is already active.",
                None,
            )

        if cooldown > 0:

            return (
                False,
                "**"
                + info["name"]
                + "** is on cooldown for **"
                + str(cooldown)
                + " more combat turn"
                + (
                    ""
                    if cooldown == 1
                    else "s"
                )
                + "**.",
                None,
            )

        cursor = await db.execute(
            """
            UPDATE ship_combat_abilities
            SET active = 1,
                cooldown_turns = ?,
                activated_by = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
              AND ability_key = ?
              AND active = 0
              AND cooldown_turns = 0
            """,
            (
                int(
                    info["cooldown"]
                ),
                int(user_id or 0),
                guild_id,
                key,
            )
        )

        if cursor.rowcount != 1:

            await db.rollback()

            return (
                False,
                "That ability is no longer available.",
                None,
            )

        await db.commit()

        return (
            True,
            "**"
            + info["name"].upper()
            + "**\n"
            + info["description"],
            {
                "key": key,
                "name": info["name"],
                "cooldown": int(
                    info["cooldown"]
                ),
            },
        )

    finally:
        await db.close()



async def activate_emergency_repairs(
    guild_id,
    *,
    user_id=0,
):

    await ensure_ship_combat_abilities(
        guild_id
    )

    operational = await get_ship_operational_status(
        guild_id,
        ship=ship
    )

    if not operational["operational"]:

        return (
            False,
            "**Emergency Repairs** cannot revive a disabled ship.",
            None,
        )

    db = await _db()

    try:

        row = await (
            await db.execute(
                """
                SELECT cooldown_turns
                FROM ship_combat_abilities
                WHERE guild_id = ?
                  AND ability_key = 'repairs'
                """,
                (
                    guild_id,
                )
            )
        ).fetchone()

        cooldown = max(
            0,
            int(
                row["cooldown_turns"]
            )
        )

        if cooldown > 0:

            return (
                False,
                "**Emergency Repairs** is on cooldown for **"
                + str(cooldown)
                + " more combat turn"
                + (
                    ""
                    if cooldown == 1
                    else "s"
                )
                + "**.",
                None,
            )

        ship = await (
            await db.execute(
                """
                SELECT hull
                FROM ships
                WHERE guild_id = ?
                """,
                (
                    guild_id,
                )
            )
        ).fetchone()

        if not ship:

            return (
                False,
                "The Living Ship could not be found.",
                None,
            )

        old_hull = max(
            0,
            int(ship["hull"])
        )

        upgrades = await get_upgrade_levels(
            guild_id
        )

        max_hull = max(
            1,
            int(
                ship_caps(
                    upgrades
                )["hull"]
            )
        )

        if old_hull >= max_hull:

            return (
                False,
                "**Emergency Repairs** are not needed; "
                "the hull is already at full strength.",
                None,
            )

        repair_amount = max(
            1,
            round(
                max_hull * 0.10
            )
        )

        new_hull = min(
            max_hull,
            old_hull + repair_amount
        )

        actual_repair = (
            new_hull - old_hull
        )

        cursor = await db.execute(
            """
            UPDATE ship_combat_abilities
            SET active = 0,
                cooldown_turns = ?,
                activated_by = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
              AND ability_key = 'repairs'
              AND active = 0
              AND cooldown_turns = 0
            """,
            (
                int(
                    SHIP_COMBAT_ABILITIES[
                        "repairs"
                    ]["cooldown"]
                ),
                int(user_id or 0),
                guild_id,
            )
        )

        if cursor.rowcount != 1:

            await db.rollback()

            return (
                False,
                "Emergency Repairs are no longer available.",
                None,
            )

        await db.execute(
            """
            UPDATE ships
            SET hull = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
            """,
            (
                new_hull,
                guild_id,
            )
        )

        await db.commit()

        return (
            True,
            "**EMERGENCY REPAIRS**\n"
            "Damage-control crews restore **"
            + str(actual_repair)
            + " hull**.\n"
            "Hull: **"
            + str(new_hull)
            + "/"
            + str(max_hull)
            + "**.",
            {
                "key": "repairs",
                "name": "Emergency Repairs",
                "repaired": actual_repair,
                "old_hull": old_hull,
                "new_hull": new_hull,
                "max_hull": max_hull,
                "cooldown": int(
                    SHIP_COMBAT_ABILITIES[
                        "repairs"
                    ]["cooldown"]
                ),
            },
        )

    finally:
        await db.close()


async def consume_ship_combat_effects(
    guild_id,
    *,
    outgoing=False,
    incoming=False,
):

    await ensure_ship_combat_abilities(
        guild_id
    )

    db = await _db()

    consumed = {
        "broadside": False,
        "brace": False,
        "rally_outgoing": False,
        "rally_incoming": False,
    }

    try:

        rows = await (
            await db.execute(
                """
                SELECT
                    ability_key,
                    active
                FROM ship_combat_abilities
                WHERE guild_id = ?
                """,
                (
                    guild_id,
                )
            )
        ).fetchall()

        active = {
            row["ability_key"]:
                bool(row["active"])
            for row in rows
        }

        if (
            outgoing
            and active.get(
                "broadside",
                False
            )
        ):

            cursor = await db.execute(
                """
                UPDATE ship_combat_abilities
                SET active = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
                  AND ability_key = 'broadside'
                  AND active = 1
                """,
                (
                    guild_id,
                )
            )

            consumed["broadside"] = (
                cursor.rowcount == 1
            )

        if (
            incoming
            and active.get(
                "brace",
                False
            )
        ):

            cursor = await db.execute(
                """
                UPDATE ship_combat_abilities
                SET active = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
                  AND ability_key = 'brace'
                  AND active = 1
                """,
                (
                    guild_id,
                )
            )

            consumed["brace"] = (
                cursor.rowcount == 1
            )

        if active.get(
            "rally",
            False
        ):

            # Rally is consumed by the first combat exchange
            # that requests either side of the effect.
            if outgoing or incoming:

                cursor = await db.execute(
                    """
                    UPDATE ship_combat_abilities
                    SET active = 0,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE guild_id = ?
                      AND ability_key = 'rally'
                      AND active = 1
                    """,
                    (
                        guild_id,
                    )
                )

                if cursor.rowcount == 1:

                    consumed[
                        "rally_outgoing"
                    ] = bool(outgoing)

                    consumed[
                        "rally_incoming"
                    ] = bool(incoming)

        await db.commit()

        return consumed

    finally:
        await db.close()


async def consume_ship_combat_ability(
    guild_id,
    raw_name,
):
    """
    Consume exactly one armed ship combat ability.

    Cooldown is intentionally preserved.
    """

    ability_key = normalize_ship_ability(
        raw_name
    )

    if not ability_key:
        return False

    db = await _db()

    try:

        cursor = await db.execute(
            """
            UPDATE ship_combat_abilities
            SET
                active = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
              AND ability_key = ?
              AND active = 1
            """,
            (
                guild_id,
                ability_key,
            )
        )

        changed = (
            cursor.rowcount == 1
        )

        await db.commit()

        return changed

    finally:
        await db.close()


async def advance_ship_ability_cooldowns(
    guild_id
):

    await ensure_ship_combat_abilities(
        guild_id
    )

    db = await _db()

    try:

        await db.execute(
            """
            UPDATE ship_combat_abilities
            SET cooldown_turns =
                CASE
                    WHEN cooldown_turns > 0
                    THEN cooldown_turns - 1
                    ELSE 0
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
              AND active = 0
              AND cooldown_turns > 0
            """,
            (
                guild_id,
            )
        )

        await db.commit()

    finally:
        await db.close()

    return await get_ship_combat_abilities(
        guild_id
    )


async def clear_ship_combat_effects(
    guild_id
):

    await ensure_ship_combat_abilities(
        guild_id
    )

    db = await _db()

    try:

        await db.execute(
            """
            UPDATE ship_combat_abilities
            SET active = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
            """,
            (
                guild_id,
            )
        )

        await db.commit()

    finally:
        await db.close()


async def combat_ship_status(guild_id):
    """
    Return combat-relevant Living Ship information.
    """

    ship = await get_ship(guild_id)
    upgrades = await get_upgrade_levels(guild_id)
    caps = ship_caps(upgrades)

    return {
        "name": ship["name"],
        "hull": int(ship["hull"]),
        "max_hull": int(caps["hull"]),
        "sails": int(ship["sails"]),
        "morale": int(ship["morale"]),
        "treasury": int(ship["treasury"]),
        "level": int(ship["level"]),
        "xp": int(ship["xp"]),
        "xp_needed": xp_needed(
            int(ship["level"])
        ),
        "disabled": (
            int(ship["hull"])
            < operational_hull_threshold(
                int(caps["hull"])
            )
        ),
        "operational_threshold": operational_hull_threshold(
            int(caps["hull"])
        ),
        "recovering": (
            int(ship["hull"])
            < operational_hull_threshold(
                int(caps["hull"])
            )
        ),
    }


async def apply_exploration_outcome(
    guild_id,
    *,
    hull_damage=0,
    sails_damage=0,
    supplies_change=0,
    morale_change=0,
    treasury_gain=0
):
    """
    Atomically apply a deterministic exploration outcome to
    the Living Ship.

    Positive hull_damage and sails_damage values represent
    damage. supplies_change and morale_change may be positive
    or negative. treasury_gain may only increase treasury.

    The entire ship-state mutation is serialized through the
    shared per-guild Ship World lock.
    """

    async with get_guild_lock(guild_id):

        await ensure_ship(guild_id)

        # Apply any passive recovery before calculating the
        # environmental outcome against current ship state.
        await _apply_passive_recovery_unlocked(
            guild_id
        )

        upgrades = await get_upgrade_levels(
            guild_id
        )

        caps = ship_caps(upgrades)

        max_supplies = int(
            caps["supplies"]
        )

        hull_damage = max(
            0,
            int(hull_damage)
        )

        sails_damage = max(
            0,
            int(sails_damage)
        )

        supplies_change = int(
            supplies_change
        )

        morale_change = int(
            morale_change
        )

        treasury_gain = max(
            0,
            int(treasury_gain)
        )

        db = await _db()

        try:

            row = await (
                await db.execute(
                    """
                    SELECT
                        hull,
                        sails,
                        supplies,
                        morale,
                        treasury
                    FROM ships
                    WHERE guild_id = ?
                    """,
                    (guild_id,)
                )
            ).fetchone()

            if row is None:
                raise RuntimeError(
                    "Living Ship state is unavailable."
                )

            old_hull = int(
                row["hull"]
            )

            old_sails = int(
                row["sails"]
            )

            old_supplies = int(
                row["supplies"]
            )

            old_morale = int(
                row["morale"]
            )

            old_treasury = int(
                row["treasury"]
            )

            new_hull = max(
                0,
                old_hull - hull_damage
            )

            new_sails = max(
                0,
                old_sails - sails_damage
            )

            new_supplies = max(
                0,
                min(
                    max_supplies,
                    old_supplies
                    + supplies_change
                )
            )

            new_morale = max(
                0,
                min(
                    100,
                    old_morale
                    + morale_change
                )
            )

            new_treasury = (
                old_treasury
                + treasury_gain
            )

            actual_hull_damage = (
                old_hull - new_hull
            )

            actual_sails_damage = (
                old_sails - new_sails
            )

            actual_supplies_change = (
                new_supplies
                - old_supplies
            )

            actual_morale_change = (
                new_morale
                - old_morale
            )

            actual_treasury_gain = (
                new_treasury
                - old_treasury
            )

            became_disabled = (
                old_hull > 0
                and new_hull <= 0
            )

            if became_disabled:

                now_text = _ts()

                recovery_started_at = (
                    now_text
                )

                recovery_last_at = (
                    now_text
                )

            else:

                recovery_started_at = None
                recovery_last_at = None

            await db.execute(
                """
                UPDATE ships
                SET hull = ?,
                    sails = ?,
                    supplies = ?,
                    morale = ?,
                    treasury = ?,
                    recovery_started_at = CASE
                        WHEN ? THEN ?
                        ELSE recovery_started_at
                    END,
                    recovery_last_at = CASE
                        WHEN ? THEN ?
                        ELSE recovery_last_at
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
                """,
                (
                    new_hull,
                    new_sails,
                    new_supplies,
                    new_morale,
                    new_treasury,
                    became_disabled,
                    recovery_started_at,
                    became_disabled,
                    recovery_last_at,
                    guild_id,
                )
            )

            await db.commit()

        finally:
            await db.close()

        if became_disabled:

            await add_history(
                guild_id,
                (
                    "The Living Ship was **DISABLED** "
                    "during exploration at **0 hull**. "
                    "Emergency passive repairs have begun."
                ),
                "ship_disabled"
            )

        return {
            "old": {
                "hull": old_hull,
                "sails": old_sails,
                "supplies": old_supplies,
                "morale": old_morale,
                "treasury": old_treasury,
            },
            "new": {
                "hull": new_hull,
                "sails": new_sails,
                "supplies": new_supplies,
                "morale": new_morale,
                "treasury": new_treasury,
            },
            "applied": {
                "hull_damage":
                    actual_hull_damage,
                "sails_damage":
                    actual_sails_damage,
                "supplies_change":
                    actual_supplies_change,
                "morale_change":
                    actual_morale_change,
                "treasury_gain":
                    actual_treasury_gain,
            },
            "became_disabled":
                became_disabled,
        }


async def add_ship_treasury(
    guild_id,
    amount
):
    await ensure_ship(guild_id)

    amount = max(0, int(amount))

    db = await _db()

    try:
        await db.execute(
            """
            UPDATE ships
            SET treasury = treasury + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
            """,
            (amount, guild_id)
        )

        await db.commit()

    finally:
        await db.close()

    return await get_ship(guild_id)


async def add_ship_supplies(
    guild_id,
    amount
):
    await ensure_ship(guild_id)

    amount = max(0, int(amount))

    upgrades = await get_upgrade_levels(
        guild_id
    )

    max_supplies = ship_caps(
        upgrades
    )["supplies"]

    db = await _db()

    try:
        await db.execute(
            """
            UPDATE ships
            SET supplies = MIN(?, supplies + ?),
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
            """,
            (
                max_supplies,
                amount,
                guild_id
            )
        )

        await db.commit()

    finally:
        await db.close()

    return await get_ship(guild_id)
