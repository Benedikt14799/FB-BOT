"""
sender.py – Async Kern-Sendelogik & Funnel Routing

Dieser Dispatcher wird vom `account_manager.py` pro Account aufgerufen, holt sich 
seine Account-spezifischen Targets aus Supabase, generiert die passende Funnel-Nachricht 
(via llm_engine) und versendet diese über die übergebene async Playwright Page.
"""

import asyncio
import json
import random
from datetime import datetime
from playwright.async_api import Page, TimeoutError

from database import get_next_pending_recipient, update_recipient_state, log_message
from llm_engine import generate_message_for_stage
from monitor import monitor
from utils import logger
from conversation import check_inbox

from config import (
    MESSENGER_URL_TEMPLATE,
    MSG_BOX,
    SEND_BTN,
    ELEMENT_TIMEOUT_MS,
    GROUP_NAME
)

async def _human_delay(min_s: float, max_s: float):
    await asyncio.sleep(random.uniform(min_s, max_s))

async def _type_like_human(page: Page, selector: str, text: str):
    box = page.locator(selector).last
    await box.wait_for(state="visible", timeout=ELEMENT_TIMEOUT_MS)
    await box.click()
    for char in text:
        await page.keyboard.press(char)
        await asyncio.sleep(random.uniform(0.05, 0.15))

async def bot_cycle_for_account(account_id: int, context, page: Page):
    """
    Die asynchrone Endlosschleife für einen spezifischen Account.
    Prüft die Inbox, holt das nächste Target und sendet Nachrichten.
    """
    logger.info(f"[Acc {account_id}] Starte Bot-Zyklus...")
    
    # 1. Inbox checken (verändert ggf. DB-Zustände auf msg1_replied etc.)
    await check_inbox(page, account_id)
    
    # 2. Safety Check Daily Limits via Monitor (müsste account_id unterstützen, wir nehmen global)
    if not monitor.is_safe_to_continue(80): # Limit idealerweise pro Account
        logger.info(f"[Acc {account_id}] Tageslimit oder Error-Limit erreicht. Pausiere...")
        await asyncio.sleep(3600)
        return

    # 3. Nächstes Target holen
    target = get_next_pending_recipient(account_id)
    
    if not target:
        logger.info(f"[Acc {account_id}] Keine pending/reply Targets gefunden. Warte...")
        await asyncio.sleep(random.uniform(180, 480))
        return

    db_id = target["id"]
    contact_id = target["facebook_id"]
    contact_name = target["name"]
    current_state = target["conversation_state"]
    history_str = target.get("conversation_history", "[]")
    try:
        history = json.loads(history_str)
    except:
        history = []

    logger.info(f"[Acc {account_id}] Target: {contact_name} | State: {current_state}")

    # Bestimme die richtige Funnel-Nachricht
    stage_map = {
        "new": "msg1",
        "msg1_replied": "msg2",
        "msg2_replied": "msg3"
    }
    
    stage = stage_map.get(current_state)
    if not stage:
        logger.warning(f"[Acc {account_id}] Unbekannter oder nicht sendefähiger State: {current_state}. Überspringe.")
        await asyncio.sleep(60)
        return

    # Nachricht generieren via GPT-4o-mini
    message_text = generate_message_for_stage(stage, contact_name, GROUP_NAME, history)
    
    if not message_text:
        logger.error(f"[Acc {account_id}] Konnte keine Nachricht für {stage} generieren.")
        return

    logger.info("=" * 60)
    logger.info(f"[Acc {account_id}] Sende [{stage}] an: {contact_name}\nText: {message_text}")
    logger.info("=" * 60)

    success = False
    error_msg = None

    try:
        messenger_url = MESSENGER_URL_TEMPLATE.format(contact_id=contact_id)
        
        # Navigation
        await page.goto(messenger_url, wait_until="domcontentloaded", timeout=40_000)
        await _human_delay(2.0, 4.0)

        # Text reintippen
        logger.info(f"[Acc {account_id}] Tippe Nachricht...")
        await _type_like_human(page, MSG_BOX, message_text)
        await _human_delay(0.5, 1.2)

        # Senden
        send_button = page.locator(SEND_BTN).last
        if await send_button.is_visible():
            await send_button.click()
        else:
            await page.keyboard.press("Enter")

        await _human_delay(2.0, 4.0)
        logger.info(f"[Acc {account_id}] Nachricht erfolgreich gesendet!")
        success = True
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[Acc {account_id}] Abbruch beim Senden: {error_msg}")
        
    # Lokale History updaten
    if success:
        history.append({"sender": "bot", "text": message_text})
        
        # State fortschreiben
        next_state = current_state
        if current_state == "new": next_state = "msg1_sent"
        elif current_state == "msg1_replied": next_state = "msg2_sent"
        elif current_state == "msg2_replied": next_state = "offer_sent"
        
        update_recipient_state(db_id, next_state, account_id, {
            "conversation_history": json.dumps(history)
        })
        log_message(contact_id, 0, message_text, True)
    else:
        log_message(contact_id, 0, message_text, False, error_msg)

    # Human Delay bis zum nächsten Target (3-8 Min + Micro)
    delay_s = random.uniform(180, 480) + random.uniform(5, 30)
    logger.info(f"[Acc {account_id}] Pausiere für {delay_s/60:.1f} Minuten nach Zyklus...")
    await asyncio.sleep(delay_s)
