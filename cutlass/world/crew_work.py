import asyncio
import os
import random
from datetime import datetime, timedelta, timezone

import aiosqlite

from cutlass.world.locks import get_guild_lock
from cutlass.world.pirate_world import (
    count_hidden_discoveries,
    count_world_discoveries,
)
from memory import (
    add_doubloons,
    award_achievement,
    get_achievements,
    get_doubloons,
)
from ship_world import (
    _apply_passive_recovery_unlocked,
    add_history,
    add_ship_supplies,
    add_ship_treasury,
    count_captured_ships,
    discord_timestamp,
    get_ship,
    get_ship_operational_status,
    get_upgrade_levels,
    operational_hull_threshold,
    ship_caps,
)

DB_PATH = os.getenv("DATABASE_PATH", "/app/data/captain.db")

WORK_ACHIEVEMENTS = {
    1: ("First Shift", "Completed yer first crew job."),
    5: ("Hard Worker", "Completed five crew jobs."),
    10: ("Veteran Hand", "Completed ten crew jobs."),
    25: ("Seasoned Crew", "Completed twenty-five crew jobs."),
}

REPAIR_ACTION_ACHIEVEMENTS = {
    1: ("First Repair Hand", "Completed yer first maintenance shift."),
    5: ("Hull Crew", "Completed five maintenance shifts."),
    15: ("Dockyard Veteran", "Completed fifteen maintenance shifts."),
    30: ("Battle Yard Master", "Completed thirty maintenance shifts."),
}

REPAIR_HULL_ACHIEVEMENTS = {
    25: ("Patch and Plank", "Restored twenty-five hull through crew maintenance."),
    100: ("Fleet Fixer", "Restored one hundred hull through crew maintenance."),
    250: ("Emergency Yardmaster", "Restored two hundred fifty hull through crew maintenance."),
}

REPAIR_RESTORE_ACHIEVEMENT = (
    "Back in Fighting Shape",
    "Helped restore the Living Ship to operational status.",
)

REPAIR_RARE_ACHIEVEMENT = (
    "Miracle Fixer",
    "Pulled off a rare maintenance recovery.",
)

GENERAL_JOBS = {
    "dockhand": {
        "kind": "crew",
        "label": "Dockside Hands",
        "aliases": {
            "dockhand",
            "dockhands",
            "dockside",
            "dockside hands",
            "dock work",
            "harbor hand",
        },
        "description": "Haul crates, scrub tar, and keep the harbor crew moving.",
        "risk": "Low",
        "cooldown_minutes": 20,
        "base_payout": (16, 28),
        "success_chance": 80,
        "bonus_chance": 15,
        "rare_chance": 5,
        "min_level": 1,
        "min_world_discoveries": 0,
        "min_hidden_discoveries": 0,
        "required_achievements": [],
        "required_captures": 0,
        "ship_bonus_type": "supplies",
        "ship_bonus_range": (3, 7),
        "ship_bonus_label": "supplies",
        "job_achievement": "Dockside Hand",
        "job_achievement_description": "Completed dockside crew work.",
        "rare_achievement": "Dockside Legend",
        "rare_achievement_description": "Pulled off a rare dockside crew-work result.",
        "unlock_text": "Available from the start.",
    },
    "salvager": {
        "kind": "crew",
        "label": "Salvager",
        "aliases": {
            "salvager",
            "salvage",
            "salvage crew",
            "wreck salvager",
        },
        "description": "Break apart wreckage, sort useful timber, and reclaim cargo.",
        "risk": "Medium",
        "cooldown_minutes": 30,
        "base_payout": (22, 38),
        "success_chance": 76,
        "bonus_chance": 16,
        "rare_chance": 8,
        "min_level": 2,
        "min_world_discoveries": 0,
        "min_hidden_discoveries": 1,
        "required_achievements": [],
        "required_captures": 0,
        "ship_bonus_type": "supplies",
        "ship_bonus_range": (5, 10),
        "ship_bonus_label": "supplies",
        "job_achievement": "Ship Salvager",
        "job_achievement_description": "Completed salvage work.",
        "rare_achievement": "Salvage Expert",
        "rare_achievement_description": "Pulled off a rare salvage operation.",
        "unlock_text": "Requires one hidden discovery or ship level 2.",
    },
    "shipwright": {
        "kind": "crew",
        "label": "Shipwright",
        "aliases": {
            "shipwright",
            "shipwright assistant",
            "hull repair",
            "yardhand",
        },
        "description": "Hand timber to the shipwright and keep the drydock busy.",
        "risk": "Medium",
        "cooldown_minutes": 40,
        "base_payout": (26, 44),
        "success_chance": 72,
        "bonus_chance": 18,
        "rare_chance": 10,
        "min_level": 3,
        "min_world_discoveries": 0,
        "min_hidden_discoveries": 0,
        "required_achievements": [],
        "required_captures": 0,
        "ship_bonus_type": "treasury",
        "ship_bonus_range": (8, 14),
        "ship_bonus_label": "treasury",
        "job_achievement": "Shipwright's Mate",
        "job_achievement_description": "Completed shipwright work.",
        "rare_achievement": "Hull Whisperer",
        "rare_achievement_description": "Pulled off a rare shipwright operation.",
        "unlock_text": "Requires ship level 3.",
    },
    "merchant": {
        "kind": "crew",
        "label": "Merchant Runner",
        "aliases": {
            "merchant",
            "merchant runner",
            "trade runner",
            "smuggler",
        },
        "description": "Run cargo, bargain with traders, and keep the ledgers straight.",
        "risk": "High",
        "cooldown_minutes": 50,
        "base_payout": (30, 52),
        "success_chance": 70,
        "bonus_chance": 20,
        "rare_chance": 10,
        "min_level": 2,
        "min_world_discoveries": 2,
        "min_hidden_discoveries": 0,
        "required_achievements": [],
        "required_captures": 0,
        "ship_bonus_type": "treasury",
        "ship_bonus_range": (10, 18),
        "ship_bonus_label": "treasury",
        "job_achievement": "Trade Runner",
        "job_achievement_description": "Completed merchant work.",
        "rare_achievement": "Golden Ledger",
        "rare_achievement_description": "Pulled off a rare merchant run.",
        "unlock_text": "Requires two discovered islands and ship level 2.",
    },
    "bounty hunter": {
        "kind": "crew",
        "label": "Bounty Hunter",
        "aliases": {
            "bounty hunter",
            "hunter",
            "bounty",
            "prize hunter",
        },
        "description": "Chase warrants, collect prizes, and come back with proof.",
        "risk": "Extreme",
        "cooldown_minutes": 70,
        "base_payout": (36, 60),
        "success_chance": 64,
        "bonus_chance": 22,
        "rare_chance": 14,
        "min_level": 3,
        "min_world_discoveries": 0,
        "min_hidden_discoveries": 0,
        "required_achievements": ["Prize of War"],
        "required_captures": 0,
        "ship_bonus_type": "treasury",
        "ship_bonus_range": (12, 22),
        "ship_bonus_label": "treasury",
        "job_achievement": "Prize Hunter",
        "job_achievement_description": "Completed bounty hunter work.",
        "rare_achievement": "Wanted Poster",
        "rare_achievement_description": "Pulled off a rare bounty hunter job.",
        "unlock_text": "Requires Prize of War and ship level 3.",
    },
}

