import asyncio


async def handle_crew_command(
    message,
    content,
    command,
    *,
    get_member_meta,
    get_relationship,
    get_user_memories_context,
    get_running_jokes,
    get_relationship_events,
    get_doubloons,
    get_achievements,
    format_birthday,
    parse_birthday,
    set_birthday,
    clear_birthday,
    get_birthdays,
    get_user_memories,
    get_stats,
    get_top_crew,
    get_doubloon_leaderboard,
    delete_user_memories
):
    """
    Handle Captain Cutlass crew/profile commands.

    Returns True when a crew command was handled.
    Returns False when the command belongs to another subsystem.
    """

    # =========================================================
    # PROFILE
    # =========================================================

    if command == "!cutlass profile":

        (
            meta,
            relationship,
            memories,
            jokes,
            events,
            balance,
            achievements
        ) = await asyncio.gather(
            get_member_meta(
                message.guild.id,
                message.author.id
            ),
            get_relationship(
                message.guild.id,
                message.author.id
            ),
            get_user_memories_context(
                message.guild.id,
                message.author.id,
                5,
                1
            ),
            get_running_jokes(
                message.guild.id,
                message.author.id,
                3
            ),
            get_relationship_events(
                message.guild.id,
                message.author.id,
                3
            ),
            get_doubloons(
                message.guild.id,
                message.author.id
            ),
            get_achievements(
                message.guild.id,
                message.author.id,
                5
            )
        )

        lines = [
            "**CREW PROFILE - "
            + message.author.display_name
            + "**"
        ]

        if relationship:
            lines += [
                "Relationship: **"
                + relationship["relationship_type"]
                + "**",
                "Familiarity: **"
                + str(relationship["familiarity"])
                + "/100**"
            ]

            if relationship.get("nickname"):
                lines.append(
                    "Captain's nickname: **"
                    + relationship["nickname"]
                    + "**"
                )

            if relationship.get("opinion"):
                lines.append(
                    "Captain's opinion: "
                    + relationship["opinion"][:250]
                )

        lines.append(
            "Doubloons: **"
            + str(balance)
            + "**"
        )

        if (
            meta
            and meta.get("birthday_month")
            and meta.get("birthday_day")
        ):
            lines.append(
                "Birthday: **"
                + format_birthday(
                    meta["birthday_month"],
                    meta["birthday_day"]
                )
                + "**"
            )

        if meta:
            lines.append(
                "Messages seen: **"
                + str(meta.get("message_count", 0))
                + "**"
            )

        if achievements:
            lines.append(
                "Achievements: "
                + ", ".join(
                    a[0]
                    for a in achievements
                )
            )

        if memories:
            lines.append(
                "Memories: "
                + str(len(memories))
                + " loaded"
            )

        if jokes:
            lines.append(
                "Running jokes: "
                + str(len(jokes))
            )

        if events:
            lines.append(
                "Recent shared events: "
                + str(len(events))
            )

        await message.reply(
            "\n".join(lines)[:1900],
            mention_author=False
        )

        return True

    # =========================================================
    # BIRTHDAYS
    # =========================================================

    if command == "!cutlass birthday":

        meta = await get_member_meta(
            message.guild.id,
            message.author.id
        )

        if (
            meta
            and meta.get("birthday_month")
            and meta.get("birthday_day")
        ):
            text = (
                "I have yer birthday marked as **"
                + format_birthday(
                    meta["birthday_month"],
                    meta["birthday_day"]
                )
                + "**."
            )
        else:
            text = (
                "I don't have yer birthday yet. "
                "Use `!cutlass birthday set August 23`."
            )

        await message.reply(
            text,
            mention_author=False
        )

        return True

    if command.startswith(
        "!cutlass birthday set "
    ):

        raw = content[
            len("!cutlass birthday set "):
        ].strip()

        try:
            month, day = parse_birthday(raw)

        except ValueError as error:
            await message.reply(
                str(error),
                mention_author=False
            )
            return True

        await set_birthday(
            message.guild.id,
            message.author.id,
            message.author.display_name,
            month,
            day
        )

        await message.reply(
            (
                "Aye! Birthday marked as **"
                + format_birthday(month, day)
                + "**. No year needed aboard this ship."
            ),
            mention_author=False
        )

        return True

    if command == "!cutlass birthday clear":

        await clear_birthday(
            message.guild.id,
            message.author.id
        )

        await message.reply(
            "Birthday cleared from me ledger.",
            mention_author=False
        )

        return True

    if command == "!cutlass birthdays":

        rows = await get_birthdays(
            message.guild.id
        )

        if not rows:
            await message.reply(
                "No birthdays be written in the crew ledger yet.",
                mention_author=False
            )
            return True

        lines = [
            "**CREW BIRTHDAYS**"
        ]

        for (
            user_id,
            username,
            month,
            day
        ) in rows[:30]:

            lines.append(
                "- "
                + str(username or user_id)
                + " - "
                + format_birthday(
                    month,
                    day
                )
            )

        await message.reply(
            "\n".join(lines)[:1900],
            mention_author=False
        )

        return True

    # =========================================================
    # MEMORY
    # =========================================================

    if command == "!cutlass memory":

        memories = await get_user_memories(
            message.guild.id,
            message.author.id,
            20
        )

        text = (
            "Me memory chest be empty for ye so far."
        )

        if memories:
            text = (
                "**Memory chest:**\n"
                + "\n".join(
                    "- " + memory
                    for memory in memories
                )
            )

        await message.reply(
            text,
            mention_author=False
        )

        return True

    # =========================================================
    # RELATIONSHIP
    # =========================================================

    if command == "!cutlass relationship":

        (
            relationship,
            jokes,
            events
        ) = await asyncio.gather(
            get_relationship(
                message.guild.id,
                message.author.id
            ),
            get_running_jokes(
                message.guild.id,
                message.author.id,
                5
            ),
            get_relationship_events(
                message.guild.id,
                message.author.id,
                5
            )
        )

        if not relationship:

            await message.reply(
                "We have not sailed enough seas yet.",
                mention_author=False
            )

            return True

        text = (
            "**Relationship:** "
            + relationship[
                "relationship_type"
            ]
            + "\n**Familiarity:** "
            + str(
                relationship[
                    "familiarity"
                ]
            )
            + "/100"
        )

        if relationship["nickname"]:
            text += (
                "\n**Nickname:** "
                + relationship["nickname"]
            )

        if relationship["opinion"]:
            text += (
                "\n**Opinion:** "
                + relationship["opinion"]
            )

        if jokes:

            text += (
                "\n\n**Running jokes:**"
            )

            for joke in jokes:
                text += (
                    "\n- "
                    + joke
                )

        if events:

            text += (
                "\n\n**Shared events:**"
            )

            for event in events:
                text += (
                    "\n- "
                    + event["event"]
                )

        await message.reply(
            text,
            mention_author=False
        )

        return True

    # =========================================================
    # STATS
    # =========================================================

    if command == "!cutlass stats":

        stats = await get_stats(
            message.guild.id
        )

        text = (
            "**Captain Cutlass Stats**\n"
            "Crew profiles: "
            + str(stats["members"])
            + "\nMemories: "
            + str(stats["memories"])
            + "\nRunning jokes: "
            + str(stats["jokes"])
            + "\nShared events: "
            + str(stats["events"])
            + "\nCaptain lore: "
            + str(stats["captain_lore"])
            + "\nServer lore: "
            + str(stats["server_lore"])
            + "\nSaved quotes: "
            + str(stats["quotes"])
            + "\nAchievements: "
            + str(stats["achievements"])
            + "\nTimeline entries: "
            + str(stats["timeline"])
            + "\nTotal doubloons: "
            + str(stats["doubloons"])
        )

        await message.reply(
            text,
            mention_author=False
        )

        return True

    # =========================================================
    # CREW RANKINGS
    # =========================================================

    if command == "!cutlass crew":

        crew = await get_top_crew(
            message.guild.id,
            10
        )

        if not crew:

            await message.reply(
                "No crew rankings yet.",
                mention_author=False
            )

            return True

        lines = []

        for number, row in enumerate(
            crew,
            start=1
        ):

            display = (
                row[1]
                if row[1]
                else row[0]
            )

            lines.append(
                (
                    str(number)
                    + ". "
                    + str(display)
                    + " - "
                    + str(row[2])
                    + " ("
                    + str(row[3])
                    + "/100)"
                )
            )

        await message.reply(
            (
                "**Captain's Top Crewmates**\n"
                + "\n".join(lines)
            ),
            mention_author=False
        )

        return True

    # =========================================================
    # DOUBLOONS
    # =========================================================

    if command == "!cutlass balance":

        balance = await get_doubloons(
            message.guild.id,
            message.author.id
        )

        await message.reply(
            (
                "Ye currently have **"
                + str(balance)
                + " doubloons**."
            ),
            mention_author=False
        )

        return True

    if command == "!cutlass leaderboard":

        crew = await get_doubloon_leaderboard(
            message.guild.id,
            10
        )

        if not crew:

            await message.reply(
                "The treasury ledger be empty.",
                mention_author=False
            )

            return True

        lines = []

        for number, row in enumerate(
            crew,
            start=1
        ):

            username = (
                row[0]
                or "Unknown Crewmate"
            )

            display = (
                row[1]
                if row[1]
                else username
            )

            lines.append(
                (
                    str(number)
                    + ". "
                    + str(display)
                    + " - "
                    + str(row[2])
                    + " doubloons"
                )
            )

        await message.reply(
            (
                "**Doubloon Leaderboard**\n"
                + "\n".join(lines)
            ),
            mention_author=False
        )

        return True

    # =========================================================
    # ACHIEVEMENTS
    # =========================================================

    if command == "!cutlass achievements":

        achievements = await get_achievements(
            message.guild.id,
            message.author.id
        )

        if not achievements:

            await message.reply(
                "Ye have not earned any achievements yet.",
                mention_author=False
            )

            return True

        text = (
            "**Yer achievements:**"
        )

        for (
            achievement,
            description
        ) in achievements:

            text += (
                "\n- **"
                + achievement
                + "**"
            )

            if description:
                text += (
                    " - "
                    + description
                )

        await message.reply(
            text,
            mention_author=False
        )

        return True

    # =========================================================
    # PRIVACY / MEMORY RESET
    # =========================================================

    if command == "!cutlass forgetme":

        await delete_user_memories(
            message.guild.id,
            message.author.id
        )

        await message.reply(
            "Yer personal memory chest has been tossed overboard.",
            mention_author=False
        )

        return True

    return False
