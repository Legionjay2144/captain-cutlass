import asyncio


async def handle_admin_command(
    message,
    command,
    content,
    *,
    is_admin,
    set_guild_setting,
    invalidate_settings_cache,
    get_ai_status=None,
    format_ai_status=None,
):
    """
    Handle Captain Cutlass administrative settings.

    Returns True when handled.
    Returns False otherwise.
    """

    # =====================================================
    # QUIET MODE
    # =====================================================

    if command.startswith(
        "!cutlass quiet "
    ):

        if not is_admin(message):

            await message.reply(
                "Only the Admiralty may silence the captain.",
                mention_author=False
            )

            return True

        value = command.split()[-1]

        if value not in (
            "on",
            "off"
        ):
            return True

        await set_guild_setting(
            message.guild.id,
            "quiet",
            1 if value == "on" else 0
        )

        invalidate_settings_cache(
            message.guild.id
        )

        await message.reply(
            (
                "Captain is now quiet."
                if value == "on"
                else "Captain is back on deck."
            ),
            mention_author=False
        )

        return True


    # =====================================================
    # CAPTAIN MOOD
    # =====================================================

    if command.startswith(
        "!cutlass mood "
    ):

        if not is_admin(message):

            await message.reply(
                "Only the Admiralty may adjust me temperament.",
                mention_author=False
            )

            return True

        parts = content.split(
            " ",
            2
        )

        if len(parts) < 3:
            return True

        mood = parts[2].strip()[:50]

        if not mood:
            return True

        await set_guild_setting(
            message.guild.id,
            "mood",
            mood
        )

        invalidate_settings_cache(
            message.guild.id
        )

        await message.reply(
            (
                "Captain's mood is now **"
                + mood
                + "**."
            ),
            mention_author=False
        )

        return True


    # =====================================================
    # ROLEPLAY EVENT MODE
    # =====================================================

    if command.startswith(
        "!cutlass event "
    ):

        if not is_admin(message):
            return True

        value = command.split()[-1]

        if value not in (
            "on",
            "off"
        ):
            return True

        await set_guild_setting(
            message.guild.id,
            "event_mode",
            1 if value == "on" else 0
        )

        invalidate_settings_cache(
            message.guild.id
        )

        await message.reply(
            (
                "Roleplay event mode activated."
                if value == "on"
                else "Roleplay event mode disabled."
            ),
            mention_author=False
        )

        return True


    # =====================================================
    # AI STATUS
    # =====================================================

    if command in (
        "!cutlass ai",
        "!cutlass ai status",
    ):

        if not is_admin(message):
            await message.reply(
                "Only the Admiralty may inspect AI status.",
                mention_author=False
            )
            return True

        if get_ai_status is None or format_ai_status is None:
            await message.reply(
                "AI status is unavailable right now.",
                mention_author=False
            )
            return True

        status = get_ai_status()
        if asyncio.iscoroutine(status):
            status = await status

        await message.reply(
            format_ai_status(status),
            mention_author=False
        )

        return True


    return False
