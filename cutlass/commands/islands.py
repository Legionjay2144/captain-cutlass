import random


async def handle_island_command(
    message,
    command,
    *,
    get_ship_settings,
    get_ship,
    get_active_battle,
    get_active_monster,
    format_island,
    choose_island_activity,
    add_ship_treasury,
    add_ship_supplies,
    add_ship_history,
    start_monster_encounter,
    start_boss,
    get_active_boss,
    post_captains_log
):

    if not command.startswith("!cutlass island"):
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

    ship_channel = message.guild.get_channel(
        settings.get("channel_id", 0)
    )

    if (
        ship_channel
        and message.channel.id != ship_channel.id
    ):
        await message.reply(
            "Island business belongs in "
            + ship_channel.mention
            + ".",
            mention_author=False
        )
        return True

    ship = await get_ship(
        message.guild.id
    )

    if int(ship["hull"]) <= 0:
        await message.reply(
            "**THE SHIP IS DISABLED**\n"
            "Repair the hull before venturing ashore.",
            mention_author=False
        )
        return True

    if await get_active_battle(
        message.guild.id
    ):
        await message.reply(
            "Finish the current naval battle before heading ashore.",
            mention_author=False
        )
        return True

    if await get_active_monster(
        message.guild.id
    ):
        await message.reply(
            "There's still a sea monster threatening the ship.",
            mention_author=False
        )
        return True

    location = ship["location"]

    if command == "!cutlass island":

        text = format_island(
            location
        )

        if text is None:
            await message.reply(
                "The ship is not currently anchored at an explorable island.",
                mention_author=False
            )
            return True

        await message.reply(
            text,
            mention_author=False
        )
        return True

    if command == "!cutlass island explore":

        activity = choose_island_activity(
            location
        )

        if activity is None:
            await message.reply(
                "There is nothing here to explore.",
                mention_author=False
            )
            return True

        text = (
            "**"
            + activity["title"].upper()
            + "**\n"
            + activity["description"]
        )

        kind = activity["type"]

        if kind == "treasure":

            reward = random.randint(
                activity["reward_min"],
                activity["reward_max"]
            )

            ship_after = await add_ship_treasury(
                message.guild.id,
                reward
            )

            text += (
                "\n\nTreasure recovered: **"
                + str(reward)
                + " doubloons**\n"
                "Treasury: **"
                + str(ship_after["treasury"])
                + "**"
            )

            await add_ship_history(
                message.guild.id,
                (
                    "Island exploration at "
                    + location
                    + " recovered "
                    + str(reward)
                    + " doubloons."
                ),
                "island_treasure"
            )

        elif kind == "supplies":

            amount = random.randint(
                activity["amount_min"],
                activity["amount_max"]
            )

            before = int(
                ship["supplies"]
            )

            ship_after = await add_ship_supplies(
                message.guild.id,
                amount
            )

            gained = max(
                0,
                int(ship_after["supplies"])
                - before
            )

            text += (
                "\n\nSupplies recovered: **+"
                + str(gained)
                + "**\n"
                "Current supplies: **"
                + str(ship_after["supplies"])
                + "**"
            )

            await add_ship_history(
                message.guild.id,
                (
                    "Island exploration at "
                    + location
                    + " recovered "
                    + str(gained)
                    + " supplies."
                ),
                "island_supplies"
            )

        elif kind == "monster":

            created, monster = await start_monster_encounter(
                message.guild.id,
                activity["monster"]
            )

            if created:
                text += (
                    "\n\n**SEA MONSTER ENCOUNTER**\n"
                    + monster["name"]
                    + " appears!\n"
                    "HP: **"
                    + str(monster["hp"])
                    + "**\n"
                    "Use `!cutlass monster`."
                )

        elif kind == "boss":

            if await get_active_boss(
                message.guild.id
            ):
                text += (
                    "\n\nA boss encounter is already active."
                )

            else:
                created, boss = await start_boss(
                    message.guild.id,
                    activity["boss"]
                )

                if created:
                    text += (
                        "\n\n**BOSS ENCOUNTER**\n"
                        + boss["name"]
                        + " emerges!\n"
                        "Danger: **"
                        + boss["danger"]
                        + "**\n"
                        "HP: **"
                        + str(boss["hp"])
                        + "**\n"
                        "Use `!cutlass boss`."
                    )

                    await add_ship_history(
                        message.guild.id,
                        (
                            "The crew discovered "
                            + boss["name"]
                            + " at "
                            + location
                            + "."
                        ),
                        "boss_discovery"
                    )

        elif kind == "lore":

            await add_ship_history(
                message.guild.id,
                (
                    activity["title"]
                    + ": "
                    + activity["description"]
                ),
                "island_lore"
            )

            text += (
                "\n\nThe discovery has been added to the ship's history."
            )

        await message.reply(
            text[:1900],
            mention_author=False
        )

        await post_captains_log(
            message.guild,
            (
                "**ISLAND EXPLORATION**\n"
                + text
            )[:1900],
            "world"
        )

        return True

    await message.reply(
        "Unknown island command. "
        "Use `!cutlass island` or `!cutlass island explore`.",
        mention_author=False
    )

    return True
