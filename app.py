import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime

# --- Page Configuration ---
st.set_page_config(page_title="Concrete Production Dashboard", layout="wide")

# --- Title ---
st.title("🧱 PRODUCTION FOR THE DAY")
st.write("Upload your daily Excel file and select the correct date to visualize daily and accumulative production data. All uploads are stored for historical viewing.")

# --- Ensure Data Folder Exists ---
DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# --- Load Available Historical Data ---
available_dates = sorted(
    [f.replace(".csv", "") for f in os.listdir(DATA_DIR) if f.endswith(".csv")]
)

# --- Date Selection or Upload ---
st.sidebar.header("📅 Data Options")

mode = st.sidebar.radio("Choose mode:", ["View Historical Data", "Upload New Data"])

if mode == "View Historical Data":
    if available_dates:
        selected_date = st.sidebar.selectbox("Select a date to view:", available_dates)
        file_path = os.path.join(DATA_DIR, f"{selected_date}.csv")
        df = pd.read_csv(file_path)
        st.success(f"Loaded saved data for **{selected_date}** ✅")
    else:
        st.warning("No historical data found. Please upload a new file first.")
        df = None

elif mode == "Upload New Data":
    uploaded_file = st.file_uploader("📤 Upload Excel file", type=["xlsx"])
    selected_date = st.date_input("📅 On which date is this file for?")

    if uploaded_file:
        # Read Excel File
        df = pd.read_excel(uploaded_file)

        required_cols = ["Plant", "Production for the Day", "Accumulative Production"]
        if not all(col in df.columns for col in required_cols):
            st.error(f"Your file must contain these columns exactly: {required_cols}")
            df = None
        else:
            # Add Date Column
            df["Date"] = pd.to_datetime(selected_date)

            # Remove Fridays
            df = df[df["Date"].dt.day_name() != "Friday"]

            # Remove TOTAL row
            df = df[df["Plant"].str.upper() != "TOTAL"]

            # Save a copy in CSV format (for history)
            save_path = os.path.join(DATA_DIR, f"{selected_date}.csv")
            df.to_csv(save_path, index=False)
            st.success(f"✅ Data for {selected_date} saved successfully and added to history.")
    else:
        df = None

# --- If Data is Available ---
if 'df' in locals() and df is not None and not df.empty:
    # --- Display Table ---
    st.subheader("📋 Production Data Table")
    st.dataframe(df, use_container_width=True)

    # --- Totals ---
    total_daily = df["Production for the Day"].sum()
    total_acc = df["Accumulative Production"].sum()
    st.markdown(f"### 🔹 Total Production for the Day: **{total_daily:.2f} m³**")
    st.markdown(f"### 🔹 Total Accumulative Production: **{total_acc:.2f} m³**")

    # --- Charts ---
    st.subheader("🌈 Daily Production Charts")
    color_scheme = px.colors.qualitative.Bold

    pie_chart = px.pie(df, names="Plant", values="Production for the Day",
                       title="Plant-wise Production (Pie Chart)",
                       color_discrete_sequence=color_scheme)
    st.plotly_chart(pie_chart, use_container_width=True)

    bar_chart = px.bar(df, x="Plant", y="Production for the Day", color="Plant",
                       title="Production per Plant (Bar Chart)",
                       color_discrete_sequence=color_scheme)
    st.plotly_chart(bar_chart, use_container_width=True)

    line_chart = px.line(df, x="Plant", y="Production for the Day", markers=True,
                         title="Production Trend (Line Chart)",
                         color_discrete_sequence=color_scheme)
    st.plotly_chart(line_chart, use_container_width=True)

    area_chart = px.area(df, x="Plant", y="Production for the Day", color="Plant",
                         title="Production Flow (Area Chart)",
                         color_discrete_sequence=color_scheme)
    st.plotly_chart(area_chart, use_container_width=True)

    # --- Highest Producer ---
    highest_row = df.loc[df["Production for the Day"].idxmax()]
    st.success(f"🏆 **Highest Producer Today:** {highest_row['Plant']} with {highest_row['Production for the Day']} m³")

    # --- Accumulative Chart ---
    st.subheader("📈 Accumulative Production Overview")
    acc_chart = px.bar(df, x="Plant", y="Accumulative Production", color="Plant",
                       title="Accumulative Production per Plant",
                       color_discrete_sequence=color_scheme)
    st.plotly_chart(acc_chart, use_container_width=True)

else:
    st.info("Please upload or select a file to begin.")
