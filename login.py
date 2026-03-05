"""
login.py – Einmaliger manueller Login-Flow für einen spezifischen Account.

Ausführung: python main.py login --account X

Was passiert:
  1. Chrome öffnet sich mit dem zugewiesenen Webshare-Proxy des Accounts.
  2. Du loggst dich manuell in Facebook ein (inkl. 2FA falls nötig).
  3. Du drückst Enter im Terminal.
  4. Die Session-Cookies werden in sessions/accountX.json gespeichert.
  5. Browser schließt sich.
"""

import sys
import os
from pathlib import Path

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

# Lokale Imports
from config import (
    ACCOUNTS,
    BROWSER_ARGS,
    VIEWPORT,
    LOCALE,
    TIMEZONE_ID,
    USER_AGENT,
)
from utils import logger, take_debug_screenshot


def run_login(account_id: int = 1) -> None:
    """
    Startet einen manuellen Login-Flow für einen definierten Account und
    speichert den Storage-State als JSON ab.
    """
    account = next((a for a in ACCOUNTS if a.get("id") == account_id), None)
    if not account:
        logger.error(f"Account mit ID {account_id} nicht in config.yaml gefunden.")
        return

    account_name = account.get("name")
    session_file = account.get("session_file")
    proxy_config = account.get("proxy")

    if not session_file:
        logger.error("Kein session_file Pfad in config für diesen Account angegeben.")
        return

    # Ensure sessions directory exists
    Path(session_file).parent.mkdir(parents=True, exist_ok=True)

    pw_proxy = None
    if proxy_config and proxy_config.get("server"):
        pw_proxy = {
            "server": proxy_config["server"],
            "username": proxy_config.get("username", ""),
            "password": proxy_config.get("password", "")
        }

    logger.info("=" * 60)
    logger.info(f"FB Messenger Bot – Login-Setup für {account_name}")
    logger.info("=" * 60)
    logger.info(f"Session wird gespeichert unter: {session_file}")
    if pw_proxy:
        logger.info(f"Nutze Proxy: {pw_proxy['server']}")
    
    logger.info("Chrome öffnet sich gleich. Bitte:")
    logger.info("  1. Manuell bei Facebook einloggen (inkl. 2FA)")
    logger.info("  2. Warten bis du vollständig eingeloggt bist")
    logger.info("  3. Hier im Terminal ENTER drücken")
    logger.info("-" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=BROWSER_ARGS,
            proxy=pw_proxy
        )
        
        context = browser.new_context(
            viewport=VIEWPORT,
            locale=LOCALE,
            timezone_id=TIMEZONE_ID,
            user_agent=USER_AGENT,
        )

        page = context.new_page()

        # Stealth-Layer anwenden
        Stealth().apply_stealth_sync(page)

        # Patches
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['de-DE', 'de', 'en-US', 'en'] });
        """)

        try:
            logger.info("Navigiere zu Facebook...")
            page.goto("https://www.facebook.com", wait_until="domcontentloaded", timeout=60_000)
            logger.info("Facebook geladen. Bitte jetzt manuell einloggen.")

        except Exception as e:
            logger.error(f"Fehler beim Laden von Facebook: {e}")
            take_debug_screenshot(page, f"login_error_acc{account_id}")
            context.close()
            browser.close()
            sys.exit(1)

        # Warten auf manuelle Aktion des Nutzers
        print("\n>>> Drücke ENTER sobald du vollständig eingeloggt bist... ", end="", flush=True)
        input()

        import time
        time.sleep(2)

        logger.info(f"Speichere Session für {account_name}...")
        context.storage_state(path=session_file)
        
        context.close()
        browser.close()

    logger.info(f"✅ Login erfolgreich! Session gespeichert unter: {session_file}")

if __name__ == "__main__":
    run_login(1)
