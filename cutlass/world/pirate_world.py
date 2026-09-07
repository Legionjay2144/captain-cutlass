import os
import random

import aiosqlite

from cutlass.world.locks import get_guild_lock


DB_PATH = os.getenv(
    "DATABASE_PATH",
    "/app/data/captain.db"
)


# ---------------------------------------------------------
# World definitions
# ---------------------------------------------------------

REGIONS = {
    "shattered_coast": {
        "name": "The Shattered Coast",
        "danger": "Low",
        "theme": "Smugglers, coves, trade lanes, and broken islands.",
        "encounter_profile": "coastal",
        "description": (
            "Broken islands, smugglers, forgotten coves, "
            "and relatively forgiving waters."
        ),
    },

    "blackwater_reach": {
        "name": "Blackwater Reach",
        "danger": "Medium",
        "theme": "Pirate hunters, ruins, reefs, and abandoned forts.",
        "encounter_profile": "blackwater",
        "description": (
            "Dark currents, pirate hunting grounds, "
            "abandoned forts, and dangerous reefs."
        ),
    },

    "emerald_tempest": {
        "name": "The Emerald Tempest",
        "danger": "High",
        "theme": "Jungle islands, violent squalls, ruins, and strange wildlife.",
        "encounter_profile": "tempest",
        "description": (
            "A storm-wracked tropical frontier where jungle-covered "
            "islands rise from brilliant green water and ancient ruins "
            "vanish beneath the vines."
        ),
    },

    "devils_expanse": {
        "name": "The Devil's Expanse",
        "danger": "Extreme",
        "theme": "Volcanoes, monsters, wrecks, and cursed waters.",
        "encounter_profile": "devils_expanse",
        "description": (
            "Violent seas where monsters, ghost stories, "
            "and legendary pirate crews are said to roam."
        ),
    },

    "frostgrave_sea": {
        "name": "The Frostgrave Sea",
        "danger": "Extreme",
        "theme": "Icebergs, frozen wrecks, blizzards, and lost expeditions.",
        "encounter_profile": "frostgrave",
        "description": (
            "A bitter northern sea of moving ice, sudden whiteouts, "
            "frozen wrecks, and expeditions that never returned."
        ),
    },
}




REGION_ENCOUNTER_TEXT = {
    "coastal": {
        "naval": (
            "Lookouts spotted unfamiliar sails weaving between "
            "the shoals and busy coastal shipping lanes."
        ),
        "monster": (
            "A huge shadow rolled beneath the clear coastal water "
            "before disappearing toward deeper seas."
        ),
        "quiet": (
            "The crew charted reefs, currents, fishing grounds, "
            "and well-traveled coastal waters."
        ),
    },
    "blackwater": {
        "naval": (
            "Dark sails emerged through the mist, using the murky "
            "channels of Blackwater Reach for cover."
        ),
        "monster": (
            "Something massive disturbed the black water below, "
            "leaving a widening wake through the fog."
        ),
        "quiet": (
            "The crew sounded the murky channels and marked hidden "
            "shoals beneath the black water."
        ),
    },
    "tempest": {
        "naval": (
            "A ship appeared between towering storm fronts, its "
            "sails flashing beneath sheets of rain and lightning."
        ),
        "monster": (
            "A vast shape surfaced beneath the storm swell as "
            "lightning illuminated the churning sea."
        ),
        "quiet": (
            "The crew mapped storm currents, jungle-lined shores, "
            "and dangerous reefs between squalls."
        ),
    },
    "devils_expanse": {
        "naval": (
            "Hostile sails crossed the red horizon through smoke, "
            "ash, and the glow of distant volcanic waters."
        ),
        "monster": (
            "The sea heaved violently as something enormous moved "
            "through the superheated depths below."
        ),
        "quiet": (
            "The crew charted volcanic shoals, boiling currents, "
            "and treacherous passages through Devil's Expanse."
        ),
    },
    "frostgrave": {
        "naval": (
            "A dark vessel emerged between drifting ice and thick "
            "fog, silently closing through the frozen sea."
        ),
        "monster": (
            "The ice groaned as something immense passed beneath "
            "the frozen surface alongside the scouting vessel."
        ),
        "quiet": (
            "The crew marked ice fields, frozen wrecks, shifting "
            "channels, and safe passages through the fog."
        ),
    },
}


REGION_ENCOUNTER_PROFILES = {
    "coastal": {
        "naval": 8,
        "monster": 2,
        "hazard": 3,
        "supplies": 12,
        "treasure": 5,
        "quiet": 70,
    },
    "blackwater": {
        "naval": 12,
        "monster": 6,
        "hazard": 10,
        "supplies": 7,
        "treasure": 5,
        "quiet": 60,
    },
    "tempest": {
        "naval": 8,
        "monster": 10,
        "hazard": 15,
        "supplies": 6,
        "treasure": 5,
        "quiet": 56,
    },
    "devils_expanse": {
        "naval": 14,
        "monster": 12,
        "hazard": 20,
        "supplies": 4,
        "treasure": 6,
        "quiet": 44,
    },
    "frostgrave": {
        "naval": 10,
        "monster": 10,
        "hazard": 18,
        "supplies": 7,
        "treasure": 5,
        "quiet": 50,
    },
}


REGION_HAZARDS = {
    "coastal": (
        {
            "name": "Hidden Reef",
            "text": (
                "A hidden reef scraped along the hull before "
                "the crew could reach deeper water."
            ),
            "hull_damage": (2, 6),
        },
        {
            "name": "Sudden Squall",
            "text": (
                "A sudden coastal squall caught the ship under "
                "too much canvas and strained the rigging."
            ),
            "sails_damage": (2, 5),
        },
    ),
    "blackwater": (
        {
            "name": "Blackwater Shoal",
            "text": (
                "The ship struck a submerged shoal hidden beneath "
                "the dark water and thick mist."
            ),
            "hull_damage": (5, 11),
        },
        {
            "name": "Lost in the Fog",
            "text": (
                "Hours were lost navigating the choking fog, "
                "burning provisions and exhausting the crew."
            ),
            "supplies_change": (-8, -3),
            "morale_change": (-5, -2),
        },
    ),
    "tempest": (
        {
            "name": "Violent Squall",
            "text": (
                "A violent squall tore through the rigging as the "
                "crew fought to keep the ship beneath her masts."
            ),
            "sails_damage": (7, 15),
            "morale_change": (-5, -2),
        },
        {
            "name": "Lightning Storm",
            "text": (
                "Lightning and mountainous seas battered the ship "
                "while the crew struggled through the storm front."
            ),
            "hull_damage": (3, 8),
            "sails_damage": (4, 10),
        },
    ),
    "devils_expanse": (
        {
            "name": "Volcanic Shoals",
            "text": (
                "The ship scraped across jagged volcanic stone "
                "hidden beneath the ash-darkened sea."
            ),
            "hull_damage": (9, 18),
        },
        {
            "name": "Boiling Current",
            "text": (
                "A superheated current forced the ship onto a long "
                "detour while heat spoiled part of the provisions."
            ),
            "supplies_change": (-12, -5),
            "morale_change": (-7, -3),
        },
        {
            "name": "Ash Storm",
            "text": (
                "Hot ash and violent wind swept across the deck, "
                "damaging canvas and wearing down the crew."
            ),
            "sails_damage": (7, 14),
            "morale_change": (-6, -2),
        },
    ),
    "frostgrave": (
        {
            "name": "Drifting Ice",
            "text": (
                "A mass of drifting ice struck the ship before "
                "the helm could turn clear."
            ),
            "hull_damage": (8, 16),
        },
        {
            "name": "Frozen Rigging",
            "text": (
                "Ice accumulated across the rigging until lines "
                "and canvas began to tear under the weight."
            ),
            "sails_damage": (7, 14),
        },
        {
            "name": "Bitter Whiteout",
            "text": (
                "A prolonged whiteout trapped the crew in freezing "
                "waters and consumed precious stores."
            ),
            "supplies_change": (-10, -4),
            "morale_change": (-8, -3),
        },
    ),
}


