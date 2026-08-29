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

    # =====================================================
    # LOW DANGER
    # Small-time raiders, smugglers, and inexperienced
    # captains. Common encounters for a young crew.
    # =====================================================

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
        "name": "The Crooked Minnow",
        "captain": "Barnacle Bill Brigg",
        "hull": 70,
        "attack_min": 7,
        "attack_max": 16,
        "reward_min": 90,
        "reward_max": 190,
        "xp": 90,
        "danger": "Low",
    },

    {
        "name": "The Salty Turnip",
        "captain": "Old Ned Turnbucket",
        "hull": 75,
        "attack_min": 7,
        "attack_max": 17,
        "reward_min": 95,
        "reward_max": 210,
        "xp": 95,
        "danger": "Low",
    },

    {
        "name": "The Coin Snatcher",
        "captain": "Silas Quickpurse",
        "hull": 85,
        "attack_min": 9,
        "attack_max": 18,
        "reward_min": 110,
        "reward_max": 240,
        "xp": 110,
        "danger": "Low",
    },

    {
        "name": "The Leaky Lantern",
        "captain": "Molly Three-Buckets",
        "hull": 90,
        "attack_min": 8,
        "attack_max": 19,
        "reward_min": 120,
        "reward_max": 250,
        "xp": 115,
        "danger": "Low",
    },

    # =====================================================
    # MEDIUM DANGER
    # Established privateers and pirate hunters.
    # =====================================================

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
        "name": "The Black Kettle",
        "captain": "Captain Bram Coalhand",
        "hull": 125,
        "attack_min": 11,
        "attack_max": 24,
        "reward_min": 210,
        "reward_max": 430,
        "xp": 215,
        "danger": "Medium",
    },

    {
        "name": "The Hangman's Smile",
        "captain": "Eliza Grim",
        "hull": 140,
        "attack_min": 13,
        "attack_max": 27,
        "reward_min": 250,
        "reward_max": 480,
        "xp": 245,
        "danger": "Medium",
    },

    {
        "name": "The Powder Monkey",
        "captain": "Gunner Gideon Flint",
        "hull": 150,
        "attack_min": 14,
        "attack_max": 28,
        "reward_min": 270,
        "reward_max": 520,
        "xp": 260,
        "danger": "Medium",
    },

    # =====================================================
    # HIGH DANGER
    # Veteran captains commanding heavily armed vessels.
    # =====================================================

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

    {
        "name": "The Widowmaker",
        "captain": "Captain Vex Blackthorn",
        "hull": 220,
        "attack_min": 20,
        "attack_max": 38,
        "reward_min": 560,
        "reward_max": 980,
        "xp": 500,
        "danger": "High",
    },

    {
        "name": "The King's Regret",
        "captain": "Commodore Elias Crow",
        "hull": 240,
        "attack_min": 21,
        "attack_max": 40,
        "reward_min": 620,
        "reward_max": 1050,
        "xp": 550,
        "danger": "High",
    },

    # =====================================================
    # EXTREME DANGER
    # Famous killers of pirate crews. These should hurt.
    # =====================================================

    {
        "name": "The Devil's Due",
        "captain": "Madame Seraphine Vane",
        "hull": 300,
        "attack_min": 25,
        "attack_max": 46,
        "reward_min": 850,
        "reward_max": 1450,
        "xp": 725,
        "danger": "Extreme",
    },

    {
        "name": "The Iron Gallows",
        "captain": "Executioner Thorne",
        "hull": 340,
        "attack_min": 27,
        "attack_max": 50,
        "reward_min": 1000,
        "reward_max": 1650,
        "xp": 850,
        "danger": "Extreme",
    },

    # =====================================================
    # LEGENDARY DANGER
    # Rare naval terror. Not technically a boss encounter,
    # but powerful enough that fleeing may be wise.
    # =====================================================

    {
        "name": "The Pale Reaper",
        "captain": "Lord Mordecai Blackwake",
        "hull": 425,
        "attack_min": 30,
        "attack_max": 56,
        "reward_min": 1400,
        "reward_max": 2300,
        "xp": 1150,
        "danger": "Legendary",
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


def get_boarding_status(battle):
    """
    Return the live boarding state for a naval battle.

    This is the single source of truth used by both
    !c battle and board_enemy().
    """

    enemy_hull = max(
        0,
        int(battle["enemy_hull"])
    )

    enemy_max_hull = max(
        1,
        int(battle["enemy_max_hull"])
    )

    required_hull = max(
        1,
        int(enemy_max_hull * 0.35)
    )

    damage_needed = max(
        0,
        enemy_hull - required_hull
    )

    hull_percent = (
        enemy_hull
        / enemy_max_hull
    )

    ready = (
        hull_percent <= 0.35
    )

    success_chance = None

    if ready:

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

    return {
        "ready": ready,
        "enemy_hull": enemy_hull,
        "enemy_max_hull": enemy_max_hull,
        "required_hull": required_hull,
        "damage_needed": damage_needed,
        "success_chance": success_chance,
    }


async def force_withdraw_battle(guild_id):
    """
    Terminate the guild's active naval encounter because the
    Living Ship became non-operational.

    This is intentionally idempotent. Only an encounter that is
    still active may transition to player_disabled.
    """

    db = await _db()

    try:
        battle = await (
            await db.execute(
                """
                SELECT *
                FROM naval_battles
                WHERE guild_id = ?
                  AND status = 'active'
                ORDER BY id DESC
                LIMIT 1
                """,
                (guild_id,),
            )
        ).fetchone()

        if not battle:
            return False, None

        cursor = await db.execute(
            """
            UPDATE naval_battles
            SET status = 'player_disabled',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status = 'active'
            """,
            (battle["id"],),
        )

        changed = cursor.rowcount == 1

        if changed:
            await db.execute(
                """
                INSERT INTO naval_battle_events (
                    battle_id,
                    guild_id,
                    action,
                    description
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    battle["id"],
                    guild_id,
                    "player_disabled",
                    (
                        "The Living Ship became non-operational. "
                        "The crew was forced to withdraw; "
                        + battle["enemy_name"]
                        + " remained undefeated."
                    ),
                ),
            )

        await db.commit()

        return changed, dict(battle)

    finally:
        await db.close()

async def format_battle(guild_id):

    battle = await get_active_battle(
        guild_id
    )

    if not battle:
        return (
            "**NAVAL BATTLE**\n"
            "The horizon is clear. No enemy ship is currently engaged."
        )

    boarding = get_boarding_status(
        battle
    )

    text = (
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
        + str(boarding["enemy_hull"])
        + "/"
        + str(boarding["enemy_max_hull"])
        + "**\n\n"
        "**BOARDING STATUS**\n"
    )

    if boarding["ready"]:

        text += (
            "Status: **READY**\n"
            "Boarding Chance: **"
            + str(boarding["success_chance"])
            + "%**\n"
            "Enemy Hull Requirement: **"
            + str(boarding["required_hull"])
            + " or lower**"
        )

    else:

        text += (
            "Status: **LOCKED**\n"
            "Required Enemy Hull: **"
            + str(boarding["required_hull"])
            + " or lower**\n"
            "Damage Needed: **"
            + str(boarding["damage_needed"])
            + "**"
        )

    text += (
        "\n\nCommands:\n"
        "`!c attack` — Fire on the enemy\n"
        "`!c defend` — Brace for incoming fire\n"
        "`!c board` — Attempt to capture the enemy vessel\n"
        "`!c flee` — Attempt to escape"
    )

    return text


async def naval_ship_is_operational(
    guild_id,
    ship
):
    """
    Defense-in-depth operational check for the naval engine.

    Command handlers already enforce this rule, but the
    engine also verifies it so direct/internal callers
    cannot fight with a recovering ship.
    """

    if not ship_can_fight(ship):
        return False

    from ship_world import (
        get_ship_operational_status
    )

    status = await get_ship_operational_status(
        guild_id
    )

    return bool(
        status["operational"]
    )


async def attack_enemy(
    guild_id,
    ship,
    damage_multiplier=1.0
):
    """
    Perform one atomic naval attack for a guild.
    """

    async with get_guild_lock(guild_id):
        return await _attack_enemy_unlocked(
            guild_id,
            ship,
            damage_multiplier=damage_multiplier,
        )


async def defend(
    guild_id,
    ship=None
):
    """
    Perform one atomic naval defense action.
    """

    async with get_guild_lock(guild_id):
        return await _defend_unlocked(
            guild_id,
            ship=ship
        )


async def board_enemy(
    guild_id,
    ship=None
):
    """
    Perform one atomic boarding attempt.
    """

    async with get_guild_lock(guild_id):
        return await _board_enemy_unlocked(
            guild_id,
            ship=ship
        )


async def flee_battle(
    guild_id
):
    """
    Perform one atomic flee attempt.
    """

    async with get_guild_lock(guild_id):
        return await _flee_battle_unlocked(
            guild_id
        )



# =========================================================
# NAVAL COMBAT EVENTS
# =========================================================

NAVAL_EVENT_CHANCE = 18

NAVAL_COMBAT_EVENTS = (
    "powder_keg",
    "exposed_broadside",
    "rogue_wave",
    "sudden_fog",
    "crew_rally",
    "cannon_jam",
)


def roll_naval_combat_event():
    """
    Return a naval combat event or None.

    Events occur on 18% of eligible naval combat actions.
    """
    if random.randint(1, 100) > NAVAL_EVENT_CHANCE:
        return None

    return random.choice(
        NAVAL_COMBAT_EVENTS
    )


def apply_naval_combat_event(
    event,
    *,
    player_damage,
    enemy_damage,
    action,
):
    """
    Apply one naval combat event to an attack/defend exchange.

    Returns:
        {
            "event": str | None,
            "title": str,
            "description": str,
            "player_damage": int,
            "enemy_damage": int,
        }

    player_damage:
        Damage being dealt to the enemy.

    enemy_damage:
        Damage being returned to the Living Ship.

    The command handler remains responsible for applying
    enemy_damage to the player's actual ship.
    """

    player_damage = max(
        0,
        int(player_damage)
    )

    enemy_damage = max(
        0,
        int(enemy_damage)
    )

    result = {
        "event": event,
        "title": "",
        "description": "",
        "player_damage": player_damage,
        "enemy_damage": enemy_damage,
    }

    if event is None:
        return result

    # -----------------------------------------------------
    # POWDER KEG
    # Extra damage to the enemy vessel.
    # -----------------------------------------------------

    if event == "powder_keg":

        bonus = max(
            4,
            int(round(
                max(1, player_damage) * 0.35
            ))
        )

        result["player_damage"] += bonus

        result["title"] = "POWDER KEG IGNITES!"

        result["description"] = (
            "A lucky shot reaches loose powder aboard the "
            "enemy vessel! The explosion adds **"
            + str(bonus)
            + "** damage."
        )

    # -----------------------------------------------------
    # EXPOSED BROADSIDE
    # Strong offensive opportunity.
    # -----------------------------------------------------

    elif event == "exposed_broadside":

        bonus = max(
            3,
            int(round(
                max(1, player_damage) * 0.25
            ))
        )

        result["player_damage"] += bonus

        result["title"] = "EXPOSED BROADSIDE!"

        result["description"] = (
            "The enemy turns too sharply and exposes her "
            "flank. The crew pours fire into the opening "
            "for **"
            + str(bonus)
            + "** bonus damage."
        )

    # -----------------------------------------------------
    # ROGUE WAVE
    # Both vessels suffer damage.
    # -----------------------------------------------------

    elif event == "rogue_wave":

        enemy_bonus = max(
            3,
            int(round(
                max(1, player_damage) * 0.20
            ))
        )

        ship_bonus = max(
            2,
            int(round(
                max(1, enemy_damage) * 0.20
            ))
        )

        result["player_damage"] += enemy_bonus
        result["enemy_damage"] += ship_bonus

        result["title"] = "ROGUE WAVE!"

        result["description"] = (
            "A wall of black water crashes through the "
            "battle. The enemy suffers **"
            + str(enemy_bonus)
            + "** extra damage and the Living Ship takes "
            "**"
            + str(ship_bonus)
            + "** extra damage."
        )

    # -----------------------------------------------------
    # SUDDEN FOG
    # Enemy retaliation is reduced.
    # -----------------------------------------------------

    elif event == "sudden_fog":

        before = result["enemy_damage"]

        result["enemy_damage"] = max(
            0,
            before // 2
        )

        prevented = (
            before
            - result["enemy_damage"]
        )

        result["title"] = "SUDDEN FOG!"

        result["description"] = (
            "A thick bank of fog swallows the ships. "
            "Enemy gunners lose their aim, preventing **"
            + str(prevented)
            + "** incoming damage."
        )

    # -----------------------------------------------------
    # CREW RALLY
    # The crew squeezes extra damage from the action.
    # -----------------------------------------------------

    elif event == "crew_rally":

        bonus = max(
            2,
            int(round(
                max(1, player_damage) * 0.20
            ))
        )

        result["player_damage"] += bonus

        result["title"] = "CREW RALLY!"

        result["description"] = (
            "The crew answers the Captain's call and works "
            "the guns like devils, adding **"
            + str(bonus)
            + "** damage."
        )

    # -----------------------------------------------------
    # CANNON JAM
    # Outgoing damage is reduced, never below 1 when the
    # original attack was capable of dealing damage.
    # -----------------------------------------------------

    elif event == "cannon_jam":

        before = result["player_damage"]

        if before > 0:
            result["player_damage"] = max(
                1,
                int(round(
                    before * 0.60
                ))
            )

        lost = (
            before
            - result["player_damage"]
        )

        result["title"] = "CANNON JAM!"

        result["description"] = (
            "A gun crew loses precious seconds clearing a "
            "jam. The salvo loses **"
            + str(lost)
            + "** damage."
        )

    return result


async def record_naval_combat_event(
    battle,
    guild_id,
    event_result,
):
    """
    Persist a triggered random naval event.
    """

    event = event_result.get(
        "event"
    )

    if not event:
        return

    await add_battle_event(
        battle["id"],
        guild_id,
        "naval_event_" + event,
        (
            event_result["title"]
            + " "
            + event_result["description"]
        )
    )


def format_naval_combat_event(
    event_result
):
    """
    Format an event for the Discord combat response.
    """

    if not event_result:
        return ""

    if not event_result.get("event"):
        return ""

    return (
        "\n\n**"
        + event_result["title"]
        + "**\n"
        + event_result["description"]
    )


async def _attack_enemy_unlocked(
    guild_id,
    ship,
    damage_multiplier=1.0
):

    battle = await get_active_battle(
        guild_id
    )

    if not battle:
        return (
            False,
            "There is no enemy ship to attack.",
            None
        )

    if not await naval_ship_is_operational(
        guild_id,
        ship
    ):
        return (
            False,
            disabled_ship_message(ship),
            None
        )

    # -----------------------------------------------------
    # BASE COMBAT ROLLS
    # -----------------------------------------------------

    player_damage = roll_player_damage(
        ship,
        "naval"
    )

    player_damage = max(
        1,
        int(round(
            player_damage
            * max(
                0.0,
                float(damage_multiplier)
            )
        ))
    )

    enemy_damage = random.randint(
        int(battle["enemy_attack_min"]),
        int(battle["enemy_attack_max"])
    )

    # -----------------------------------------------------
    # RANDOM NAVAL EVENT
    # -----------------------------------------------------

    naval_event = roll_naval_combat_event()

    event_result = apply_naval_combat_event(
        naval_event,
        player_damage=player_damage,
        enemy_damage=enemy_damage,
        action="attack",
    )

    player_damage = int(
        event_result["player_damage"]
    )

    enemy_damage = int(
        event_result["enemy_damage"]
    )

    enemy_hull = max(
        0,
        int(battle["enemy_hull"])
        - player_damage
    )

    # A destroyed enemy cannot return fire.
    if enemy_hull <= 0:
        enemy_damage = 0

    # -----------------------------------------------------
    # DATABASE UPDATE
    # -----------------------------------------------------

    db = await _db()

    try:

        await db.execute(
            """
            UPDATE naval_battles
            SET enemy_hull = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status = 'active'
            """,
            (
                enemy_hull,
                battle["id"],
            )
        )

        victory_claimed = False

        if enemy_hull <= 0:

            cursor = await db.execute(
                """
                UPDATE naval_battles
                SET status = 'victory',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                  AND status = 'active'
                """,
                (
                    battle["id"],
                )
            )

            victory_claimed = (
                cursor.rowcount == 1
            )

        await db.commit()

    finally:
        await db.close()

    # -----------------------------------------------------
    # TERMINAL OWNERSHIP
    # -----------------------------------------------------

    if enemy_hull <= 0 and not victory_claimed:
        return (
            False,
            "The battle has already ended.",
            None
        )

    # Record the random event only after this action has
    # confirmed it still owns any terminal transition.
    await record_naval_combat_event(
        battle,
        guild_id,
        event_result,
    )

    event_text = format_naval_combat_event(
        event_result
    )

    # -----------------------------------------------------
    # VICTORY
    # -----------------------------------------------------

    if enemy_hull <= 0:

        reward = random.randint(
            int(battle["reward_min"]),
            int(battle["reward_max"])
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

        return (
            True,
            (
                "**ENEMY SHIP DEFEATED**\n"
                + battle["enemy_name"]
                + " takes **"
                + str(player_damage)
                + "** damage and slips beneath the waves."
                + event_text
                + "\n\nRecovered: **"
                + str(reward)
                + " doubloons**\n"
                "Ship XP: **"
                + str(battle["xp_reward"])
                + "**"
            ),
            {
                "victory": True,
                "reward": reward,
                "xp": int(battle["xp_reward"]),
                "enemy_damage": 0,
                "enemy_name": battle["enemy_name"],
                "naval_event": naval_event,
                "player_damage": player_damage,
            }
        )

    # -----------------------------------------------------
    # BATTLE CONTINUES
    # -----------------------------------------------------

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

    return (
        True,
        (
            "**CANNONS FIRE!**\n"
            "Your broadside deals **"
            + str(player_damage)
            + "** damage.\n"
            + battle["enemy_name"]
            + " returns fire for **"
            + str(enemy_damage)
            + "** damage."
            + event_text
            + "\n\nEnemy Hull: **"
            + str(enemy_hull)
            + "/"
            + str(battle["enemy_max_hull"])
            + "**"
        ),
        {
            "victory": False,
            "reward": 0,
            "xp": 0,
            "enemy_damage": enemy_damage,
            "enemy_name": battle["enemy_name"],
            "naval_event": naval_event,
            "player_damage": player_damage,
        }
    )



async def _defend_unlocked(
    guild_id,
    ship=None
):

    if not await naval_ship_is_operational(
        guild_id,
        ship
    ):
        return (
            False,
            disabled_ship_message(ship),
            None
        )

    battle = await get_active_battle(
        guild_id
    )

    if not battle:
        return (
            False,
            "There is no enemy to defend against.",
            None
        )

    # Defend sacrifices offensive power for survivability.
    #
    # 15% chance to evade the enemy salvo completely.
    # Otherwise incoming damage is reduced by 50%.
    # Counterfire begins at 35% normal naval damage.

    raw_damage = random.randint(
        int(battle["enemy_attack_min"]),
        int(battle["enemy_attack_max"])
    )

    evade_roll = random.randint(
        1,
        100
    )

    evaded = (
        evade_roll <= 15
    )

    if evaded:
        enemy_damage = 0
    else:
        enemy_damage = max(
            1,
            raw_damage // 2
        )

    normal_damage = roll_player_damage(
        ship,
        "naval"
    )

    counter_damage = max(
        1,
        int(round(
            normal_damage * 0.35
        ))
    )

    # -----------------------------------------------------
    # RANDOM NAVAL EVENT
    # -----------------------------------------------------

    naval_event = roll_naval_combat_event()

    event_result = apply_naval_combat_event(
        naval_event,
        player_damage=counter_damage,
        enemy_damage=enemy_damage,
        action="defend",
    )

    counter_damage = int(
        event_result["player_damage"]
    )

    enemy_damage = int(
        event_result["enemy_damage"]
    )

    enemy_hull = max(
        0,
        int(battle["enemy_hull"])
        - counter_damage
    )

    # Counterfire destroyed the enemy before it could
    # complete the exchange.
    if enemy_hull <= 0:
        enemy_damage = 0

    # -----------------------------------------------------
    # DATABASE UPDATE
    # -----------------------------------------------------

    db = await _db()

    try:

        await db.execute(
            """
            UPDATE naval_battles
            SET enemy_hull = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status = 'active'
            """,
            (
                enemy_hull,
                battle["id"],
            )
        )

        victory_claimed = False

        if enemy_hull <= 0:

            cursor = await db.execute(
                """
                UPDATE naval_battles
                SET status = 'victory',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                  AND status = 'active'
                """,
                (
                    battle["id"],
                )
            )

            victory_claimed = (
                cursor.rowcount == 1
            )

        await db.commit()

    finally:
        await db.close()

    if enemy_hull <= 0 and not victory_claimed:
        return (
            False,
            "The battle has already ended.",
            None
        )

    await record_naval_combat_event(
        battle,
        guild_id,
        event_result,
    )

    event_text = format_naval_combat_event(
        event_result
    )

    # -----------------------------------------------------
    # VICTORY
    # -----------------------------------------------------

    if enemy_hull <= 0:

        reward = random.randint(
            int(battle["reward_min"]),
            int(battle["reward_max"])
        )

        await add_battle_event(
            battle["id"],
            guild_id,
            "defend_victory",
            (
                "The crew destroyed "
                + battle["enemy_name"]
                + " with defensive counterfire."
            )
        )

        return (
            True,
            (
                "**COUNTERFIRE VICTORY!**\n"
                "The crew braces against the attack and "
                "fires a disciplined counter-broadside.\n"
                + battle["enemy_name"]
                + " takes **"
                + str(counter_damage)
                + "** damage and is destroyed."
                + event_text
                + "\n\nRecovered: **"
                + str(reward)
                + " doubloons**\n"
                "Ship XP: **"
                + str(battle["xp_reward"])
                + "**"
            ),
            {
                "victory": True,
                "reward": reward,
                "xp": int(battle["xp_reward"]),
                "enemy_damage": 0,
                "enemy_name": battle["enemy_name"],
                "defended": True,
                "evaded": evaded,
                "counter_damage": counter_damage,
                "naval_event": naval_event,
            }
        )

    # -----------------------------------------------------
    # DEFENSE TEXT
    # -----------------------------------------------------

    if evaded and enemy_damage == 0:

        defense_text = (
            "**EVASIVE DEFENSE!**\n"
            "The helm answers perfectly and the enemy "
            "salvo tears through empty water.\n"
            "**Incoming damage: 0**"
        )

    else:

        defense_text = (
            "**BRACE FOR IMPACT!**\n"
            "The crew angles the hull against the "
            "enemy broadside.\n"
            "Base defensive damage: **"
            + str(
                0
                if evaded
                else max(
                    1,
                    raw_damage // 2
                )
            )
            + "**\n"
            "Final incoming damage: **"
            + str(enemy_damage)
            + "**."
        )

    await add_battle_event(
        battle["id"],
        guild_id,
        "defend",
        (
            "Crew defended against "
            + str(raw_damage)
            + " potential damage, received "
            + str(enemy_damage)
            + ", and returned "
            + str(counter_damage)
            + " counterfire damage."
        )
    )

    return (
        True,
        (
            defense_text
            + "\n\n**COUNTERFIRE**\n"
            "A controlled return broadside deals **"
            + str(counter_damage)
            + "** damage."
            + event_text
            + "\n"
            "Enemy Hull: **"
            + str(enemy_hull)
            + "/"
            + str(battle["enemy_max_hull"])
            + "**"
        ),
        {
            "victory": False,
            "reward": 0,
            "xp": 0,
            "enemy_damage": enemy_damage,
            "enemy_name": battle["enemy_name"],
            "defended": True,
            "evaded": evaded,
            "counter_damage": counter_damage,
            "naval_event": naval_event,
        }
    )


async def _board_enemy_unlocked(
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

    if not await naval_ship_is_operational(
        guild_id,
        ship
    ):
        return (
            False,
            disabled_ship_message(ship),
            None
        )

    boarding = get_boarding_status(
        battle
    )

    enemy_hull = boarding[
        "enemy_hull"
    ]

    enemy_max_hull = boarding[
        "enemy_max_hull"
    ]

    # Boarding is only possible once the target has been
    # sufficiently weakened.
    if not boarding["ready"]:

        return (
            False,
            (
                "**TOO DANGEROUS TO BOARD!**\n"
                + battle["enemy_name"]
                + " is still fighting too strongly.\n\n"
                "Reduce the enemy to **"
                + str(boarding["required_hull"])
                + " hull or less** before boarding.\n"
                "Damage still needed: **"
                + str(boarding["damage_needed"])
                + "**."
            ),
            None
        )

    success_chance = int(
        boarding["success_chance"]
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

        # Failed boarding leaves the crew exposed.
        # Retaliation is 125% of the enemy's normal roll.
        enemy_damage = max(
            1,
            int(round(
                raw_damage * 1.25
            ))
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

        cursor = await db.execute("""
            UPDATE naval_battles
            SET status = 'boarded',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status = 'active'
        """, (
            battle["id"],
        ))

        changed = (
            cursor.rowcount == 1
        )

        await db.commit()

    finally:
        await db.close()

    if not changed:
        return (
            False,
            "The battle is no longer active.",
            None
        )

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



async def _flee_battle_unlocked(guild_id):

    battle = await get_active_battle(
        guild_id
    )

    if not battle:
        return (
            False,
            "There is no battle to flee from.",
            None
        )

    # More dangerous enemies are harder to disengage from.

    danger = str(
        battle["danger"] or ""
    ).strip().casefold()

    flee_chances = {
        "low": 75,
        "medium": 65,
        "high": 55,
        "extreme": 45,
        "legendary": 35,
    }

    success_chance = flee_chances.get(
        danger,
        60
    )

    roll = random.randint(
        1,
        100
    )

    success = (
        roll <= success_chance
    )

    # -----------------------------------------------------
    # FAILED ESCAPE
    # -----------------------------------------------------

    if not success:

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
            "flee_failed",
            (
                "The crew attempted to flee "
                + battle["enemy_name"]
                + " but was intercepted. "
                "The enemy dealt "
                + str(enemy_damage)
                + " damage."
            )
        )

        return (
            True,
            (
                "**ESCAPE CUT OFF!**\n"
                + battle["enemy_name"]
                + " intercepts the Living Ship before "
                "she can break away.\n"
                "The retreat exposes the hull to **"
                + str(enemy_damage)
                + "** damage.\n\n"
                "Escape chance: **"
                + str(success_chance)
                + "%**\n"
                "**The battle continues.**"
            ),
            {
                "victory": False,
                "fled": False,
                "reward": 0,
                "xp": 0,
                "enemy_damage": enemy_damage,
                "enemy_name": battle["enemy_name"],
                "success_chance": success_chance,
            }
        )

    # -----------------------------------------------------
    # SUCCESSFUL ESCAPE
    # -----------------------------------------------------

    db = await _db()

    try:

        cursor = await db.execute(
            """
            UPDATE naval_battles
            SET status = 'fled',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status = 'active'
            """,
            (
                battle["id"],
            )
        )

        changed = (
            cursor.rowcount == 1
        )

        await db.commit()

    finally:
        await db.close()

    if not changed:

        return (
            False,
            "The battle is no longer active.",
            None
        )

    await add_battle_event(
        battle["id"],
        guild_id,
        "flee",
        (
            "The crew successfully escaped "
            + battle["enemy_name"]
            + "."
        )
    )

    return (
        True,
        (
            "**SUCCESSFUL WITHDRAWAL**\n"
            "Full sails! The crew escapes **"
            + battle["enemy_name"]
            + "** and disappears over the horizon.\n\n"
            "Escape chance: **"
            + str(success_chance)
            + "%**"
        ),
        {
            "victory": False,
            "fled": True,
            "reward": 0,
            "xp": 0,
            "enemy_damage": 0,
            "enemy_name": battle["enemy_name"],
            "success_chance": success_chance,
        }
    )

