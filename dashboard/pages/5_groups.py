import streamlit as st
import pandas as pd
from dash_utils.supabase_client import sb

st.set_page_config(page_title="Gruppen & Targeting", layout="wide")
st.title("👥 Gruppen & Targeting")

# --- LADE DATEN ---
@st.cache_data(ttl=10)
def load_groups():
    res = sb.table("groups").select("*").execute()
    return pd.DataFrame(res.data)

@st.cache_data(ttl=10)
def load_account_groups():
    res = sb.table("account_groups").select("account_id, group_id, is_active").execute()
    return res.data

@st.cache_data(ttl=10)
def load_accounts():
    res = sb.table("accounts").select("account_id, status").execute()
    return pd.DataFrame(res.data)

df_groups = load_groups()
account_groups = load_account_groups()
df_accounts = load_accounts()

col_left, col_right = st.columns([1, 2])

# --- ADD GROUP FORM ---
with col_left:
    st.subheader("➕ Neue Gruppe anlegen")
    with st.form("add_group_form"):
        g_name = st.text_input("Gruppen Name (z.B. Facebook Affiliate Marketing DACH)")
        g_url = st.text_input("Gruppen URL (z.B. https://facebook.com/groups/12345)")
        g_cat = st.selectbox("Kategorie", ["Marketing", "Fitness", "Coaching", "Allgemein", "Sonstiges"])
        submitted = st.form_submit_button("Speichern")
        
        if submitted and g_name:
            sb.table("groups").insert({
                "name": g_name,
                "url": g_url,
                "category": g_cat,
                "status": "active"
            }).execute()
            st.success(f"Gruppe {g_name} hinzugefügt!")
            st.rerun()

# --- GROUP LIST & ASSIGNMENTS ---
with col_right:
    st.subheader("📂 Alle Facebook Gruppen")
    
    if df_groups.empty:
        st.info("Keine Gruppen konfiguriert.")
    else:
        accounts_list = [str(x) for x in df_accounts['account_id'].tolist()] if not df_accounts.empty else ["1", "2", "3", "4", "5", "6"]
        
        for idx, row in df_groups.iterrows():
            with st.expander(f"📌 {row['name']} | Status: {row['status']}"):
                col_i, col_j = st.columns(2)
                
                with col_i:
                    st.write("**Details**")
                    st.write(f"Kategorie: {row['category']}")
                    st.write(f"URL: {row['url']}")
                    
                    new_status = "paused" if row['status'] == "active" else "active"
                    btn_text = "Gruppe Pausieren" if row['status'] == "active" else "Gruppe Reaktivieren"
                    if st.button(btn_text, key=f"tog_grp_{row['id']}"):
                        sb.table("groups").update({"status": new_status}).eq("id", row['id']).execute()
                        st.rerun()
                
                with col_j:
                    st.write("**Account Zuweisung**")
                    # Welche accounts sind zugewiesen?
                    active_accs_for_grp = [
                        str(ag['account_id']) for ag in account_groups 
                        if ag['group_id'] == row['id'] and ag['is_active']
                    ]
                    
                    selected_accs = st.multiselect("Zuständige Accounts", accounts_list, default=active_accs_for_grp, key=f"ms_{row['id']}")
                    
                    if st.button("💾 Setup Speichern", key=f"save_asgn_{row['id']}"):
                        with st.spinner("Speichere Zuweisungen..."):
                            # Alle alten auf inactive setzen
                            sb.table("account_groups").update({"is_active": False}).eq("group_id", row['id']).execute()
                            # Neue auf active setzen bzw. einfügen
                            for acc_id in selected_accs:
                                sb.table("account_groups").upsert({
                                    "account_id": acc_id,
                                    "group_id": row['id'],
                                    "is_active": True
                                }, on_conflict="account_id,group_id").execute()
                        st.success("Zuweisung aktualisiert!")
                        st.rerun()
