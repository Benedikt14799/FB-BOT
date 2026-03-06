"""
safe_login.py – Auto-Login mit Retries für den Always On Daemon
Fängt abgelaufene Sessions auf und versucht sich neu einzuloggen.
"""
import asyncio
from playwright.async_api import Page
from monitor import monitor
from utils import logger, human_delay

MAX_RETRIES = 3
RETRY_WAIT = 30 * 60       # 30 Minuten
LONG_PAUSE = 24 * 60 * 60  # 24 Stunden

async def automated_login(account: dict, page: Page) -> bool:
    """Versucht einen automatisierten Login per Playwright (ohne 2FA-Support)."""
    email = account.get("email")
    password = account.get("password")
    
    if not email or not password:
        logger.error(f"[{account['name']}] Fehlende Login-Daten in config!")
        return False
        
    try:
        await page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=40000)
        
        # Prüfen, ob wir nicht ohnehin schon eingeloggt sind
        if await page.locator('input[type="password"]').count() == 0:
            return True # Schon eingeloggt
            
        # Email & Passwort eingeben
        await page.locator('input[type="text"], input[type="email"]').first.fill(email)
        await asyncio.sleep(1)
        await page.locator('input[type="password"]').fill(password)
        await asyncio.sleep(1)
        
        # Sende-Button
        await page.locator('button[name="login"]').click()
        await page.wait_for_timeout(10000)
        
        # Prüfen, ob Passwort-Feld immer noch da ist (Login fehlgeschlagen oder 2FA)
        if await page.locator('input[type="password"]').count() > 0:
            return False
            
        # Erfolgreich eingeloggt
        # Session abspeichern (macht account_manager.py normalerweise, aber wir können es dem context sagen)
        # Weil context in account_manager wohnt, prüfen wir in main return
        return True
    except Exception as e:
        logger.error(f"[{account['name']}] Automatischer Login fehlgeschlagen: {e}")
        return False

async def safe_login(account: dict, page: Page, context) -> bool:
    """Wrapper Funktion mit Max-Retries und Alerts."""
    account_id = account.get("id")
    account_name = account.get("name")
    
    # 1. Check if logged in already implicitly
    try:
        await page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=30000)
        if await page.locator('input[type="password"]').count() == 0:
            logger.info(f"[{account_name}] Erfolgreich authentifiziert via Cookies.")
            return True
    except Exception as e:
        logger.error(f"[{account_name}] Navigation fehlgeschlagen: {e}")
        return False

    logger.warning(f"[{account_name}] ACHTUNG: Session ist ausgelaufen, Login erforderlich!")
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            success = await automated_login(account, page)
            if success:
                logger.info(f"[Login OK] {account_name} – Versuch {attempt}")
                # Session Speichern
                session_file = account.get("session_file")
                if session_file:
                    await context.storage_state(path=session_file)
                return True
            else:
                logger.warning(f"[Login Fehlgeschlagen] Versuch {attempt}/{MAX_RETRIES} für {account_name}")
        except Exception as e:
            logger.error(f"[Login Exception] {e} – Versuch {attempt}/{MAX_RETRIES} für {account_name}")
        
        if attempt < MAX_RETRIES:
            logger.info(f"[{account_name}] Warte {RETRY_WAIT // 60} Minuten vor nächstem Versuch...")
            await asyncio.sleep(RETRY_WAIT)

    monitor.send_alert(f"🔴 {account_name}: Login nach {MAX_RETRIES} Versuchen gescheitert. 24h Pause.")
    await asyncio.sleep(LONG_PAUSE)
    return False
