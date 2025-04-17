import datetime
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

############################################
# Streamlit page config + minimal dark CSS #
############################################

st.set_page_config(
    page_title="S&S KPI Dashboard",
    layout="wide",
    page_icon="💈",
)

###############################
# 0. Utility – local CSS for cards
###############################

st.markdown(
    """
    <style>
        .kpi-card {background:#1e1e24;padding:1rem 1.2rem;border-radius:12px;box-shadow:0 2px 6px rgba(0,0,0,0.45);}
        .kpi-title {color:#8b949e;font-size:.8rem;margin-bottom:.3rem;letter-spacing:.5px;text-transform:uppercase;}
        .kpi-val {font-size:2.2rem;font-weight:700;margin:0;}
        .kpi-delta {font-size:1rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

###############################
# 1. Load & cache data        #
###############################

@st.cache_data(show_spinner=False, ttl=1800)
def load_data(path: str | Path = "shop_kpi_dashboard_full.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    return df

data_path = Path("shop_kpi_dashboard_full.csv")
if not data_path.exists():
    st.error("🔴  CSV missing – upload shop_kpi_dashboard_full.csv to repo root.")
    st.stop()

df_raw = load_data(data_path)

###############################
# 2. Sidebar controls         #
###############################

st.sidebar.header("🎚️  Controls")
shop_options = sorted(df_raw["Shop"].unique())
shops_sel = st.sidebar.multiselect("Shop(s)", shop_options, default=shop_options)

all_kpis = sorted(df_raw["KPI"].unique())
primary_kpi = st.sidebar.selectbox("Primary KPI", all_kpis, index=all_kpis.index("net_revenue"))

compare_kpis = st.sidebar.multiselect(
    "Overlay KPI(s)",
    options=[k for k in all_kpis if k != primary_kpi],
)

min_date, max_date = df_raw["Date"].min(), df_raw["Date"].max()
start_dt, end_dt = st.sidebar.slider(
    "Date range",
    min_value=min_date,
    max_value=max_date,
    value=(min_date, max_date),
    step=datetime.timedelta(days=31),
    format="MMM YYYY",
)

agg_method = st.sidebar.radio("Aggregation", ["Average", "Sum"], horizontal=True)
agg_func = np.mean if agg_method == "Average" else np.sum
normalize_toggle = st.sidebar.checkbox("Normalize overlay lines (index = 100)")

promo_toggle = st.sidebar.checkbox("Show Men’s Grooming Month (Aug 2023)")

###############################
# 3. Filter dataframe         #
###############################

filt = df_raw[(df_raw["Shop"].isin(shops_sel)) & df_raw["Date"].between(start_dt, end_dt)].copy()
if filt.empty:
    st.warning("No data for selected filters.")
    st.stop()

###############################
# 4. Helpers                  #
###############################

def month_agg(df: pd.DataFrame, kpi: str) -> pd.DataFrame:
    tmp = df[df["KPI"] == kpi]
    if agg_method == "Average":
        out = tmp.groupby("Date")["Value"].mean().reset_index()
    else:
        out = tmp.groupby("Date")["Value"].sum().reset_index()
    return out.sort_values("Date")

def latest_metrics(mdf: pd.DataFrame):
    mdf = mdf.dropna(subset=["Value"])
    latest = mdf.iloc[-1]
    latest_val = latest["Value"]
    mom = np.nan
    if len(mdf) >= 2:
        prev = mdf.iloc[-2]["Value"]
        mom = (latest_val - prev) / prev * 100 if prev else np.nan
    yoy = np.nan
    try:
        tgt = datetime.date(latest["Date"].year - 1, latest["Date"].month, 1)
        yoy_val = mdf.loc[mdf["Date"] == tgt, "Value"].iloc[0]
        yoy = (latest_val - yoy_val) / yoy_val * 100 if yoy_val else np.nan
    except Exception:
        pass
    return latest_val, mom, yoy

###############################
# 5. Scorecard strip          #
###############################

score_kpis = ["net_revenue", "total_appointments", "total_clients", "new_members"]
sc_cols = st.columns(len(score_kpis))
for kpi, col in zip(score_kpis, sc_cols):
    mdf = month_agg(filt, kpi)
    if mdf.empty:
        continue
    val, mom, _ = latest_metrics(mdf)
    delta_color = "#10b981" if mom >= 0 else "#ef4444"
    with col.container():
        st.markdown("<div class='kpi-card'>", unsafe_allow_html=True)
        st.markdown(f"<div class='kpi-title'>{kpi.replace('_',' ').title()}</div>", unsafe_allow_html=True)
        st.markdown(f"<p class='kpi-val'>{val:,.0f}</p>", unsafe_allow_html=True)
        st.markdown(f"<span class='kpi-delta' style='color:{delta_color}'>{mom:+.1f}% MoM</span>", unsafe_allow_html=True)
        spark = (
            alt.Chart(mdf)
            .mark_line(color="#4ade80", strokeWidth=2)
            .encode(x="Date:T", y="Value:Q")
            .properties(height=40)
        )
        st.altair_chart(spark, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

st.divider()

################################
# 6.  MULTI‑KPI OVERLAY CHART  #
################################

st.markdown(f"## {primary_kpi.replace('_',' ').title()} & Overlays")
sel_kpis = [primary_kpi] + compare_kpis
long_rows = []
for k in sel_kpis:
    mdf = month_agg(filt, k)
    if normalize_toggle and not mdf.empty:
        base_val = mdf.iloc[0]["Value"]
        mdf["Value"] = mdf["Value"] / base_val * 100 if base_val else mdf["Value"]
    mdf["KPI"] = k.replace("_", " ").title()
    long_rows.append(mdf)

overlay_df = pd.concat(long_rows)

color_scale = alt.Scale(scheme="category10")
line_overlay = (
    alt.Chart(overlay_df)
    .mark_line(interpolate="monotone", strokeWidth=2)
    .encode(
        x="Date:T",
        y="Value:Q",
        color=alt.Color("KPI:N", scale=color_scale),
        tooltip=["KPI", "Date:T", alt.Tooltip("Value:Q", format=",.0f")],
    )
)
layer_list = [line_overlay]
if promo_toggle:
    band = alt.Chart(pd.DataFrame({"start":[datetime.date(2023,8,1)],"end":[datetime.date(2023,8,31)]}))\
        .mark_rect(opacity=0.15, color="#8e44ad")\
        .encode(x="start:T", x2="end:T")
    layer_list.append(band)

st.altair_chart(alt.layer(*layer_list).interactive(bind_y=False), use_container_width=True)

################################
# 7. MoM bar for primary KPI   #
################################

primary_df = month_agg(filt, primary_kpi)
if len(primary_df) > 1:
    momdf = primary_df.assign(MoM_pct=primary_df["Value"].pct_change()*100).dropna()
    bar_color = alt.Scale(domain=[-40,0,40], range=["#ef4444","#facc15","#10b981"])
    bar = alt.Chart(momdf).mark_bar().encode(
        x="Date:T", y="MoM_pct:Q", color=alt.Color("MoM_pct:Q", scale=bar_color, legend=None),
        tooltip=["Date:T", alt.Tooltip("MoM_pct:Q", format="+.1f")]
    ).properties(height=140)
    st.altair_chart(bar, use_container_width=True)

################################
# 8. Data + download           #
################################
with st.expander("📄 Raw data"):
    st.dataframe(filt.sort_values(["Shop","Date"]).reset_index(drop=True), use_container_width=True)

st.download_button("📥 Download CSV", data=filt.to_csv(index=False).encode(), file_name="filtered_kpi.csv")

st.caption("💈 Scissors & Scotch • v3.2 • Data thru Feb 2025")
