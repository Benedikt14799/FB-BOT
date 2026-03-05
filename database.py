"""
database.py – Supabase Anbindung

Verwaltet die Datenbank-Operationen (Suchen, Hinzufügen, Status-Updates) 
über die Supabase REST API (Python Client).
"""

import os
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

from utils import logger
from config import MIN_SCORE_FOR_MESSAGE

load_dotenv()

URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")

if not URL or not KEY:
    logger.error("Supabase URL oder KEY fehlen in der .env-Datei!")

supabase: Client = create_client(URL, KEY)


def add_pending_recipient(facebook_id: str, name: str, priority: int = 3, person_score: int = 0, common_groups: list = None) -> bool:
    """
    Fügt einen neuen Empfänger in die Tabelle 'recipients' hinzu.
    Setzt Initiale Phase-1-Scoring-Werte und default conversation_state auf 'new'.
    """
    try:
        response = supabase.table("recipients").insert({
            "facebook_id": facebook_id,
            "name": name,
            "status": "pending",
            "conversation_state": "new",
            "priority": priority,
            "person_score": person_score,
            "common_groups": common_groups or []
        }).execute()
        
        return True
    except Exception as e:
        if "duplicate key" not in str(e).lower():
            logger.error(f"Fehler beim Hinzufügen des Empfängers {facebook_id}: {e}")
        return False


def get_next_pending_recipient(account_id: int) -> dict:
    """
    Holt sich den priorisierten anstehenden Empfänger für Phase 2 für EINEN spezifischen Account.
    Bedingung: 
    1. account_id = NULL (neuer Lead, wird dem Account zugewiesen) ODER account_id = dieses Account ID
    2. status = 'pending' ODER 'active_funnel'
    """
    try:
        # Complex OR query requires PostgREST syntax string 
        # For simplicity, we fetch assigning logic first:
        
        # 1. Prio: Gib mir jemand, der auf MEINE (account_id) Nachricht gewartet hat und jetzt dran ist
        response_active = supabase.table("recipients") \
            .select("*") \
            .eq("account_id", account_id) \
            .in_("conversation_state", ["msg1_replied", "msg2_replied"]) \
            .order("reply_received_at", desc=False) \
            .limit(1).execute()
            
        if response_active.data:
            return response_active.data[0]
            
        # 2. Prio: Gib mir einen komplett neuen (Score >= 40)
        response_new = supabase.table("recipients") \
            .select("*") \
            .eq("conversation_state", "new") \
            .is_("account_id", "null") \
            .gte("person_score", MIN_SCORE_FOR_MESSAGE) \
            .order("priority", desc=False) \
            .order("created_at", desc=False) \
            .limit(1).execute()
            
        if response_new.data:
            return response_new.data[0]
            
        return None
    except Exception as e:
        logger.error(f"[DB] Fehler beim Abrufen anstehender Empfänger für Account {account_id}: {e}")
        return None


def update_recipient_state(db_id: int, state: str, account_id: int = None, additional_payload: dict = None) -> bool:
    """
    Aktualisiert den conversation_state (zB 'msg1_sent'). 
    Bindet den Kontakt bei der 1. Nachricht an den account_id.
    """
    try:
        payload = {"conversation_state": state}
        if account_id is not None:
             payload["account_id"] = account_id
             
        if state == "msg1_sent" or state == "msg2_sent" or state == "offer_sent":
             payload["status"] = "active_funnel"
        elif state == "blacklisted":
             payload["status"] = "blacklisted"
             
        if additional_payload:
             payload.update(additional_payload)
             
        supabase.table("recipients").update(payload).eq("id", db_id).execute()
        return True
    except Exception as e:
        logger.error(f"Fehler beim Update des Empfänger-Status {db_id}: {e}")
        return False



def log_message(recipient_id: str, variant_id: int, content: str, success: bool, error_msg: str = None):
    """
    Schreibt einen Log-Eintrag für eine versendete Nachricht in die Datenbank.
    """
    try:
        supabase.table("message_logs").insert({
            "recipient_id": recipient_id,
            "variant_id": variant_id,
            "content": content,
            "success": success,
            "error_message": error_msg
        }).execute()
    except Exception as e:
        logger.error(f"Datenbank Logging fehlgeschlagen: {e}")

# --- Account Tracking Logic ---

def init_account_in_db(account_id: int):
    """Initialisiert den Account in der Datenbank, falls er noch nicht existiert."""
    try:
        response = supabase.table("accounts").select("account_id").eq("account_id", account_id).execute()
        if not response.data:
            supabase.table("accounts").insert({"account_id": account_id}).execute()
            logger.info(f"[DB] Account {account_id} in der Datenbank initialisiert.")
    except Exception as e:
        logger.error(f"[DB] Fehler beim Initialisieren von Account {account_id}: {e}")

def get_account_age_days(account_id: int) -> int:
    """Berechnet das Alter des Accounts in Tagen basierend auf first_login_at."""
    try:
        response = supabase.table("accounts").select("first_login_at").eq("account_id", account_id).execute()
        if response.data:
            first_login_str = response.data[0].get("first_login_at")
            if first_login_str:
                first_date = datetime.fromisoformat(first_login_str.replace("Z", "+00:00")).replace(tzinfo=None)
                age = (datetime.now() - first_date).days
                return max(0, age)
        return 0
    except Exception as e:
        logger.error(f"[DB] Fehler beim Abrufen des Alters für Account {account_id}: {e}")
        return 0

def update_daily_account_stats(account_id: int):
    """Setzt messages_sent_today zurück, wenn ein neuer Tag angebrochen ist."""
    try:
        response = supabase.table("accounts").select("last_activity_date").eq("account_id", account_id).execute()
        if response.data:
            last_date_str = response.data[0].get("last_activity_date")
            today_str = datetime.now().strftime("%Y-%m-%d")
            
            if last_date_str != today_str:
                supabase.table("accounts").update({
                    "messages_sent_today": 0,
                    "last_activity_date": today_str
                }).eq("account_id", account_id).execute()
    except Exception as e:
        logger.error(f"[DB] Fehler beim Update der Daily Stats für Account {account_id}: {e}")

def get_messages_sent_today(account_id: int) -> int:
    """Gibt die Anzahl der heute gesendeten Nachrichten für diesen Account zurück."""
    update_daily_account_stats(account_id)
    try:
        response = supabase.table("accounts").select("messages_sent_today").eq("account_id", account_id).execute()
        if response.data:
             return response.data[0].get("messages_sent_today", 0)
        return 0
    except Exception as e:
        logger.error(f"[DB] Fehler beim Abrufen von messages_sent_today für Account {account_id}: {e}")
        return 0

def record_message_sent(account_id: int):
    """Zählt messages_sent_today für den Account hoch."""
    try:
        current = get_messages_sent_today(account_id)
        supabase.table("accounts").update({"messages_sent_today": current + 1}).eq("account_id", account_id).execute()
    except Exception as e:
        logger.error(f"[DB] Fehler beim Inkrementieren von messages_sent_today für Account {account_id}: {e}")

def is_already_contacted(facebook_id: str) -> bool:
    """Prüft, ob diese Person jemals (von irgendeinem Account) angeschrieben oder erfasst wurde."""
    try:
        response = supabase.table("recipients").select("id").eq("facebook_id", facebook_id).execute()
        return len(response.data) > 0
    except Exception as e:
        logger.error(f"[DB] Fehler bei is_already_contacted für {facebook_id}: {e}")
        return False

