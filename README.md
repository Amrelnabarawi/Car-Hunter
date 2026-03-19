# 🚗 Car Hunter Deutschland

> **Automated used car finder for Germany — powered by AI, runs 24/7 for free**

An intelligent bot that searches 4 major German car marketplaces every hour, scores each listing using Claude AI, and instantly notifies you via **Telegram** and **Email** when it finds a great match.

---

## ✨ Features

- 🔍 **Searches 4 platforms** simultaneously: AutoScout24, Mobile.de, Kleinanzeigen, eBay Motors
- 🤖 **AI-powered scoring** (0–10) — evaluates TÜV, service history, accident records, seller rating
- 📍 **Location-aware** — only shows cars within 300 km of Freiburg im Breisgau
- 💳 **Financing priority** — cars with instalment options ranked first
- 💎 **Premium tier** — cars up to 10,000 € accepted if AI score ≥ 9/10
- 📱 **Instant Telegram alerts** with full car details in Arabic
- 📧 **HTML email digest** with all new listings
- 📊 **Daily summary** every evening at 20:00
- 🔄 **Runs hourly** via GitHub Actions — no laptop needed, completely free
- 💾 **Smart deduplication** — never notifies you about the same car twice

---

## 🎯 Search Criteria

| Parameter | Value |
|-----------|-------|
| 💰 Price (standard) | 4,000 – 8,000 € |
| 💎 Price (premium, score ≥ 9) | up to 10,000 € |
| 📍 Mileage | max 70,000 km |
| 📅 Year | 2016 or newer |
| 🔄 Transmission | **Automatic only** (DSG / CVT / Tiptronic) |
| 🚙 Body type | Kombi / Limousine / SUV |
| 📍 Location | Within 300 km of Freiburg im Breisgau |
| ✅ Accepted makes | Any brand except Korean & French |
| ❌ Excluded makes | Hyundai, Kia, Genesis, SsangYong, Daewoo |
| ❌ Excluded makes | Renault, Peugeot, Citroën, Dacia, DS, Alpine |

---

## 🤖 AI Scoring System

Each car is evaluated by Claude AI on a **0–10 scale**. Minimum score to receive a notification:

- **Standard (≤ 8,000 €):** score ≥ 7
- **Premium (8,001–10,000 €):** score ≥ 9

### Scoring criteria

| Points | Reason |
|--------|--------|
| +2 | Good seller rating on platform (≥ 4 stars) |
| +2 | TÜV / HU valid for at least 6 months |
| +2 | Full service history (Scheckheft) |
| +1 | Explicitly accident-free |
| +1 | Non-smoker vehicle |
| +1 | 1–2 previous owners |
| +1 | 💳 Financing / instalment available |
| +1 | Good overall condition |
| -2 | Vague or suspicious listing |
| -2 | Accident or engine damage mentioned |
| -1 | TÜV expiring soon |
| -1 | Poor or no seller rating |
| -1 | Known defects or repair needed |

---

## 📁 Project Structure

```
car-hunter/
├── car_hunter.py              # Main bot script
├── requirements.txt           # Python dependencies
├── README.md                  # This file
├── SETUP_GUIDE.html           # Full setup guide in Arabic
├── seen_cars.json             # Auto-generated: tracks seen listings
├── daily_stats.json           # Auto-generated: daily run statistics
└── .github/
    └── workflows/
        └── car_hunter.yml     # GitHub Actions — runs every hour
```

---

## 🚀 Setup Guide

### Prerequisites

