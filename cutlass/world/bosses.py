import os
import random

import aiosqlite


DB_PATH = os.getenv(
    "DATABASE_PATH",
    "/app/data/captain.db"
)


BOSSES = {
    "skullfin_guardian": {
        "name": "Guardian of Skullfin",
        "hp": 350,
        "attack_min": 18,
        "attack_max": 32,
        "reward_min": 700,
        "reward_max": 1100,
        "xp": 600,
        "danger": "Extreme",
        "phases": 2,
    },

    "drowned_captain": {
        "name": "The Drowned Captain",
        "hp": 420,
        "attack_min": 20,
        "attack_max": 36,
        "reward_min": 900,
        "reward_max": 1400,
        "xp": 750,
        "danger": "Extreme",
        "phases": 2,
    },

    "drowned_king": {
        "name": "The Drowned King",
        "hp": 650,
        "attack_min": 28,
        "attack_max": 48,
        "reward_min": 1600,
        "reward_max": 2600,
        "xp": 1400,
        "danger": "Legendary",
        "phases": 3,
    },
}


async def _db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def initialize_bosses():

    db = await _db()

    try:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS boss_encounters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            boss_key TEXT NOT NULL,
            name TEXT NOT NULL,
            hp INTEGER NOT NULL,
            max_hp INTEGER NOT NULL,
            attack_min INTEGER NOT NULL,
            attack_max INTEGER NOT NULL,
            reward_min INTEGER NOT NULL,
            reward_max INTEGER NOT NULL,
            xp_reward INTEGER NOT NULL,
            danger TEXT DEFAULT 'Extreme',
            phase INTEGER DEFAULT 1,
            max_phase INTEGER DEFAULT 1,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_boss_active
        ON boss_encounters(guild_id)
        WHERE status = 'active';

        CREATE TABLE IF NOT EXISTS boss_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            boss_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            action TEXT DEFAULT '',
            description TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        await db.commit()

    finally:
        await db.close()


async def get_active_boss(guild_id):

    db = await _db()

    try:
        row = await (
            await db.execute("""
                SELECT *
                FROM boss_encounters
                WHERE guild_id = ?
                  AND status = 'active'
                ORDER BY id DESC
                LIMIT 1
            """, (guild_id,))
        ).fetchone()

        return row

    finally:
        await db.close()


async def start_boss(
    guild_id,
    boss_key
):

    active = await get_active_boss(
        guild_id
    )

    if active:
        return False, active

    if boss_key not in BOSSES:
        return False, "Unknown boss."

    boss = BOSSES[boss_key]

    db = await _db()

    try:
        await db.execute("""
            INSERT INTO boss_encounters (
                guild_id,
                boss_key,
                name,
                hp,
                max_hp,
                attack_min,
                attack_max,
                reward_min,
                reward_max,
                xp_reward,
                danger,
                max_phase
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            guild_id,
            boss_key,
            boss["name"],
            boss["hp"],
            boss["hp"],
            boss["attack_min"],
            boss["attack_max"],
            boss["reward_min"],
            boss["reward_max"],
            boss["xp"],
            boss["danger"],
            boss["phases"],
        ))

        await db.commit()

    finally:
        await db.close()

    return True, await get_active_boss(
        guild_id
    )


async def format_boss(guild_id):

    boss = await get_active_boss(
        guild_id
    )

    if not boss:
        return (
            "**BOSS ENCOUNTER**\n"
            "No legendary enemy is currently engaged."
        )

    return (
        "**"
        + boss["name"].upper()
        + "**\n"
        "Danger: **"
        + boss["danger"]
        + "**\n"
        "HP: **"
        + str(boss["hp"])
        + "/"
        + str(boss["max_hp"])
        + "**\n"
        "Phase: **"
        + str(boss["phase"])
        + "/"
        + str(boss["max_phase"])
        + "**"
    )


async def attack_boss(guild_id):

    boss = await get_active_boss(
        guild_id
    )

    if not boss:
        return False, "There is no boss to attack.", None

    player_damage = random.randint(
        18,
        34
    )

    hp = max(
        0,
        int(boss["hp"])
        - player_damage
    )

    phase = int(boss["phase"])
    max_phase = int(boss["max_phase"])

    # Phase thresholds.
    phase_size = max(
        1,
        int(boss["max_hp"]) // max_phase
    )

    expected_phase = min(
        max_phase,
        max(
            1,
            max_phase - (hp // phase_size)
        )
    )

    phase_changed = (
        expected_phase > phase
        and hp > 0
    )

    if phase_changed:
        phase = expected_phase

    attack_min = int(
        boss["attack_min"]
    )

    attack_max = int(
        boss["attack_max"]
    )

    # Boss grows more dangerous each phase.
    attack_min += (phase - 1) * 4
    attack_max += (phase - 1) * 7

    enemy_damage = 0

    if hp > 0:
        enemy_damage = random.randint(
            attack_min,
            attack_max
        )

    db = await _db()

    try:
        await db.execute("""
            UPDATE boss_encounters
            SET hp = ?,
                phase = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            hp,
            phase,
            boss["id"],
        ))

        if hp <= 0:
            await db.execute("""
                UPDATE boss_encounters
                SET status = 'victory',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                boss["id"],
            ))

        await db.commit()

    finally:
        await db.close()

    if hp <= 0:

        reward = random.randint(
            int(boss["reward_min"]),
            int(boss["reward_max"])
        )

        return True, (
            "**"
            + boss["name"].upper()
            + " DEFEATED**\n"
            "The final blow lands for **"
            + str(player_damage)
            + "** damage.\n\n"
            "Recovered treasure: **"
            + str(reward)
            + " doubloons**\n"
            "Ship XP: **"
            + str(boss["xp_reward"])
            + "**"
        ), {
            "victory": True,
            "reward": reward,
            "xp": int(boss["xp_reward"]),
            "enemy_damage": 0,
            "name": boss["name"],
        }

    text = (
        "**BOSS ATTACK**\n"
        "The crew deals **"
        + str(player_damage)
        + "** damage to "
        + boss["name"]
        + ".\n"
    )

    if phase_changed:
        text += (
            "\n**PHASE "
            + str(phase)
            + " BEGINS!**\n"
            + boss["name"]
            + " grows more dangerous.\n"
        )

    text += (
        boss["name"]
        + " retaliates for **"
        + str(enemy_damage)
        + "** damage.\n\n"
        "HP: **"
        + str(hp)
        + "/"
        + str(boss["max_hp"])
        + "**\n"
        "Phase: **"
        + str(phase)
        + "/"
        + str(max_phase)
        + "**"
    )

    return True, text, {
        "victory": False,
        "reward": 0,
        "xp": 0,
        "enemy_damage": enemy_damage,
        "name": boss["name"],
    }


async def defend_boss(guild_id):

    boss = await get_active_boss(
        guild_id
    )

    if not boss:
        return False, "There is no boss to defend against.", None

    phase = int(
        boss["phase"]
    )

    raw = random.randint(
        int(boss["attack_min"]) + (phase - 1) * 4,
        int(boss["attack_max"]) + (phase - 1) * 7
    )

    damage = max(
        1,
        raw // 2
    )

    return True, (
        "**HOLD THE LINE!**\n"
        "The crew braces against "
        + boss["name"]
        + ".\n"
        "Incoming damage reduced to **"
        + str(damage)
        + "**."
    ), {
        "enemy_damage": damage,
    }
