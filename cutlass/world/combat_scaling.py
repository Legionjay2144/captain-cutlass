"""
Central combat scaling for Captain Cutlass Ship World.

Encounter definitions describe the identity of an enemy.
This module converts those base values into playable stats
appropriate for the Living Ship's current level.
"""

import random


# =========================================================
# DANGER TUNING
# =========================================================

HP_DANGER = {
    "Low": 0.75,
    "Medium": 0.85,
    "High": 0.95,
    "Extreme": 1.00,
    "Legendary": 1.15,
}


DAMAGE_DANGER = {
    "Low": 0.75,
    "Medium": 0.90,
    "High": 1.00,
    "Extreme": 1.10,
    "Legendary": 1.20,
}


REWARD_DANGER = {
    "Low": 0.80,
    "Medium": 0.90,
    "High": 1.00,
    "Extreme": 1.10,
    "Legendary": 1.25,
}


# =========================================================
# ENCOUNTER TYPE TUNING
# =========================================================

HP_TYPE = {
    "naval": 0.85,
    "monster": 0.60,
    "boss": 0.75,
}


DAMAGE_TYPE = {
    "naval": 0.65,
    "monster": 0.50,
    "boss": 0.55,
}


# =========================================================
# SHIP LEVEL
# =========================================================

def _level(ship):

    if not ship:
        return 1

    try:
        return max(
            1,
            int(ship.get("level", 1))
        )

    except (TypeError, ValueError):
        return 1


def ship_power_multiplier(ship):
    """
    Crew offense improves faster than enemy scaling.

    Level 1 = 1.00
    Level 2 = 1.12
    Level 3 = 1.24
    """

    return 1.0 + (
        (_level(ship) - 1) * 0.12
    )


def encounter_level_multiplier(ship):
    """
    Enemy progression is intentionally slower than crew
    progression so ship levels feel meaningful.

    Level 1 = 1.00
    Level 2 = 1.06
    Level 3 = 1.12
    """

    return 1.0 + (
        (_level(ship) - 1) * 0.06
    )


# =========================================================
# PLAYER DAMAGE
# =========================================================

def player_attack_range(
    ship,
    combat_type="naval"
):

    bases = {
        "naval": (20, 32),
        "monster": (24, 38),
        "boss": (25, 40),
    }

    base_min, base_max = bases.get(
        combat_type,
        bases["naval"]
    )

    multiplier = ship_power_multiplier(
        ship
    )

    minimum = max(
        1,
        round(
            base_min * multiplier
        )
    )

    maximum = max(
        minimum,
        round(
            base_max * multiplier
        )
    )

    return minimum, maximum


def roll_player_damage(
    ship,
    combat_type="naval"
):

    minimum, maximum = player_attack_range(
        ship,
        combat_type
    )

    return random.randint(
        minimum,
        maximum
    )


# =========================================================
# ENCOUNTER SCALING
# =========================================================

def scale_encounter_stats(
    ship,
    *,
    base_hp,
    attack_min,
    attack_max,
    reward_min,
    reward_max,
    xp_reward,
    danger="Medium",
    encounter_type="naval",
):
    """
    Scale an encounter once when it begins.

    Stats are stored in the encounter database afterward so
    an enemy never changes strength halfway through combat.
    """

    level_mult = encounter_level_multiplier(
        ship
    )

    hp_danger = HP_DANGER.get(
        str(danger),
        0.85
    )

    damage_danger = DAMAGE_DANGER.get(
        str(danger),
        0.90
    )

    reward_danger = REWARD_DANGER.get(
        str(danger),
        1.00
    )

    hp_type = HP_TYPE.get(
        encounter_type,
        0.85
    )

    damage_type = DAMAGE_TYPE.get(
        encounter_type,
        0.65
    )


    # =====================================================
    # HP
    # =====================================================

    max_hp = max(
        25,
        round(
            base_hp
            * hp_type
            * hp_danger
            * level_mult
        )
    )


    # =====================================================
    # ENEMY DAMAGE
    # =====================================================

    damage_mult = (
        damage_type
        * damage_danger
        * level_mult
    )

    scaled_attack_min = max(
        1,
        round(
            attack_min
            * damage_mult
        )
    )

    scaled_attack_max = max(
        scaled_attack_min,
        round(
            attack_max
            * damage_mult
        )
    )


    # =====================================================
    # REWARDS
    # =====================================================

    reward_level = (
        0.80
        + ((_level(ship) - 1) * 0.10)
    )

    reward_mult = (
        reward_level
        * reward_danger
    )

    scaled_reward_min = max(
        1,
        round(
            reward_min
            * reward_mult
        )
    )

    scaled_reward_max = max(
        scaled_reward_min,
        round(
            reward_max
            * reward_mult
        )
    )

    scaled_xp = max(
        1,
        round(
            xp_reward
            * reward_mult
        )
    )


    return {
        "max_hp": max_hp,
        "attack_min": scaled_attack_min,
        "attack_max": scaled_attack_max,
        "reward_min": scaled_reward_min,
        "reward_max": scaled_reward_max,
        "xp_reward": scaled_xp,
    }


# =========================================================
# DISABLED SHIP
# =========================================================

def ship_can_fight(ship):

    if not ship:
        return False

    try:
        return int(
            ship.get("hull", 0)
        ) > 0

    except (TypeError, ValueError):
        return False


def disabled_ship_message(ship=None):

    name = (
        ship.get(
            "name",
            "The Living Ship"
        )
        if ship
        else "The Living Ship"
    )

    return (
        "**SHIP DISABLED**\n"
        + name
        + " has **0 hull** and cannot continue fighting.\n"
        "Repair the ship before returning to combat."
    )
