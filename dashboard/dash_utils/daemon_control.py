"""
daemon_control.py - Steuert die Systemd Services der einzelnen Bot-Accounts
"""
import subprocess
import os

import psutil

def restart_daemon():
    """Startet den gesamten Bot Daemon neu."""
    return False, "Neustart via Dashboard unter Windows aktuell nicht unterstützt."

def is_daemon_running():
    """Prüft ob der Bot Main-Prozess läuft."""
    try:
        for proc in psutil.process_iter(['name', 'cmdline']):
            if proc.info['cmdline']:
                cmd = " ".join(proc.info['cmdline']).lower()
                if "python" in cmd and "main.py run" in cmd:
                    return True
        return False
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False
