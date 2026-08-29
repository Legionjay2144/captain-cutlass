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

    "last_jailer": {
        "name": "The Last Jailer",
        "hp": 500,
        "attack_min": 23,
        "attack_max": 40,
        "reward_min": 1150,
        "reward_max": 1800,
        "xp": 950,
        "danger": "Extreme",
        "phases": 2,
    },

    "admiral_coldgrave": {
        "name": "Admiral Coldgrave",
        "hp": 725,
        "attack_min": 30,
        "attack_max": 50,
        "reward_min": 1900,
        "reward_max": 3000,
        "xp": 1600,
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


async def add_boss_event(
    boss_id,
    guild_id,
    action,
    description
):
    db = await _db()

    try:
        await db.execute("""
            INSERT INTO boss_events (
                boss_id,
                guild_id,
                action,
                description
            )
            VALUES (?, ?, ?, ?)
        """, (
            boss_id,
            guild_id,
            action,
            description,
        ))

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
    boss_key,
    ship=None
):
    async with get_guild_lock(guild_id):

        active = await get_active_boss(
            guild_id
        )

        if active:
            return False, active

        if boss_key not in BOSSES:
            return False, "Unknown boss."

        boss = BOSSES[boss_key]

        scaled = scale_encounter_stats(
            ship,
            base_hp=boss["hp"],
            attack_min=boss["attack_min"],
            attack_max=boss["attack_max"],
            reward_min=boss["reward_min"],
            reward_max=boss["reward_max"],
            xp_reward=boss["xp"],
            danger=boss["danger"],
            encounter_type="boss",
        )

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
                scaled["max_hp"],
                scaled["max_hp"],
                scaled["attack_min"],
                scaled["attack_max"],
                scaled["reward_min"],
                scaled["reward_max"],
                scaled["xp_reward"],
                boss["danger"],
                boss["phases"],
            ))

            await db.commit()

        finally:
            await db.close()

        active_boss = await get_active_boss(
            guild_id
        )

        if active_boss:
            await add_boss_event(
                active_boss["id"],
                guild_id,
                "start",
                (
                    active_boss["name"]
                    + " entered combat with the crew."
                )
            )

        return True, active_boss


