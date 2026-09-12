# Captain Cutlass

Captain Cutlass is a Discord bot built around a shared Living Ship, pirate-world exploration, crew work, combat, history, and conversation.

This repository is container-first. The provided `Dockerfile` and `docker-compose.yml` build the app, install dependencies, compile the Python sources, keep persistent data in `/app/data`, and use OpenAI by default.

## Features

Captain Cutlass is a persistent pirate-world Discord bot. Crew members can talk with the Captain, earn Doubloons, build up a shared Living Ship, explore a growing world, fight enemies, work jobs, and leave behind a history for the server.

### Living Ship

The Living Ship is shared across the server and persists in the database. It has a name, hull, sails, supplies, morale, treasury, XP, level, upgrades, voyage history, captured ships, and recovery state.

Supported ship features include:

- Server-wide ship status with hull, supplies, morale, treasury, level, XP, location, and next milestone.
- Ship World enable/disable controls and a dedicated ship channel.
- Ship renaming.
- Treasury donations and top contributor tracking.
- Paid ship repairs through `!c repair` / `!c ship repair`.
- Passive recovery when the ship is disabled.
- Crew maintenance jobs that help restore the ship toward operational hull.
- Ship upgrades and level-gated progression.
- Voyage destinations, voyage status, and voyage starts.
- Captured ship viewing, selling, and salvaging.
- Ship history for major events.

### Pirate World And Exploration

Captain Cutlass has a persistent world map with regions, islands, discoveries, findings, and world history.

World features include:

- Known regions and discovered islands.
- Hidden locations that only appear after discovery.
- Region and island discovery tracking.
- World map, world locations, discoveries, findings, events, and history.
- Scouting with `!c explore`.
- Island inspection with `!c island` and named island lookup like `!c island blacktooth cove`.
- Island exploration with treasure, supplies, lore, monsters, and bosses.
- Revisit tracking and exploration cooldowns.
- Major discoveries recorded into world history.

Current content includes multiple regions, 14 island content entries, hidden discoveries, island activities, world findings, 8 sea monsters, 5 bosses, and 25 naval enemies.

### Combat

Combat is unified around the active encounter. Crew members can use the same core commands whether the ship is facing a naval enemy, sea monster, or boss.

Combat features include:

- `!c attack`, `!c defend`, `!c board`, and `!c flee`.
- Naval battles with enemy ships and captains.
- Sea monster encounters.
- Boss encounters with phases.
- Combat scaling tied to ship progression.
- Automatic encounter termination when the Living Ship becomes non-operational.
- Boarding and captured vessel flow for weakened naval enemies.
- Ship combat abilities:
  - Full Broadside
  - Brace for Impact
  - Emergency Repairs
  - Rally the Crew
- Combat rewards, ship XP, treasury rewards, and achievements.

### Crew Work And Jobs

Crew Work gives members a way to earn income and support the ship outside major voyages and battles. Jobs have cooldowns, risk, unlock rules, payouts, outcomes, and ship benefits.

Current jobs include:

- Dockside Hands
- Salvager
- Shipwright
- Merchant Runner
- Bounty Hunter
- Patch the Hull
- Salvage Lumber
- Dockyard Assistance
- Clear the Bilge
- Help the Shipwright
- Scavenge Repair Materials
- Emergency Repairs

Crew Work supports:

- `!c jobs` for the job board.
- `!c work` for a personal work ledger.
- `!c work <job>` to take a shift.
- Doubloon payouts.
- Ship treasury and supply bonuses.
- Maintenance jobs that restore hull during recovery.
- Job cooldowns.
- Unlocks tied to ship level, discoveries, captures, and recovery state.
- Work and repair achievements.
- Individual contribution tracking for recovery work.

### Economy, Profiles, And Achievements

Members can build up a persistent profile through play and conversation.

Crew systems include:

- Doubloon balances.
- Leaderboards.
- Crew profiles.
- Member stats.
- Achievements.
- Birthdays.
- Relationship state with the Captain.
- Memories, running jokes, and relationship events.
- `!c forgetme` for removing stored member memories.

### Conversation And Personality

Captain Cutlass can answer naturally while staying grounded in the bot's real command set and server state.

Conversation features include:

- Pirate-themed Captain Cutlass personality.
- Natural command help for questions like "what jobs are available?" or "how do I repair the ship?"
- Follow-up context for recent messages.
- Relationship and memory context.
- Creator recognition.
- Gender-neutral behavior when gender or pronouns are unknown.
- Routing that separates commands, gameplay questions, jokes, hypotheticals, and normal conversation.
- Grounding so gameplay help points to real commands instead of invented syntax.

### Parrot, Lore, And Fun

Captain Cutlass includes a persistent parrot companion and several lore/fun systems.

Fun and lore features include:

- Parrot status, mood, relationship, memories, jokes, and history.
- Parrot banter.
- Captain lore and server lore.
- Captain canon.
- Quotes and saved quotes.
- Pirate wisdom.
- Captain's Journal.
- Timeline.
- Story mode.
- Pun battle.
- Treasure clues and treasure hunts.
- Weekly chronicles.
- Captain mood.

### Admin And Server Controls

Admiralty commands let server admins configure the bot for each Discord server.

Admin features include:

- Welcome messages and welcome channel controls.
- Returner messages and returner day thresholds.
- Captain's Log channel controls.
- Manual chronicle generation.
- Ship World channel and enable/disable controls.
- Quiet mode.
- Mood and event mode controls.
- AI status command.
- Treasure hunt setup.

### AI Provider Support

Captain Cutlass uses a provider-agnostic AI gateway. OpenAI is the default, and OpenAI-compatible local endpoints are supported.

AI features include:

- OpenAI provider mode.
- Local-only mode.
- OpenAI-first or local-first fallback modes.
- Configurable model names.
- Configurable local endpoint and API key.
- Configurable timeout, retry, token, and temperature settings.
- Runtime AI status output.
- Gameplay command execution kept separate from generated text.

### Docker And Persistence

Captain Cutlass is designed to run from Docker Compose.

Deployment features include:

- Container-first setup.
- Persistent `/app/data` volume.
- Build-time Python compilation.
- `.dockerignore` to avoid copying local data, caches, and secrets.
- Optional Ollama service through the `local-ai` Compose profile.
- Environment-driven configuration through `.env`.

## Container setup

### Prerequisites

- Docker Engine
- Docker Compose v2
- A Discord bot token
- An OpenAI key
- Optional: local Ollama if you want to run the bot in local-AI mode

### 1) Create a `.env` file

Clone the repository and enter it:

```bash
git clone https://github.com/Legionjay2144/captain-cutlass.git
cd captain-cutlass
```

Create a file named `.env` in the repository root.

If you just cloned the repository, create the data directory first:

```bash
mkdir -p data
```

Recommended OpenAI setup:

```env
DISCORD_TOKEN=your_discord_bot_token
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4.1-mini
AI_PROVIDER=openai
AI_FALLBACK_PROVIDER=none
```

If you want the bot to use a local endpoint only, set:

```env
DISCORD_TOKEN=your_discord_bot_token
AI_PROVIDER=local-only
AI_FALLBACK_PROVIDER=none
LOCAL_AI_BASE_URL=http://your-local-endpoint:11434/v1
LOCAL_AI_API_KEY=local
LOCAL_AI_MODEL=your-local-model
```

If you want OpenAI with a local fallback, set:

```env
DISCORD_TOKEN=your_discord_bot_token
OPENAI_API_KEY=your_openai_api_key
AI_PROVIDER=openai-first
AI_FALLBACK_PROVIDER=local
LOCAL_AI_BASE_URL=http://your-local-endpoint:11434/v1
LOCAL_AI_API_KEY=local
LOCAL_AI_MODEL=your-local-model
```

If you want to run the local Ollama service in Compose, start it with the `local-ai` profile and set the local variables you need. The default local base URL inside the Compose network is `http://ollama:11434/v1`.

After starting the local-AI profile, pull the model once:

```bash
docker compose exec ollama ollama pull llama3.2
```

### 2) Start the container

From the repository root:

```bash
docker compose up -d --build
```

This will:

- build the image from `Dockerfile`
- install Python dependencies
- compile the app during the image build
- start the bot container
- persist runtime data under `/app/data`

If you want Ollama too, start it with:

```bash
docker compose --profile local-ai up -d --build
```

### 3) Check logs

```bash
docker compose logs -f
```

At startup the bot prints:

- the active AI provider
- fallback provider
- model names
- endpoint information
- timeout and retry settings

### 4) Stop or restart

```bash
docker compose down
docker compose restart
```

## Alternative build commands

Build the image without Compose:

```bash
docker build -t captain-cutlass:latest .
```

Run the image directly:

```bash
docker run --rm \
  --env-file .env \
  -v "$(pwd)/data:/app/data" \
  captain-cutlass:latest
```

## Data persistence

The bot stores its database and runtime files in `/app/data`.

When using Compose, the container mounts:

```yaml
- ./data:/app/data
```

If you use the direct `docker run` command, create the host data directory first:

```bash
mkdir -p data
```

## Updating the bot

Pull the latest source changes, then rebuild and restart:

```bash
git pull
docker compose up -d --build
```

## AI provider notes

The bot supports:

- OpenAI
- OpenAI-compatible local endpoints
- Ollama when the optional Compose profile is enabled

Useful environment variables:

- `AI_PROVIDER`
- `AI_FALLBACK_PROVIDER`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`
- `LOCAL_AI_BASE_URL`
- `LOCAL_AI_API_KEY`
- `LOCAL_AI_MODEL`
- `LOCAL_AI_MAX_OUTPUT_TOKENS`
- `LOCAL_AI_TEMPERATURE`

If the selected provider is unavailable, the bot can fall back to the other provider when configured.

## Runtime checks

Useful commands:

```bash
docker compose logs -f
docker compose ps
docker compose exec captain-cutlass python -c "import bot; print('ok')"
```

## Notes

- The image is built from source.
- The container does not need a separate build step after the image has been rebuilt.
- The repository includes a `.dockerignore` so build context stays small and excludes local data, caches, and secrets.

## Web dashboard

The project includes a read-only dashboard for inspecting Captain Cutlass data outside Discord. It shows:

- Per-server Living Ship stats, treasury, hull, sails, supplies, morale, voyages, and location.
- Crew personality/profile data from profiles, relationships, memories, running jokes, and relationship events.
- Doubloons, ship treasury contributions, achievements, and crew-work totals.
- World discoveries, recent world history, ship history, voyages, captured ships, and job summaries.

The dashboard uses the same Docker image as the bot and reads the SQLite database through the existing `./data:/app/data` volume. The dashboard container mounts that volume read-only.

Start the dashboard:

```bash
docker compose --profile dashboard up -d --build dashboard
```

Open it on the host:

```text
http://127.0.0.1:8787
```

The compose file binds the dashboard to localhost only:

```yaml
127.0.0.1:8787:8787
```

If you want a simple bearer/query token, add this to `.env`:

```env
DASHBOARD_TOKEN=choose-a-long-random-value
```

Then open:

```text
http://127.0.0.1:8787/?token=choose-a-long-random-value
```

Health/API checks:

```bash
curl http://127.0.0.1:8787/api/health
curl http://127.0.0.1:8787/api/overview
```

Stop the dashboard without stopping the bot:

```bash
docker compose --profile dashboard stop dashboard
```

