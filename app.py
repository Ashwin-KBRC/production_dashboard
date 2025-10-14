"""
Production Dashboard - Final Full Version (with Secure Login & GitHub API Upload)
- Password-protected login (hashed users or via Streamlit Secrets)
- Upload Excel file, confirm date, and save to data/YYYY-MM-DD.csv
- Automatic upload to GitHub using REST API (works in Streamlit Cloud)
- Historical viewer, rename/delete, analytics, chart themes, and summaries
"""

import os
import hashlib
import base64
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple, List

import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st

# ----------------------------
# Page config
# ----------------------------
st.set_page_config(page_title="Production Dashboard", layout="wide", page_icon="📊")

# ----------------------------
# Ensure data dir
# ----------------------------
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------
# Required columns
# ----------------------------
REQUIRED_COLS = ["Plant", "Production for the Day", "Accumulative Production"]

# ----------------------------
# Load secrets / env
# ----------------------------
SECRETS = {}
try:
    SECRETS = dict(st.secrets)
except Exception:
    try:
        SECRETS = dict(os.environ)
    except Exception:
        SECRETS = {}

GITHUB_TOKEN = SECRETS.get("GITHUB_TOKEN")
GITHUB_REPO = SECRETS.get("GITHUB_REPO")
GITHUB_USER = SECRETS.get("GITHUB_USER", "streamlit-bot")
GITHUB_EMAIL = SECRETS.get("GITHUB_EMAIL", "streamlit@example.com")

# ----------------------------
# Default users (hashed)
# ----------------------------
_default_users = {
    "admin": hashlib.sha256("admin123".encode()).hexdigest()
}
USERS: Dict[str, str] = _default_users.copy()
if "USERS" in SECRETS and isinstance(SECRETS["USERS"], dict):
    for k, v in SECRETS["USERS"].items():
        USERS[k] = v

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
# Authentication helpers
# ----------------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def check_credentials(username: str, password: str) -> bool:
    if not username:
        return False
    user = username.strip()
    return user in USERS and hash_password(password) == USERS[user]

def login_ui():
    st.sidebar.subheader("🔐 Login")
    with st.sidebar.form("login_form"):
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pwd")
        submitted = st.form_submit_button("Sign in")
        if submitted:
            if check_credentials(username, password):
                st.session_state["logged_in"] = True
                st.session_state["username"] = username.strip()
                st.rerun()
            else:
                st.sidebar.error("Invalid username or password")

def logout():
    if "logged_in" in st.session_state:
        del st.session_state["logged_in"]
    if "username" in st.session_state:
        del st.session_state["username"]
    st.rerun()

def logged_in() -> bool:
    return st.session_state.get("logged_in", False)

# ----------------------------
# File helpers
# ----------------------------
def save_csv(df: pd.DataFrame, date_obj: datetime.date, overwrite: bool=False) -> Path:
    fname = f"{date_obj.strftime('%Y-%m-%d')}.csv"
    p = DATA_DIR / fname
    if p.exists() and not overwrite:
        raise FileExistsError(f"{fname} already exists. Set overwrite=True to replace.")
    df.to_csv(p, index=False)
    return p

def list_saved_dates() -> List[str]:
    return sorted([p.name.replace(".csv","") for p in DATA_DIR.glob("*.csv")], reverse=True)

def load_saved(date_str: str) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / f"{date_str}.csv")

def rename_saved(old_date: str, new_date: str) -> bool:
    old = DATA_DIR / f"{old_date}.csv"
    new = DATA_DIR / f"{new_date}.csv"
    if old.exists():
        old.rename(new)
        return True
    return False

def delete_saved(date_str: str) -> bool:
    p = DATA_DIR / f"{date_str}.csv"
    if p.exists():
        p.unlink()
        return True
    return False

