# Gaming Portal

A self-hosted web portal for tabletop RPG groups — campaign wikis, session notes, and a Discord recording bot that transcribes and summarizes sessions automatically.

## Features

- **Campaign wiki** — per-campaign wiki with categories, Markdown editing, status workflow (Draft → Active → Completed → Archived), and full-text search
- **Discord OAuth** — staff access controlled by Discord user ID allowlist
- **Notion sync** — import characters, locations, factions, and other content from Notion databases
- **Lasombra** — Discord bot that joins voice, records per-user audio, transcribes locally with [faster-whisper](https://github.com/SYSTRAN/faster-whisper), summarizes with Claude, and posts session notes directly to the wiki

## Stack

| Layer | Tech |
|---|---|
| Web app | Python / Flask, SQLite (dev) / Turso (prod) |
| Hosting | Google Cloud Run |
| Bot | discord.py + discord-ext-voice-recv |
| Transcription | faster-whisper (local, no API cost) |
| Summarization | Anthropic Claude |

## Getting Started

### Portal (local dev)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in values
python run.py
```

### Lasombra bot + management UI (Docker)

Requires Docker and Docker Compose.

```bash
cp discord_bot/.env.example discord_bot/.env   # fill in values
cp bot_ui/.env.example bot_ui/.env             # fill in values
docker compose up --build -d
```

Management UI available at **http://localhost:3000**.

First run will download the Whisper model (~1.5 GB) automatically.

### Database migration

If upgrading an existing install, add the Sessions wiki category to all campaigns:

```bash
python scripts/add_sessions_category.py
```

## Configuration

### Portal `.env`

| Variable | Description |
|---|---|
| `SECRET_KEY` | Flask secret key |
| `DATABASE_URL` | Turso `libsql://` URL (omit for local SQLite) |
| `TURSO_AUTH_TOKEN` | Turso auth token |
| `DISCORD_CLIENT_ID` | Discord OAuth2 client ID |
| `DISCORD_CLIENT_SECRET` | Discord OAuth2 client secret |
| `ALLOWED_DISCORD_IDS` | Comma-separated Discord user IDs with staff access |

### Bot `discord_bot/.env`

| Variable | Description |
|---|---|
| `DISCORD_BOT_TOKEN` | Bot token from Discord developer portal |
| `DISCORD_GUILD_IDS` | Comma-separated server IDs for instant command sync |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude summarization |
| `DATABASE_URL` | Same Turso URL as the portal |
| `TURSO_AUTH_TOKEN` | Same Turso token as the portal |
| `PORTAL_URL` | Public URL of your portal (for wiki links) |
| `WHISPER_MODEL` | `tiny` / `base` / `small` / `medium` / `large-v3` (default: `medium`) |

## Bot Usage

| Command | Description |
|---|---|
| `/record start campaign:<slug>` | Join your voice channel and start recording |
| `/record stop` | Stop recording; transcribe, summarize, and post to wiki |
| `/record status` | Show elapsed time and captured speakers |
| `/record campaigns` | List available campaign slugs |

## Disclaimer

Audio recording must comply with applicable laws in your jurisdiction. All participants in a recorded session should be informed that recording is taking place. This software is provided for personal, private gaming group use. The authors are not responsible for misuse.

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
