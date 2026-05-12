# Deploy: Render Free + GitHub Pages + Supabase

Use this guide if Koyeb is unavailable or paid.

Architecture:

- **Render Free Web Service**: Python backend, Telegram webhook, stats API.
- **GitHub Pages**: Telegram Mini App frontend from `docs/`.
- **Supabase Free**: shared persistent statistics.

Important Render Free limitation:

- the service can sleep after inactivity;
- the first request after sleep can be slow;
- for a hobby Telegram bot this is acceptable, but not ideal for production.

## 1. Supabase

1. Open Supabase.
2. Create a project.
3. Open **SQL Editor**.
4. Run all SQL from:

```text
supabase_schema.sql
```

5. Open **Project Settings → API**.
6. Copy:

```text
Project URL
anon public key
service_role key
```

Keep `service_role key` secret.

## 2. GitHub Pages

GitHub Pages should serve the `docs/` folder.

In GitHub repository:

```text
Settings → Pages
Source: Deploy from a branch
Branch: main
Folder: /docs
```

Mini App URL:

```text
https://valsirom.github.io/telegram-tic-tac-toe/
```

## 3. Render Web Service

1. Open Render.
2. Create **New Web Service**.
3. Connect GitHub repository:

```text
Valsirom/telegram-tic-tac-toe
```

4. Runtime: Python.
5. Build command:

```bash
pip install -r requirements.txt
```

6. Start command:

```bash
uvicorn bot:app --host 0.0.0.0 --port $PORT
```

7. Choose Free instance type if available.

## 4. Render environment variables

Add these environment variables in Render:

```text
TELEGRAM_BOT_TOKEN=your_bot_token_from_BotFather
TELEGRAM_WEBAPP_URL=https://valsirom.github.io/telegram-tic-tac-toe/
SUPABASE_URL=https://YOUR_SUPABASE_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
SUPABASE_ANON_KEY=your_supabase_anon_key
PUBLIC_API_BASE_URL=https://YOUR-RENDER-APP.onrender.com
TELEGRAM_WEBHOOK_URL=https://YOUR-RENDER-APP.onrender.com/webhook
```

You will get the exact Render URL after creating the service. It usually looks like:

```text
https://your-app-name.onrender.com
```

After you know it, update:

```text
PUBLIC_API_BASE_URL
TELEGRAM_WEBHOOK_URL
```

Then redeploy.

## 5. Check Render

Open:

```text
https://YOUR-RENDER-APP.onrender.com/health
```

Expected:

```json
{"ok": true}
```

## 6. Connect GitHub Pages Mini App to Render API

Edit:

```text
docs/config.js
```

Set:

```js
window.TIC_TAC_TOE_CONFIG = {
  API_BASE_URL: "https://YOUR-RENDER-APP.onrender.com",
};
```

Commit and push:

```powershell
git add .
git commit -m "Configure Render API URL"
git push
```

GitHub Pages will update after a short delay.

## 7. BotFather

Open `@BotFather`:

```text
/mybots → your bot → Bot Settings → Menu Button
```

Set URL:

```text
https://valsirom.github.io/telegram-tic-tac-toe/
```

If BotFather asks for a domain, use:

```text
valsirom.github.io
```

## 8. Test

1. Send `/start` to your bot.
2. Send `/app`.
3. Open Mini App.
4. Play a game.
5. Check Supabase:

```text
Table Editor → public → user_stats
```

If stats appear there, synchronization works.

## 9. If Render sleeps

On the free plan, Render can sleep after inactivity.

Symptoms:

- first `/start` after a long pause may be slow;
- Mini App stats may load slowly at first;
- Telegram may retry webhook delivery.

This is a free hosting limitation.