# ----------------------------
# GitHub API upload (NEW)
# ----------------------------
def attempt_git_push(file_path: Path, commit_message: str) -> Tuple[bool, str]:
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False, "GitHub credentials not configured."

    try:
        repo = GITHUB_REPO.strip().replace("https://github.com/", "").replace(".git", "")
        api_url = f"https://api.github.com/repos/{repo}/contents/data/{file_path.name}"

        with open(file_path, "rb") as f:
            content_b64 = base64.b64encode(f.read()).decode("utf-8")

        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        resp = requests.get(api_url, headers=headers)
        sha = resp.json().get("sha") if resp.status_code == 200 else None

        payload = {
            "message": commit_message,
            "content": content_b64,
            "branch": "main",
            "committer": {"name": GITHUB_USER, "email": GITHUB_EMAIL}
        }
        if sha:
            payload["sha"] = sha

        r = requests.put(api_url, headers=headers, json=payload)
        if r.status_code in [200, 201]:
            return True, f"✅ Successfully uploaded to GitHub: data/{file_path.name}"
        else:
            err = r.json().get("message", r.text)
            return False, f"❌ GitHub upload failed: {err}"

    except Exception as e:
        return False, f"Exception during GitHub upload: {e}"

# ----------------------------
# Charts
# ----------------------------
def pie_chart(df, col, colors, title):
    fig = px.pie(df, names="Plant", values=col, color_discrete_sequence=colors, title=title)
    fig.update_traces(textinfo="percent+label")
    fig.update_layout(title_x=0.5)
    return fig

def bar_chart(df, col, colors, title):
    fig = px.bar(df, x="Plant", y=col, color="Plant", text=col, color_discrete_sequence=colors, title=title)
    fig.update_traces(texttemplate="%{text:.2s}", textposition="outside")
    fig.update_layout(xaxis_tickangle=-45, title_x=0.5)
    return fig

def line_chart(df, col, colors, title):
    fig = px.line(df, x="Plant", y=col, markers=True, color_discrete_sequence=colors, title=title)
    fig.update_layout(title_x=0.5)
    return fig

def area_chart(df, col, colors, title):
    fig = px.area(df, x="Plant", y=col, color="Plant", color_discrete_sequence=colors, title=title)
    fig.update_layout(title_x=0.5)
    return fig

# ----------------------------
# Safe numeric + summary
# ----------------------------
def safe_numeric(df: pd.DataFrame) -> pd.DataFrame:
    df["Production for the Day"] = pd.to_numeric(df["Production for the Day"], errors="coerce").fillna(0)
    df["Accumulative Production"] = pd.to_numeric(df["Accumulative Production"], errors="coerce").fillna(0)
    return df

def ai_summary(df_display: pd.DataFrame, date_str: str) -> str:
    try:
        total = df_display["Production for the Day"].sum()
        top = df_display.loc[df_display["Production for the Day"].idxmax()]
        low = df_display.loc[df_display["Production for the Day"].idxmin()]
        lines = [
            f"On {date_str}, total production was **{total:,.2f} m³**.",
            f"Top producer: **{top['Plant']}** with **{top['Production for the Day']:,.2f} m³**.",
            f"Lowest producer: **{low['Plant']}** with **{low['Production for the Day']:,.2f} m³**."
        ]
        return "  \n".join(lines)
    except Exception as e:
        return f"Summary unavailable: {e}"

# ----------------------------
# UI: Login
# ----------------------------
if not logged_in():
    st.title("Production Dashboard — Login required")
    login_ui()
    st.sidebar.caption("If you don't have credentials, please contact the admin.")
    st.stop()

# ----------------------------
# Sidebar
# ----------------------------
st.sidebar.title("Controls")
st.sidebar.write(f"Logged in as: **{st.session_state.get('username','-')}**")
if st.sidebar.button("Logout"):
    logout()

mode = st.sidebar.radio("Mode", ["Upload New Data", "View Historical Data", "Manage Data", "Analytics"], index=0)
theme_choice = st.sidebar.selectbox("Theme", list(COLOR_THEMES.keys()), index=list(COLOR_THEMES.keys()).index(st.session_state["theme"]))
st.session_state["theme"] = theme_choice
theme_colors = COLOR_THEMES[theme_choice]
alert_threshold = st.sidebar.number_input("Alert threshold (m³)", min_value=0.0, value=50.0, step=10.0)

