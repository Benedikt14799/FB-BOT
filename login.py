"""
login.py – Einmaliger manueller Login-Flow für den FB Messenger Bot.

Ausführung: python login.py  (oder: python main.py login)

Was passiert:
  1. Chrome öffnet sich mit einem leeren / neuen Profil
  2. Du loggst dich manuell in Facebook ein (inkl. 2FA falls nötig)
  3. Du drückst Enter im Terminal
  4. Das Chrome-Profil wird in ./fb_profile/ gespeichert
  5. Browser schließt sich sauber

Nach diesem Schritt kann send_message.py ohne Login starten.
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

# Lokale Imports
from config import (
    USER_DATA_DIR,
    BROWSER_ARGS,
    VIEWPORT,
    LOCALE,
    TIMEZONE_ID,
    USER_AGENT,
)
from utils import logger, take_debug_screenshot


def run_login() -> None:
    """
    Startet einen manuellen Login-Flow und persistiert das Chrome-Profil.
    """
    profile_path = Path(USER_DATA_DIR)
    profile_path.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("FB Messenger Bot – Login-Setup")
    logger.info("=" * 60)
    logger.info(f"Chrome-Profil wird unter gespeichert: {USER_DATA_DIR}")
    logger.info("Chrome öffnet sich gleich. Bitte:")
    logger.info("  1. Manuell bei Facebook einloggen (inkl. 2FA)")
    logger.info("  2. Warten bis du vollständig eingeloggt bist")
    logger.info("  3. Hier im Terminal ENTER drücken")
    logger.info("-" * 60)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
            channel="chrome",
            args=BROWSER_ARGS,
            viewport=VIEWPORT,
            locale=LOCALE,
            timezone_id=TIMEZONE_ID,
            user_agent=USER_AGENT,
        )

        page = context.new_page()

        # Stealth-Layer anwenden
        Stealth().apply_stealth_sync(page)

        # Zusätzliche Patches für verbleibende Automation-Flags
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['de-DE', 'de', 'en-US', 'en'],
            });
        """)

        try:
            logger.info("Navigiere zu Facebook...")
            page.goto("https://www.facebook.com", wait_until="domcontentloaded", timeout=30_000)
            logger.info("Facebook geladen. Bitte jetzt manuell einloggen.")

        except Exception as e:
            logger.error(f"Fehler beim Laden von Facebook: {e}")
            take_debug_screenshot(page, "login_error")
            context.close()
            sys.exit(1)

        # Warten auf manuelle Aktion des Nutzers
        print("\n>>> Drücke ENTER sobald du vollständig eingeloggt bist... ", end="", flush=True)
        input()

        # Kurze Pause damit alles gespeichert wird
        import time
        time.sleep(2)

        logger.info("Session wird gespeichert...")
        context.close()

    logger.info("✅ Login erfolgreich! Profil gespeichert unter: " + USER_DATA_DIR)
    logger.info("Du kannst jetzt 'python main.py send' ausführen.")


if __name__ == "__main__":
    run_login()
