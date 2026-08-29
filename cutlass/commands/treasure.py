async def handle_treasure_command(
    message,
    command,
    content,
    *,
    is_admin,
    start_treasure_hunt,
    get_treasure_hunt,
):

    # =====================================================
    # TREASURE CLUE
    # =====================================================

    if command == "!cutlass treasure clue":

        hunt = await get_treasure_hunt(
            message.guild.id
        )

        if (
            not hunt
            or not hunt["active"]
        ):

            await message.reply(
                "There be no active treasure hunt.",
                mention_author=False
            )

            return True

        await message.reply(
            (
                "Treasure clue: "
                + hunt["clue"]
            ),
            mention_author=False
        )

        return True


    # =====================================================
    # START TREASURE HUNT
    # =====================================================

    if command.startswith(
        "!cutlass treasure start "
    ):

        if not is_admin(message):
            return True

        payload = content[
            len("!cutlass treasure start "):
        ]

        if "|" not in payload:

            await message.reply(
                (
                    "Use: `!cutlass treasure start "
                    "ANSWER | CLUE`"
                ),
                mention_author=False
            )

            return True

        answer, clue = payload.split(
            "|",
            1
        )

        answer = answer.strip()
        clue = clue.strip()

        if not answer or not clue:

            await message.reply(
                (
                    "Use: `!cutlass treasure start "
                    "ANSWER | CLUE`"
                ),
                mention_author=False
            )

            return True

        await start_treasure_hunt(
            message.guild.id,
            answer,
            clue
        )

        await message.reply(
            (
                "A new treasure hunt has begun. "
                "May the cleverest scallywag find it."
            ),
            mention_author=False
        )

        return True

    return False


async def check_treasure_answer(
    message,
    *,
    get_treasure_hunt,
    finish_treasure_hunt,
    add_doubloons,
    award_achievement,
    add_relationship_event,
    add_timeline_entry,
    post_captains_log,
):

    hunt = await get_treasure_hunt(
        message.guild.id
    )

    if (
        not hunt
        or not hunt["active"]
    ):
        return False

    if (
        message.content
        .lower()
        .strip()
        != hunt["answer"]
    ):
        return False

    claimed = await finish_treasure_hunt(
        message.guild.id,
        message.author.id,
        message.author.display_name
    )

    if not claimed:
        await message.reply(
            (
                "Too late, matey — another crewmate "
                "claimed that treasure first."
            ),
            mention_author=False
        )
        return True

    await add_doubloons(
        message.guild.id,
        message.author.id,
        100
    )

    await award_achievement(
        message.guild.id,
        message.author.id,
        "Treasure Hunter",
        "Won a Captain Cutlass treasure hunt."
    )

    await add_relationship_event(
        message.guild.id,
        message.author.id,
        "Won one of Captain Cutlass's treasure hunts.",
        importance=8
    )

    await add_timeline_entry(
        message.guild.id,
        (
            message.author.display_name
            + " won one of Captain Cutlass's treasure hunts."
        ),
        importance=8
    )

    await message.reply(
        (
            "Treasure found! "
            + message.author.display_name
            + " has claimed the booty and earned "
            "100 doubloons!"
        ),
        mention_author=False
    )

    await post_captains_log(
        message.guild,
        (
            "**TREASURE HUNT**\n"
            + message.author.mention
            + " found the treasure, earned "
            "**100 doubloons**, and claimed the "
            "**Treasure Hunter** achievement."
        ),
        "treasure"
    )

    return True
