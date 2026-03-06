"""
proxy_manager.py – Verifizierung des dedizierten Account-Proxys
Stellt sicher, dass jeder Account mit seiner residenten IP läuft und nicht die Datacenter-IP nutzt.
"""

import requests
from utils import logger
from monitor import monitor

def get_proxy(account_config: dict) -> dict:
    """Extrahiert die Proxy-URL (HTTP) aus der Account-Config."""
    proxy_config = account_config.get("proxy")
    if not proxy_config or not proxy_config.get("server"):
        return None
        
    server = proxy_config["server"].replace("http://", "").replace("https://", "")
    username = proxy_config.get("username", "")
    password = proxy_config.get("password", "")
    
    auth_str = f"{username}:{password}@" if username and password else ""
    # Wir benutzen das standard http scheme für requests
    proxy_url = f"http://{auth_str}{server}"
    
    return {
        "http": proxy_url,
        "https": proxy_url
    }

def test_proxy(account_id: int, proxy: dict) -> bool:
    """Führt einen API Request zu ipify aus, um die tatsächliche IP zu prüfen."""
    if not proxy:
        logger.error(f"[Acc {account_id}] Kein Proxy für diesen Account konfiguriert! Abbruch zum Schutz der VPS IP.")
        return False
        
    try:
        r = requests.get("https://api.ipify.org?format=json", proxies=proxy, timeout=15)
        ip = r.json().get("ip")
        logger.info(f"[Acc {account_id}] Proxy OK. Öffentliche Setup-IP: {ip}")
        return True
    except Exception as e:
        logger.error(f"[Acc {account_id}] Proxy FEHLER: {e}")
        return False