MAINTENANCE_JOBS = {
    "patch the hull": {
        "kind": "maintenance",
        "label": "Patch the Hull",
        "aliases": {
            "patch the hull",
            "patch hull",
            "hull patch",
            "plank patch",
        },
        "description": "Caulk seams, replace planks, and seal leaks while the ship recovers.",
        "risk": "Low",
        "cooldown_minutes": 18,
        "base_payout": (12, 20),
        "repair_points": (2, 4),
        "success_chance": 84,
        "bonus_chance": 11,
        "rare_chance": 5,
        "min_level": 1,
        "min_world_discoveries": 0,
        "min_hidden_discoveries": 0,
        "required_achievements": [],
        "required_captures": 0,
        "requires_recovery": True,
        "requires_disabled": False,
        "ship_bonus_type": "supplies",
        "ship_bonus_range": (2, 5),
        "ship_bonus_label": "supplies",
        "job_achievement": "Hull Patcher",
        "job_achievement_description": "Helped patch the Living Ship's hull.",
        "rare_achievement": "Seam Surgeon",
        "rare_achievement_description": "Pulled off a rare hull patching shift.",
        "unlock_text": "Available while the ship is recovering.",
    },
    "salvage lumber": {
        "kind": "maintenance",
        "label": "Salvage Lumber",
        "aliases": {
            "salvage lumber",
            "lumber salvage",
            "wood salvage",
            "timber salvage",
        },
        "description": "Drag in usable timber and keep the repair pile fed.",
        "risk": "Medium",
        "cooldown_minutes": 22,
        "base_payout": (14, 24),
        "repair_points": (3, 5),
        "success_chance": 80,
        "bonus_chance": 12,
        "rare_chance": 8,
        "min_level": 1,
        "min_world_discoveries": 1,
        "min_hidden_discoveries": 0,
        "required_achievements": [],
        "required_captures": 0,
        "requires_recovery": True,
        "requires_disabled": False,
        "ship_bonus_type": "supplies",
        "ship_bonus_range": (3, 6),
        "ship_bonus_label": "supplies",
        "job_achievement": "Timber Runner",
        "job_achievement_description": "Helped salvage lumber for repairs.",
        "rare_achievement": "Lucky Saw",
        "rare_achievement_description": "Pulled off a rare lumber salvage shift.",
        "unlock_text": "Requires one discovered island.",
    },
    "dockyard assistance": {
        "kind": "maintenance",
        "label": "Dockyard Assistance",
        "aliases": {
            "dockyard assistance",
            "dockyard help",
            "dock assistance",
            "yard assistance",
        },
        "description": "Lend hands to the dock crew and keep the yard moving.",
        "risk": "Medium",
        "cooldown_minutes": 26,
        "base_payout": (16, 28),
        "repair_points": (3, 5),
        "success_chance": 78,
        "bonus_chance": 14,
        "rare_chance": 8,
        "min_level": 1,
        "min_world_discoveries": 0,
        "min_hidden_discoveries": 0,
        "required_achievements": [],
        "required_captures": 0,
        "requires_recovery": True,
        "requires_disabled": False,
        "ship_bonus_type": "treasury",
        "ship_bonus_range": (4, 8),
        "ship_bonus_label": "treasury",
        "job_achievement": "Yard Hand",
        "job_achievement_description": "Helped in the dockyard during recovery.",
        "rare_achievement": "Dockmaster's Favor",
        "rare_achievement_description": "Pulled off a rare dockyard assistance shift.",
        "unlock_text": "Available while the ship is recovering.",
    },
    "clear the bilge": {
        "kind": "maintenance",
        "label": "Clear the Bilge",
        "aliases": {
            "clear the bilge",
            "bilge clearing",
            "clear bilge",
        },
        "description": "Pump out the foul water and keep the hull breathing again.",
        "risk": "Low",
        "cooldown_minutes": 18,
        "base_payout": (12, 22),
        "repair_points": (2, 4),
        "success_chance": 86,
        "bonus_chance": 9,
        "rare_chance": 5,
        "min_level": 1,
        "min_world_discoveries": 0,
        "min_hidden_discoveries": 0,
        "required_achievements": [],
        "required_captures": 0,
        "requires_recovery": True,
        "requires_disabled": False,
        "ship_bonus_type": "supplies",
        "ship_bonus_range": (1, 4),
        "ship_bonus_label": "supplies",
        "job_achievement": "Bilge Cleaner",
        "job_achievement_description": "Kept the bilge clear during repairs.",
        "rare_achievement": "Dry Decks",
        "rare_achievement_description": "Pulled off a rare bilge cleaning shift.",
        "unlock_text": "Available while the ship is recovering.",
    },
    "help the shipwright": {
        "kind": "maintenance",
        "label": "Help the Shipwright",
        "aliases": {
            "help the shipwright",
            "shipwright help",
            "help shipwright",
        },
        "description": "Hold timbers, fetch tools, and keep the master repairer supplied.",
        "risk": "Medium",
        "cooldown_minutes": 30,
        "base_payout": (18, 30),
        "repair_points": (4, 6),
        "success_chance": 76,
        "bonus_chance": 14,
        "rare_chance": 10,
        "min_level": 2,
        "min_world_discoveries": 0,
        "min_hidden_discoveries": 0,
        "required_achievements": [],
        "required_captures": 0,
        "requires_recovery": True,
        "requires_disabled": False,
        "ship_bonus_type": "treasury",
        "ship_bonus_range": (5, 10),
        "ship_bonus_label": "treasury",
        "job_achievement": "Shipwright's Mate",
        "job_achievement_description": "Helped the shipwright during recovery.",
        "rare_achievement": "Master's Apprentice",
        "rare_achievement_description": "Pulled off a rare shipwright support shift.",
        "unlock_text": "Requires ship level 2 and active recovery.",
    },
    "scavenge repair materials": {
        "kind": "maintenance",
        "label": "Scavenge Repair Materials",
        "aliases": {
            "scavenge repair materials",
            "repair materials",
            "scavenge materials",
            "repair scavenging",
        },
        "description": "Search wreckage and driftwood for fittings, bolts, and spare timber.",
        "risk": "High",
        "cooldown_minutes": 36,
        "base_payout": (20, 34),
        "repair_points": (4, 7),
        "success_chance": 72,
        "bonus_chance": 16,
        "rare_chance": 12,
        "min_level": 2,
        "min_world_discoveries": 1,
        "min_hidden_discoveries": 1,
        "required_achievements": [],
        "required_captures": 0,
        "requires_recovery": True,
        "requires_disabled": False,
        "ship_bonus_type": "supplies",
        "ship_bonus_range": (4, 8),
        "ship_bonus_label": "supplies",
        "job_achievement": "Material Scavenger",
        "job_achievement_description": "Scavenged repair materials during recovery.",
        "rare_achievement": "Lucky Salvage",
        "rare_achievement_description": "Pulled off a rare repair-material run.",
        "unlock_text": "Requires one discovered island, one hidden discovery, and ship level 2.",
    },
    "emergency repairs": {
        "kind": "maintenance",
        "label": "Emergency Repairs",
        "aliases": {
            "emergency repairs",
            "emergency repair",
            "wreck repair",
            "battle damage repair",
        },
        "description": "Throw every spare hand at the hull and bring the ship back from zero.",
        "risk": "Extreme",
        "cooldown_minutes": 60,
        "base_payout": (24, 40),
        "repair_points": (6, 10),
        "success_chance": 68,
        "bonus_chance": 18,
        "rare_chance": 14,
        "min_level": 2,
        "min_world_discoveries": 0,
        "min_hidden_discoveries": 0,
        "required_achievements": [],
        "required_captures": 0,
        "requires_recovery": True,
        "requires_disabled": True,
        "ship_bonus_type": "treasury",
        "ship_bonus_range": (8, 14),
        "ship_bonus_label": "treasury",
        "job_achievement": "Emergency Hand",
        "job_achievement_description": "Helped bring the Living Ship back from zero.",
        "rare_achievement": "Miracle Maker",
        "rare_achievement_description": "Pulled off a rare emergency repair.",
        "unlock_text": "Only available when the Living Ship is at 0 hull.",
    },
}

