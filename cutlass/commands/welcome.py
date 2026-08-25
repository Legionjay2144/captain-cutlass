async def handle_welcome_command(
    message,
    command,
    content,
    *,
    is_admin,
    cached_settings,
    set_guild_setting,
    invalidate_settings_cache,
    get_welcome_message,
):

    # =====================================================
    # WELCOME SYSTEM
    # =====================================================

    if command == "!cutlass welcome status":

        settings = await cached_settings(
            message.guild.id
        )

        channel_id = settings[
            "welcome_channel_id"
        ]

        channel = (
            message.guild.get_channel(
                channel_id
            )
            if channel_id
            else None
        )

        channel_text = (
            channel.mention
            if channel
            else "Not configured"
        )

        enabled_text = (
            "Enabled"
            if settings["welcome_enabled"]
            else "Disabled"
        )

        await message.reply(
            (
                "**Welcome System**\n"
                "Status: "
                + enabled_text
                + "\nChannel: "
                + channel_text
            ),
            mention_author=False
        )

        return True


    if command == "!cutlass welcome on":

        if not is_admin(message):

            await message.reply(
                "Only the Admiralty may configure welcomes.",
                mention_author=False
            )

            return True

        settings = await cached_settings(
            message.guild.id
        )

        if not settings[
            "welcome_channel_id"
        ]:

            await message.reply(
                (
                    "Set a welcome channel first with "
                    "`!cutlass welcome channel #channel`."
                ),
                mention_author=False
            )

            return True

        await set_guild_setting(
            message.guild.id,
            "welcome_enabled",
            1
        )

        invalidate_settings_cache(
            message.guild.id
        )

        await message.reply(
            "Welcome messages are now enabled for this ship.",
            mention_author=False
        )

        return True


    if command == "!cutlass welcome off":

        if not is_admin(message):

            await message.reply(
                "Only the Admiralty may configure welcomes.",
                mention_author=False
            )

            return True

        await set_guild_setting(
            message.guild.id,
            "welcome_enabled",
            0
        )

        invalidate_settings_cache(
            message.guild.id
        )

        await message.reply(
            "Welcome messages are now disabled for this ship.",
            mention_author=False
        )

        return True


    if command.startswith(
        "!cutlass welcome channel"
    ):

        if not is_admin(message):

            await message.reply(
                "Only the Admiralty may configure welcomes.",
                mention_author=False
            )

            return True

        channel = None

        if message.channel_mentions:

            channel = message.channel_mentions[0]

        else:

            parts = content.split()

            if len(parts) >= 4:

                raw = parts[3]

                raw = (
                    raw
                    .replace("<#", "")
                    .replace(">", "")
                )

                try:

                    channel_id = int(raw)

                    channel = (
                        message.guild.get_channel(
                            channel_id
                        )
                    )

                except ValueError:

                    channel = None

        if channel is None:

            await message.reply(
                "Use: `!cutlass welcome channel #welcome`",
                mention_author=False
            )

            return True

        await set_guild_setting(
            message.guild.id,
            "welcome_channel_id",
            channel.id
        )

        invalidate_settings_cache(
            message.guild.id
        )

        await message.reply(
            (
                "Welcome channel set to "
                + channel.mention
                + "."
            ),
            mention_author=False
        )

        return True


    if command == "!cutlass testwelcome":

        if not is_admin(message):

            await message.reply(
                (
                    "Only the Admiralty may summon "
                    "imaginary new crewmates."
                ),
                mention_author=False
            )

            return True

        settings = await cached_settings(
            message.guild.id
        )

        mood = settings.get(
            "mood",
            "cheerful"
        )

        greeting = get_welcome_message(
            message.author.mention,
            mood
        )

        await message.reply(
            greeting,
            mention_author=False
        )

        return True


    # =====================================================
    # RETURNING CREWMATES
    # =====================================================

    if command == "!cutlass returners status":

        settings = await cached_settings(
            message.guild.id
        )

        await message.reply(
            (
                "**Returning Crewmates**\n"
                "Status: "
                + (
                    "Enabled"
                    if settings.get(
                        "returning_enabled"
                    )
                    else "Disabled"
                )
                + "\nAbsence threshold: "
                + str(
                    settings.get(
                        "returning_days",
                        14
                    )
                )
                + " days"
            ),
            mention_author=False
        )

        return True


    if command in (
        "!cutlass returners on",
        "!cutlass returners off"
    ):

        if not is_admin(message):

            await message.reply(
                (
                    "Only the Admiralty may configure "
                    "returning crewmates."
                ),
                mention_author=False
            )

            return True

        enabled = command.endswith(" on")

        await set_guild_setting(
            message.guild.id,
            "returning_enabled",
            1 if enabled else 0
        )

        invalidate_settings_cache(
            message.guild.id
        )

        await message.reply(
            (
                "Returning crewmate greetings are now "
                + (
                    "enabled."
                    if enabled
                    else "disabled."
                )
            ),
            mention_author=False
        )

        return True


    if command.startswith(
        "!cutlass returners days "
    ):

        if not is_admin(message):

            await message.reply(
                (
                    "Only the Admiralty may configure "
                    "returning crewmates."
                ),
                mention_author=False
            )

            return True

        try:

            days = int(
                content.split()[-1]
            )

            if days < 1 or days > 365:
                raise ValueError

        except ValueError:

            await message.reply(
                "Choose between 1 and 365 days.",
                mention_author=False
            )

            return True

        await set_guild_setting(
            message.guild.id,
            "returning_days",
            days
        )

        invalidate_settings_cache(
            message.guild.id
        )

        await message.reply(
            (
                "I'll call a crewmate returning after **"
                + str(days)
                + " days** away."
            ),
            mention_author=False
        )

        return True


    return False
