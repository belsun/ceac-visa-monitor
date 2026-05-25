#!/usr/bin/env python3
"""
CEAC Visa Status Monitor
Periodically checks the U.S. Department of State CEAC visa status page
and sends notifications when the status changes.

Usage:
    python ceac_monitor.py                  # Single check
    python ceac_monitor.py --loop           # Continuous monitoring (default: every 60 min)
    python ceac_monitor.py --loop --interval 30  # Check every 30 minutes
"""

import argparse
import json
import logging
import os
import re
import sys
import tempfile
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.yaml"
DEFAULT_STATE_DIR = Path(__file__).parent / "state"

CEAC_URL = "https://ceac.state.gov/CEACStatTracker/Status.aspx"
CAPTCHA_BASE = "https://ceac.state.gov/CEACStatTracker/BotDetectCaptcha.ashx"

STATUS_KEYWORDS = [
    "Administrative Processing",
    "Approved",
    "Issued",
    "Refused",
    "Denied",
    "Ready",
    "In Transit",
    "Origination Scan",
    "No Status",
]

HELP_TEXT_SKIP = [
    "if your visa",
    "was issued",
    "case number is listed",
    "was approved",
    "will be processed",
    "for more information",
    "please visit",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ceac-monitor")


def load_config(config_path: str | Path | None = None) -> dict:
    """Load config from YAML file, falling back to env vars."""
    cfg = {
        "app_id": "",
        "passport": "",
        "surname": "",
        "location": "HNK",
        "visa_type": "NIV",
        "captcha_method": "ocr",  # ocr | manual
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "notify_webhook": "",
        "check_interval_minutes": 60,
    }

    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if path.exists():
        try:
            import yaml
            with open(path) as f:
                file_cfg = yaml.safe_load(f) or {}
            # Flatten nested 'case' section
            case = file_cfg.get("case", {})
            for k in ("app_id", "passport", "surname", "location", "visa_type"):
                if k in case:
                    cfg[k] = case[k]
            # Notification
            tg = file_cfg.get("notification", {}).get("telegram", {})
            if tg.get("bot_token"):
                cfg["telegram_bot_token"] = tg["bot_token"]
            if tg.get("chat_id"):
                cfg["telegram_chat_id"] = tg["chat_id"]
            webhook = file_cfg.get("notification", {}).get("webhook", "")
            if webhook:
                cfg["notify_webhook"] = webhook
            # Settings
            settings = file_cfg.get("settings", {})
            if "captcha_method" in settings:
                cfg["captcha_method"] = settings["captcha_method"]
            if "check_interval_minutes" in settings:
                cfg["check_interval_minutes"] = settings["check_interval_minutes"]
        except ImportError:
            log.warning("PyYAML not installed, falling back to env vars")

    # Env var overrides
    cfg["app_id"] = os.getenv("CEAC_APP_ID", cfg["app_id"])
    cfg["passport"] = os.getenv("CEAC_PASSPORT", cfg["passport"])
    cfg["surname"] = os.getenv("CEAC_SURNAME", cfg["surname"])
    cfg["location"] = os.getenv("CEAC_LOCATION", cfg["location"])
    cfg["visa_type"] = os.getenv("CEAC_VISA_TYPE", cfg["visa_type"])
    cfg["telegram_bot_token"] = os.getenv("TELEGRAM_BOT_TOKEN", cfg["telegram_bot_token"])
    cfg["telegram_chat_id"] = os.getenv("TELEGRAM_CHAT_ID", cfg["telegram_chat_id"])
    cfg["notify_webhook"] = os.getenv("NOTIFY_WEBHOOK", cfg["notify_webhook"])

    return cfg


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": CEAC_URL,
    })
    return s


def extract_fields(soup: BeautifulSoup) -> dict:
    """Extract ASP.NET hidden form fields."""
    fields = {}
    for name in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__VIEWSTATEENCRYPTED",
                  "__EVENTTARGET", "__EVENTARGUMENT", "__LASTFOCUS"]:
        el = soup.find("input", {"name": name})
        if el:
            fields[name] = el.get("value", "")
    vcid = soup.find("input", {"name": lambda n: n and "VCID" in n})
    if vcid:
        fields["vcid_name"] = vcid["name"]
        fields["vcid_value"] = vcid["value"]
    return fields


# ---------------------------------------------------------------------------
# CAPTCHA solving
# ---------------------------------------------------------------------------

def solve_captcha_ocr(image_bytes: bytes) -> str:
    """Solve CAPTCHA using ddddocr library."""
    try:
        import ddddocr
        ocr = ddddocr.DdddOcr(show_ad=False)
        return ocr.classification(image_bytes)
    except ImportError:
        log.error("ddddocr not installed. Run: pip install ddddocr")
        sys.exit(1)


