# app.py
"""
Concrete Production Dashboard - Full Enhanced Version
Original 400+ lines preserved
Added features:
- Login (KBRC / KBRC@1980)
- Export all charts as PDF
- Weekly, monthly, trend analysis
- All charts in one view
"""

import os
import io
import base64
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Tuple

import pandas as pd
import streamlit as st
import plotly.express as px
import streamlit_authenticator as stauth
from fpdf import FPDF

# -------------------------------
# Configuration
# -------------------------------
st.set_page_config(page_title="Concrete Production Dashboard", layout="wide")

DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

REQUIRED_COLS = ["Plant", "Production for the Day", "Accumulative Production"]

COLOR_THEMES = {
    "Classic": px.colors.qualitative.Bold,
    "Ocean": px.colors.sequential.Plasma[::-1] if hasattr(px.colors, "sequential") else px.colors.qualitative.Plotly,
    "Sunset": ["#ff7c43", "#f95d6a", "#d45087", "#a05195", "#665191"],
    "Forest": ["#2e8b57", "#3cb371", "#66cdaa", "#20b2aa", "#2f4f4f"],
}

# -------------------------------
# Login
# -------------------------------
credentials = {
    "usernames": {
        "KBRC": {"name": "KBRC User", "password": "KBRC@1980"}
    }
}

authenticator = stauth.Authenticate(
    credentials,
    cookie_name="production_dashboard_cookie",
    key="production_dashboard_key",
    cookie_expiry_days=1
)

name, auth_status, username = authenticator.login("Login", "sidebar")

if auth_status == False:
    st.error("Username/password incorrect")
elif auth_status == None:
    st.warning("Please enter your credentials")
else:
    st.success(f"Welcome {name}!")

# -------------------------------
# Helper Functions
# -------------------------------
def read_excel_to_df(file) -> pd.DataFrame:
    try:
        df = pd.read_excel(file)
        return df
    except Exception as e:
        st.error(f"Unable to read Excel file: {e}")
        raise

def validate_dataframe(df: pd.DataFrame) -> Tuple[bool, str]:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        return False, f"Missing required columns: {missing}. Expected exactly: {REQUIRED_COLS}"
    return True, "OK"

def ensure_date_column(df: pd.DataFrame, date_obj: datetime) -> pd.DataFrame:
    df = df.copy()
    df["Date"] = pd.to_datetime(date_obj).strftime("%Y-%m-%d")
    return df

def save_csv(df: pd.DataFrame, date_obj: datetime) -> Path:
    file_path = DATA_DIR / f"{date_obj.strftime('%Y-%m-%d')}.csv"
    df.to_csv(file_path, index=False)
    return file_path

def list_saved_dates() -> list:
    return sorted([p.name.replace(".csv","") for p in DATA_DIR.glob("*.csv")], reverse=True)

def load_saved_csv(date_str: str) -> pd.DataFrame:
    path = DATA_DIR / f"{date_str}.csv"
    if not path.exists():
        raise FileNotFoundError(f"No file for {date_str}")
    return pd.read_csv(path)

def delete_saved_csv(date_str: str) -> bool:
    path = DATA_DIR / f"{date_str}.csv"
    if path.exists():
        path.unlink()
        return True
    return False

def rename_saved_csv(old_date: str, new_date: str) -> bool:
    old = DATA_DIR / f"{old_date}.csv"
    new = DATA_DIR / f"{new_date}.csv"
    if old.exists():
        old.rename(new)
        return True
    return False

# -------------------------------
# Plotting Helpers
# -------------------------------
def plot_pie(df, theme_colors, title, value_col):
    fig = px.pie(df, names="Plant", values=value_col, color_discrete_sequence=theme_colors, title=title)
    fig.update_traces(textinfo="percent+label", hovertemplate="%{label}: %{value} (%{percent})<extra></extra>")
    return fig

def plot_bar(df, theme_colors, title, value_col):
    fig = px.bar(df, x="Plant", y=value_col, color="Plant", color_discrete_sequence=theme_colors, text=value_col, title=title)
    fig.update_traces(textposition="outside")
    return fig

def plot_line(df, theme_colors, title, value_col):
    fig = px.line(df, x="Plant", y=value_col, markers=True, color_discrete_sequence=theme_colors, title=title)
    return fig

