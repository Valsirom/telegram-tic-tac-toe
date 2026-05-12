# Telegram Tic-Tac-Toe Bot

## Project path

`C:\Users\Grigoriy\telegram_tic_tac_toe_bot`

## How to run

PowerShell:

```powershell
cd C:\Users\Grigoriy\telegram_tic_tac_toe_bot
$env:TELEGRAM_BOT_TOKEN="ВАШ_ТОКЕН"
python bot.py
```

To enable Telegram Mini App button, also set:

```powershell
$env:TELEGRAM_WEBAPP_URL="https://YOUR_HTTPS_WEBAPP_URL"
```

The `python` command is configured in the user's PowerShell profile as an alias to Python 3.10:

`C:\Users\Grigoriy\AppData\Local\Programs\Python\Python310\python.exe`

If the alias does not work, use:

```powershell
py -3.10 bot.py
```

## Dependencies

Install dependencies with:

```powershell
python -m pip install -r requirements.txt
```

or:

```powershell
py -3.10 -m pip install -r requirements.txt
```

The main dependency is `python-telegram-bot`.

## Main files

- `bot.py` — main Telegram bot code
- `webapp/index.html` — Telegram Mini App frontend
- `webapp/config.js` — Mini App API URL config for GitHub Pages
- `docs/index.html` — GitHub Pages copy of Mini App
- `docs/config.js` — GitHub Pages copy of Mini App config
- `requirements.txt` — Python dependencies
- `Procfile` — Koyeb/Procfile web start command
- `runtime.txt` — Python runtime hint
- `supabase_schema.sql` — Supabase table setup
- `DEPLOY.md` — detailed deploy guide for Koyeb + GitHub Pages + Supabase
- `stats.json` — persistent user statistics
- `AGENTS.md` — project memory/instructions for future assistant sessions

## Current bot features

- Telegram tic-tac-toe game.
- Inline keyboard game board.
- Telegram Mini App:
  - static frontend in `webapp/index.html`
  - opens from bot button `Открыть приложение`
  - requires HTTPS URL in `TELEGRAM_WEBAPP_URL`
  - command `/app` sends Mini App open button
  - supports game with bot and local game with friend on one device
  - in Mini App the game starts only after pressing `Новая игра`
  - Mini App bot moves are delayed by `botMoveDelay`
  - Mini App can be hosted on GitHub Pages and configured through `webapp/config.js`
- Emojis:
  - `X` is displayed as `❎`
  - `O` is displayed as `⭕`
- Game with bot:
  - user can choose `❎`, `⭕`, or random side
  - bot uses minimax
  - bot sometimes makes a weaker move
  - weakness chance is controlled by `BOT_MISTAKE_CHANCE`
  - bot moves are delayed by `BOT_MOVE_DELAY_SECONDS`
- Game with another user:
  - user clicks `Играть с другом`
  - bot puts user into matchmaking queue
  - when another user clicks `Играть с другом`, bot pairs them randomly
  - sides are assigned randomly
  - the board is updated for both players
  - users can move only on their turn
- Statistics:
  - command `/stats`
  - stats button in menus
  - stats persist in `stats.json` locally or Supabase when configured
  - stats are split into:
    - game with bot (`bot`)
    - game with friend (`pvp`)
  - old flat stats format is migrated automatically into the bot stats section
- Deployment architecture:
  - Koyeb runs `uvicorn bot:app --host 0.0.0.0 --port $PORT`
  - Koyeb serves Telegram webhook at `/webhook`
  - Koyeb serves stats API at `/api/stats/{user_id}`
  - GitHub Pages serves the Mini App from `docs/`
  - Supabase stores shared stats in `public.user_stats`

## Notes

- The bot token must not be committed or written into project files.
- The token is provided via environment variable `TELEGRAM_BOT_TOKEN`.
- Supabase service role key must only be stored as a backend secret, never in GitHub Pages.
- If PowerShell cannot load the profile, check execution policy. It was set for the current user to `RemoteSigned`.
- If `python` points to `C:\WINDOWS\system32\python.exe`, that file was found to be empty/broken. Prefer `python` alias or `py -3.10`.

## Verification

Use this to check syntax:

```powershell
py -3.10 -m py_compile bot.py
```
