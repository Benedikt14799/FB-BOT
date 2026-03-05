"""
conversation.py – Inbox Monitoring & State Updates

Sucht im Playwright Context nach der Facebook Messenger Inbox,
liest neue Nachrichten-Antworten aus und aktualisiert den 
Database State ("msg1_replied", "msg2_replied").
"""

import asyncio
import json
from datetime import datetime
from playwright.async_api import Page
from utils import logger
from database import update_recipient_state

async def check_inbox(page: Page, account_id: int):
    """
    Routinemäßiger Check der Facebook Inbox für diesen Account.
    Prüft auf '.unread-indicator' (ungelesene Nachrichten)
    und updatet den DB-Status für den nächsten Funnel-Schritt.
    """
    logger.info(f"[Acc {account_id}] Starte Inbox Check...")
    
    try:
        # Navigiere zur Messenger-Übersicht (falls nicht schon dort)
        await page.goto("https://www.facebook.com/messages/t/", wait_until="networkidle", timeout=30000)
        
        # Warte kurz, bis die Chats geladen sind
        await asyncio.sleep(3)
        
        # Finde alle Chat-Elemente in der Seitenleiste
        # (Facebook ändert relative oft Klassennamen, XPath/ARIA-Labels sind hier robuster,
        # zur Vereinfachung nutzen wir für den PoC exemplarisch aria-label Check)
        
        # Finde Threads, die das Wort "Ungelesen" im Label haben (oder dicke Schrift)
        # Eine typische FB Messenger DOM-Struktur hat oft aria-label mit "1 ungelesene Nachricht"
        unread_conversations = await page.locator("div[aria-label*='ungelesen'], div[aria-label*='Unread']").all()
        
        if not unread_conversations:
            logger.info(f"[Acc {account_id}] Keine neuen/ungelesenen Nachrichten gefunden.")
            return

        logger.info(f"[Acc {account_id}] {len(unread_conversations)} ungelesene Chat(s) gefunden. Verarbeite...")
        
        for index, conv in enumerate(unread_conversations):
            # Kick in to read the message
            await conv.click(timeout=5000)
            await asyncio.sleep(2) # Lade Chatverlauf
            
            # Profilnamen aus dem Header extrahieren
            header_name_locator = page.locator("h2 span, h1 span").first
            contact_name = "Unbekannt"
            if await header_name_locator.count() > 0:
                 contact_name = await header_name_locator.inner_text()
            
            # Letzte Nachricht extrahieren
            messages = await page.locator("div[role='row']").all()
            if not messages:
                continue
                
            last_message_container = messages[-1]
            last_text = await last_message_container.inner_text()
            last_text = last_text.strip() if last_text else "Media/Voice"
            
            logger.info(f"[Acc {account_id}] Neue Antwort von '{contact_name}': {last_text[:40]}...")
            
            # -- Abgleich mit Datenbank --
            # In einer echten Umgebung bräuchte man hier idealerweise die Facebook-ID
            # Facebook speichert die ID oft in der URL (/messages/t/10002939...)
            current_url = page.url
            contact_id = current_url.split("/")[-1].split("?")[0]
            if not contact_id.isdigit():
                 # Fallback: Suche nach dem Namen in unserer DB bei diesem Account
                 # In Production sollte zwingend mit der ID gearbeitet werden
                 pass 
            
            # Lade bestehenden Empfänger
            from database import supabase
            res = supabase.table("recipients").select("*").eq("account_id", account_id).eq("facebook_id", contact_id).execute()
            
            if res.data:
                target = res.data[0]
                db_id = target["id"]
                current_state = target["conversation_state"]
                
                # Append to conversation history
                history = json.loads(target["conversation_history"] or "[]")
                history.append({"sender": "contact", "text": last_text})
                
                # State Machine Progression
                new_state = current_state
                if current_state == "msg1_sent":
                    new_state = "msg1_replied"
                elif current_state == "msg2_sent":
                    new_state = "msg2_replied"
                elif current_state == "active_funnel" or "replied" in current_state:
                     new_state = current_state # Beibehalten
                else:
                    new_state = "converted" # Wildcard
                    
                update_recipient_state(db_id, new_state, account_id, {
                    "conversation_history": json.dumps(history),
                    "reply_received_at": datetime.utcnow().isoformat()
                })
                logger.info(f"[Acc {account_id}] Status für {contact_name} geupdatet auf: {new_state}")
            else:
                logger.warning(f"[Acc {account_id}] Konnte Chat '{contact_name}' (ID: {contact_id}) nicht in lokaler DB finden.")
                
        # Fertig
        await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"[Acc {account_id}] Fehler beim Inbox Check: {e}")
