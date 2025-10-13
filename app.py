# app.py
"""
Concrete Production Dashboard - Full Enhanced Version
Features:
- Simple login (username/password)
- Upload daily Excel (.xlsx)
- Weekly & monthly analysis
- 7-day moving average trend analysis
- Export charts and summary as PDF
- Historical data view
- Rename/Delete saved files
- Chart themes
"""

import os
from pathlib import Path
from datetime import datetime
import io
import base64

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
# Authentication (Simple)
# -------------------------------
names = ["KBRC User"]
usernames = ["KBRC"]
passwords = ["KBRC@1980"]

authenticator = stauth.Authenticate(
    names,
    usernames,
    passwords,
    "cookie_name",
    "signature_key"
)

name, auth_status, username = authenticator.login("Login", "main")

if auth_status != True:
    if auth_status == False:
        st.error("Username/password incorrect")
    elif auth_status == None:
        st.warning("Please enter your credentials")
    st.stop()

st.success(f"Welcome {name}!")

# -------------------------------
# Helper Functions
# -------------------------------
def read_excel_to_df(file):
    try:
        return pd.read_excel(file)
    except Exception as e:
        st.error(f"Unable to read Excel: {e}")
        raise

def validate_dataframe(df):
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        return False, f"Missing required columns: {missing}"
    return True, "OK"

def ensure_date_column(df, date_obj):
    df = df.copy()
    df["Date"] = pd.to_datetime(date_obj).strftime("%Y-%m-%d")
    return df

def save_csv(df, date_obj):
    file_path = DATA_DIR / f"{date_obj.strftime('%Y-%m-%d')}.csv"
    df.to_csv(file_path, index=False)
    return file_path

def list_saved_dates():
    return sorted([p.name.replace(".csv","") for p in DATA_DIR.glob("*.csv")], reverse=True)

def load_saved_csv(date_str):
    path = DATA_DIR / f"{date_str}.csv"
    if not path.exists():
        raise FileNotFoundError(f"No file for {date_str}")
    return pd.read_csv(path)

def delete_saved_csv(date_str):
    path = DATA_DIR / f"{date_str}.csv"
    if path.exists():
        path.unlink()
        return True
    return False

def rename_saved_csv(old_date, new_date):
    old = DATA_DIR / f"{old_date}.csv"
    new = DATA_DIR / f"{new_date}.csv"
    if old.exists():
        old.rename(new)
        return True
    return False

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

def export_pdf(charts_dict, summary_text, filename="Production_Report.pdf"):
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
mode = st.sidebar.radio("Mode", ["Upload New Data", "Historical & Analytics", "Manage Data"])
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
    st.header("Upload Daily Production Data")
    uploaded_file = st.file_uploader("Select Excel file", type=["xlsx"])
    selected_date = st.date_input("Select date", value=datetime.today())

    if uploaded_file:
        df_uploaded = read_excel_to_df(uploaded_file)
        valid, msg = validate_dataframe(df_uploaded)
        if not valid:
            st.error(msg)
        else:
            st.subheader("Preview")
            st.dataframe(df_uploaded.head(20))
            confirm = st.checkbox("Confirm data is correct")
            if confirm:
                if st.button("Save Data"):
                    df_save = ensure_date_column(df_uploaded, selected_date)
                    weekday_name = pd.to_datetime(df_save["Date"].iloc[0]).day_name()
                    if weekday_name == "Friday":
                        st.error("Selected date is Friday. Skipping upload.")
                    else:
                        file_path = save_csv(df_save, selected_date)
                        st.success(f"Saved: {file_path}")

                        # Prepare charts
                        df_display = df_save.copy()
                        df_display = df_display[~df_display["Plant"].astype(str).str.upper().str.contains("TOTAL")]
                        df_display["Production for the Day"] = pd.to_numeric(df_display["Production for the Day"], errors="coerce").fillna(0)
                        df_display["Accumulative Production"] = pd.to_numeric(df_display["Accumulative Production"], errors="coerce").fillna(0)

                        st.subheader("Charts")
                        col1, col2 = st.columns(2)
                        charts = {}
                        with col1:
                            fig_pie = plot_pie(df_display, theme_colors, "Plant-wise Production (Pie)", "Production for the Day")
                            st.plotly_chart(fig_pie, use_container_width=True)
                            charts["Pie Chart"] = fig_pie
                        with col2:
                            fig_bar = plot_bar(df_display, theme_colors, "Production per Plant (Bar)", "Production for the Day")
                            st.plotly_chart(fig_bar, use_container_width=True)
                            charts["Bar Chart"] = fig_bar

                        total_daily = df_display["Production for the Day"].sum()
                        total_acc = df_display["Accumulative Production"].sum()
                        summary_text = f"Date: {selected_date}\nTotal Production Today: {total_daily:.2f} m³\nTotal Accumulative Production: {total_acc:.2f} m³"
                        export_pdf(charts, summary_text)

