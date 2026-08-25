# Captain Cutlass Changelog
## August 24, 2026

### Major Architecture Changes

Captain Cutlass underwent a major modularization pass.

Command handling has been moved out of the monolithic `bot.py` implementation and into dedicated modules under:

`cutlass/commands/`

The central `handle_commands()` function is now primarily a command router rather than containing individual command implementations.

### Pirate World

Added and expanded the persistent Pirate World system.

Features include:

- Persistent world regions and islands
- Island discovery
- World map
- World discovery history
- Exploration system
- Island-specific activities
- Treasure discoveries
- Supply discoveries
- Island lore
- Special encounters

Commands include:

- `!cutlass world`
- `!cutlass world map`
- `!cutlass world locations`
- `!cutlass world history`
- `!cutlass explore`
- `!cutlass island`
- `!cutlass island explore`

### Living Ship Integration

The Pirate World is integrated with the server's persistent Living Ship.

Exploration and combat can affect:

- Hull
- Supplies
- Treasury
- XP
- Ship level
- Ship history

The active ship remains persistent across the server.

### Naval Combat

Added persistent naval combat.

Features include:

- Enemy ships
- Enemy captains
- Difficulty levels
- Hull damage
- Counterattacks
- Defense
- Boarding support
- Fleeing
- Rewards
- Ship XP
- Ship history entries

### Sea Monsters

Added persistent sea-monster encounters.

Implemented encounters include:

- The Kraken
- The Leviathan

Monster combat directly damages the Living Ship and prevents incompatible activities while an encounter is active.

### Boss System

Added the foundation for legendary boss encounters.

Features include:

- Persistent boss state
- Boss attack
- Boss defense
- Ship damage
- Rewards
- Ship XP
- Captain's Log integration

### Encounter Locking

World systems now prevent conflicting encounters.

Examples:

- Cannot explore during naval combat
- Cannot begin naval combat while fighting a sea monster
- Cannot begin certain encounters with a disabled ship
- Island encounters respect active combat state

### Modular Command Architecture

Command systems were separated into dedicated modules, including:

- Help
- Crew
- Lore
- Chronicle
- Welcome / Returning Crewmates
- Treasure
- Captain
- Admin
- Parrot
- Ship
- Pirate World
- Exploration
- Islands
- Naval Battles
- Sea Monsters
- Bosses

The command router now dispatches requests to these modules instead of implementing the commands directly.

### Captain Commands

Moved Captain identity/state functionality into its own module.

Includes:

- `!cutlass creator`
- `!cutlass mood`

### Administrative Commands

Moved Captain/server behavior controls into a dedicated administrative module.

Includes:

- `!cutlass quiet on/off`
- `!cutlass mood <mood>`
- `!cutlass event on/off`

### Welcome System

Completed modularization of:

- Welcome status
- Welcome enable/disable
- Welcome channel configuration
- Test welcomes
- Returning crewmate status
- Returning crewmate enable/disable
- Returning absence threshold

### Crew System

Modularized crew/profile functionality including:

- Profiles
- Relationships
- Memories
- Birthdays
- Crew statistics
- Doubloons
- Achievements
- Leaderboards
- Forget-me functionality

### Lore and Chronicle Systems

Separated lore and chronicle functionality from the primary bot runtime.

Existing Captain lore, server lore, canon, journal, timeline, quotes, and historical systems remain persistent.

### Treasure Hunts

Treasure hunt command handling was moved into its own module while preserving passive answer detection.

Treasure hunts continue to support:

- Admin-created hunts
- Clues
- Answers
- Doubloon rewards
- Achievements
- Relationship events
- Timeline entries
- Captain's Log entries

### Conversation Fixes

Fixed an issue preventing Captain Cutlass from responding correctly to direct Discord mentions.

Normal conversation and direct mentions now continue through the conversational AI path instead of being incorrectly consumed by the command router.

### Database / Initialization Fixes

Fixed initialization and persistence issues encountered while adding the new world systems, including missing naval battle table initialization.

Added initialization for the new persistent world and encounter systems.

### Codebase Cleanup

`bot.py` has been reduced to approximately 5,087 lines.

`handle_commands()` has been reduced from a large command implementation to approximately 354 lines of primarily routing logic.

Old duplicate inline handlers were removed after their modular replacements were installed and compiled successfully.

### Current Status

The major command modularization pass is complete.

Next development phase:

**AI / Conversation Brain Modularization**

Future work can separate:

- Conversation context building
- Member context
- World context
- Direct-question detection
- Humor detection
- AI message analysis
- Structured brain processing
- Relationship processing
- Conversation response generation