async def force_withdraw_boss(guild_id):
    """
    Terminate the active boss encounter because the Living Ship
    became non-operational.

    The boss remains undefeated and no victory rewards are
    generated here.
    """

    db = await _db()

    try:
        boss = await (
            await db.execute(
                """
                SELECT *
                FROM boss_encounters
                WHERE guild_id = ?
                  AND status = 'active'
                ORDER BY id DESC
                LIMIT 1
                """,
                (guild_id,),
            )
        ).fetchone()

        if not boss:
            return False, None

        cursor = await db.execute(
            """
            UPDATE boss_encounters
            SET status = 'player_disabled',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status = 'active'
            """,
            (boss["id"],),
        )

        changed = cursor.rowcount == 1

        if changed:
            await db.execute(
                """
                INSERT INTO boss_events (
                    boss_id,
                    guild_id,
                    action,
                    description
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    boss["id"],
                    guild_id,
                    "player_disabled",
                    (
                        "The Living Ship became non-operational. "
                        "The crew was forced to withdraw from "
                        + boss["name"]
                        + "; the boss remained undefeated."
                    ),
                ),
            )

        await db.commit()

        return changed, dict(boss)

    finally:
        await db.close()

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



# =========================================================
# BOSS PHASE MECHANICS
# =========================================================

BOSS_PHASE_MECHANICS = {

    "skullfin_guardian": {
        1: {
            "name": "Guardian's Watch",
            "enemy_damage_mult": 1.00,
            "defend_mult": 0.50,
        },
        2: {
            "name": "Blood in the Water",
            "enemy_damage_mult": 1.25,
            "defend_mult": 0.50,
        },
    },

    "drowned_captain": {
        1: {
            "name": "Dead Man's Command",
            "enemy_damage_mult": 1.00,
            "defend_mult": 0.50,
        },
        2: {
            "name": "All Hands Below",
            "enemy_damage_mult": 1.20,
            "defend_mult": 0.50,
        },
    },

    "drowned_king": {
        1: {
            "name": "Sunken Throne",
            "enemy_damage_mult": 1.00,
            "defend_mult": 0.50,
        },
        2: {
            "name": "Call of the Abyss",
            "enemy_damage_mult": 1.20,

            # Only 40% blocked:
            # player receives 60%.
            "defend_mult": 0.60,
        },
        3: {
            "name": "Wrath of the Deep",
            "enemy_damage_mult": 1.45,
            "defend_mult": 0.60,
        },
    },

    "last_jailer": {
        1: {
            "name": "Keeper of the Gallows",
            "enemy_damage_mult": 1.00,
            "defend_mult": 0.50,
        },
        2: {
            "name": "Break the Chains",
            "enemy_damage_mult": 1.30,
            "defend_mult": 0.55,
        },
    },

    "admiral_coldgrave": {
        1: {
            "name": "Frozen Command",
            "enemy_damage_mult": 1.00,
            "defend_mult": 0.50,
        },
        2: {
            "name": "Broadside Beneath the Ice",
            "enemy_damage_mult": 1.25,
            "defend_mult": 0.55,
        },
        3: {
            "name": "Coldgrave's Last Stand",
            "enemy_damage_mult": 1.50,
            "defend_mult": 0.60,
        },
    },
}


def calculate_boss_phase(
    hp,
    max_hp,
    max_phase,
):
    """
    Determine boss phase from remaining HP.

    Two-phase bosses:
        Phase 2 at <= 50%.

    Three-phase bosses:
        Phase 2 at <= 65%.
        Phase 3 at <= 30%.
    """

    hp = max(
        0,
        int(hp)
    )

    max_hp = max(
        1,
        int(max_hp)
    )

    max_phase = max(
        1,
        int(max_phase)
    )

    ratio = hp / max_hp

    if max_phase >= 3:

        if ratio <= 0.30:
            return 3

        if ratio <= 0.65:
            return 2

        return 1

    if max_phase == 2:

        if ratio <= 0.50:
            return 2

        return 1

    return 1


def get_boss_phase_data(
    boss_key,
    phase,
):
    phases = BOSS_PHASE_MECHANICS.get(
        str(boss_key),
        {}
    )

    return phases.get(
        int(phase),
        {
            "name": "Unknown Phase",
            "enemy_damage_mult": 1.00,
            "defend_mult": 0.50,
        }
    )


def boss_phase_attack_range(
    boss,
    phase,
):
    """
    Preserve the existing +4/+7 numerical escalation.
    """

    phase = max(
        1,
        int(phase)
    )

    return (
        int(boss["attack_min"])
        + ((phase - 1) * 4),

        int(boss["attack_max"])
        + ((phase - 1) * 7),
    )


def apply_boss_phase_retaliation(
    boss_key,
    phase,
    enemy_damage,
    *,
    special_roll=None,
):
    data = get_boss_phase_data(
        boss_key,
        phase,
    )

    final_damage = max(
        0,
        int(round(
            int(enemy_damage)
            * float(
                data.get(
                    "enemy_damage_mult",
                    1.00
                )
            )
        ))
    )

    special_name = None
    special_text = ""

    if special_roll is None:
        special_roll = random.randint(
            1,
            100
        )

    if (
        boss_key == "skullfin_guardian"
        and int(phase) == 2
        and special_roll <= 20
    ):

        bonus = max(
            1,
            int(round(
                final_damage * 0.30
            ))
        )

        final_damage += bonus
        special_name = "rending_bite"

        special_text = (
            "**RENDING BITE!**\n"
            "The Guardian tears into the Living Ship "
            "for **"
            + str(bonus)
            + "** additional damage."
        )

    elif (
        boss_key == "drowned_captain"
        and int(phase) == 2
        and special_roll <= 25
    ):

        bonus = max(
            1,
            int(round(
                final_damage * 0.35
            ))
        )

        final_damage += bonus
        special_name = "ghostly_broadside"

        special_text = (
            "**GHOSTLY BROADSIDE!**\n"
            "Spectral cannons rake the Living Ship "
            "for **"
            + str(bonus)
            + "** additional damage."
        )

    elif (
        boss_key == "drowned_king"
        and int(phase) == 3
        and special_roll <= 20
    ):

        bonus = max(
            1,
            int(round(
                final_damage * 0.30
            ))
        )

        final_damage += bonus
        special_name = "abyssal_surge"

        special_text = (
            "**ABYSSAL SURGE!**\n"
            "The black sea rises at the King's command "
            "for **"
            + str(bonus)
            + "** additional damage."
        )

    return (
        final_damage,
        special_name,
        special_text,
    )


def apply_boss_defense(
    boss_key,
    phase,
    raw_damage,
):
    """
    Apply phase-specific defensive effectiveness.
    """

    data = get_boss_phase_data(
        boss_key,
        phase,
    )

    multiplier = float(
        data.get(
            "defend_mult",
            0.50
        )
    )

    return max(
        1,
        int(round(
            int(raw_damage)
            * multiplier
        ))
    )


def format_boss_phase_transition(
    boss_key,
    phase,
):
    data = get_boss_phase_data(
        boss_key,
        phase,
    )

    numerals = {
        1: "I",
        2: "II",
        3: "III",
    }

    return (
        "**PHASE "
        + numerals.get(
            int(phase),
            str(phase)
        )
        + " — "
        + str(data["name"]).upper()
        + "**"
    )


async def attack_boss(
    guild_id,
    ship=None,
    damage_multiplier=1.0
):

    boss = await get_active_boss(
        guild_id
    )

    if not boss:
        return (
            False,
            "There is no boss to attack.",
            None
        )

    if not ship_can_fight(ship):
        return (
            False,
            disabled_ship_message(ship),
            None
        )

    boss_key = str(
        boss["boss_key"]
    )

    old_phase = max(
        1,
        int(
            boss["phase"]
        )
    )

    max_phase = max(
        1,
        int(
            boss["max_phase"]
        )
    )

    # -----------------------------------------------------
    # PLAYER ATTACK
    # -----------------------------------------------------

    player_damage = roll_player_damage(
        ship,
        "boss"
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

    hp = max(
        0,
        int(boss["hp"])
        - player_damage
    )

    # -----------------------------------------------------
    # PHASE CALCULATION
    #
    # The player's hit lands first.
    # If the boss survives and crosses a threshold,
    # retaliation uses the NEW phase immediately.
    # -----------------------------------------------------

    new_phase = calculate_boss_phase(
        hp,
        int(boss["max_hp"]),
        max_phase,
    )

    if hp <= 0:
        new_phase = old_phase

    phase_changed = (
        hp > 0
        and new_phase > old_phase
    )

    phase = (
        new_phase
        if phase_changed
        else old_phase
    )

    # -----------------------------------------------------
    # RETALIATION
    # -----------------------------------------------------

    enemy_damage = 0
    special_name = None
    special_text = ""

    if hp > 0:

        (
            attack_min,
            attack_max,
        ) = boss_phase_attack_range(
            boss,
            phase,
        )

        raw_enemy_damage = random.randint(
            attack_min,
            attack_max,
        )

        (
            enemy_damage,
            special_name,
            special_text,
        ) = apply_boss_phase_retaliation(
            boss_key,
            phase,
            raw_enemy_damage,
        )

    # -----------------------------------------------------
    # ATOMIC ACTIVE-STATUS UPDATE
    # -----------------------------------------------------

    db = await _db()

    try:

        cursor = await db.execute(
            """
            UPDATE boss_encounters
            SET hp = ?,
                phase = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status = 'active'
            """,
            (
                hp,
                phase,
                boss["id"],
            )
        )

        changed = (
            cursor.rowcount == 1
        )

        if not changed:

            await db.rollback()

            return (
                False,
                "The boss encounter is no longer active.",
                None
            )

        if hp <= 0:

            victory_cursor = await db.execute(
                """
                UPDATE boss_encounters
                SET status = 'victory',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                  AND status = 'active'
                """,
                (
                    boss["id"],
                )
            )

            victory_changed = (
                victory_cursor.rowcount == 1
            )

            if not victory_changed:

                await db.rollback()

                return (
                    False,
                    "The boss encounter is no longer active.",
                    None
                )

        await db.commit()

    finally:
        await db.close()

    # -----------------------------------------------------
    # NORMAL ATTACK EVENT
    # -----------------------------------------------------

    await add_boss_event(
        boss["id"],
        guild_id,
        "attack",
        (
            "The crew dealt "
            + str(player_damage)
            + " damage to "
            + boss["name"]
            + "."
        )
    )

    # -----------------------------------------------------
    # PHASE TRANSITION EVENT
    # -----------------------------------------------------

    if phase_changed:

        phase_data = get_boss_phase_data(
            boss_key,
            phase,
        )

        await add_boss_event(
            boss["id"],
            guild_id,
            "phase_change",
            (
                boss["name"]
                + " entered phase "
                + str(phase)
                + ": "
                + str(
                    phase_data["name"]
                )
                + "."
            )
        )

    # -----------------------------------------------------
    # VICTORY
    # -----------------------------------------------------

    if hp <= 0:

        reward = random.randint(
            int(boss["reward_min"]),
            int(boss["reward_max"])
        )

        await add_boss_event(
            boss["id"],
            guild_id,
            "victory",
            (
                boss["name"]
                + " was defeated. Reward "
                + str(reward)
                + " doubloons and "
                + str(boss["xp_reward"])
                + " XP."
            )
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
            "xp": int(
                boss["xp_reward"]
            ),
            "enemy_damage": 0,
            "name": boss["name"],
            "phase": old_phase,
            "phase_changed": False,
            "special": None,
            "player_damage": player_damage,
        }

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

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
            "\n"
            + format_boss_phase_transition(
                boss_key,
                phase,
            )
            + "\n"
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

    if special_text:

        text += (
            "\n\n"
            + special_text
        )

    return True, text, {
        "victory": False,
        "reward": 0,
        "xp": 0,
        "enemy_damage": enemy_damage,
        "name": boss["name"],
        "phase": phase,
        "phase_changed": phase_changed,
        "special": special_name,
        "player_damage": player_damage,
    }

async def defend_boss(
    guild_id,
    ship=None
):

    if not ship_can_fight(ship):
        return (
            False,
            disabled_ship_message(ship),
            None
        )

    boss = await get_active_boss(
        guild_id
    )

    if not boss:
        return (
            False,
            "There is no boss to defend against.",
            None
        )

    boss_key = str(
        boss["boss_key"]
    )

    phase = max(
        1,
        int(
            boss["phase"]
        )
    )

    (
        attack_min,
        attack_max,
    ) = boss_phase_attack_range(
        boss,
        phase,
    )

    raw_damage = random.randint(
        attack_min,
        attack_max,
    )

    damage = apply_boss_defense(
        boss_key,
        phase,
        raw_damage,
    )

    await add_boss_event(
        boss["id"],
        guild_id,
        "defend",
        (
            "The crew defended against "
            + boss["name"]
            + " during phase "
            + str(phase)
            + " and reduced incoming damage from "
            + str(raw_damage)
            + " to "
            + str(damage)
            + "."
        )
    )

    phase_data = get_boss_phase_data(
        boss_key,
        phase,
    )

    return True, (
        "**HOLD THE LINE!**\n"
        "The crew braces against "
        + boss["name"]
        + ".\n"
        "Phase: **"
        + str(phase)
        + " — "
        + str(
            phase_data["name"]
        )
        + "**\n"
        "Incoming damage reduced to **"
        + str(damage)
        + "**."
    ), {
        "victory": False,
        "reward": 0,
        "xp": 0,
        "enemy_damage": damage,
        "name": boss["name"],
        "phase": phase,
        "phase_changed": False,
        "special": None,
    }

