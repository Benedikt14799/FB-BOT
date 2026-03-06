import streamlit as st
import pandas as pd
from dash_utils.supabase_client import sb

st.set_page_config(page_title="Alerts & Warnungen", layout="wide")
st.title("🚨 Alerts & System Events")

col1, col2 = st.columns([3, 1])

# --- LADE DATEN ---
@st.cache_data(ttl=10)
def load_alerts():
    res = sb.table("alerts").select("*").order("created_at", desc=True).limit(200).execute()
    return pd.DataFrame(res.data)

df = load_alerts()

if df.empty:
    st.success("Keine System-Alerts vorhanden. Alles läuft einwandfrei! 🎉")
    st.stop()

df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%d.%m.%Y %H:%M')

with col2:
    st.subheader("Filter")
    show_resolved = st.checkbox("Zeige auch gelöste", value=False)
    
    if st.button("Alle als gelesen markieren ✅", type="primary"):
        sb.table("alerts").update({"resolved": True}).eq("resolved", False).execute()
        st.success("Erledigt!")
        st.rerun()

if not show_resolved:
    df = df[df['resolved'] == False]

with col1:
    if df.empty:
        st.info("Alle Alerts wurden abgearbeitet.")
    else:
        for idx, row in df.iterrows():
            # Styling je nach Typ
            alert_type = row['type']
            if alert_type in ["ACCOUNT_BLOCKED", "PROXY_ERROR", "LOGIN_FAILED"]:
                st_method = st.error
                icon = "🔴"
            elif alert_type in ["FACEBOOK_WARNING"]:
                st_method = st.warning
                icon = "⚠️"
            else:
                st_method = st.info
                icon = "ℹ️"
                
            with st.container():
                col_icon, col_txt, col_btn = st.columns([1, 8, 2])
                with col_icon:
                    st.write(f"### {icon}")
                with col_txt:
                    st.write(f"**{alert_type}** | Account: {row['account_id']} | {row['created_at']}")
                    st.write(row['detail'])
                with col_btn:
                    if not row['resolved']:
                        if st.button("Als erledigt markieren", key=f"res_{row['id']}"):
                            sb.table("alerts").update({"resolved": True}).eq("id", row['id']).execute()
                            st.rerun()
                st.markdown("---")
