import streamlit as st
import pandas as pd
import plotly.express as px
from dash_utils.supabase_client import sb

st.set_page_config(page_title="KPI Dashboard", layout="wide")

st.title("📊 KPI & Funnel Dashboard")

# Zeitraum Filter
time_filter = st.selectbox("Zeitraum", ["Gesamtzeit", "Letzte 7 Tage", "Heute"])

# Lade Daten
@st.cache_data(ttl=30)
def load_kpis():
    # Holt alle recipients für Funnel-Analyse
    res = sb.table("recipients").select("conversation_state, created_at, account_id").execute()
    return pd.DataFrame(res.data)

df = load_kpis()

if df.empty:
    st.warning("Noch keine Konversationsdaten vorhanden.")
    st.stop()

# Datumsfilter anwenden (Dummy für "Letzte 7 Tage" / "Heute" falls wir echte Timestamps bräuchten,
# Streamlit demo-mäßig filtern wir hier das DataFrame)
df['created_at'] = pd.to_datetime(df['created_at'])
today = pd.Timestamp.now(tz='UTC').normalize()

if time_filter == "Heute":
    df = df[df['created_at'] >= today]
elif time_filter == "Letzte 7 Tage":
    df = df[df['created_at'] >= (today - pd.Timedelta(days=7))]

# --- METRIKEN BERECHNEN ---

total_sent = len(df[df['conversation_state'].isin(['msg1_sent', 'msg1_replied', 'msg2_sent', 'msg2_replied', 'offer_sent', 'converted', 'no_reply_24h'])])
msg1_replies = len(df[df['conversation_state'].isin(['msg1_replied', 'msg2_sent', 'msg2_replied', 'offer_sent', 'converted'])])
warm_leads = len(df[df['conversation_state'].isin(['msg2_replied', 'offer_sent', 'converted'])])
offers_sent = len(df[df['conversation_state'].isin(['offer_sent', 'converted'])])
conversions = len(df[df['conversation_state'] == 'converted'])
blocks = len(df[df['conversation_state'] == 'blacklisted'])

msg1_rate = (msg1_replies / total_sent * 100) if total_sent > 0 else 0
warm_rate = (warm_leads / msg1_replies * 100) if msg1_replies > 0 else 0

st.markdown("### Kern-Metriken")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Messages Sent (Total)", total_sent)
col2.metric("Reply Quote (Msg1)", f"{msg1_rate:.1f}%")
col3.metric("Warm Leads", warm_leads)
col4.metric("Conversions (Offer accepted)", conversions)

st.markdown("---")

# --- CHARTS ---
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Funnel Conversion")
    funnel_data = dict(
        number=[total_sent, msg1_replies, warm_leads, offers_sent, conversions],
        stage=["Sent (Msg1)", "Replied (Msg1)", "Warm Lead (Msg2 Reply)", "Offer Sent", "Converted"]
    )
    funnel_df = pd.DataFrame(funnel_data)
    fig_funnel = px.funnel(funnel_df, x='number', y='stage')
    st.plotly_chart(fig_funnel, use_container_width=True)

with col_right:
    st.subheader("Messages Sent pro Tag")
    # Gruppieren nach Datum und Account
    df['date'] = df['created_at'].dt.date
    sent_df = df[df['conversation_state'] != 'new'].groupby(['date', 'account_id']).size().reset_index(name='count')
    
    if not sent_df.empty:
        fig_line = px.line(sent_df, x='date', y='count', color='account_id', markers=True)
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("Keine historischen Daten für Graph verfügbar.")

st.markdown("---")
st.subheader("Problemfokus")
st.metric("Spam Reports / Blacklisted / Blocked", blocks)