REGION_RESOURCE_TEXT = {
    "coastal": {
        "supplies": (
            "The crew recovered usable stores from abandoned "
            "cargo drifting near the trade lanes."
        ),
        "treasure": (
            "A waterlogged strongbox was recovered from wreckage "
            "caught between the coastal shoals."
        ),
    },
    "blackwater": {
        "supplies": (
            "Sealed provision barrels were found drifting through "
            "the mist among the remains of an old wreck."
        ),
        "treasure": (
            "The crew hauled a locked naval pay chest from wreckage "
            "half-hidden beneath the black water."
        ),
    },
    "tempest": {
        "supplies": (
            "Storm-tossed expedition crates were recovered before "
            "the next squall swept across the sea."
        ),
        "treasure": (
            "Fresh wreckage revealed a sealed strongbox thrown "
            "overboard by the violent storms."
        ),
    },
    "devils_expanse": {
        "supplies": (
            "The crew salvaged heat-scarred but usable stores from "
            "a wreck drifting beyond the volcanic shoals."
        ),
        "treasure": (
            "A scorched treasure chest was pulled from wreckage "
            "circling the volcanic current."
        ),
    },
    "frostgrave": {
        "supplies": (
            "Frozen expedition stores were recovered from wreckage "
            "preserved between the ice floes."
        ),
        "treasure": (
            "The crew freed an old strongbox from a frozen wreck "
            "before the ice closed around it again."
        ),
    },
}


ISLANDS = {
    # ---------------------------------------------------------
    # The Shattered Coast
    # ---------------------------------------------------------

    "blacktooth_cove": {
        "name": "Blacktooth Cove",
        "region": "shattered_coast",
        "danger": "Low",
        "terrain": "harbor",
        "hidden": False,
        "discovery_weight": 100,
        "description": (
            "A crooked little harbor filled with smugglers, "
            "taverns, and suspicious merchants."
        ),
    },

    "whispering_key": {
        "name": "Whispering Key",
        "region": "shattered_coast",
        "danger": "Low",
        "terrain": "tropical",
        "hidden": False,
        "discovery_weight": 90,
        "description": (
            "A quiet island where strange stone markers "
            "point toward something buried beneath the palms."
        ),
    },

    "gullwatch_cay": {
        "name": "Gullwatch Cay",
        "region": "shattered_coast",
        "danger": "Low",
        "terrain": "coastal",
        "hidden": False,
        "discovery_weight": 100,
        "description": (
            "A wind-beaten cay overlooking busy trade waters, "
            "popular with fishermen, smugglers, and spies."
        ),
    },

    "smugglers_hollow": {
        "name": "Smuggler's Hollow",
        "region": "shattered_coast",
        "danger": "Medium",
        "terrain": "caverns",
        "hidden": True,
        "discovery_weight": 18,
        "description": (
            "A concealed inlet hidden behind sea caves and jagged stone, "
            "almost invisible unless approached on the right tide."
        ),
    },

    # ---------------------------------------------------------
    # Blackwater Reach
    # ---------------------------------------------------------

    "skullfin_island": {
        "name": "Skullfin Island",
        "region": "blackwater_reach",
        "danger": "Medium",
        "terrain": "jungle_ruins",
        "hidden": False,
        "discovery_weight": 90,
        "description": (
            "A jungle-covered island dotted with ruins, "
            "caves, and the bones of unfortunate explorers."
        ),
    },

    "deadmans_rest": {
        "name": "Deadman's Rest",
        "region": "blackwater_reach",
        "danger": "High",
        "terrain": "abandoned_settlement",
        "hidden": False,
        "discovery_weight": 75,
        "description": (
            "An abandoned pirate settlement where lanterns "
            "are sometimes seen despite nobody living there."
        ),
    },

    "gallows_key": {
        "name": "Gallows Key",
        "region": "blackwater_reach",
        "danger": "High",
        "terrain": "fortress_ruins",
        "hidden": False,
        "discovery_weight": 75,
        "description": (
            "A rocky island crowned by the ruins of an old naval prison "
            "and the remains of a weather-blackened gallows."
        ),
    },

    # ---------------------------------------------------------
    # The Emerald Tempest
    # ---------------------------------------------------------

    "verdant_fang": {
        "name": "Verdant Fang",
        "region": "emerald_tempest",
        "danger": "High",
        "terrain": "dense_jungle",
        "hidden": False,
        "discovery_weight": 70,
        "description": (
            "A steep jungle island shaped like a fang, covered in "
            "waterfalls, ancient terraces, and aggressive wildlife."
        ),
    },

    "stormglass_isle": {
        "name": "Stormglass Isle",
        "region": "emerald_tempest",
        "danger": "High",
        "terrain": "storm_coast",
        "hidden": False,
        "discovery_weight": 65,
        "description": (
            "Lightning repeatedly strikes the island's black beaches, "
            "leaving strange green glass scattered along the shore."
        ),
    },

    "moonpool_sanctuary": {
        "name": "Moonpool Sanctuary",
        "region": "emerald_tempest",
        "danger": "Medium",
        "terrain": "hidden_lagoon",
        "hidden": True,
        "discovery_weight": 12,
        "description": (
            "A sheltered lagoon enclosed by jungle cliffs, reachable "
            "only through a narrow flooded passage at low tide."
        ),
    },

    # ---------------------------------------------------------
    # The Devil's Expanse
    # ---------------------------------------------------------

    "devils_maw": {
        "name": "Devil's Maw",
        "region": "devils_expanse",
        "danger": "Extreme",
        "terrain": "volcanic",
        "hidden": False,
        "discovery_weight": 55,
        "description": (
            "A volcanic island surrounded by brutal waters "
            "and tales of creatures large enough to swallow ships."
        ),
    },

    "siren_reef": {
        "name": "Siren's Reef",
        "region": "devils_expanse",
        "danger": "Extreme",
        "terrain": "reef_wreckage",
        "hidden": False,
        "discovery_weight": 50,
        "description": (
            "Jagged coral, shipwrecks, and enough sailor tales "
            "to make even Captain Cutlass check the horizon twice."
        ),
    },

    # ---------------------------------------------------------
    # The Frostgrave Sea
    # ---------------------------------------------------------

    "whitebone_isle": {
        "name": "Whitebone Isle",
        "region": "frostgrave_sea",
        "danger": "Extreme",
        "terrain": "frozen_tundra",
        "hidden": False,
        "discovery_weight": 45,
        "description": (
            "A frozen island of pale cliffs and wind-carved ice where "
            "the bones of enormous sea creatures litter the coast."
        ),
    },

    "frozen_wreckyard": {
        "name": "The Frozen Wreckyard",
        "region": "frostgrave_sea",
        "danger": "Extreme",
        "terrain": "icebound_wrecks",
        "hidden": True,
        "discovery_weight": 8,
        "description": (
            "A maze of ancient ships trapped deep within shifting pack ice, "
            "visible only when the frozen sea opens a temporary passage."
        ),
    },
}


