# Shelter - Multi-Persona Roleplay Framework (OpenClaw)

Shelter is an OpenClaw agent with:
- base identity + memory
- dynamic persona creation/loading
- per-character persistent profile and memory isolation
- Discord command + natural language persona switching
- OpenRouter-backed character research and response generation

## Updated Folder Structure
```text
shelter/
  AGENTS.md
  SOUL.md
  USER.md
  .env.example
  requirements.txt
  core/
    __init__.py
    persona_types.py
  services/
    __init__.py
    character_researcher.py
    profile_builder.py
    memory_router.py
    persona_manager.py
  runtime/
    bot.py
    memory_store.py
    openrouter_client.py
    style_engine.py
  config/
    persona.json
  examples/
    persona_index_example.json
    character_profile_example.json
    character_memory_example.json
    discord_interactions.md
  deploy/
    register_openclaw_agent.py
    systemd/shelter-bot.service
    pm2/ecosystem.config.cjs
```

## Runtime Data Layout (Persistent)
Default on VPS (via env or auto-derived from agent dir):
```text
/home/lifadmin/.openclaw/agents/shelter/
  memory/
    base_memory.json
  personas/
    index.json
    {character_slug}/
      profile.json
      memory.json
      scenes/
```

## Core Persona Flow
1. User requests a persona switch (`!persona load X` or natural language).
2. Shelter checks `personas/index.json`.
3. If profile exists, load:
   - `personas/{slug}/profile.json`
   - `personas/{slug}/memory.json`
4. If profile does not exist:
   - run researcher (`services/character_researcher.py`)
   - build normalized profile (`services/profile_builder.py`)
   - persist profile + isolated memory + index entry
5. Respond in active persona while keeping persona memory isolated.
6. On each active-persona message:
   - update only persona memory
   - write minimal base note in base memory loop (no detailed contamination)

## Persona Commands (Discord)
- `!persona list`
- `!persona load <name>`
- `!persona create <name> [canon|inspired|original] [--source <text>]`
- `!persona reset <name>`
- `!persona info <name>`
- `!persona off`

Natural language switching (DMs/channels when bot is addressable):
- `Shelter, portray Makima.`
- `Switch to Gojo.`
- `Be Lady Dimitrescu.`
- `Return to your normal self.`
- `Load the character profile for X.`

## Environment Variables
Copy `.env.example` to `.env`:

- `DISCORD_BOT_TOKEN`
- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL_PRIMARY`
- `OPENROUTER_MODEL_FALLBACKS`
- `OPENROUTER_SITE_URL`
- `OPENROUTER_APP_NAME`
- `SHELTER_DB_PATH`
- `SHELTER_LOG_PATH`
- `SHELTER_REPLY_IN_GUILDS_MENTION_ONLY`
- `SHELTER_DEFAULT_MODE`
- `SHELTER_DEFAULT_PERSONA`
- `SHELTER_AGENT_DIR` (optional; default agent path, used to locate persona storage root)
- `SHELTER_AGENT_ROOT` (optional explicit root for `/memory` + `/personas`)
- `SHELTER_PERSONA_ROOT` (optional explicit persona folder path)

## Local Setup
```bash
cd shelter
python3 -m pip install --break-system-packages -r requirements.txt
cp .env.example .env
python runtime/bot.py
```

## VPS Setup
```bash
mkdir -p ~/.openclaw/workspace-shelter
rsync -av ./ ~/.openclaw/workspace-shelter/
cd ~/.openclaw/workspace-shelter
python3 -m pip install --user --break-system-packages -r requirements.txt
cp .env.example .env
python deploy/register_openclaw_agent.py
openclaw config validate
```

## Deployment
### PM2
```bash
pm2 start deploy/pm2/ecosystem.config.cjs
pm2 save
pm2 logs shelter-bot --lines 100
```

### systemd
```bash
sudo cp deploy/systemd/shelter-bot.service /etc/systemd/system/shelter-bot.service
sudo systemctl daemon-reload
sudo systemctl enable shelter-bot
sudo systemctl start shelter-bot
sudo systemctl status shelter-bot
```

## Research + Profile Builder Notes
- Researcher outputs structured JSON and marks uncertainty in `confidence_notes`.
- Profile builder normalizes missing fields and enforces a stable schema.
- Unknown or obscure characters still receive grounded fallback profiles.

## Sample Files
- Persona index: `examples/persona_index_example.json`
- Character profile: `examples/character_profile_example.json`
- Character memory: `examples/character_memory_example.json`
- Discord usage: `examples/discord_interactions.md`