# -------------------------------
# Historical & Analytics Mode
# -------------------------------
elif mode == "Historical & Analytics":
    st.header("Historical & Trend Analysis")
    saved_dates = list_saved_dates()
    if not saved_dates: st.info("No saved files yet")
    else:
        chosen_date = st.selectbox("Select date", saved_dates)
        df_hist = load_saved_csv(chosen_date)
        df_hist["Date"] = pd.to_datetime(df_hist["Date"])
        df_hist["Production for the Day"] = pd.to_numeric(df_hist["Production for the Day"], errors="coerce").fillna(0)
        df_hist["Accumulative Production"] = pd.to_numeric(df_hist["Accumulative Production"], errors="coerce").fillna(0)
        st.subheader(f"Data for {chosen_date}")
        st.dataframe(df_hist)

        # Aggregate all data
        df_all = pd.concat([load_saved_csv(d).assign(Date=pd.to_datetime(d)) for d in saved_dates])
        df_all["Production for the Day"] = pd.to_numeric(df_all["Production for the Day"], errors="coerce").fillna(0)

        # Weekly
        df_weekly = df_all.groupby([pd.Grouper(key='Date', freq='W-MON'), 'Plant']).sum().reset_index()
        st.subheader("Weekly Analysis")
        fig_weekly = px.bar(df_weekly, x="Date", y="Production for the Day", color="Plant", text="Production for the Day")
        st.plotly_chart(fig_weekly, use_container_width=True)

        # Monthly
        df_monthly = df_all.groupby([pd.Grouper(key='Date', freq='M'), 'Plant']).sum().reset_index()
        st.subheader("Monthly Analysis")
        fig_monthly = px.bar(df_monthly, x="Date", y="Production for the Day", color="Plant", text="Production for the Day")
        st.plotly_chart(fig_monthly, use_container_width=True)

        # Trend analysis - 7 day moving avg
        st.subheader("Trend Analysis (7-day MA)")
        df_trend = df_all.groupby("Date").sum().reset_index()
        df_trend["7d_MA"] = df_trend["Production for the Day"].rolling(7).mean()
        fig_trend = px.line(df_trend, x="Date", y=["Production for the Day","7d_MA"], markers=True)
        st.plotly_chart(fig_trend, use_container_width=True)

# -------------------------------
# Manage Data
# -------------------------------
elif mode == "Manage Data":
    st.header("Manage Saved Data")
    saved_dates = list_saved_dates()
    if not saved_dates: st.info("No files saved yet")
    else:
        chosen = st.selectbox("Select file", saved_dates)
        action = st.radio("Action", ["Rename","Delete"])
        if action=="Rename":
            new_date = st.date_input("New date")
            new_date_str = new_date.strftime("%Y-%m-%d")
            if st.button("Confirm Rename"):
                if rename_saved_csv(chosen,new_date_str):
                    st.success(f"{chosen} renamed to {new_date_str}")
                else:
                    st.error("Rename failed")
        elif action=="Delete":
            if st.button("Confirm Delete"):
                if delete_saved_csv(chosen):
                    st.success(f"{chosen} deleted")
                else:
                    st.error("Delete failed")
