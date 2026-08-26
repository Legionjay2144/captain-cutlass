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

    # =====================================================
    # Main Help
    # =====================================================

    if command in (
        "!cutlass help",
        "!cutlass commands"
    ):
        parrot = await get_parrot(
            message.guild.id
        )

        ship = await get_ship(
            message.guild.id
        )

        embed = discord.Embed(
            title="🏴‍☠️ Captain Cutlass Help",
            description=(
                "Welcome aboard. Choose a category below "
                "to see the commands ye need.\n\n"

                "**Crew & Profiles** — "
                "`!cutlass help crew`\n"

                "**Fun, Lore & History** — "
                "`!cutlass help fun`\n"

                f"**{parrot['name']}** — "
                "`!cutlass help parrot`\n"

                f"**{ship['name']}** — "
                "`!cutlass help ship`\n"

                "**Pirate World & Combat** — "
                "`!cutlass help world`\n"

                "**Admiralty Controls** — "
                "`!cutlass help admin`\n\n"

                "**Shortcut:** `!c` can replace "
                "`!cutlass` on any command.\n"

                "Example: `!c ship`, `!c explore`, "
                "`!c attack`\n\n"

                "Use `!cutlass help all` for the "
                "full command list."
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

    # =====================================================
    # Crew
    # =====================================================

    if command == "!cutlass help crew":

        embed = discord.Embed(
            title="👤 Crew & Profile Commands",
            color=0x3498DB
        )

        embed.description = (
            "`!cutlass profile` — View your crew profile\n"
            "`!cutlass memory` — Captain's memories of you\n"
            "`!cutlass relationship` — Relationship with Captain\n"
            "`!cutlass creator` — Creator recognition\n"
            "`!cutlass balance` — View your Doubloons\n"
            "`!cutlass achievements` — View achievements\n"
            "`!cutlass leaderboard` — Doubloon leaderboard\n"
            "`!cutlass crew` — Top crewmates\n"
            "`!cutlass stats` — Your statistics\n"
            "`!cutlass birthday` — View your birthday\n"
            "`!cutlass birthday set <month> <day>` — Set birthday\n"
            "`!cutlass birthday clear` — Remove birthday\n"
            "`!cutlass birthdays` — Crew birthdays\n"
            "`!cutlass forgetme` — Forget stored member memories"
        )

        await message.reply(
            embed=embed,
            mention_author=False
        )

        return True

    # =====================================================
    # Fun / Lore
    # =====================================================

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

    # =====================================================
    # Parrot
    # =====================================================

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

    # =====================================================
    # Living Ship
    # =====================================================

    if command == "!cutlass help ship":

        ship = await get_ship(
            message.guild.id
        )

        embed = discord.Embed(
            title="🚢 " + ship["name"] + " — Living Ship",
            description=(
                "Level **"
                + str(ship["level"])
                + "** • Treasury **"
                + str(ship["treasury"])
                + " Doubloons**\n\n"

                "The Living Ship is shared by the whole crew. "
                "Damage, supplies, voyages, combat, XP, and "
                "upgrades persist across the server."
            ),
            color=0x3498DB
        )

        embed.add_field(
            name="Ship Commands",
            value=(
                "`!c ship` — Current ship status\n"
                "`!c ship history` — Recorded ship history\n"
                "`!c ship treasury` — Treasury\n"
                "`!c ship donate <amount>` — Donate Doubloons\n"
                "`!c ship repair` — Repair the ship\n"
                "`!c ship upgrades` — View upgrades\n"
                "`!c ship upgrade <name>` — Purchase an upgrade"
            ),
            inline=False
        )

        embed.add_field(
            name="Voyages",
            value=(
                "`!c voyage` — Charted voyage destinations\n"
                "`!c voyage destinations` — Charted destinations\n"
                "`!c voyage status` — Current voyage\n"
                "`!c voyage start <number>` — Set sail\n\n"

                "Only charted islands can be reached. "
                "Some routes also require a higher "
                "Living Ship level."
            ),
            inline=False
        )

        embed.add_field(
            name="Exploration",
            value=(
                "`!c explore` — Scout surrounding waters\n"
                "`!c island` — Inspect the current island\n"
                "`!c island explore` — Explore the current island\n\n"

                "Scouting can discover islands but does not move "
                "the Living Ship. Voyages physically move her."
            ),
            inline=False
        )

        await message.reply(
            embed=embed,
            mention_author=False
        )

        return True

    # =====================================================
    # Pirate World
    # =====================================================

    if command == "!cutlass help world":

        embed = discord.Embed(
            title="🌍 Pirate World & Combat",
            color=0x3498DB
        )

        embed.add_field(
            name="World & Scouting",
            value=(
                "`!c world` — Pirate World status\n"
                "`!c world map` — Discovered regions and islands\n"
                "`!c world locations` — Discovered locations\n"
                "`!c world history` — World discovery history\n"
                "`!c explore` — Scout surrounding waters\n\n"

                "Scouting may discover new islands. "
                "It does **not** physically move the Living Ship."
            ),
            inline=False
        )

        embed.add_field(
            name="Island Exploration",
            value=(
                "`!c island` — View the island at the ship's location\n"
                "`!c island explore` — Explore that island\n\n"

                "Island exploration can uncover treasure, supplies, "
                "lore, strange events, monsters, and legendary "
                "encounters. Revisited islands use an exploration "
                "cooldown."
            ),
            inline=False
        )

        embed.add_field(
            name="Unified Combat",
            value=(
                "`!c attack` — Attack the active encounter\n"
                "`!c defend` — Defend when supported\n"
                "`!c board` — Board an enemy vessel when supported\n"
                "`!c flee` — Attempt to flee when supported\n\n"

                "Combat automatically targets the active naval "
                "battle, sea monster, or boss encounter."
            ),
            inline=False
        )

        embed.add_field(
            name="Encounter Status",
            value=(
                "`!c battle` — Current naval battle\n"
                "`!c monster` — Current sea monster encounter\n"
                "`!c boss` — Current legendary boss encounter"
            ),
            inline=False
        )

        embed.add_field(
            name="Legacy / Advanced Aliases",
            value=(
                "`!cutlass battle attack/defend/board/flee`\n"
                "`!cutlass monster attack`\n"
                "`!cutlass boss attack/defend`"
            ),
            inline=False
        )

        await message.reply(
            embed=embed,
            mention_author=False
        )

        return True

    # =====================================================
    # Admiralty
    # =====================================================

    if command == "!cutlass help admin":

        embed = discord.Embed(
            title="⚙️ Admiralty Controls",
            description=(
                "Server configuration commands reserved "
                "for the Admiralty."
            ),
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
            name="Ship World Configuration",
            value=(
                "`!cutlass ship channel #channel`\n"
                "`!cutlass ship on/off`\n"
                "`!cutlass ship status`\n"
                "`!cutlass ship name <name>`"
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

        embed.set_footer(
            text=(
                "Admiralty configures the Ship World. "
                "The crew plays the Ship World."
            )
        )

        await message.reply(
            embed=embed,
            mention_author=False
        )

        return True

    # =====================================================
    # Full Command List
    # =====================================================

    if command == "!cutlass help all":

        pages = [
            (
                "**Crew & Profiles**\n"
                "`!c profile`\n"
                "`!c memory`\n"
                "`!c relationship`\n"
                "`!c balance`\n"
                "`!c achievements`\n"
                "`!c leaderboard`\n"
                "`!c crew`\n"
                "`!c stats`\n"
                "`!c birthday`\n"
                "`!c birthdays`\n"
                "`!c forgetme`"
            ),
            (
                "**Fun, Lore & History**\n"
                "`!c lore`\n"
                "`!c canon`\n"
                "`!c serverlore`\n"
                "`!c quote`\n"
                "`!c wisdom`\n"
                "`!c journal`\n"
                "`!c timeline`\n"
                "`!c story`\n"
                "`!c punbattle`\n"
                "`!c chronicle latest`\n"
                "`!c mood`"
            ),
            (
                "**Parrot**\n"
                "`!c parrot`\n"
                "`!c parrot talk <message>`\n"
                "`!c parrot relationship`\n"
                "`!c parrot memories`\n"
                "`!c parrot jokes`\n"
                "`!c parrot history`\n"
                "`!c parrot mood`"
            ),
            (
                "**Pirate World & Exploration**\n"
                "`!c world`\n"
                "`!c world map`\n"
                "`!c world locations`\n"
                "`!c world history`\n"
                "`!c explore` — Scout surrounding waters\n"
                "`!c island` — Current island\n"
                "`!c island explore` — Explore current island"
            ),
            (
                "**Combat**\n"
                "`!c attack` — Attack active encounter\n"
                "`!c defend` — Defend when supported\n"
                "`!c board` — Board when supported\n"
                "`!c flee` — Flee when supported\n"
                "`!c battle` — Naval battle status\n"
                "`!c monster` — Monster status\n"
                "`!c boss` — Boss status"
            ),
            (
                "**Living Ship & Voyages**\n"
                "`!c ship`\n"
                "`!c ship history`\n"
                "`!c ship treasury`\n"
                "`!c ship donate <amount>`\n"
                "`!c ship repair`\n"
                "`!c ship upgrades`\n"
                "`!c ship upgrade <name>`\n"
                "`!c voyage`\n"
                "`!c voyage status`\n"
                "`!c voyage start <number>`"
            )
        ]

        for page in pages:
            await message.channel.send(
                page
            )

        return True

    return False
