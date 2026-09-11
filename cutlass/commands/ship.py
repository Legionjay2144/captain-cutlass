SHIP_HISTORY_LABELS = {
    "battle_boarding": "Boarding",
    "battle_victory": "Naval Victory",
    "boss_victory": "Boss Victory",
    "capture": "Capture",
    "capture_milestone": "Capture Milestone",
    "capture_salvage": "Capture Salvaged",
    "capture_sell": "Capture Sold",
    "crew_work": "Crew Work",
    "monster_victory": "Monster Victory",
    "rename": "Renamed",
    "ship_restored": "Restored",
    "upgrade": "Upgrade",
    "voyage_complete": "Voyage Complete",
}


def _history_label(event_type):
    return SHIP_HISTORY_LABELS.get(
        str(event_type or "event"),
        str(event_type or "event").replace("_", " ").title(),
    )


def _format_history_row(row):
    content = row[0]
    created_at = row[1] if len(row) > 1 else ""
    event_type = row[2] if len(row) > 2 else "event"

    date_text = str(created_at or "")[:10]
    prefix = "**" + _history_label(event_type) + "**"

    if date_text:
        prefix += " · " + date_text

    return "- " + prefix + " — " + str(content)


async def handle_ship_command(
    message,
    content,
    command,
    *,
    is_admin,
    get_ship_settings,
    get_ship,
    set_ship_setting,
    invalidate_settings_cache,
    format_ship_status,
    rename_ship,
    get_history,
    top_contributors,
    donate,
    get_doubloons,
    add_doubloons,
    repair_ship,
    format_upgrades,
    buy_upgrade,
    format_captured_ships,
    resolve_captured_ship,
    format_destinations,
    get_active_voyage,
    start_voyage,
    discord_timestamp,
    post_captains_log
):
    """
    Handle Ship World and voyage commands.

    Returns True when a Ship World command was handled.
    Returns False when the command belongs to another subsystem.
    """

    if not (
        command.startswith("!cutlass ship")
        or command.startswith("!cutlass voyage")
    ):
        return False

    settings = await get_ship_settings(
        message.guild.id
    )

    ship_channel = message.guild.get_channel(
        settings.get("channel_id", 0)
    )

    # ---------------------------------------------------------
    # Ship World configuration
    # ---------------------------------------------------------

    if command.startswith(
        "!cutlass ship channel"
    ):
        if not is_admin(message):
            await message.reply(
                "Only the Admiralty may set the Ship World channel.",
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
                "Use: `!cutlass ship channel #ship-world`",
                mention_author=False
            )
            return True

        await set_ship_setting(
            message.guild.id,
            "channel_id",
            channel.id
        )

        invalidate_settings_cache(
            message.guild.id
        )

        await message.reply(
            "Ship World set to " + channel.mention + ".",
            mention_author=False
        )

        return True

    if command in (
        "!cutlass ship on",
        "!cutlass ship off"
    ):
        if not is_admin(message):
            await message.reply(
                "Only the Admiralty may configure Ship World.",
                mention_author=False
            )
            return True

        enabled = command.endswith(" on")

        if enabled and not settings.get(
            "channel_id"
        ):
            await message.reply(
                "Set the channel first with "
                "`!cutlass ship channel #ship-world`.",
                mention_author=False
            )
            return True

        await set_ship_setting(
            message.guild.id,
            "enabled",
            1 if enabled else 0
        )

        invalidate_settings_cache(
            message.guild.id
        )

        await message.reply(
            "Ship World is now "
            + (
                "enabled."
                if enabled
                else "disabled."
            ),
            mention_author=False
        )

        return True

    if command == "!cutlass ship status":
        state = (
            "Enabled"
            if settings.get("enabled")
            else "Disabled"
        )

        await message.reply(
            "**SHIP WORLD**\n"
            "Status: "
            + state
            + "\nChannel: "
            + (
                ship_channel.mention
                if ship_channel
                else "Not configured"
            ),
            mention_author=False
        )

        return True

    # ---------------------------------------------------------
    # Ship World routing
    # ---------------------------------------------------------

    if not settings.get("enabled"):
        await message.reply(
            "Ship World is disabled on this server.",
            mention_author=False
        )
        return True

    if ship_channel is None:
        await message.reply(
            "The Ship World channel is not configured.",
            mention_author=False
        )
        return True

    if message.channel.id != ship_channel.id:
        await message.reply(
            "All ship business belongs in "
            + ship_channel.mention
            + ".",
            mention_author=False
        )
        return True

    # ---------------------------------------------------------
    # Ship status
    # ---------------------------------------------------------

    if command in (
        "!cutlass ship",
        "!cutlass ship world"
    ):
        await message.reply(
            await format_ship_status(
                message.guild.id
            ),
            mention_author=False
        )
        return True

    # ---------------------------------------------------------
    # Rename ship
    # ---------------------------------------------------------

    if command.startswith(
        "!cutlass ship name "
    ):
        if not is_admin(message):
            await message.reply(
                "Only the Admiralty may rename the ship.",
                mention_author=False
            )
            return True

        try:
            name = await rename_ship(
                message.guild.id,
                content[
                    len("!cutlass ship name "):
                ]
            )
        except ValueError as error:
            await message.reply(
                str(error),
                mention_author=False
            )
            return True

        await message.reply(
            "Strike the old name from the ledger. "
            "She is now **"
            + name
            + "**.",
            mention_author=False
        )

        await post_captains_log(
            message.guild,
            "**SHIP WORLD**\n"
            "The server ship was renamed **"
            + name
            + "**.",
            "ship"
        )

        return True

    # ---------------------------------------------------------
    # Ship history
    # ---------------------------------------------------------

    if command == "!cutlass ship history":
        rows = await get_history(
            message.guild.id,
            12
        )

        if not rows:
            await message.reply(
                "The ship's history is still a blank page.",
                mention_author=False
            )
        else:
            await message.reply(
                (
                    "**SHIP HISTORY**\n"
                    + "\n".join(
                        _format_history_row(row)
                        for row in rows
                    )
                )[:1900],
                mention_author=False
            )

        return True

    # ---------------------------------------------------------
    # Treasury
    # ---------------------------------------------------------

    if command == "!cutlass ship treasury":
        ship_text = await format_ship_status(
            message.guild.id
        )

        contributors = await top_contributors(
            message.guild.id
        )

        treasury_line = next(
            (
                line
                for line in ship_text.splitlines()
                if line.startswith("Treasury:")
            ),
            "Treasury: **0 doubloons**"
        )

        text = (
            "**SHIP TREASURY**\n"
            + treasury_line.replace(
                "Treasury: ",
                ""
            )
        )

        if contributors:
            text += (
                "\n\n**Top Contributors**\n"
                + "\n".join(
                    str(i)
                    + ". "
                    + str(name or "Unknown")
                    + " - "
                    + str(amount)
                    for i, (name, amount)
                    in enumerate(
                        contributors,
                        1
                    )
                )
            )

        await message.reply(
            text,
            mention_author=False
        )

        return True

    if command.startswith(
        "!cutlass ship donate "
    ):
        try:
            amount = int(
                content.split()[-1]
            )
        except ValueError:
            await message.reply(
                "Use: `!cutlass ship donate 100`",
                mention_author=False
            )
            return True

        donation_result = await donate(
            message.guild.id,
            message.author.id,
            message.author.display_name,
            amount,
            get_doubloons,
            add_doubloons
        )

        ok = donation_result[0]
        text = donation_result[1]

        milestones = (
            donation_result[2]
            if (
                ok
                and len(donation_result) > 2
            )
            else []
        )

        pending_reward_total = (
            int(donation_result[3])
            if (
                ok
                and len(donation_result) > 3
            )
            else 0
        )

        if milestones:

            total_reward = sum(
                int(item["reward"])
                for item in milestones
            )

            milestone_lines = [
                (
                    "**"
                    + str(item["milestone"])
                    + " donated** — **+"
                    + str(item["reward"])
                    + " doubloons**"
                )
                for item in milestones
            ]

            text += (
                "\n\n"
                "🏴‍☠️ **CREW CONTRIBUTION REWARD!**\n"
                + "\n".join(
                    milestone_lines
                )
                + "\n**Total reward: +"
                + str(total_reward)
                + " doubloons**"
            )

        if pending_reward_total:

            text += (
                "\n\n"
                "⚠️ **Contribution reward queued:** "
                "**"
                + str(pending_reward_total)
                + " doubloons**. "
                "The reward will be retried automatically "
                "on yer next successful ship donation."
            )

        await message.reply(
            text,
            mention_author=False
        )

        if ok:
            await post_captains_log(
                message.guild,
                "**SHIP TREASURY**\n" + text,
                "ship"
            )

        return True

    # ---------------------------------------------------------
    # Repairs
    # ---------------------------------------------------------

    if command == "!cutlass ship repair":

        ok, text = await repair_ship(
            message.guild.id
        )

        await message.reply(
            text,
            mention_author=False
        )

        if ok:
            await post_captains_log(
                message.guild,
                "**SHIP REPAIRS**\n" + text,
                "ship"
            )

        return True

    # ---------------------------------------------------------
    # Upgrades
    # ---------------------------------------------------------

    if command == "!cutlass ship upgrades":
        await message.reply(
            await format_upgrades(
                message.guild.id
            ),
            mention_author=False
        )

        return True

    if command.startswith(
        "!cutlass ship upgrade "
    ):

        ok, text = await buy_upgrade(
            message.guild.id,
            content[
                len("!cutlass ship upgrade "):
            ]
        )

        await message.reply(
            text,
            mention_author=False
        )

        if ok:
            await post_captains_log(
                message.guild,
                "**SHIP UPGRADE**\n" + text,
                "ship"
            )

        return True

    if command == "!cutlass ship captures":
        await message.reply(
            await format_captured_ships(
                message.guild.id
            ),
            mention_author=False
        )

        return True

    if command == "!cutlass ship capture":
        await message.reply(
            "Use `!cutlass ship captures` to view the prize ledger, "
            "`!cutlass ship capture sell <id>` to sell a captured vessel, "
            "or `!cutlass ship capture salvage <id>` to strip it for parts.",
            mention_author=False
        )

        return True

    if command.startswith(
        "!cutlass ship capture "
    ):
        parts = content.split()

        if len(parts) < 5:
            await message.reply(
                "Use: `!cutlass ship capture sell <id>` or `!cutlass ship capture salvage <id>`",
                mention_author=False
            )
            return True

        action = parts[3].lower().strip()

        try:
            capture_id = int(parts[4])
        except ValueError:
            await message.reply(
                "Use a numeric capture id from `!cutlass ship captures`.",
                mention_author=False
            )
            return True

        ok, text = await resolve_captured_ship(
            message.guild.id,
            capture_id,
            action
        )

        await message.reply(
            text,
            mention_author=False
        )

        if ok:
            await post_captains_log(
                message.guild,
                "**CAPTURED SHIP**\n" + text,
                "ship"
            )

        return True

    # ---------------------------------------------------------
    # Voyages
    # ---------------------------------------------------------

    if command in (
        "!cutlass voyage",
        "!cutlass voyage destinations"
    ):
        await message.reply(
            await format_destinations(
                message.guild.id
            ),
            mention_author=False
        )

        return True

    if command == "!cutlass voyage status":
        voyage = await get_active_voyage(
            message.guild.id
        )

        if not voyage:
            await message.reply(
                "The ship is currently anchored. "
                "No voyage is active.",
                mention_author=False
            )
        else:
            await message.reply(
                "**CURRENT VOYAGE**\n"
                "Destination: **"
                + voyage["destination"]
                + "**\nRisk: **"
                + voyage["risk"]
                + "**\nExpected completion: **"
                + discord_timestamp(
                    voyage["completes_at"]
                )
                + "**",
                mention_author=False
            )

        return True

    if command.startswith(
        "!cutlass voyage start "
    ):
        ship = await get_ship(
            message.guild.id
        )

        if int(ship["hull"]) <= 0:
            await message.reply(
                "**THE SHIP IS DISABLED**\n"
                "Repair the hull before ordering another voyage.",
                mention_author=False
            )
            return True


        try:
            destination = int(
                content.split()[-1]
            )
        except ValueError:
            await message.reply(
                "Use: `!cutlass voyage start 1`",
                mention_author=False
            )
            return True

        ok, result = await start_voyage(
            message.guild.id,
            destination
        )

        if not ok:
            await message.reply(
                result,
                mention_author=False
            )
            return True

        text = (
            "**VOYAGE BEGUN**\n"
            "Destination: **"
            + result["name"]
            + "**\nRisk: **"
            + result["risk"]
            + "**\nSupplies used: **"
            + str(result["supplies"])
            + "**\nExpected completion: **"
            + discord_timestamp(
                result["completes_at"]
            )
            + "**"
        )

        await message.reply(
            text,
            mention_author=False
        )

        await post_captains_log(
            message.guild,
            text,
            "voyage"
        )

        return True

    await message.reply(
        "Unknown Ship World command. "
        "Use `!cutlass help`.",
        mention_author=False
    )

    return True
