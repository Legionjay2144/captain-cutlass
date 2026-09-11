WORLD_HISTORY_LABELS = {
    "discovery": "Discovery",
    "event": "World Event",
    "finding": "Finding",
    "island_boss": "Island Boss",
    "island_lore": "Island Lore",
    "island_supplies": "Island Supplies",
    "island_treasure": "Island Treasure",
    "world": "World",
}


def _world_history_label(event_type):
    return WORLD_HISTORY_LABELS.get(
        str(event_type or "world"),
        str(event_type or "world").replace("_", " ").title(),
    )


def _format_world_history_row(row):
    event_type = row["event_type"]
    content = row["content"]
    created_at = row["created_at"]
    date_text = str(created_at or "")[:10]

    prefix = "**" + _world_history_label(event_type) + "**"

    if date_text:
        prefix += " · " + date_text

    return "• " + prefix + " — " + str(content)


async def handle_world_command(
    message,
    command,
    *,
    format_world,
    format_world_map,
    format_discoveries,
    format_world_findings,
    format_world_events,
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

    if command == "!cutlass world events":

        await message.reply(
            await format_world_events(
                message.guild.id
            ),
            mention_author=False
        )

        return True

    if command == "!cutlass world findings":

        await message.reply(
            await format_world_findings(
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
                _format_world_history_row(row)
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