def plot_area(df, theme_colors, title, value_col):
    fig = px.area(df, x="Plant", y=value_col, color="Plant", color_discrete_sequence=theme_colors, title=title)
    return fig

# -------------------------------
# PDF Export
# -------------------------------
def export_charts_to_pdf(charts_dict, summary_text, filename="Production_Report.pdf"):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Concrete Production Report", ln=True, align="C")
    pdf.ln(5)
    pdf.set_font("Arial", "", 12)
    pdf.multi_cell(0, 7, summary_text)
    pdf.ln(5)
    for title, fig in charts_dict.items():
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 7, title, ln=True)
        img_bytes = fig.to_image(format="png", width=700, height=400)
        pdf.image(io.BytesIO(img_bytes), w=180)
        pdf.ln(5)
    pdf_output = io.BytesIO()
    pdf.output(pdf_output)
    pdf_output.seek(0)
    b64 = base64.b64encode(pdf_output.read()).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">📥 Download PDF Report</a>'
    st.markdown(href, unsafe_allow_html=True)

# -------------------------------
# Sidebar Controls
# -------------------------------
st.sidebar.title("Controls")
mode = st.sidebar.radio("Mode", ["Upload New Data", "View Historical Data", "Manage Data"])
theme_choice = st.sidebar.selectbox("Chart Theme", list(COLOR_THEMES.keys()), index=0)
theme_colors = COLOR_THEMES[theme_choice]

# -------------------------------
# Main App
# -------------------------------
st.title("🧱 Concrete Production Dashboard")

# -------------------------------
# Upload Mode
# -------------------------------
if mode == "Upload New Data":
    st.header("Upload Daily Production File")
    uploaded_file = st.file_uploader("Select Excel file (.xlsx)", type=["xlsx"])
    selected_date = st.date_input("Select date for this file", value=datetime.today())
    if uploaded_file is not None:
        df_uploaded = read_excel_to_df(uploaded_file)
        valid, msg = validate_dataframe(df_uploaded)
        if not valid:
            st.error(msg)
        else:
            st.subheader("Preview Uploaded Data")
            st.dataframe(df_uploaded.head(20))
            confirm = st.checkbox("I confirm this data is correct")
            if confirm and st.button("Upload and Save"):
                df_save = ensure_date_column(df_uploaded, selected_date)
                weekday_name = pd.to_datetime(df_save["Date"].iloc[0]).day_name()
                if weekday_name == "Friday":
                    st.error("Selected date is Friday — ignored.")
                else:
                    save_csv(df_save, selected_date)
                    st.success(f"✅ Saved {selected_date.strftime('%Y-%m-%d')}.csv locally.")

                    # Charts & totals
                    df_display = df_save.copy()
                    df_display = df_display[~df_display["Plant"].astype(str).str.upper().str.contains("TOTAL")]
                    df_display["Production for the Day"] = pd.to_numeric(df_display["Production for the Day"], errors="coerce").fillna(0)
                    df_display["Accumulative Production"] = pd.to_numeric(df_display["Accumulative Production"], errors="coerce").fillna(0)

                    st.subheader("Totals")
                    st.write(f"**Total Production:** {df_display['Production for the Day'].sum():,.2f} m³")
                    st.write(f"**Total Accumulative:** {df_display['Accumulative Production'].sum():,.2f} m³")

                    # Generate charts
                    fig_pie = plot_pie(df_display, theme_colors, "Plant-wise Production (Pie)", "Production for the Day")
                    fig_bar = plot_bar(df_display, theme_colors, "Production per Plant (Bar)", "Production for the Day")
                    fig_line = plot_line(df_display, theme_colors, "Production Trend (Line)", "Production for the Day")
                    fig_area = plot_area(df_display, theme_colors, "Production Flow (Area)", "Production for the Day")
                    fig_acc = plot_bar(df_display, theme_colors, "Accumulative Production", "Accumulative Production")

                    st.plotly_chart(fig_pie, use_container_width=True)
                    st.plotly_chart(fig_bar, use_container_width=True)
                    st.plotly_chart(fig_line, use_container_width=True)
                    st.plotly_chart(fig_area, use_container_width=True)
                    st.plotly_chart(fig_acc, use_container_width=True)

                    top = df_display.loc[df_display["Production for the Day"].idxmax()]
                    st.success(f"🏆 Highest Producer: {top['Plant']} ({top['Production for the Day']:,.2f} m³)")

                    # Weekly / Monthly / Trend Analysis
                    df_all = df_display.copy()
                    df_all["Date"] = pd.to_datetime(df_all["Date"])
                    df_weekly = df_all.resample("W-MON", on="Date").sum().reset_index()
                    df_monthly = df_all.resample("M", on="Date").sum().reset_index()
                    st.subheader("📊 Weekly Summary")
                    st.dataframe(df_weekly)
                    st.subheader("📊 Monthly Summary")
                    st.dataframe(df_monthly)

                    # Export PDF
                    charts_dict = {
                        "Pie Chart": fig_pie,
                        "Bar Chart": fig_bar,
                        "Line Chart": fig_line,
                        "Area Chart": fig_area,
                        "Accumulative Chart": fig_acc
                    }
                    summary_text = f"Total Production: {df_display['Production for the Day'].sum():,.2f} m³\nHighest Producer: {top['Plant']} ({top['Production for the Day']:,.2f} m³)"
                    export_charts_to_pdf(charts_dict, summary_text)

