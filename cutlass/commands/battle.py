async def handle_battle_command(
    message,
    command,
    *,
    is_admin,
    get_ship_settings,
    get_ship,
    start_naval_battle,
    get_active_monster,
    format_battle,
    attack_enemy,
    defend,
    flee_battle,
    damage_ship,
    reward_ship,
    combat_ship_status,
    add_ship_history,
    post_captains_log
):

    if not command.startswith(
        "!cutlass battle"
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
            "Naval combat belongs in "
            + ship_channel.mention
            + ".",
            mention_author=False
        )
        return True

    if command == "!cutlass battle":

        await message.reply(
            await format_battle(
                message.guild.id
            ),
            mention_author=False
        )

        return True

    if command == "!cutlass battle start":

        ship = await get_ship(
            message.guild.id
        )

        if int(ship["hull"]) <= 0:
            await message.reply(
                "**THE SHIP IS DISABLED**\n"
                "The hull is at zero. Repair the ship before seeking battle.",
                mention_author=False
            )
            return True

        if not is_admin(message):
            await message.reply(
                "Only the Admiralty may deliberately seek battle.",
                mention_author=False
            )
            return True

        monster = await get_active_monster(
            message.guild.id
        )

        if monster:
            await message.reply(
                "Ye've already got **"
                + monster["name"]
                + "** trying to tear the ship apart. "
                "Deal with that before picking a fight with another vessel.",
                mention_author=False
            )
            return True

        created, battle = await start_naval_battle(
            message.guild.id
        )

        if not created:
            await message.reply(
                "An enemy vessel is already engaged.\n\n"
                + await format_battle(
                    message.guild.id
                ),
                mention_author=False
            )
            return True

        text = (
            "**ENEMY SHIP SIGHTED**\n"
            + battle["enemy_name"]
            + " approaches under the command of **"
            + battle["enemy_captain"]
            + "**.\n"
            "Danger: **"
            + battle["danger"]
            + "**\n"
            "Enemy Hull: **"
            + str(battle["enemy_hull"])
            + "**"
        )

        await message.reply(
            text,
            mention_author=False
        )

        await post_captains_log(
            message.guild,
            text,
            "battle"
        )

        return True

    if command == "!cutlass battle attack":

        ship = await get_ship(
            message.guild.id
        )

        if int(ship["hull"]) <= 0:
            await message.reply(
                "**THE SHIP IS DISABLED**\n"
                "The hull is too badly damaged to continue fighting. "
                "Repair the ship before returning to battle.",
                mention_author=False
            )
            return True

        ok, text, result = await attack_enemy(
            message.guild.id,
            ship
        )

        if not ok:
            await message.reply(
                text,
                mention_author=False
            )
            return True

        enemy_damage = 0

        if result:
            enemy_damage = int(
                result.get("enemy_damage", 0)
            )

        ship_after = None

        if enemy_damage > 0:
            ship_after = await damage_ship(
                message.guild.id,
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

        if (
            ship_after
            and int(ship_after["hull"]) <= 0
        ):
            text += (
                "\n\n**SHIP DISABLED!**\n"
                "The hull has been battered to zero. "
                "The crew can no longer continue the fight."
            )

            await add_ship_history(
                message.guild.id,
                "The ship was disabled during naval combat.",
                "battle_defeat"
            )

            await message.reply(
                text,
                mention_author=False
            )

            await post_captains_log(
                message.guild,
                text,
                "battle"
            )

            return True

        if result and result.get("victory"):

            reward = int(
                result.get("reward", 0)
            )

            xp_reward = int(
                result.get("xp", 0)
            )

            awarded = await reward_ship(
                message.guild.id,
                doubloons=reward,
                xp_reward=xp_reward
            )

            text += (
                "\n\n**LIVING SHIP UPDATED**\n"
                "Treasury: **+"
                + str(reward)
                + " doubloons**\n"
                "Ship XP: **+"
                + str(xp_reward)
                + "**"
            )

            if awarded["levels_gained"]:
                text += (
                    "\nThe ship reached **Level "
                    + str(awarded["level"])
                    + "**!"
                )

            await add_ship_history(
                message.guild.id,
                (
                    "Defeated "
                    + str(result.get(
                        "enemy_name",
                        "an enemy vessel"
                    ))
                    + " in naval combat. Treasury +"
                    + str(reward)
                    + ", XP +"
                    + str(xp_reward)
                    + "."
                ),
                "battle_victory"
            )

            await post_captains_log(
                message.guild,
                text,
                "battle"
            )

        await message.reply(
            text,
            mention_author=False
        )

        return True


    if command == "!cutlass battle defend":

        ship = await get_ship(
            message.guild.id
        )

        if int(ship["hull"]) <= 0:
            await message.reply(
                "**THE SHIP IS DISABLED**\n"
                "The crew cannot defend a ship with no hull remaining. "
                "Repairs are required.",
                mention_author=False
            )
            return True

        ok, text, result = await defend(
            message.guild.id
        )

        if not ok:
            await message.reply(
                text,
                mention_author=False
            )
            return True

        damage = 0

        if result:
            damage = int(
                result.get("enemy_damage", 0)
            )

        if damage > 0:

            ship_after = await damage_ship(
                message.guild.id,
                damage
            )

            text += (
                "\n\n**"
                + str(ship_after["name"])
                + "**\n"
                "Hull: **"
                + str(ship_after["hull"])
                + "**"
            )

            if int(ship_after["hull"]) <= 0:

                text += (
                    "\n\n**SHIP DISABLED!**\n"
                    "The hull has been reduced to zero."
                )

                await add_ship_history(
                    message.guild.id,
                    "The ship was disabled while defending during naval combat.",
                    "battle_defeat"
                )

                await post_captains_log(
                    message.guild,
                    text,
                    "battle"
                )

        await message.reply(
            text,
            mention_author=False
        )

        return True


    if command == "!cutlass battle flee":

        ok, text = await flee_battle(
            message.guild.id
        )

        await message.reply(
            text,
            mention_author=False
        )

        return True

    if command == "!cutlass battle board":

        await message.reply(
            "Boarding actions are coming with the next combat expansion.",
            mention_author=False
        )

        return True

    await message.reply(
        "Unknown battle command. "
        "Use `!cutlass battle`.",
        mention_author=False
    )

    return True
