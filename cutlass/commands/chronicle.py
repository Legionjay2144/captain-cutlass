async def handle_chronicle_command(
    message,
    command,
    *,
    is_admin,
    cached_settings,
    set_guild_setting,
    invalidate_settings_cache,
    get_latest_chronicle,
    generate_chronicle
):
    """
    Handle Captain's Log and Chronicle commands.

    Returns True when a Chronicle command was handled.
    Returns False when the command belongs to another subsystem.
    """

    # ---------------------------------------------------------
    # Captain's Log status
    # ---------------------------------------------------------

    if command == "!cutlass log status":

        settings = await cached_settings(
            message.guild.id
        )

        channel = message.guild.get_channel(
            settings.get(
                "chronicle_channel_id",
                0
            )
        )

        await message.reply(
            "**Captain's Log**\n"
            "Status: "
            + (
                "Enabled"
                if settings.get("chronicle_enabled")
                else "Disabled"
            )
            + "\nChannel: "
            + (
                channel.mention
                if channel
                else "Not configured"
            )
            + "\nWeekly chronicles: "
            + (
                "Enabled"
                if settings.get("chronicle_enabled")
                else "Disabled"
            ),
            mention_author=False
        )

        return True

    # ---------------------------------------------------------
    # Captain's Log channel
    # ---------------------------------------------------------

    if command.startswith(
        "!cutlass log channel"
    ):

        if not is_admin(message):

            await message.reply(
                "Only the Admiralty may move the Captain's Log.",
                mention_author=False
            )

            return True

        channel = (
            message.channel_mentions[0]
            if message.channel_mentions
            else None
        )

        if channel is None:

            await message.reply(
                "Use: `!cutlass log channel #captains-log`",
                mention_author=False
            )

            return True

        await set_guild_setting(
            message.guild.id,
            "chronicle_channel_id",
            channel.id
        )

        invalidate_settings_cache(
            message.guild.id
        )

        await message.reply(
            "Captain's Log set to "
            + channel.mention
            + ".",
            mention_author=False
        )

        return True

    # ---------------------------------------------------------
    # Captain's Log enable / disable
    # ---------------------------------------------------------

    if command in (
        "!cutlass log on",
        "!cutlass log off"
    ):

        if not is_admin(message):
            return True

        enabled = command.endswith(" on")

        if enabled:

            settings = await cached_settings(
                message.guild.id
            )

            if not settings.get(
                "chronicle_channel_id"
            ):

                await message.reply(
                    "Set the channel first with "
                    "`!cutlass log channel #captains-log`.",
                    mention_author=False
                )

                return True

        await set_guild_setting(
            message.guild.id,
            "chronicle_enabled",
            1 if enabled else 0
        )

        invalidate_settings_cache(
            message.guild.id
        )

        await message.reply(
            "Captain's Log is now "
            + (
                "enabled."
                if enabled
                else "disabled."
            ),
            mention_author=False
        )

        return True

    # ---------------------------------------------------------
    # Latest Chronicle
    # ---------------------------------------------------------

    if command == "!cutlass chronicle latest":

        row = await get_latest_chronicle(
            message.guild.id
        )

        await message.reply(
            (
                row[0]
                if row
                else "No chronicle has been written yet."
            )[:1900],
            mention_author=False
        )

        return True

    # ---------------------------------------------------------
    # Generate Chronicle now
    # ---------------------------------------------------------

    if command == "!cutlass chronicle now":

        if not is_admin(message):
            return True

        chronicle, error = await generate_chronicle(
            message.guild
        )

        await message.reply(
            (
                "Chronicle posted to the Captain's Log."
                if chronicle
                else error
            ),
            mention_author=False
        )

        return True

    return False
