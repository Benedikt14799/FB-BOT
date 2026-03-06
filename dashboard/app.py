import streamlit as st
from dash_utils.supabase_client import sb
from dash_utils.daemon_control import is_daemon_running, restart_daemon

st.set_page_config(
    page_title="FB Bot Control",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- PASSWORD PROTECTION ---
def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        if st.session_state["password"] == st.secrets.get("auth", {}).get("password", "admin"):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Passwort", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Passwort", type="password", on_change=password_entered, key="password")
        st.error("😕 Passwort inkorrekt")
        return False
    else:
        return True

if not check_password():
    st.stop()

# --- MAIN APP ---
st.title("🤖 FB Bot Control Dashboard")

col1, col2, col3 = st.columns(3)

# Metrics holen
try:
    acc_res = sb.table("accounts").select("status").execute()
    active_accs = sum(1 for item in acc_res.data if item.get("status") == "active")
    paused_accs = sum(1 for item in acc_res.data if item.get("status") == "paused")
    
    alert_res = sb.table("alerts").select("id").eq("resolved", False).execute()
    open_alerts = len(alert_res.data)
except Exception as e:
    st.error(f"DB Error: {e}")
    active_accs, paused_accs, open_alerts = 0, 0, 0

with col1:
    st.metric("Aktive Accounts", active_accs)
with col2:
    st.metric("Pausierte / Fehler Accounts", paused_accs)
with col3:
    st.metric("Ungelöste Alerts", open_alerts, delta_color="inverse")

st.markdown("---")

st.subheader("System Status")
is_running = is_daemon_running()

if is_running:
    st.success("🟢 Bot-Daemon (main.py run) läuft aktuell.")
else:
    st.warning("🔴 Bot-Daemon ist offline.")

if st.button("🔄 Daemon Neustearten"):
    ok, msg = restart_daemon()
    if ok:
         st.success(msg)
    else:
         st.error(msg)

st.markdown("---")
st.subheader("Letzte 5 Alerts")
try:
    latest_alerts = sb.table("alerts").select("*").order("created_at", desc=True).limit(5).execute()
    if latest_alerts.data:
        for alert in latest_alerts.data:
            color = "🔴" if alert["type"] in ["ACCOUNT_BLOCKED", "LOGIN_FAILED", "PROXY_ERROR"] else "⚠️"
            stat = "Gelesen" if alert["resolved"] else "Offen"
            st.info(f"{color} **{alert['type']}** (Acc: {alert['account_id']}) - {alert['created_at'][:16]}\n\nDetails: {alert['detail']}\n\nStatus: {stat}")
    else:
        st.write("Keine Alerts vorhanden.")
except Exception as e:
    st.error(f"Fehler beim Laden von Alerts: {e}")