JOB_DEFINITIONS = {
    **GENERAL_JOBS,
    **MAINTENANCE_JOBS,
}

JOB_ORDER = (
    "dockhand",
    "salvager",
    "shipwright",
    "merchant",
    "bounty hunter",
    "patch the hull",
    "salvage lumber",
    "dockyard assistance",
    "clear the bilge",
    "help the shipwright",
    "scavenge repair materials",
    "emergency repairs",
)

GENERAL_JOB_KEYS = tuple(GENERAL_JOBS)
MAINTENANCE_JOB_KEYS = tuple(MAINTENANCE_JOBS)


def _now():
    return datetime.now(timezone.utc)


def _ts(dt=None):
    return (dt or _now()).strftime("%Y-%m-%d %H:%M:%S")


def _parse_timestamp(value):
    if not value:
        return None

    try:
        dt = datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None

    return dt.replace(tzinfo=timezone.utc)


async def _db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def _add_missing_columns(table_name, columns):
    db = await _db()
    try:
        rows = await (await db.execute(f"PRAGMA table_info({table_name})")).fetchall()
        existing = {str(row["name"]).lower() for row in rows}
        for column_sql, column_name in columns:
            if column_name.lower() not in existing:
                await db.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")
        await db.commit()
    finally:
        await db.close()


