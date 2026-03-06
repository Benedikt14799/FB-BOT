import streamlit as st
import pandas as pd
from dash_utils.supabase_client import sb

st.set_page_config(page_title="Account-Übersicht", layout="wide")

st.title("👤 Account Übersicht & Steuerung")

# Lade alle Accounts
@st.cache_data(ttl=10)
def load_accounts():
    res = sb.table("accounts").select("*").order("account_id").execute()
    return res.data

accounts = load_accounts()

if not accounts:
    st.warning("Noch keine Accounts in der Datenbank registriert. Bitte den Bot mindestens einmal starten (`__init_account_in_db`).")
    st.stop()

# Layout als Cards
for acc in accounts:
    with st.container(border=True):
        col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 2, 1])
        
        acc_id = acc.get("account_id")
        status = acc.get("status", "active")
        limit = acc.get("daily_limit", 80)
        sent_today = acc.get("messages_sent_today", 0)
        proxy = acc.get("proxy_ip", "Kein Proxy gesetzt")
        
        # Emoji Status
        if status == "active": stat_ico = "🟢 Aktiv"
        elif status == "paused": stat_ico = "⏸️ Pausiert"
        else: stat_ico = "🔴 Fehler"

        with col1:
            st.subheader(f"Account {acc_id}")
            st.write(stat_ico)
            
        with col2:
            st.write("**Heutiger Fortschritt**")
            st.progress(min(sent_today / max(limit, 1), 1.0))
            st.write(f"{sent_today} / {limit} Gesendet")
            
        with col3:
            st.write("**Proxy / IP**")
            st.code(proxy)
            if st.button("🔄 IP Wechsel", key=f"proxy_{acc_id}"):
                st.info("Proxy Wechsel angestoßen (WIP - erfordert API Aufruf an Provider)")
                
        with col4:
            new_limit = st.slider("Tageslimit anpassen", 0, 150, limit, key=f"slider_{acc_id}")
            if new_limit != limit:
                if st.button("💾 Speichern", key=f"save_{acc_id}"):
                    sb.table("accounts").update({"daily_limit": new_limit}).eq("account_id", acc_id).execute()
                    st.success("Limit geupdated!")
                    st.rerun()
                    
        with col5:
            new_status = "paused" if status == "active" else "active"
            btn_txt = "⏸ Pausieren" if status == "active" else "▶ Reaktivieren"
            
            if st.button(btn_txt, key=f"tog_{acc_id}"):
                sb.table("accounts").update({"status": new_status}).eq("account_id", acc_id).execute()
                st.rerun()

st.markdown("---")
st.caption("Ein Neustart des Daemons kann 15-30 Minuten dauern, bis Änderungen wie pausierte Accounts wirksam werden, da laufende Loops erst beendet werden.")