def solve_captcha_manual(image_path: str) -> str:
    """Prompt user to manually enter CAPTCHA text."""
    print(f"\n  CAPTCHA image saved to: {image_path}")
    try:
        # Try to open the image for the user
        import subprocess
        subprocess.Popen(["open", image_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    return input("  Enter the CAPTCHA text: ").strip()


def solve_captcha_tesseract(image_bytes: bytes) -> str:
    """Solve CAPTCHA using Tesseract OCR (less reliable for CEAC CAPTCHAs)."""
    try:
        import pytesseract
        from PIL import Image
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(image_bytes)
            tmp = f.name
        try:
            img = Image.open(tmp)
            img = img.convert("L")
            w, h = img.size
            img = img.resize((w * 3, h * 3), Image.LANCZOS)
            text = pytesseract.image_to_string(
                img, config="--psm 7 --oem 3 "
                "-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
            ).strip()
            return re.sub(r"[^A-Za-z0-9]", "", text)
        finally:
            os.unlink(tmp)
    except ImportError:
        log.error("pytesseract not installed. Run: pip install pytesseract Pillow")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Core checking logic
# ---------------------------------------------------------------------------

def download_captcha(cfg: dict, state_dir: Path) -> tuple[requests.Session, dict, str]:
    """Download the CEAC page and CAPTCHA. Returns (session, form_state, captcha_path)."""
    state_dir.mkdir(parents=True, exist_ok=True)
    captcha_path = str(state_dir / "captcha.png")
    form_state_path = state_dir / "form_state.json"

    session = make_session()

    # GET initial page
    resp = session.get(CEAC_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    fields = extract_fields(soup)

    # POST to switch to NIV mode (ASP.NET postback)
    post_data = {
        "ctl00_ToolkitScriptManager1_HiddenField": "",
        "__EVENTTARGET": "ctl00$ContentPlaceHolder1$Visa_Application_Type",
        "__EVENTARGUMENT": "",
        "__LASTFOCUS": "",
        "__VIEWSTATE": fields["__VIEWSTATE"],
        "__VIEWSTATEGENERATOR": fields.get("__VIEWSTATEGENERATOR", ""),
        "__VIEWSTATEENCRYPTED": "",
        "ctl00$ContentPlaceHolder1$Visa_Application_Type": cfg["visa_type"],
        "ctl00$ContentPlaceHolder1$Location_Dropdown": "",
        "ctl00$ContentPlaceHolder1$Visa_Case_Number": "",
        "ctl00$ContentPlaceHolder1$Passport_Number": "",
        "ctl00$ContentPlaceHolder1$Surname": "",
        "ctl00$ContentPlaceHolder1$Captcha": "",
        fields["vcid_name"]: fields["vcid_value"],
        "LBD_BackWorkaround_c_status_ctl00_contentplaceholder1_defaultcaptcha": "1",
        "ctl00$ApplicationInfo": "G-CS3M0DZ3BF",
    }

    resp2 = session.post(CEAC_URL, data=post_data, timeout=30)
    resp2.raise_for_status()
    soup2 = BeautifulSoup(resp2.text, "html.parser")
    fields2 = extract_fields(soup2)

    # Download CAPTCHA
    vcid_val = fields2.get("vcid_value", fields.get("vcid_value"))
    captcha_url = (
        f"{CAPTCHA_BASE}?get=image"
        f"&c=c_status_ctl00_contentplaceholder1_defaultcaptcha&t={vcid_val}"
    )
    captcha_resp = session.get(captcha_url, timeout=30)
    captcha_resp.raise_for_status()
    Path(captcha_path).write_bytes(captcha_resp.content)

    # Save form state
    form_state = {
        "viewstate": fields2.get("__VIEWSTATE", fields["__VIEWSTATE"]),
        "viewstate_generator": fields2.get("__VIEWSTATEGENERATOR", fields.get("__VIEWSTATEGENERATOR", "")),
        "vcid_name": fields2.get("vcid_name", fields["vcid_name"]),
        "vcid_value": vcid_val,
        "cookies": dict(session.cookies),
        "captcha_path": captcha_path,
        "timestamp": time.time(),
    }
    form_state_path.write_text(json.dumps(form_state, indent=2))

    return session, form_state, captcha_path


def submit_form(
    session: requests.Session,
    form_state: dict,
    cfg: dict,
    captcha_text: str,
) -> dict:
    """Submit the CEAC form and parse the result."""
    # Check state freshness
    if time.time() - form_state.get("timestamp", 0) > 300:
        raise RuntimeError("Form state expired (>5 min). Re-run download.")

    # Restore cookies
    for name, value in form_state.get("cookies", {}).items():
        session.cookies.set(name, value)

    post_data = {
        "ctl00_ToolkitScriptManager1_HiddenField": "",
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        "__LASTFOCUS": "",
        "__VIEWSTATE": form_state["viewstate"],
        "__VIEWSTATEGENERATOR": form_state["viewstate_generator"],
        "__VIEWSTATEENCRYPTED": "",
        "ctl00$ContentPlaceHolder1$Visa_Application_Type": cfg["visa_type"],
        "ctl00$ContentPlaceHolder1$Location_Dropdown": cfg["location"],
        "ctl00$ContentPlaceHolder1$Visa_Case_Number": cfg["app_id"],
        "ctl00$ContentPlaceHolder1$Passport_Number": cfg["passport"],
        "ctl00$ContentPlaceHolder1$Surname": cfg["surname"],
        "ctl00$ContentPlaceHolder1$Captcha": captcha_text,
        form_state["vcid_name"]: form_state["vcid_value"],
        "LBD_BackWorkaround_c_status_ctl00_contentplaceholder1_defaultcaptcha": "1",
        "ctl00$ApplicationInfo": "G-CS3M0DZ3BF",
        "ctl00$ContentPlaceHolder1$btnSubmit": "",
    }

    resp = session.post(CEAC_URL, data=post_data, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Detect CAPTCHA error
    page_text = soup.get_text()
    if "incorrect security code" in page_text.lower():
        raise ValueError("CAPTCHA incorrect")

    # Check if still on form page
    h2_tags = [h.get_text(strip=True) for h in soup.find_all("h2")]
    if any("select a location" in h.lower() or "enter your application" in h.lower()
           for h in h2_tags):
        raise ValueError("Form not submitted (likely wrong CAPTCHA)")

    # Check for validation errors
    error_spans = soup.find_all("span", class_="field-validation-error")
    error_texts = [s.get_text(strip=True) for s in error_spans if s.get_text(strip=True)]
    if error_texts:
        raise ValueError(f"Validation error: {'; '.join(error_texts)}")

    # Parse status
    # Remove scripts/styles to avoid false matches
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()

    found_status = None

    # Method 1: Exact match in headings
    for tag in soup.find_all(["h1", "h2", "h3", "strong", "b"]):
        text = tag.get_text(strip=True)
        for pattern in STATUS_KEYWORDS:
            if text == pattern:
                found_status = pattern
                break
        if found_status:
            break

    # Method 2: Exact match in other elements
    if not found_status:
        for tag in soup.find_all(["div", "span", "p", "td"]):
            text = tag.get_text(strip=True)
            if text in STATUS_KEYWORDS:
                found_status = text
                break

    # Method 3: Broader search with context filtering
    if not found_status:
        body = soup.find("body")
        if body:
            body_text = body.get_text()
            for pattern in STATUS_KEYWORDS:
                regex = re.compile(r"\b" + re.escape(pattern) + r"\b", re.IGNORECASE)
                for m in regex.finditer(body_text):
                    start = max(0, m.start() - 100)
                    context = body_text[start : m.end() + 100]
                    if any(skip in context.lower() for skip in HELP_TEXT_SKIP):
                        continue
                    found_status = pattern
                    break
                if found_status:
                    break

    if not found_status:
        raise RuntimeError("Could not determine status from response")

    # Extract case details
    details = {}
    case_match = re.search(r"Application ID.*?:\s*(\S+)", page_text)
    created_match = re.search(r"Case Created:\s*([\d\-]+-[A-Za-z]+-[\d]+)", page_text)
    updated_match = re.search(r"Case Last Updated:\s*([\d\-]+-[A-Za-z]+-[\d]+)", page_text)
    if case_match:
        details["case_id"] = case_match.group(1)
    if created_match:
        details["created"] = created_match.group(1)
    if updated_match:
        details["updated"] = updated_match.group(1)

    return {"status": found_status, "details": details}


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def load_state(state_dir: Path) -> dict:
    path = state_dir / "last_status.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {"status": None}


def save_state(state_dir: Path, status: str, details: dict):
    state_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "status": status,
        "details": details,
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (state_dir / "last_status.json").write_text(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def send_telegram(bot_token: str, chat_id: str, text: str):
    """Send a message via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()
        log.info("Telegram notification sent")
    except Exception as e:
        log.error(f"Telegram send failed: {e}")


def send_webhook(webhook_url: str, text: str):
    """Send a notification via generic webhook (POST JSON)."""
    try:
        r = requests.post(webhook_url, json={"text": text}, timeout=15)
        r.raise_for_status()
        log.info("Webhook notification sent")
    except Exception as e:
        log.error(f"Webhook send failed: {e}")


def notify(cfg: dict, message: str):
    """Send notification through configured channels."""
    if cfg.get("telegram_bot_token") and cfg.get("telegram_chat_id"):
        send_telegram(cfg["telegram_bot_token"], cfg["telegram_chat_id"], message)
    if cfg.get("notify_webhook"):
        send_webhook(cfg["notify_webhook"], message)
    # Always print to stdout
    print(f"\n{'='*50}")
    print(message)
    print(f"{'='*50}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def check_once(cfg: dict, state_dir: Path) -> bool:
    """
    Run a single check. Returns True if status changed (or first check).
    """
    method = cfg.get("captcha_method", "ocr")
    state = load_state(state_dir)
    prev_status = state.get("status")

    log.info(f"Checking CEAC status for {cfg['app_id']}...")

    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            session, form_state, captcha_path = download_captcha(cfg, state_dir)

            # Solve CAPTCHA
            captcha_bytes = Path(captcha_path).read_bytes()
            if method == "manual":
                captcha_text = solve_captcha_manual(captcha_path)
            elif method == "tesseract":
                captcha_text = solve_captcha_tesseract(captcha_bytes)
            else:  # ocr (default)
                captcha_text = solve_captcha_ocr(captcha_bytes)

            if not captcha_text or len(captcha_text) < 3:
                log.warning(f"CAPTCHA recognition too short: '{captcha_text}', retrying...")
                time.sleep(2)
                continue

            log.info(f"CAPTCHA solved: {captcha_text} (attempt {attempt})")

            # Submit
            result = submit_form(session, form_state, cfg, captcha_text)
            status = result["status"]
            details = result["details"]

            log.info(f"Status: {status}")

            # Compare with previous
            changed = prev_status is not None and prev_status.lower() != status.lower()
            first_check = prev_status is None

            # Save state
            save_state(state_dir, status, details)

            # Notify if changed or first check
            if changed or first_check:
                msg_lines = [f"🇺🇸 <b>CEAC Visa Status Update</b>", ""]
                msg_lines.append(f"<b>Status:</b> {status}")
                for k, v in details.items():
                    msg_lines.append(f"<b>{k}:</b> {v}")
                msg_lines.append(f"<b>Checked:</b> {time.strftime('%Y-%m-%d %H:%M:%S')}")
                msg_lines.append(f"<b>Case ID:</b> {cfg['app_id']}")
                if changed:
                    msg_lines.append("")
                    msg_lines.append(f"⚠️ <b>Status changed!</b>")
                    msg_lines.append(f"Previous: {prev_status}")
                    msg_lines.append(f"Current: {status}")
                notify(cfg, "\n".join(msg_lines))
                return True
            else:
                log.info("Status unchanged, no notification needed")
                return False

        except ValueError as e:
            if "CAPTCHA" in str(e) or "wrong" in str(e).lower():
                log.warning(f"CAPTCHA failed (attempt {attempt}/{max_retries}): {e}")
                time.sleep(2)
                continue
            raise
        except Exception as e:
            log.error(f"Error on attempt {attempt}: {e}")
            if attempt < max_retries:
                time.sleep(3)
                continue
            raise

    log.error(f"Failed after {max_retries} CAPTCHA attempts")
    return False


def main():
    parser = argparse.ArgumentParser(description="CEAC Visa Status Monitor")
    parser.add_argument("-c", "--config", help="Path to config.yaml")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, help="Check interval in minutes (default: 60)")
    parser.add_argument("--state-dir", help="Directory for state files")
    parser.add_argument("--once", action="store_true", help="Single check then exit (default)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    state_dir = Path(args.state_dir) if args.state_dir else DEFAULT_STATE_DIR
    interval = args.interval or cfg.get("check_interval_minutes", 60)

    # Validate required fields
    if not cfg["app_id"]:
        log.error("App ID / Case Number is required. Set in config.yaml or CEAC_APP_ID env var.")
        sys.exit(1)

    if args.loop:
        log.info(f"Starting continuous monitoring (interval: {interval} min)")
        while True:
            try:
                check_once(cfg, state_dir)
            except KeyboardInterrupt:
                log.info("Stopped by user")
                break
            except Exception as e:
                log.error(f"Check failed: {e}")
            log.info(f"Next check in {interval} minutes...")
            try:
                time.sleep(interval * 60)
            except KeyboardInterrupt:
                log.info("Stopped by user")
                break
    else:
        try:
            check_once(cfg, state_dir)
        except Exception as e:
            log.error(f"Check failed: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
