# Captain Cutlass

Captain Cutlass is a Discord bot built around a shared Living Ship, pirate-world exploration, crew work, combat, history, and conversation.

This repository is container-first. The provided `Dockerfile` and `docker-compose.yml` build the app, install dependencies, compile the Python sources, keep persistent data in `/app/data`, and run a local Ollama AI service for the bot by default.

## Container setup

### Prerequisites

- Docker Engine
- Docker Compose v2
- A Discord bot token
- Optional: an OpenAI key for fallback

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

Recommended local AI setup:

```env
DISCORD_TOKEN=your_discord_bot_token
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4.1-mini
AI_PROVIDER=local-first
AI_FALLBACK_PROVIDER=openai
LOCAL_AI_BASE_URL=http://ollama:11434/v1
LOCAL_AI_API_KEY=ollama
LOCAL_AI_MODEL=llama3.2
LOCAL_AI_MAX_OUTPUT_TOKENS=512
LOCAL_AI_TEMPERATURE=0.7
```

If you want OpenAI only, set:

```env
DISCORD_TOKEN=your_discord_bot_token
OPENAI_API_KEY=your_openai_api_key
AI_PROVIDER=openai-only
AI_FALLBACK_PROVIDER=none
```

If you want the bot to run against a local endpoint only, set:

```env
AI_PROVIDER=local-only
AI_FALLBACK_PROVIDER=none
LOCAL_AI_BASE_URL=http://your-local-endpoint:11434/v1
LOCAL_AI_API_KEY=local
LOCAL_AI_MODEL=your-local-model
```

The Compose file starts Ollama on the same network as the bot. The default local base URL is `http://ollama:11434/v1`.

### 2) Start the container

From the repository root:

```bash
docker compose up -d --build
```

This will:

- build the image from `Dockerfile`
- install Python dependencies
- compile the app during the image build
- start Ollama for local inference
- start the bot container
- persist runtime data under `/app/data`

After the stack is up, pull the local model once:

```bash
docker compose exec ollama ollama pull llama3.2
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
- Ollama running in the Compose stack

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
docker compose exec ollama ollama list
```

## Notes

- The image is built from source.
- The container does not need a separate build step after the image has been rebuilt.
- The repository includes a `.dockerignore` so build context stays small and excludes local data, caches, and secrets.
