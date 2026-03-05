"""
warmup.py – Account-Warming Modul zur Simulation menschlichen Verhaltens

Bewegt sich zufällig auf Facebook, ohne Nachrichten zu senden.
Dient zur Aufrechterhaltung des Trust-Scores beim Meta-Algorithmus.
"""

import asyncio
import random
from playwright.async_api import Page, TimeoutError
from utils import logger

TARGETS = [
    "https://www.facebook.com/",
    "https://www.facebook.com/watch/",
    "https://www.facebook.com/groups/feed/",
    "https://www.facebook.com/friends/"
]

async def _human_delay(min_s: float, max_s: float):
    await asyncio.sleep(random.uniform(min_s, max_s))

async def _random_scroll(page: Page):
    scroll_amount = random.randint(80, 450)
    await page.mouse.wheel(0, scroll_amount)
    await _human_delay(0.4, 1.2)
    if random.random() > 0.6:
        await page.mouse.wheel(0, -random.randint(30, 150))
        await _human_delay(0.3, 0.8)

async def _random_mouse_move(page: Page):
    x = random.randint(200, 1200)
    y = random.randint(200, 700)
    await page.mouse.move(x, y, steps=random.randint(5, 15))
    await _human_delay(0.2, 0.5)

async def perform_warmup(page: Page, account_id: int):
    """Simuliert menschliches Surfen für diesen spezifischen Account."""
    logger.info(f"[Acc {account_id}] Starte Account-Warmup (Newsfeed Surfing)")

    try:
        pages_to_visit = random.sample(TARGETS, random.randint(2, 4))
        
        for url in pages_to_visit:
            logger.info(f"[Acc {account_id}] Navigiere zu: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=40_000)
            await _human_delay(3.0, 6.0)
            
            scrolls = random.randint(3, 8)
            for _ in range(scrolls):
                await _random_scroll(page)
                await _human_delay(1.5, 4.0)
                
            await _random_mouse_move(page)
            
    except TimeoutError:
        logger.warning(f"[Acc {account_id}] Timeout beim Warmup (Proxy zu langsam?).")
    except Exception as e:
        logger.error(f"[Acc {account_id}] Fehler während des Warmups: {e}")
        
    logger.info(f"[Acc {account_id}] Warmup beendet.")