async def initialize_crew_work():
    db = await _db()
    try:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS crew_work_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT DEFAULT '',
                job_key TEXT NOT NULL,
                job_label TEXT NOT NULL,
                result_type TEXT NOT NULL,
                payout INTEGER DEFAULT 0,
                ship_bonus_type TEXT DEFAULT '',
                ship_bonus_value INTEGER DEFAULT 0,
                repair_hull INTEGER DEFAULT 0,
                repair_cap INTEGER DEFAULT 0,
                recovery_key TEXT DEFAULT '',
                details TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_crew_work_runs_user
            ON crew_work_runs(guild_id, user_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS crew_work_stats (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                job_key TEXT NOT NULL,
                job_label TEXT DEFAULT '',
                total_runs INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                bonus_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                rare_count INTEGER DEFAULT 0,
                payout_total INTEGER DEFAULT 0,
                ship_bonus_total INTEGER DEFAULT 0,
                repair_actions INTEGER DEFAULT 0,
                repair_hull_total INTEGER DEFAULT 0,
                repair_restore_count INTEGER DEFAULT 0,
                last_run_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, user_id, job_key)
            );

            CREATE TABLE IF NOT EXISTS crew_work_cooldowns (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                job_key TEXT NOT NULL,
                available_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_run_at DATETIME,
                PRIMARY KEY (guild_id, user_id, job_key)
            );

            CREATE TABLE IF NOT EXISTS ship_repair_contributions (
                guild_id INTEGER NOT NULL,
                recovery_key TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT DEFAULT '',
                job_key TEXT NOT NULL,
                job_label TEXT NOT NULL,
                hull_restored INTEGER DEFAULT 0,
                action_count INTEGER DEFAULT 0,
                rare_count INTEGER DEFAULT 0,
                first_action_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_action_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, recovery_key, user_id, job_key)
            );

            CREATE INDEX IF NOT EXISTS idx_ship_repair_contributions_cycle
            ON ship_repair_contributions(guild_id, recovery_key, hull_restored DESC, last_action_at DESC);
            """
        )

        await _add_missing_columns(
            "crew_work_runs",
            [
                ("repair_hull INTEGER DEFAULT 0", "repair_hull"),
                ("repair_cap INTEGER DEFAULT 0", "repair_cap"),
                ("recovery_key TEXT DEFAULT ''", "recovery_key"),
            ],
        )

        await _add_missing_columns(
            "crew_work_stats",
            [
                ("repair_actions INTEGER DEFAULT 0", "repair_actions"),
                ("repair_hull_total INTEGER DEFAULT 0", "repair_hull_total"),
                ("repair_restore_count INTEGER DEFAULT 0", "repair_restore_count"),
            ],
        )

        await db.commit()
    finally:
        await db.close()


def normalize_job_key(raw_value):
    key = " ".join(str(raw_value or "").lower().split())
    if not key:
        return None

    for job_key, info in JOB_DEFINITIONS.items():
        if key == job_key or key in info["aliases"]:
            return job_key

    return None


async def get_job_context(guild_id, user_id):
    ship = await get_ship(guild_id)
    ship_operational = await get_ship_operational_status(guild_id, ship=ship)
    world_discoveries, hidden_discoveries, achievements, captured_ships = await asyncio.gather(
        count_world_discoveries(guild_id),
        count_hidden_discoveries(guild_id),
        get_achievements(guild_id, user_id),
        count_captured_ships(guild_id),
    )

    return {
        "ship": ship,
        "ship_level": int(ship["level"]),
        "ship_operational": ship_operational,
        "world_discoveries": int(world_discoveries),
        "hidden_discoveries": int(hidden_discoveries),
        "achievements": achievements,
        "captured_ships": int(captured_ships),
    }


async def _get_job_state(guild_id, user_id, job_key):
    db = await _db()
    try:
        row = await (
            await db.execute(
                """
                SELECT *
                FROM crew_work_cooldowns
                WHERE guild_id = ?
                  AND user_id = ?
                  AND job_key = ?
                """,
                (guild_id, user_id, job_key),
            )
        ).fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def _cooldown_reason(guild_id, user_id, job_key):
    state = await _get_job_state(guild_id, user_id, job_key)
    if not state:
        return None

    available_at = _parse_timestamp(state["available_at"])
    if available_at and available_at > _now():
        return "That job is on cooldown. Ready at " + discord_timestamp(_ts(available_at)) + "."

    return None


async def get_work_stats(guild_id, user_id):
    db = await _db()
    try:
        rows = await (
            await db.execute(
                """
                SELECT
                    job_key,
                    job_label,
                    total_runs,
                    success_count,
                    bonus_count,
                    failure_count,
                    rare_count,
                    payout_total,
                    ship_bonus_total,
                    repair_actions,
                    repair_hull_total,
                    repair_restore_count,
                    last_run_at
                FROM crew_work_stats
                WHERE guild_id = ?
                  AND user_id = ?
                ORDER BY job_key
                """,
                (guild_id, user_id),
            )
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_work_totals(guild_id, user_id):
    db = await _db()
    try:
        row = await (
            await db.execute(
                """
                SELECT
                    COALESCE(SUM(total_runs), 0) AS total_runs,
                    COALESCE(SUM(success_count), 0) AS success_count,
                    COALESCE(SUM(bonus_count), 0) AS bonus_count,
                    COALESCE(SUM(failure_count), 0) AS failure_count,
                    COALESCE(SUM(rare_count), 0) AS rare_count,
                    COALESCE(SUM(payout_total), 0) AS payout_total,
                    COALESCE(SUM(ship_bonus_total), 0) AS ship_bonus_total,
                    COALESCE(SUM(repair_actions), 0) AS repair_actions,
                    COALESCE(SUM(repair_hull_total), 0) AS repair_hull_total,
                    COALESCE(SUM(repair_restore_count), 0) AS repair_restore_count
                FROM crew_work_stats
                WHERE guild_id = ?
                  AND user_id = ?
                """,
                (guild_id, user_id),
            )
        ).fetchone()

        return {
            "total_runs": int(row["total_runs"]),
            "success_count": int(row["success_count"]),
            "bonus_count": int(row["bonus_count"]),
            "failure_count": int(row["failure_count"]),
            "rare_count": int(row["rare_count"]),
            "payout_total": int(row["payout_total"]),
            "ship_bonus_total": int(row["ship_bonus_total"]),
            "repair_actions": int(row["repair_actions"]),
            "repair_hull_total": int(row["repair_hull_total"]),
            "repair_restore_count": int(row["repair_restore_count"]),
        }
    finally:
        await db.close()


async def get_repair_snapshot(guild_id):
    ship = await get_ship(guild_id)
    operational = await get_ship_operational_status(guild_id, ship=ship)

    if operational["operational"]:
        return {
            "active": False,
            "ship": ship,
            "operational": operational,
            "cycle_hull_restored": 0,
            "contributions": [],
            "contributors": [],
            "remaining": 0,
            "cycle_key": None,
        }

    recovery_key = ship.get("recovery_started_at") or ship.get("recovery_last_at")
    if not recovery_key:
        return {
            "active": False,
            "ship": ship,
            "operational": operational,
            "cycle_hull_restored": 0,
            "contributions": [],
            "contributors": [],
            "remaining": operational["needed"],
            "cycle_key": None,
        }

    db = await _db()
    try:
        rows = await (
            await db.execute(
                """
                SELECT
                    user_id,
                    username,
                    job_key,
                    job_label,
                    hull_restored,
                    action_count,
                    rare_count,
                    first_action_at,
                    last_action_at
                FROM ship_repair_contributions
                WHERE guild_id = ?
                  AND recovery_key = ?
                ORDER BY hull_restored DESC, action_count DESC, last_action_at DESC
                """,
                (guild_id, recovery_key),
            )
        ).fetchall()

        contributions = [dict(row) for row in rows]
        cycle_hull_restored = sum(int(row["hull_restored"]) for row in contributions)
        contributors = [
            {
                "username": row["username"],
                "job_label": row["job_label"],
                "hull_restored": int(row["hull_restored"]),
                "action_count": int(row["action_count"]),
            }
            for row in contributions
        ]

        return {
            "active": True,
            "ship": ship,
            "operational": operational,
            "cycle_hull_restored": cycle_hull_restored,
            "contributions": contributions,
            "contributors": contributors,
            "remaining": max(0, operational["needed"]),
            "cycle_key": recovery_key,
        }
    finally:
        await db.close()


def _job_unlock_reason(job, context):
    ship_level = int(context["ship_level"])

    if ship_level < int(job.get("min_level", 1)):
        return (
            "Requires Living Ship level "
            + str(job.get("min_level", 1))
            + "."
        )

    if context["world_discoveries"] < int(job.get("min_world_discoveries", 0)):
        return (
            "Requires "
            + str(job.get("min_world_discoveries", 0))
            + " discovered islands."
        )

    if context["hidden_discoveries"] < int(job.get("min_hidden_discoveries", 0)):
        return (
            "Requires "
            + str(job.get("min_hidden_discoveries", 0))
            + " hidden discoveries."
        )

    required_achievements = {
        str(name).lower().strip()
        for name in job.get("required_achievements", [])
    }

    if required_achievements:
        user_achievements = {
            str(row[0]).lower().strip()
            for row in context["achievements"]
        }

        if not required_achievements.intersection(user_achievements):
            return (
                "Requires one of: "
                + ", ".join(job.get("required_achievements", []))
                + "."
            )

    required_captures = int(job.get("required_captures", 0))
    if context["captured_ships"] < required_captures:
        return "Requires " + str(required_captures) + " captured ships."

    if job.get("requires_recovery") and context["ship_operational"]["operational"]:
        return "Available only while the Living Ship is recovering."

    if job.get("requires_disabled") and context["ship"]["hull"] > 0:
        return "Requires the Living Ship to be at 0 hull."

    return None


def _risk_multiplier(job):
    return {
        "Low": 1.00,
        "Medium": 1.12,
        "High": 1.25,
        "Extreme": 1.40,
    }.get(job.get("risk", "Low"), 1.0)


def _progress_multiplier(context):
    ship_level = int(context["ship_level"])
    discoveries = int(context["world_discoveries"])
    hidden = int(context["hidden_discoveries"])
    captures = int(context["captured_ships"])

    return (
        1.0
        + min(0.04 * max(0, ship_level - 1), 0.24)
        + min(0.02 * discoveries, 0.10)
        + min(0.03 * hidden, 0.09)
        + min(0.01 * captures, 0.08)
    )


def _format_duration(minutes):
    minutes = max(0, int(minutes))

    if minutes < 60:
        return f"{minutes}m"

    hours, rem = divmod(minutes, 60)
    if rem:
        return f"{hours}h {rem}m"
    return f"{hours}h"


def _format_bonus(bonus_type, bonus_value):
    if not bonus_type or bonus_value <= 0:
        return ""
    return "+" + str(bonus_value) + " " + bonus_type


def _format_ship_bonus(job, ship_bonus_value):
    bonus_type = job.get("ship_bonus_type")
    if not bonus_type or ship_bonus_value <= 0:
        return "none"
    return "+" + str(ship_bonus_value) + " " + job.get("ship_bonus_label", bonus_type)


def _job_roll(job):
    roll = random.randint(1, 100)
    success_cutoff = int(job.get("success_chance", 75))
    bonus_cutoff = success_cutoff + int(job.get("bonus_chance", 15))
    rare_cutoff = bonus_cutoff + int(job.get("rare_chance", 5))

    if roll <= success_cutoff:
        return "success"
    if roll <= bonus_cutoff:
        return "bonus"
    if roll <= rare_cutoff:
        return "rare"
    return "failure"


def _result_payout(job, result_type, context):
    base_min, base_max = job["base_payout"]
    base = random.randint(int(base_min), int(base_max))
    payout = round(base * _risk_multiplier(job) * _progress_multiplier(context))

    if result_type == "bonus":
        payout = round(payout * 1.25)
    elif result_type == "rare":
        payout = round(payout * 1.6)
    elif result_type == "failure":
        payout = max(5, round(payout * 0.35))

    return max(5, int(payout))


def _result_ship_bonus(job, result_type, context):
    bonus_type = job.get("ship_bonus_type")
    if not bonus_type:
        return None, 0

    min_bonus, max_bonus = job["ship_bonus_range"]
    value = round(random.randint(int(min_bonus), int(max_bonus)) * _progress_multiplier(context))

    if result_type == "bonus":
        value = round(value * 1.25)
    elif result_type == "rare":
        value = round(value * 1.6)
    elif result_type == "failure":
        value = round(value * 0.5)

    return bonus_type, max(0, int(value))


def _result_repair_points(job, result_type, context):
    if job.get("kind") != "maintenance":
        return 0

    min_points, max_points = job["repair_points"]
    amount = round(random.randint(int(min_points), int(max_points)) * _progress_multiplier(context))

    if result_type == "bonus":
        amount = round(amount * 1.25)
    elif result_type == "rare":
        amount = round(amount * 1.6)
    elif result_type == "failure":
        amount = max(1, round(amount * 0.5))

    return max(1, int(amount))


async def _award_work_milestones(guild_id, user_id, total_runs, job_key, job_stats, result_type):
    unlocked = []

    for threshold, (name, description) in WORK_ACHIEVEMENTS.items():
        if total_runs == threshold and await award_achievement(guild_id, user_id, name, description):
            unlocked.append(name)

    job = JOB_DEFINITIONS[job_key]

    if int(job_stats.get("success_count", 0)) == 1:
        if await award_achievement(guild_id, user_id, job["job_achievement"], job["job_achievement_description"]):
            unlocked.append(job["job_achievement"])

    if result_type == "rare":
        rare_name = job["rare_achievement"]
        if await award_achievement(guild_id, user_id, rare_name, job["rare_achievement_description"]):
            unlocked.append(rare_name)

    return unlocked


async def _award_repair_milestones(guild_id, user_id, stats, result_type, restored_operational):
    unlocked = []
    repair_actions = int(stats.get("repair_actions", 0))
    repair_hull_total = int(stats.get("repair_hull_total", 0))
    repair_restore_count = int(stats.get("repair_restore_count", 0))

    for threshold, (name, description) in REPAIR_ACTION_ACHIEVEMENTS.items():
        if repair_actions == threshold and await award_achievement(guild_id, user_id, name, description):
            unlocked.append(name)

    for threshold, (name, description) in REPAIR_HULL_ACHIEVEMENTS.items():
        if repair_hull_total >= threshold and await award_achievement(guild_id, user_id, name, description):
            unlocked.append(name)

    if restored_operational:
        name, description = REPAIR_RESTORE_ACHIEVEMENT
        if await award_achievement(guild_id, user_id, name, description):
            unlocked.append(name)

    if result_type == "rare":
        name, description = REPAIR_RARE_ACHIEVEMENT
        if await award_achievement(guild_id, user_id, name, description):
            unlocked.append(name)

    if repair_restore_count >= 3:
        if await award_achievement(guild_id, user_id, "Repeat Refloater", "Helped restore the Living Ship three times."):
            unlocked.append("Repeat Refloater")

    return unlocked


def _format_job_result_label(job, result_type):
    if job.get("kind") == "maintenance":
        return {
            "rare": "RARE RECOVERY",
            "bonus": "RECOVERY BOOST",
            "failure": "ROUGH REPAIR",
        }.get(result_type, "MAINTENANCE SHIFT COMPLETE")

    return {
        "rare": "RARE OUTCOME",
        "bonus": "BONUS SHIFT",
        "failure": "ROUGH SHIFT",
    }.get(result_type, "SHIFT COMPLETE")


async def format_jobs_board(guild_id, user_id):
    context = await get_job_context(guild_id, user_id)
    repair_snapshot = await get_repair_snapshot(guild_id)

    lines = [
        "**CREW WORK BOARD**",
        "The ship can be disabled and these jobs still work ashore.",
        "Maintenance jobs open while the Living Ship is recovering.",
        "",
        "Ship level: **" + str(context["ship_level"]) + "** | " + (
            "Operational"
            if context["ship_operational"]["operational"]
            else "Disabled / Recovering"
        ),
    ]

    if repair_snapshot and repair_snapshot["active"]:
        lines.extend(
            [
                "Current recovery: **" + str(repair_snapshot["cycle_hull_restored"]) + " hull restored by crew**",
                "Remaining to operational: **" + str(repair_snapshot["remaining"]) + " hull**",
            ]
        )

    for job_key in JOB_ORDER:
        job = JOB_DEFINITIONS[job_key]
        reason = _job_unlock_reason(job, context)
        payout_min, payout_max = job["base_payout"]
        cooldown = _format_duration(job["cooldown_minutes"])

        status = "**READY**" if reason is None else "**LOCKED**"
        lines.extend(
            [
                "",
                "**" + job["label"] + "** — " + status,
                job["description"],
            ]
        )

        if job["kind"] == "maintenance":
            repair_min, repair_max = job["repair_points"]
            lines.append(
                "Payout: **"
                + str(payout_min)
                + "-"
                + str(payout_max)
                + " doubloons** | Repair: **+"
                + str(repair_min)
                + "-"
                + str(repair_max)
                + " hull** | Cooldown: **"
                + cooldown
                + "** | Risk: **"
                + job["risk"]
                + "**"
            )
        else:
            lines.append(
                "Payout: **"
                + str(payout_min)
                + "-"
                + str(payout_max)
                + " doubloons** | Cooldown: **"
                + cooldown
                + "** | Risk: **"
                + job["risk"]
                + "**"
            )

        if job.get("ship_bonus_type"):
            bonus_min, bonus_max = job["ship_bonus_range"]
            lines.append(
                "Ship benefit: **+"
                + str(bonus_min)
                + "-"
                + str(bonus_max)
                + " "
                + job.get("ship_bonus_label", job["ship_bonus_type"])
                + "**"
            )

        lines.append(
            "Unlock: " + (job["unlock_text"] if reason is None else reason)
        )

    return "\n".join(lines)


async def format_work_summary(guild_id, user_id):
    context = await get_job_context(guild_id, user_id)
    totals = await get_work_totals(guild_id, user_id)
    repair_snapshot = await get_repair_snapshot(guild_id)

    lines = [
        "**YOUR WORK LEDGER**",
        "Doubloons: **" + str(await get_doubloons(guild_id, user_id)) + "**",
        "Ship level: **" + str(context["ship_level"]) + "**",
        "Ship status: **"
        + (
            "Operational"
            if context["ship_operational"]["operational"]
            else "Disabled / Recovering"
        )
        + "**",
        "Completed jobs: **" + str(totals["total_runs"]) + "**",
        "Successful runs: **" + str(totals["success_count"]) + "**",
        "Rare outcomes: **" + str(totals["rare_count"]) + "**",
        "Doubloons earned: **" + str(totals["payout_total"]) + "**",
        "Ship benefits delivered: **" + str(totals["ship_bonus_total"]) + "**",
        "Maintenance shifts: **" + str(totals["repair_actions"]) + "**",
        "Hull restored by crew: **" + str(totals["repair_hull_total"]) + "**",
        "Ship restorations: **" + str(totals["repair_restore_count"]) + "**",
        "",
        "Use `!cutlass jobs` to see the board or `!cutlass work <job>` to take a shift.",
    ]

    if repair_snapshot and repair_snapshot["active"]:
        lines.extend(
            [
                "",
                "**ACTIVE RECOVERY CYCLE**",
                "Hull restored this cycle: **"
                + str(repair_snapshot["cycle_hull_restored"]) 
                + "**",
                "Hull remaining to operational: **"
                + str(repair_snapshot["remaining"]) 
                + "**",
            ]
        )

        top_contributors = repair_snapshot["contributors"][:3]
        if top_contributors:
            lines.append("Top contributors:")
            for row in top_contributors:
                lines.append(
                    "- **"
                    + str(row["username"] or "Unknown")
                    + "** via **"
                    + str(row["job_label"])
                    + "**: **+"
                    + str(row["hull_restored"])
                    + " hull**"
                )

    stats = await get_work_stats(guild_id, user_id)

    if stats:
        lines.append("")
        lines.append("**Active job cooldowns**")

        for row in stats:
            cooldown_row = await _get_job_state(guild_id, user_id, row["job_key"])
            if cooldown_row:
                available_at = _parse_timestamp(cooldown_row["available_at"])
            else:
                available_at = None

            if available_at and available_at > _now():
                ready_text = "Ready at " + discord_timestamp(_ts(available_at))
            else:
                ready_text = "Ready now"

            lines.append("- **" + row["job_label"] + "**: " + ready_text)

    return "\n".join(lines)


async def _apply_general_job(
    guild_id,
    user_id,
    username,
    job_key,
    job,
    context,
    result_type,
    payout,
    ship_bonus_type,
    ship_bonus_value,
):
    db = await _db()
    try:
        run_cursor = await db.execute(
            """
            INSERT INTO crew_work_runs (
                guild_id,
                user_id,
                username,
                job_key,
                job_label,
                result_type,
                payout,
                ship_bonus_type,
                ship_bonus_value,
                repair_hull,
                repair_cap,
                recovery_key,
                details
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, '', ?)
            """,
            (
                guild_id,
                user_id,
                username,
                job_key,
                job["label"],
                result_type,
                payout,
                ship_bonus_type or "",
                ship_bonus_value,
                job["description"],
            ),
        )

        await db.execute(
            """
            INSERT INTO crew_work_stats (
                guild_id,
                user_id,
                job_key,
                job_label,
                total_runs,
                success_count,
                bonus_count,
                failure_count,
                rare_count,
                payout_total,
                ship_bonus_total,
                repair_actions,
                repair_hull_total,
                repair_restore_count,
                last_run_at
            )
            VALUES (
                ?, ?, ?, ?, 1,
                ?, ?, ?, ?,
                ?, ?, 0, 0, 0, CURRENT_TIMESTAMP
            )
            ON CONFLICT(guild_id, user_id, job_key)
            DO UPDATE SET
                job_label = excluded.job_label,
                total_runs = crew_work_stats.total_runs + 1,
                success_count = crew_work_stats.success_count + excluded.success_count,
                bonus_count = crew_work_stats.bonus_count + excluded.bonus_count,
                failure_count = crew_work_stats.failure_count + excluded.failure_count,
                rare_count = crew_work_stats.rare_count + excluded.rare_count,
                payout_total = crew_work_stats.payout_total + excluded.payout_total,
                ship_bonus_total = crew_work_stats.ship_bonus_total + excluded.ship_bonus_total,
                last_run_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                guild_id,
                user_id,
                job_key,
                job["label"],
                1 if result_type in {"success", "bonus", "rare"} else 0,
                1 if result_type == "bonus" else 0,
                1 if result_type == "failure" else 0,
                1 if result_type == "rare" else 0,
                payout,
                ship_bonus_value,
            ),
        )

        await db.execute(
            """
            INSERT INTO crew_work_cooldowns (
                guild_id,
                user_id,
                job_key,
                available_at,
                last_run_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id, job_key)
            DO UPDATE SET
                available_at = excluded.available_at,
                last_run_at = excluded.last_run_at
            """,
            (
                guild_id,
                user_id,
                job_key,
                _ts(_now() + timedelta(minutes=int(job["cooldown_minutes"]))),
                _ts(),
            ),
        )

        await db.commit()
        return int(run_cursor.lastrowid or 0)
    finally:
        await db.close()


