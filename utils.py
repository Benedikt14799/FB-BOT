"""
utils.py – Human-Behavior-Utilities und Logging für den FB Messenger Bot.
"""

import time
import random
import logging
import sys
from pathlib import Path
from datetime import datetime

from playwright.sync_api import Page


# ─────────────────────────────────────────────
# Logging Setup
# ─────────────────────────────────────────────

def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """
    Konfiguriert strukturiertes Logging auf Konsole und in Datei.
    Log-Datei: logs/bot_YYYY-MM-DD.log
    """
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)

    log_filename = log_dir / f"bot_{datetime.now().strftime('%Y-%m-%d')}.log"

    formatter = logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    logger = logging.getLogger("fb_bot")
    logger.setLevel(level)

    # Konsole
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Datei
    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


logger = setup_logging()


# ─────────────────────────────────────────────
# Human Behavior Utilities
# ─────────────────────────────────────────────

def human_delay(min_s: float = 0.8, max_s: float = 2.5) -> None:
    """
    Zufälliger Delay zur Simulation menschlichen Verhaltens.
    Bitte nie auf 0 setzen – Facebook analysiert Timing-Muster.
    """
    delay = random.uniform(min_s, max_s)
    time.sleep(delay)


def type_like_human(page: Page, selector: str, text: str) -> None:
    """
    Sicheres Eintragen von Text in das Messenger-Eingabefeld.
    Nutzt Focus und press_sequentially statt raw keyboard.type, um
    Probleme mit Newlines, Emojis und Fokusverlust zu vermeiden.

    Args:
        page:     Playwright-Page-Objekt
        selector: CSS-/ARIA-Selektor des Textfelds
        text:     Der zu tippende Text
    """
    try:
        locator = page.locator(selector).last
        
        # Sicherstellen, dass das Element im Viewport ist und Fokus hat
        locator.scroll_into_view_if_needed()
        locator.click()
        human_delay(0.3, 0.8)

        # Bei Facebook Messenger (Draft.js / Lexical Editor) ist press_sequentially
        # teilweise problematisch mit Newlines (\n), da Enter die Nachricht sendet.
        # Lösung: Wir splitten beim Zeilenumbruch und machen manuell Shift+Enter.
        logger.info("Tippe Text ein...")
        
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if line:
                locator.press_sequentially(line, delay=random.randint(20, 80))
            
            # Wenn es nicht die letzte Zeile ist, mache einen Zeilenumbruch im Editor
            if i < len(lines) - 1:
                page.keyboard.press("Shift+Enter")
                human_delay(0.1, 0.3)
        
        human_delay(0.4, 1.0)
    except Exception as e:
        logger.error(f"Fehler beim Tippen: {e}")
        # Fallback auf einfaches fill, falls press_sequentially scheitert
        try:
            logger.info("Fallback: Nutze locator.fill()...")
            page.locator(selector).last.fill(text)
            human_delay(0.5, 1.0)
        except Exception as e2:
            logger.error(f"Fallback-Tippen fehlgeschlagen: {e2}")


def random_scroll(page: Page) -> None:
    """
    Minimales Scroll-Verhalten zur Session-Legitimierung.
    Scrollt leicht nach unten und wieder zurück.
    """
    scroll_amount = random.randint(80, 350)
    page.mouse.wheel(0, scroll_amount)
    human_delay(0.4, 1.0)
    # Manchmal auch leicht zurück scrollen
    if random.random() > 0.5:
        page.mouse.wheel(0, -random.randint(30, 100))
        human_delay(0.3, 0.7)


def random_mouse_move(page: Page) -> None:
    """
    Zufällige Mausbewegung zur Simulation menschlichen Verhaltens.
    """
    x = random.randint(200, 1200)
    y = random.randint(200, 700)
    page.mouse.move(x, y, steps=random.randint(5, 15))
    human_delay(0.2, 0.5)


# ─────────────────────────────────────────────
# Debug Utilities
# ─────────────────────────────────────────────

def take_debug_screenshot(page: Page, name: str = "debug") -> str:
    """
    Erstellt einen Debug-Screenshot im Projektverzeichnis.
    Gibt den Dateipfad zurück.
    """
    screenshots_dir = Path(__file__).parent / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = str(screenshots_dir / f"{name}_{timestamp}.png")

    try:
        page.screenshot(path=path, full_page=False)
        logger.info(f"Debug-Screenshot gespeichert: {path}")
    except Exception as e:
        logger.warning(f"Screenshot fehlgeschlagen: {e}")

    return path


def check_profile_exists(user_data_dir: str) -> bool:
    """
    Prüft ob ein persistentes Chrome-Profil vorhanden ist.
    """
    profile_path = Path(user_data_dir)
    exists = profile_path.exists() and any(profile_path.iterdir())
    if not exists:
        logger.warning(
            f"Kein Chrome-Profil gefunden unter: {user_data_dir}\n"
            "Bitte zuerst 'python main.py login' ausführen."
        )
    return exists
