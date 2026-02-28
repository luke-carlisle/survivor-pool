# Fundas Friends Survivor 50 — Deployment Guide
## From zero to live in ~20 minutes

---

## What you have in this folder

```
survivor-pool/
├── index.html          ← Your page (goes to Netlify)
├── api.py              ← The API server (goes to Render)
├── scraper.py          ← Nightly data scraper (goes to Render)
├── survivor_data.json  ← Current episode data (goes to Render)
├── render.yaml         ← Render deployment config
├── requirements.txt    ← Python dependencies (none needed)
└── DEPLOY.md           ← This file
```

---

## STEP 1 — Put the code on GitHub (5 min)

GitHub stores your code so Render can access it.

1. Go to **github.com** and sign in
2. Click the **"+"** button (top right) → **"New repository"**
3. Name it: `survivor-pool`
4. Leave everything else as default
5. Click **"Create repository"**
6. On the next screen, click **"uploading an existing file"**
7. Drag ALL the files from your `survivor-pool` folder into the upload area
8. Scroll down, click **"Commit changes"**

✅ Your code is now on GitHub.

---

## STEP 2 — Deploy the API to Render (8 min)

1. Go to **render.com** and sign in
2. Click **"New +"** → **"Web Service"**
3. Click **"Connect a repository"** → select your `survivor-pool` repo
4. Fill in the form:
   - **Name:** `survivor-pool-api`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python api.py`
   - **Instance Type:** `Free`
5. Click **"Create Web Service"**
6. Wait ~2 minutes for it to build and deploy
7. **Copy the URL** it gives you — looks like `https://survivor-pool-api.onrender.com`

✅ Your API is live. Test it by visiting `https://your-url.onrender.com/data` — you should see JSON.

---

## STEP 3 — Add the Render URL to your HTML (2 min)

1. Open `index.html` in any text editor (TextEdit on Mac works fine)
2. Find this line (near the bottom, in the `<script>` section):
   ```
   var API_URL = 'YOUR_RENDER_API_URL/data';
   ```
3. Replace `YOUR_RENDER_API_URL` with your actual Render URL, e.g.:
   ```
   var API_URL = 'https://survivor-pool-api.onrender.com/data';
   ```
4. Save the file

---

## STEP 4 — Set up the nightly scraper on Render (3 min)

1. In Render, click **"New +"** → **"Cron Job"**
2. Connect the same `survivor-pool` repository
3. Fill in:
   - **Name:** `survivor-scraper`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Schedule:** `0 2 * * *` *(runs 2am UTC = 10pm EST, after Survivor airs)*
   - **Start Command:** `python scraper.py`
4. Click **"Create Cron Job"**

✅ The scraper will now run automatically every Wednesday night.

---

## STEP 5 — Deploy to Netlify (3 min)

1. Go to **app.netlify.com/drop**
2. Drag your updated `index.html` onto the page
3. Copy the URL it gives you (e.g. `whimsical-sundae-abc123.netlify.app`)
4. Share that URL with your friends! 🎉

---

## Updating after each episode

### Automatic (ideal)
The scraper runs every night at 2am UTC. If the Survivor wiki has been updated, your page updates automatically. Nothing to do.

### Manual override (if scraper misses something)
1. Open `scraper.py` in a text editor
2. Find `USE_MANUAL_OVERRIDE = False` and change it to `True`
3. Fill in the `MANUAL_DATA` section with the correct info
4. Upload the updated `scraper.py` to GitHub (drag and drop, same as Step 1)
5. In Render, find your cron job and click **"Trigger Run"**
6. Your page updates within seconds

---

## Keeping Render awake (optional)

Render's free tier "sleeps" after 15 minutes of no traffic.
The first load after sleeping takes ~20-30 seconds.

To prevent this, use a free uptime service:
1. Go to **uptimerobot.com** (free account)
2. Add a new monitor: HTTP, your Render URL (`/health`), every 5 minutes
3. Done — Render stays awake.

---

## Troubleshooting

**Page shows "Live data unavailable"**
→ Your Render API might be sleeping. Visit the Render URL directly first to wake it up, then refresh your page.

**Scraper ran but data looks wrong**
→ Set `USE_MANUAL_OVERRIDE = True` in scraper.py and fill in correct data manually.

**Want to update the page design?**
→ Edit `index.html`, then drag the new version onto Netlify Drop again. Takes 30 seconds.
