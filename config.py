"""
config.py – Zentrale Konfiguration für den FB Messenger Bot.
Passe RECIPIENTS und optional die Selektoren hier an.
"""

import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

# ENV laden (.env Datei für kritische Secrets wie SUPABASE_KEY / OPENAI_API_KEY)
load_dotenv()

# ─────────────────────────────────────────────
# Pfade
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
USER_DATA_DIR = str(BASE_DIR / "fb_profile")
YAML_PATH = BASE_DIR / "config.yaml"

# ─────────────────────────────────────────────
# YAML-Konfiguration laden
# ─────────────────────────────────────────────
def load_config() -> dict:
    if not YAML_PATH.exists():
        raise FileNotFoundError(f"Konfigurationsdatei fehlt: {YAML_PATH}")
    with open(YAML_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

_config = load_config()

# ─────────────────────────────────────────────
# 1. API Keys & DB
# ─────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ─────────────────────────────────────────────
# 2. Zielgruppe & Basis-Setup
# ─────────────────────────────────────────────
GROUP_ID = _config.get("group_id")
GROUP_NAME = _config.get("group_name")
MESSENGER_PIN = _config.get("messenger_pin")
LOG_LEVEL = _config.get("log_level", "INFO")

# ─────────────────────────────────────────────
# 3. Timing & Limits (Phase 2 Nachrichten)
# ─────────────────────────────────────────────
_timing = _config.get("timing", {})
ACTIVE_HOURS_START = _timing.get("active_hours_start", 9)
ACTIVE_HOURS_END = _timing.get("active_hours_end", 20)
MAX_DAILY_MESSAGES = _timing.get("max_daily_messages", 80)
SCHEDULER_DELAY_MIN = _timing.get("scheduler_delay_min_sec", 180)
SCHEDULER_DELAY_MAX = _timing.get("scheduler_delay_max_sec", 480)
TYPING_MICRO_DELAY_MIN = _timing.get("typing_micro_delay_min_sec", 5)
TYPING_MICRO_DELAY_MAX = _timing.get("typing_micro_delay_max_sec", 30)

# Timeout für DOM-Element-Suche
ELEMENT_TIMEOUT_MS = 15_000  # 15 Sekunden

# ─────────────────────────────────────────────
# Multi-Account & Funnel Configuration
# ─────────────────────────────────────────────
ACCOUNTS = _config.get("accounts", [])
FUNNEL = _config.get("funnel", {
    "msg1_delay_min_hours": 24,
    "msg1_reply_delay_min_minutes": 30,
    "msg1_reply_delay_max_minutes": 90,
    "msg2_delay_min_hours": 24,
    "msg2_reply_delay_min_minutes": 30,
    "msg2_reply_delay_max_minutes": 60
})

# ─────────────────────────────────────────────
# 4. Scoring & Priorisierung (Phase 1 Engagement)
# ─────────────────────────────────────────────
_scoring = _config.get("scoring", {})
MIN_SCORE_FOR_MESSAGE = _scoring.get("min_score_for_message", 40)
SCORE_POINTS = _scoring.get("points", {
    "gemeinsame_gruppe": 10,
    "kommentar_erhalten": 20,
    "like_erhalten": 10,
    "freundschaft_angenommen": 40,
    "reagiert_auf_mein_kommentar": 25
})

# ─────────────────────────────────────────────
# Messenger URL Schema & DOM
# ─────────────────────────────────────────────
MESSENGER_URL_TEMPLATE = "https://www.facebook.com/messages/t/{contact_id}"
MSG_BOX = 'div[contenteditable="true"][role="textbox"]'
SEND_BTN = 'div[aria-label="Senden"]'  # Fallback: 'div[aria-label="Send"]'

# ─────────────────────────────────────────────
# Browser-Konfiguration
# ─────────────────────────────────────────────
BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-infobars",
    "--window-size=1440,900",
    "--disable-extensions-except=",
    "--start-maximized",
]

VIEWPORT = {"width": 1440, "height": 900}
LOCALE = "de-DE"
TIMEZONE_ID = "Europe/Berlin"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/132.0.0.0 Safari/537.36"
)

