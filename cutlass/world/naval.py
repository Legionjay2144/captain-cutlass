import os
import random

import aiosqlite

from cutlass.world.combat_scaling import (
    scale_encounter_stats,
    roll_player_damage,
    ship_can_fight,
    disabled_ship_message,
)
from cutlass.world.locks import get_guild_lock


DB_PATH = os.getenv(
    "DATABASE_PATH",
    "/app/data/captain.db"
)


ENEMY_SHIPS = [
    {
        "name": "The Rusted Fang",
        "captain": "Captain Ironjaw",
        "hull": 80,
        "attack_min": 8,
        "attack_max": 18,
        "reward_min": 100,
        "reward_max": 220,
        "xp": 100,
        "danger": "Low",
    },
    {
        "name": "The Crimson Widow",
        "captain": "Red Mara",
        "hull": 130,
        "attack_min": 12,
        "attack_max": 25,
        "reward_min": 220,
        "reward_max": 450,
        "xp": 225,
        "danger": "Medium",
    },
    {
        "name": "The Drowned Crown",
        "captain": "Admiral Graves",
        "hull": 200,
        "attack_min": 18,
        "attack_max": 35,
        "reward_min": 500,
        "reward_max": 900,
        "xp": 450,
        "danger": "High",
    },
]


async def _db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def initialize_naval():

    db = await _db()

    try:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS naval_battles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            enemy_name TEXT NOT NULL,
            enemy_captain TEXT DEFAULT '',
            enemy_hull INTEGER NOT NULL,
            enemy_max_hull INTEGER NOT NULL,
            enemy_attack_min INTEGER DEFAULT 5,
            enemy_attack_max INTEGER DEFAULT 15,
            reward_min INTEGER DEFAULT 50,
            reward_max INTEGER DEFAULT 150,
            xp_reward INTEGER DEFAULT 50,
            danger TEXT DEFAULT 'Low',
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_naval_active
        ON naval_battles(guild_id, status, id DESC);

        CREATE UNIQUE INDEX IF NOT EXISTS idx_naval_one_active
        ON naval_battles(guild_id)
        WHERE status = 'active';

        CREATE TABLE IF NOT EXISTS naval_battle_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            battle_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            action TEXT DEFAULT '',
            description TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_naval_events
        ON naval_battle_events(battle_id, id);
        """)

        await db.commit()

    finally:
        await db.close()


async def get_active_battle(guild_id):

    db = await _db()

    try:
        cursor = await db.execute("""
            SELECT *
            FROM naval_battles
            WHERE guild_id = ?
              AND status = 'active'
            ORDER BY id DESC
            LIMIT 1
        """, (guild_id,))

        return await cursor.fetchone()

    finally:
        await db.close()


async def add_battle_event(
    battle_id,
    guild_id,
    action,
    description
):

    db = await _db()

    try:
        await db.execute("""
            INSERT INTO naval_battle_events (
                battle_id,
                guild_id,
                action,
                description
            )
            VALUES (?, ?, ?, ?)
        """, (
            battle_id,
            guild_id,
            action,
            description,
        ))

        await db.commit()

    finally:
        await db.close()


async def start_naval_battle(
    guild_id,
    ship=None
):
    async with get_guild_lock(guild_id):

        active = await get_active_battle(
            guild_id
        )

        if active:
            return False, active

        enemy = random.choice(
            ENEMY_SHIPS
        )

        scaled = scale_encounter_stats(
            ship,
            base_hp=enemy["hull"],
            attack_min=enemy["attack_min"],
            attack_max=enemy["attack_max"],
            reward_min=enemy["reward_min"],
            reward_max=enemy["reward_max"],
            xp_reward=enemy["xp"],
            danger=enemy["danger"],
            encounter_type="naval",
        )

        db = await _db()

        try:
            cursor = await db.execute("""
                INSERT INTO naval_battles (
                    guild_id,
                    enemy_name,
                    enemy_captain,
                    enemy_hull,
                    enemy_max_hull,
                    enemy_attack_min,
                    enemy_attack_max,
                    reward_min,
                    reward_max,
                    xp_reward,
                    danger
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                guild_id,
                enemy["name"],
                enemy["captain"],
                scaled["max_hp"],
                scaled["max_hp"],
                scaled["attack_min"],
                scaled["attack_max"],
                scaled["reward_min"],
                scaled["reward_max"],
                scaled["xp_reward"],
                enemy["danger"],
            ))

            battle_id = cursor.lastrowid

            await db.commit()

        finally:
            await db.close()

        await add_battle_event(
            battle_id,
            guild_id,
            "start",
            (
                enemy["name"]
                + " commanded by "
                + enemy["captain"]
                + " engaged the crew."
            )
        )

        return True, await get_active_battle(
            guild_id
        )


