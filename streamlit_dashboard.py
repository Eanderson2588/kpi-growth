import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import datetime
from pathlib import Path

###############################
# 1. Load & cache KPI dataset #
###############################

@st.cache_data(ttl=3600, show_spinner=False)
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
kpis = sorted(df["KPI"].unique())

selected_shops = st.sidebar.multiselect("Shops", options=shops, default=shops)
selected_kpi = st.sidebar.selectbox("KPI", options=kpis, index=kpis.index("net_revenue") if "net_revenue" in kpis else 0)

min_date, max_date = df["Date"].min(), df["Date"].max()
start_date, end_date = st.sidebar.slider(
    "Date range",
    min_value=min_date,
    max_value=max_date,
    value=(min_date, max_date),
    step=datetime.timedelta(days=31),
    format="MMM YYYY",
)

promo_toggle = st.sidebar.checkbox("Highlight Men’s Grooming Month (Aug 2023)", value=True)

########################
# 3. Filter the dataset #
########################

mask = (
    df["Shop"].isin(selected_shops)
    & (df["KPI"] == selected_kpi)
    & df["Date"].between(start_date, end_date)
)
filtered = df.loc[mask].copy()

################################
# 4. Summary metrics snapshot   #
################################

st.title("Scissors & Scotch KPI Dashboard")
readable_kpi = selected_kpi.replace("_", " ").title()
st.subheader(readable_kpi)

if filtered.empty:
    st.warning("No data for selected filters.")
    st.stop()

latest_date = max(filtered["Date"])
latest_df = filtered[filtered["Date"] == latest_date]

# Current aggregated value across selected shops
curr_val = latest_df["Value"].mean()

# MoM delta
prev_month_date = (datetime.date(latest_date.year, latest_date.month, 1) - datetime.timedelta(days=1)).replace(day=1)
prev_df = filtered[filtered["Date"] == prev_month_date]
prev_val = prev_df["Value"].mean() if not prev_df.empty else np.nan
mom_delta = (curr_val - prev_val) / prev_val * 100 if pd.notna(prev_val) and prev_val != 0 else np.nan

# YoY delta
try:
    yoy_date = datetime.date(latest_date.year - 1, latest_date.month, 1)
except ValueError:
    yoy_date = None
if yoy_date:
    yoy_df = filtered[filtered["Date"] == yoy_date]
    yoy_val = yoy_df["Value"].mean() if not yoy_df.empty else np.nan
else:
    yoy_val = np.nan

yoy_delta = (curr_val - yoy_val) / yoy_val * 100 if pd.notna(yoy_val) and yoy_val != 0 else np.nan

col1, col2, col3 = st.columns(3)
col1.metric("Latest (avg across shops)", f"{curr_val:,.2f}")
col2.metric("MoM ∆", f"{mom_delta:+.1f}%" if pd.notna(mom_delta) else "—")
col3.metric("YoY ∆", f"{yoy_delta:+.1f}%" if pd.notna(yoy_delta) else "—")

#########################
# 5. KPI trend line chart #
#########################

# Build pivot for Altair
pivot = filtered.pivot_table(index="Date", columns="Shop", values="Value")
chart_data = pivot.reset_index().melt(id_vars="Date", var_name="Shop", value_name="Value")

base = alt.Chart(chart_data).mark_line().encode(
    x=alt.X("Date:T", title="Month"),
    y=alt.Y("Value:Q", title=readable_kpi),
    color="Shop:N"
)

layers = [base]

# Promo shading (Aug 2023)
if promo_toggle:
    promo_start = datetime.date(2023, 8, 1)
    promo_end = datetime.date(2023, 8, 31)
    band = alt.Chart(pd.DataFrame({"start": [promo_start], "end": [promo_end]})).mark_rect(opacity=0.2, color="purple").encode(
        x="start:T",
        x2="end:T",
    )
    layers.append(band)

st.altair_chart(alt.layer(*layers).interactive(), use_container_width=True)

############################
# 6. Raw table (collapsible) #
############################

with st.expander("📄 Show raw data table"):
    st.dataframe(
        filtered[["Shop", "Date", "Value", "MoM_%", "YoY_%"]]
        .rename(columns={"Value": readable_kpi, "MoM_%": "MoM %", "YoY_%": "YoY %"})
        .sort_values(["Shop", "Date"]),
        use_container_width=True,
    )

#############################
# 7. CSV download of result #
#############################

csv_bytes = filtered.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇️ Download filtered data (CSV)",
    data=csv_bytes,
    mime="text/csv",
    file_name=f"{selected_kpi}_{start_date}_{end_date}.csv",
)

###################
# 8. Footer badge #
###################

st.caption("Powered by Streamlit · Data through Feb 2025 · v2.0")