- Free [GitHub](https://github.com) account
- Telegram account
- Gmail account
- [Anthropic API key](https://console.anthropic.com) (~0.50–1 € / month)

---

### Step 1 — Create GitHub Repository

1. Go to [github.com](https://github.com) → click **New repository**
2. Name it `car-hunter`, set to **Private**, click **Create repository**
3. Upload all project files maintaining this folder structure:
   ```
   .github/workflows/car_hunter.yml   ← must be in this exact path
   car_hunter.py
   requirements.txt
   README.md
   ```

---

### Step 2 — Create Telegram Bot

1. Open Telegram → search for **@BotFather** → start chat
2. Send: `/newbot`
3. Choose a name (e.g. `Car Hunter Amr`) and a username ending in `bot` (e.g. `car_hunter_amr_bot`)
4. BotFather sends you a **token** like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz` — save it
5. Open your new bot and send any message
6. Visit this URL in your browser (replace `YOUR_TOKEN`):
   ```
   https://api.telegram.org/botYOUR_TOKEN/getUpdates
   ```
7. Find `"chat":{"id":` — the number after it is your **Chat ID** — save it

---

### Step 3 — Gmail App Password

> ⚠️ This is NOT your regular Gmail password — it's a special app password

1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** (required)
3. Search for **App passwords** → click it
4. Enter name: `Car Hunter` → click **Create**
5. Copy the 16-character password (e.g. `xxxx xxxx xxxx xxxx`) — save it

---

### Step 4 — Add GitHub Secrets

In your repository: **Settings → Secrets and variables → Actions → New repository secret**

Add these 6 secrets exactly as shown:

| Secret Name | Value | Source |
|-------------|-------|--------|
| `TELEGRAM_BOT_TOKEN` | Your bot token from BotFather | Step 2 |
| `TELEGRAM_CHAT_ID` | Your numeric chat ID | Step 2 |
| `GMAIL_USER` | Your full Gmail address | Your Gmail |
| `GMAIL_APP_PASSWORD` | The 16-character app password | Step 3 |
| `NOTIFY_EMAIL` | Email to receive notifications | Can be same as Gmail |
| `ANTHROPIC_API_KEY` | Your Claude API key | console.anthropic.com |

> ⚠️ Secret names are **case-sensitive** — type them exactly as shown above

---

### Step 5 — First Run

1. In your repository, click **Actions** tab
2. Click **🚗 Car Hunter — Hourly Search**
3. Click **Run workflow → Run workflow**
4. Wait 2–3 minutes
5. Check your Telegram and email — if cars were found, you'll receive notifications immediately!

From now on, the bot runs **automatically every hour** — no action needed.

---

## 📱 Notification Format

### Telegram Message
```
🚗 سيارة ممتازة وجدتها! 🇩🇪
━━━━━━━━━━━━━━━━━━━━
💳 تقسيط متاح!
📌 BMW 320d xDrive Touring
🟢 تقييم AI: 9/10
⭐ تقييم الموقع: 4.8 von 5
💰 السعر: 7.490 €
📍 الكيلومترات: 54.000 km
🔄 الجيربوكس: Automatik
🚘 الشكل: Kombi
🌐 المصدر: AutoScout24
🏅 ✅ TÜV gültig · 📋 Scheckheft · 🛡 Unfallfrei
✨ مميزات: Vollausstattung | Sitzheizung | Navi
📝 بي إم دبليو 320 ديزل أوتوماتيك، حالة ممتازة...
━━━━━━━━━━━━━━━━━━━━
🔗 اضغط هنا للتفاصيل
```

---

## 💰 Cost Breakdown

| Service | Cost |
|---------|------|
| GitHub Actions (hourly runs) | **Free** ✅ |
| AutoScout24 / Mobile.de scraping | **Free** ✅ |
| Telegram Bot API | **Free** ✅ |
| Gmail SMTP | **Free** ✅ |
| Anthropic Claude API | **~0.50–1 € / month** |
| **Total** | **≈ 1 € / month** |

---

## 🗺️ Search Coverage — 300 km around Freiburg

The bot searches within a 300 km radius of Freiburg im Breisgau (PLZ 79098), covering:

- ✅ All of **Baden-Württemberg** (Stuttgart, Karlsruhe, Mannheim, Konstanz...)
- ✅ **Southern Bavaria** (München, Augsburg)
- ✅ **Switzerland** (Basel, Zürich)
- ✅ **Alsace, France** (Strasbourg, Mulhouse)
- ✅ **Hessen / Rheinland-Pfalz** (Frankfurt, Saarbrücken)
- ❌ Too far: Berlin, Hamburg, Hannover, Dortmund

---

## 🔧 Troubleshooting

**Workflow failed (red X in Actions)**
→ Click the failed run → check logs → usually a misconfigured Secret

**Not receiving Telegram messages**
→ Make sure you sent the bot a message first (required to activate the chat)
→ Double-check your `TELEGRAM_CHAT_ID` — must be numeric

**Gmail not working**
→ Confirm 2-Step Verification is enabled
→ Use App Password — NOT your regular Gmail password

**No cars found**
→ This is normal — new listings don't appear every hour
→ You'll receive a daily summary at 20:00 regardless

**Want to change search area?**
→ Edit `SEARCH_ZIP` and `SEARCH_RADIUS` in `car_hunter.py` (lines ~50-56)

---

## 🛠️ Customization

All main settings are at the top of `car_hunter.py`:

```python
PRICE_MIN         = 4000    # Minimum price €
PRICE_MAX         = 8000    # Standard max price €
PRICE_MAX_PREMIUM = 10000   # Premium tier (requires score ≥ 9)
KM_MAX            = 70000   # Maximum mileage
YEAR_MIN          = 2016    # Minimum year
SEARCH_ZIP        = '79098' # Your city ZIP code
SEARCH_RADIUS     = 300     # Search radius in km
```

To edit: go to your GitHub repo → click `car_hunter.py` → click the ✏️ pencil icon → edit → **Commit changes**. The next hourly run picks up your changes automatically.

---

## 📄 License

Built for personal use. Free to use and modify.

---

*🤖 Powered by Claude AI · 🇩🇪 Made for car hunting in Germany*
