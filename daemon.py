"""
daemon.py – Das 'Always On' Herzstück der Automatisierung.

Steuert den Bot-Zyklus pro Account in Endlosschleife, prüft Limits, Alter
und kombiniert Natural Behavior mit gezieltem Messaging (Funnel).
"""

import asyncio
import random
from datetime import datetime
from playwright.async_api import Page

from config import ACCOUNTS
from utils import logger
from database import get_account_age_days, get_messages_sent_today, record_message_sent
from monitor import monitor
from natural_behavior import run_session as natural_run_session, scroll_feed
from sender import send_single_message

def get_daily_message_limit(account_age_days: int) -> int:
    """Basis-Limit abhängig vom Alter des Accounts."""
    if account_age_days < 8:
        return 0   # Nur natürliches Verhalten, keine Nachrichten
    elif account_age_days < 15:
        return 5   # Erste vorsichtige Nachrichten
    elif account_age_days < 22:
        return 10  # Steigerung
    elif account_age_days < 30:
        return 20  # Normalbetrieb
    else:
        return 30  # Vollbetrieb ab Tag 30

def get_weekend_message_limit(base_limit: int) -> int:
    """Halbiert das Limit am Wochenende."""
    if datetime.now().weekday() >= 5:  # Sa oder So
        return int(base_limit * 0.5)
    return base_limit

def get_actual_daily_limit(age: int) -> int:
    """Berechnet das finale Limit inklusive Wochenends-Malus und ±20% Zufall."""
    base_limit = get_daily_message_limit(age)
    if base_limit == 0:
        return 0
    weekend_limit = get_weekend_message_limit(base_limit)
    if weekend_limit == 0:
        return 0
    
    variance = int(weekend_limit * 0.2)
    return random.randint(max(1, weekend_limit - variance), weekend_limit + variance)

def should_rest_today(account: dict) -> bool:
    """Prüft, ob der Account heute laut config ruhen soll."""
    day_of_week = datetime.now().weekday()
    rest_days = account.get("rest_days", [])
    return day_of_week in rest_days

def should_do_short_session() -> bool:
    """20% Chance, dass der User nur ganz kurz online kommt und dann verschwindet."""
    return random.random() < 0.2

def is_active_window() -> bool:
    """Aktivitätsfenster 08:00 – 21:00 Uhr."""
    hour = datetime.now().hour
    return 8 <= hour <= 21

async def run_account_loop(account_id: int, account: dict, context, page: Page):
    """Der Always-On Endlos-Zyklus für EINEN Account."""
    logger.info(f"[{account.get('name')}] Daemon Loop gestartet.")

    while True:
        try:
            # 1. Ist gerade Tag/Nacht?
            if not is_active_window():
                sleep_hours = random.uniform(8, 11)  # Bis zum nächsten Morgen warten
                logger.info(f"[Acc {account_id}] Nachtruhe. Schlafe für {sleep_hours:.1f}h...")
                await asyncio.sleep(sleep_hours * 3600)
                continue

            # 2. Ist heute Ruhetag?
            if should_rest_today(account):
                logger.info(f"[Acc {account_id}] Hat heute Ruhetag. Warte bis morgen...")
                await asyncio.sleep(12 * 3600) # Grober Sprung bis zum nächsten Check
                continue

            # 3. Ist es eine kurze Anti-Bot-Session?
            if should_do_short_session():
                logger.info(f"[Acc {account_id}] Macht heute nur eine 3-Minuten Kurz-Session...")
                await scroll_feed(page, account_id, seconds=random.randint(60, 180))
                # Sehr lange Pause danach (Halber Tag oft)
                logger.info(f"[Acc {account_id}] Kurz-Session beendet. Geht offline.")
                await asyncio.sleep(random.uniform(3, 8) * 3600)
                continue
            
            age = get_account_age_days(account_id)
            daily_limit = get_actual_daily_limit(age)
            already_sent = get_messages_sent_today(account_id)
            remaining = daily_limit - already_sent

            logger.info(f"[Acc {account_id}] Daily Status: Age={age}d, Limit={daily_limit}, Sent={already_sent}, Remaining={remaining}")
            
            # --- START NATURAL SESSION ---
            await natural_run_session(page, account_id, account)
            # --- END NATURAL SESSION ---

            # --- START MESSAGING SESSION (Wenn Limit > 0) ---
            if remaining > 0 and monitor.is_safe_to_continue(account_id, daily_limit):
                batch_size = random.randint(1, min(remaining, 4)) # Sende nie mehr als 1-4 am Stück
                logger.info(f"[Acc {account_id}] Bot versucht nun bis zu {batch_size} Nachrichten zu senden (im Funnel oder neu).")
                
                sent_in_batch = 0
                for _ in range(batch_size):
                    success = await send_single_message(account_id, context, page)
                    if success:
                        record_message_sent(account_id)
                        sent_in_batch += 1
                        # Längere Pause zwischen Nachrichten im selben Batch
                        await asyncio.sleep(random.uniform(180, 480))
                    else:
                        break # Keine Targets mehr oder Fehler -> Batch beenden
                        
                if sent_in_batch > 0:
                    logger.info(f"[Acc {account_id}] Messenger Batch beendet. ({sent_in_batch} gesendet)")
                    # Session durch Messaging nochmal mit Random Surf abschließen
                    await scroll_feed(page, account_id, seconds=int(random.uniform(120, 300)))
            
            # 5. Pause zwischen Sessions (human-like)
            delay = random.uniform(1800, 3600) # 30–60 min Offline-Zeit
            logger.info(f"[Acc {account_id}] Geht offline für {delay/60:.1f} Minuten.")
            await asyncio.sleep(delay)

        except Exception as e:
            logger.error(f"[Acc {account_id}] Fehler in der Haupt-Loop: {e}", exc_info=True)
            # Im Fehlerfall 30 Minuten abkühlen
            await asyncio.sleep(1800)