# ---------------------------------------------------------
# Persistent world findings
# ---------------------------------------------------------
#
# These are discoveries within already charted locations.
# They are deliberately separate from world_discoveries:
#
#   world_discoveries -> islands / charted geography
#   world_findings    -> unique sites, wrecks, ruins,
#                        landmarks, and lore discoveries
#
# Each finding may be discovered only once per guild.
# ---------------------------------------------------------

WORLD_FINDINGS = {
    # -----------------------------------------------------
    # Shattered Coast
    # -----------------------------------------------------
    "blacktooth_signal_tower": {
        "location": "blacktooth_cove",
        "type": "landmark",
        "name": "The Old Signal Tower",
        "rarity": "Common",
        "importance": 4,
        "description": (
            "A weather-beaten signal tower overlooking the "
            "approach to Blacktooth Cove, its fire basket "
            "still blackened from decades of use."
        ),
    },
    "whispering_stone_circle": {
        "location": "whispering_key",
        "type": "ruin",
        "name": "The Whispering Stones",
        "rarity": "Uncommon",
        "importance": 5,
        "description": (
            "A ring of salt-worn standing stones hidden "
            "among the palms, carved with symbols no living "
            "sailor can fully translate."
        ),
    },
    "gullwatch_beacon": {
        "location": "gullwatch_cay",
        "type": "landmark",
        "name": "The Gullwatch Beacon",
        "rarity": "Common",
        "importance": 4,
        "description": (
            "The remains of an old navigation beacon built "
            "to guide merchant ships safely through the "
            "coastal shoals."
        ),
    },
    "hollow_smuggler_vault": {
        "location": "smugglers_hollow",
        "type": "hidden_site",
        "name": "The Sealed Smuggler Vault",
        "rarity": "Rare",
        "importance": 7,
        "description": (
            "A concealed stone chamber beyond the flooded "
            "caverns, marked with the symbols of a vanished "
            "smuggling brotherhood."
        ),
    },

    # -----------------------------------------------------
    # Blackwater Reach
    # -----------------------------------------------------
    "skullfin_serpent_idol": {
        "location": "skullfin_island",
        "type": "ruin",
        "name": "The Serpent Idol",
        "rarity": "Uncommon",
        "importance": 5,
        "description": (
            "A moss-covered stone idol buried deep among "
            "Skullfin's ruins, depicting a crowned serpent "
            "rising from the sea."
        ),
    },
    "deadmans_bell": {
        "location": "deadmans_rest",
        "type": "lore",
        "name": "The Bell of Deadman's Rest",
        "rarity": "Uncommon",
        "importance": 6,
        "description": (
            "A cracked settlement bell whose inscription "
            "records the final evacuation of Deadman's Rest."
        ),
    },
    "gallows_prison_archive": {
        "location": "gallows_key",
        "type": "lore",
        "name": "The Gallows Prison Archive",
        "rarity": "Rare",
        "importance": 7,
        "description": (
            "A water-damaged registry naming prisoners, "
            "privateers, and condemned captains once held "
            "inside the ruined fortress."
        ),
    },

    # -----------------------------------------------------
    # Emerald Tempest
    # -----------------------------------------------------
    "verdant_sunken_temple": {
        "location": "verdant_fang",
        "type": "ruin",
        "name": "The Sunken Jungle Temple",
        "rarity": "Rare",
        "importance": 7,
        "description": (
            "A vine-covered temple complex sinking slowly "
            "into the jungle floor beneath the roots of "
            "enormous ancient trees."
        ),
    },
    "stormglass_observatory": {
        "location": "stormglass_isle",
        "type": "landmark",
        "name": "The Stormglass Observatory",
        "rarity": "Rare",
        "importance": 7,
        "description": (
            "A shattered stone observatory positioned where "
            "lightning repeatedly strikes the island's "
            "highest ridge."
        ),
    },
    "moonpool_tide_chamber": {
        "location": "moonpool_sanctuary",
        "type": "hidden_site",
        "name": "The Moonpool Tide Chamber",
        "rarity": "Legendary",
        "importance": 9,
        "description": (
            "A hidden chamber beneath the lagoon whose "
            "carved walls track tides, moons, and forgotten "
            "routes across the pirate seas."
        ),
    },

    # -----------------------------------------------------
    # Devil's Expanse
    # -----------------------------------------------------
    "maw_obsidian_gate": {
        "location": "devils_maw",
        "type": "landmark",
        "name": "The Obsidian Gate",
        "rarity": "Rare",
        "importance": 7,
        "description": (
            "Two immense pillars of volcanic glass forming "
            "a natural gateway above the boiling shoreline."
        ),
    },
    "siren_drowned_galleon": {
        "location": "siren_reef",
        "type": "wreck",
        "name": "The Drowned Galleon",
        "rarity": "Rare",
        "importance": 7,
        "description": (
            "The mostly intact remains of an unidentified "
            "galleon resting beneath the reef among dozens "
            "of smaller wrecks."
        ),
    },

    # -----------------------------------------------------
    # Frostgrave Sea
    # -----------------------------------------------------
    "whitebone_colossus": {
        "location": "whitebone_isle",
        "type": "landmark",
        "name": "The Whitebone Colossus",
        "rarity": "Rare",
        "importance": 7,
        "description": (
            "The enormous frozen skeleton of a sea creature "
            "far larger than any monster recorded by the "
            "crew."
        ),
    },
    "coldgrave_flagship": {
        "location": "frozen_wreckyard",
        "type": "wreck",
        "name": "Coldgrave's Lost Flagship",
        "rarity": "Legendary",
        "importance": 9,
        "description": (
            "A massive warship trapped upright in ancient "
            "ice, its frozen pennants still bearing the "
            "mark of Admiral Coldgrave."
        ),
    },
}


# ---------------------------------------------------------
# Priority 4 — Living World Events
# ---------------------------------------------------------

