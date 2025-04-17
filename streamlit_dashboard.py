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

promo_toggle = st.sidebar.checkbox("Highlight Men’s Grooming Month (Aug 2023)", value=True)

# Choose aggregation method (sum vs average) – useful for volume vs rate KPIs
agg_method = st.sidebar.radio("Aggregation", options=["Average", "Sum"], index=0, horizontal=True)
agg_func = np.mean if agg_method == "Average" else np.sum

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

# latest month present in current filter window
latest_date = filtered["Date"].max()
latest_val = agg_func(filtered.loc[filtered["Date"] == latest_date, "Value"])

# Previous month available in filtered dataset (not calendar assumption)
mask_prev = filtered["Date"] < latest_date
if mask_prev.any():
    prev_date = filtered.loc[mask_prev, "Date"].max()
    prev_val = agg_func(filtered.loc[filtered["Date"] == prev_date, "Value"])
    mom_delta = (latest_val - prev_val) / prev_val * 100 if prev_val != 0 else np.nan
else:
    prev_date, prev_val, mom_delta = None, np.nan, np.nan

# YoY – look 12 months back from latest
try:
    yoy_date = datetime.date(latest_date.year - 1, latest_date.month, 1)
except ValueError:
    yoy_date = None
if yoy_date and (filtered["Date"] == yoy_date).any():
    yoy_val = agg_func(filtered.loc[filtered["Date"] == yoy_date, "Value"])
    yoy_delta = (latest_val - yoy_val) / yoy_val * 100 if yoy_val != 0 else np.nan
else:
    yoy_delta = np.nan

col1, col2, col3 = st.columns(3)
col1.metric("Latest ({} across shops)".format(agg_method.lower()), f"{latest_val:,.2f}")
col2.metric("MoM ∆", f"{mom_delta:+.1f}%" if pd.notna(mom_delta) else "—")
col3.metric("YoY ∆", f"{yoy_delta:+.1f}%" if pd.notna(yoy_delta) else "—")

#########################
# 5. KPI trend line chart #
#########################

pivot = filtered.pivot_table(index="Date", columns="Shop", values="Value", aggfunc="mean")
chart_data = pivot.reset_index().melt(id_vars="Date", var_name="Shop", value_name="Value")

base = alt.Chart(chart_data).mark_line().encode(
    x=alt.X("Date:T", title="Month"),
    y=alt.Y("Value:Q", title=readable_kpi),
    color="Shop:N",
    tooltip=["Shop", "Date:T", alt.Tooltip("Value:Q", format=",.2f")]
).interactive()

layers = [base]

if promo_toggle:
    promo_start = datetime.date(2023, 8, 1)
    promo_end = datetime.date(2023, 8, 31)
    band = alt.Chart(pd.DataFrame({"start": [promo_start], "end": [promo_end]})).mark_rect(opacity=0.15, color="#8e44ad").encode(
        x="start:T",
        x2="end:T",
    )
    layers.append(band)

st.altair_chart(alt.layer(*layers), use_container_width=True)

############################
# 6. Raw table (collapsible) #
############################

with st.expander("📄 Show raw data table"):
    table = filtered.copy()
    table = table.assign(Date=table["Date"].astype(str))  # nicer display
    st.dataframe(
        table[["Shop", "Date", "Value", "MoM_%", "YoY_%"]]
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

st.caption("Powered by Streamlit · Data through Feb 2025 · v2.1")


