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


async def attack_monster(
    guild_id,
    ship=None,
    damage_multiplier=1.0
):
    """
    Perform one atomic monster attack for a guild.
    """

    async with get_guild_lock(guild_id):
        return await _attack_monster_unlocked(
            guild_id,
            ship=ship,
            damage_multiplier=damage_multiplier,
        )


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


async def add_monster_event(
    encounter_id,
    guild_id,
    action,
    description
):
    db = await _db()

    try:
        await db.execute("""
            INSERT INTO monster_events (
                encounter_id,
                guild_id,
                action,
                description
            )
            VALUES (?, ?, ?, ?)
        """, (
            encounter_id,
            guild_id,
            action,
            description,
        ))

        await db.commit()

    finally:
        await db.close()



async def start_monster_encounter(
    guild_id,
    monster_key=None,
    ship=None
):
    async with get_guild_lock(guild_id):

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

        scaled = scale_encounter_stats(
            ship,
            base_hp=monster["hp"],
            attack_min=monster["attack_min"],
            attack_max=monster["attack_max"],
            reward_min=monster["reward_min"],
            reward_max=monster["reward_max"],
            xp_reward=monster["xp"],
            danger=monster["danger"],
            encounter_type="monster",
        )

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
                scaled["max_hp"],
                scaled["max_hp"],
                scaled["attack_min"],
                scaled["attack_max"],
                scaled["reward_min"],
                scaled["reward_max"],
                scaled["xp_reward"],
                monster["danger"],
            ))

            await db.commit()

            encounter_id = cursor.lastrowid

        finally:
            await db.close()

        await add_monster_event(
            encounter_id,
            guild_id,
            "start",
            (
                monster["name"]
                + " entered combat with the crew."
            )
        )

        return True, await get_active_monster(
            guild_id
        )


