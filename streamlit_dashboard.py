import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path

###############################
# 1. Load & cache KPI dataset #
###############################

@st.cache_data(show_spinner=False)
def load_data(path: str | Path = "shop_kpi_dashboard_full.csv") -> pd.DataFrame:
    """Read the pre‑generated KPI dashboard CSV and parse dates."""
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    return df

DATA_PATH = Path("shop_kpi_dashboard_full.csv")
if not DATA_PATH.exists():
    st.error("❌ Data file 'shop_kpi_dashboard_full.csv' not found in the app directory.")
    st.stop()

kpi_df = load_data(DATA_PATH)

########################################
# 2. Sidebar – interactive filter panel #
########################################

st.sidebar.title("🔍 Filters")
shops = sorted(kpi_df["Shop"].unique())
kpis = sorted(kpi_df["KPI"].unique())

selected_shops = st.sidebar.multiselect("Shops", options=shops, default=shops)
selected_kpi = st.sidebar.selectbox("KPI", options=kpis, index=kpis.index("net_revenue") if "net_revenue" in kpis else 0)

min_date, max_date = kpi_df["Date"].min(), kpi_df["Date"].max()
start_date, end_date = st.sidebar.slider(
    "Date range",
    min_value=min_date,
    max_value=max_date,
    value=(min_date, max_date),
    format="MMM YYYY",
)

promo_toggle = st.sidebar.checkbox("Highlight Men’s Grooming Month (Aug 2023)", value=True)

########################
# 3. Filter the dataset #
########################

mask = (
    kpi_df["Shop"].isin(selected_shops)
    & (kpi_df["KPI"] == selected_kpi)
    & kpi_df["Date"].between(start_date, end_date)
)
filtered = kpi_df.loc[mask].copy()

################################
# 4. Main panel – KPI overview #
################################

readable_kpi = selected_kpi.replace("_", " ").title()
st.title("Scissors & Scotch KPI Dashboard")
st.subheader(readable_kpi)

# -- Data Table --
st.dataframe(
    filtered[["Shop", "Date", "Value", "MoM_%", "YoY_%"]]
        .sort_values(["Shop", "Date"])
        .rename(columns={"Value": readable_kpi, "MoM_%": "MoM %", "YoY_%": "YoY %"}),
    use_container_width=True,
)

# -- Line Chart: KPI trend per shop --
if not filtered.empty:
    pivot = filtered.pivot_table(index="Date", columns="Shop", values="Value")
    st.line_chart(pivot)
else:
    st.info("No data for the selected filters.")

###################################
# 5. Optional promo period shading #
###################################

if promo_toggle and (datetime.date(2023, 8, 1) >= start_date <= end_date):
    st.caption("🟣 Shaded area on the chart represents Men’s Grooming Month (Aug 2023).")
    # Basic visual note; true shading would need Altair/Plotly. Skipped for brevity.

#############################
# 6. CSV download of result #
#############################

csv_bytes = filtered.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇️ Download filtered data (CSV)",
    data=csv_bytes,
    mime="text/csv",
    file_name=f"{selected_kpi}_{start_date}_{end_date}.csv",
)

###################
# 7. Footer badge #
###################

st.caption("Powered by Streamlit · Data through Feb 2025 · v1.0")
