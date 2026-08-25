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

    "sirens_reef": {
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