async def format_battle(guild_id):

    battle = await get_active_battle(
        guild_id
    )

    if not battle:
        return (
            "**NAVAL BATTLE**\n"
            "The horizon is clear. No enemy ship is currently engaged."
        )

    return (
        "**NAVAL BATTLE**\n"
        "Enemy: **"
        + battle["enemy_name"]
        + "**\n"
        "Captain: **"
        + battle["enemy_captain"]
        + "**\n"
        "Danger: **"
        + battle["danger"]
        + "**\n"
        "Enemy Hull: **"
        + str(battle["enemy_hull"])
        + "/"
        + str(battle["enemy_max_hull"])
        + "**\n\n"
        "Commands:\n"
        "`!c attack` — Fire on the enemy\n"
        "`!c defend` — Brace for incoming fire\n"
        "`!c board` — Attempt boarding at 35% hull or less\n"
        "`!c flee` — Attempt to escape"
    )


async def attack_enemy(
    guild_id,
    ship
):

    battle = await get_active_battle(
        guild_id
    )

    if not battle:
        return False, "There is no enemy ship to attack.", None

    if not ship_can_fight(ship):
        return (
            False,
            disabled_ship_message(ship),
            None
        )

    player_damage = roll_player_damage(
        ship,
        "naval"
    )

    enemy_hull = max(
        0,
        battle["enemy_hull"]
        - player_damage
    )

    enemy_damage = 0

    if enemy_hull > 0:
        enemy_damage = random.randint(
            battle["enemy_attack_min"],
            battle["enemy_attack_max"]
        )

    db = await _db()

    try:
        await db.execute("""
            UPDATE naval_battles
            SET enemy_hull = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            enemy_hull,
            battle["id"],
        ))

        if enemy_hull <= 0:
            await db.execute("""
                UPDATE naval_battles
                SET status = 'victory',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                battle["id"],
            ))

        await db.commit()

    finally:
        await db.close()

    if enemy_hull <= 0:

        reward = random.randint(
            battle["reward_min"],
            battle["reward_max"]
        )

        await add_battle_event(
            battle["id"],
            guild_id,
            "victory",
            (
                battle["enemy_name"]
                + " was defeated."
            )
        )

        return True, (
            "**ENEMY SHIP DEFEATED**\n"
            + battle["enemy_name"]
            + " takes **"
            + str(player_damage)
            + "** damage and slips beneath the waves.\n\n"
            "Recovered: **"
            + str(reward)
            + " doubloons**\n"
            "Ship XP: **"
            + str(battle["xp_reward"])
            + "**"
        ), {
            "victory": True,
            "reward": reward,
            "xp": battle["xp_reward"],
            "enemy_damage": 0,
            "enemy_name": battle["enemy_name"],
        }

    await add_battle_event(
        battle["id"],
        guild_id,
        "attack",
        (
            "Crew dealt "
            + str(player_damage)
            + " damage; enemy returned "
            + str(enemy_damage)
            + "."
        )
    )

    return True, (
        "**CANNONS FIRE!**\n"
        "Your broadside deals **"
        + str(player_damage)
        + "** damage.\n"
        + battle["enemy_name"]
        + " returns fire for **"
        + str(enemy_damage)
        + "** damage.\n\n"
        "Enemy Hull: **"
        + str(enemy_hull)
        + "/"
        + str(battle["enemy_max_hull"])
        + "**"
    ), {
        "victory": False,
        "reward": 0,
        "xp": 0,
        "enemy_damage": enemy_damage,
    }


async def defend(
    guild_id,
    ship=None
):

    if not ship_can_fight(ship):
        return (
            False,
            disabled_ship_message(ship),
            None
        )

    battle = await get_active_battle(
        guild_id
    )

    if not battle:
        return False, "There is no enemy to defend against.", None

    raw_damage = random.randint(
        battle["enemy_attack_min"],
        battle["enemy_attack_max"]
    )

    damage = max(
        1,
        raw_damage // 2
    )

    await add_battle_event(
        battle["id"],
        guild_id,
        "defend",
        (
            "Crew braced for impact and reduced incoming damage to "
            + str(damage)
            + "."
        )
    )

    return True, (
        "**BRACE FOR IMPACT!**\n"
        "The crew tightens the lines and turns the hull into the attack.\n"
        "Incoming damage reduced to **"
        + str(damage)
        + "**."
    ), {
        "enemy_damage": damage,
    }


