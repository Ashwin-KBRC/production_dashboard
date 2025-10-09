import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- PAGE SETTINGS ---
st.set_page_config(
    page_title="Daily Production Dashboard",
    layout="wide",
    page_icon="📊"
)

st.title("🏭 Daily Production Dashboard")
st.markdown("Upload your daily Excel file to view today's production performance.")

# --- FILE UPLOAD ---
uploaded_file = st.file_uploader("📤 Upload Excel File", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # --- BASIC CLEANUP ---
    df.columns = [c.strip() for c in df.columns]
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

    # --- EXCLUDE FRIDAYS ---
    df = df[df['Date'].dt.day_name() != 'Friday']

    if df.empty:
        st.warning("⚠️ No valid production data found (Friday is excluded).")
    else:
        # --- METRICS ---
        total_prod = df["Production for the Day (m³)"].sum()
        top_plant = df.loc[df["Production for the Day (m³)"].idxmax(), "Plant Name"]
        top_value = df["Production for the Day (m³)"].max()

        col1, col2 = st.columns(2)
        col1.metric("🔹 Total Production (m³)", f"{total_prod:,.2f}")
        col2.metric("🏆 Highest Producer", f"{top_plant} ({top_value:,.1f} m³)")

        st.divider()

        # --- CHART COLORS ---
        st.sidebar.header("🎨 Customize Chart Colors")
        pie_color = st.sidebar.color_picker("Pie Chart Base Color", "#007bff")
        bar_color = st.sidebar.color_picker("Bar Chart Base Color", "#28a745")
        line_color = st.sidebar.color_picker("Line Graph Base Color", "#ff7f0e")

        # --- PIE CHART ---
        st.subheader("🍰 Production Share per Plant (Today)")
        fig_pie = px.pie(
            df,
            names="Plant Name",
            values="Production for the Day (m³)",
            color_discrete_sequence=[pie_color],
            hole=0.3
        )
        st.plotly_chart(fig_pie, use_container_width=True)

        # --- BAR CHART ---
        st.subheader("📊 Production Comparison per Plant")
        fig_bar = px.bar(
            df,
            x="Plant Name",
            y="Production for the Day (m³)",
            color="Plant Name",
            color_discrete_sequence=[bar_color]*len(df),
            text_auto=True
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        # --- LINE CHART ---
        st.subheader("📈 Production Trend (if multiple days uploaded)")
        fig_line = px.line(
            df,
            x="Date",
            y="Production for the Day (m³)",
            color="Plant Name",
            markers=True,
            color_discrete_sequence=[line_color]
        )
        st.plotly_chart(fig_line, use_container_width=True)

        # --- ACCUMULATIVE CHART ---
        st.divider()
        st.subheader("📦 Accumulative Production Overview")
        fig_acc = px.bar(
            df,
            x="Plant Name",
            y="Accumulative Production (m³)",
            color="Plant Name",
            text_auto=True
        )
        st.plotly_chart(fig_acc, use_container_width=True)

        st.success("✅ Dashboard updated successfully!")

else:
    st.info("Please upload your Excel file to begin.")
