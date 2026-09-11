# Captain Cutlass

Captain Cutlass is a Discord bot built around a shared Living Ship, pirate-world exploration, crew work, combat, history, and conversation.

This repository is container-first. The provided `Dockerfile` and `docker-compose.yml` build the app, install dependencies, compile the Python sources, keep persistent data in `/app/data`, and use OpenAI by default.

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
