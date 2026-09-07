import asyncio
import os
import random
from datetime import datetime, timedelta, timezone

import aiosqlite

from cutlass.world.locks import get_guild_lock
from memory import (
    add_doubloons,
    award_achievement,
    get_doubloons,
    get_achievements,
)
from ship_world import (
    add_history,
    add_ship_supplies,
    add_ship_treasury,
    count_captured_ships,
    discord_timestamp,
    get_ship,
    get_ship_operational_status,
)
from cutlass.world.pirate_world import (
    count_hidden_discoveries,
    count_world_discoveries,
)

DB_PATH = os.getenv("DATABASE_PATH", "/app/data/captain.db")

WORK_ACHIEVEMENTS = {
    1: ("First Shift", "Completed yer first crew job."),
    5: ("Hard Worker", "Completed five crew jobs."),
    10: ("Veteran Hand", "Completed ten crew jobs."),
    25: ("Seasoned Crew", "Completed twenty-five crew jobs."),
}

JOB_DEFINITIONS = {
    "dockhand": {
        "label": "Dockside Hands",
        "aliases": {
            "dockhand",
            "dockhands",
            "dockside",
            "dockside hands",
            "dock work",
            "harbor hand",
        },
        "description": (
            "Haul crates, scrub tar, and keep the harbor crew moving."
        ),
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
        "rare_achievement_description": (
            "Pulled off a rare dockside crew-work result."
        ),
        "unlock_text": "Available from the start.",
    },
    "salvager": {
        "label": "Salvager",
        "aliases": {
            "salvager",
            "salvage",
            "salvage crew",
            "wreck salvager",
        },
        "description": (
            "Break apart wreckage, sort useful timber, and reclaim cargo."
        ),
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
        "rare_achievement_description": (
            "Pulled off a rare salvage operation."
        ),
        "unlock_text": "Requires one hidden discovery or ship level 2.",
    },
    "shipwright": {
        "label": "Shipwright",
        "aliases": {
            "shipwright",
            "shipwright assistant",
            "hull repair",
            "yardhand",
        },
        "description": (
            "Hand timber to the shipwright and keep the drydock busy."
        ),
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
        "rare_achievement_description": (
            "Pulled off a rare shipwright operation."
        ),
        "unlock_text": "Requires ship level 3.",
    },
    "merchant": {
        "label": "Merchant Runner",
        "aliases": {
            "merchant",
            "merchant runner",
            "trade runner",
            "smuggler",
        },
        "description": (
            "Run cargo, bargain with traders, and keep the ledgers straight."
        ),
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
        "rare_achievement_description": (
            "Pulled off a rare merchant run."
        ),
        "unlock_text": "Requires two discovered islands and ship level 2.",
    },
    "bounty hunter": {
        "label": "Bounty Hunter",
        "aliases": {
            "bounty hunter",
            "hunter",
            "bounty",
            "prize hunter",
        },
        "description": (
            "Chase warrants, collect prizes, and come back with proof."
        ),
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
        "rare_achievement_description": (
            "Pulled off a rare bounty hunter job."
        ),
        "unlock_text": "Requires Prize of War and ship level 3.",
    },
}

JOB_ORDER = (
    "dockhand",
    "salvager",
    "shipwright",
    "merchant",
    "bounty hunter",
)


def _now():
    return datetime.now(timezone.utc)


def _ts(dt=None):
    return (dt or _now()).strftime("%Y-%m-%d %H:%M:%S")


def _parse_timestamp(value):
    if not value:
        return None

    try:
        dt = datetime.strptime(
            str(value),
            "%Y-%m-%d %H:%M:%S"
        )
    except (TypeError, ValueError):
        return None

    return dt.replace(tzinfo=timezone.utc)


