async def handle_battle_command(
    message,
    command,
    *,
    is_admin,
    get_ship_settings,
    get_ship,
    get_ship_operational_status,
    start_naval_battle,
    get_active_monster,
    format_battle,
    attack_enemy,
    defend,
    board_enemy,
    flee_battle,
    damage_ship,
    reward_ship,
    record_captured_ship,
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

        operational = await get_ship_operational_status(
            message.guild.id,
            ship=ship
        )

        if not operational["operational"]:
            await message.reply(
                "**SHIP DISABLED / RECOVERING**\n"
                "The Living Ship cannot start a naval battle until it reaches **"
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
            message.guild.id,
            ship=ship
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

        operational = await get_ship_operational_status(
            message.guild.id
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

        if ship_after:

            operational_after = await get_ship_operational_status(
                message.guild.id,
                ship=ship_after
            )

            if not operational_after["operational"]:

                if int(ship_after["hull"]) <= 0:
                    text += (
                        "\n\n**SHIP DISABLED!**\n"
                        "The hull has been battered to **0/"
                        + str(operational_after["max_hull"])
                        + "**. Passive emergency recovery has begun."
                    )

                else:
                    text += (
                        "\n\n**SHIP DISABLED / RECOVERING!**\n"
                        "Current hull: **"
                        + str(operational_after["hull"])
                        + "/"
                        + str(operational_after["max_hull"])
                        + "**\n"
                        "Operational at: **"
                        + str(operational_after["threshold"])
                        + "/"
                        + str(operational_after["max_hull"])
                        + "**."
                    )

                await add_ship_history(
                    message.guild.id,
                    (
                        "The ship became non-operational during naval combat at "
                        + str(operational_after["hull"])
                        + "/"
                        + str(operational_after["max_hull"])
                        + " hull."
                    ),
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
                xp_reward=xp_reward,
                achievement_user_id=message.author.id
            )

            if result.get("boarded"):
                capture = await record_captured_ship(
                    message.guild.id,
                    result.get(
                        "enemy_name",
                        "an enemy vessel"
                    ),
                    captured_by_user_id=message.author.id,
                    captured_by_name=message.author.display_name,
                    reward=reward,
                    xp_reward=xp_reward,
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

            if awarded.get("milestone_text"):
                text += (
                    "\n"
                    + awarded["milestone_text"]
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

        operational = await get_ship_operational_status(
            message.guild.id,
            ship=ship
        )

        if not operational["operational"]:
            await message.reply(
                "**SHIP DISABLED / RECOVERING**\n"
                "The Living Ship cannot defend in combat until it reaches **"
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

        ok, text, result = await defend(
            message.guild.id,
            ship=ship
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

            operational_after = await get_ship_operational_status(
                message.guild.id,
                ship=ship_after
            )

            if not operational_after["operational"]:

                if int(ship_after["hull"]) <= 0:
                    text += (
                        "\n\n**SHIP DISABLED!**\n"
                        "The hull has been reduced to **0/"
                        + str(operational_after["max_hull"])
                        + "**."
                    )

                else:
                    text += (
                        "\n\n**SHIP DISABLED / RECOVERING!**\n"
                        "Current hull: **"
                        + str(operational_after["hull"])
                        + "/"
                        + str(operational_after["max_hull"])
                        + "**\n"
                        "Operational at: **"
                        + str(operational_after["threshold"])
                        + "/"
                        + str(operational_after["max_hull"])
                        + "**."
                    )

                await add_ship_history(
                    message.guild.id,
                    (
                        "The ship became non-operational while defending "
                        "during naval combat at "
                        + str(operational_after["hull"])
                        + "/"
                        + str(operational_after["max_hull"])
                        + " hull."
                    ),
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
                "The Living Ship cannot attempt boarding until it reaches **"
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

        ok, text, result = await board_enemy(
            message.guild.id,
            ship=ship
        )

        if not ok:
            await message.reply(
                text,
                mention_author=False
            )
            return True

        result = result or {}

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
                + str(ship_after["name"])
                + "**\n"
                "Hull: **"
                + str(ship_after["hull"])
                + "**"
            )

            operational_after = await get_ship_operational_status(
                message.guild.id,
                ship=ship_after
            )

            if not operational_after["operational"]:

                if int(ship_after["hull"]) <= 0:
                    text += (
                        "\n\n**SHIP DISABLED!**\n"
                        "The failed boarding action reduced the ship to **0/"
                        + str(operational_after["max_hull"])
                        + "**."
                    )

                else:
                    text += (
                        "\n\n**SHIP DISABLED / RECOVERING!**\n"
                        "The failed boarding action left the ship below "
                        "operational hull.\n"
                        "Current hull: **"
                        + str(operational_after["hull"])
                        + "/"
                        + str(operational_after["max_hull"])
                        + "**\n"
                        "Operational at: **"
                        + str(operational_after["threshold"])
                        + "/"
                        + str(operational_after["max_hull"])
                        + "**."
                    )

                await add_ship_history(
                    message.guild.id,
                    (
                        "The ship became non-operational during a failed "
                        "boarding action at "
                        + str(operational_after["hull"])
                        + "/"
                        + str(operational_after["max_hull"])
                        + " hull."
                    ),
                    "battle_defeat"
                )

        if result.get("victory"):

            reward = int(
                result.get(
                    "reward",
                    0
                )
            )

            xp_reward = int(
                result.get(
                    "xp",
                    0
                )
            )

            awarded = await reward_ship(
                message.guild.id,
                doubloons=reward,
                xp_reward=xp_reward,
                achievement_user_id=message.author.id
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

            if awarded.get("milestone_text"):
                text += (
                    "\n"
                    + awarded["milestone_text"]
                )

            await add_ship_history(
                message.guild.id,
                (
                    "Captured "
                    + str(result.get(
                        "enemy_name",
                        "an enemy vessel"
                    ))
                    + " by boarding. Treasury +"
                    + str(reward)
                    + ", XP +"
                    + str(xp_reward)
                    + "."
                ),
                "battle_boarding"
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
