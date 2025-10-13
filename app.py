# app.py
"""
Production Dashboard - Final version
Features:
- Upload daily Excel file (choose date)
- Confirmation before saving/uploading
- Save to data/YYYY-MM-DD.csv
- Attempt to push to GitHub using token from Streamlit Secrets
- Historical view (select any saved date)
- Rename/Delete saved date files (with confirmation)
- 4 chart themes
- Value labels on charts and top-producer highlight
- Ignores Fridays
- Export charts and tables to PDF
- Weekly and monthly analysis
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple
from fpdf import FPDF
import tempfile

# -------------------------------
# Configuration
# -------------------------------
st.set_page_config(page_title="Concrete Production Dashboard", layout="wide")

# Repo and data folder (adjust repo string if needed)
GITHUB_REPO = os.getenv("GITHUB_REPO", "Ashwin-KBRC/production_dashboard")
DATA_DIR = Path("data")
TOKEN = os.getenv("GITHUB_TOKEN")  # Set this in Streamlit Secrets as TOML: GITHUB_TOKEN="ghp_..."

# Required column names (exact)
REQUIRED_COLS = ["Plant", "Production for the Day", "Accumulative Production"]

# Color themes
COLOR_THEMES = {
    "Classic": px.colors.qualitative.Bold,
    "Ocean": px.colors.sequential.Plasma[::-1] if hasattr(px.colors, "sequential") else px.colors.qualitative.Plotly,
    "Sunset": ["#ff7c43", "#f95d6a", "#d45087", "#a05195", "#665191"],
    "Forest": ["#2e8b57", "#3cb371", "#66cdaa", "#20b2aa", "#2f4f4f"],
}

# Make sure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------------
# Helper functions
# -------------------------------
def read_excel_to_df(file) -> pd.DataFrame:
    """Read uploaded excel file into pandas DataFrame."""
    try:
        df = pd.read_excel(file)
        return df
    except Exception as e:
        st.error(f"Unable to read Excel file: {e}")
        raise


def validate_dataframe(df: pd.DataFrame) -> Tuple[bool, str]:
    """Check for required columns and return (valid, message)."""
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        return False, f"Missing required columns: {missing}. Expected exactly: {REQUIRED_COLS}"
    return True, "OK"


def ensure_date_column(df: pd.DataFrame, date_obj: datetime.date) -> pd.DataFrame:
    """Ensure the Date column exists and is standardized to YYYY-MM-DD strings."""
    df = df.copy()
    df["Date"] = pd.to_datetime(date_obj).strftime("%Y-%m-%d")
    return df


def save_csv_and_attempt_push(df: pd.DataFrame, date_obj: datetime.date) -> Tuple[bool, str]:
    """
    Save the df to data/YYYY-MM-DD.csv.
    Attempt to push to GitHub via git commands using TOKEN if present.
    Returns: (pushed_boolean, message)
    """
    date_str = date_obj.strftime("%Y-%m-%d")
    file_path = DATA_DIR / f"{date_str}.csv"
    df.to_csv(file_path, index=False)

    # Try to commit & push
    if not TOKEN:
        return False, "GITHUB_TOKEN not configured in environment (Streamlit Secrets). File saved locally."

    # Use the token in the remote URL for push
    remote_url = f"https://{TOKEN}@github.com/{GITHUB_REPO}.git"

    try:
        # Configure git user (local config in container)
        subprocess.run(["git", "config", "--global", "user.email", "streamlit@example.com"], check=False)
        subprocess.run(["git", "config", "--global", "user.name", "Streamlit App"], check=False)

        # Add file
        subprocess.run(["git", "add", str(file_path)], check=True)

        # Commit - may fail if no changes; capture output
        commit_proc = subprocess.run(["git", "commit", "-m", f"Add production data for {date_str}"], check=False, capture_output=True, text=True)
        if commit_proc.returncode != 0:
            stdout = commit_proc.stdout + commit_proc.stderr
            # If nothing to commit, treat as OK (not an error)
            if "nothing to commit" in stdout.lower() or "no changes added to commit" in stdout.lower():
                # No new changes - still treated as success but nothing pushed
                return True, "File saved; no new changes to commit (already present)."
            else:
                return False, f"Git commit failed: {stdout.strip()}"

        # Push
        push_proc = subprocess.run(["git", "push", remote_url, "main"], check=False, capture_output=True, text=True)
        if push_proc.returncode != 0:
            return False, f"Git push failed: {push_proc.stderr.strip() or push_proc.stdout.strip()}"
        return True, "File saved and pushed to GitHub successfully."

    except Exception as ex:
        return False, f"Exception while pushing: {ex}"


def list_saved_dates() -> list:
    """Return list of YYYY-MM-DD strings saved in data folder sorted descending."""
    files = sorted([p.name.replace(".csv", "") for p in DATA_DIR.glob("*.csv")], reverse=True)
    return files


def load_saved_csv(date_str: str) -> pd.DataFrame:
    """Load a saved CSV by date string."""
    path = DATA_DIR / f"{date_str}.csv"
    if not path.exists():
        raise FileNotFoundError(f"No saved file for {date_str}")
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
# Plotting helpers (plotly)
# -------------------------------
def plot_production_pie(df: pd.DataFrame, theme_colors: list, title: str, value_col: str):
    """Return a plotly pie figure with labels and hover that includes value labels in the hover."""
    fig = px.pie(df, names="Plant", values=value_col, title=title, color_discrete_sequence=theme_colors)
    # show percentage + value in hover
    fig.update_traces(textinfo="percent+label", hovertemplate="%{label}: %{value} (%{percent})<extra></extra>")
    return fig


def plot_production_bar(df: pd.DataFrame, theme_colors: list, title: str, value_col: str):
    """Return a plotly bar figure with values displayed on top of bars."""
    fig = px.bar(df, x="Plant", y=value_col, title=title, color="Plant", color_discrete_sequence=theme_colors, text=value_col)
    fig.update_traces(textposition="outside")
    fig.update_layout(uniformtext_minsize=8, uniformtext_mode="hide", xaxis_title=None, yaxis_title="m³")
    return fig


def plot_production_line(df: pd.DataFrame, theme_colors: list, title: str, value_col: str):
    fig = px.line(df, x="Plant", y=value_col, title=title, markers=True, color_discrete_sequence=theme_colors)
    return fig


def plot_production_area(df: pd.DataFrame, theme_colors: list, title: str, value_col: str):
    fig = px.area(df, x="Plant", y=value_col, title=title, color="Plant", color_discrete_sequence=theme_colors)
    return fig


# -------------------------------
# PDF Export function
# -------------------------------
def export_charts_to_pdf(df: pd.DataFrame, date_label: str, theme_colors: list):
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"Production Report — {date_label}", ln=True, align="C")
    pdf.ln(5)

    # Table
    pdf.set_font("Arial", "", 12)
    col_width = 60
    row_height = 8
    for i, col in enumerate(df.columns):
        pdf.cell(col_width, row_height, str(col), border=1)
    pdf.ln(row_height)
    for index, row in df.iterrows():
        for col in df.columns:
            pdf.cell(col_width, row_height, str(row[col]), border=1)
        pdf.ln(row_height)
    pdf.ln(5)

    # Charts
    chart_types = [
        ("Pie Chart", plot_production_pie),
        ("Bar Chart", plot_production_bar),
        ("Line Chart", plot_production_line),
        ("Area Chart", plot_production_area),
        ("Accumulative Bar", plot_production_bar),
    ]
    for title, func in chart_types:
        fig = func(df, theme_colors, title, "Production for the Day" if "Accumulative" not in title else "Accumulative Production")
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
                fig.write_image(tmpfile.name)
                pdf.image(tmpfile.name, w=180)
        except Exception as e:
            st.error(f"PDF chart generation failed: {e}")

        pdf.ln(5)

    # Save PDF to temp file and return path
    pdf_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf.output(pdf_file.name)
    return pdf_file.name


# -------------------------------
# UI - Sidebar controls
# -------------------------------
st.sidebar.title("Controls")
mode = st.sidebar.radio("Mode", ["Upload New Data", "View Historical Data", "Manage Data", "Weekly Analysis", "Monthly Analysis"])

st.sidebar.markdown("---")
theme_choice = st.sidebar.selectbox("Chart Theme", list(COLOR_THEMES.keys()), index=0)
theme_colors = COLOR_THEMES[theme_choice]

st.sidebar.markdown("---")
st.sidebar.write("Notes:")
st.sidebar.write("- Upload an Excel (.xlsx) with columns: Plant, Production for the Day, Accumulative Production")
st.sidebar.write("- Select the date for the upload (this tags every row with the chosen date).")
st.sidebar.write("- Fridays are non-production days and will be ignored.")


# -------------------------------
# Main app body
# -------------------------------
st.title("🧱 PRODUCTION DASHBOARD — Web Dashboard")

# Upload Mode
if mode == "Upload New Data":
    st.header("Upload new daily production file")
    st.markdown("Upload an Excel (.xlsx) containing the columns: `Plant`, `Production for the Day`, `Accumulative Production`.")
    uploaded_file = st.file_uploader("Select Excel file to upload", type=["xlsx"])
    selected_date = st.date_input("📅 On which date is this file for?", value=datetime.today())

    if uploaded_file is not None:
        try:
            df_uploaded = read_excel_to_df(uploaded_file)
        except Exception:
            st.stop()

        valid, msg = validate_dataframe(df_uploaded)
        if not valid:
            st.error(msg)
            st.info("Make sure the Excel has exact headers and no merged cells. Example headers: Date, Plant, Production for the Day, Accumulative Production")
        else:
            st.subheader("Preview of uploaded data (first rows)")
            st.dataframe(df_uploaded.head(20))
            confirm = st.checkbox("I confirm this data is correct and ready to upload")
            if confirm:
                if st.button("Upload and Save to History"):
                    df_save = ensure_date_column(df_uploaded, selected_date)
                    weekday_name = pd.to_datetime(df_save["Date"].iloc[0]).day_name()
                    if weekday_name == "Friday":
                        st.error("Selected date is a Friday — Fridays are non-production days and will be ignored.")
                    else:
                        pushed, message = save_csv_and_attempt_push(df_save, selected_date)
                        st.success(f"✅ Saved data to {DATA_DIR}/{selected_date.strftime('%Y-%m-%d')}.csv")
                        if pushed:
                            st.success(f"🚀 {message}")
                        else:
                            st.warning(f"⚠️ Could not push to GitHub automatically. {message}")

                        df_display = df_save.copy()
                        df_display = df_display[~df_display["Plant"].astype(str).str.upper().str.contains("TOTAL")]
                        df_display["Production for the Day"] = pd.to_numeric(df_display["Production for the Day"], errors="coerce").fillna(0.0)
                        df_display["Accumulative Production"] = pd.to_numeric(df_display["Accumulative Production"], errors="coerce").fillna(0.0)

                        st.markdown("---")
                        st.subheader(f"🔹 Totals for {selected_date.strftime('%Y-%m-%d')}")
                        total_daily = df_display["Production for the Day"].sum()
                        total_acc = df_display["Accumulative Production"].sum()
                        st.write(f"**Total Production for the Day:** {total_daily:,.2f} m³")
                        st.write(f"**Total Accumulative Production:** {total_acc:,.2f} m³")

                        st.subheader("📋 Uploaded Production Table")
                        st.dataframe(df_display, use_container_width=True)

                        # Charts
                        st.subheader("🌈 Production Charts (Uploaded)")
                        col1, col2 = st.columns(2)
                        with col1:
                            try:
                                fig_pie = plot_production_pie(df_display, theme_colors, "Plant-wise Production (Pie)", "Production for the Day")
                                st.plotly_chart(fig_pie, use_container_width=True)
                            except Exception as e:
                                st.error(f"Could not create pie chart: {e}")
                        with col2:
                            try:
                                fig_bar = plot_production_bar(df_display, theme_colors, "Production per Plant (Bar)", "Production for the Day")
                                st.plotly_chart(fig_bar, use_container_width=True)
                            except Exception as e:
                                st.error(f"Could not create bar chart: {e}")
                        try:
                            fig_line = plot_production_line(df_display, theme_colors, "Production Trend (Line)", "Production for the Day")
                            st.plotly_chart(fig_line, use_container_width=True)
                        except Exception as e:
                            st.error(f"Could not create line chart: {e}")
                        try:
                            fig_area = plot_production_area(df_display, theme_colors, "Production Flow (Area)", "Production for the Day")
                            st.plotly_chart(fig_area, use_container_width=True)
                        except Exception as e:
                            st.error(f"Could not create area chart: {e}")
                        try:
                            fig_acc = plot_production_bar(df_display, theme_colors, "Accumulative Production per Plant", "Accumulative Production")
                            st.plotly_chart(fig_acc, use_container_width=True)
                        except Exception as e:
                            st.error(f"Could not create accumulative chart: {e}")

                        # Top producer
                        try:
                            top = df_display.loc[df_display["Production for the Day"].astype(float).idxmax()]
                            st.success(f"🏆 Highest Producer: **{top['Plant']}** with {float(top['Production for the Day']):,.2f} m³")
                        except Exception:
                            pass

                        # PDF Export button
                        if st.button("📄 Export Uploaded Data & Charts to PDF"):
                            pdf_file = export_charts_to_pdf(df_display, selected_date.strftime('%Y-%m-%d'), theme_colors)
                            with open(pdf_file, "rb") as f:
                                st.download_button("Download PDF", f, file_name=f"Production_{selected_date.strftime('%Y-%m-%d')}.pdf", mime="application/pdf")
