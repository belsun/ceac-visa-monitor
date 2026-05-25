# 🇺🇸 CEAC Visa Status Monitor

Automated monitoring tool for U.S. Department of State [CEAC](https://ceac.state.gov/) visa application status. Detects status changes (Administrative Processing → Approved/Issued/Refused etc.) and sends notifications via Telegram or webhook.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## ✨ Features

- 🔄 **Automatic CAPTCHA solving** via [ddddocr](https://github.com/sml2h3/ddddocr) OCR
- 📱 **Telegram notifications** when status changes
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

### Location Codes (Common)

| Code | Location |
|------|----------|
| `HNK` | Hong Kong |
| `CHI` | Beijing |
| `CGS` | Guangzhou |
| `SHA` | Shanghai |
| `CGO` | Chengdu |
| `SYA` | Shenyang |
| `WUH` | Wuhan |
| `LON` | London |
| `TYO` | Tokyo |
| `SEL` | Seoul |

### CAPTCHA Solving

| Method | Pros | Cons |
|--------|------|------|
| `ocr` (default) | Fast, automatic | ~70% success rate, may need retries |
| `manual` | 100% accurate | Requires human input each time |
| `tesseract` | No extra deps beyond pytesseract | Low accuracy on CEAC CAPTCHAs |

### Telegram Setup

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow instructions
3. Copy the bot token into `config.yaml`
4. Message [@userinfobot](https://t.me/userinfobot) to get your chat ID
5. Put the chat ID in `config.yaml`

## 🔁 Cron Setup

For scheduled monitoring without the `--loop` flag:

```bash
# Check every hour
0 * * * * cd /path/to/ceac-visa-monitor && python ceac_monitor.py >> logs/monitor.log 2>&1

# Check every 30 minutes during daytime (8am-10pm)
*/30 8-22 * * * cd /path/to/ceac-visa-monitor && python ceac_monitor.py >> logs/monitor.log 2>&1
```

## 📊 Status Types

| Status | Meaning |
|--------|---------|
| **Administrative Processing** | Under review (221g) — most common after interview |
| **Approved** | Visa approved, pending issuance |
| **Issued** | Visa has been issued and mailed |
| **Refused** | Visa application denied |
| **Ready** | Application ready for interview |
| **In Transit** | Visa in transit to consulate |
| **Origination Scan** | Being processed at origin |

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
├── .gitignore
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
- Docker support

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

## ⚖️ Disclaimer

This tool is provided for educational and personal use only. Use responsibly and respect the CEAC website's terms of service. The author is not responsible for any misuse or issues arising from the use of this tool.
