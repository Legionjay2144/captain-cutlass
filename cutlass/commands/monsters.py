async def handle_monster_command(
    message,
    command,
    *,
    is_admin,
    get_ship_settings,
    get_ship,
    start_monster_encounter,
    get_active_battle,
    format_monster,
    attack_monster,
    damage_ship,
    reward_ship,
    add_ship_history,
    post_captains_log
):

    if not command.startswith(
        "!cutlass monster"
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

    if int(ship["hull"]) <= 0:
        await message.reply(
            "**THE SHIP IS DISABLED**\n"
            "Repair the hull before facing anything with tentacles.",
            mention_author=False
        )
        return True

    if command in (
        "!cutlass monster",
        "!cutlass monsters"
    ):
        await message.reply(
            await format_monster(
                message.guild.id
            ),
            mention_author=False
        )
        return True

    if command.startswith(
        "!cutlass monster start"
    ):


        parts = command.split()

        key = (
            parts[3]
            if len(parts) >= 4
            else None
        )

        battle = await get_active_battle(
            message.guild.id
        )

        if battle:
            await message.reply(
                "We're already trading cannon fire with **"
                + battle["enemy_name"]
                + "**. One catastrophe at a time, matey.",
                mention_author=False
            )
            return True

        ship = await get_ship(
            message.guild.id
        )

        created, result = await start_monster_encounter(
            message.guild.id,
            key,
            ship=ship
        )

        if not created:
            await message.reply(
                "A monster encounter is already active.",
                mention_author=False
            )
            return True

        text = (
            "**SEA MONSTER SIGHTED**\n"
            + result["name"]
            + " rises from the sea.\n"
            "Danger: **"
            + result["danger"]
            + "**\n"
            "HP: **"
            + str(result["hp"])
            + "**"
        )

        await message.reply(
            text,
            mention_author=False
        )

        await post_captains_log(
            message.guild,
            text,
            "monster"
        )

        return True

    if command == "!cutlass monster attack":

        ship = await get_ship(
            message.guild.id
        )

        ok, text, result = await attack_monster(
            message.guild.id,
            ship=ship
        )

        if not ok:
            await message.reply(
                text,
                mention_author=False
            )
            return True

        enemy_damage = int(
            result.get(
                "enemy_damage",
                0
            )
        )

        if enemy_damage > 0:

            ship_after = await damage_ship(
                message.guild.id,
                enemy_damage
            )

            text += (
                "\n\n**"
                + ship_after["name"]
                + "**\n"
                "Hull: **"
                + str(ship_after["hull"])
                + "**"
            )

            if int(ship_after["hull"]) <= 0:

                text += (
                    "\n\n**SHIP DISABLED!**\n"
                    "The monster has battered the hull to zero. "
                    "The crew can no longer continue the fight."
                )

                await add_ship_history(
                    message.guild.id,
                    (
                        "The ship was disabled while fighting "
                        + str(
                            result.get(
                                "name",
                                "a sea monster"
                            )
                        )
                        + "."
                    ),
                    "monster_defeat"
                )

                await post_captains_log(
                    message.guild,
                    text,
                    "monster"
                )

                await message.reply(
                    text[:1900],
                    mention_author=False
                )

                return True

        if result.get("victory"):

            reward = int(
                result["reward"]
            )

            xp = int(
                result["xp"]
            )

            award = await reward_ship(
                message.guild.id,
                reward,
                xp
            )

            text += (
                "\n\n**LIVING SHIP UPDATED**\n"
                "Treasury: **+"
                + str(reward)
                + "**\n"
                "Ship XP: **+"
                + str(xp)
                + "**"
            )

            if award["levels_gained"]:
                text += (
                    "\nShip reached **Level "
                    + str(award["level"])
                    + "**!"
                )

            await add_ship_history(
                message.guild.id,
                (
                    "Defeated "
                    + result["name"]
                    + ". Treasury +"
                    + str(reward)
                    + ", XP +"
                    + str(xp)
                    + "."
                ),
                "monster_victory"
            )

            await post_captains_log(
                message.guild,
                text,
                "monster"
            )

        await message.reply(
            text,
            mention_author=False
        )

        return True

    await message.reply(
        "Unknown monster command.",
        mention_author=False
    )

    return True
