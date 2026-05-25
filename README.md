# 🇺🇸 CEAC Visa Status Monitor

Automated monitoring tool for U.S. Department of State [CEAC](https://ceac.state.gov/) visa application status. Detects status changes (Administrative Processing → Approved/Issued/Refused etc.) and sends notifications via Telegram or webhook.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## ✨ Features

- 🔄 **Automatic CAPTCHA solving** via [ddddocr](https://github.com/sml2h3/ddddocr) OCR
- 📱 **Telegram notifications** when status changes
- 💬 **WeChat notifications** via iLink Bot API
- 🔔 **Webhook support** for custom integrations (Discord, Slack, etc.)
- 🔁 **Continuous monitoring** mode with configurable interval
- 📊 **Status tracking** — remembers last known status, only notifies on changes
- 🛡️ **Anti-detection** — proper User-Agent, session handling, ASP.NET postback support

## 🚀 Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure

```bash
cp config.example.yaml config.yaml
# Edit config.yaml with your case details
```

Or use environment variables:

```bash
export CEAC_APP_ID="AA000000000"
export CEAC_PASSPORT="E12345678"
export CEAC_SURNAME="ZHANG"
export CEAC_LOCATION="HNK"
export TELEGRAM_BOT_TOKEN="your-bot-token"
export TELEGRAM_CHAT_ID="your-chat-id"
```

### 3. Run

```bash
# Single check
python ceac_monitor.py

# Continuous monitoring (every 60 minutes)
python ceac_monitor.py --loop

# Custom interval (every 30 minutes)
python ceac_monitor.py --loop --interval 30
```

## 📋 Configuration

### Case Information

| Field | Description | Example |
|-------|-------------|---------|
| `app_id` | Application ID / Case Number | `AA0020AKAX` |
| `passport` | Passport number | `E12345678` |
| `surname` | First 5 letters of surname | `ZHANG` |
| `location` | Embassy/Consulate code | `HNK` (Hong Kong) |
| `visa_type` | `NIV` (Nonimmigrant) or `IV` (Immigrant) | `NIV` |

### Location Codes

229 locations supported — see [LOCATIONS.md](LOCATIONS.md) for the full list.

| Code | Location |
|------|----------|
| `HNK` | Hong Kong |
| `BEJ` | Beijing |
| `GUZ` | Guangzhou |
| `SHG` | Shanghai |
| `CHE` | Chengdu |
| `SNY` | Shenyang |
| `WUH` | Wuhan |
| `LND` | London |
| `TKY` | Tokyo |
| `SEO` | Seoul |
| `TAI` | Taipei |
| `SGP` | Singapore |
| `BNK` | Bangkok |

### CAPTCHA Solving

CEAC uses dot-matrix style CAPTCHAs that are difficult for basic OCR.

| Method | Accuracy | Cost | Best for |
|--------|----------|------|----------|
| `2captcha` (recommended) | ~99% | ~$3/1000 | Automated monitoring |
| `audio` | ~80% | Free | Fallback option |
| `ocr` (ddddocr) | ~0% on CEAC | Free | Other CAPTCHA types |
| `tesseract` | ~0% on CEAC | Free | Other CAPTCHA types |
| `manual` | 100% | Free | Local debugging |

> 💡 For GitHub Actions, use `2captcha`. Sign up at [2captcha.com](https://2captcha.com), add $3 credit, and get your API key.

### Telegram Setup

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow instructions
3. Copy the bot token into `config.yaml`
4. Message [@userinfobot](https://t.me/userinfobot) to get your chat ID
5. Put the chat ID in `config.yaml`

### WeChat Setup (iLink Bot)

WeChat uses the iLink Bot API. You need a bot created via Hermes or the iLink QR login flow.

1. Get your bot credentials from your Hermes setup:
   - `WEIXIN_TOKEN` — from `~/.hermes/.env`
   - `WEIXIN_ACCOUNT_ID` — your bot account ID
   - `WEIXIN_BASE_URL` — default is `https://ilinkai.weixin.qq.com`
2. Get your WeChat user ID by messaging the bot and checking logs
3. Put these in `config.yaml` or as GitHub Secrets:
   - `WEIXIN_TOKEN`
   - `WEIXIN_TO_USER` — your WeChat user ID (e.g. `o9xxx@im.wechat`)

> 💡 If you don't have a WeChat bot, you can use Telegram (easier) or the generic webhook to connect to any service.

## ☁️ GitHub Actions (Recommended — No Local Setup)

The easiest way to monitor — runs in the cloud, no computer needed.

### 1. Fork or clone this repo

### 2. Add secrets to your repo

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these secrets:

| Secret | Value | Required |
|--------|-------|----------|
| `CEAC_APP_ID` | Your Application ID (e.g. `AA0020AKAX`) | ✅ |
| `CEAC_PASSPORT` | Your passport number | ✅ |
| `CEAC_SURNAME` | First 5 letters of surname | ✅ |
| `CEAC_LOCATION` | Embassy code (e.g. `HNK`) | ✅ |
| `CEAC_VISA_TYPE` | `NIV` or `IV` | Optional |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | At least one |
| `TELEGRAM_CHAT_ID` | Chat ID from @userinfobot | notification |
| `WEIXIN_TOKEN` | WeChat iLink bot token | channel is |
| `WEIXIN_BASE_URL` | iLink API URL | Optional |
| `WEIXIN_TO_USER` | WeChat user ID | needed |

### 3. Enable the workflow

Go to **Actions** tab → Click **"I understand my workflows, go ahead and enable them"**

The monitor will automatically run **every hour**. You can also trigger it manually from the Actions tab.

> 🔒 **Your data is safe:** Secrets are encrypted by GitHub and never appear in logs or code. The `state/` directory with your status history is cached locally in the runner and never committed to the repo.

## 🔁 Cron Setup (Self-Hosted)

For scheduled monitoring without the `--loop` flag, on your own machine:

```bash
# Check every hour
0 * * * * cd /path/to/ceac-visa-monitor && python ceac_monitor.py >> logs/monitor.log 2>&1

# Check every 30 minutes during daytime (8am-10pm)
*/30 8-22 * * * cd /path/to/ceac-visa-monitor && python ceac_monitor.py >> logs/monitor.log 2>&1
```

## 🐳 Docker (One-Click Deploy)

Run the monitor in a container — no Python setup needed.

```bash
# 1. Fill in your credentials
cp config.example.yaml config.yaml
# Edit config.yaml with your case details

# 2. Set environment variables (or create a .env file)
export CEAC_APP_ID="AA000000000"
export CEAC_PASSPORT="E12345678"
export CEAC_SURNAME="ZHANG"
export CEAC_LOCATION="HNK"
export TELEGRAM_BOT_TOKEN="your-token"
export TELEGRAM_CHAT_ID="your-chat-id"

# 3. Build and run
docker compose up -d

# Check logs
docker compose logs -f

# Stop
docker compose down
```

Or with plain Docker:

```bash
docker build -t ceac-monitor .
docker run -d --name ceac-monitor \
  -e CEAC_APP_ID="AA000000000" \
  -e CEAC_PASSPORT="E12345678" \
  -e CEAC_SURNAME="ZHANG" \
  -e CEAC_LOCATION="HNK" \
  -e TELEGRAM_BOT_TOKEN="your-token" \
  -e TELEGRAM_CHAT_ID="your-chat-id" \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/state:/app/state \
  ceac-monitor
```

## 📊 Status Types

| Status | Meaning |
|--------|---------|
| **Administrative Processing** | Under review (221g) — most common after interview |
| **Approved** | Visa approved, pending issuance |
| **Issued** | Visa has been issued and mailed |
| **Refused** | Visa application denied |
| **Refused under INA 214(b)** | Denied — insufficient ties to home country |
| **Refused under INA 221(g)** | Denied — missing documents or additional admin processing |
| **Refused under INA 212(a)** | Denied — inadmissibility grounds |
| **Denied** | Application denied |
| **Ready** | Application ready for interview |
| **In Transit** | Visa in transit to consulate |
| **Origination Scan** | Being processed at origin |
| **Application Received** | Application received by consulate |
| **Expedited** | Under expedited processing |

> The monitor also catches any `Refused under INA ...` variant automatically via prefix matching.

## ⚠️ Notes

- The CEAC website uses ASP.NET with ViewState — this tool handles the full postback flow
- CAPTCHA success rate with `ddddocr` is ~70%; the tool auto-retries up to 5 times
- Status changes are rare (Administrative Processing can last days to weeks)
- Don't check too frequently — the CEAC site may rate-limit excessive requests
- This tool is for personal use. Be responsible with your monitoring frequency

## 📁 Project Structure

```
ceac-visa-monitor/
├── ceac_monitor.py        # Main script
├── config.example.yaml    # Config template
├── config.yaml            # Your config (git-ignored)
├── requirements.txt       # Python dependencies
├── Dockerfile             # Docker image build
├── docker-compose.yml     # Docker Compose config
├── .dockerignore
├── LOCATIONS.md           # Full list of 229 location codes
├── .gitignore
├── LICENSE                # MIT
├── README.md
└── state/                 # Runtime state (git-ignored)
    ├── captcha.png        # Latest CAPTCHA image
    ├── form_state.json    # ASP.NET form state
    └── last_status.json   # Last known visa status
```

## 🤝 Contributing

Contributions welcome! Some ideas:
- Better CAPTCHA solving (ML models, third-party APIs)
- Email notifications
- WhatsApp/Discord/Slack integration
- Web dashboard

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

## ⚖️ Disclaimer

This tool is provided for educational and personal use only. Use responsibly and respect the CEAC website's terms of service. The author is not responsible for any misuse or issues arising from the use of this tool.
