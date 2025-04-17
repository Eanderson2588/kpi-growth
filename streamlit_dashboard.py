import datetime
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

###############################
# Streamlit page config
###############################

st.set_page_config(
    page_title="S&S KPI Dashboard",
    layout="wide",
    page_icon="💈",
)

###############################
# 1. Load & cache KPI dataset #
###############################

@st.cache_data(show_spinner=False, ttl=3600)
def load_data(path: str | Path = "shop_kpi_dashboard_full.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    return df

DATA_PATH = Path("shop_kpi_dashboard_full.csv")
if not DATA_PATH.exists():
    st.error("❌  shop_kpi_dashboard_full.csv not found.")
    st.stop()

df = load_data(DATA_PATH)

###############################
# 2. Sidebar controls         #
###############################

st.sidebar.title("🔎  Filters")

shops = sorted(df["Shop"].unique())
sel_shops = st.sidebar.multiselect("Shops", shops, default=shops)

kpis = sorted(df["KPI"].unique())
sel_kpi = st.sidebar.selectbox("Primary KPI", kpis, index=kpis.index("net_revenue"))

min_date, max_date = df["Date"].min(), df["Date"].max()
start_date, end_date = st.sidebar.slider(
    "Date range",
    min_value=min_date,
    max_value=max_date,
    value=(min_date, max_date),
    step=datetime.timedelta(days=31),
    format="MMM YYYY",
)

promo_toggle = st.sidebar.checkbox("Highlight Men’s Grooming Month (Aug 2023)")
agg_method = st.sidebar.radio("Aggregation", ["Average", "Sum"], horizontal=True)
agg_func = np.mean if agg_method == "Average" else np.sum

###############################
# 3. Filtered dataframe        #
###############################

mask = (
    df["Shop"].isin(sel_shops)
    & df["Date"].between(start_date, end_date)
)
flt = df.loc[mask].copy()

if flt.empty:
    st.warning("No data for selected filters.")
    st.stop()

###############################
# 4. Helper functions          #
###############################

def build_month_df(subset: pd.DataFrame, kpi: str) -> pd.DataFrame:
    if agg_method == "Average":
        mdf = subset[subset["KPI"] == kpi].groupby("Date")["Value"].mean().reset_index()
    else:
        mdf = subset[subset["KPI"] == kpi].groupby("Date")["Value"].sum().reset_index()
    mdf = mdf.sort_values("Date").reset_index(drop=True)
    return mdf

def get_latest_metrics(mdf: pd.DataFrame) -> tuple[float, float, float]:
    valid = mdf.dropna(subset=["Value"])
    latest_val = valid.iloc[-1]["Value"]
    # MoM
    prev = valid.iloc[-2]["Value"] if len(valid) >= 2 else np.nan
    mom = (latest_val - prev) / prev * 100 if np.isfinite(prev) and prev else np.nan
    # YoY
    latest_date = valid.iloc[-1]["Date"]
    try:
        tgt = datetime.date(latest_date.year - 1, latest_date.month, 1)
        yoy_val = valid.loc[valid["Date"] == tgt, "Value"].dropna().iloc[0]
        yoy = (latest_val - yoy_val) / yoy_val * 100 if yoy_val else np.nan
    except (IndexError, ValueError):
        yoy = np.nan
    return latest_val, mom, yoy

###############################
# 5. KPI Score‑card grid (B)  #
###############################

card_kpis = [
    "net_revenue",
    "total_appointments",
    "total_clients",
    "new_members",
]

st.markdown("## KPI Scorecards")
card_cols = st.columns(len(card_kpis))

for kpi_name, col in zip(card_kpis, card_cols):
    if kpi_name not in kpis:
        continue
    mdf = build_month_df(flt, kpi_name)
    latest_val, mom_pct, yoy_pct = get_latest_metrics(mdf)
    spark = alt.Chart(mdf).mark_line().encode(
        x="Date:T",
        y="Value:Q",
    ).properties(height=40, width=150)
    col.altair_chart(spark, use_container_width=False)
    col.metric(kpi_name.replace("_", " ").title(), f"{latest_val:,.0f}", f"{mom_pct:+.1f}% MoM")

st.divider()

###############################
# 6. Primary KPI section       #
###############################

primary_md = build_month_df(flt, sel_kpi)
latest_val, mom_pct, yoy_pct = get_latest_metrics(primary_md)

st.markdown("### {}".format(sel_kpi.replace("_", " ").title()))

m1, m2, m3 = st.columns(3)
m1.metric("Latest ({} across shops)".format(agg_method.lower()), f"{latest_val:,.2f}")
m2.metric("MoM ∆", f"{mom_pct:+.1f}%" if np.isfinite(mom_pct) else "—")
m3.metric("YoY ∆", f"{yoy_pct:+.1f}%" if np.isfinite(yoy_pct) else "—")

###############################
# 7. Primary KPI line chart    # (A, C)
###############################

base = alt.Chart(primary_md).encode(x="monthdate(Date):T", y="Value:Q")
line = base.mark_line(interpolate="monotone", strokeWidth=2, color="#60a5fa")

layers = [line]
if promo_toggle:
    band = alt.Chart(
        pd.DataFrame({"start": [datetime.date(2023, 8, 1)], "end": [datetime.date(2023, 8, 31)]})
    ).mark_rect(opacity=0.15, color="#8e44ad").encode(x="start:T", x2="end:T")
    layers.append(band)

st.altair_chart(alt.layer(*layers).interactive(bind_y=False), use_container_width=True)

###############################
# 8. MoM % bar chart           # (H gradient)
###############################

if len(primary_md) > 1:
    mom_df = primary_md.copy()
    mom_df["MoM_%"] = mom_df["Value"].pct_change() * 100
    mom_df = mom_df.dropna(subset=["MoM_%"])
    color_scale = alt.Scale(domain=[-50, 0, 50], range=["#ef4444", "#fde047", "#10b981"])  # red→yellow→green

    mom_bar = (
        alt.Chart(mom_df)
        .mark_bar()
        .encode(
            x="monthdate(Date):T",
            y="MoM_%:Q",
            color=alt.Color("MoM_%:Q", scale=color_scale, legend=None),
            tooltip=["Date:T", alt.Tooltip("MoM_%:Q", format="+.1f")],
        )
        .properties(height=180)
    )
    st.altair_chart(mom_bar, use_container_width=True)

###############################
# 9. Raw table & download      #
###############################

with st.expander("📄  Show raw data table"):
    st.dataframe(
        flt.sort_values(["Shop", "Date"]).reset_index(drop=True),
        use_container_width=True,
    )

st.download_button(
    "📥  Download filtered data (CSV)",
    data=flt.to_csv(index=False).encode("utf-8"),
    file_name="filtered_kpi.csv",
)

st.caption("Powered by Streamlit • Data through Feb 2025 • v3.0")