async def _db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


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
            """
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
        return (
            "Requires "
            + str(required_captures)
            + " captured ships."
        )

    return None


async def get_job_context(guild_id, user_id):
    ship, ship_operational, world_discoveries, hidden_discoveries, achievements, captured_ships = await asyncio.gather(
        get_ship(guild_id),
        get_ship_operational_status(guild_id),
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


async def get_job_state(guild_id, user_id, job_key):
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
                (
                    guild_id,
                    user_id,
                    job_key,
                )
            )
        ).fetchone()

        if row is None:
            return None

        return dict(row)

    finally:
        await db.close()


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
                    last_run_at
                FROM crew_work_stats
                WHERE guild_id = ?
                  AND user_id = ?
                ORDER BY job_key
                """,
                (
                    guild_id,
                    user_id,
                )
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
                    COALESCE(SUM(ship_bonus_total), 0) AS ship_bonus_total
                FROM crew_work_stats
                WHERE guild_id = ?
                  AND user_id = ?
                """,
                (
                    guild_id,
                    user_id,
                )
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
        }

    finally:
        await db.close()


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

    return (
        1.0
        + min(0.04 * max(0, ship_level - 1), 0.24)
        + min(0.02 * discoveries, 0.10)
        + min(0.03 * hidden, 0.09)
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

    return (
        "+"
        + str(bonus_value)
        + " "
        + bonus_type
    )


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

    payout = round(
        base
        * _risk_multiplier(job)
        * _progress_multiplier(context)
    )

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

    progress = _progress_multiplier(context)
    value = round(
        random.randint(int(min_bonus), int(max_bonus))
        * progress
    )

    if result_type == "bonus":
        value = round(value * 1.25)
    elif result_type == "rare":
        value = round(value * 1.6)
    elif result_type == "failure":
        value = round(value * 0.5)

    return bonus_type, max(0, int(value))


async def _award_work_milestones(
    guild_id,
    user_id,
    username,
    total_runs,
    job_key,
    success_count,
    result_type,
):
    unlocked = []

    for threshold, (name, description) in WORK_ACHIEVEMENTS.items():
        if total_runs == threshold:
            if await award_achievement(
                guild_id,
                user_id,
                name,
                description
            ):
                unlocked.append(name)

    job = JOB_DEFINITIONS[job_key]

    if success_count == 1:
        if await award_achievement(
            guild_id,
            user_id,
            job["job_achievement"],
            job["job_achievement_description"]
        ):
            unlocked.append(job["job_achievement"])

    if result_type == "rare":
        rare_name = job["rare_achievement"]
        if await award_achievement(
            guild_id,
            user_id,
            rare_name,
            job["rare_achievement_description"]
        ):
            unlocked.append(rare_name)

    return unlocked


async def format_jobs_board(guild_id, user_id):
    context = await get_job_context(
        guild_id,
        user_id
    )

    lines = [
        "**CREW WORK BOARD**",
        "The ship can be disabled and these jobs still work ashore.",
        "",
        "Ship level: **"
        + str(context["ship_level"])
        + "** | "
        + (
            "Operational"
            if context["ship_operational"]["operational"]
            else "Disabled / Recovering"
        ),
    ]

    for job_key in JOB_ORDER:
        job = JOB_DEFINITIONS[job_key]
        reason = _job_unlock_reason(
            job,
            context
        )

        payout_min, payout_max = job["base_payout"]
        cooldown = _format_duration(job["cooldown_minutes"])

        status = (
            "**READY**"
            if reason is None
            else "**LOCKED**"
        )

        lines.extend([
            "",
            "**"
            + job["label"]
            + "** — "
            + status,
            job["description"],
            (
                "Payout: **"
                + str(payout_min)
                + "-"
                + str(payout_max)
                + " doubloons** | Cooldown: **"
                + cooldown
                + "** | Risk: **"
                + job["risk"]
                + "**"
            ),
        ])

        if reason is None:
            lines.append(
                "Unlock: "
                + job["unlock_text"]
            )
        else:
            lines.append(
                "Locked: "
                + reason
            )

    return "\n".join(lines)


async def format_work_summary(guild_id, user_id):
    context = await get_job_context(
        guild_id,
        user_id
    )

    totals = await get_work_totals(
        guild_id,
        user_id
    )

    lines = [
        "**YOUR WORK LEDGER**",
        "Doubloons: **"
        + str(await get_doubloons(guild_id, user_id))
        + "**",
        "Ship level: **"
        + str(context["ship_level"])
        + "**",
        (
            "Ship status: **"
            + (
                "Operational"
                if context["ship_operational"]["operational"]
                else "Disabled / Recovering"
            )
            + "**"
        ),
        "Completed jobs: **"
        + str(totals["total_runs"])
        + "**",
        "Successful runs: **"
        + str(totals["success_count"])
        + "**",
        "Rare outcomes: **"
        + str(totals["rare_count"])
        + "**",
        "Doubloons earned: **"
        + str(totals["payout_total"])
        + "**",
        "Ship benefits delivered: **"
        + str(totals["ship_bonus_total"])
        + "**",
        "",
        "Use `!cutlass jobs` to see the board or `!cutlass work <job>` to take a shift.",
    ]

    stats = await get_work_stats(
        guild_id,
        user_id
    )

    if stats:
        lines.append("")
        lines.append("**Active job cooldowns**")

        for row in stats:
            cooldown_row = await get_job_state(
                guild_id,
                user_id,
                row["job_key"]
            )

            if cooldown_row:
                available_at = _parse_timestamp(
                    cooldown_row["available_at"]
                )
            else:
                available_at = None

            if available_at and available_at > _now():
                ready_text = (
                    "Ready at "
                    + discord_timestamp(_ts(available_at))
                )
            else:
                ready_text = "Ready now"

            lines.append(
                "- **"
                + row["job_label"]
                + "**: "
                + ready_text
            )

    return "\n".join(lines)


async def perform_job(
    guild_id,
    user_id,
    username,
    raw_job_key
):
    job_key = normalize_job_key(
        raw_job_key
    )

    if not job_key:
        return (
            False,
            "That job does not exist. Use `!cutlass jobs`.",
        )

    job = JOB_DEFINITIONS[job_key]
    context = await get_job_context(
        guild_id,
        user_id
    )

    unlock_reason = _job_unlock_reason(
        job,
        context
    )

    if unlock_reason:
        return (
            False,
            "**JOB LOCKED**\n"
            + job["label"]
            + " is not open yet.\n"
            + unlock_reason
        )

    async with get_guild_lock(guild_id):
        cooldown_row = await get_job_state(
            guild_id,
            user_id,
            job_key
        )

        if cooldown_row:
            available_at = _parse_timestamp(
                cooldown_row["available_at"]
            )
            if available_at and available_at > _now():
                return (
                    False,
                    "**COOLDOWN**\n"
                    + job["label"]
                    + " will be ready again at "
                    + discord_timestamp(
                        _ts(available_at)
                    )
                    + "."
                )

        result_type = _job_roll(job)
        payout = _result_payout(
            job,
            result_type,
            context
        )
        ship_bonus_type, ship_bonus_value = _result_ship_bonus(
            job,
            result_type,
            context
        )

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
                    details
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                )
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
                    last_run_at
                )
                VALUES (
                    ?, ?, ?, ?, 1,
                    ?, ?, ?, ?,
                    ?, ?, CURRENT_TIMESTAMP
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
                )
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
                    _ts(
                        _now()
                        + timedelta(minutes=int(job["cooldown_minutes"]))
                    ),
                    _ts(),
                )
            )

            await db.commit()

        finally:
            await db.close()

        await add_doubloons(
            guild_id,
            user_id,
            payout
        )

        ship_messages = []

        if ship_bonus_type == "supplies" and ship_bonus_value:
            await add_ship_supplies(
                guild_id,
                ship_bonus_value
            )
            ship_messages.append(
                "+"
                + str(ship_bonus_value)
                + " supplies to the ship"
            )
        elif ship_bonus_type == "treasury" and ship_bonus_value:
            await add_ship_treasury(
                guild_id,
                ship_bonus_value
            )
            ship_messages.append(
                "+"
                + str(ship_bonus_value)
                + " doubloons to the ship treasury"
            )

        totals = await get_work_totals(
            guild_id,
            user_id
        )

        stats = await get_work_stats(
            guild_id,
            user_id
        )

        job_stats = next(
            (
                row
                for row in stats
                if row["job_key"] == job_key
            ),
            None
        )

        unlocked_achievements = await _award_work_milestones(
            guild_id,
            user_id,
            username,
            totals["total_runs"],
            job_key,
            int(job_stats["success_count"]) if job_stats else 0,
            result_type,
        )

        if result_type == "rare":
            result_label = "RARE OUTCOME"
        elif result_type == "bonus":
            result_label = "BONUS SHIFT"
        elif result_type == "failure":
            result_label = "ROUGH SHIFT"
        else:
            result_label = "SHIFT COMPLETE"

        text_lines = [
            "**"
            + result_label
            + "** — "
            + job["label"],
            job["description"],
            "Payout: **+"
            + str(payout)
            + " doubloons**",
        ]

        if ship_messages:
            text_lines.append(
                "Ship benefit: **"
                + ", ".join(ship_messages)
                + "**"
            )
        else:
            text_lines.append(
                "Ship benefit: **none**"
            )

        text_lines.append(
            "Cooldown: **"
            + _format_duration(job["cooldown_minutes"])
            + "**"
        )

        if result_type == "failure":
            text_lines.append(
                "The crew still finished the shift, but the haul was thin."
            )
        elif result_type == "bonus":
            text_lines.append(
                "The crew turned up extra value from the work."
            )
        elif result_type == "rare":
            text_lines.append(
                "That one will be talked about at the dockside."
            )

        if unlocked_achievements:
            text_lines.extend([
                "",
                "**ACHIEVEMENT UNLOCKED**",
            ])

            text_lines.extend(
                "🏆 **" + achievement + "**"
                for achievement in unlocked_achievements
            )

        await add_history(
            guild_id,
            (
                username
                + " completed "
                + job["label"]
                + " crew work and earned "
                + str(payout)
                + " doubloons."
            ),
            "crew_work"
        )

        return True, "\n".join(text_lines)