async def board_enemy(
    guild_id,
    ship=None
):
    """
    Attempt to capture an enemy vessel.

    Boarding becomes available once the enemy has been
    reduced to 35% hull or less.

    Success:
        - enemy vessel is captured
        - battle ends with status 'boarded'
        - 125% treasure reward
        - normal XP reward

    Failure:
        - battle continues
        - enemy deals half retaliation damage
    """

    battle = await get_active_battle(
        guild_id
    )

    if not battle:
        return (
            False,
            "There is no enemy ship to board.",
            None
        )

    if not ship_can_fight(ship):
        return (
            False,
            disabled_ship_message(ship),
            None
        )

    enemy_hull = int(
        battle["enemy_hull"]
    )

    enemy_max_hull = max(
        1,
        int(battle["enemy_max_hull"])
    )

    hull_percent = (
        enemy_hull
        / enemy_max_hull
    )

    # Boarding is only possible once the target has been
    # sufficiently weakened.
    if hull_percent > 0.35:

        required_hull = max(
            1,
            int(enemy_max_hull * 0.35)
        )

        return (
            False,
            (
                "**TOO DANGEROUS TO BOARD!**\n"
                + battle["enemy_name"]
                + " is still fighting too strongly.\n\n"
                "Reduce the enemy to **"
                + str(required_hull)
                + " hull or less** before boarding."
            ),
            None
        )

    # -----------------------------------------------------
    # Boarding success chance
    #
    # 35% hull = roughly 55%
    # Near 0% hull = roughly 75%
    # -----------------------------------------------------

    weakness_bonus = int(
        (
            (0.35 - hull_percent)
            / 0.35
        )
        * 20
    )

    success_chance = (
        55
        + weakness_bonus
    )

    danger = str(
        battle["danger"] or ""
    ).strip().casefold()

    if danger == "high":
        success_chance -= 5

    elif danger == "extreme":
        success_chance -= 10

    success_chance = max(
        25,
        min(
            85,
            success_chance
        )
    )

    roll = random.randint(
        1,
        100
    )

    # -----------------------------------------------------
    # FAILED BOARDING
    # -----------------------------------------------------

    if roll > success_chance:

        raw_damage = random.randint(
            int(battle["enemy_attack_min"]),
            int(battle["enemy_attack_max"])
        )

        enemy_damage = max(
            1,
            raw_damage // 2
        )

        await add_battle_event(
            battle["id"],
            guild_id,
            "board_failed",
            (
                "The crew attempted to board "
                + battle["enemy_name"]
                + " but was repelled. "
                "The enemy dealt "
                + str(enemy_damage)
                + " damage during the retreat."
            )
        )

        return (
            True,
            (
                "**BOARDING REPULSED!**\n"
                "The crew swings across to **"
                + battle["enemy_name"]
                + "**, but the enemy drives them back.\n\n"
                "Retreating under fire causes **"
                + str(enemy_damage)
                + " damage**."
            ),
            {
                "victory": False,
                "boarded": False,
                "reward": 0,
                "xp": 0,
                "enemy_damage": enemy_damage,
                "success_chance": success_chance,
            }
        )

    # -----------------------------------------------------
    # SUCCESSFUL BOARDING
    # -----------------------------------------------------

    base_reward = random.randint(
        int(battle["reward_min"]),
        int(battle["reward_max"])
    )

    reward = max(
        1,
        int(round(base_reward * 1.25))
    )

    xp_reward = int(
        battle["xp_reward"]
    )

    db = await _db()

    try:

        await db.execute("""
            UPDATE naval_battles
            SET status = 'boarded',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            battle["id"],
        ))

        await db.commit()

    finally:
        await db.close()

    await add_battle_event(
        battle["id"],
        guild_id,
        "board",
        (
            "The crew successfully boarded and captured "
            + battle["enemy_name"]
            + ". Reward "
            + str(reward)
            + " doubloons and "
            + str(xp_reward)
            + " XP."
        )
    )

    return (
        True,
        (
            "**ENEMY VESSEL CAPTURED!**\n"
            "The crew storms aboard **"
            + battle["enemy_name"]
            + "** and overwhelms her defenders.\n\n"
            "**BOARDING VICTORY**\n"
            "Captured treasure: **"
            + str(reward)
            + " doubloons**\n"
            "Ship XP: **"
            + str(xp_reward)
            + "**"
        ),
        {
            "victory": True,
            "boarded": True,
            "reward": reward,
            "xp": xp_reward,
            "enemy_damage": 0,
            "success_chance": success_chance,
            "enemy_name": battle["enemy_name"],
        }
    )



async def flee_battle(guild_id):

    battle = await get_active_battle(
        guild_id
    )

    if not battle:
        return False, "There is no battle to flee from."

    success = random.randint(
        1,
        100
    ) <= 60

    if not success:
        return False, (
            "The enemy cuts off the escape route. "
            "The battle continues."
        )

    db = await _db()

    try:
        await db.execute("""
            UPDATE naval_battles
            SET status = 'fled',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            battle["id"],
        ))

        await db.commit()

    finally:
        await db.close()

    await add_battle_event(
        battle["id"],
        guild_id,
        "flee",
        "The crew successfully escaped the battle."
    )

    return True, (
        "Full sails! The crew escapes "
        + battle["enemy_name"]
        + " and disappears over the horizon."
    )