st.title("📊 Production Dashboard")

# ----------------------------
# Upload Mode
# ----------------------------
if mode == "Upload New Data":
    st.header("Upload new daily production file")
    uploaded = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx"])
    selected_date = st.date_input("Which date is this file for?", value=datetime.today())

    if uploaded:
        df_uploaded = pd.read_excel(uploaded)
        df_uploaded.columns = df_uploaded.columns.str.strip().str.replace("\n"," ").str.replace("  "," ")
        missing = [c for c in REQUIRED_COLS if c not in df_uploaded.columns]

        if missing:
            st.error(f"Missing columns: {missing}")
        else:
            st.dataframe(df_uploaded.head(20))
            confirm = st.checkbox("I confirm this data is correct and ready to upload")
            if confirm and st.button("Upload & Save to History"):
                df_uploaded["Date"] = selected_date.strftime("%Y-%m-%d")
                saved_path = save_csv(df_uploaded, selected_date, overwrite=True)
                st.success(f"Saved to {saved_path}")

                pushed, message = attempt_git_push(saved_path, f"Add production data for {selected_date.strftime('%Y-%m-%d')}")
                st.info(message)

                df_display = safe_numeric(df_uploaded)
                st.subheader("Summary")
                st.markdown(ai_summary(df_display, selected_date.strftime("%Y-%m-%d")))

                c1, c2 = st.columns(2)
                c1.plotly_chart(pie_chart(df_display, "Production for the Day", theme_colors, "Production Share"), use_container_width=True)
                c2.plotly_chart(bar_chart(df_display, "Production for the Day", theme_colors, "Production per Plant"), use_container_width=True)

# ----------------------------
# Historical
# ----------------------------
elif mode == "View Historical Data":
    st.header("Historical Data Viewer")
    saved = list_saved_dates()
    if not saved:
        st.info("No history found.")
    else:
        chosen = st.selectbox("Select date", saved)
        df = load_saved(chosen)
        df_display = safe_numeric(df)
        st.dataframe(df_display)
        st.plotly_chart(bar_chart(df_display, "Production for the Day", theme_colors, f"{chosen} Production"), use_container_width=True)
        st.markdown(ai_summary(df_display, chosen))

# ----------------------------
# Manage
# ----------------------------
elif mode == "Manage Data":
    st.header("Manage saved data")
    saved = list_saved_dates()
    if not saved:
        st.info("No saved files.")
    else:
        chosen = st.selectbox("Select file", saved)
        act = st.radio("Action", ["Rename", "Delete"])
        if act == "Rename":
            new_date = st.date_input("New date")
            if st.button("Rename"):
                if rename_saved(chosen, new_date.strftime("%Y-%m-%d")):
                    st.success("Renamed successfully.")
        else:
            if st.button("Delete"):
                if delete_saved(chosen):
                    st.success("Deleted successfully.")

# ----------------------------
# Analytics
# ----------------------------
elif mode == "Analytics":
    st.header("Analytics & Trends")
    saved = list_saved_dates()
    if len(saved) < 2:
        st.info("Upload more than one file to view analytics.")
    else:
        frames = [load_saved(d) for d in saved]
        all_df = pd.concat(frames)
        all_df["Date"] = pd.to_datetime(all_df["Date"])
        totals = all_df.groupby("Date")["Production for the Day"].sum().reset_index()
        totals["7d_avg"] = totals["Production for the Day"].rolling(7, min_periods=1).mean()
        st.plotly_chart(px.line(totals, x="Date", y=["Production for the Day", "7d_avg"], title="Production Trend"), use_container_width=True)

# ----------------------------
# Sidebar footer
# ----------------------------
st.sidebar.caption("If GitHub upload fails, check your GITHUB_TOKEN and repo permissions in Streamlit Secrets.")
