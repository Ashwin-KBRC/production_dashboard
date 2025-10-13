# app.py
"""
Full Production Dashboard - Long version
Features:
- Secure login (session-based) with hashed passwords (can be set via Streamlit Secrets)
- Upload daily Excel file (choose date) and confirm before saving
- Save to data/YYYY-MM-DD.csv; attempt to push automatically to GitHub using token from secrets
- Historical view (select any saved date)
- Rename/Delete saved date with confirmations
- 4 color themes; charts: pie, bar, line, area with numeric labels
- Totals, top producer, alerts, 7/30 day trends, simple AI-style textual summary
- Robust error handling and friendly messages if push fails (manual instructions)
"""

import os
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Tuple, Dict, Any

import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="Production Dashboard (Secure)", layout="wide")

# -------------------------
# Constants & data dir
# -------------------------
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

REQUIRED_COLS = ["Plant", "Production for the Day", "Accumulative Production"]

# -------------------------
# GitHub integration (from env or Streamlit secrets)
# -------------------------
# The app expects Streamlit Secrets in TOML form:
# GITHUB_TOKEN = "ghp_xxx..."
# GITHUB_REPO = "username/repo_name"
# Optionally:
# USERS = {"admin":"<sha256hash>", "boss":"<sha256hash>"}
SECRETS = {}
try:
    SECRETS = dict(st.secrets)
except Exception:
    SECRETS = dict(os.environ)  # fallback to environment, if any

