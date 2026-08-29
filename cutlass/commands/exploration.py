import random

from cutlass.world.locks import get_guild_lock


async def handle_exploration_command(
    message,
    command,
    *,
    get_ship_settings,
    get_ship,
    get_ship_operational_status,
    get_active_battle,
    get_active_monster,
    get_active_boss,
    explore_random_island,
    start_naval_battle,
    start_monster_encounter,
    add_ship_treasury,
    add_ship_supplies,
    apply_exploration_outcome,
    add_ship_history,
    post_captains_log
):

    if command not in (
        "!cutlass explore",
        "!cutlass explore island"
    ):
        return False

    settings = await get_ship_settings(
        message.guild.id
    )

    if not settings.get("enabled"):
        await message.reply(
            "Ship World is disabled on this server.",
            mention_author=False
        )
        return True

    ship = await get_ship(
        message.guild.id
    )

    operational = await get_ship_operational_status(
        message.guild.id
    )

    if not operational["operational"]:
        await message.reply(
            "**SHIP DISABLED / RECOVERING**\n"
            "The Living Ship cannot explore until it reaches **"
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

    ship_channel = message.guild.get_channel(
        settings.get("channel_id", 0)
    )

    if (
        ship_channel
        and message.channel.id != ship_channel.id
    ):
        await message.reply(
            "Exploration belongs in "
            + ship_channel.mention
            + ".",
            mention_author=False
        )
        return True

    async with get_guild_lock(message.guild.id):
        battle = await get_active_battle(
            message.guild.id
        )

        if battle:
            await message.reply(
                "We're already engaged with **"
                + battle["enemy_name"]
                + "**. Finish the battle before exploring.",
                mention_author=False
            )
            return True

        monster = await get_active_monster(
            message.guild.id
        )

        if monster:
            await message.reply(
                "**"
                + monster["name"]
                + "** is still threatening the ship. "
                "Exploration can wait.",
                mention_author=False
            )
            return True

        boss = await get_active_boss(
            message.guild.id
        )

        if boss:
            await message.reply(
                "**"
                + boss["name"]
                + "** is still threatening the crew. "
                "Exploration can wait.",
                mention_author=False
            )
            return True

        result = await explore_random_island(
            message.guild.id,
            message.author.id,
            message.author.display_name
        )

        title = (
            "NEW ISLAND DISCOVERED"
            if result["new"]
            else "ISLAND EXPLORATION"
        )

        text = (
            "**"
            + title
            + "**\n"
            "Island: **"
            + result["name"]
            + "**\n"
            "Region: **"
            + result["region"]
            + "**\n"
            "Danger: **"
            + result["danger"]
            + "**\n\n"
            + result["description"]
            + "\n\n"
            "**Encounter:** "
            + result["encounter"]
        )

        encounter_type = result.get(
            "encounter_type",
            "quiet"
        )

        # ---------------------------------------------------------
        # Naval encounter
        # ---------------------------------------------------------

        if encounter_type == "naval":

            ship = await get_ship(
                message.guild.id
            )

            created, battle = await start_naval_battle(
                message.guild.id,
                ship=ship
            )

            if created:
                text += (
                    "\n\n**ENEMY SHIP SIGHTED**\n"
                    + battle["enemy_name"]
                    + " appears under the command of **"
                    + battle["enemy_captain"]
                    + "**.\n"
                    "Enemy Hull: **"
                    + str(battle["enemy_hull"])
                    + "**\n"
                    "Use `!cutlass battle`."
                )

        # ---------------------------------------------------------
        # Monster encounter
        # ---------------------------------------------------------

        elif encounter_type == "monster":

            # Mostly Kraken, occasionally Leviathan.
            monster_key = (
                "leviathan"
                if random.randint(1, 100) <= 20
                else "kraken"
            )

            ship = await get_ship(
                message.guild.id
            )

            created, monster = await start_monster_encounter(
                message.guild.id,
                monster_key,
                ship=ship
            )

            if created:
                text += (
                    "\n\n**SEA MONSTER SIGHTED**\n"
                    + monster["name"]
                    + " rises from the water!\n"
                    "HP: **"
                    + str(monster["hp"])
                    + "**\n"
                    "Use `!cutlass monster`."
                )

        # ---------------------------------------------------------
        # Environmental hazard
        # ---------------------------------------------------------

        elif encounter_type == "hazard":

            hazard = result.get("hazard") or {}

            def roll_effect(name):
                value = hazard.get(name, 0)

                if isinstance(value, (tuple, list)):
                    low, high = value
                    return random.randint(
                        int(low),
                        int(high)
                    )

                return int(value or 0)

            outcome = await apply_exploration_outcome(
                message.guild.id,
                hull_damage=roll_effect(
                    "hull_damage"
                ),
                sails_damage=roll_effect(
                    "sails_damage"
                ),
                supplies_change=roll_effect(
                    "supplies_change"
                ),
                morale_change=roll_effect(
                    "morale_change"
                ),
            )

            applied = outcome["applied"]

            effect_lines = []

            if applied["hull_damage"]:
                effect_lines.append(
                    "Hull **-"
                    + str(
                        applied["hull_damage"]
                    )
                    + "**"
                )

            if applied["sails_damage"]:
                effect_lines.append(
                    "Sails **-"
                    + str(
                        applied["sails_damage"]
                    )
                    + "**"
                )

            if applied["supplies_change"]:
                sign = (
                    "+"
                    if applied[
                        "supplies_change"
                    ] > 0
                    else ""
                )

                effect_lines.append(
                    "Supplies **"
                    + sign
                    + str(
                        applied[
                            "supplies_change"
                        ]
                    )
                    + "**"
                )

            if applied["morale_change"]:
                sign = (
                    "+"
                    if applied[
                        "morale_change"
                    ] > 0
                    else ""
                )

                effect_lines.append(
                    "Morale **"
                    + sign
                    + str(
                        applied[
                            "morale_change"
                        ]
                    )
                    + "**"
                )

            text += (
                "\n\n**ENVIRONMENTAL HAZARD — "
                + str(
                    hazard.get(
                        "name",
                        "Dangerous Waters"
                    )
                )
                + "**"
            )

            if effect_lines:
                text += (
                    "\n"
                    + "\n".join(
                        effect_lines
                    )
                )

            text += (
                "\nHull: **"
                + str(
                    outcome["new"]["hull"]
                )
                + "** | Sails: **"
                + str(
                    outcome["new"]["sails"]
                )
                + "** | Supplies: **"
                + str(
                    outcome["new"]["supplies"]
                )
                + "** | Morale: **"
                + str(
                    outcome["new"]["morale"]
                )
                + "**"
            )

            history_effects = (
                ", ".join(
                    line.replace(
                        "**",
                        ""
                    )
                    for line in effect_lines
                )
                if effect_lines
                else "no lasting damage"
            )

            await add_ship_history(
                message.guild.id,
                (
                    "Exploration near "
                    + result["name"]
                    + " encountered "
                    + str(
                        hazard.get(
                            "name",
                            "dangerous waters"
                        )
                    )
                    + ": "
                    + history_effects
                    + "."
                ),
                "exploration_hazard"
            )

        # ---------------------------------------------------------
        # Treasure
        # ---------------------------------------------------------

        elif encounter_type == "treasure":

            reward = random.randint(
                75,
                250
            )

            ship_after = await add_ship_treasury(
                message.guild.id,
                reward
            )

            text += (
                "\n\n**TREASURE FOUND**\n"
                "Recovered **"
                + str(reward)
                + " doubloons**.\n"
                "Treasury: **"
                + str(ship_after["treasury"])
                + " doubloons**"
            )

            await add_ship_history(
                message.guild.id,
                (
                    "Exploration at "
                    + result["name"]
                    + " uncovered "
                    + str(reward)
                    + " doubloons."
                ),
                "exploration_treasure"
            )

        # ---------------------------------------------------------
        # Supplies
        # ---------------------------------------------------------

        elif encounter_type == "supplies":

            found = random.randint(
                10,
                30
            )

            before = int(
                ship["supplies"]
            )

            ship_after = await add_ship_supplies(
                message.guild.id,
                found
            )

            gained = max(
                0,
                int(ship_after["supplies"])
                - before
            )

            text += (
                "\n\n**SUPPLIES RECOVERED**\n"
                "Supplies **+"
                + str(gained)
                + "**\n"
                "Current supplies: **"
                + str(ship_after["supplies"])
                + "**"
            )

            await add_ship_history(
                message.guild.id,
                (
                    "The crew recovered "
                    + str(gained)
                    + " supplies while exploring "
                    + result["name"]
                    + "."
                ),
                "exploration_supplies"
            )

        # ---------------------------------------------------------
        # Quiet / lore event
        # ---------------------------------------------------------

        else:

            await add_ship_history(
                message.guild.id,
                (
                    "The crew explored "
                    + result["name"]
                    + " without incident."
                ),
                "exploration"
            )

        await message.reply(
            text[:1900],
            mention_author=False
        )

        if result["new"]:

            await post_captains_log(
                message.guild,
                (
                    "**WORLD DISCOVERY**\n"
                    + message.author.display_name
                    + " discovered **"
                    + result["name"]
                    + "** in **"
                    + result["region"]
                    + "**."
                ),
                "world"
            )

        return True
