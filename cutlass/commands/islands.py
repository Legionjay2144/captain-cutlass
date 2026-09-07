import random
from datetime import datetime, timezone

from cutlass.world.locks import get_guild_lock


async def handle_island_command(
    message,
    command,
    *,
    cached_settings,
    get_ship,
    get_ship_operational_status,
    get_active_battle,
    get_active_monster,
    format_island,
    choose_island_activity,
    resolve_island_key,
    add_ship_treasury,
    add_ship_supplies,
    add_ship_history,
    start_monster_encounter,
    start_boss,
    get_active_boss,
    get_island_activity_state,
    record_island_visit,
    get_completed_island_activities,
    complete_island_activity,
    valid_boss_keys,
    valid_monster_keys,
    add_world_history,
    post_captains_log
):

    if not command.startswith("!cutlass island"):
        return False

    settings = await cached_settings(
        message.guild.id
    )

    if not settings.get("enabled"):
        await message.reply(
            "Ship World is disabled on this server.",
            mention_author=False
        )
        return True

    ship_channel = message.guild.get_channel(
        settings.get("channel_id", 0)
    )

    if (
        ship_channel
        and message.channel.id != ship_channel.id
    ):
        await message.reply(
            "Island business belongs in "
            + ship_channel.mention
            + ".",
            mention_author=False
        )
        return True

    ship = await get_ship(
        message.guild.id
    )

    operational = await get_ship_operational_status(
        message.guild.id,
        ship=ship
    )

    if not operational["operational"]:
        await message.reply(
            "**SHIP DISABLED / RECOVERING**\n"
            "The crew cannot venture ashore until the ship reaches **"
            + str(operational["threshold"])
            + "/"
            + str(operational["max_hull"])
            + " hull**.\n"
            "Current hull: **"
            + str(operational["hull"])
            + "/"
            + str(operational["max_hull"])
            + "**.\n"
            "Needed: **+"
            + str(operational["needed"])
            + " hull**.",
            mention_author=False
        )
        return True

    if await get_active_battle(
        message.guild.id
    ):
        await message.reply(
            "Finish the current naval battle before heading ashore.",
            mention_author=False
        )
        return True

    if await get_active_monster(
        message.guild.id
    ):
        await message.reply(
            "There's still a sea monster threatening the ship.",
            mention_author=False
        )
        return True

    location = ship["location"]

    if command == "!cutlass island":

        text = format_island(
            location
        )

        if text is None:
            await message.reply(
                "The ship is not currently anchored at an explorable island.",
                mention_author=False
            )
            return True

        await message.reply(
            text,
            mention_author=False
        )
        return True

    if command == "!cutlass island explore":

        async with get_guild_lock(message.guild.id):

            if await get_active_battle(
                message.guild.id
            ):
                await message.reply(
                    "Another crew action already has the ship engaged "
                    "in a naval battle. Finish it before exploring.",
                    mention_author=False
                )
                return True

            if await get_active_monster(
                message.guild.id
            ):
                await message.reply(
                    "Another crew action already has the ship engaged "
                    "with a sea monster. Finish it before exploring.",
                    mention_author=False
                )
                return True

            if await get_active_boss(
                message.guild.id
            ):
                await message.reply(
                    "Another crew action already has the ship engaged "
                    "with a boss. Finish it before exploring.",
                    mention_author=False
                )
                return True


            # -------------------------------------------------
            # Physical island exploration cooldown
            # -------------------------------------------------

            location_key = resolve_island_key(
                location
            )

            state = await get_island_activity_state(
                message.guild.id,
                location_key
            )

            last_explored = state.get(
                "last_explored_at"
            )

            if last_explored:

                try:
                    last_time = datetime.fromisoformat(
                        str(last_explored)
                    )

                    if last_time.tzinfo is None:
                        last_time = last_time.replace(
                            tzinfo=timezone.utc
                        )

                    now = datetime.now(
                        timezone.utc
                    )

                    elapsed = (
                        now - last_time
                    ).total_seconds()

                    cooldown = 30 * 60

                    if elapsed < cooldown:

                        remaining = int(
                            cooldown - elapsed
                        )

                        minutes = max(
                            1,
                            (remaining + 59) // 60
                        )

                        await message.reply(
                            "**ISLAND EXPLORATION COOLDOWN**\n"
                            "The crew has already searched this island recently.\n"
                            "Try again in about **"
                            + str(minutes)
                            + " minute"
                            + (
                                ""
                                if minutes == 1
                                else "s"
                            )
                            + "**.",
                            mention_author=False
                        )

                        return True

                except (TypeError, ValueError):
                    pass

            visit_claim = await record_island_visit(
                message.guild.id,
                location_key,
                cooldown_seconds=30 * 60
            )

            if not visit_claim["claimed"]:
                remaining = max(
                    1,
                    int(
                        visit_claim[
                            "remaining_seconds"
                        ]
                    )
                )

                minutes = max(
                    1,
                    (remaining + 59) // 60
                )

                await message.reply(
                    "**ISLAND EXPLORATION COOLDOWN**\n"
                    "Another crew expedition has already "
                    "searched this island.\n"
                    "Try again in about **"
                    + str(minutes)
                    + " minute"
                    + (
                        ""
                        if minutes == 1
                        else "s"
                    )
                    + "**.",
                    mention_author=False
                )

                return True

            visit_number = int(
                visit_claim["visits"]
            )

            completed_rows = (
                await get_completed_island_activities(
                    message.guild.id,
                    location_key
                )
            )

            completed_keys = {
                row["activity_key"]
                for row in completed_rows
            }

            activity = choose_island_activity(
                location,
                completed_keys=completed_keys,
                valid_boss_keys=valid_boss_keys,
                valid_monster_keys=valid_monster_keys
            )

            if activity is None:
                await message.reply(
                    "There is nothing here to explore.",
                    mention_author=False
                )
                return True

            text = (
                "**"
                + activity["title"].upper()
                + "**\n"
                + activity["description"]
            )

            kind = activity["type"]

            # -------------------------------------------------
            # Revisit progression
            # -------------------------------------------------

            if visit_number == 1:
                text += (
                    "\n\n**First Expedition**\n"
                    "The crew begins properly charting this island."
                )

            elif visit_number >= 5:
                text += (
                    "\n\n**Seasoned Explorers**\n"
                    "This is expedition **#"
                    + str(visit_number)
                    + "** to "
                    + location
                    + ". The crew knows these shores well."
                )

            else:
                text += (
                    "\n\nIsland expedition **#"
                    + str(visit_number)
                    + "**."
                )

            rare_revisit = (
                visit_number >= 3
                and random.randint(1, 100) <= 15
            )

            if kind == "treasure":

                reward = random.randint(
                    activity["reward_min"],
                    activity["reward_max"]
                )

                if rare_revisit:
                    bonus = max(
                        10,
                        int(round(reward * 0.20))
                    )

                    reward += bonus

                    text += (
                        "\n\n**FAMILIAR GROUND BONUS**\n"
                        "The crew remembers an overlooked hiding place. "
                        "Treasure value **+"
                        + str(bonus)
                        + " doubloons**."
                    )

                ship_after = await add_ship_treasury(
                    message.guild.id,
                    reward
                )

                text += (
                    "\n\nTreasure recovered: **"
                    + str(reward)
                    + " doubloons**\n"
                    "Treasury: **"
                    + str(ship_after["treasury"])
                    + "**"
                )

                await add_ship_history(
                    message.guild.id,
                    (
                        "Island exploration at "
                        + location
                        + " recovered "
                        + str(reward)
                        + " doubloons."
                    ),
                    "island_treasure"
                )

            elif kind == "supplies":

                amount = random.randint(
                    activity["amount_min"],
                    activity["amount_max"]
                )

                if rare_revisit:
                    bonus = max(
                        3,
                        int(round(amount * 0.20))
                    )

                    amount += bonus

                    text += (
                        "\n\n**FAMILIAR GROUND BONUS**\n"
                        "The crew remembers where useful provisions "
                        "were overlooked. Supplies found **+"
                        + str(bonus)
                        + "**."
                    )

                before = int(
                    ship["supplies"]
                )

                ship_after = await add_ship_supplies(
                    message.guild.id,
                    amount
                )

                gained = max(
                    0,
                    int(ship_after["supplies"])
                    - before
                )

                text += (
                    "\n\nSupplies recovered: **+"
                    + str(gained)
                    + "**\n"
                    "Current supplies: **"
                    + str(ship_after["supplies"])
                    + "**"
                )

                await add_ship_history(
                    message.guild.id,
                    (
                        "Island exploration at "
                        + location
                        + " recovered "
                        + str(gained)
                        + " supplies."
                    ),
                    "island_supplies"
                )

            elif kind == "monster":

                ship = await get_ship(
                    message.guild.id
                )

                created, monster = await start_monster_encounter(
                    message.guild.id,
                    activity["monster"],
                    ship=ship
                )

                if created:
                    text += (
                        "\n\n**SEA MONSTER ENCOUNTER**\n"
                        + monster["name"]
                        + " appears!\n"
                        "HP: **"
                        + str(monster["hp"])
                        + "**\n"
                        "Use `!cutlass monster`."
                    )

            elif kind == "boss":

                if await get_active_boss(
                    message.guild.id
                ):
                    text += (
                        "\n\nA boss encounter is already active."
                    )

                else:
                    ship = await get_ship(
                        message.guild.id
                    )

                    created, boss = await start_boss(
                        message.guild.id,
                        activity["boss"],
                        ship=ship
                    )

                    if created:
                        text += (
                            "\n\n**BOSS ENCOUNTER**\n"
                            + boss["name"]
                            + " emerges!\n"
                            "Danger: **"
                            + boss["danger"]
                            + "**\n"
                            "HP: **"
                            + str(boss["hp"])
                            + "**\n"
                            "Use `!cutlass boss`."
                        )

                        completion_won, _ = (
                            await complete_island_activity(
                                message.guild.id,
                                location_key,
                                activity["activity_key"],
                                activity["type"],
                                activity["title"],
                                message.author.id,
                                message.author.display_name
                            )
                        )

                        if completion_won:
                            boss_history = (
                                message.author.display_name
                                + " discovered "
                                + boss["name"]
                                + " at "
                                + location
                                + "."
                            )

                            await add_ship_history(
                                message.guild.id,
                                (
                                    "The crew discovered "
                                    + boss["name"]
                                    + " at "
                                    + location
                                    + "."
                                ),
                                "boss_discovery"
                            )

                            await add_world_history(
                                message.guild.id,
                                boss_history,
                                "boss_discovery",
                                8
                            )

                            await post_captains_log(
                                message.guild,
                                (
                                    "**MAJOR ISLAND DISCOVERY**\n"
                                    + message.author.display_name
                                    + " discovered **"
                                    + boss["name"]
                                    + "** at **"
                                    + location
                                    + "**."
                                ),
                                "world"
                            )

                            text += (
                                "\n\n**ISLAND DISCOVERY COMPLETE**\n"
                                "This boss discovery is now recorded "
                                "for the crew."
                            )

            elif kind == "lore":

                completion_won, _ = (
                    await complete_island_activity(
                        message.guild.id,
                        location_key,
                        activity["activity_key"],
                        activity["type"],
                        activity["title"],
                        message.author.id,
                        message.author.display_name
                    )
                )

                if completion_won:

                    if rare_revisit:
                        text += (
                            "\n\n**HIDDEN DETAIL UNCOVERED**\n"
                            "Familiarity with the island reveals something "
                            "the crew missed on earlier expeditions."
                        )

                    lore_history = (
                        message.author.display_name
                        + " uncovered "
                        + activity["title"]
                        + " while exploring "
                        + location
                        + "."
                    )

                    await add_ship_history(
                        message.guild.id,
                        (
                            activity["title"]
                            + ": "
                            + activity["description"]
                        ),
                        "island_lore"
                    )

                    await add_world_history(
                        message.guild.id,
                        lore_history,
                        "island_lore",
                        6
                    )

                    text += (
                        "\n\n**ISLAND DISCOVERY COMPLETE**\n"
                        "The discovery has been added to "
                        "the ship's and world's history."
                    )

                else:
                    text += (
                        "\n\nThis discovery was already "
                        "recorded for the crew."
                    )

            await message.reply(
                text[:1900],
                mention_author=False
            )

            return True

    await message.reply(
        "Unknown island command. "
        "Use `!cutlass island` or `!cutlass island explore`.",
        mention_author=False
    )

    return True
