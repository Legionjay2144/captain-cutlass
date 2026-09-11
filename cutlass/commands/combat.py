import random

from cutlass.world.locks import get_guild_lock

from memory import award_achievement

from ship_world import (
    SHIP_COMBAT_ABILITIES,
    get_ship_combat_abilities,
    activate_ship_combat_ability,
    activate_emergency_repairs,
    advance_ship_ability_cooldowns,
    consume_ship_combat_ability,
    clear_ship_combat_effects,
    apply_ship_incoming_ability,
    record_captured_ship,
)

# =========================================================
# Combat flavor
#
# Presentation only. Nothing in this section may alter
# damage, rewards, encounter state, cooldowns, achievements,
# or any other combat mechanics.
# =========================================================

COMBAT_FLAVOR = {
    "naval_attack": (
        "Cannons thunder across the waves as the crew unleashes a broadside.",
        "The gun decks erupt, sending iron screaming toward the enemy hull.",
        "Powder flashes below deck as the crew answers with cannon fire.",
        "The Living Ship cuts across the swell and lets the cannons speak.",
        "Smoke rolls over the deck as another volley tears across the sea.",
    ),

    "naval_defend": (
        "The crew braces behind the rails as enemy guns find their range.",
        "Orders ring across the deck as the crew prepares for incoming fire.",
        "The helm turns hard while the crew fights to spoil the enemy's aim.",
        "The Living Ship angles her hull and prepares to weather the barrage.",
        "The crew ducks low as cannon smoke gathers across the enemy deck.",
    ),

    "board_attempt": (
        "Grappling hooks fly as the crew prepares to cross the gap.",
        "Steel is drawn and the boarding party surges toward the enemy rail.",
        "The ships grind together as the crew makes ready to board.",
        "Hooks bite into timber and the boarding party charges forward.",
        "The crew raises a roar and prepares to take the enemy deck by force.",
    ),

    "flee": (
        "Every scrap of sail is raised as the crew tries to break away.",
        "The helm swings hard and the Living Ship races for open water.",
        "The crew trims the sails and searches desperately for an escape.",
        "Rigging strains as the Living Ship attempts to outrun the enemy.",
        "The crew abandons the firing line and makes a run for the horizon.",
    ),

    "monster_attack": (
        "The crew fires into the churning sea as the creature closes in.",
        "Cannons roar while something enormous moves beneath the waves.",
        "The deck shudders as the crew takes aim at the beast.",
        "The Living Ship turns toward the creature and opens fire.",
        "Spray crashes over the rails as the crew attacks the monster.",
    ),

    "boss_attack": (
        "The crew answers the legendary foe with everything the ship has.",
        "Cannons roar as the Living Ship challenges a terror of the seas.",
        "The crew holds its nerve and drives the attack straight at the boss.",
        "Powder smoke blankets the deck as the battle reaches another furious exchange.",
        "The Living Ship surges forward, refusing to yield to the legendary enemy.",
    ),

    "boss_defend": (
        "The crew locks down the deck and prepares for the boss's assault.",
        "Every sailor braces as the legendary enemy prepares to strike.",
        "The Living Ship turns defensively as danger closes from every side.",
        "Orders echo across the deck as the crew prepares to absorb the attack.",
        "The crew holds formation while the boss bears down upon the ship.",
    ),

    "broadside": (
        "The gun crews fire as one, shaking the Living Ship from bow to stern.",
        "A perfectly timed broadside turns the gun deck into thunder.",
        "Every loaded cannon speaks at once in a wall of smoke and iron.",
    ),

    "brace": (
        "The crew digs in as the impact crashes across the hull.",
        "Timbers groan, but the braced crew holds fast.",
        "The deck bucks beneath them as the crew absorbs the blow.",
    ),

    "rally": (
        "A roar rises from the deck as the crew finds fresh courage.",
        "The crew answers the call and fights with renewed fury.",
        "Fear gives way to determination as the entire crew rallies.",
    ),

    "critical": (
        "The Living Ship is barely holding together, but the flag still flies.",
        "Broken timber litters the deck, yet the crew refuses to surrender.",
        "The hull groans at the edge of disaster, but the ship fights on.",
    ),

    "victory": (
        "The crew answers the victory with a thunderous cheer.",
        "The enemy is beaten and the Living Ship still rules the waves.",
        "Smoke clears from the deck as the crew claims the victory.",
        "Another foe falls before the Living Ship and her crew.",
        "The guns fall silent, leaving victory in their wake.",
    ),

    "boarding_victory": (
        "The enemy colors come down as the boarding party takes the deck.",
        "The last resistance breaks and the captured vessel belongs to the crew.",
        "Steel lowers as the enemy crew yields the ship.",
        "The boarding party secures the deck and claims the vessel as a prize.",
    ),
}


