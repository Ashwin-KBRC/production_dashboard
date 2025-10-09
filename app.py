import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- Page Configuration ---
st.set_page_config(page_title="Concrete Production Dashboard", layout="wide")

# --- Title ---
st.title("🧱 PRODUCTION FOR THE DAY")
st.write("Upload your daily Excel file and select the correct date to visualize daily and accumulative production data.")

# --- File Upload ---
uploaded_file = st.file_uploader("📤 Upload Excel file", type=["xlsx"])

# --- Date Selector ---
selected_date = st.date_input("📅 On which date is this file for?")

if uploaded_file:
    # Read Excel File
    df = pd.read_excel(uploaded_file)

    # Expected columns check
    required_cols = ["Plant", "Production for the Day", "Accumulative Production"]
    if not all(col in df.columns for col in required_cols):
        st.error(f"Your file must contain these columns exactly: {required_cols}")
    else:
        # Add selected date to all rows
        df["Date"] = pd.to_datetime(selected_date)

        # Remove Fridays (off day)
        df = df[df["Date"].dt.day_name() != "Friday"]

        # Remove any total row for visual clarity (optional)
        df_display = df[df["Plant"].str.upper() != "TOTAL"]

        # --- Display Data Table ---
        st.subheader("📋 Production Data Table")
        st.dataframe(df_display, use_container_width=True)

        # --- Daily Charts Section ---
        st.subheader("🌈 Daily Production Charts")
        color_scheme = px.colors.qualitative.Bold

        # Pie Chart
        pie_chart = px.pie(df_display, names="Plant", values="Production for the Day",
                           title="Plant-wise Production (Pie Chart)",
                           color_discrete_sequence=color_scheme)
        st.plotly_chart(pie_chart, use_container_width=True)

        # Bar Chart
        bar_chart = px.bar(df_display, x="Plant", y="Production for the Day", color="Plant",
                           title="Production per Plant (Bar Chart)",
                           color_discrete_sequence=color_scheme)
        st.plotly_chart(bar_chart, use_container_width=True)

        # Line Chart
        line_chart = px.line(df_display, x="Plant", y="Production for the Day", markers=True,
                             title="Production Trend (Line Chart)",
                             color_discrete_sequence=color_scheme)
        st.plotly_chart(line_chart, use_container_width=True)

        # Area Chart
        area_chart = px.area(df_display, x="Plant", y="Production for the Day", color="Plant",
                             title="Production Flow (Area Chart)",
                             color_discrete_sequence=color_scheme)
        st.plotly_chart(area_chart, use_container_width=True)

        # --- Highlight Top Producer ---
        highest_row = df_display.loc[df_display["Production for the Day"].idxmax()]
        st.success(f"🏆 **Highest Producer Today:** {highest_row['Plant']} with {highest_row['Production for the Day']} m³")

        # --- Accumulative Chart ---
        st.subheader("📈 Accumulative Production Overview")
        acc_chart = px.bar(df_display, x="Plant", y="Accumulative Production", color="Plant",
                           title="Accumulative Production per Plant",
                           color_discrete_sequence=color_scheme)
        st.plotly_chart(acc_chart, use_container_width=True)

else:
    st.info("Please upload an Excel file to begin.")
