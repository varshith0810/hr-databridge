"""
dashboard/app.py
Streamlit dashboard — HR DataBridge
Displays sync health, headcount, attrition, diversity, and data quality KPIs.

Run: streamlit run dashboard/app.py
"""

import os
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

st.set_page_config(
    page_title="HR DataBridge",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    .metric-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 16px 20px;
        border: 1px solid #e0e0e0;
    }
    .status-ok { color: #2e7d32; font-weight: 600; }
    .status-partial { color: #f57c00; font-weight: 600; }
    .status-error { color: #c62828; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------ #
#  Helpers
# ------------------------------------------------------------------ #

@st.cache_data(ttl=60)
def fetch(endpoint: str) -> list[dict] | dict:
    try:
        resp = requests.get(f"{API_BASE}{endpoint}", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"API error on {endpoint}: {exc}")
        return []


def kpi_to_df(data: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(data) if data else pd.DataFrame()


# ------------------------------------------------------------------ #
#  Header
# ------------------------------------------------------------------ #

st.title("🔗 HR DataBridge")
st.caption("ATS Integration Middleware + Workforce Analytics · Live from API")

col_refresh, col_trigger, _ = st.columns([1, 1, 8])
with col_refresh:
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()
with col_trigger:
    if st.button("▶ Trigger Sync"):
        resp = requests.post(f"{API_BASE}/sync/trigger", timeout=10)
        if resp.status_code == 200:
            st.success("Sync triggered!")
        elif resp.status_code == 409:
            st.warning("Sync already running.")
        else:
            st.error("Failed to trigger sync.")

st.divider()

# ------------------------------------------------------------------ #
#  Sync Health
# ------------------------------------------------------------------ #

st.subheader("📡 Sync Status")
sync_data = fetch("/sync/status")

if sync_data:
    cols = st.columns(len(sync_data))
    for col, s in zip(cols, sync_data):
        status_class = {"success": "status-ok", "partial": "status-partial", "failed": "status-error"}.get(s["status"], "")
        col.markdown(f"""
        <div class="metric-card">
            <b>{s['source_system'].capitalize()}</b><br>
            <span class="{status_class}">{s['status'].upper()}</span><br>
            <small>Last sync: {s.get('last_synced_at','—')[:19]}</small><br>
            <small>↓ {s['records_pulled']} pulled &nbsp;|&nbsp; + {s['records_inserted']} inserted &nbsp;|&nbsp; ✏ {s['records_updated']} updated</small><br>
            <small>⚠ {s['conflicts_detected']} conflicts &nbsp;|&nbsp; ⏱ {s.get('duration_seconds','—'):.1f}s</small>
        </div>
        """, unsafe_allow_html=True)

st.divider()

# ------------------------------------------------------------------ #
#  Headcount by Department
# ------------------------------------------------------------------ #

col1, col2 = st.columns(2)

with col1:
    st.subheader("👥 Headcount by Department")
    df_hc = kpi_to_df(fetch("/analytics/headcount"))
    if not df_hc.empty:
        df_hc = df_hc.sort_values("value", ascending=True)
        fig = px.bar(
            df_hc, x="value", y="dimension", orientation="h",
            labels={"value": "Headcount", "dimension": "Department"},
            color="value", color_continuous_scale="teal",
        )
        fig.update_layout(showlegend=False, coloraxis_showscale=False,
                          plot_bgcolor="white", height=350)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No headcount data yet — run a sync first.")

with col2:
    st.subheader("📉 Monthly Attrition Rate")
    df_at = kpi_to_df(fetch("/analytics/attrition"))
    if not df_at.empty:
        df_at = df_at.sort_values("dimension")
        fig = px.line(
            df_at, x="dimension", y="value",
            labels={"dimension": "Month", "value": "Attrition Rate (%)"},
            markers=True, line_shape="spline",
        )
        fig.update_traces(line_color="#d94f3d", marker_color="#d94f3d")
        fig.update_layout(plot_bgcolor="white", height=350)
        fig.add_hline(y=df_at["value"].mean(), line_dash="dot",
                      annotation_text="Avg", line_color="#888")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No attrition data yet.")

st.divider()

# ------------------------------------------------------------------ #
#  Diversity + Tenure
# ------------------------------------------------------------------ #

col3, col4 = st.columns(2)

with col3:
    st.subheader("🌍 Gender Diversity by Department")
    df_div = kpi_to_df(fetch("/analytics/diversity"))
    if not df_div.empty:
        df_div[["department", "gender"]] = df_div["dimension"].str.split("::", expand=True)
        fig = px.bar(
            df_div, x="department", y="value", color="gender", barmode="stack",
            labels={"value": "% of Dept", "department": "Department"},
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_layout(plot_bgcolor="white", height=350, legend_title="Gender")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No diversity data yet.")

with col4:
    st.subheader("⏳ Avg Tenure by Department (months)")
    df_ten = kpi_to_df(fetch("/analytics/tenure"))
    if not df_ten.empty:
        df_ten = df_ten.sort_values("value", ascending=False)
        fig = px.bar(
            df_ten, x="dimension", y="value",
            labels={"dimension": "Department", "value": "Avg Tenure (months)"},
            color="value", color_continuous_scale="purples",
        )
        fig.update_layout(plot_bgcolor="white", height=350, coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No tenure data yet.")

st.divider()

# ------------------------------------------------------------------ #
#  Data Quality
# ------------------------------------------------------------------ #

st.subheader("✅ Data Quality by Source System")
df_dq = kpi_to_df(fetch("/analytics/data-quality"))
if not df_dq.empty:
    df_dq["field"] = df_dq["kpi_name"].str.replace("data_quality_", "")
    fig = px.bar(
        df_dq, x="field", y="value", color="dimension", barmode="group",
        labels={"field": "Field", "value": "Completeness (%)", "dimension": "Source"},
        color_discrete_map={"greenhouse": "#1D9E75", "workday": "#534AB7"},
    )
    fig.update_layout(plot_bgcolor="white", yaxis_range=[0, 100])
    fig.add_hline(y=90, line_dash="dot", line_color="#c62828",
                  annotation_text="90% threshold")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No data quality metrics yet.")

# ------------------------------------------------------------------ #
#  Sync Audit Log
# ------------------------------------------------------------------ #

st.subheader("📋 Sync Audit Log")
logs = fetch("/sync/logs?limit=20")
if isinstance(logs, dict) and logs.get("results"):
    df_logs = pd.DataFrame(logs["results"])
    df_logs["synced_at"] = pd.to_datetime(df_logs["synced_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    st.dataframe(
        df_logs[["synced_at", "source_system", "status", "records_pulled",
                  "records_inserted", "records_updated", "conflicts_detected", "duration_seconds"]],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No sync logs yet.")