def get_combat_flavor(
    flavor_type,
):
    choices = COMBAT_FLAVOR.get(
        flavor_type,
        (),
    )

    if not choices:
        return ""

    return random.choice(
        choices
    )


def prepend_combat_flavor(
    text,
    flavor_type,
):
    flavor = get_combat_flavor(
        flavor_type
    )

    if not flavor:
        return text

    return (
        "*" + flavor + "*\n\n"
        + text
    )


async def handle_combat_command(
    message,
    command,
    *,
    get_ship_settings,
    get_ship,
    get_ship_operational_status,
    get_active_battle,
    get_active_monster,
    get_active_boss,
    attack_enemy,
    defend,
    board_enemy,
    flee_battle,
    attack_monster,
    attack_boss,
    defend_boss,
    damage_ship,
    reward_ship,
    add_ship_history,
    post_captains_log,
    force_withdraw_battle,
    force_withdraw_monster,
    force_withdraw_boss
):

    # ---------------------------------------------------------
    # Unified command aliases
    # ---------------------------------------------------------

    aliases = {
        # Unified short/long commands.
        "!cutlass attack": "attack",
        "!c attack": "attack",

        "!cutlass defend": "defend",
        "!c defend": "defend",

        "!cutlass flee": "flee",
        "!c flee": "flee",

        "!cutlass board": "board",
        "!c board": "board",

        # -------------------------------------------------
        # Legacy encounter-specific action commands.
        #
        # These intentionally route through this same
        # multiplayer-safe transaction handler.
        # -------------------------------------------------

        "!cutlass battle attack": "attack",
        "!cutlass battle defend": "defend",
        "!cutlass battle flee": "flee",
        "!cutlass battle board": "board",

        "!cutlass monster attack": "attack",

        "!cutlass boss attack": "attack",
        "!cutlass boss defend": "defend",
    }

    action = aliases.get(command)

    ability_prefixes = (
        "!cutlass ability",
        "!cutlass abilities",
        "!c ability",
        "!c abilities",
    )

    ability_command = any(
        command == prefix
        or command.startswith(
            prefix + " "
        )
        for prefix in ability_prefixes
    )

    if not action and not ability_command:
        return False

    guild_id = message.guild.id

    # ---------------------------------------------------------
    # Ship World availability
    # ---------------------------------------------------------

    settings = await get_ship_settings(
        guild_id
    )

    if not settings.get("enabled"):
        await message.reply(
            "Ship World is disabled on this server.",
            mention_author=False
        )
        return True

    ship_channel = message.guild.get_channel(
        settings.get("channel_id", 0)
    )

    if (
        ship_channel
        and message.channel.id != ship_channel.id
    ):
        await message.reply(
            "Combat commands belong in "
            + ship_channel.mention
            + ".",
            mention_author=False
        )
        return True

    async with get_guild_lock(guild_id):

        # =================================================
        # Ship combat abilities
        # =================================================

        if ability_command:

            requested = ""

            for prefix in ability_prefixes:

                if command == prefix:
                    requested = ""
                    break

                if command.startswith(
                    prefix + " "
                ):
                    requested = command[
                        len(prefix):
                    ].strip()
                    break

            battle = await get_active_battle(
                guild_id
            )

            monster = await get_active_monster(
                guild_id
            )

            boss = await get_active_boss(
                guild_id
            )

            encounter_active = any(
                (
                    battle,
                    monster,
                    boss,
                )
            )

            # ---------------------------------------------
            # !c ability
            # ---------------------------------------------

            if not requested:

                states = await get_ship_combat_abilities(
                    guild_id
                )

                lines = [
                    "**SHIP COMBAT ABILITIES**"
                ]

                for key, info in SHIP_COMBAT_ABILITIES.items():

                    state = states.get(
                        key,
                        {}
                    )

                    active = bool(
                        state.get(
                            "active",
                            False,
                        )
                    )

                    cooldown = max(
                        0,
                        int(
                            state.get(
                                "cooldown_turns",
                                0,
                            )
                        )
                    )

                    if active:

                        status = "ACTIVE"

                    elif cooldown > 0:

                        status = (
                            "Cooldown: "
                            + str(cooldown)
                            + " turn"
                            + (
                                ""
                                if cooldown == 1
                                else "s"
                            )
                        )

                    else:

                        status = "READY"

                    lines.append(
                        "**"
                        + info["name"]
                        + "** — "
                        + status
                        + "\n"
                        + info["description"]
                    )

                if not encounter_active:

                    lines.append(
                        "Abilities may only be activated "
                        "during an active combat encounter."
                    )

                await message.reply(
                    "\n\n".join(lines)[:1900],
                    mention_author=False
                )

                return True

            # ---------------------------------------------
            # Activation requires active encounter.
            # ---------------------------------------------

            if not encounter_active:

                await message.reply(
                    "There is no active combat encounter. "
                    "Ship abilities can only be activated "
                    "during battle.",
                    mention_author=False
                )

                return True

            ship = await get_ship(
                guild_id
            )

            operational = (
                await get_ship_operational_status(
                    guild_id,
                    ship=ship
                )
            )

            if not operational["operational"]:

                await message.reply(
                    "**SHIP DISABLED / RECOVERING**\n"
                    "The Living Ship cannot activate "
                    "combat abilities while disabled.",
                    mention_author=False
                )

                return True

            normalized = " ".join(
                requested.lower().split()
            )

            repair_aliases = {
                "repair",
                "repairs",
                "emergency repair",
                "emergency repairs",
            }

            if normalized in repair_aliases:

                ok, response, result = (
                    await activate_emergency_repairs(
                        guild_id,
                        user_id=message.author.id,
                    )
                )

            else:

                ok, response, result = (
                    await activate_ship_combat_ability(
                        guild_id,
                        requested,
                        user_id=message.author.id,
                    )
                )

            if (
                not ok
                and response
                == "Unknown ship combat ability."
            ):

                response = (
                    "Unknown ship combat ability. "
                    "Try **brace**, **broadside**, "
                    "**repairs**, or **rally**."
                )

            await message.reply(
                response[:1900],
                mention_author=False
            )

            return True

        ship = await get_ship(
            guild_id
        )

        operational = await get_ship_operational_status(
            guild_id,
            ship=ship
        )

        if not operational["operational"]:
            await message.reply(
                "**SHIP DISABLED / RECOVERING**\n"
                "The Living Ship cannot continue combat until it reaches **"
                + str(operational["threshold"])
                + "/"
                + str(operational["max_hull"])
                + " hull**.\n"
                "Current hull: **"
                + str(operational["hull"])
                + "/"
                + str(operational["max_hull"])
                + "**.\n"
                "Needed: **+"
                + str(operational["needed"])
                + " hull**.",
                mention_author=False
            )
            return True

        # ---------------------------------------------------------
        # Determine active encounter
        #
        # Boss gets priority because it is the most specialized
        # encounter. Normally only one combat encounter should
        # exist at once anyway.
        # ---------------------------------------------------------

        boss = await get_active_boss(
            guild_id
        )

        monster = await get_active_monster(
            guild_id
        )

        battle = await get_active_battle(
            guild_id
        )

        if boss:
            encounter = "boss"

        elif monster:
            encounter = "monster"

        elif battle:
            encounter = "naval"

        else:
            await message.reply(
                "**NO ACTIVE ENCOUNTER**\n"
                "There is nothing for the crew to "
                + action
                + ".",
                mention_author=False
            )
            return True

        # ---------------------------------------------------------
        # BOARD
        # ---------------------------------------------------------

        if action == "board":

            if encounter != "naval":
                await message.reply(
                    "**BOARDING UNAVAILABLE**\n"
                    "Ye can only board another vessel.",
                    mention_author=False
                )
                return True

        # ---------------------------------------------------------
        # FLEE
        # ---------------------------------------------------------

        if action == "flee":

            if encounter == "monster":

                await message.reply(
                    "**NO ESCAPE!**\n"
                    "The sea monster has the ship engaged. "
                    "The crew must defeat it or survive the fight.",
                    mention_author=False
                )

                return True

            if encounter == "boss":

                await message.reply(
                    "**NO ESCAPE!**\n"
                    "A boss encounter cannot be abandoned.",
                    mention_author=False
                )

                return True

        # ---------------------------------------------------------
        # MONSTER DEFEND
        #
        # Monster combat currently has no defend function.
        # ---------------------------------------------------------

        if (
            action == "defend"
            and encounter == "monster"
        ):
            await message.reply(
                "**DEFEND UNAVAILABLE**\n"
                "The crew cannot take a dedicated defensive "
                "action against sea monsters yet.",
                mention_author=False
            )

            return True

        # ---------------------------------------------------------
        # Ship combat ability state for this exchange
        # ---------------------------------------------------------

        ability_state = await get_ship_combat_abilities(
            guild_id
        )

        broadside_active = bool(
            ability_state.get(
                "broadside",
                {}
            ).get(
                "active",
                False
            )
        )

        brace_active = bool(
            ability_state.get(
                "brace",
                {}
            ).get(
                "active",
                False
            )
        )

        rally_active = bool(
            ability_state.get(
                "rally",
                {}
            ).get(
                "active",
                False
            )
        )

        # A valid combat action advances existing cooldowns.
        # Armed abilities themselves are intentionally excluded
        # by the state-layer helper until consumed.
        await advance_ship_ability_cooldowns(
            guild_id
        )

        outgoing_multiplier = 1.0

        if action == "attack":

            if broadside_active:
                outgoing_multiplier *= 1.50

            if rally_active:
                outgoing_multiplier *= 1.25

        # ---------------------------------------------------------
        # Perform ATTACK / DEFEND
        # ---------------------------------------------------------

        if encounter == "naval":

            if action == "attack":

                ok, text, result = await attack_enemy(
                    guild_id,
                    ship,
                    damage_multiplier=outgoing_multiplier,
                )

            elif action == "board":

                ok, text, result = await board_enemy(
                    guild_id,
                    ship=ship
                )

            elif action == "flee":

                ok, text, result = await flee_battle(
                    guild_id
                )

            else:

                ok, text, result = await defend(
                    guild_id,
                    ship=ship
                )

        elif encounter == "monster":

            ok, text, result = await attack_monster(
                guild_id,
                ship=ship,
                damage_multiplier=outgoing_multiplier,
            )

        else:

            if action == "attack":

                ok, text, result = await attack_boss(
                    guild_id,
                    ship=ship,
                    damage_multiplier=outgoing_multiplier,
                )

            else:

                ok, text, result = await defend_boss(
                    guild_id,
                    ship=ship
                )

        if not ok:

            await message.reply(
                text,
                mention_author=False
            )

            return True

        result = result or {}

        # ---------------------------------------------------------
        # Narrative combat flavor
        #
        # Combat has already been resolved by the engine.
        # This changes presentation only.
        # ---------------------------------------------------------

        if encounter == "naval":

            if action == "attack":
                text = prepend_combat_flavor(
                    text,
                    "naval_attack",
                )

            elif action == "defend":
                text = prepend_combat_flavor(
                    text,
                    "naval_defend",
                )

            elif action == "board":
                text = prepend_combat_flavor(
                    text,
                    "board_attempt",
                )

            elif action == "flee":
                text = prepend_combat_flavor(
                    text,
                    "flee",
                )

        elif encounter == "monster":

            text = prepend_combat_flavor(
                text,
                "monster_attack",
            )

        elif encounter == "boss":

            if action == "defend":
                flavor_type = "boss_defend"
            else:
                flavor_type = "boss_attack"

            text = prepend_combat_flavor(
                text,
                flavor_type,
            )

        # ---------------------------------------------------------
        # Apply incoming damage
        # ---------------------------------------------------------

        enemy_damage = int(
            result.get(
                "enemy_damage",
                0
            )
        )

        ability_text = []

        # -----------------------------------------------------
        # Outgoing effects are consumed only after a successful
        # attack exchange actually occurred.
        # -----------------------------------------------------

        if action == "attack":

            if broadside_active:

                consumed = await consume_ship_combat_ability(
                    guild_id,
                    "broadside"
                )

                if consumed:
                    ability_text.append(
                        "*"
                        + get_combat_flavor(
                            "broadside"
                        )
                        + "*\n"
                        "**FULL BROADSIDE** increased outgoing "
                        "attack damage by **50%**."
                    )

            # Rally's outgoing component is part of this same
            # exchange. Its incoming component below still uses
            # our pre-action snapshot before the row is consumed.
            if rally_active:

                await consume_ship_combat_ability(
                    guild_id,
                    "rally"
                )

        ship_after = None

        if enemy_damage > 0:

            original_enemy_damage = enemy_damage

            enemy_damage = apply_ship_incoming_ability(
                enemy_damage,
                brace=brace_active,
                rally=rally_active,
            )

            if brace_active:

                consumed = await consume_ship_combat_ability(
                    guild_id,
                    "brace"
                )

                if consumed:
                    ability_text.append(
                        "*"
                        + get_combat_flavor(
                            "brace"
                        )
                        + "*\n"
                        "**BRACE FOR IMPACT** reduced incoming "
                        "damage by **50%**."
                    )

            # Rally may already have been consumed by an attack's
            # outgoing half; consuming again is safely idempotent.
            if rally_active:

                await consume_ship_combat_ability(
                    guild_id,
                    "rally"
                )

                ability_text.append(
                    "*"
                    + get_combat_flavor(
                        "rally"
                    )
                    + "*\n"
                    "**RALLY THE CREW** reduced incoming "
                    "damage by **25%**."
                )

            if enemy_damage != original_enemy_damage:

                ability_text.append(
                    "Incoming damage: **"
                    + str(original_enemy_damage)
                    + " → "
                    + str(enemy_damage)
                    + "**."
                )

            ship_after = await damage_ship(
                guild_id,
                enemy_damage
            )

            text += (
                "\n\n**"
                + str(ship_after["name"])
                + "**\n"
                "Hull: **"
                + str(ship_after["hull"])
                + "**"
            )

        # -----------------------------------------------------
        # Critical-hull flavor
        #
        # Narrative only. No combat state is changed here.
        # -----------------------------------------------------

        if (
            ship_after
            and int(ship_after["hull"]) > 0
        ):
            current_hull = int(
                ship_after["hull"]
            )

            current_max_hull = max(
                int(
                    ship_after.get(
                        "max_hull",
                        operational.get(
                            "max_hull",
                            1,
                        ),
                    )
                ),
                1,
            )

            if (
                current_hull * 10
                <= current_max_hull
            ):
                text += (
                    "\n\n*"
                    + get_combat_flavor(
                        "critical"
                    )
                    + "*"
                )

        if ability_text:

            text += (
                "\n\n"
                + "\n".join(
                    ability_text
                )
            )

        # ---------------------------------------------------------
        # Ship disabled / recovering
        #
        # The ship becomes non-operational below the recovery
        # threshold, even if hull is still above zero.
        # ---------------------------------------------------------

        if ship_after:

            operational_after = await get_ship_operational_status(
                guild_id,
                ship=ship_after
            )

            if not operational_after["operational"]:

                if int(ship_after["hull"]) <= 0:

                    text += (
                        "\n\n**SHIP DISABLED!**\n"
                        "The hull has been battered to **0/"
                        + str(operational_after["max_hull"])
                        + "**.\n"
                        "Passive emergency recovery has begun."
                    )

                else:

                    text += (
                        "\n\n**SHIP DISABLED / RECOVERING!**\n"
                        "The ship has fallen below operational hull.\n"
                        "Current hull: **"
                        + str(operational_after["hull"])
                        + "/"
                        + str(operational_after["max_hull"])
                        + "**\n"
                        "Operational at: **"
                        + str(operational_after["threshold"])
                        + "/"
                        + str(operational_after["max_hull"])
                        + "**\n"
                        "Needed: **+"
                        + str(operational_after["needed"])
                        + " hull**."
                    )

                # -------------------------------------------------
                # Automatic combat exit
                # -------------------------------------------------

                if encounter == "naval":

                    terminated, defeated_encounter = (
                        await force_withdraw_battle(
                            guild_id
                        )
                    )

                    history_type = "battle_defeat"

                elif encounter == "monster":

                    terminated, defeated_encounter = (
                        await force_withdraw_monster(
                            guild_id
                        )
                    )

                    history_type = "monster_defeat"

                else:

                    terminated, defeated_encounter = (
                        await force_withdraw_boss(
                            guild_id
                        )
                    )

                    history_type = "boss_defeat"

                text += (
                    "\n\n**FORCED WITHDRAWAL**\n"
                    "The Living Ship can no longer remain in combat. "
                    "The crew withdraws while emergency repairs begin.\n"
                    "**The enemy remains undefeated.**"
                )

                # Only the command that actually changes the encounter
                # from active -> player_disabled owns persistent
                # defeat history and Captain's Log output.
                if terminated:

                    await add_ship_history(
                        guild_id,
                        (
                            "Forced withdrawal from "
                            + encounter
                            + " combat after the Living Ship became "
                            "non-operational at "
                            + str(operational_after["hull"])
                            + "/"
                            + str(operational_after["max_hull"])
                            + " hull. The enemy remained undefeated."
                        ),
                        history_type
                    )

                    await post_captains_log(
                        message.guild,
                        text,
                        encounter
                    )

                await clear_ship_combat_effects(
                    guild_id
                )

                await message.reply(
                    text[:1900],
                    mention_author=False
                )

                return True


        # ---------------------------------------------------------

        if result.get("fled"):

            await clear_ship_combat_effects(
                guild_id
            )

        if result.get("victory"):

            # -------------------------------------------------
            # Victory flavor
            # -------------------------------------------------

            if result.get("boarded"):
                text += (
                    "\n\n*"
                    + get_combat_flavor(
                        "boarding_victory"
                    )
                    + "*"
                )

            else:
                text += (
                    "\n\n*"
                    + get_combat_flavor(
                        "victory"
                    )
                    + "*"
                )

            await clear_ship_combat_effects(
                guild_id
            )

            reward = int(
                result.get(
                    "reward",
                    0
                )
            )

            xp = int(
                result.get(
                    "xp",
                    0
                )
            )

            award = await reward_ship(
                guild_id,
                reward,
                xp,
                achievement_user_id=message.author.id
            )

            if result.get("boarded"):
                capture = await record_captured_ship(
                    guild_id,
                    result.get(
                        "enemy_name",
                        "an enemy vessel"
                    ),
                    captured_by_user_id=message.author.id,
                    captured_by_name=message.author.display_name,
                    reward=reward,
                    xp_reward=xp,
                    award_user_id=message.author.id,
                )

                if capture:
                    text += (
                        "\nPrize ledger entry: **#"
                        + str(capture["id"])
                        + "**"
                    )

                    if capture.get("milestone_text"):
                        text += (
                            "\n"
                            + capture["milestone_text"]
                        )

            # -------------------------------------------------
            # Combat achievements
            #
            # This block only executes for an actual terminal
            # victory. Forced withdrawal returns before reaching
            # this point, so defeat/flee paths cannot award these.
            # -------------------------------------------------

            achievement_candidates = []

            if encounter == "naval":

                achievement_candidates.append(
                    (
                        "First Blood",
                        (
                            "Won a naval battle with "
                            "the Living Ship."
                        ),
                    )
                )

                if result.get("boarded"):

                    achievement_candidates.append(
                        (
                            "Prize of War",
                            (
                                "Successfully boarded "
                                "and captured an enemy vessel."
                            ),
                        )
                    )

            elif encounter == "monster":

                achievement_candidates.append(
                    (
                        "Monster Hunter",
                        (
                            "Defeated a sea monster "
                            "in combat."
                        ),
                    )
                )

            elif encounter == "boss":

                achievement_candidates.append(
                    (
                        "Kingslayer",
                        (
                            "Defeated a legendary boss "
                            "encounter."
                        ),
                    )
                )

            # -------------------------------------------------
            # Critical-hull victory
            # -------------------------------------------------

            victory_ship_status = (
                await get_ship_operational_status(
                    guild_id,
                    ship=ship_after or ship
                )
            )

            victory_hull = int(
                victory_ship_status.get(
                    "hull",
                    0
                )
            )

            victory_max_hull = max(
                int(
                    victory_ship_status.get(
                        "max_hull",
                        1
                    )
                ),
                1,
            )

            if (
                victory_ship_status.get(
                    "operational"
                )
                and victory_hull > 0
                and (
                    victory_hull * 10
                    <= victory_max_hull
                )
            ):

                achievement_candidates.append(
                    (
                        "By a Thread",
                        (
                            "Won a combat encounter "
                            "at 10% hull or less while "
                            "the Living Ship remained "
                            "operational."
                        ),
                    )
                )

            # -------------------------------------------------
            # Tactical ability victory achievements
            # -------------------------------------------------

            if (
                action == "attack"
                and broadside_active
            ):

                achievement_candidates.append(
                    (
                        "Broadside!",
                        (
                            "Won a combat encounter "
                            "using Full Broadside."
                        ),
                    )
                )

            if brace_active:

                achievement_candidates.append(
                    (
                        "Hold Fast",
                        (
                            "Won a combat encounter "
                            "while Brace for Impact "
                            "was armed."
                        ),
                    )
                )

            if rally_active:

                achievement_candidates.append(
                    (
                        "Rally the Crew",
                        (
                            "Won a combat encounter "
                            "while Rally the Crew "
                            "was active."
                        ),
                    )
                )

            # -------------------------------------------------
            # award_achievement() is protected by the new
            # unique case-insensitive database index.
            #
            # Only newly-created achievements are displayed.
            # -------------------------------------------------

            unlocked_achievements = []

            for (
                achievement_name,
                achievement_description,
            ) in achievement_candidates:

                unlocked = await award_achievement(
                    guild_id,
                    message.author.id,
                    achievement_name,
                    achievement_description,
                )

                if unlocked:

                    unlocked_achievements.append(
                        achievement_name
                    )

            if unlocked_achievements:

                text += (
                    "\n\n**ACHIEVEMENT UNLOCKED**\n"
                    + "\n".join(
                        "🏆 **" + name + "**"
                        for name
                        in unlocked_achievements
                    )
                )

            if encounter == "boss":

                text += (
                    "\n\n**LEGENDARY VICTORY**"
                )

            text += (
                "\n\n**LIVING SHIP UPDATED**\n"
                "Treasury: **+"
                + str(reward)
                + " doubloons**\n"
                "Ship XP: **+"
                + str(xp)
                + "**"
            )

            if award["levels_gained"]:

                text += (
                    "\nThe ship reached **Level "
                    + str(award["level"])
                    + "**!"
                )

            if award.get("milestone_text"):
                text += (
                    "\n"
                    + award["milestone_text"]
                )

            if encounter == "naval":

                enemy_name = str(
                    result.get(
                        "enemy_name",
                        "an enemy vessel"
                    )
                )

                if result.get("boarded"):

                    history = (
                        "Captured "
                        + enemy_name
                        + " by boarding. Treasury +"
                        + str(reward)
                        + ", XP +"
                        + str(xp)
                        + "."
                    )

                    history_type = "battle_boarding"

                else:

                    history = (
                        "Defeated "
                        + enemy_name
                        + " in naval combat. Treasury +"
                        + str(reward)
                        + ", XP +"
                        + str(xp)
                        + "."
                    )

                    history_type = "battle_victory"

            elif encounter == "monster":

                history = (
                    "Defeated "
                    + str(
                        result.get(
                            "name",
                            "a sea monster"
                        )
                    )
                    + ". Treasury +"
                    + str(reward)
                    + ", XP +"
                    + str(xp)
                    + "."
                )

                history_type = "monster_victory"

            else:

                history = (
                    "Defeated legendary boss "
                    + str(
                        result.get(
                            "name",
                            "unknown boss"
                        )
                    )
                    + ". Treasury +"
                    + str(reward)
                    + ", XP +"
                    + str(xp)
                    + "."
                )

                history_type = "boss_victory"

            await add_ship_history(
                guild_id,
                history,
                history_type
            )

            await post_captains_log(
                message.guild,
                text,
                encounter
            )

        await message.reply(
            text[:1900],
            mention_author=False
        )

        return True
