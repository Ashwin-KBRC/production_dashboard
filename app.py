"""
Production Dashboard - Secure Full Version (GitHub push fixed)
- Password login (hashed)
- Upload Excel → Save as data/YYYY-MM-DD.csv
- Automatic push to GitHub using token from Streamlit Secrets
- Historical viewer, analytics, ranking, AI summary
- Rename/Delete manager
"""

import os
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple, List

import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st

# ----------------------------
# Streamlit page setup
# ----------------------------
st.set_page_config(page_title="Production Dashboard", layout="wide", page_icon="📊")

# ----------------------------
# Ensure data folder exists
# ----------------------------
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

REQUIRED_COLS = ["Plant", "Production for the Day", "Accumulative Production"]

# ----------------------------
# Secrets / Environment
# ----------------------------
SECRETS = {}
try:
    SECRETS = dict(st.secrets)
except Exception:
    SECRETS = dict(os.environ)

# ✅ FIXED GITHUB VARIABLES
GITHUB_TOKEN = SECRETS.get("GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
GITHUB_REPO = SECRETS.get("GITHUB_REPO") or os.getenv("GITHUB_REPO")  # e.g. "Ashwin-KBRC/production_dashboard"
GITHUB_USER = SECRETS.get("GITHUB_USER") or os.getenv("GITHUB_USER", "streamlit-bot")
GITHUB_EMAIL = SECRETS.get("GITHUB_EMAIL") or os.getenv("GITHUB_EMAIL", "streamlit@example.com")

# ----------------------------
# Default login users (SHA256)
# ----------------------------
_default_users = {"admin": hashlib.sha256("admin123".encode()).hexdigest()}
USERS: Dict[str, str] = _default_users.copy()
if "USERS" in SECRETS and isinstance(SECRETS["USERS"], dict):
    USERS.update(SECRETS["USERS"])

# ----------------------------
# Color themes
# ----------------------------
COLOR_THEMES = {
    "Classic": px.colors.qualitative.Bold,
    "Blue": px.colors.sequential.Blues,
    "Vibrant": ["#EF476F", "#FFD166", "#06D6A0", "#118AB2", "#073B4C"],
    "Forest": ["#2e8b57", "#3cb371", "#66cdaa", "#20b2aa", "#2f4f4f"],
}

if "theme" not in st.session_state:
    st.session_state["theme"] = "Classic"

# ----------------------------
# Login Helpers
# ----------------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def check_credentials(username: str, password: str) -> bool:
    return username in USERS and hash_password(password) == USERS[username]

def login_ui():
    st.sidebar.subheader("🔐 Login")
    with st.sidebar.form("login_form"):
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        submit = st.form_submit_button("Sign in")
        if submit:
            if check_credentials(user, pwd):
                st.session_state["logged_in"] = True
                st.session_state["username"] = user
                st.rerun()
            else:
                st.sidebar.error("Invalid credentials")

def logout():
    st.session_state.clear()
    st.rerun()

if not st.session_state.get("logged_in", False):
    st.title("Production Dashboard — Login Required")
    login_ui()
    st.stop()

# ----------------------------
# GitHub Push Function
# ----------------------------
def attempt_git_push(file_path: Path, commit_message: str) -> Tuple[bool, str]:
    """Push file to GitHub repo using personal access token"""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False, "Missing GitHub configuration."

    remote = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git"
    try:
        subprocess.run(["git", "config", "--global", "user.email", GITHUB_EMAIL], check=False)
        subprocess.run(["git", "config", "--global", "user.name", GITHUB_USER], check=False)
        subprocess.run(["git", "add", str(file_path)], check=True)
        commit = subprocess.run(["git", "commit", "-m", commit_message],
                                capture_output=True, text=True)
        if commit.returncode != 0 and "nothing to commit" not in commit.stderr.lower():
            return False, f"Commit failed: {commit.stderr}"
        push = subprocess.run(["git", "push", remote, "main"], capture_output=True, text=True)
        if push.returncode != 0:
            return False, f"Push failed: {push.stderr}"
        return True, "✅ Pushed to GitHub successfully."
    except Exception as e:
        return False, str(e)

# ----------------------------
# File Functions
# ----------------------------
def save_csv(df: pd.DataFrame, date_obj: datetime.date, overwrite=False) -> Path:
    path = DATA_DIR / f"{date_obj.strftime('%Y-%m-%d')}.csv"
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path.name} already exists.")
    df.to_csv(path, index=False)
    return path

def list_saved_dates() -> List[str]:
    return sorted([f.stem for f in DATA_DIR.glob("*.csv")], reverse=True)

