"""
account_manager.py – Multi-Account Orchestration (Phase 1+2 Async)

Verwaltet die 6 parallelen Browser-Instanzen.
Jede Instanz läuft asynchron und nutzt einen eigenen Webshare Proxy
sowie eine eigene isolierte Storage-State Datei.
"""

import asyncio
from playwright.async_api import async_playwright, Playwright

from config import ACCOUNTS, BROWSER_ARGS, VIEWPORT, LOCALE, TIMEZONE_ID, USER_AGENT
from utils import logger
from daemon import run_account_loop
from database import init_account_in_db

STEALTH_INIT_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['de-DE', 'de', 'en-US', 'en'] });
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
"""

async def run_account(playwright: Playwright, account: dict, task_func=None, *args, **kwargs):
    """
    Startet und betreut die Browser-Session für EINEN Account.
    Wenn task_func übergeben wird, wird nur diese ausgeführt,
    ansonsten läuft die Endlosschleife (Scheduler) für diesen Account.
    """
    account_id = account.get("id")
    account_name = account.get("name")
    session_file = account.get("session_file")
    proxy_config = account.get("proxy")

    init_account_in_db(account_id)

    logger.info(f"[{account_name}] Initialisiere Browser-Instanz...")

    try:
        # Proxy in Playwright Format konvertieren (falls konfiguriert)
        pw_proxy = None
        if proxy_config and proxy_config.get("server"):
            pw_proxy = {
                "server": proxy_config["server"],
                "username": proxy_config.get("username", ""),
                "password": proxy_config.get("password", "")
            }

        # Browser starten
        browser = await playwright.chromium.launch(
            headless=False, # Für Tests sichtbar, später ggf True
            args=BROWSER_ARGS,
            proxy=pw_proxy
        )

        # Context mit gespeichertem Session-Cookie laden
        try:
            context = await browser.new_context(
                storage_state=session_file,
                viewport=VIEWPORT,
                locale=LOCALE,
                timezone_id=TIMEZONE_ID,
                user_agent=USER_AGENT,
            )
            logger.info(f"[{account_name}] Lade bestehende Session erfolgreich.")
        except Exception as e:
            logger.warning(f"[{account_name}] Keine Session gefunden oder fehlerhaft: {e}. Erstelle leeren Context.")
            # Falls Fallback nötig (sollte vorher per `main.py login <id>` erstellt werden)
            context = await browser.new_context(
                viewport=VIEWPORT,
                locale=LOCALE,
                timezone_id=TIMEZONE_ID,
                user_agent=USER_AGENT,
            )

        page = await context.new_page()
        await page.add_init_script(STEALTH_INIT_SCRIPT)
        
        # Test-Navigation um Proxy und Session zu validieren
        logger.info(f"[{account_name}] Instanz bereit. Führe Test-Navigation zu FB aus...")
        try:
            await page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=30000)
            if await page.locator('input[type="password"]').count() > 0:
                logger.error(f"[{account_name}] ACHTUNG: Session ist ausgelaufen, Login erforderlich!")
            else:
                logger.info(f"[{account_name}] Erfolgreich authentifiziert.")
        except Exception as e:
             logger.error(f"[{account_name}] Navigation fehlgeschlagen, evtl. Proxy offline? {e}")

        if task_func:
            logger.info(f"[{account_name}] Führe dedizierte CLI-Aufgabe aus...")
            await task_func(page, account_id, account, *args, **kwargs)
        else:
            # Starte den asynchronen Always On Daemon-Loop für diesen Account
            logger.info(f"[{account_name}] Übergabe an Always-On Daemon...")
            await run_account_loop(account_id, account, context, page)

    except Exception as e:
        logger.critical(f"[{account_name}] Fataler Absturz der Instanz: {e}", exc_info=True)


async def run_single_account_task(account_id: int, task_func, *args, **kwargs):
    """Startet Playwright isoliert für eine einzelne CLI-Operation für einen Account."""
    account = next((a for a in ACCOUNTS if a.get("id") == account_id), None)
    if not account:
        logger.error(f"Account mit ID {account_id} nicht in config.yaml gefunden.")
        return
        
    async with async_playwright() as playwright:
        await run_account(playwright, account, task_func, *args, **kwargs)


async def start_all_accounts():
    """
    Startet alle in config.yaml definierten Accounts parallel via asyncio.gather.
    """
    if not ACCOUNTS:
        logger.error("Keine Accounts in config.yaml konfiguriert!")
        return

    logger.info("="*60)
    logger.info(f"Multi-Account Manager startet {len(ACCOUNTS)} Instanzen...")
    logger.info("="*60)

    async with async_playwright() as playwright:
        # Erstelle Task-Liste für alle Accounts
        tasks = [run_account(playwright, acc) for acc in ACCOUNTS]
        
        # Führe sie gleichzeitig aus (blockiert bis alle fertig/abgestürzt sind)
        await asyncio.gather(*tasks)

    logger.info("Multi-Account Manager beendet.")
