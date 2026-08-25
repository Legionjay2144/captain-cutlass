async def handle_parrot_command(
    message,
    content,
    command,
    *,
    is_admin,
    get_parrot,
    format_parrot_status,
    format_parrot_captain_history,
    format_parrot_relationship,
    get_parrot_memories,
    get_parrot_jokes,
    ensure_parrot_relationship,
    get_parrot_relationship,
    analyze_parrot_message,
    add_parrot_memory,
    update_parrot_relationship,
    add_parrot_joke,
    set_parrot_enabled,
    set_parrot_chance,
    set_parrot_mood,
    randomize_parrot_mood,
    PARROT_MOODS,
    increment_parrot_interactions,
    increase_parrot_familiarity
):
    """
    Handle direct Barnacle commands.

    Returns True when a Barnacle command was handled.
    Returns False when the command belongs to another subsystem.
    """


    if command.startswith(
        "!cutlass parrot talk "
    ):

        parrot = await get_parrot(
            message.guild.id
        )

        if not parrot["enabled"]:

            await message.reply(
                "The parrot is currently ashore.",
                mention_author=False
            )

            return True

        user_text = content[
            len("!cutlass parrot talk "):
        ].strip()

        if not user_text:

            await message.reply(
                "Use: `!cutlass parrot talk hello`",
                mention_author=False
            )

            return True

        await ensure_parrot_relationship(
            message.guild.id,
            message.author.id,
            message.author.display_name
        )

        relationship = await get_parrot_relationship(
            message.guild.id,
            message.author.id
        )

        memories = await get_parrot_memories(
            message.guild.id,
            message.author.id,
            6
        )

        jokes = await get_parrot_jokes(
            message.guild.id,
            message.author.id,
            6
        )

        result = await analyze_parrot_message(
            message,
            parrot,
            relationship,
            memories,
            jokes,
            user_text
        )

        if not result:

            await message.reply(
                "*The parrot tilts its head and refuses to cooperate.*",
                mention_author=False
            )

            return True

        reply = str(
            result.get(
                "reply",
                ""
            )
        ).strip()

        memory = str(
            result.get(
                "memory",
                "NONE"
            )
        ).strip()

        opinion = str(
            result.get(
                "opinion",
                "NONE"
            )
        ).strip()

        nickname = str(
            result.get(
                "nickname",
                "NONE"
            )
        ).strip()

        joke = str(
            result.get(
                "joke",
                "NONE"
            )
        ).strip()

        blocked_parrot_memories = (
            "not made any memorable",
            "nothing memorable",
            "no memorable",
            "has not revealed",
            "hasn't revealed"
        )

        if (
            memory.upper()
            not in ("NONE", "KEEP", "")
            and not any(
                phrase in memory.lower()
                for phrase in blocked_parrot_memories
            )
        ):
            await add_parrot_memory(
                message.guild.id,
                message.author.id,
                memory
            )

        if (
            opinion.upper()
            not in ("NONE", "KEEP", "")
            or nickname.upper()
            not in ("NONE", "KEEP", "")
        ):

            await update_parrot_relationship(
                message.guild.id,
                message.author.id,
                message.author.display_name,
                opinion=(
                    opinion
                    if opinion.upper()
                    not in ("NONE", "KEEP", "")
                    else None
                ),
                nickname=(
                    nickname
                    if nickname.upper()
                    not in ("NONE", "KEEP", "")
                    else None
                )
            )

        if joke.upper() not in (
            "NONE",
            "KEEP",
            ""
        ):
            await add_parrot_joke(
                message.guild.id,
                message.author.id,
                joke
            )

        await increment_parrot_interactions(
            message.guild.id
        )

        await increase_parrot_familiarity(
            message.guild.id,
            message.author.id,
            message.author.display_name,
            amount=2
        )

        await message.reply(
            "**"
            + parrot["name"]
            + ":** "
            + reply[:1800],
            mention_author=False
        )

        return True


    if command in (
        "!cutlass parrot history",
        "!cutlass parrot banter"
    ):

        text = await format_parrot_captain_history(
            message.guild.id,
            10
        )

        await message.reply(
            text[:1900],
            mention_author=False
        )

        return True


    if command == "!cutlass parrot relationship":

        text = await format_parrot_relationship(
            message.guild.id,
            message.author.id,
            message.author.display_name
        )

        await message.reply(
            text,
            mention_author=False
        )

        return True


    if command == "!cutlass parrot memories":

        memories = await get_parrot_memories(
            message.guild.id,
            message.author.id,
            10
        )

        parrot = await get_parrot(
            message.guild.id
        )

        if not memories:

            await message.reply(
                "**"
                + parrot["name"]
                + "** doesn't remember anything about ye yet.",
                mention_author=False
            )

            return True

        lines = [
            "**"
            + parrot["name"]
            + "'s Memories of "
            + message.author.display_name
            + "**"
        ]

        for item in memories:
            lines.append(
                "• "
                + item["memory"]
                + " ("
                + str(item["confidence"])
                + ")"
            )

        await message.reply(
            "\n".join(lines)[:1900],
            mention_author=False
        )

        return True


    if command == "!cutlass parrot jokes":

        jokes = await get_parrot_jokes(
            message.guild.id,
            message.author.id,
            10
        )

        parrot = await get_parrot(
            message.guild.id
        )

        if not jokes:

            await message.reply(
                "**"
                + parrot["name"]
                + "** hasn't collected any running jokes about ye yet.",
                mention_author=False
            )

            return True

        lines = [
            "**"
            + parrot["name"]
            + "'s Running Jokes with "
            + message.author.display_name
            + "**"
        ]

        for joke in jokes:
            lines.append(
                "• " + joke
            )

        await message.reply(
            "\n".join(lines)[:1900],
            mention_author=False
        )

        return True


    if command in (
        "!cutlass parrot",
        "!cutlass parrot status"
    ):

        text = await format_parrot_status(
            message.guild.id
        )

        await message.reply(
            text,
            mention_author=False
        )

        return True


    if command in (
        "!cutlass parrot on",
        "!cutlass parrot off"
    ):

        if not is_admin(message):
            await message.reply(
                "Only the Admiralty may send Barnacle ashore or bring him back aboard.",
                mention_author=False
            )
            return True

        enabled = command.endswith(
            " on"
        )

        await set_parrot_enabled(
            message.guild.id,
            enabled
        )

        if enabled:

            await message.reply(
                "The parrot is back aboard. Hide anything shiny.",
                mention_author=False
            )

        else:

            await message.reply(
                "The parrot has been sent ashore for now.",
                mention_author=False
            )

        return True


    if command.startswith(
        "!cutlass parrot chance "
    ):

        if not is_admin(message):
            await message.reply(
                "Only the Admiralty may change how often Barnacle sticks his beak into conversations.",
                mention_author=False
            )
            return True

        raw = content[
            len("!cutlass parrot chance "):
        ].strip()

        try:

            chance = int(raw)

            chance = await set_parrot_chance(
                message.guild.id,
                chance
            )

            await message.reply(
                "Parrot participation chance set to **"
                + str(chance)
                + "%**.",
                mention_author=False
            )

        except ValueError:

            await message.reply(
                "Use a number from **0 to 100**. "
                "Example: `!cutlass parrot chance 5`",
                mention_author=False
            )

        return True


    if command == "!cutlass parrot mood":

        parrot = await get_parrot(
            message.guild.id
        )

        await message.reply(
            "**"
            + parrot["name"]
            + "** is currently **"
            + parrot["mood"]
            + "**.",
            mention_author=False
        )

        return True


    if command.startswith(
        "!cutlass parrot mood "
    ):

        if not is_admin(message):
            await message.reply(
                "Only the Admiralty may meddle with Barnacle's mood.",
                mention_author=False
            )
            return True

        raw_mood = content[
            len("!cutlass parrot mood "):
        ].strip()

        try:

            mood = await set_parrot_mood(
                message.guild.id,
                raw_mood
            )

            parrot = await get_parrot(
                message.guild.id
            )

            await message.reply(
                "**"
                + parrot["name"]
                + "** is now feeling **"
                + mood
                + "**.",
                mention_author=False
            )

        except ValueError:

            await message.reply(
                "Available parrot moods: "
                + ", ".join(PARROT_MOODS),
                mention_author=False
            )

        return True


    if command == "!cutlass parrot randommood":

        if not is_admin(message):
            await message.reply(
                "Only the Admiralty may send Barnacle's mood spinning.",
                mention_author=False
            )
            return True

        mood = await randomize_parrot_mood(
            message.guild.id
        )

        parrot = await get_parrot(
            message.guild.id
        )

        await message.reply(
            "**"
            + parrot["name"]
            + "** is now feeling **"
            + mood
            + "**.",
            mention_author=False
        )

        return True

    return False
