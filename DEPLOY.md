# Deploy: Koyeb + GitHub Pages + Supabase

This project can be deployed as:

- **Koyeb**: Python backend, Telegram bot webhook, stats API.
- **GitHub Pages**: Telegram Mini App frontend from `webapp/`.
- **Supabase**: shared persistent statistics.

## 1. Supabase setup

1. Create an account at Supabase.
2. Create a new project.
3. Open **SQL Editor**.
4. Run all SQL from `supabase_schema.sql`.
5. Open **Project Settings → API**.
6. Copy:
   - Project URL
   - `anon public` key
   - `service_role` key

Keep the `service_role` key secret. Do not put it into GitHub Pages.

## 2. GitHub repository

Create a GitHub repository for this project and upload files:

- `bot.py`
- `requirements.txt`
- `Procfile`
- `runtime.txt`
- `supabase_schema.sql`
- `webapp/index.html`
- `webapp/config.js`
- `webapp/config.example.js`
- `docs/index.html`
- `docs/config.js`
- `docs/config.example.js`
- `AGENTS.md`
- `DEPLOY.md`

Do not upload `.env` or real bot tokens.

## 3. GitHub Pages setup for Mini App

1. In the GitHub repository, open `webapp/config.js`.
2. Set your future Koyeb backend URL:

```js
window.TIC_TAC_TOE_CONFIG = {
  API_BASE_URL: "https://YOUR-KOYEB-APP.koyeb.app",
};
```

3. Commit the change.
4. Open repository **Settings → Pages**.
5. Choose deploy from branch.
6. Select the branch, for example `main`.
7. Select folder `/docs`.
8. Wait until GitHub gives you an HTTPS URL.

The Mini App URL will look like:

```text
https://YOUR_USERNAME.github.io/YOUR_REPOSITORY/
```

## 4. Koyeb setup for bot/backend

1. Create an account at Koyeb.
2. Create a new Web Service.
3. Connect the GitHub repository.
4. Use Python build.
5. Build command:

```bash
pip install -r requirements.txt
```

6. Run command:

```bash
uvicorn bot:app --host 0.0.0.0 --port $PORT
```

7. Add environment variables:

```text
TELEGRAM_BOT_TOKEN=your_bot_token_from_BotFather
TELEGRAM_WEBAPP_URL=https://YOUR_USERNAME.github.io/YOUR_REPOSITORY/
TELEGRAM_WEBHOOK_URL=https://YOUR-KOYEB-APP.koyeb.app/webhook
SUPABASE_URL=https://YOUR_SUPABASE_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
SUPABASE_ANON_KEY=your_supabase_anon_key
PUBLIC_API_BASE_URL=https://YOUR-KOYEB-APP.koyeb.app
```

`SUPABASE_SERVICE_ROLE_KEY` is secret and must only be stored on Koyeb.

8. Deploy the service.
9. Open:

```text
https://YOUR-KOYEB-APP.koyeb.app/health
```

Expected response:

```json
{"ok": true}
```

## 5. Connect Mini App to BotFather

1. Open Telegram.
2. Open `@BotFather`.
3. Use `/mybots`.
4. Choose your bot.
5. Open **Bot Settings → Menu Button**.
6. Set menu button URL to the GitHub Pages URL:

```text
https://YOUR_USERNAME.github.io/YOUR_REPOSITORY/
```

You can also open Mini App via `/app` command if `TELEGRAM_WEBAPP_URL` is set on Koyeb.

## 6. Check Telegram webhook

After Koyeb deployment, send `/start` to the bot.

If the bot does not answer:

1. Check Koyeb logs.
2. Check that `TELEGRAM_WEBHOOK_URL` is exactly:

```text
https://YOUR-KOYEB-APP.koyeb.app/webhook
```

3. Check that `TELEGRAM_BOT_TOKEN` is correct.

## 7. How statistics work

Statistics are stored in Supabase table:

```text
public.user_stats
```

The Telegram bot writes results through Koyeb backend.

The Mini App on GitHub Pages calls Koyeb API:

```text
GET  /api/stats/{user_id}
POST /api/stats/{user_id}/result
```

Koyeb backend writes those results to Supabase.

## 8. Local development

Run the bot locally with polling:

```powershell
cd C:\Users\Grigoriy\telegram_tic_tac_toe_bot
$env:TELEGRAM_BOT_TOKEN="YOUR_TOKEN"
$env:TELEGRAM_WEBAPP_URL="https://YOUR_USERNAME.github.io/YOUR_REPOSITORY/"
python bot.py
```

Run the backend locally:

```powershell
cd C:\Users\Grigoriy\telegram_tic_tac_toe_bot
$env:TELEGRAM_BOT_TOKEN="YOUR_TOKEN"
uvicorn bot:app --host 0.0.0.0 --port 8000
```

For local backend testing, open:

```text
http://localhost:8000/health
```

Telegram webhook requires a public HTTPS URL, so local webhook will not work without a tunnel.