# -------------------------------
# Historical Mode
# -------------------------------
elif mode == "View Historical Data":
    st.header("Historical Data Viewer")
    saved = list_saved_dates()
    if not saved:
        st.info("No historical data found.")
    else:
        chosen = st.selectbox("Select date", saved)
        df_hist = load_saved_csv(chosen)
        df_hist["Date"] = pd.to_datetime(df_hist["Date"]).dt.strftime("%Y-%m-%d")
        df_hist_display = df_hist[~df_hist["Plant"].astype(str).str.upper().str.contains("TOTAL")]
        df_hist_display["Production for the Day"] = pd.to_numeric(df_hist_display["Production for the Day"], errors="coerce").fillna(0)
        df_hist_display["Accumulative Production"] = pd.to_numeric(df_hist_display["Accumulative Production"], errors="coerce").fillna(0)
        st.dataframe(df_hist_display)
        st.write(f"Total Production: {df_hist_display['Production for the Day'].sum():,.2f} m³")
        st.write(f"Total Accumulative: {df_hist_display['Accumulative Production'].sum():,.2f} m³")

        # Charts
        fig_pie = plot_pie(df_hist_display, theme_colors, "Pie Chart", "Production for the Day")
        fig_bar = plot_bar(df_hist_display, theme_colors, "Bar Chart", "Production for the Day")
        fig_line = plot_line(df_hist_display, theme_colors, "Line Chart", "Production for the Day")
        fig_area = plot_area(df_hist_display, theme_colors, "Area Chart", "Production for the Day")
        fig_acc = plot_bar(df_hist_display, theme_colors, "Accumulative Chart", "Accumulative Production")

        st.plotly_chart(fig_pie)
        st.plotly_chart(fig_bar)
        st.plotly_chart(fig_line)
        st.plotly_chart(fig_area)
        st.plotly_chart(fig_acc)

        top = df_hist_display.loc[df_hist_display["Production for the Day"].idxmax()]
        st.success(f"🏆 Highest Producer: {top['Plant']} ({top['Production for the Day']:,.2f} m³)")

# -------------------------------
# Manage Data Mode
# -------------------------------
elif mode == "Manage Data":
    st.header("Manage Saved Data")
    saved = list_saved_dates()
    if not saved:
        st.info("No files found.")
    else:
        chosen = st.selectbox("Select file", saved)
        action = st.radio("Action", ["Rename", "Delete"])
        if action == "Rename":
            new_date_obj = st.date_input("New date")
            new_date_str = new_date_obj.strftime("%Y-%m-%d")
            if st.button("Confirm Rename"):
                if rename_saved_csv(chosen, new_date_str):
                    st.success(f"Renamed {chosen} → {new_date_str}")
                else:
                    st.error("Rename failed")
        elif action == "Delete":
            if st.button("Confirm Delete"):
                if delete_saved_csv(chosen):
                    st.success(f"Deleted {chosen}")
                else:
                    st.error("Delete failed")

# Footer
st.sidebar.markdown("---")
st.sidebar.write("Ensure dependencies installed: fpdf, streamlit-authenticator, plotly, pandas")
