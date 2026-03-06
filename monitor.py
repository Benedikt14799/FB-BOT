"""
monitor.py – Fortschrittliche Logging, Alarm- und Stop-Logik pro Account

Erstellt tägliche .log Dateien und fasst diese zusammen. Stoppt den
Bot-Betrieb (Daemon) für einen Account temporär, wenn zu viele Timeouts
passieren. Beinhaltet die Funnel-Blacklisting-Logik (Timeout nach 48h).
"""

import os
from datetime import datetime

from utils import logger
from database import supabase

LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

class BotMonitor:
    def __init__(self, max_consecutive_errors: int = 3):
        self.max_consecutive_errors = max_consecutive_errors
        self.consecutive_errors = {}
        self.daily_count = {}
        self.daily_fails = {}
        self._set_daily_logfile()

    def _set_daily_logfile(self):
        """Erstellt einen neuen Dateinamen anhand des aktuellen Datums."""
        today = datetime.now().strftime("%Y-%m-%d")
        self.current_log_file = os.path.join(LOGS_DIR, f"bot_run_{today}.log")

    def send_alert(self, message: str, alert_type: str = "SYSTEM_WARNING", account_id: str = "GLOBAL"):
        """
        Sendet eine Warnung an das Streamlit-Dashboard (in die `alerts` Tabelle).
        Zusätzlich auch ins Log.
        """
        logger.warning(f"[ALERT] {alert_type}: {message.strip()}")
        
        try:
            from database import supabase
            if supabase:
                supabase.table("alerts").insert({
                    "account_id": str(account_id),
                    "type": alert_type,
                    "detail": message.strip()
                }).execute()
        except Exception as e:
            logger.error(f"Konnte Alert nicht an DB senden: {e}")

    def _write_to_log(self, message: str):
        """Schreibt in die tägliche Protokolldatei."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.current_log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")

    def record_success(self, account_id: int):
        self.consecutive_errors[account_id] = 0
        self.daily_count[account_id] = self.daily_count.get(account_id, 0) + 1
        msg = f"[Acc {account_id}] SUCCESS: Nachricht erfolgreich versendet. (Count heute: {self.daily_count[account_id]})"
        logger.info(msg)
        self._write_to_log(msg)

    def record_error(self, account_id: int, error_msg: str = ""):
        self.consecutive_errors[account_id] = self.consecutive_errors.get(account_id, 0) + 1
        self.daily_fails[account_id] = self.daily_fails.get(account_id, 0) + 1
        msg = f"[Acc {account_id}] ERROR: Fehler beim Senden. Serie: {self.consecutive_errors[account_id]}/{self.max_consecutive_errors} - {error_msg}"
        logger.warning(msg)
        self._write_to_log(msg)

    def is_safe_to_continue(self, account_id: int, limit: int = 80) -> bool:
        # Check consecutive errors
        errors = self.consecutive_errors.get(account_id, 0)
        if errors >= self.max_consecutive_errors:
            msg = f"[Acc {account_id}] NOTSTOPP: Zu viele Fehler in Folge ({errors}). Beende den Bot-Zyklus temporär."
            logger.critical(msg)
            self._write_to_log(f"CRITICAL: {msg}")
            return False
        
        # Check daily limit
        count = self.daily_count.get(account_id, 0)
        if count >= limit:
            msg = f"[Acc {account_id}] Tageslimit erreicht ({count}/{limit}). Mache Feierabend für heute."
            logger.info(msg)
            self._write_to_log(msg)
            return False
            
        return True

    def reset_daily_count(self):
        """Zieht Bilanz für den abgelaufenen Tag pro Account und setzt Zähler zurück."""
        self._write_to_log("="*40)
        self._write_to_log("Tagesabschluss (Multi-Account):")
        for acc_id in self.daily_count.keys():
            self._write_to_log(f" [Acc {acc_id}] Gesendet: {self.daily_count.get(acc_id, 0)}, Fehler: {self.daily_fails.get(acc_id, 0)}")
        self._write_to_log("="*40)
        
        self.daily_count.clear()
        self.daily_fails.clear()
        self.consecutive_errors.clear()
        self._set_daily_logfile()
        
        msg = "Tageslimit wurde für alle Accounts zurückgesetzt (neuer Tag)."
        logger.info(msg)
        self._write_to_log(msg)
        
        # Blacklist Checks am Ende des Tages ausführen
        self.run_blacklist_checks()

    def run_blacklist_checks(self):
        """
        Prüft ob Funnel-Kontakte > 48h nicht geantwortet haben.
        Setzt deren Status/State auf 'blacklisted'.
        """
        try:
            # Hole alle 'active_funnel', um Timeout zu prüfen
            response = supabase.table("recipients").select("id, last_contact, conversation_state").eq("status", "active_funnel").execute()
            
            data = response.data
            count = 0
            if data:
                now = datetime.now()
                for row in data:
                    state = row.get("conversation_state")
                    if state in ["msg1_sent", "msg2_sent", "offer_sent"]:
                        last_contact_str = row.get("last_contact")
                        if last_contact_str:
                            last_date = datetime.fromisoformat(last_contact_str.replace("Z", "+00:00")).replace(tzinfo=None)
                            diff = (now - last_date).total_seconds() / 3600 # hours
                            if diff > 48:
                                # Blackliste diesen Kontakt wg. Funnel Timeout
                                supabase.table("recipients").update({
                                    "status": "blacklisted",
                                    "conversation_state": "blacklisted_timeout"
                                }).eq("id", row["id"]).execute()
                                count += 1
            
            msg = f"Funnel Blacklist-Lauf beendet. {count} inaktive Kontakte gesperrt."
            logger.info(msg)
            self._write_to_log(msg)
            
        except Exception as e:
            logger.error(f"Fehler beim Ausführen der Blacklist Checks: {e}")

# Global singleton
monitor = BotMonitor()
