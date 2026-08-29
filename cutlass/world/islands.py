import random


ISLAND_CONTENT = {
    "blacktooth_cove": {
        "name": "Blacktooth Cove",
        "activities": [
            {
                "type": "treasure",
                "title": "Smuggler's Cache",
                "description": "The crew finds a hidden cache beneath an abandoned dock.",
                "reward_min": 40,
                "reward_max": 120,
            },
            {
                "type": "supplies",
                "title": "Dockside Supplies",
                "description": "Several unattended crates appear to have changed ownership.",
                "amount_min": 10,
                "amount_max": 25,
            },
            {
                "type": "lore",
                "title": "Tavern Rumor",
                "description": "A nervous sailor whispers about strange lights beyond the Devil's Expanse.",
            },
        ],
    },

    "skullfin_island": {
        "name": "Skullfin Island",
        "activities": [
            {
                "type": "treasure",
                "title": "Ancient Ruins",
                "description": "The crew uncovers a sealed chamber beneath the jungle ruins.",
                "reward_min": 100,
                "reward_max": 250,
            },
            {
                "type": "supplies",
                "title": "Abandoned Expedition",
                "description": "Supplies from a failed expedition are recovered from the jungle.",
                "amount_min": 15,
                "amount_max": 35,
            },
            {
                "type": "boss",
                "title": "Guardian of Skullfin",
                "description": "Something enormous moves beyond the ruined temple.",
                "boss": "skullfin_guardian",
            },
        ],
    },

    "deadmans_rest": {
        "name": "Deadman's Rest",
        "activities": [
            {
                "type": "treasure",
                "title": "Cursed Strongbox",
                "description": "A barnacle-covered strongbox is found inside an abandoned home.",
                "reward_min": 150,
                "reward_max": 300,
            },
            {
                "type": "lore",
                "title": "The Empty Settlement",
                "description": "Fresh footprints cross streets that have supposedly been abandoned for decades.",
            },
            {
                "type": "boss",
                "title": "The Drowned Captain",
                "description": "A dead captain walks from the surf with a rusted cutlass in hand.",
                "boss": "drowned_captain",
            },
        ],
    },

    "devils_maw": {
        "name": "Devil's Maw",
        "activities": [
            {
                "type": "treasure",
                "title": "Volcanic Vault",
                "description": "A cave behind flowing lava conceals an old pirate vault.",
                "reward_min": 250,
                "reward_max": 500,
            },
            {
                "type": "monster",
                "title": "Something Beneath the Maw",
                "description": "The sea begins to churn violently beside the island.",
                "monster": "leviathan",
            },
            {
                "type": "lore",
                "title": "Burned Captain's Log",
                "description": "A scorched journal describes a creature sleeping beneath the surrounding waters.",
            },
        ],
    },

    "whispering_key": {
        "name": "Whispering Key",
        "activities": [
            {
                "type": "treasure",
                "title": "Buried Cache",
                "description": "An old map leads the crew beneath a crooked palm tree.",
                "reward_min": 120,
                "reward_max": 300,
            },
            {
                "type": "lore",
                "title": "Whispers in the Trees",
                "description": "The wind seems to repeat the names of pirates who vanished years ago.",
            },
        ],
    },

    "siren_reef": {
        "name": "Siren's Reef",
        "activities": [
            {
                "type": "treasure",
                "title": "Sunken Cargo",
                "description": "The crew dives to a wreck trapped between the reefs.",
                "reward_min": 175,
                "reward_max": 350,
            },
            {
                "type": "monster",
                "title": "Predator of the Reef",
                "description": "A massive shadow circles beneath the diving crew.",
                "monster": "leviathan",
            },
            {
                "type": "supplies",
                "title": "Salvaged Provisions",
                "description": "Sealed barrels are recovered from a remarkably intact wreck.",
                "amount_min": 15,
                "amount_max": 30,
            },
        ],
    },

    # ---------------------------------------------------------
    # Priority 4 — The Shattered Coast
    # ---------------------------------------------------------

    "gullwatch_cay": {
        "name": "Gullwatch Cay",
        "activities": [
            {
                "type": "supplies",
                "title": "Fisherman's Storehouse",
                "description": (
                    "The crew finds a weathered storehouse "
                    "packed with preserved food and fresh water."
                ),
                "amount_min": 12,
                "amount_max": 28,
            },
            {
                "type": "treasure",
                "title": "Contraband Ledger",
                "description": (
                    "A smuggler's ledger leads the crew to "
                    "a payment chest hidden beneath the cliffs."
                ),
                "reward_min": 60,
                "reward_max": 150,
            },
            {
                "type": "lore",
                "title": "Signals on the Horizon",
                "description": (
                    "A lookout's journal describes coded lantern "
                    "signals exchanged with ships that never enter port."
                ),
            },
        ],
    },

    "smugglers_hollow": {
        "name": "Smuggler's Hollow",
        "activities": [
            {
                "type": "treasure",
                "title": "The Hollow's Reserve",
                "description": (
                    "Behind a false cavern wall lies a forgotten "
                    "smuggling reserve of coin and valuables."
                ),
                "reward_min": 180,
                "reward_max": 375,
            },
            {
                "type": "supplies",
                "title": "Hidden Provision Caves",
                "description": (
                    "Dry chambers above the tide line contain sealed "
                    "barrels left by smugglers who never returned."
                ),
                "amount_min": 20,
                "amount_max": 40,
            },
            {
                "type": "lore",
                "title": "The Tide Cipher",
                "description": (
                    "Symbols carved into the cave walls reveal how "
                    "old smugglers predicted the hidden passage's tides."
                ),
            },
        ],
    },

    # ---------------------------------------------------------
    # Priority 4 — Blackwater Reach
    # ---------------------------------------------------------

    "gallows_key": {
        "name": "Gallows Key",
        "activities": [
            {
                "type": "treasure",
                "title": "Confiscated Pirate Gold",
                "description": (
                    "A collapsed prison office hides valuables "
                    "confiscated from condemned pirates."
                ),
                "reward_min": 160,
                "reward_max": 340,
            },
            {
                "type": "lore",
                "title": "The Prisoner's Wall",
                "description": (
                    "Names and final messages cover a cell wall, "
                    "including references to a treasure fleet "
                    "that supposedly vanished without a battle."
                ),
            },
            {
                "type": "boss",
                "title": "The Last Jailer",
                "description": (
                    "Heavy chains drag across the ruined prison "
                    "courtyard though no living jailer remains."
                ),
                "boss": "last_jailer",
            },
        ],
    },

    # ---------------------------------------------------------
    # Priority 4 — The Emerald Tempest
    # ---------------------------------------------------------

    "verdant_fang": {
        "name": "Verdant Fang",
        "activities": [
            {
                "type": "supplies",
                "title": "Jungle Harvest",
                "description": (
                    "The crew gathers fresh fruit, medicinal plants, "
                    "and clean water from the island interior."
                ),
                "amount_min": 18,
                "amount_max": 38,
            },
            {
                "type": "treasure",
                "title": "Temple Offering",
                "description": (
                    "An overgrown stone terrace conceals an ancient "
                    "offering chamber untouched by looters."
                ),
                "reward_min": 200,
                "reward_max": 425,
            },
            {
                "type": "lore",
                "title": "The Fang Stirs",
                "description": (
                    "Trees crash in the jungle as something enormous "
                    "begins stalking the expedition."
                ),
            },
            {
                "type": "lore",
                "title": "The Vine-Covered Map",
                "description": (
                    "A ruined stone map depicts islands and sea routes "
                    "that do not appear on modern charts."
                ),
            },
        ],
    },

    "stormglass_isle": {
        "name": "Stormglass Isle",
        "activities": [
            {
                "type": "treasure",
                "title": "Stormglass Cache",
                "description": (
                    "Rare green stormglass and an old pirate strongbox "
                    "are recovered from a lightning-scarred ravine."
                ),
                "reward_min": 225,
                "reward_max": 450,
            },
            {
                "type": "supplies",
                "title": "Sheltered Expedition Camp",
                "description": (
                    "A reinforced camp abandoned between storms still "
                    "contains usable expedition supplies."
                ),
                "amount_min": 15,
                "amount_max": 32,
            },
            {
                "type": "lore",
                "title": "The Lightning Stones",
                "description": (
                    "Old expedition notes claim the island's storms "
                    "follow a repeating pattern centered on ancient stones."
                ),
            },
        ],
    },

    "moonpool_sanctuary": {
        "name": "Moonpool Sanctuary",
        "activities": [
            {
                "type": "treasure",
                "title": "The Moonpool Offering",
                "description": (
                    "Silver coins and gemstones lie beneath the clear "
                    "water of a ceremonial pool."
                ),
                "reward_min": 300,
                "reward_max": 600,
            },
            {
                "type": "supplies",
                "title": "Untouched Sanctuary",
                "description": (
                    "Fresh water, fruit, and medicinal plants flourish "
                    "inside the protected lagoon."
                ),
                "amount_min": 25,
                "amount_max": 45,
            },
            {
                "type": "lore",
                "title": "The Sanctuary Carvings",
                "description": (
                    "Ancient carvings describe sailors hiding here "
                    "from a catastrophe that came from the open sea."
                ),
            },
        ],
    },

    # ---------------------------------------------------------
    # Priority 4 — The Frostgrave Sea
    # ---------------------------------------------------------

    "whitebone_isle": {
        "name": "Whitebone Isle",
        "activities": [
            {
                "type": "treasure",
                "title": "Frozen Expedition Chest",
                "description": (
                    "A century-old expedition chest is cut free "
                    "from the ice beneath an abandoned camp."
                ),
                "reward_min": 275,
                "reward_max": 550,
            },
            {
                "type": "supplies",
                "title": "Expedition Stores",
                "description": (
                    "Cold-preserved provisions and lamp oil remain "
                    "usable inside a frozen supply hut."
                ),
                "amount_min": 18,
                "amount_max": 35,
            },
            {
                "type": "lore",
                "title": "The Whitebone Hunter",
                "description": (
                    "A massive shape moves between the ice ridges "
                    "and begins circling the landing party."
                ),
            },
            {
                "type": "lore",
                "title": "Bones Beneath the Ice",
                "description": (
                    "The enormous bones along the coast appear far "
                    "older than any known charts of the Frostgrave Sea."
                ),
            },
        ],
    },

    "frozen_wreckyard": {
        "name": "The Frozen Wreckyard",
        "activities": [
            {
                "type": "treasure",
                "title": "Admiral's Lost Payroll",
                "description": (
                    "Deep inside an icebound naval wreck, the crew "
                    "finds a payroll chest that never reached its fleet."
                ),
                "reward_min": 400,
                "reward_max": 800,
            },
            {
                "type": "supplies",
                "title": "Frozen Naval Stores",
                "description": (
                    "Sealed naval stores survive inside one of the "
                    "better-preserved wrecks."
                ),
                "amount_min": 25,
                "amount_max": 50,
            },
            {
                "type": "boss",
                "title": "Admiral Coldgrave",
                "description": (
                    "A frozen figure in an admiral's coat rises from "
                    "the flagship as the wreckyard groans around it."
                ),
                "boss": "admiral_coldgrave",
            },
            {
                "type": "lore",
                "title": "The Fleet's Final Orders",
                "description": (
                    "The flagship's log reveals the fleet entered "
                    "the ice deliberately while pursuing something."
                ),
            },
        ],
    },
}


def normalize_island_name(name):
    return (
        str(name)
        .lower()
        .replace("'", "")
        .replace("’", "")
        .replace("-", "_")
        .replace(" ", "_")
    )


def get_island_content(name):
    return ISLAND_CONTENT.get(
        normalize_island_name(name)
    )


def format_island(name):
    island = get_island_content(name)

    if island is None:
        return None

    lines = [
        "**" + island["name"].upper() + "**",
        "",
        "Available discoveries:",
    ]

    for activity in island["activities"]:
        lines.append(
            "• " + activity["title"]
        )

    lines.extend([
        "",
        "Use `!cutlass island explore` to investigate."
    ])

    return "\n".join(lines)


def choose_island_activity(name):
    island = get_island_content(name)

    if island is None:
        return None

    return random.choice(
        island["activities"]
    )
