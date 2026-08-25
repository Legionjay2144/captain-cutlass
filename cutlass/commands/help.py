import discord


async def handle_help_command(
    message,
    command,
    *,
    get_parrot,
    get_ship
):
    """
    Handle Captain Cutlass help commands.

    Returns True when a help command was handled.
    Returns False when the command belongs to another subsystem.
    """

    if command in (
        "!cutlass help",
        "!cutlass commands"
    ):
        parrot = await get_parrot(message.guild.id)
        ship = await get_ship(message.guild.id)

        embed = discord.Embed(
            title="🏴‍☠️ Captain Cutlass Help",
            description=(
                "Welcome aboard. Choose a category below to see the commands ye need.\n\n"
                "**Crew & Profiles** — `!cutlass help crew`\n"
                "**Fun, Lore & History** — `!cutlass help fun`\n"
                f"**{parrot['name']}** — `!cutlass help parrot`\n"
                f"**{ship['name']}** — `!cutlass help ship`\n"
                "**Pirate World & Combat** — `!cutlass help world`\n"
                "**Admiralty Controls** — `!cutlass help admin`\n\n"
                "Use `!cutlass help all` for the full command list."
            ),
            color=0x3498DB
        )

        embed.set_footer(
            text="Captain Cutlass • Help Menu"
        )

        await message.reply(
            embed=embed,
            mention_author=False
        )

        return True

    if command == "!cutlass help crew":
        embed = discord.Embed(
            title="👤 Crew & Profile Commands",
            color=0x3498DB
        )

        embed.description = (
            "`!cutlass profile` — View your crew profile\n"
            "`!cutlass memory` — View Captain's memories of you\n"
            "`!cutlass relationship` — View your relationship with Captain\n"
            "`!cutlass creator` — Creator recognition\n"
            "`!cutlass balance` — View your Doubloons\n"
            "`!cutlass achievements` — View achievements\n"
            "`!cutlass leaderboard` — Doubloon leaderboard\n"
            "`!cutlass crew` — Top crewmates\n"
            "`!cutlass stats` — Your statistics\n"
            "`!cutlass birthday` — View your birthday\n"
            "`!cutlass birthday set <month> <day>` — Set birthday\n"
            "`!cutlass birthday clear` — Remove birthday\n"
            "`!cutlass birthdays` — View crew birthdays\n"
            "`!cutlass forgetme` — Forget stored member memories"
        )

        await message.reply(
            embed=embed,
            mention_author=False
        )

        return True

    if command == "!cutlass help fun":
        embed = discord.Embed(
            title="🎭 Fun, Lore & History",
            color=0x3498DB
        )

        embed.description = (
            "`!cutlass lore` — Captain lore\n"
            "`!cutlass canon` — Captain Core Canon\n"
            "`!cutlass serverlore` — Server lore\n"
            "`!cutlass quote` — Random Captain quote\n"
            "`!cutlass savequote` — Save a replied quote\n"
            "`!cutlass wisdom` — Pirate wisdom\n"
            "`!cutlass journal` — Captain's Journal\n"
            "`!cutlass timeline` — Ship timeline\n"
            "`!cutlass story` — Pirate story mode\n"
            "`!cutlass punbattle` — Pun battle\n"
            "`!cutlass treasure clue` — Current treasure clue\n"
            "`!cutlass chronicle latest` — Latest weekly chronicle\n"
            "`!cutlass mood` — Current Captain mood"
        )

        await message.reply(
            embed=embed,
            mention_author=False
        )

        return True

    if command == "!cutlass help parrot":
        parrot = await get_parrot(
            message.guild.id
        )

        embed = discord.Embed(
            title="🦜 " + parrot["name"] + " Commands",
            description=(
                "Current mood: **"
                + parrot["mood"]
                + "**\n"
                "Participation chance: **"
                + str(parrot["participation_chance"])
                + "%**"
            ),
            color=0x3498DB
        )

        embed.add_field(
            name="Crew Commands",
            value=(
                "`!cutlass parrot` — Status\n"
                "`!cutlass parrot talk <message>` — Talk directly\n"
                "`!cutlass parrot relationship` — Your relationship\n"
                "`!cutlass parrot memories` — Memories of you\n"
                "`!cutlass parrot jokes` — Running jokes\n"
                "`!cutlass parrot history` — Captain/parrot history\n"
                "`!cutlass parrot mood` — Current mood"
            ),
            inline=False
        )

        embed.add_field(
            name="Admiralty",
            value=(
                "`!cutlass parrot mood <mood>`\n"
                "`!cutlass parrot randommood`\n"
                "`!cutlass parrot chance <percent>`\n"
                "`!cutlass parrot on/off`"
            ),
            inline=False
        )

        await message.reply(
            embed=embed,
            mention_author=False
        )

        return True

    if command == "!cutlass help ship":
        ship = await get_ship(
            message.guild.id
        )

        embed = discord.Embed(
            title="🚢 " + ship["name"] + " — Ship World",
            description=(
                "Level **"
                + str(ship["level"])
                + "** • Treasury **"
                + str(ship["treasury"])
                + " Doubloons**"
            ),
            color=0x3498DB
        )

        embed.add_field(
            name="Ship Commands",
            value=(
                "`!cutlass ship` — Ship status\n"
                "`!cutlass ship history` — Ship history\n"
                "`!cutlass ship treasury` — Treasury\n"
                "`!cutlass ship donate <amount>` — Donate Doubloons\n"
                "`!cutlass ship repair` — Repair ship\n"
                "`!cutlass ship upgrades` — View upgrades\n"
                "`!cutlass ship upgrade <name>` — Buy upgrade"
            ),
            inline=False
        )

        embed.add_field(
            name="Voyages",
            value=(
                "`!cutlass voyage destinations` — Available voyages\n"
                "`!cutlass voyage status` — Current voyage\n"
                "`!cutlass voyage start <number>` — Begin voyage"
            ),
            inline=False
        )

        await message.reply(
            embed=embed,
            mention_author=False
        )

        return True

    if command == "!cutlass help world":
        embed = discord.Embed(
            title="🌍 Pirate World & Combat",
            description=(
                "**World & Exploration**\n"
                "`!cutlass world` — Pirate World status\n"
                "`!cutlass world map` — View discovered regions and islands\n"
                "`!cutlass world locations` — View discovered locations\n"
                "`!cutlass world history` — View world history\n"
                "`!cutlass explore` — Explore the Pirate World\n"
                "`!cutlass island` — View the current island\n"
                "`!cutlass island explore` — Explore the current island\n\n"

                "**Naval Combat**\n"
                "`!cutlass battle` — Current naval battle\n"
                "`!cutlass battle attack` — Fire on the enemy\n"
                "`!cutlass battle defend` — Brace for incoming fire\n"
                "`!cutlass battle board` — Boarding action status\n"
                "`!cutlass battle flee` — Attempt to escape\n\n"

                "**Sea Monsters**\n"
                "`!cutlass monster` — Current monster encounter\n"
                "`!cutlass monster attack` — Attack the monster\n\n"

                "**Boss Encounters**\n"
                "`!cutlass boss` — Current boss encounter\n"
                "`!cutlass boss attack` — Attack the boss\n"
                "`!cutlass boss defend` — Defend against the boss"
            ),
            color=0x3498DB
        )

        await message.reply(
            embed=embed,
            mention_author=False
        )

        return True


    if command == "!cutlass help admin":
        embed = discord.Embed(
            title="⚙️ Admiralty Controls",
            description="Administrative Captain Cutlass settings.",
            color=0x3498DB
        )

        embed.add_field(
            name="Welcome & Returners",
            value=(
                "`!cutlass welcome status`\n"
                "`!cutlass welcome channel #channel`\n"
                "`!cutlass welcome on/off`\n"
                "`!cutlass testwelcome`\n"
                "`!cutlass returners status`\n"
                "`!cutlass returners on/off`\n"
                "`!cutlass returners days <days>`"
            ),
            inline=False
        )

        embed.add_field(
            name="Captain's Log",
            value=(
                "`!cutlass log channel #channel`\n"
                "`!cutlass log on/off`\n"
                "`!cutlass log status`\n"
                "`!cutlass chronicle now`"
            ),
            inline=False
        )

        embed.add_field(
            name="Ship World",
            value=(
                "`!cutlass ship channel #channel`\n"
                "`!cutlass ship on/off`\n"
                "`!cutlass ship status`\n"
                "`!cutlass ship name <name>`\n"
                "`!cutlass ship upgrade <name>`\n"
                "`!cutlass voyage start <number>`"
            ),
            inline=False
        )

        embed.add_field(
            name="Server Controls",
            value=(
                "`!cutlass quiet on/off`\n"
                "`!cutlass mood <mood>`\n"
                "`!cutlass event on/off`\n"
                "`!cutlass treasure start ANSWER | CLUE`"
            ),
            inline=False
        )

        await message.reply(
            embed=embed,
            mention_author=False
        )

        return True

    if command == "!cutlass help all":
        pages = [
            (
                "**Crew & Profiles**\n"
                "`!cutlass profile`\n"
                "`!cutlass memory`\n"
                "`!cutlass relationship`\n"
                "`!cutlass balance`\n"
                "`!cutlass achievements`\n"
                "`!cutlass leaderboard`\n"
                "`!cutlass birthday`\n"
                "`!cutlass birthdays`"
            ),
            (
                "**Fun & History**\n"
                "`!cutlass lore`\n"
                "`!cutlass canon`\n"
                "`!cutlass serverlore`\n"
                "`!cutlass quote`\n"
                "`!cutlass wisdom`\n"
                "`!cutlass journal`\n"
                "`!cutlass timeline`\n"
                "`!cutlass story`\n"
                "`!cutlass punbattle`\n"
                "`!cutlass chronicle latest`"
            ),
            (
                "**Parrot**\n"
                "`!cutlass parrot`\n"
                "`!cutlass parrot talk <message>`\n"
                "`!cutlass parrot relationship`\n"
                "`!cutlass parrot memories`\n"
                "`!cutlass parrot jokes`\n"
                "`!cutlass parrot history`"
            ),
            (
                "**Pirate World & Combat**\n"
                "`!cutlass world`\n"
                "`!cutlass world map`\n"
                "`!cutlass world locations`\n"
                "`!cutlass explore`\n"
                "`!cutlass island`\n"
                "`!cutlass island explore`\n"
                "`!cutlass battle`\n"
                "`!cutlass battle attack`\n"
                "`!cutlass battle defend`\n"
                "`!cutlass battle flee`\n"
                "`!cutlass monster`\n"
                "`!cutlass monster attack`\n"
                "`!cutlass boss`\n"
                "`!cutlass boss attack`\n"
                "`!cutlass boss defend`"
            ),
            (
                "**Ship World**\n"
                "`!cutlass ship`\n"
                "`!cutlass ship history`\n"
                "`!cutlass ship treasury`\n"
                "`!cutlass ship donate <amount>`\n"
                "`!cutlass ship repair`\n"
                "`!cutlass ship upgrades`\n"
                "`!cutlass voyage destinations`\n"
                "`!cutlass voyage status`"
            )
        ]

        for page in pages:
            await message.channel.send(page)

        return True

    return False
