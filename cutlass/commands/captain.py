async def handle_captain_command(
    message,
    command,
    *,
    is_creator,
    cached_settings,
):
    """
    Handle Captain identity and state commands.

    Returns True when handled.
    Returns False otherwise.
    """

    if command == "!cutlass creator":

        if is_creator(
            message.author.id
        ):

            await message.reply(
                (
                    "Aye, Shipwright. Ye be the scallywag "
                    "responsible for dragging this old pirate aboard."
                ),
                mention_author=False
            )

        else:

            await message.reply(
                (
                    "Nay. Me creator be somewhere aboard, "
                    "probably adding another container."
                ),
                mention_author=False
            )

        return True


    if command == "!cutlass mood":

        settings = await cached_settings(
            message.guild.id
        )

        await message.reply(
            (
                "Current mood: **"
                + settings["mood"]
                + "**"
            ),
            mention_author=False
        )

        return True


    return False