WORLD_EVENTS = {
    "merchant_convoy_season": {
        "name": "Merchant Convoy Season",
        "region_profile": "coastal",
        "duration_hours": 6,
        "importance": 5,
        "description": (
            "Merchant convoys crowd the Shattered Coast, "
            "drawing salvagers, escorts, and opportunistic pirates."
        ),
        "effect_text": (
            "Treasure and usable supplies are more common "
            "in coastal waters."
        ),
        "encounter_modifiers": {
            "supplies": 8,
            "treasure": 7,
            "quiet": -15,
        },
        "treasure_multiplier": 1.20,
        "supplies_multiplier": 1.25,
    },

    "blackwater_pirate_surge": {
        "name": "Blackwater Pirate Surge",
        "region_profile": "blackwater",
        "duration_hours": 6,
        "importance": 6,
        "description": (
            "Rival pirate crews flood Blackwater Reach after "
            "rumors spread of poorly defended naval treasure."
        ),
        "effect_text": (
            "Enemy ships and valuable drifting wreckage are "
            "more common throughout Blackwater Reach."
        ),
        "encounter_modifiers": {
            "naval": 10,
            "treasure": 5,
            "quiet": -15,
        },
        "treasure_multiplier": 1.20,
        "supplies_multiplier": 1.00,
    },

    "emerald_tempest_event": {
        "name": "The Emerald Tempest",
        "region_profile": "tempest",
        "duration_hours": 5,
        "importance": 7,
        "description": (
            "A violent storm system settles over the Emerald "
            "Tempest and drives dangerous creatures toward "
            "the surface."
        ),
        "effect_text": (
            "Storm hazards and sea monsters become more common."
        ),
        "encounter_modifiers": {
            "monster": 8,
            "hazard": 12,
            "quiet": -20,
        },
        "treasure_multiplier": 1.00,
        "supplies_multiplier": 1.00,
    },

    "devils_red_tide": {
        "name": "Devil's Red Tide",
        "region_profile": "devils_expanse",
        "duration_hours": 5,
        "importance": 8,
        "description": (
            "The waters of Devil's Expanse turn crimson as "
            "predators and hostile vessels converge around "
            "the volcanic currents."
        ),
        "effect_text": (
            "Naval threats and monsters become significantly "
            "more common in Devil's Expanse."
        ),
        "encounter_modifiers": {
            "naval": 7,
            "monster": 9,
            "hazard": 4,
            "quiet": -20,
        },
        "treasure_multiplier": 1.10,
        "supplies_multiplier": 1.00,
    },

    "frostgrave_whiteout": {
        "name": "Frostgrave Whiteout",
        "region_profile": "frostgrave",
        "duration_hours": 5,
        "importance": 7,
        "description": (
            "A vast whiteout swallows Frostgrave Sea, hiding "
            "ice fields, wrecks, and safe passages alike."
        ),
        "effect_text": (
            "Environmental hazards become more common while "
            "recoverable supplies become harder to find."
        ),
        "encounter_modifiers": {
            "hazard": 14,
            "supplies": -4,
            "quiet": -10,
        },
        "treasure_multiplier": 1.00,
        "supplies_multiplier": 0.85,
    },
}


async def _db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


# ---------------------------------------------------------
# Initialization
# ---------------------------------------------------------