async def force_withdraw_monster(guild_id):
    """
    Terminate the active monster encounter because the Living
    Ship became non-operational.

    The monster is not recorded as defeated and no rewards are
    generated here.
    """

    db = await _db()

    try:
        encounter = await (
            await db.execute(
                """
                SELECT *
                FROM monster_encounters
                WHERE guild_id = ?
                  AND status = 'active'
                ORDER BY id DESC
                LIMIT 1
                """,
                (guild_id,),
            )
        ).fetchone()

        if not encounter:
            return False, None

        cursor = await db.execute(
            """
            UPDATE monster_encounters
            SET status = 'player_disabled',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status = 'active'
            """,
            (encounter["id"],),
        )

        changed = cursor.rowcount == 1

        if changed:
            await db.execute(
                """
                INSERT INTO monster_events (
                    encounter_id,
                    guild_id,
                    action,
                    description
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    encounter["id"],
                    guild_id,
                    "player_disabled",
                    (
                        "The Living Ship became non-operational. "
                        "The crew was forced to withdraw from "
                        + encounter["name"]
                        + "; the creature remained undefeated."
                    ),
                ),
            )

        await db.commit()

        return changed, dict(encounter)

    finally:
        await db.close()

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



# =========================================================
# MONSTER COMBAT PHASES
# =========================================================

MONSTER_PHASES = {

    "kraken": {
        1: {
            "name": "The Hunt",
            "enemy_damage_mult": 1.00,
            "player_damage_mult": 1.00,
        },
        2: {
            "name": "Thrashing Tentacles",
            "enemy_damage_mult": 1.15,
            "player_damage_mult": 1.00,
        },
        3: {
            "name": "Frenzy",
            "enemy_damage_mult": 1.30,
            "player_damage_mult": 1.00,
        },
    },

    "leviathan": {
        1: {
            "name": "Surface Assault",
            "enemy_damage_mult": 1.00,
            "player_damage_mult": 1.00,
        },
        2: {
            "name": "The Dive",
            "enemy_damage_mult": 1.10,
            "player_damage_mult": 0.75,
        },
        3: {
            "name": "Leviathan's Rage",
            "enemy_damage_mult": 1.35,
            "player_damage_mult": 1.00,
        },
    },

    "drowned_king": {
        1: {
            "name": "The Fallen King",
            "enemy_damage_mult": 1.00,
            "player_damage_mult": 1.00,
        },
        2: {
            "name": "Call of the Deep",
            "enemy_damage_mult": 1.20,
            "player_damage_mult": 1.00,
        },
        3: {
            "name": "Drowned Wrath",
            "enemy_damage_mult": 1.45,
            "player_damage_mult": 1.00,
        },
    },
}


def calculate_monster_phase(
    hp,
    max_hp,
):
    """
    Determine monster phase from remaining HP.

    Phase 1: above 65%
    Phase 2: 31-65%
    Phase 3: 30% or below
    """

    max_hp = max(
        1,
        int(max_hp)
    )

    hp = max(
        0,
        int(hp)
    )

    ratio = (
        hp / max_hp
    )

    if ratio <= 0.30:
        return 3

    if ratio <= 0.65:
        return 2

    return 1


def get_monster_phase_data(
    monster_key,
    phase,
):
    """
    Return phase mechanics for a monster.
    """

    phases = MONSTER_PHASES.get(
        str(monster_key),
        {}
    )

    return phases.get(
        int(phase),
        {
            "name": "Unknown Phase",
            "enemy_damage_mult": 1.00,
            "player_damage_mult": 1.00,
        }
    )


def apply_monster_phase_player_damage(
    monster_key,
    phase,
    player_damage,
):
    """
    Apply phase-specific protection to incoming player damage.
    """

    data = get_monster_phase_data(
        monster_key,
        phase,
    )

    multiplier = float(
        data.get(
            "player_damage_mult",
            1.00
        )
    )

    return max(
        1,
        int(round(
            int(player_damage)
            * multiplier
        ))
    )


def apply_monster_phase_retaliation(
    monster_key,
    phase,
    enemy_damage,
    *,
    special_roll=None,
):
    """
    Apply phase retaliation and optional special attacks.

    Returns:
        final_damage,
        special_name,
        special_text
    """

    data = get_monster_phase_data(
        monster_key,
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

    # -----------------------------------------------------
    # KRAKEN PHASE 3 — TENTACLE SMASH
    # -----------------------------------------------------

    if (
        monster_key == "kraken"
        and int(phase) == 3
        and special_roll <= 20
    ):

        bonus = max(
            1,
            int(round(
                final_damage * 0.35
            ))
        )

        final_damage += bonus

        special_name = "tentacle_smash"

        special_text = (
            "**TENTACLE SMASH!**\n"
            "The Kraken brings a massive tentacle down "
            "across the Living Ship for **"
            + str(bonus)
            + "** additional damage."
        )

    # -----------------------------------------------------
    # DROWNED KING PHASE 3 — DROWNED WRATH
    # -----------------------------------------------------

    elif (
        monster_key == "drowned_king"
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

        special_name = "drowned_wrath"

        special_text = (
            "**DROWNED WRATH!**\n"
            "The Drowned King calls the black sea against "
            "the hull for **"
            + str(bonus)
            + "** additional damage."
        )

    return (
        final_damage,
        special_name,
        special_text,
    )


def format_monster_phase_transition(
    monster_key,
    phase,
):
    data = get_monster_phase_data(
        monster_key,
        phase,
    )

    names = {
        1: "I",
        2: "II",
        3: "III",
    }

    return (
        "**PHASE "
        + names.get(
            int(phase),
            str(phase)
        )
        + " — "
        + str(data["name"]).upper()
        + "**"
    )


async def record_monster_phase_change(
    encounter,
    guild_id,
    old_phase,
    new_phase,
):
    """
    Persist a phase transition and its history event.
    """

    if int(new_phase) == int(old_phase):
        return False

    db = await _db()

    try:

        cursor = await db.execute(
            """
            UPDATE monster_encounters
            SET phase = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status = 'active'
              AND phase = ?
            """,
            (
                int(new_phase),
                encounter["id"],
                int(old_phase),
            )
        )

        changed = (
            cursor.rowcount == 1
        )

        await db.commit()

    finally:
        await db.close()

    if not changed:
        return False

    phase_data = get_monster_phase_data(
        encounter["monster_key"],
        new_phase,
    )

    await add_monster_event(
        encounter["id"],
        guild_id,
        "phase_change",
        (
            encounter["name"]
            + " entered Phase "
            + str(new_phase)
            + ": "
            + str(phase_data["name"])
            + "."
        )
    )

    return True


async def _attack_monster_unlocked(
    guild_id,
    ship=None,
    damage_multiplier=1.0
):

    if not ship_can_fight(ship):
        return (
            False,
            disabled_ship_message(ship),
            None
        )

    encounter = await get_active_monster(
        guild_id
    )

    if not encounter:
        return (
            False,
            "There is no monster to attack.",
            None
        )

    monster_key = str(
        encounter["monster_key"]
    )

    old_phase = int(
        encounter["phase"]
        if encounter["phase"] is not None
        else 1
    )

    # -----------------------------------------------------
    # PLAYER ATTACK
    #
    # Phase protection uses the phase that existed at the
    # START of the turn.
    #
    # This is important for Leviathan's Dive: a cannon hit
    # that causes Phase 2 is not retroactively reduced.
    # -----------------------------------------------------

    raw_player_damage = roll_player_damage(
        ship,
        "monster"
    )

    raw_player_damage = max(
        1,
        int(round(
            raw_player_damage
            * max(
                0.0,
                float(damage_multiplier)
            )
        ))
    )

    player_damage = (
        apply_monster_phase_player_damage(
            monster_key,
            old_phase,
            raw_player_damage,
        )
    )

    hp = max(
        0,
        int(encounter["hp"])
        - player_damage
    )

    # -----------------------------------------------------
    # DETERMINE POST-HIT PHASE
    # -----------------------------------------------------

    new_phase = calculate_monster_phase(
        hp,
        int(encounter["max_hp"]),
    )

    phase_changed = (
        hp > 0
        and new_phase != old_phase
    )

    # -----------------------------------------------------
    # MONSTER RETALIATION
    #
    # Retaliation uses the NEW phase immediately.
    # -----------------------------------------------------

    enemy_damage = 0
    special_name = None
    special_text = ""

    if hp > 0:

        raw_enemy_damage = random.randint(
            int(encounter["attack_min"]),
            int(encounter["attack_max"])
        )

        (
            enemy_damage,
            special_name,
            special_text,
        ) = apply_monster_phase_retaliation(
            monster_key,
            new_phase,
            raw_enemy_damage,
        )

    # -----------------------------------------------------
    # PERSIST HP / VICTORY
    # -----------------------------------------------------

    db = await _db()

    try:

        await db.execute(
            """
            UPDATE monster_encounters
            SET hp = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status = 'active'
            """,
            (
                hp,
                encounter["id"],
            )
        )

        victory_claimed = False

        if hp <= 0:

            cursor = await db.execute(
                """
                UPDATE monster_encounters
                SET status = 'victory',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                  AND status = 'active'
                """,
                (
                    encounter["id"],
                )
            )

            victory_claimed = (
                cursor.rowcount == 1
            )

        await db.commit()

    finally:
        await db.close()

    # -----------------------------------------------------
    # VICTORY
    # -----------------------------------------------------

    if hp <= 0:

        if not victory_claimed:
            return (
                False,
                "The monster encounter has already ended.",
                None
            )

        reward = random.randint(
            int(encounter["reward_min"]),
            int(encounter["reward_max"])
        )

        await add_monster_event(
            encounter["id"],
            guild_id,
            "victory",
            (
                encounter["name"]
                + " was defeated. Reward "
                + str(reward)
                + " doubloons and "
                + str(encounter["xp_reward"])
                + " XP."
            )
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
            "xp": int(
                encounter["xp_reward"]
            ),
            "enemy_damage": 0,
            "name": encounter["name"],
            "phase": old_phase,
            "phase_changed": False,
            "special": None,
            "player_damage": player_damage,
            "raw_player_damage": raw_player_damage,
        }

    # -----------------------------------------------------
    # PHASE TRANSITION
    # -----------------------------------------------------

    transition_text = ""

    if phase_changed:

        changed = (
            await record_monster_phase_change(
                encounter,
                guild_id,
                old_phase,
                new_phase,
            )
        )

        if changed:

            transition_text = (
                "\n\n"
                + format_monster_phase_transition(
                    monster_key,
                    new_phase,
                )
            )

    # -----------------------------------------------------
    # ATTACK HISTORY
    # -----------------------------------------------------

    description = (
        "The crew dealt "
        + str(player_damage)
        + " damage to "
        + encounter["name"]
        + "; "
        + encounter["name"]
        + " retaliated for "
        + str(enemy_damage)
        + " damage."
    )

    if special_name:

        description += (
            " Special attack: "
            + special_name
            + "."
        )

    await add_monster_event(
        encounter["id"],
        guild_id,
        "attack",
        description,
    )

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    text = (
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
    )

    text += transition_text

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
        "name": encounter["name"],
        "phase": new_phase,
        "phase_changed": phase_changed,
        "special": special_name,
        "player_damage": player_damage,
        "raw_player_damage": raw_player_damage,
    }