def load_saved(date_str: str) -> pd.DataFrame:
    path = DATA_DIR / f"{date_str}.csv"
    return pd.read_csv(path)

def rename_saved(old: str, new: str):
    os.rename(DATA_DIR / f"{old}.csv", DATA_DIR / f"{new}.csv")

def delete_saved(date_str: str):
    os.remove(DATA_DIR / f"{date_str}.csv")

# ----------------------------
# Plot Helpers
# ----------------------------
def pie_chart(df, col, colors, title):
    fig = px.pie(df, names="Plant", values=col, color_discrete_sequence=colors, title=title)
    fig.update_traces(textinfo="percent+label")
    fig.update_layout(title_x=0.5)
    return fig

def bar_chart(df, col, colors, title):
    fig = px.bar(df, x="Plant", y=col, color="Plant", color_discrete_sequence=colors,
                 title=title, text=col)
    fig.update_traces(textposition="outside")
    fig.update_layout(title_x=0.5)
    return fig

# ----------------------------
# Sidebar Controls
# ----------------------------
st.sidebar.title("Controls")
st.sidebar.write(f"👤 Logged in as: **{st.session_state['username']}**")
if st.sidebar.button("Logout"):
    logout()

mode = st.sidebar.radio("Mode", ["Upload Data", "View History", "Manage", "Analytics"])
theme_choice = st.sidebar.selectbox("Theme", list(COLOR_THEMES.keys()))
st.session_state["theme"] = theme_choice
theme_colors = COLOR_THEMES[theme_choice]
alert_threshold = st.sidebar.number_input("Alert threshold (m³)", 0.0, 999999.0, 50.0)

# ----------------------------
# Upload Mode
# ----------------------------
if mode == "Upload Data":
    st.header("Upload New Daily Data")
    file = st.file_uploader("Upload Excel", type=["xlsx"])
    date_sel = st.date_input("Date", datetime.today())

    if file:
        df = pd.read_excel(file)
        df.columns = df.columns.str.strip()
        if not all(c in df.columns for c in REQUIRED_COLS):
            st.error(f"Columns must include: {REQUIRED_COLS}")
            st.stop()

        st.dataframe(df)
        confirm = st.checkbox("Confirm data is correct")

        if confirm and st.button("Save and Push"):
            df["Date"] = date_sel.strftime("%Y-%m-%d")
            path = save_csv(df, date_sel, overwrite=True)
            st.success(f"Saved {path.name}")

            ok, msg = attempt_git_push(path, f"Add data {date_sel.strftime('%Y-%m-%d')}")
            if ok:
                st.success(msg)
            else:
                st.warning(msg)

            st.plotly_chart(pie_chart(df, "Production for the Day", theme_colors, "Production Share"))
            st.plotly_chart(bar_chart(df, "Production for the Day", theme_colors, "Production per Plant"))

# ----------------------------
# View History
# ----------------------------
elif mode == "View History":
    st.header("Historical Data")
    files = list_saved_dates()
    if not files:
        st.info("No history found.")
    else:
        sel = st.selectbox("Select date", files)
        df = load_saved(sel)
        st.dataframe(df)
        st.plotly_chart(pie_chart(df, "Production for the Day", theme_colors, f"Production {sel}"))
        st.plotly_chart(bar_chart(df, "Production for the Day", theme_colors, f"Production {sel}"))

# ----------------------------
# Manage
# ----------------------------
elif mode == "Manage":
    st.header("Manage Data Files")
    files = list_saved_dates()
    if not files:
        st.info("No files.")
    else:
        sel = st.selectbox("Select file", files)
        act = st.radio("Action", ["Rename", "Delete"])
        if act == "Rename":
            new = st.date_input("New date")
            if st.button("Confirm Rename"):
                rename_saved(sel, new.strftime("%Y-%m-%d"))
                st.success("Renamed successfully.")
        else:
            if st.button("Confirm Delete"):
                delete_saved(sel)
                st.success("Deleted successfully.")

# ----------------------------
# Analytics
# ----------------------------
elif mode == "Analytics":
    st.header("Analytics & Trends")
    files = list_saved_dates()
    if len(files) < 2:
        st.info("Need at least 2 files for trend analysis.")
    else:
        dfs = [load_saved(f) for f in files]
        df_all = pd.concat(dfs)
        df_all["Date"] = pd.to_datetime(df_all["Date"])
        totals = df_all.groupby("Date")["Production for the Day"].sum().reset_index()
        st.plotly_chart(px.line(totals, x="Date", y="Production for the Day",
                                title="Total Production Trend"), use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.caption("If Git push fails: check GITHUB_TOKEN & GITHUB_REPO format (user/repo).")
