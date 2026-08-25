import os
import random

import aiosqlite


DB_PATH = os.getenv(
    "DATABASE_PATH",
    "/app/data/captain.db"
)


MONSTERS = {
    "kraken": {
        "name": "The Kraken",
        "type": "monster",
        "hp": 250,
        "attack_min": 15,
        "attack_max": 30,
        "reward_min": 400,
        "reward_max": 700,
        "xp": 350,
        "danger": "High",
    },

    "leviathan": {
        "name": "The Leviathan",
        "type": "monster",
        "hp": 400,
        "attack_min": 20,
        "attack_max": 40,
        "reward_min": 700,
        "reward_max": 1200,
        "xp": 600,
        "danger": "Extreme",
    },

    "drowned_king": {
        "name": "The Drowned King",
        "type": "boss",
        "hp": 600,
        "attack_min": 25,
        "attack_max": 50,
        "reward_min": 1200,
        "reward_max": 2000,
        "xp": 1000,
        "danger": "Legendary",
    },
}


async def _db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def initialize_monsters():

    db = await _db()

    try:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS monster_encounters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            monster_key TEXT NOT NULL,
            name TEXT NOT NULL,
            encounter_type TEXT DEFAULT 'monster',
            hp INTEGER NOT NULL,
            max_hp INTEGER NOT NULL,
            attack_min INTEGER NOT NULL,
            attack_max INTEGER NOT NULL,
            reward_min INTEGER NOT NULL,
            reward_max INTEGER NOT NULL,
            xp_reward INTEGER NOT NULL,
            danger TEXT DEFAULT 'High',
            phase INTEGER DEFAULT 1,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_monster_active
        ON monster_encounters(guild_id)
        WHERE status = 'active';

        CREATE TABLE IF NOT EXISTS monster_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            encounter_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            action TEXT DEFAULT '',
            description TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        await db.commit()

    finally:
        await db.close()


async def get_active_monster(guild_id):

    db = await _db()

    try:
        row = await (
            await db.execute("""
                SELECT *
                FROM monster_encounters
                WHERE guild_id = ?
                  AND status = 'active'
                ORDER BY id DESC
                LIMIT 1
            """, (guild_id,))
        ).fetchone()

        return row

    finally:
        await db.close()


async def start_monster_encounter(
    guild_id,
    monster_key=None
):

    active = await get_active_monster(
        guild_id
    )

    if active:
        return False, active

    if monster_key is None:
        monster_key = random.choice(
            list(MONSTERS.keys())
        )

    if monster_key not in MONSTERS:
        return False, "Unknown monster."

    monster = MONSTERS[monster_key]

    db = await _db()

    try:
        cursor = await db.execute("""
            INSERT INTO monster_encounters (
                guild_id,
                monster_key,
                name,
                encounter_type,
                hp,
                max_hp,
                attack_min,
                attack_max,
                reward_min,
                reward_max,
                xp_reward,
                danger
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            guild_id,
            monster_key,
            monster["name"],
            monster["type"],
            monster["hp"],
            monster["hp"],
            monster["attack_min"],
            monster["attack_max"],
            monster["reward_min"],
            monster["reward_max"],
            monster["xp"],
            monster["danger"],
        ))

        await db.commit()

        encounter_id = cursor.lastrowid

    finally:
        await db.close()

    return True, await get_active_monster(
        guild_id
    )


async def format_monster(guild_id):

    encounter = await get_active_monster(
        guild_id
    )

    if not encounter:
        return (
            "**SEA MONSTERS**\n"
            "The waters are quiet... for now."
        )

    return (
        "**"
        + encounter["name"].upper()
        + "**\n"
        "Type: **"
        + encounter["encounter_type"].title()
        + "**\n"
        "Danger: **"
        + encounter["danger"]
        + "**\n"
        "HP: **"
        + str(encounter["hp"])
        + "/"
        + str(encounter["max_hp"])
        + "**\n"
        "Phase: **"
        + str(encounter["phase"])
        + "**"
    )


async def attack_monster(guild_id):

    encounter = await get_active_monster(
        guild_id
    )

    if not encounter:
        return False, "There is no monster to attack.", None

    player_damage = random.randint(
        15,
        30
    )

    hp = max(
        0,
        int(encounter["hp"])
        - player_damage
    )

    enemy_damage = 0

    if hp > 0:
        enemy_damage = random.randint(
            int(encounter["attack_min"]),
            int(encounter["attack_max"])
        )

    db = await _db()

    try:
        await db.execute("""
            UPDATE monster_encounters
            SET hp = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            hp,
            encounter["id"],
        ))

        if hp <= 0:
            await db.execute("""
                UPDATE monster_encounters
                SET status = 'victory',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                encounter["id"],
            ))

        await db.commit()

    finally:
        await db.close()

    if hp <= 0:

        reward = random.randint(
            int(encounter["reward_min"]),
            int(encounter["reward_max"])
        )

        return True, (
            "**"
            + encounter["name"].upper()
            + " DEFEATED**\n"
            "The creature takes **"
            + str(player_damage)
            + "** damage and disappears beneath the waves.\n\n"
            "Recovered treasure: **"
            + str(reward)
            + " doubloons**\n"
            "Ship XP: **"
            + str(encounter["xp_reward"])
            + "**"
        ), {
            "victory": True,
            "reward": reward,
            "xp": int(encounter["xp_reward"]),
            "enemy_damage": 0,
            "name": encounter["name"],
        }

    return True, (
        "**MONSTER ATTACK**\n"
        "The crew deals **"
        + str(player_damage)
        + "** damage to "
        + encounter["name"]
        + ".\n"
        + encounter["name"]
        + " retaliates for **"
        + str(enemy_damage)
        + "** damage.\n\n"
        "HP: **"
        + str(hp)
        + "/"
        + str(encounter["max_hp"])
        + "**"
    ), {
        "victory": False,
        "reward": 0,
        "xp": 0,
        "enemy_damage": enemy_damage,
        "name": encounter["name"],
    }
