async def handle_lore_command(
    message,
    command,
    *,
    get_captain_lore,
    format_captain_canon,
    get_server_lore,
    random_wisdom,
    get_random_quote,
    handle_quote_save,
    get_journal,
    get_timeline
):
    """
    Handle Captain Cutlass lore, quotes, journal, and history commands.

    Returns True when a lore/history command was handled.
    Returns False when the command belongs to another subsystem.
    """

    # ---------------------------------------------------------
    # Captain lore
    # ---------------------------------------------------------

    if command == "!cutlass lore":

        lore = await get_captain_lore(15)

        text = (
            "Me legendary career has not been documented yet."
        )

        if lore:
            text = (
                "**Tales from me questionable past:**\n"
                + "\n".join(
                    "- " + item["lore"]
                    for item in lore
                )
            )

        await message.reply(
            text,
            mention_author=False
        )

        return True

    # ---------------------------------------------------------
    # Core canon
    # ---------------------------------------------------------

    if command == "!cutlass canon":

        text = await format_captain_canon()

        await message.reply(
            text[:1900],
            mention_author=False
        )

        return True

    # ---------------------------------------------------------
    # Server lore
    # ---------------------------------------------------------

    if command == "!cutlass serverlore":

        lore = await get_server_lore(
            message.guild.id,
            15
        )

        text = (
            "This ship has not accumulated enough "
            "questionable history yet."
        )

        if lore:
            text = (
                "**Ship lore:**\n"
                + "\n".join(
                    "- " + item
                    for item in lore
                )
            )

        await message.reply(
            text,
            mention_author=False
        )

        return True

    # ---------------------------------------------------------
    # Wisdom
    # ---------------------------------------------------------

    if command == "!cutlass wisdom":

        await message.reply(
            random_wisdom(),
            mention_author=False
        )

        return True

    # ---------------------------------------------------------
    # Quotes
    # ---------------------------------------------------------

    if command == "!cutlass quote":

        quote = await get_random_quote(
            message.guild.id
        )

        await message.reply(
            (
                quote
                if quote
                else "Me quote book be suspiciously empty."
            ),
            mention_author=False
        )

        return True

    if command == "!cutlass savequote":

        return await handle_quote_save(
            message
        )

    # ---------------------------------------------------------
    # Captain's journal
    # ---------------------------------------------------------

    if command == "!cutlass journal":

        entries = await get_journal(
            message.guild.id,
            5
        )

        if not entries:

            await message.reply(
                "Me journal pages are blank.",
                mention_author=False
            )

            return True

        text = "**Captain's Journal**"

        for entry, date in entries:

            text += (
                "\n\n**"
                + str(date)
                + "**\n"
                + entry
            )

        await message.reply(
            text,
            mention_author=False
        )

        return True

    # ---------------------------------------------------------
    # Timeline
    # ---------------------------------------------------------

    if command == "!cutlass timeline":

        entries = await get_timeline(
            message.guild.id,
            10
        )

        if not entries:

            await message.reply(
                "The ship's timeline be empty.",
                mention_author=False
            )

            return True

        text = "**Captain's Timeline**"

        for entry, date in entries:

            text += (
                "\n\n**"
                + str(date)
                + "**\n"
                + entry
            )

        await message.reply(
            text,
            mention_author=False
        )

        return True

    return False