async def initialize_pirate_world():

    db = await _db()

    try:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS world_regions (
            region_key TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            danger TEXT DEFAULT 'Low',
            description TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS world_locations (
            location_key TEXT PRIMARY KEY,
            region_key TEXT NOT NULL,
            name TEXT NOT NULL,
            location_type TEXT DEFAULT 'island',
            danger TEXT DEFAULT 'Low',
            terrain TEXT DEFAULT '',
            hidden INTEGER DEFAULT 0,
            discovery_weight INTEGER DEFAULT 100,
            description TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS world_discoveries (
            guild_id INTEGER NOT NULL,
            location_key TEXT NOT NULL,
            discovered_by INTEGER DEFAULT 0,
            discovered_by_name TEXT DEFAULT '',
            discovered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            visits INTEGER DEFAULT 1,
            PRIMARY KEY (guild_id, location_key)
        );

        CREATE TABLE IF NOT EXISTS world_findings (
            guild_id INTEGER NOT NULL,
            finding_key TEXT NOT NULL,
            location_key TEXT NOT NULL,
            finding_type TEXT NOT NULL,
            name TEXT NOT NULL,
            rarity TEXT DEFAULT 'Common',
            description TEXT DEFAULT '',
            discovered_by INTEGER DEFAULT 0,
            discovered_by_name TEXT DEFAULT '',
            discovered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (guild_id, finding_key)
        );

        CREATE INDEX IF NOT EXISTS idx_world_findings_guild
        ON world_findings(guild_id, discovered_at DESC);

        CREATE INDEX IF NOT EXISTS idx_world_findings_location
        ON world_findings(guild_id, location_key);

        CREATE TABLE IF NOT EXISTS island_activity_state (
            guild_id INTEGER NOT NULL,
            location_key TEXT NOT NULL,
            visits INTEGER DEFAULT 0,
            last_explored_at DATETIME,
            PRIMARY KEY (guild_id, location_key)
        );

        CREATE TABLE IF NOT EXISTS island_activity_completions (
            guild_id INTEGER NOT NULL,
            location_key TEXT NOT NULL,
            activity_key TEXT NOT NULL,
            activity_type TEXT NOT NULL,
            activity_title TEXT NOT NULL,
            completed_by INTEGER DEFAULT 0,
            completed_by_name TEXT DEFAULT '',
            completed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (
                guild_id,
                location_key,
                activity_key
            )
        );

        CREATE INDEX IF NOT EXISTS
        idx_island_activity_completions_guild
        ON island_activity_completions(
            guild_id,
            completed_at DESC
        );

        CREATE TABLE IF NOT EXISTS world_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            event_key TEXT NOT NULL,
            region_profile TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            starts_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            ends_at DATETIME NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE UNIQUE INDEX IF NOT EXISTS
        idx_world_events_active_guild
        ON world_events(guild_id)
        WHERE status = 'active';

        CREATE INDEX IF NOT EXISTS
        idx_world_events_guild
        ON world_events(
            guild_id,
            id DESC
        );

        CREATE TABLE IF NOT EXISTS world_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            event_type TEXT DEFAULT 'world',
            content TEXT NOT NULL,
            importance INTEGER DEFAULT 5,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_world_history_guild
        ON world_history(guild_id, id DESC);

        CREATE INDEX IF NOT EXISTS idx_world_discoveries_guild
        ON world_discoveries(guild_id, discovered_at DESC);
        """)

        # -------------------------------------------------
        # Priority 4 geography metadata migrations
        # -------------------------------------------------

        location_columns = await (
            await db.execute(
                "PRAGMA table_info(world_locations)"
            )
        ).fetchall()

        location_column_names = {
            row["name"]
            for row in location_columns
        }

        if "terrain" not in location_column_names:
            await db.execute("""
                ALTER TABLE world_locations
                ADD COLUMN terrain TEXT DEFAULT ''
            """)

        if "hidden" not in location_column_names:
            await db.execute("""
                ALTER TABLE world_locations
                ADD COLUMN hidden INTEGER DEFAULT 0
            """)

        if "discovery_weight" not in location_column_names:
            await db.execute("""
                ALTER TABLE world_locations
                ADD COLUMN discovery_weight INTEGER DEFAULT 100
            """)

        for key, region in REGIONS.items():

            await db.execute("""
                INSERT INTO world_regions (
                    region_key,
                    name,
                    danger,
                    description
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(region_key)
                DO UPDATE SET
                    name = excluded.name,
                    danger = excluded.danger,
                    description = excluded.description
            """, (
                key,
                region["name"],
                region["danger"],
                region["description"],
            ))

        for key, island in ISLANDS.items():

            await db.execute("""
                INSERT INTO world_locations (
                    location_key,
                    region_key,
                    name,
                    location_type,
                    danger,
                    terrain,
                    hidden,
                    discovery_weight,
                    description
                )
                VALUES (?, ?, ?, 'island', ?, ?, ?, ?, ?)
                ON CONFLICT(location_key)
                DO UPDATE SET
                    region_key = excluded.region_key,
                    name = excluded.name,
                    danger = excluded.danger,
                    terrain = excluded.terrain,
                    hidden = excluded.hidden,
                    discovery_weight = excluded.discovery_weight,
                    description = excluded.description
            """, (
                key,
                island["region"],
                island["name"],
                island["danger"],
                island.get("terrain", ""),
                1 if island.get("hidden") else 0,
                max(
                    1,
                    int(
                        island.get(
                            "discovery_weight",
                            100
                        )
                    )
                ),
                island["description"],
            ))

        await db.commit()

    finally:
        await db.close()


# ---------------------------------------------------------
# Living World Events
# ---------------------------------------------------------

async def _expire_world_events_unlocked(
    db,
    guild_id
):
    """
    Expire stale active events for one guild.

    Returns the rows whose active -> expired transition
    was owned by this call.
    """

    rows = await (
        await db.execute(
            """
            SELECT *
            FROM world_events
            WHERE guild_id = ?
              AND status = 'active'
              AND datetime(ends_at)
                  <= datetime('now')
            ORDER BY id
            """,
            (
                guild_id,
            )
        )
    ).fetchall()

    expired = []

    for row in rows:

        cursor = await db.execute(
            """
            UPDATE world_events
            SET status = 'expired',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status = 'active'
              AND datetime(ends_at)
                  <= datetime('now')
            """,
            (
                row["id"],
            )
        )

        if cursor.rowcount != 1:
            continue

        expired.append(
            row
        )

        await db.execute(
            """
            INSERT INTO world_history (
                guild_id,
                event_type,
                content,
                importance
            )
            VALUES (?, 'world_event', ?, ?)
            """,
            (
                guild_id,
                (
                    row["name"]
                    + " ended in "
                    + row["region_profile"]
                    .replace("_", " ")
                    .title()
                    + "."
                ),
                5,
            )
        )

    return expired


async def expire_world_events(
    guild_id
):
    """
    Deterministically expire stale events.

    No scheduler is required; reads and world actions may
    safely call this before using active event state.
    """

    async with get_guild_lock(
        guild_id
    ):

        db = await _db()

        try:
            await db.execute(
                "BEGIN IMMEDIATE"
            )

            expired = (
                await _expire_world_events_unlocked(
                    db,
                    guild_id
                )
            )

            await db.commit()

            return [
                dict(row)
                for row in expired
            ]

        except Exception:
            await db.rollback()
            raise

        finally:
            await db.close()


async def get_active_world_event(
    guild_id
):
    """
    Return the guild's currently active Living World Event.

    Stale state is expired before the result is returned.
    """

    async with get_guild_lock(
        guild_id
    ):

        db = await _db()

        try:
            await db.execute(
                "BEGIN IMMEDIATE"
            )

            await _expire_world_events_unlocked(
                db,
                guild_id
            )

            row = await (
                await db.execute(
                    """
                    SELECT *
                    FROM world_events
                    WHERE guild_id = ?
                      AND status = 'active'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (
                        guild_id,
                    )
                )
            ).fetchone()

            await db.commit()

            return (
                dict(row)
                if row
                else None
            )

        except Exception:
            await db.rollback()
            raise

        finally:
            await db.close()


async def activate_world_event(
    guild_id,
    event_key,
    duration_hours=None
):
    """
    Atomically activate one Living World Event.

    Exactly one active event may exist per guild.

    Returns:
        (True, row) when this call created the event.
        (False, row) when another event is already active.
        (False, None) for an unknown event key.
    """

    event = WORLD_EVENTS.get(
        str(event_key)
    )

    if not event:
        return False, None

    duration = (
        event["duration_hours"]
        if duration_hours is None
        else duration_hours
    )

    duration = max(
        1,
        int(duration)
    )

    async with get_guild_lock(
        guild_id
    ):

        db = await _db()

        try:
            await db.execute(
                "BEGIN IMMEDIATE"
            )

            await _expire_world_events_unlocked(
                db,
                guild_id
            )

            active = await (
                await db.execute(
                    """
                    SELECT *
                    FROM world_events
                    WHERE guild_id = ?
                      AND status = 'active'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (
                        guild_id,
                    )
                )
            ).fetchone()

            if active:
                await db.commit()

                return (
                    False,
                    dict(active)
                )

            modifier = (
                "+"
                + str(duration)
                + " hours"
            )

            cursor = await db.execute(
                """
                INSERT INTO world_events (
                    guild_id,
                    event_key,
                    region_profile,
                    name,
                    description,
                    ends_at
                )
                VALUES (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    datetime(
                        'now',
                        ?
                    )
                )
                """,
                (
                    guild_id,
                    event_key,
                    event["region_profile"],
                    event["name"],
                    event["description"],
                    modifier,
                )
            )

            event_id = (
                cursor.lastrowid
            )

            row = await (
                await db.execute(
                    """
                    SELECT *
                    FROM world_events
                    WHERE id = ?
                    """,
                    (
                        event_id,
                    )
                )
            ).fetchone()

            await db.execute(
                """
                INSERT INTO world_history (
                    guild_id,
                    event_type,
                    content,
                    importance
                )
                VALUES (?, 'world_event', ?, ?)
                """,
                (
                    guild_id,
                    (
                        event["name"]
                        + " began in "
                        + event[
                            "region_profile"
                        ]
                        .replace("_", " ")
                        .title()
                        + "."
                    ),
                    int(
                        event.get(
                            "importance",
                            5
                        )
                    ),
                )
            )

            await db.commit()

            return (
                True,
                dict(row)
            )

        except Exception:
            await db.rollback()
            raise

        finally:
            await db.close()


async def end_world_event(
    guild_id
):
    """
    Explicitly end the active world event.

    Primarily useful for deterministic tests and future
    administrative/event-resolution flows.
    """

    async with get_guild_lock(
        guild_id
    ):

        db = await _db()

        try:
            await db.execute(
                "BEGIN IMMEDIATE"
            )

            await _expire_world_events_unlocked(
                db,
                guild_id
            )

            row = await (
                await db.execute(
                    """
                    SELECT *
                    FROM world_events
                    WHERE guild_id = ?
                      AND status = 'active'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (
                        guild_id,
                    )
                )
            ).fetchone()

            if not row:
                await db.commit()

                return False, None

            cursor = await db.execute(
                """
                UPDATE world_events
                SET status = 'ended',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                  AND status = 'active'
                """,
                (
                    row["id"],
                )
            )

            changed = (
                cursor.rowcount == 1
            )

            if changed:
                await db.execute(
                    """
                    INSERT INTO world_history (
                        guild_id,
                        event_type,
                        content,
                        importance
                    )
                    VALUES (
                        ?,
                        'world_event',
                        ?,
                        5
                    )
                    """,
                    (
                        guild_id,
                        (
                            row["name"]
                            + " ended."
                        ),
                    )
                )

            await db.commit()

            return (
                changed,
                dict(row)
            )

        except Exception:
            await db.rollback()
            raise

        finally:
            await db.close()


async def format_world_events(
    guild_id
):
    """
    Format the currently active Living World Event.
    """

    event = await get_active_world_event(
        guild_id
    )

    if not event:
        return (
            "**LIVING WORLD EVENTS**\n"
            "No major world event is currently active."
        )

    definition = WORLD_EVENTS.get(
        event["event_key"],
        {}
    )

    effect_text = definition.get(
        "effect_text",
        (
            "The event is changing conditions "
            "across the region."
        )
    )

    region_name = (
        event["region_profile"]
        .replace("_", " ")
        .title()
    )

    return (
        "**LIVING WORLD EVENT**\n"
        "**"
        + event["name"]
        + "**\n"
        "Region: **"
        + region_name
        + "**\n"
        + event["description"]
        + "\n\n"
        "**Current Conditions:** "
        + effect_text
        + "\n"
        "Ends (UTC): **"
        + str(event["ends_at"])
        + "**"
    )


# ---------------------------------------------------------
# History
# ---------------------------------------------------------

async def add_world_history(
    guild_id,
    content,
    event_type="world",
    importance=5
):

    db = await _db()

    try:
        await db.execute("""
            INSERT INTO world_history (
                guild_id,
                event_type,
                content,
                importance
            )
            VALUES (?, ?, ?, ?)
        """, (
            guild_id,
            event_type,
            content,
            importance,
        ))

        await db.commit()

    finally:
        await db.close()


async def get_world_history(
    guild_id,
    limit=15
):

    db = await _db()

    try:
        cursor = await db.execute("""
            SELECT
                event_type,
                content,
                created_at
            FROM world_history
            WHERE guild_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (
            guild_id,
            limit,
        ))

        return await cursor.fetchall()

    finally:
        await db.close()


# ---------------------------------------------------------
# Discoveries
# ---------------------------------------------------------

async def discover_location(
    guild_id,
    location_key,
    user_id,
    username
):

    if location_key not in ISLANDS:
        return False, "Unknown location."

    db = await _db()

    try:
        cursor = await db.execute("""
            SELECT visits
            FROM world_discoveries
            WHERE guild_id = ?
              AND location_key = ?
        """, (
            guild_id,
            location_key,
        ))

        existing = await cursor.fetchone()

        if existing:

            await db.execute("""
                UPDATE world_discoveries
                SET visits = visits + 1
                WHERE guild_id = ?
                  AND location_key = ?
            """, (
                guild_id,
                location_key,
            ))

            await db.commit()

            return False, "already_discovered"

        await db.execute("""
            INSERT INTO world_discoveries (
                guild_id,
                location_key,
                discovered_by,
                discovered_by_name
            )
            VALUES (?, ?, ?, ?)
        """, (
            guild_id,
            location_key,
            user_id,
            username,
        ))

        await db.commit()

        island = ISLANDS[location_key]

        await add_world_history(
            guild_id,
            (
                username
                + " discovered "
                + island["name"]
                + " in "
                + REGIONS[island["region"]]["name"]
                + "."
            ),
            "discovery",
            7
        )

        return True, island

    finally:
        await db.close()


async def get_discovered_locations(
    guild_id
):

    db = await _db()

    try:
        cursor = await db.execute("""
            SELECT
                location_key,
                discovered_by_name,
                discovered_at,
                visits
            FROM world_discoveries
            WHERE guild_id = ?
            ORDER BY discovered_at
        """, (
            guild_id,
        ))

        return await cursor.fetchall()

    finally:
        await db.close()


async def count_world_discoveries(
    guild_id,
    user_id=None
):
    db = await _db()

    try:

        if user_id is None:

            row = await (
                await db.execute(
                    """
                    SELECT COUNT(*)
                    FROM world_discoveries
                    WHERE guild_id = ?
                    """,
                    (
                        guild_id,
                    )
                )
            ).fetchone()

        else:

            row = await (
                await db.execute(
                    """
                    SELECT COUNT(*)
                    FROM world_discoveries
                    WHERE guild_id = ?
                      AND discovered_by = ?
                    """,
                    (
                        guild_id,
                        user_id,
                    )
                )
            ).fetchone()

        return int(row[0] or 0)

    finally:
        await db.close()


async def count_hidden_discoveries(
    guild_id,
    user_id=None
):
    db = await _db()

    try:

        if user_id is None:

            row = await (
                await db.execute(
                    """
                    SELECT COUNT(*)
                    FROM world_discoveries wd
                    JOIN world_locations wl
                      ON wl.location_key = wd.location_key
                    WHERE wd.guild_id = ?
                      AND wl.hidden = 1
                    """,
                    (
                        guild_id,
                    )
                )
            ).fetchone()

        else:

            row = await (
                await db.execute(
                    """
                    SELECT COUNT(*)
                    FROM world_discoveries wd
                    JOIN world_locations wl
                      ON wl.location_key = wd.location_key
                    WHERE wd.guild_id = ?
                      AND wd.discovered_by = ?
                      AND wl.hidden = 1
                    """,
                    (
                        guild_id,
                        user_id,
                    )
                )
            ).fetchone()

        return int(row[0] or 0)

    finally:
        await db.close()


# ---------------------------------------------------------
# World findings
# ---------------------------------------------------------

async def discover_world_finding(
    guild_id,
    finding_key,
    user_id,
    username
):
    """
    Atomically claim a unique world finding for a guild.

    Returns:
        (True, finding) when this call discovered it.
        (False, finding) when already discovered.
        (False, None) for an unknown finding.
    """

    finding = WORLD_FINDINGS.get(
        finding_key
    )

    if not finding:
        return False, None

    location_key = finding["location"]

    if location_key not in ISLANDS:
        return False, None

    db = await _db()

    try:

        cursor = await db.execute(
            """
            INSERT OR IGNORE INTO world_findings (
                guild_id,
                finding_key,
                location_key,
                finding_type,
                name,
                rarity,
                description,
                discovered_by,
                discovered_by_name
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                finding_key,
                location_key,
                finding["type"],
                finding["name"],
                finding.get(
                    "rarity",
                    "Common"
                ),
                finding["description"],
                user_id,
                username,
            )
        )

        await db.commit()

        if cursor.rowcount != 1:

            existing = await (
                await db.execute(
                    """
                    SELECT
                        finding_key,
                        location_key,
                        finding_type,
                        name,
                        rarity,
                        description,
                        discovered_by,
                        discovered_by_name,
                        discovered_at
                    FROM world_findings
                    WHERE guild_id = ?
                      AND finding_key = ?
                    """,
                    (
                        guild_id,
                        finding_key,
                    )
                )
            ).fetchone()

            return False, existing

        row = await (
            await db.execute(
                """
                SELECT
                    finding_key,
                    location_key,
                    finding_type,
                    name,
                    rarity,
                    description,
                    discovered_by,
                    discovered_by_name,
                    discovered_at
                FROM world_findings
                WHERE guild_id = ?
                  AND finding_key = ?
                """,
                (
                    guild_id,
                    finding_key,
                )
            )
        ).fetchone()

        return True, row

    finally:
        await db.close()


async def get_world_findings(
    guild_id,
    location_key=None
):

    db = await _db()

    try:

        if location_key:

            cursor = await db.execute(
                """
                SELECT
                    finding_key,
                    location_key,
                    finding_type,
                    name,
                    rarity,
                    description,
                    discovered_by,
                    discovered_by_name,
                    discovered_at
                FROM world_findings
                WHERE guild_id = ?
                  AND location_key = ?
                ORDER BY discovered_at,
                         finding_key
                """,
                (
                    guild_id,
                    location_key,
                )
            )

        else:

            cursor = await db.execute(
                """
                SELECT
                    finding_key,
                    location_key,
                    finding_type,
                    name,
                    rarity,
                    description,
                    discovered_by,
                    discovered_by_name,
                    discovered_at
                FROM world_findings
                WHERE guild_id = ?
                ORDER BY discovered_at,
                         finding_key
                """,
                (
                    guild_id,
                )
            )

        return await cursor.fetchall()

    finally:
        await db.close()


async def count_world_findings(
    guild_id,
    user_id=None
):
    db = await _db()

    try:

        if user_id is None:

            row = await (
                await db.execute(
                    """
                    SELECT COUNT(*)
                    FROM world_findings
                    WHERE guild_id = ?
                    """,
                    (
                        guild_id,
                    )
                )
            ).fetchone()

        else:

            row = await (
                await db.execute(
                    """
                    SELECT COUNT(*)
                    FROM world_findings
                    WHERE guild_id = ?
                      AND discovered_by = ?
                    """,
                    (
                        guild_id,
                        user_id,
                    )
                )
            ).fetchone()

        return int(row[0] or 0)

    finally:
        await db.close()


async def format_world_findings(
    guild_id
):

    rows = await get_world_findings(
        guild_id
    )

    if not rows:
        return (
            "**WORLD FINDINGS**\n"
            "The crew hasn't uncovered any "
            "special world findings yet."
        )

    lines = [
        "**WORLD FINDINGS**"
    ]

    for row in rows:

        island = ISLANDS.get(
            row["location_key"]
        )

        location_name = (
            island["name"]
            if island
            else row["location_key"]
        )

        lines.append(
            "• **"
            + row["name"]
            + "** ["
            + row["rarity"]
            + " "
            + row["finding_type"].replace(
                "_",
                " "
            ).title()
            + "] — "
            + location_name
            + " • found by "
            + (
                row["discovered_by_name"]
                or "Unknown"
            )
        )

    return "\n".join(lines)[:1900]


# ---------------------------------------------------------
# Exploration
# ---------------------------------------------------------

async def explore_random_island(
    guild_id,
    user_id,
    username
):
    """
    Scout the surrounding seas.

    Exploration represents scouting and charting rather
    than physically moving the Living Ship.

    New islands are discovered gradually. Treasure,
    supplies, island lore, and island-specific encounters
    belong to physical island exploration after arrival.
    """

    discovered = await get_discovered_locations(
        guild_id
    )

    discovered_keys = {
        row["location_key"]
        for row in discovered
    }

    undiscovered = [
        key
        for key in ISLANDS
        if key not in discovered_keys
    ]

    # -----------------------------------------------------
    # Discovery roll
    #
    # Only 25% of scouting attempts reveal a new island.
    # This prevents the entire world from being discovered
    # after only a handful of explore commands.
    # -----------------------------------------------------

    discover_new = (
        bool(undiscovered)
        and random.randint(1, 100) <= 25
    )

    if discover_new:

        location_key = random.choices(
            undiscovered,
            weights=[
                max(
                    1,
                    int(
                        ISLANDS[key].get(
                            "discovery_weight",
                            100
                        )
                    )
                )
                for key in undiscovered
            ],
            k=1
        )[0]

        is_new, _ = await discover_location(
            guild_id,
            location_key,
            user_id,
            username
        )

    else:

        is_new = False

        # Scout somewhere already charted. Blacktooth Cove
        # acts as the crew's starting known waters before
        # the first true discovery has been made.
        known_keys = list(
            discovered_keys
        )

        if not known_keys:
            known_keys = [
                "blacktooth_cove"
            ]

        location_key = random.choice(
            known_keys
        )

    island = ISLANDS[
        location_key
    ]

    region = REGIONS[
        island["region"]
    ]

    # -----------------------------------------------------
    # Scouting encounters
    #
    # Scouting happens from the ship at sea. Physical
    # island rewards are intentionally excluded here.
    # -----------------------------------------------------

    encounter_profile = region.get(
        "encounter_profile",
        "coastal"
    )

    base_encounter_weights = (
        REGION_ENCOUNTER_PROFILES.get(
            encounter_profile,
            REGION_ENCOUNTER_PROFILES["coastal"]
        )
    )

    # Always work from a copy. Living World Events must never
    # mutate the global regional profile definitions.
    encounter_weights = dict(
        base_encounter_weights
    )

    active_world_event = (
        await get_active_world_event(
            guild_id
        )
    )

    applied_world_event = None

    if (
        active_world_event
        and active_world_event[
            "region_profile"
        ] == encounter_profile
    ):
        definition = WORLD_EVENTS.get(
            active_world_event[
                "event_key"
            ]
        )

        if definition:

            for kind, modifier in (
                definition.get(
                    "encounter_modifiers",
                    {}
                ).items()
            ):
                if kind not in encounter_weights:
                    continue

                encounter_weights[kind] = max(
                    0,
                    int(
                        encounter_weights[kind]
                    )
                    + int(modifier)
                )

            # Protect random.choices from malformed future
            # configuration while keeping the current catalog
            # fully deterministic.
            if sum(
                encounter_weights.values()
            ) <= 0:
                encounter_weights = dict(
                    base_encounter_weights
                )
            else:
                applied_world_event = {
                    "id": active_world_event["id"],
                    "event_key": (
                        active_world_event[
                            "event_key"
                        ]
                    ),
                    "name": (
                        active_world_event[
                            "name"
                        ]
                    ),
                    "region_profile": (
                        active_world_event[
                            "region_profile"
                        ]
                    ),
                    "description": (
                        active_world_event[
                            "description"
                        ]
                    ),
                    "effect_text": (
                        definition.get(
                            "effect_text",
                            ""
                        )
                    ),
                    "encounter_modifiers": dict(
                        definition.get(
                            "encounter_modifiers",
                            {}
                        )
                    ),
                    "treasure_multiplier": float(
                        definition.get(
                            "treasure_multiplier",
                            1.0
                        )
                    ),
                    "supplies_multiplier": float(
                        definition.get(
                            "supplies_multiplier",
                            1.0
                        )
                    ),
                    "ends_at": (
                        active_world_event[
                            "ends_at"
                        ]
                    ),
                }

    encounter_types = (
        "naval",
        "monster",
        "hazard",
        "supplies",
        "treasure",
        "quiet",
    )

    encounter_type = random.choices(
        encounter_types,
        weights=tuple(
            encounter_weights[kind]
            for kind in encounter_types
        ),
        k=1
    )[0]

    encounter_text = (
        REGION_ENCOUNTER_TEXT.get(
            encounter_profile,
            REGION_ENCOUNTER_TEXT["coastal"]
        )
    )

    if encounter_type == "naval":

        encounter = encounter_text["naval"]

    elif encounter_type == "monster":

        encounter = encounter_text["monster"]

    elif encounter_type == "hazard":

        hazard = random.choice(
            REGION_HAZARDS.get(
                encounter_profile,
                REGION_HAZARDS["coastal"]
            )
        )

        encounter = hazard["text"]

    elif encounter_type in (
        "supplies",
        "treasure",
    ):

        resource_text = REGION_RESOURCE_TEXT.get(
            encounter_profile,
            REGION_RESOURCE_TEXT["coastal"]
        )

        encounter = resource_text[
            encounter_type
        ]

    else:

        if is_new:
            encounter = (
                "The crew charted **"
                + island["name"]
                + "** from offshore and marked it "
                "on the ship's maps. "
                + encounter_text["quiet"]
            )
        else:
            encounter = encounter_text["quiet"]

    return {
        "new": is_new,
        "key": location_key,
        "name": island["name"],
        "region": region["name"],
        "encounter_profile": encounter_profile,
        "encounter_weights": dict(
            encounter_weights
        ),
        "world_event": applied_world_event,
        "danger": island["danger"],
        "terrain": island.get("terrain", ""),
        "hidden": bool(island.get("hidden", False)),
        "description": island["description"],
        "finding_key": next(
            (
                key
                for key, finding
                in WORLD_FINDINGS.items()
                if finding["location"]
                == location_key
            ),
            None
        ),
        "encounter_type": encounter_type,
        "encounter": encounter,
        "hazard": (
            hazard
            if encounter_type == "hazard"
            else None
        ),
    }


# ---------------------------------------------------------
# Island activity completion
# ---------------------------------------------------------

async def get_completed_island_activities(
    guild_id,
    location_key=None
):
    db = await _db()

    try:

        if location_key:

            cursor = await db.execute(
                """
                SELECT
                    location_key,
                    activity_key,
                    activity_type,
                    activity_title,
                    completed_by,
                    completed_by_name,
                    completed_at
                FROM island_activity_completions
                WHERE guild_id = ?
                  AND location_key = ?
                ORDER BY completed_at,
                         activity_key
                """,
                (
                    guild_id,
                    location_key,
                )
            )

        else:

            cursor = await db.execute(
                """
                SELECT
                    location_key,
                    activity_key,
                    activity_type,
                    activity_title,
                    completed_by,
                    completed_by_name,
                    completed_at
                FROM island_activity_completions
                WHERE guild_id = ?
                ORDER BY completed_at,
                         location_key,
                         activity_key
                """,
                (
                    guild_id,
                )
            )

        return await cursor.fetchall()

    finally:
        await db.close()


async def complete_island_activity(
    guild_id,
    location_key,
    activity_key,
    activity_type,
    activity_title,
    user_id,
    username
):
    """
    Atomically record one persistent island activity.

    Returns:
        (True, row) for the single successful claimant.
        (False, row) when already completed.
    """

    db = await _db()

    try:

        cursor = await db.execute(
            """
            INSERT OR IGNORE INTO
            island_activity_completions (
                guild_id,
                location_key,
                activity_key,
                activity_type,
                activity_title,
                completed_by,
                completed_by_name
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                location_key,
                activity_key,
                activity_type,
                activity_title,
                user_id,
                username,
            )
        )

        await db.commit()

        row = await (
            await db.execute(
                """
                SELECT
                    location_key,
                    activity_key,
                    activity_type,
                    activity_title,
                    completed_by,
                    completed_by_name,
                    completed_at
                FROM island_activity_completions
                WHERE guild_id = ?
                  AND location_key = ?
                  AND activity_key = ?
                """,
                (
                    guild_id,
                    location_key,
                    activity_key,
                )
            )
        ).fetchone()

        return (
            cursor.rowcount == 1,
            row
        )

    finally:
        await db.close()


# ---------------------------------------------------------
# Island revisit progression
# ---------------------------------------------------------

async def get_island_activity_state(
    guild_id,
    location_key
):
    db = await _db()

    try:
        row = await (
            await db.execute(
                """
                SELECT
                    visits,
                    last_explored_at
                FROM island_activity_state
                WHERE guild_id = ?
                  AND location_key = ?
                """,
                (
                    guild_id,
                    location_key,
                )
            )
        ).fetchone()

        if not row:
            return {
                "visits": 0,
                "last_explored_at": None,
            }

        return {
            "visits": int(row["visits"]),
            "last_explored_at": row["last_explored_at"],
        }

    finally:
        await db.close()


async def record_island_visit(
    guild_id,
    location_key,
    cooldown_seconds=30 * 60
):
    """
    Atomically claim one physical island exploration.

    Exactly one caller may advance the visit counter during
    a cooldown window. Race losers receive the current state
    without incrementing visits or resetting the cooldown.
    """

    cooldown_seconds = max(
        0,
        int(cooldown_seconds)
    )

    db = await _db()

    try:
        await db.execute(
            "BEGIN IMMEDIATE"
        )

        row = await (
            await db.execute(
                """
                SELECT
                    visits,
                    last_explored_at,
                    CAST(
                        (
                            julianday('now')
                            - julianday(last_explored_at)
                        ) * 86400
                        AS INTEGER
                    ) AS elapsed_seconds
                FROM island_activity_state
                WHERE guild_id = ?
                  AND location_key = ?
                """,
                (
                    guild_id,
                    location_key,
                )
            )
        ).fetchone()

        if row:
            elapsed = (
                int(row["elapsed_seconds"])
                if row["elapsed_seconds"] is not None
                else cooldown_seconds
            )

            if elapsed < cooldown_seconds:
                await db.rollback()

                return {
                    "claimed": False,
                    "visits": int(row["visits"]),
                    "last_explored_at": row[
                        "last_explored_at"
                    ],
                    "remaining_seconds": max(
                        1,
                        cooldown_seconds - elapsed
                    ),
                }

            visits = int(row["visits"]) + 1

            await db.execute(
                """
                UPDATE island_activity_state
                SET visits = ?,
                    last_explored_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
                  AND location_key = ?
                """,
                (
                    visits,
                    guild_id,
                    location_key,
                )
            )

        else:
            visits = 1

            await db.execute(
                """
                INSERT INTO island_activity_state (
                    guild_id,
                    location_key,
                    visits,
                    last_explored_at
                )
                VALUES (?, ?, 1, CURRENT_TIMESTAMP)
                """,
                (
                    guild_id,
                    location_key,
                )
            )

        await db.commit()

        return {
            "claimed": True,
            "visits": visits,
            "last_explored_at": None,
            "remaining_seconds": 0,
        }

    except Exception:
        try:
            await db.rollback()
        except Exception:
            pass

        raise

    finally:
        await db.close()


# ---------------------------------------------------------
# Formatting
# ---------------------------------------------------------

async def format_world(
    guild_id
):

    discoveries = await get_discovered_locations(
        guild_id
    )

    discovered_keys = {
        row["location_key"]
        for row in discoveries
    }

    visible_island_keys = {
        island_key
        for island_key, island in ISLANDS.items()
        if (
            not island.get("hidden", False)
            or island_key in discovered_keys
        )
    }

    visible_discoveries = {
        island_key
        for island_key in discovered_keys
        if island_key in visible_island_keys
    }

    return (
        "**PIRATE WORLD**\\n"
        "Known Regions: **"
        + str(len(REGIONS))
        + "**\\n"
        "Known Islands: **"
        + str(len(visible_island_keys))
        + "**\\n"
        "Crew Discoveries: **"
        + str(len(visible_discoveries))
        + "/"
        + str(len(visible_island_keys))
        + "**\\n\\n"
        "Use `!cutlass world map` to view the seas."
    )

async def format_world_map(
    guild_id
):

    discoveries = await get_discovered_locations(
        guild_id
    )

    discovered_keys = {
        row["location_key"]
        for row in discoveries
    }

    lines = [
        "**PIRATE WORLD MAP**"
    ]

    for region_key, region in REGIONS.items():

        lines.append(
            "\\n**"
            + region["name"]
            + "**"
            + " — "
            + region["danger"]
        )

        for island_key, island in ISLANDS.items():

            if island["region"] != region_key:
                continue

            is_discovered = (
                island_key in discovered_keys
            )

            is_hidden = bool(
                island.get("hidden", False)
            )

            # Hidden locations do not occupy a visible map
            # slot until the crew actually discovers them.
            if is_hidden and not is_discovered:
                continue

            marker = (
                "✓"
                if is_discovered
                else "?"
            )

            lines.append(
                marker
                + " "
                + (
                    island["name"]
                    if is_discovered
                    else "Undiscovered Island"
                )
            )

    return "\\n".join(lines)[:1900]

async def format_discoveries(
    guild_id
):

    rows = await get_discovered_locations(
        guild_id
    )

    if not rows:
        return (
            "**WORLD DISCOVERIES**\n"
            "The crew hasn't discovered any islands yet."
        )

    lines = [
        "**WORLD DISCOVERIES**"
    ]

    for row in rows:

        island = ISLANDS.get(
            row["location_key"]
        )

        if not island:
            continue

        lines.append(
            "• "
            + island["name"]
            + " — discovered by "
            + (
                row["discovered_by_name"]
                or "Unknown"
            )
            + " • Visits: "
            + str(row["visits"])
        )

    return "\n".join(lines)[:1900]
