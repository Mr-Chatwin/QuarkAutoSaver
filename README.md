# Quark Auto Saver

An automated tool to search, save, and rename Quark Drive resources following Emby standard naming conventions.

## Features
- **Telegram Bot**: Send `/search Movie Name` to easily find and save resources.
- **FastAPI Backend**: Ready for Web UI integration.
- **PanSou Integration**: Reliable search for Quark Drive links.
- **TMDB Standard**: Auto-recognizes movie/TV year and type for standard Emby folder structures.
- **Auto Rename**: Automatically renames downloaded EP files to `S01E01` format based on regex.

## Setup

1. Clone or copy this directory.
2. Copy `.env.example` to `.env` and fill in your details:
   - `TMDB_API_KEY`: Get from TMDB.
   - `QUARK_COOKIE`: Grab your cookie from the Quark Web Drive network requests.
   - `TG_BOT_TOKEN`: Get from @BotFather on Telegram.
3. Run with Docker Compose:
   ```bash
   docker-compose up -d
   ```

## Usage
Start a chat with your Telegram Bot and send:
`/search 绝命毒师`

The bot will query TMDB, find Quark links, and present inline buttons for you to save them directly to your Quark Drive perfectly organized for Emby!
