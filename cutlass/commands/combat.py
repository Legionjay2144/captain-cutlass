from cutlass.world.locks import get_guild_lock

async def handle_combat_command(
    message,
    command,
    *,
    get_ship_settings,
    get_ship,
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
    post_captains_log
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

    if not action:
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

        ship = await get_ship(
            guild_id
        )

        if int(ship["hull"]) <= 0:
            await message.reply(
                "**THE SHIP IS DISABLED**\n"
                "The Living Ship is at **0 hull**. "
                "Repair the ship before continuing combat.",
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

            if encounter == "naval":

                ok, text = await flee_battle(
                    guild_id
                )

                await message.reply(
                    text,
                    mention_author=False
                )

                return True

            if encounter == "monster":

                await message.reply(
                    "**NO ESCAPE!**\n"
                    "The sea monster has the ship engaged. "
                    "The crew must defeat it or survive the fight.",
                    mention_author=False
                )

                return True

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
        # Perform ATTACK / DEFEND
        # ---------------------------------------------------------

        if encounter == "naval":

            if action == "attack":

                ok, text, result = await attack_enemy(
                    guild_id,
                    ship
                )

            elif action == "board":

                ok, text, result = await board_enemy(
                    guild_id,
                    ship=ship
                )

            else:

                ok, text, result = await defend(
                    guild_id,
                    ship=ship
                )

        elif encounter == "monster":

            ok, text, result = await attack_monster(
                guild_id,
                ship=ship
            )

        else:

            if action == "attack":

                ok, text, result = await attack_boss(
                    guild_id,
                    ship=ship
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
        # Apply incoming damage
        # ---------------------------------------------------------

        enemy_damage = int(
            result.get(
                "enemy_damage",
                0
            )
        )

        ship_after = None

        if enemy_damage > 0:

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

        # ---------------------------------------------------------
        # Ship disabled
        # ---------------------------------------------------------

        if (
            ship_after
            and int(ship_after["hull"]) <= 0
        ):

            text += (
                "\n\n**SHIP DISABLED!**\n"
                "The hull has been battered to zero. "
                "The crew can no longer continue the fight."
            )

            history_type = (
                "battle_defeat"
                if encounter == "naval"
                else (
                    "monster_defeat"
                    if encounter == "monster"
                    else "boss_defeat"
                )
            )

            await add_ship_history(
                guild_id,
                "The Living Ship was disabled during "
                + encounter
                + " combat.",
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

        # ---------------------------------------------------------
        # Victory rewards
        # ---------------------------------------------------------

        if result.get("victory"):

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
                xp
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
