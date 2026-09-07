import random

from cutlass.world.locks import get_guild_lock


async def handle_exploration_command(
    message,
    command,
    *,
    cached_settings,
    award_achievement,
    get_ship,
    get_ship_operational_status,
    get_active_battle,
    get_active_monster,
    get_active_boss,
    explore_random_island,
    count_world_discoveries,
    count_hidden_discoveries,
    count_world_findings,
    start_naval_battle,
    start_monster_encounter,
    add_ship_treasury,
    add_ship_supplies,
    apply_exploration_outcome,
    add_ship_history,
    discover_world_finding,
    add_world_history,
    post_captains_log
):

    if command not in (
        "!cutlass explore",
        "!cutlass explore island"
    ):
        return False

    settings = await cached_settings(
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
        message.guild.id,
        ship=ship
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

        unlocked_achievements = []

        async def unlock_achievement(name, description):
            success = await award_achievement(
                message.guild.id,
                message.author.id,
                name,
                description
            )

            if success:
                unlocked_achievements.append(
                    name
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

        active_event = result.get(
            "world_event"
        )

        if active_event:
            event_history = (
                message.author.display_name
                + " explored "
                + result["name"]
                + " during "
                + active_event["name"]
                + " in "
                + result["region"]
                + "."
            )

            await add_world_history(
                message.guild.id,
                event_history,
                "world_event",
                int(
                    active_event.get(
                        "importance",
                        5
                    )
                )
            )

            await post_captains_log(
                message.guild,
                (
                    "**LIVING WORLD EVENT**\n"
                    + event_history
                ),
                "world"
            )

            await unlock_achievement(
                "Event Witness",
                "Explored the Living Pirate World during an active world event."
            )

        world_event = result.get(
            "world_event"
        )

        if world_event:
            text += (
                "\n\n**LIVING WORLD EVENT — "
                + world_event["name"]
                + "**\n"
                + world_event.get(
                    "effect_text",
                    ""
                )
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
                ship=ship,
                region_profile=result.get(
                    "encounter_profile"
                )
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

            ship = await get_ship(
                message.guild.id
            )

            created, monster = await start_monster_encounter(
                message.guild.id,
                ship=ship,
                region_profile=result.get(
                    "encounter_profile"
                )
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

            treasure_multiplier = float(
                (
                    world_event
                    or {}
                ).get(
                    "treasure_multiplier",
                    1.0
                )
            )

            if treasure_multiplier != 1.0:
                base_reward = reward

                reward = max(
                    1,
                    int(
                        round(
                            reward
                            * treasure_multiplier
                        )
                    )
                )

                bonus = (
                    reward
                    - base_reward
                )

                if bonus > 0:
                    text += (
                        "\n\n**WORLD EVENT BONUS**\n"
                        "Event conditions increased the "
                        "treasure haul by **"
                        + str(bonus)
                        + " doubloons**."
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

            supplies_multiplier = float(
                (
                    world_event
                    or {}
                ).get(
                    "supplies_multiplier",
                    1.0
                )
            )

            if supplies_multiplier != 1.0:
                base_found = found

                found = max(
                    1,
                    int(
                        round(
                            found
                            * supplies_multiplier
                        )
                    )
                )

                difference = (
                    found
                    - base_found
                )

                if difference > 0:
                    text += (
                        "\n\n**WORLD EVENT BONUS**\n"
                        "Event conditions increased the "
                        "recoverable supplies by **+"
                        + str(difference)
                        + "**."
                    )

                elif difference < 0:
                    text += (
                        "\n\n**WORLD EVENT CONDITIONS**\n"
                        "Regional conditions reduced the "
                        "recoverable supplies by **"
                        + str(
                            abs(difference)
                        )
                        + "**."
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

            finding_discovered = False

            # -------------------------------------------------
            # Unique world finding roll
            #
            # Findings may only appear during a quiet revisit
            # to an already-charted location.
            #
            # New-island discovery remains its own event and
            # cannot reveal the island's internal finding in
            # the same command.
            # -------------------------------------------------

            if (
                not result["new"]
                and random.randint(1, 100) <= 30
            ):

                finding_key = result.get(
                    "finding_key"
                )

                if finding_key:

                    claimed, finding = (
                        await discover_world_finding(
                            message.guild.id,
                            finding_key,
                            message.author.id,
                            message.author.display_name
                        )
                    )

                    if claimed and finding:

                        finding_discovered = True

                        finding_name = finding[
                            "name"
                        ]

                        finding_rarity = finding[
                            "rarity"
                        ]

                        finding_type = (
                            finding[
                                "finding_type"
                            ]
                            .replace(
                                "_",
                                " "
                            )
                            .title()
                        )

                        text += (
                            "\n\n"
                            "**WORLD FINDING**\n"
                            "**"
                            + finding_name
                            + "**\n"
                            + finding[
                                "description"
                            ]
                            + "\n"
                            + finding_rarity
                            + " "
                            + finding_type
                        )

                        history_text = (
                            message.author.display_name
                            + " uncovered **"
                            + finding_name
                            + "** while exploring **"
                            + result["name"]
                            + "**."
                        )

                        await add_ship_history(
                            message.guild.id,
                            history_text,
                            "world_finding"
                        )

                        importance = 5

                        if finding_rarity == "Rare":
                            importance = 7

                        elif finding_rarity == "Legendary":
                            importance = 9

                        await add_world_history(
                            message.guild.id,
                            history_text,
                            "finding",
                            importance
                        )

                        if finding_rarity in (
                            "Rare",
                            "Legendary"
                        ):

                            await post_captains_log(
                                message.guild,
                                (
                                    "**WORLD FINDING**\n"
                                    + message.author.display_name
                                    + " uncovered **"
                                    + finding_name
                                    + "** at **"
                                    + result["name"]
                                    + "**."
                                ),
                                "world"
                            )

            if not finding_discovered:

                await add_ship_history(
                    message.guild.id,
                    (
                        "The crew explored "
                        + result["name"]
                        + " without incident."
                    ),
                    "exploration"
                )

        if result["new"]:

            discovery_count = await count_world_discoveries(
                message.guild.id,
                message.author.id
            )

            if discovery_count == 1:
                await unlock_achievement(
                    "Charted Waters",
                    "Discovered an island for the first time."
                )

            if discovery_count == 5:
                await unlock_achievement(
                    "Cartographer",
                    "Discovered five islands."
                )

            if discovery_count == 10:
                await unlock_achievement(
                    "Master Cartographer",
                    "Discovered ten islands."
                )

            if result.get("hidden"):
                hidden_discovery_count = await count_hidden_discoveries(
                    message.guild.id,
                    message.author.id
                )

                if hidden_discovery_count == 1:
                    await unlock_achievement(
                        "Hidden Passage",
                        "Discovered a hidden island."
                    )

        if finding_discovered:

            finding_count = await count_world_findings(
                message.guild.id,
                message.author.id
            )

            if finding_count == 1:
                await unlock_achievement(
                    "Field Naturalist",
                    "Discovered a world finding for the first time."
                )

            if finding_rarity == "Legendary":
                await unlock_achievement(
                    "Legend Hunter",
                    "Discovered a legendary world finding."
                )

        await message.reply(
            text[:1900],
            mention_author=False
        )

        if unlocked_achievements:
            await message.channel.send(
                (
                    message.author.display_name
                    + " earned "
                    + ", ".join(
                        "**" + achievement + "**"
                        for achievement in unlocked_achievements
                    )
                    + "."
                )
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
