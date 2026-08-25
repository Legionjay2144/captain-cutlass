async def handle_world_command(
    message,
    command,
    *,
    format_world,
    format_world_map,
    format_discoveries,
    get_world_history
):

    if not command.startswith(
        "!cutlass world"
    ):
        return False

    if command == "!cutlass world":

        await message.reply(
            await format_world(
                message.guild.id
            ),
            mention_author=False
        )

        return True

    if command == "!cutlass world map":

        await message.reply(
            await format_world_map(
                message.guild.id
            ),
            mention_author=False
        )

        return True

    if command in (
        "!cutlass world locations",
        "!cutlass world discoveries"
    ):

        await message.reply(
            await format_discoveries(
                message.guild.id
            ),
            mention_author=False
        )

        return True

    if command == "!cutlass world history":

        rows = await get_world_history(
            message.guild.id,
            15
        )

        if not rows:

            await message.reply(
                "The world ledger is still blank.",
                mention_author=False
            )

            return True

        text = (
            "**PIRATE WORLD HISTORY**\n"
            + "\n".join(
                "• " + row["content"]
                for row in rows
            )
        )

        await message.reply(
            text[:1900],
            mention_author=False
        )

        return True

    await message.reply(
        "Unknown world command. "
        "Try `!cutlass world map`.",
        mention_author=False
    )

    return True
