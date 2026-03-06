import streamlit as st
import pandas as pd
import json
from dash_utils.supabase_client import sb

st.set_page_config(page_title="Conversation Log", layout="wide")
st.title("💬 Conversation Log")

# --- LADE DATEN ---
@st.cache_data(ttl=15)
def load_conversations():
    res = sb.table("recipients").select("*").order("updated_at", desc=True).limit(500).execute()
    return pd.DataFrame(res.data)

df = load_conversations()

if df.empty:
    st.warning("Keine Konversationen gefunden.")
    st.stop()

# --- FILTER ---
col1, col2 = st.columns(2)
accounts_list = ["Alle"] + sorted([str(x) for x in df['account_id'].dropna().unique().tolist()])
statuses = ["Alle", "new", "msg1_sent", "msg1_replied", "msg2_sent", "msg2_replied", "offer_sent", "converted", "no_reply_24h", "blacklisted"]

with col1:
    acc_filter = st.selectbox("Account Filter", accounts_list)
with col2:
    status_filter = st.selectbox("Status Filter", statuses)

# Filter anwenden
if acc_filter != "Alle":
    df = df[df['account_id'] == int(acc_filter) if acc_filter.isdigit() else acc_filter]
if status_filter != "Alle":
    df = df[df['conversation_state'] == status_filter]

# --- TABELLE ---
st.write(f"Zeigt {len(df)} Ergebnisse an")

if not df.empty:
    # Bereite DataFrame für die Anzeige vor
    display_df = df[['name', 'facebook_id', 'account_id', 'conversation_state', 'updated_at']].copy()
    display_df['updated_at'] = pd.to_datetime(display_df['updated_at']).dt.strftime('%d.%m. %H:%M')
    
    # st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # Detail-Ansicht auf Klick (mit Expander pro Zeile für besseres UI Layout in Streamlit)
    for idx, row in df.iterrows():
        with st.expander(f"👤 {row['name']} | Status: {row['conversation_state']} | Acc: {row['account_id']} | ⏰ {pd.to_datetime(row['updated_at']).strftime('%d.%m.%y %H:%M')}"):
            col_l, col_r = st.columns([1, 2])
            
            with col_l:
                st.write("**Facebook ID:**")
                st.code(row['facebook_id'])
                st.write("**Letzter Kontakt (Timestamp):**")
                st.write(pd.to_datetime(row['last_contact']).strftime('%d.%m.%y %H:%M') if pd.notna(row['last_contact']) else "N/A")
                if st.button("Als Converted markieren ✅", key=f"conv_{row['id']}"):
                     sb.table("recipients").update({"conversation_state": "converted"}).eq("id", row['id']).execute()
                     st.rerun()
                if st.button("Auf Blacklist setzen 🚫", key=f"black_{row['id']}"):
                     sb.table("recipients").update({"conversation_state": "blacklisted"}).eq("id", row['id']).execute()
                     st.rerun()
                     
            with col_r:
                st.write("**Chat Verlauf:**")
                try:
                    history = json.loads(row.get('conversation_history', '[]'))
                    if not history:
                        st.info("Noch keine Nachrichten gesendet.")
                    else:
                        for msg in history:
                            if msg.get("sender") == "bot":
                                st.success(f"🤖 **Bot:** {msg.get('text')}")
                            else:
                                st.info(f"👤 **User:** {msg.get('text')}")
                except Exception as e:
                    st.error(f"Fehler beim Parsen der Historie: {e}")
