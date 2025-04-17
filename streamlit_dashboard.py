import datetime
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

###############################
# 1. Load & cache KPI dataset #
###############################

@st.cache_data(show_spinner=False, ttl=3600)
def load_data(path: str | Path = "shop_kpi_dashboard_full.csv") -> pd.DataFrame:
    """Read the pre‑generated KPI dashboard CSV and parse dates."""
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    return df

DATA_PATH = Path("shop_kpi_dashboard_full.csv")
if not DATA_PATH.exists():
    st.error("❌ Data file 'shop_kpi_dashboard_full.csv' not found in the app directory.")
    st.stop()

df = load_data(DATA_PATH)

########################################
# 2. Sidebar – interactive filter panel #
########################################

st.sidebar.title("🔍 Filters")

shops = sorted(df["Shop"].unique())
sel_shops = st.sidebar.multiselect("Shops", options=shops, default=shops)

kpis = sorted(df["KPI"].unique())
sel_kpi = st.sidebar.selectbox("KPI", options=kpis, index=kpis.index("net_revenue"))

min_date, max_date = df["Date"].min(), df["Date"].max()
start_date, end_date = st.sidebar.slider(
    "Date range",
    min_value=min_date,
    max_value=max_date,
    value=(min_date, max_date),
    step=datetime.timedelta(days=31),
    format="MMM YYYY",
)

promo_toggle = st.sidebar.checkbox("Highlight Men’s Grooming Month (Aug 2023)")
agg_method = st.sidebar.radio("Aggregation", ["Average", "Sum"], horizontal=True)
agg_func = np.mean if agg_method == "Average" else np.sum

########################
# 3. Filter the dataset #
########################

mask = (
    df["Shop"].isin(sel_shops)
    & (df["KPI"] == sel_kpi)
    & df["Date"].between(start_date, end_date)
)
flt = df.loc[mask].copy()

if flt.empty:
    st.warning("No data for the selected filters.")
    st.stop()

########################################
# 4. Build month‑level dataframe       #
########################################

if agg_method == "Average":
    month_df = flt.groupby("Date")["Value"].mean().reset_index()
else:
    month_df = flt.groupby("Date")["Value"].sum().reset_index()

month_df = month_df.sort_values("Date").reset_index(drop=True)

# latest non‑NaN value row
valid_rows = month_df.dropna(subset=["Value"])
latest_row = valid_rows.iloc[-1]
latest_date, latest_val = latest_row["Date"], latest_row["Value"]

# previous month with data
prev_rows = valid_rows[valid_rows["Date"] < latest_date]
if not prev_rows.empty:
    prev_val = prev_rows.iloc[-1]["Value"]
    mom_pct = (latest_val - prev_val) / prev_val * 100 if prev_val else np.nan
else:
    mom_pct = np.nan

# YoY comparison
try:
    yoy_date = datetime.date(latest_date.year - 1, latest_date.month, 1)
    yoy_val = valid_rows.loc[valid_rows["Date"] == yoy_date, "Value"].iloc[0]
    yoy_pct = (latest_val - yoy_val) / yoy_val * 100 if yoy_val else np.nan
except (IndexError, ValueError):
    yoy_pct = np.nan

########################
# 5. Main page heading  #
########################

st.title("Scissors & Scotch KPI Dashboard")
readable_kpi = sel_kpi.replace("_", " ").title()
st.subheader(readable_kpi)

col1, col2, col3 = st.columns(3)
col1.metric("Latest ({} across shops)".format(agg_method.lower()), f"{latest_val:,.2f}")
col2.metric("MoM ∆", f"{mom_pct:+.1f}%" if np.isfinite(mom_pct) else "—")
col3.metric("YoY ∆", f"{yoy_pct:+.1f}%" if np.isfinite(yoy_pct) else "—")

#########################
# 6. KPI trend line chart #
#########################

line_chart = (
    alt.Chart(month_df)
    .mark_line(interpolate="monotone", strokeWidth=2)
    .encode(
        x=alt.X("monthdate(Date):T", title="Month"),
        y=alt.Y("Value:Q", title=readable_kpi),
        tooltip=[alt.Tooltip("Date:T"), alt.Tooltip("Value:Q", format=",.2f")],
    )
)

layers = [line_chart]

if promo_toggle:
    band = alt.Chart(
        pd.DataFrame({"start": [datetime.date(2023, 8, 1)], "end": [datetime.date(2023, 8, 31)]})
    ).mark_rect(opacity=0.15, color="#8e44ad").encode(x="start:T", x2="end:T")
    layers.append(band)

st.altair_chart(alt.layer(*layers).interactive(), use_container_width=True)

###############################
# 7. MoM % bar chart (optional)
###############################

if len(month_df) > 1:
    mom_df = month_df.copy()
    mom_df["MoM_%"] = mom_df["Value"].pct_change() * 100
    mom_df = mom_df.dropna(subset=["MoM_%"])

    mom_bar = (
        alt.Chart(mom_df)
        .mark_bar()
        .encode(
            x=alt.X("monthdate(Date):T", title="Month"),
            y=alt.Y("MoM_%:Q", title="MoM %"),
            color=alt.condition(alt.datum.MoM_ > 0, alt.value("#10b981"), alt.value("#ef4444")),
            tooltip=[alt.Tooltip("Date:T"), alt.Tooltip("MoM_%:Q", format="+.1f")],
        )
        .properties(height=180)
    )

    st.subheader("Month‑over‑Month % Change")
    st.altair_chart(mom_bar, use_container_width=True)

############################
# 8. Raw table & download  #
############################

with st.expander("📄 Show raw data table"):
    st.dataframe(
        flt.sort_values(["Shop", "Date"])
        .assign(Date=flt["Date"].astype(str))
        .reset_index(drop=True),
        use_container_width=True,
    )

csv_bytes = flt.to_csv(index=False).encode("utf-8")
st.download_button("📥 Download filtered data (CSV)", data=csv_bytes, file_name="filtered_data.csv")

st.caption("Powered by Streamlit • Data through Feb 2025 • v2.2")