async def _apply_maintenance_job(
    guild_id,
    user_id,
    username,
    job_key,
    job,
    context,
    result_type,
    payout,
    ship_bonus_type,
    ship_bonus_value,
):
    async with get_guild_lock(guild_id):
        ship = await get_ship(guild_id)
        upgrades = await get_upgrade_levels(guild_id)
        max_hull = int(ship_caps(upgrades)["hull"])
        threshold = operational_hull_threshold(max_hull)
        current_hull = int(ship["hull"])
        current_sails = int(ship["sails"])
        recovery_key = ship.get("recovery_started_at") or ship.get("recovery_last_at") or _ts()

        if current_hull >= threshold:
            return False, "The Living Ship is already operational. Use `!cutlass jobs` for regular work."

        repair_points = _result_repair_points(job, result_type, context)
        if repair_points <= 0:
            repair_points = 1

        hull_restored = min(repair_points, max(0, threshold - current_hull))
        if hull_restored <= 0:
            return False, "The recovery crew already pushed the ship back to operational hull."

        new_hull = min(threshold, current_hull + hull_restored)
        became_operational = new_hull >= threshold

        db = await _db()
        try:
            await db.execute(
                """
                UPDATE ships
                SET hull = ?,
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
                    new_hull,
                    became_operational,
                    became_operational,
                    guild_id,
                ),
            )

            await db.execute(
                """
                INSERT INTO ship_repair_contributions (
                    guild_id,
                    recovery_key,
                    user_id,
                    username,
                    job_key,
                    job_label,
                    hull_restored,
                    action_count,
                    rare_count,
                    first_action_at,
                    last_action_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(guild_id, recovery_key, user_id, job_key)
                DO UPDATE SET
                    username = excluded.username,
                    job_label = excluded.job_label,
                    hull_restored = ship_repair_contributions.hull_restored + excluded.hull_restored,
                    action_count = ship_repair_contributions.action_count + excluded.action_count,
                    rare_count = ship_repair_contributions.rare_count + excluded.rare_count,
                    last_action_at = CURRENT_TIMESTAMP
                """,
                (
                    guild_id,
                    recovery_key,
                    user_id,
                    username,
                    job_key,
                    job["label"],
                    hull_restored,
                    1 if result_type == "rare" else 0,
                ),
            )

            await db.execute(
                """
                INSERT INTO crew_work_runs (
                    guild_id,
                    user_id,
                    username,
                    job_key,
                    job_label,
                    result_type,
                    payout,
                    ship_bonus_type,
                    ship_bonus_value,
                    repair_hull,
                    repair_cap,
                    recovery_key,
                    details
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    guild_id,
                    user_id,
                    username,
                    job_key,
                    job["label"],
                    result_type,
                    payout,
                    ship_bonus_type or "",
                    ship_bonus_value,
                    hull_restored,
                    threshold,
                    recovery_key,
                    job["description"],
                ),
            )

            await db.execute(
                """
                INSERT INTO crew_work_stats (
                    guild_id,
                    user_id,
                    job_key,
                    job_label,
                    total_runs,
                    success_count,
                    bonus_count,
                    failure_count,
                    rare_count,
                    payout_total,
                    ship_bonus_total,
                    repair_actions,
                    repair_hull_total,
                    repair_restore_count,
                    last_run_at
                )
                VALUES (
                    ?, ?, ?, ?, 1,
                    ?, ?, ?, ?,
                    ?, ?, 1, ?, ?, CURRENT_TIMESTAMP
                )
                ON CONFLICT(guild_id, user_id, job_key)
                DO UPDATE SET
                    job_label = excluded.job_label,
                    total_runs = crew_work_stats.total_runs + 1,
                    success_count = crew_work_stats.success_count + excluded.success_count,
                    bonus_count = crew_work_stats.bonus_count + excluded.bonus_count,
                    failure_count = crew_work_stats.failure_count + excluded.failure_count,
                    rare_count = crew_work_stats.rare_count + excluded.rare_count,
                    payout_total = crew_work_stats.payout_total + excluded.payout_total,
                    ship_bonus_total = crew_work_stats.ship_bonus_total + excluded.ship_bonus_total,
                    repair_actions = crew_work_stats.repair_actions + excluded.repair_actions,
                    repair_hull_total = crew_work_stats.repair_hull_total + excluded.repair_hull_total,
                    repair_restore_count = crew_work_stats.repair_restore_count + excluded.repair_restore_count,
                    last_run_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    guild_id,
                    user_id,
                    job_key,
                    job["label"],
                    1 if result_type in {"success", "bonus", "rare"} else 0,
                    1 if result_type == "bonus" else 0,
                    1 if result_type == "failure" else 0,
                    1 if result_type == "rare" else 0,
                    payout,
                    ship_bonus_value,
                    hull_restored,
                    1 if became_operational else 0,
                ),
            )

            await db.execute(
                """
                INSERT INTO crew_work_cooldowns (
                    guild_id,
                    user_id,
                    job_key,
                    available_at,
                    last_run_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id, job_key)
                DO UPDATE SET
                    available_at = excluded.available_at,
                    last_run_at = excluded.last_run_at
                """,
                (
                    guild_id,
                    user_id,
                    job_key,
                    _ts(_now() + timedelta(minutes=int(job["cooldown_minutes"]))),
                    _ts(),
                ),
            )

            await db.commit()
        finally:
            await db.close()

        if ship["hull"] < threshold and int(ship["hull"]) == 0:
            pass

        return True, {
            "hull_restored": hull_restored,
            "new_hull": new_hull,
            "threshold": threshold,
            "became_operational": became_operational,
            "recovery_key": recovery_key,
            "current_hull": current_hull,
            "current_sails": current_sails,
        }


async def perform_job(guild_id, user_id, username, raw_job_key):
    job_key = normalize_job_key(raw_job_key)
    if not job_key:
        return False, "That job does not exist. Use `!cutlass jobs`."

    job = JOB_DEFINITIONS[job_key]

    async with get_guild_lock(guild_id):
        context = await get_job_context(guild_id, user_id)
        unlock_reason = _job_unlock_reason(job, context)
        if unlock_reason:
            return False, "**JOB LOCKED**\n" + job["label"] + " is not open yet.\n" + unlock_reason

        cooldown_reason = await _cooldown_reason(guild_id, user_id, job_key)
        if cooldown_reason:
            return False, "**JOB COOLDOWN**\n" + job["label"] + " is still cooling down.\n" + cooldown_reason

        result_type = _job_roll(job)
        payout = _result_payout(job, result_type, context)
        ship_bonus_type, ship_bonus_value = _result_ship_bonus(job, result_type, context)

        if job["kind"] == "maintenance":
            repair_ok, repair_result = await _apply_maintenance_job(
                guild_id,
                user_id,
                username,
                job_key,
                job,
                context,
                result_type,
                payout,
                ship_bonus_type,
                ship_bonus_value,
            )

            if not repair_ok:
                return False, repair_result

            await add_doubloons(guild_id, user_id, payout)

            ship_messages = []
            if ship_bonus_type == "supplies" and ship_bonus_value:
                await add_ship_supplies(guild_id, ship_bonus_value)
                ship_messages.append("+" + str(ship_bonus_value) + " supplies to the ship")
            elif ship_bonus_type == "treasury" and ship_bonus_value:
                await add_ship_treasury(guild_id, ship_bonus_value)
                ship_messages.append("+" + str(ship_bonus_value) + " doubloons to the ship treasury")

            totals = await get_work_totals(guild_id, user_id)
            stats = await get_work_stats(guild_id, user_id)
            job_stats = next((row for row in stats if row["job_key"] == job_key), None)

            unlocked_achievements = await _award_work_milestones(
                guild_id,
                user_id,
                totals["total_runs"],
                job_key,
                job_stats or {"success_count": 0},
                result_type,
            )

            repaired_stats = {
                "repair_actions": totals["repair_actions"],
                "repair_hull_total": totals["repair_hull_total"],
                "repair_restore_count": totals["repair_restore_count"],
            }
            repair_awards = await _award_repair_milestones(
                guild_id,
                user_id,
                repaired_stats,
                result_type,
                repair_result["became_operational"],
            )
            unlocked_achievements.extend(repair_awards)

            if repair_result["became_operational"]:
                await add_history(
                    guild_id,
                    (
                        "Crew maintenance restored the Living Ship to **operational status** at **"
                        + str(repair_result["new_hull"])
                        + "/"
                        + str(repair_result["threshold"])
                        + " hull**."
                    ),
                    "ship_restored",
                )

            if int(repair_result["current_hull"]) == 0:
                await add_history(
                    guild_id,
                    username + " led emergency repair work on the Living Ship.",
                    "crew_work",
                )

            result_label = _format_job_result_label(job, result_type)
            text_lines = [
                "**" + result_label + "** — " + job["label"],
                job["description"],
                "Payout: **+" + str(payout) + " doubloons**",
                "Hull restored: **+" + str(repair_result["hull_restored"]) + " hull**",
                "Ship benefit: **" + (
                    ", ".join(ship_messages) if ship_messages else "none"
                ) + "**",
                "Cooldown: **" + _format_duration(job["cooldown_minutes"]) + "**",
            ]

            if result_type == "failure":
                text_lines.append("The crew still made progress, but the work was rough.")
            elif result_type == "bonus":
                text_lines.append("The crew found extra value in the repair run.")
            elif result_type == "rare":
                text_lines.append("That one will be talked about at the dockside.")

            if unlocked_achievements:
                text_lines.extend(["", "**ACHIEVEMENT UNLOCKED**"])
                text_lines.extend("🏆 **" + achievement + "**" for achievement in unlocked_achievements)

            return True, "\n".join(text_lines)

        run_id = await _apply_general_job(
            guild_id,
            user_id,
            username,
            job_key,
            job,
            context,
            result_type,
            payout,
            ship_bonus_type,
            ship_bonus_value,
        )

    await add_doubloons(guild_id, user_id, payout)

    ship_messages = []
    if ship_bonus_type == "supplies" and ship_bonus_value:
        await add_ship_supplies(guild_id, ship_bonus_value)
        ship_messages.append("+" + str(ship_bonus_value) + " supplies to the ship")
    elif ship_bonus_type == "treasury" and ship_bonus_value:
        await add_ship_treasury(guild_id, ship_bonus_value)
        ship_messages.append("+" + str(ship_bonus_value) + " doubloons to the ship treasury")

    totals = await get_work_totals(guild_id, user_id)
    stats = await get_work_stats(guild_id, user_id)
    job_stats = next((row for row in stats if row["job_key"] == job_key), None)

    unlocked_achievements = await _award_work_milestones(
        guild_id,
        user_id,
        totals["total_runs"],
        job_key,
        job_stats or {"success_count": 0},
        result_type,
    )

    result_label = _format_job_result_label(job, result_type)
    text_lines = [
        "**" + result_label + "** — " + job["label"],
        job["description"],
        "Payout: **+" + str(payout) + " doubloons**",
        "Ship benefit: **" + (
            ", ".join(ship_messages) if ship_messages else "none"
        ) + "**",
        "Cooldown: **" + _format_duration(job["cooldown_minutes"]) + "**",
    ]

    if result_type == "failure":
        text_lines.append("The crew still finished the shift, but the haul was thin.")
    elif result_type == "bonus":
        text_lines.append("The crew turned up extra value from the work.")
    elif result_type == "rare":
        text_lines.append("That one will be talked about at the dockside.")

    if unlocked_achievements:
        text_lines.extend(["", "**ACHIEVEMENT UNLOCKED**"])
        text_lines.extend("🏆 **" + achievement + "**" for achievement in unlocked_achievements)

    await add_history(
        guild_id,
        username
        + " completed "
        + job["label"]
        + " crew work and earned "
        + str(payout)
        + " doubloons.",
        "crew_work",
    )

    return True, "\n".join(text_lines)
