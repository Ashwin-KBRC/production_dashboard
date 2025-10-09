import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Concrete Production Dashboard", layout="wide")

st.title("🧱 PRODUCTION FOR THE DAY")

st.write("Upload your daily Excel file below. The app will display today's and accumulative production data with charts.")

uploaded_file = st.file_uploader("📤 Upload Excel file", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # Ensure required columns exist
    required_columns = ["Date", "Plant", "Production", "Type"]
    if not all(col in df.columns for col in required_columns):
        st.error(f"Your file must contain these columns: {required_columns}")
    else:
        # Convert date
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

        # Filter out Fridays
        df = df[df["Date"].dt.day_name() != "Friday"]

        # Separate daily and accumulative data
        daily_df = df[df["Type"].str.lower() == "daily"]
        acc_df = df[df["Type"].str.lower() == "accumulative"]

        st.subheader("📊 Production Summary Table")
        st.dataframe(daily_df[["Date", "Plant", "Production"]])

        # --- Daily Production Charts ---
        st.subheader("🌈 Daily Production Charts")

        color_scheme = px.colors.qualitative.Vivid

        # Pie chart
        pie_fig = px.pie(daily_df, names="Plant", values="Production", title="Plant-wise Production (Pie Chart)", color_discrete_sequence=color_scheme)
        st.plotly_chart(pie_fig, use_container_width=True)

        # Bar chart
        bar_fig = px.bar(daily_df, x="Plant", y="Production", color="Plant",
                         title="Production per Plant (Bar Chart)", color_discrete_sequence=color_scheme)
        st.plotly_chart(bar_fig, use_container_width=True)

        # Line chart (trend)
        line_fig = px.line(daily_df, x="Plant", y="Production", markers=True,
                           title="Production Trend per Plant", color_discrete_sequence=color_scheme)
        st.plotly_chart(line_fig, use_container_width=True)

        # Flow-like area chart
        area_fig = px.area(daily_df, x="Plant", y="Production", color="Plant",
                           title="Production Flow (Area Chart)", color_discrete_sequence=color_scheme)
        st.plotly_chart(area_fig, use_container_width=True)

        # --- Highest Producer ---
        highest = daily_df.loc[daily_df["Production"].idxmax()]
        st.success(f"🏆 **Highest Producer Today:** {highest['Plant']} with {highest['Production']} m³")

        # --- Accumulative Chart ---
        if not acc_df.empty:
            st.subheader("📈 Accumulative Production Overview")
            acc_chart = px.bar(acc_df, x="Plant", y="Production", color="Plant",
                               title="Total Accumulative Production", color_discrete_sequence=color_scheme)
            st.plotly_chart(acc_chart, use_container_width=True)
        else:
            st.info("No accumulative data found in this file.")

else:
    st.info("Please upload an Excel file to view the dashboard.")