GITHUB_TOKEN = SECRETS.get("GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
GITHUB_REPO = SECRETS.get("GITHUB_REPO") or os.getenv("GITHUB_REPO")
GITHUB_USER = SECRETS.get("GITHUB_USER") or os.getenv("GITHUB_USER", "streamlit-bot")
GITHUB_EMAIL = SECRETS.get("GITHUB_EMAIL") or os.getenv("GITHUB_EMAIL", "streamlit@example.com")

# -------------------------
# Default users (hashed) - change ASAP or use Streamlit Secrets "USERS"
# -------------------------
# Default credentials (for initial testing ONLY)
# username: admin, password: admin123  (change immediately)
_default_users = {
    "admin": hashlib.sha256("admin123".encode()).hexdigest()
}

# if user provided USERS in secrets (as a mapping), use that
USERS = {}
if "USERS" in SECRETS and isinstance(SECRETS["USERS"], dict):
    USERS = SECRETS["USERS"]
else:
    USERS = _default_users

# -------------------------
# Color themes
# -------------------------
COLOR_THEMES = {
    "Classic": px.colors.qualitative.Bold,
    "Blue": px.colors.sequential.Blues,
    "Vibrant": ["#EF476F", "#FFD166", "#06D6A0", "#118AB2", "#073B4C"],
    "Forest": ["#2e8b57", "#3cb371", "#66cdaa", "#20b2aa", "#2f4f4f"],
}

# -------------------------
# Utility functions
# -------------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def check_credentials(username: str, password: str) -> bool:
    """Check plaintext password against stored hash in USERS dict."""
    if username in USERS:
        return hash_password(password) == USERS[username]
    return False

def logged_in() -> bool:
    return st.session_state.get("logged_in", False)

def login_ui():
    st.sidebar.subheader("🔐 Login")
    with st.sidebar.form("login_form", clear_on_submit=False):
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            if check_credentials(user.strip(), pwd):
                st.session_state["logged_in"] = True
                st.session_state["username"] = user.strip()
                st.experimental_rerun()
            else:
                st.sidebar.error("Invalid username or password.")

def logout():
    if "logged_in" in st.session_state:
        del st.session_state["logged_in"]
    if "username" in st.session_state:
        del st.session_state["username"]
    st.experimental_rerun()

# -------------------------
# File / Git functions
# -------------------------
def save_csv(df: pd.DataFrame, date_obj: datetime.date, overwrite: bool=False) -> Path:
    """Save dataframe to data/YYYY-MM-DD.csv. Returns Path."""
    fname = f"{date_obj.strftime('%Y-%m-%d')}.csv"
    path = DATA_DIR / fname
    if path.exists() and not overwrite:
        raise FileExistsError(f"File {fname} already exists. Use overwrite=True to replace.")
    df.to_csv(path, index=False)
    return path

def attempt_git_push(file_path: Path, commit_message: str) -> Tuple[bool, str]:
    """
    Attempt to add/commit/push to GitHub using GITHUB_TOKEN and GITHUB_REPO.
    Returns (success, message). Gracefully handles common failures.
    """
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False, "GITHUB_TOKEN or GITHUB_REPO not configured in Streamlit Secrets."

    remote_url = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git"
    try:
        # Configure git user locally
        subprocess.run(["git", "config", "--global", "user.email", GITHUB_EMAIL], check=False)
        subprocess.run(["git", "config", "--global", "user.name", GITHUB_USER], check=False)

        # Add file
        subprocess.run(["git", "add", str(file_path)], check=True)

        # Commit (may return non-zero if nothing to commit)
        commit = subprocess.run(["git", "commit", "-m", commit_message], capture_output=True, text=True)
        if commit.returncode != 0:
            out = (commit.stdout or "") + (commit.stderr or "")
            if "nothing to commit" in out.lower() or "no changes added to commit" in out.lower():
                # nothing new (not an error)
                return True, "No changes to commit (file already present)."
            else:
                return False, f"Git commit failed: {out.strip()}"
        # Push
        push = subprocess.run(["git", "push", remote_url, "main"], capture_output=True, text=True)
        if push.returncode != 0:
            return False, f"Git push failed: {push.stderr.strip() or push.stdout.strip()}"
        return True, "File pushed to GitHub successfully."
    except Exception as e:
        return False, f"Exception during git push: {e}"

# -------------------------
# Chart helper functions (plotly)
# -------------------------
def pie_chart(df: pd.DataFrame, value_col: str, colors: list, title: str):
    fig = px.pie(df, names="Plant", values=value_col, title=title, color_discrete_sequence=colors)
    fig.update_traces(textinfo="percent+label", textfont_size=12)
    fig.update_layout(title_x=0.5)
    return fig

def bar_chart(df: pd.DataFrame, value_col: str, colors: list, title: str):
    fig = px.bar(df, x="Plant", y=value_col, color="Plant", title=title, color_discrete_sequence=colors, text=value_col)
    fig.update_traces(texttemplate="%{text:.2s}", textposition="outside")
    fig.update_layout(title_x=0.5, xaxis_tickangle=-45)
    return fig

def line_chart(df: pd.DataFrame, value_col: str, colors: list, title: str):
    fig = px.line(df, x="Plant", y=value_col, markers=True, title=title, color_discrete_sequence=colors)
    fig.update_layout(title_x=0.5)
    return fig

def area_chart(df: pd.DataFrame, value_col: str, colors: list, title: str):
    fig = px.area(df, x="Plant", y=value_col, color="Plant", title=title, color_discrete_sequence=colors)
    fig.update_layout(title_x=0.5)
    return fig

# -------------------------
# Data helpers
# -------------------------
def list_saved_dates() -> list:
    files = sorted([p.name.replace(".csv","") for p in DATA_DIR.glob("*.csv")], reverse=True)
    return files

def load_saved_date(date_str: str) -> pd.DataFrame:
    p = DATA_DIR / f"{date_str}.csv"
    if not p.exists():
        raise FileNotFoundError(f"No file for {date_str}")
    return pd.read_csv(p)

def safe_to_numeric_cols(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()
    df2["Production for the Day"] = pd.to_numeric(df2["Production for the Day"], errors="coerce").fillna(0.0)
    df2["Accumulative Production"] = pd.to_numeric(df2["Accumulative Production"], errors="coerce").fillna(0.0)
    return df2

# -------------------------
# Analytics helpers
# -------------------------
def compute_rankings(all_df: pd.DataFrame, as_of_date: str) -> Dict[str, Any]:
    all_df['Date'] = pd.to_datetime(all_df['Date'])
    as_of = pd.to_datetime(as_of_date)
    # Daily
    daily = all_df[all_df['Date'].dt.strftime('%Y-%m-%d') == as_of_date].groupby('Plant')['Production for the Day'].sum().sort_values(ascending=False)
    # Weekly (last 7 days)
    start7 = as_of - pd.Timedelta(days=6)
    weekly = all_df[(all_df['Date']>=start7) & (all_df['Date']<=as_of)].groupby('Plant')['Production for the Day'].sum().sort_values(ascending=False)
    # Monthly (30 days)
    start30 = as_of - pd.Timedelta(days=29)
    monthly = all_df[(all_df['Date']>=start30) & (all_df['Date']<=as_of)].groupby('Plant')['Production for the Day'].sum().sort_values(ascending=False)
    return {"daily": daily, "weekly": weekly, "monthly": monthly}

def ai_summary(df_display: pd.DataFrame, historical_df: pd.DataFrame, as_of_date: str) -> str:
    try:
        total_daily = df_display["Production for the Day"].sum()
        top = df_display.loc[df_display["Production for the Day"].idxmax()]
        bottom = df_display.loc[df_display["Production for the Day"].idxmin()]
        lines = []
        lines.append(f"On {as_of_date}, total production was **{total_daily:,.2f} m³**.")
        lines.append(f"Top producer: **{top['Plant']}** with **{float(top['Production for the Day']):,.2f} m³**.")
        lines.append(f"Lowest producer: **{bottom['Plant']}** with **{float(bottom['Production for the Day']):,.2f} m³**.")
        # compare vs 7-day average if data exists
        if historical_df is not None and not historical_df.empty:
            hist = historical_df.copy()
            hist['Date'] = pd.to_datetime(hist['Date'])
            as_dt = pd.to_datetime(as_of_date)
            start7 = as_dt - pd.Timedelta(days=7)
            prev7 = hist[(hist['Date'] >= start7) & (hist['Date'] < as_dt)]
            if not prev7.empty:
                avg7 = prev7.groupby('Plant')['Production for the Day'].mean()
                diffs = []
                for _, row in df_display.iterrows():
                    plant = row['Plant']
                    today = row['Production for the Day']
                    if plant in avg7.index:
                        avg = avg7.loc[plant]
                        pct = (today - avg)/avg*100 if avg != 0 else 0
                        if abs(pct) >= 10:
                            diffs.append((plant, pct))
                for plant, pct in diffs:
                    if pct > 0:
                        lines.append(f"{plant} is up {pct:.1f}% vs its 7-day average.")
                    else:
                        lines.append(f"{plant} is down {abs(pct):.1f}% vs its 7-day average.")
        return "  \n".join(lines)
    except Exception as e:
        return f"Summary unavailable: {e}"

# -------------------------
# UI - Login
# -------------------------
if not logged_in():
    st.sidebar.title("Sign in")
    login_ui()
    st.sidebar.write("---")
    st.sidebar.caption("Enter username & password to access the dashboard.")
    st.title("Please login to access the Production Dashboard")
    st.stop()

# -------------------------
# UI - Main App
# -------------------------
st.sidebar.title("Controls")
st.sidebar.write(f"Signed in as: **{st.session_state.get('username','-')}**")
if st.sidebar.button("Logout"):
    logout()

mode = st.sidebar.radio("Mode", ["Upload New Data", "View Historical Data", "Manage Data", "Analytics"], index=1)
theme_choice = st.sidebar.selectbox("Chart Theme", list(COLOR_THEMES.keys()), index=0)
theme_colors = COLOR_THEMES[theme_choice]

alert_threshold = st.sidebar.number_input("Alert threshold (m³)", min_value=0.0, value=50.0, step=10.0)
st.sidebar.write("---")
st.sidebar.write("Tips: Excel must have columns: Plant, Production for the Day, Accumulative Production")

st.title("PRODUCTION FOR THE DAY")
st.write("Upload your Excel, choose date, and save. View history or run analytics from the sidebar.")

# -------------------------
# Upload New Data mode
# -------------------------
if mode == "Upload New Data":
    st.header("Upload new daily production file")
    uploaded = st.file_uploader("Upload Excel (.xlsx) with columns: Plant, Production for the Day, Accumulative Production", type=["xlsx"])
    selected_date = st.date_input("On which date is this file for?", value=datetime.today())

    if uploaded is not None:
        try:
            df_uploaded = pd.read_excel(uploaded)
            df_uploaded.columns = df_uploaded.columns.str.strip().str.replace("\n"," ").str.replace("  "," ")
        except Exception as e:
            st.error(f"Failed to read Excel: {e}")
            st.stop()

        # Validate headers
        missing = [c for c in REQUIRED_COLS if c not in df_uploaded.columns]
        if missing:
            st.error(f"Your file is missing columns: {missing}. Expected: {REQUIRED_COLS}")
        else:
            st.subheader("Preview")
            st.dataframe(df_uploaded.head(20))
            overwrite = False
            save_path = DATA_DIR / f"{selected_date.strftime('%Y-%m-%d')}.csv"
            if save_path.exists():
                overwrite = st.checkbox("A file for this date already exists — check to overwrite", value=False)
            confirm = st.checkbox("I confirm this data is correct and ready to upload")
            if confirm and st.button("Save to history"):
                # prepare df
                df_save = df_uploaded.copy()
                df_save["Date"] = selected_date.strftime("%Y-%m-%d")
                # skip Friday
                if pd.to_datetime(df_save["Date"].iloc[0]).day_name() == "Friday":
                    st.warning("Selected date is Friday — non-production day. Upload cancelled.")
                else:
                    try:
                        saved_path = save_csv(df_save, selected_date, overwrite=overwrite)
                    except FileExistsError as fe:
                        st.error(str(fe))
                        st.stop()
                    st.success(f"Saved to {saved_path}")

                    # attempt to push to GitHub
                    pushed, msg = attempt_git_push(saved_path, f"Add production data for {selected_date.strftime('%Y-%m-%d')}")
                    if pushed:
                        st.success(msg)
                    else:
                        st.warning(msg)
                        st.info("If push failed, you can manually upload the CSV to your repo's data/ folder on GitHub.")

                    # Show results & charts
                    df_display = df_save.copy()
                    df_display = df_display[~df_display["Plant"].astype(str).str.upper().str.contains("TOTAL")]
                    df_display = safe_to_numeric_cols(df_display)

                    st.markdown("### Totals")
                    total_daily = df_display["Production for the Day"].sum()
                    total_acc = df_display["Accumulative Production"].sum()
                    st.write(f"- Total Production for the Day: **{total_daily:,.2f} m³**")
                    st.write(f"- Total Accumulative Production: **{total_acc:,.2f} m³**")

                    # Alerts
                    alerts = df_display[df_display["Production for the Day"] < alert_threshold]
                    if not alerts.empty:
                        st.warning("⚠️ Plants below threshold:")
                        for _, r in alerts.iterrows():
                            st.write(f"- {r['Plant']}: {r['Production for the Day']} m³")

                    # Charts
                    st.markdown("### Production Charts")
                    c1, c2 = st.columns(2)
                    with c1:
                        try:
                            st.plotly_chart(pie_chart(df_display, "Production for the Day", theme_colors, "Plant-wise Production (Pie)"), use_container_width=True)
                        except Exception as e:
                            st.error(f"Pie chart error: {e}")
                    with c2:
                        try:
                            st.plotly_chart(bar_chart(df_display, "Production for the Day", theme_colors, "Production per Plant (Bar)"), use_container_width=True)
                        except Exception as e:
                            st.error(f"Bar chart error: {e}")

                    # Additional charts
                    try:
                        st.plotly_chart(line_chart(df_display, "Production for the Day", theme_colors, "Production Trend (Line)"), use_container_width=True)
                        st.plotly_chart(area_chart(df_display, "Production for the Day", theme_colors, "Production Flow (Area)"), use_container_width=True)
                    except Exception as e:
                        st.warning(f"Additional chart error: {e}")

                    # Accumulative
                    try:
                        st.plotly_chart(bar_chart(df_display, "Accumulative Production", theme_colors, "Accumulative Production"), use_container_width=True)
                    except Exception:
                        st.info("No accumulative chart available.")

                    # Highest Producer
                    try:
                        top = df_display.loc[df_display["Production for the Day"].idxmax()]
                        st.success(f"🏆 Highest Producer: {top['Plant']} — {float(top['Production for the Day']):,.2f} m³")
                    except Exception:
                        pass

# -------------------------
# View Historical Data
# -------------------------
elif mode == "View Historical Data":
    st.header("View Historical Data")
    saved = list_saved_dates()
    if not saved:
        st.info("No historical data saved yet. Upload a file first.")
    else:
        chosen = st.selectbox("Select date to view", saved, index=0)
        try:
            df_hist = load_saved_date(chosen)
        except Exception as e:
            st.error(f"Unable to load saved file: {e}")
            st.stop()

        df_hist = df_hist.copy()
        if "Date" in df_hist.columns:
            try:
                df_hist["Date"] = pd.to_datetime(df_hist["Date"]).dt.strftime("%Y-%m-%d")
            except Exception:
                pass

        df_hist_display = df_hist[~df_hist["Plant"].astype(str).str.upper().str.contains("TOTAL")]
        df_hist_display = safe_to_numeric_cols(df_hist_display)

        st.subheader(f"Data for {chosen}")
        st.dataframe(df_hist_display, use_container_width=True)

        # Totals
        total_daily = df_hist_display["Production for the Day"].sum()
        total_acc = df_hist_display["Accumulative Production"].sum()
        st.markdown("### Totals")
        st.write(f"- Daily: **{total_daily:,.2f} m³** — Accumulative: **{total_acc:,.2f} m³**")

        # Charts section with try/except to avoid full crash
        st.markdown("### Charts")
        try:
            st.plotly_chart(pie_chart(df_hist_display, "Production for the Day", theme_colors, f"Production Share — {chosen}"), use_container_width=True)
            st.plotly_chart(bar_chart(df_hist_display, "Production for the Day", theme_colors, f"Production per Plant — {chosen}"), use_container_width=True)
            st.plotly_chart(line_chart(df_hist_display, "Production for the Day", theme_colors, f"Production Trend — {chosen}"), use_container_width=True)
            st.plotly_chart(area_chart(df_hist_display, "Production for the Day", theme_colors, f"Production Flow — {chosen}"), use_container_width=True)
        except Exception as e:
            st.warning(f"Chart generation problem: {e}")

        # Accumulative chart if present
        if "Accumulative Production" in df_hist_display.columns:
            try:
                st.plotly_chart(bar_chart(df_hist_display, "Accumulative Production", theme_colors, f"Accumulative Production — {chosen}"), use_container_width=True)
            except Exception as e:
                st.warning(f"Accumulative chart issue: {e}")

        # Rankings using all historical data
        try:
            frames = [load_saved_date(d) for d in list_saved_dates()]
            all_df = pd.concat(frames, ignore_index=True)
            ranks = compute_rankings(all_df, chosen)
            st.markdown("### Rankings")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.write("Daily")
                st.dataframe(ranks['daily'].reset_index().rename(columns={'index':'Plant','Production for the Day':'Total'}))
            with c2:
                st.write("Weekly")
                st.dataframe(ranks['weekly'].reset_index().rename(columns={'index':'Plant','Production for the Day':'Total'}))
            with c3:
                st.write("Monthly")
                st.dataframe(ranks['monthly'].reset_index().rename(columns={'index':'Plant','Production for the Day':'Total'}))
        except Exception:
            st.info("Not enough historical data for rankings.")

        # AI-style summary
        try:
            # combine historical frames
            frames = [load_saved_date(d) for d in list_saved_dates()]
            all_hist = pd.concat(frames, ignore_index=True)
            summary = ai_summary(df_hist_display, all_hist, chosen)
            st.markdown("### Quick Summary")
            st.markdown(summary)
        except Exception:
            pass

# -------------------------
# Manage Data mode (rename / delete)
# -------------------------
elif mode == "Manage Data":
    st.header("Manage saved data (rename / delete)")
    saved = list_saved_dates()
    if not saved:
        st.info("No saved files found.")
    else:
        chosen = st.selectbox("Select saved date to manage", saved)
        action = st.radio("Action", ["Rename", "Delete"])
        if action == "Rename":
            new_dt = st.date_input("Choose new date", value=datetime.today())
            if st.button("Confirm rename"):
                ok = rename_saved_csv = None
                try:
                    old_path = DATA_DIR / f"{chosen}.csv"
                    new_path = DATA_DIR / f"{new_dt.strftime('%Y-%m-%d')}.csv"
                    if old_path.exists():
                        old_path.rename(new_path)
                        st.success(f"Renamed {chosen} → {new_dt.strftime('%Y-%m-%d')}")
                    else:
                        st.error("Original file not found.")
                except Exception as e:
                    st.error(f"Rename failed: {e}")
        else:
            st.warning("You are about to permanently delete the selected file.")
            if st.button("Confirm Delete"):
                try:
                    p = DATA_DIR / f"{chosen}.csv"
                    if p.exists():
                        p.unlink()
                        st.success("File deleted.")
                    else:
                        st.error("File not found.")
                except Exception as e:
                    st.error(f"Delete failed: {e}")

# -------------------------
# Analytics mode
# -------------------------
elif mode == "Analytics":
    st.header("Analytics & Trends")
    saved = list_saved_dates()
    if len(saved) < 2:
        st.info("Upload at least two dates to see trends.")
    else:
        frames = [load_saved_date(d) for d in saved]
        all_df = pd.concat(frames, ignore_index=True)
        all_df['Date'] = pd.to_datetime(all_df['Date'])
        totals = all_df.groupby('Date')['Production for the Day'].sum().reset_index().sort_values('Date')
        totals['7d_ma'] = totals['Production for the Day'].rolling(7, min_periods=1).mean()
        st.subheader("Total production trend")
        st.plotly_chart(px.line(totals, x='Date', y=['Production for the Day','7d_ma'], labels={'value':'m³','variable':'Metric'}), use_container_width=True)

# -------------------------
# Footer / help
# -------------------------
st.sidebar.markdown("---")
st.sidebar.write("If automatic Git push fails, either:")
st.sidebar.write("1) Ensure GITHUB_TOKEN & GITHUB_REPO are set in Streamlit Secrets (TOML).")
st.sidebar.write("2) Manually upload the CSV from this app's data/ folder to your repo's data/ folder via GitHub UI.")
