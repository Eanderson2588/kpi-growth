import datetime
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

###############################
# Streamlit page config + CSS #
###############################

st.set_page_config(
    page_title="S&S KPI Dashboard",
    layout="wide",
    page_icon="💈",
)

# -- Inject a tiny bit of CSS for modern card look
st.markdown(
    """
    <style>
        .big-metric {
            font-size: 2.8rem !important;
            font-weight: 700;
            margin: 0;
        }
        .metric-delta {
            font-size: 1.2rem !important;
        }
        .kpi-card {
            background: #1e1e24;
            padding: 1rem 1.2rem;
            border-radius: 12px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.4);
        }
        .kpi-title {
            color: #8b949e;
            font-size: .9rem;
            margin-bottom: .3rem;
        }
        .sparkline-container svg {
            width: 100% !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

###############################
# 1. Load data               #
###############################

@st.cache_data(show_spinner=False, ttl=1800)
def load_csv(path: str | Path = "shop_kpi_dashboard_full.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    return df

data_path = Path("shop_kpi_dashboard_full.csv")
if not data_path.exists():
    st.error("❌  shop_kpi_dashboard_full.csv not found in repo root.")
    st.stop()

raw_df = load_csv(data_path)

###############################
# 2. Sidebar filters          #
###############################

st.sidebar.header("🔍  Filters")
all_shops = sorted(raw_df["Shop"].unique())
shop_sel = st.sidebar.multiselect("Shop(s)", all_shops, default=all_shops)

all_kpis = sorted(raw_df["KPI"].unique())
primary_kpi = st.sidebar.selectbox("Primary KPI", all_kpis, index=all_kpis.index("net_revenue"))

min_dt, max_dt = raw_df["Date"].min(), raw_df["Date"].max()
start_dt, end_dt = st.sidebar.slider(
    "Date range",
    min_value=min_dt,
    max_value=max_dt,
    value=(min_dt, max_dt),
    step=datetime.timedelta(days=31),
    format="MMM YYYY",
)

promo_toggle = st.sidebar.checkbox("Show Men’s Grooming Month band (Aug 2023)")
agg_method = st.sidebar.radio("Aggregation", ["Average", "Sum"], horizontal=True)
agg_func = np.mean if agg_method == "Average" else np.sum

###############################
# 3. Filter df                #
###############################

flt_df = raw_df[
    (raw_df["Shop"].isin(shop_sel))
    & raw_df["Date"].between(start_dt, end_dt)
].copy()

if flt_df.empty:
    st.warning("No data for selection.")
    st.stop()

###############################
# 4. Helper funcs             #
###############################

def month_agg(df: pd.DataFrame, kpi: str) -> pd.DataFrame:
    """Return month‑level aggregated df for one KPI."""
    if agg_method == "Average":
        m = df[df["KPI"] == kpi].groupby("Date")["Value"].mean().reset_index()
    else:
        m = df[df["KPI"] == kpi].groupby("Date")["Value"].sum().reset_index()
    return m.sort_values("Date").reset_index(drop=True)

def latest_vals(mdf: pd.DataFrame):
    valid = mdf.dropna(subset=["Value"])
    latest = valid.iloc[-1]
    latest_val = latest["Value"]
    prev_val = valid.iloc[-2]["Value"] if len(valid) >= 2 else np.nan
    mom = (latest_val - prev_val) / prev_val * 100 if np.isfinite(prev_val) and prev_val else np.nan
    try:
        yoy_date = datetime.date(latest["Date"].year - 1, latest["Date"].month, 1)
        yoy_val = valid.loc[valid["Date"] == yoy_date, "Value"].dropna().iloc[0]
        yoy = (latest_val - yoy_val) / yoy_val * 100 if yoy_val else np.nan
    except Exception:
        yoy = np.nan
    return latest_val, mom, yoy

###############################
# 5. KPI scorecard row        #
###############################

score_kpis = [
    "net_revenue",
    "total_appointments",
    "total_clients",
    "new_members",
]

st.markdown("### KPI Scorecards")
card_cols = st.columns(len(score_kpis))

for kpi, col in zip(score_kpis, card_cols):
    if kpi not in all_kpis:
        continue
    card_df = month_agg(flt_df, kpi)
    latest, mom, _ = latest_vals(card_df)

    with col.container():
        st.markdown("<div class='kpi-card'>", unsafe_allow_html=True)
        st.markdown(f"<div class='kpi-title'>{kpi.replace('_',' ').title()}</div>", unsafe_allow_html=True)
        st.markdown(f"<p class='big-metric'>{latest:,.0f}</p>", unsafe_allow_html=True)
        delta_color = "#10b981" if mom >= 0 else "#ef4444"
        st.markdown(
            f"<span class='metric-delta' style='color:{delta_color}'>"
            f"{mom:+.1f}% MoM</span>", unsafe_allow_html=True
        )
        spark = (
            alt.Chart(card_df)
            .mark_line(opacity=0.85, strokeWidth=2, color="#4ade80")
            .encode(x="Date:T", y="Value:Q")
            .properties(height=40)
        )
        st.altair_chart(spark, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

st.divider()

###############################
# 6. Primary KPI section      #
###############################

primary_df = month_agg(flt_df, primary_kpi)
l_val, l_mom, l_yoy = latest_vals(primary_df)

st.markdown(f"## {primary_kpi.replace('_',' ').title()}")
metric_cols = st.columns(3)
metric_cols[0].metric("Latest", f"{l_val:,.2f}")
metric_cols[1].metric("MoM", f"{l_mom:+.1f}%")
metric_cols[2].metric("YoY", f"{l_yoy:+.1f}%" if np.isfinite(l_yoy) else "—")

# -- Line chart with tooltip & promo overlay
base = (
    alt.Chart(primary_df)
    .encode(x="Date:T", y="Value:Q", tooltip=["Date:T", alt.Tooltip("Value:Q", format=",.0f")])
)
line = base.mark_line(interpolate="monotone", strokeWidth=2, color="#60a5fa")
layer_list = [line]
if promo_toggle:
    band = alt.Chart(pd.DataFrame({"start":[datetime.date(2023,8,1)],"end":[datetime.date(2023,8,31)]}))\
        .mark_rect(opacity=0.15, color="#8e44ad")\
        .encode(x="start:T", x2="end:T")
    layer_list.append(band)

st.altair_chart(alt.layer(*layer_list).interactive(bind_y=False), use_container_width=True)

# -- MoM bar chart with gradient (green↔red)
if len(primary_df) > 1:
    mom_df = primary_df.copy()
    mom_df["MoM_%"] = mom_df["Value"].pct_change() * 100
    mom_df = mom_df.dropna(subset=["MoM_%"])
    cscale = alt.Scale(domain=[-40, 0, 40], range=["#ef4444", "#facc15", "#10b981"])
    bar = (
        alt.Chart(mom_df)
        .mark_bar()
        .encode(
            x="Date:T",
            y="MoM_%:Q",
            color=alt.Color("MoM_%:Q", scale=cscale, legend=None),
            tooltip=["Date:T", alt.Tooltip("MoM_%:Q", format="+.1f")],
        )
        .properties(height=140)
    )
    st.altair_chart(bar, use_container_width=True)

###############################
# 7. Raw data + download       #
###############################

with st.expander("📄 Raw data"):
    st.dataframe(flt_df.sort_values(["Shop", "Date"]).reset_index(drop=True), use_container_width=True)

st.download_button("📥 Download CSV", data=flt_df.to_csv(index=False).encode("utf-8"), file_name="filtered_kpi.csv")

st.caption("💈 Scissors & Scotch • Data thru Feb 2025 • v3.1")
