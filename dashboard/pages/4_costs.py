import streamlit as st
import pandas as pd
import plotly.express as px
from dash_utils.supabase_client import sb

st.set_page_config(page_title="Token Kosten", layout="wide")
st.title("💰 Token & OpenAI Kosten")

# --- LADE DATEN ---
@st.cache_data(ttl=30)
def load_costs():
    res = sb.table("gpt_usage").select("*").execute()
    return pd.DataFrame(res.data)

df = load_costs()

if df.empty:
    st.info("Noch kein LLM-Verbrauch protokolliert.")
    st.stop()

df['created_at'] = pd.to_datetime(df['created_at'])
df['date'] = df['created_at'].dt.date
df['total_tokens'] = df['tokens_input'] + df['tokens_output']

# OpenAI gpt-4o-mini Pricing (ca. $0.150 / 1M input, $0.600 / 1M output)
# Aktualisierte Werte können hier angepasst werden
COST_PER_1K_IN = 0.00015
COST_PER_1K_OUT = 0.0006

df['calculated_cost_usd'] = (df['tokens_input'] / 1000 * COST_PER_1K_IN) + (df['tokens_output'] / 1000 * COST_PER_1K_OUT)

st.markdown("---")

# --- METRIKEN ---
total_cost = df['calculated_cost_usd'].sum()
total_tokens = df['total_tokens'].sum()
avg_cost_msg = df['calculated_cost_usd'].mean()

today = pd.Timestamp.now(tz='UTC').date()
cost_today = df[df['date'] == today]['calculated_cost_usd'].sum()
# Hochrechnung 30 Tage
projection = cost_today * 30

col1, col2, col3, col4 = st.columns(4)
col1.metric("Gesamtkosten (USD)", f"${total_cost:.4f}")
col2.metric("Kosten Heute (USD)", f"${cost_today:.4f}")
col3.metric("Projektion 30 Tage", f"~${projection:.2f}")
col4.metric("Ø Kosten / Prompt", f"${avg_cost_msg:.5f}")

st.markdown("---")

# --- CHARTS ---
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Täglicher Verbrauch (Tokens)")
    daily_tokens = df.groupby(['date', 'account_id'])['total_tokens'].sum().reset_index()
    fig1 = px.bar(daily_tokens, x="date", y="total_tokens", color="account_id", barmode="group")
    st.plotly_chart(fig1, use_container_width=True)

with col_right:
    st.subheader("Kosten-Breakdown nach Typ")
    type_costs = df.groupby('type')['calculated_cost_usd'].sum().reset_index()
    fig2 = px.pie(type_costs, values='calculated_cost_usd', names='type', hole=0.4)
    st.plotly_chart(fig2, use_container_width=True)

# --- RAW TABELLE ---
with st.expander("Genaue Logs ansehen"):
    st.dataframe(df.sort_values(by="created_at", ascending=False), use_container_width=True)
