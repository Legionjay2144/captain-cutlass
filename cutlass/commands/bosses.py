async def handle_boss_command(
    message,
    command,
    *,
    get_ship_settings,
    get_ship,
    get_active_battle,
    get_active_monster,
    get_active_boss,
    format_boss,
    attack_boss,
    defend_boss,
    damage_ship,
    reward_ship,
    add_ship_history,
    post_captains_log
):

    if not command.startswith(
        "!cutlass boss"
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

    ship_channel = message.guild.get_channel(
        settings.get("channel_id", 0)
    )

    if (
        ship_channel
        and message.channel.id != ship_channel.id
    ):
        await message.reply(
            "Boss encounters belong in "
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
            "Repair before challenging a boss.",
            mention_author=False
        )
        return True

    if command == "!cutlass boss":

        await message.reply(
            await format_boss(
                message.guild.id
            ),
            mention_author=False
        )

        return True

    if command in (
        "!cutlass boss attack",
        "!cutlass boss defend"
    ):

        boss = await get_active_boss(
            message.guild.id
        )

        if not boss:
            await message.reply(
                "There is no active boss encounter.",
                mention_author=False
            )
            return True

    if command == "!cutlass boss attack":

        ok, text, result = await attack_boss(
            message.guild.id
        )

        if not ok:
            await message.reply(
                text,
                mention_author=False
            )
            return True

        damage = int(
            result.get(
                "enemy_damage",
                0
            )
        )

        if damage > 0:

            ship_after = await damage_ship(
                message.guild.id,
                damage
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
                    "The boss has battered the ship into submission."
                )

                await add_ship_history(
                    message.guild.id,
                    (
                        "The ship was disabled while fighting "
                        + result["name"]
                        + "."
                    ),
                    "boss_defeat"
                )

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
                "\n\n**LEGENDARY VICTORY**\n"
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
                    "Defeated legendary boss "
                    + result["name"]
                    + ". Treasury +"
                    + str(reward)
                    + ", XP +"
                    + str(xp)
                    + "."
                ),
                "boss_victory"
            )

            await post_captains_log(
                message.guild,
                text,
                "boss"
            )

        await message.reply(
            text[:1900],
            mention_author=False
        )

        return True

    if command == "!cutlass boss defend":

        ok, text, result = await defend_boss(
            message.guild.id
        )

        if not ok:
            await message.reply(
                text,
                mention_author=False
            )
            return True

        damage = int(
            result.get(
                "enemy_damage",
                0
            )
        )

        if damage > 0:

            ship_after = await damage_ship(
                message.guild.id,
                damage
            )

            text += (
                "\n\n**"
                + ship_after["name"]
                + "**\n"
                "Hull: **"
                + str(ship_after["hull"])
                + "**"
            )

        await message.reply(
            text[:1900],
            mention_author=False
        )

        return True

    await message.reply(
        "Unknown boss command. "
        "Use `!cutlass boss`, `!cutlass boss attack`, "
        "or `!cutlass boss defend`.",
        mention_author=False
    )

    return True
