import os
import hashlib
import base64
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, List
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st
import io
import xlsxwriter

# ========================================
# PAGE CONFIG & SETUP
# ========================================
st.set_page_config(page_title="Production Dashboard", layout="wide", page_icon="Chart")
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
REQUIRED_COLS = ["Plant", "Production for the Day", "Accumulative Production"]

# ========================================
# SECRETS & AUTH
# ========================================
SECRETS = {}
try:
    SECRETS = dict(st.secrets)
except Exception:
    try:
        SECRETS = dict(os.environ)
    except Exception:
        SECRETS = {}

GITHUB_TOKEN = SECRETS.get("GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
GITHUB_REPO = SECRETS.get("GITHUB_REPO") or os.getenv("GITHUB_REPO")
GITHUB_USER = SECRETS.get("GITHUB_USER") or os.getenv("GITHUB_USER", "streamlit-bot")
GITHUB_EMAIL = SECRETS.get("GITHUB_EMAIL") or os.getenv("GITHUB_EMAIL", "streamlit@example.com")

_default_users = {"admin": hashlib.sha256("kbrc123".encode()).hexdigest()}
USERS: Dict[str, str] = _default_users.copy()
if "USERS" in SECRETS and isinstance(SECRETS["USERS"], dict):
    for k, v in SECRETS["USERS"].items():
        USERS[k] = v

# ========================================
# THEMES
# ========================================
COLOR_THEMES = {
    "Modern Slate": ["#4A6572", "#7D9D9C", "#A4C3B2", "#C9D7D6", "#E5ECE9", "#6B7280", "#9CA3AF", "#D1D5DB", "#E5E7EB", "#F9FAFB"],
    "Sunset Glow": ["#F28C38", "#E96E5D", "#D66BA0", "#A56EC3", "#6B5B95", "#F1A340", "#E76F51", "#D15B8A", "#9F5DBB", "#5F5290"],
    "Ocean Breeze": ["#2E8B8B", "#48A9A6", "#73C2A5", "#9DE0A4", "#C5E8A3", "#3A9D9D", "#54B5B2", "#7FCEB1", "#A9EBAF", "#D1F4B7"],
    "Corporate": ["#FF4040", "#4040FF", "#40FF40", "#FF8000", "#FFFF40", "#CC0000", "#0000CC", "#00CC00", "#CC6600", "#CCCC00"],
    "Midnight Sky": ["#283593", "#3F51B5", "#673AB7", "#9C27B0", "#BA68C8", "#1A237E", "#303F9F", "#512DA8", "#8E24AA", "#AB47BC"],
    "Spring Bloom": ["#D4A59A", "#C2D4B7", "#A9C5A7", "#8DB596", "#71A684", "#D8A08D", "#B6C8A9", "#9DB99A", "#82A98B", "#669A7A"],
    "Executive Suite": ["#4A4A4A", "#1E3A8A", "#D4A017", "#8A8A8A", "#A3BFFA", "#333333", "#172F6E", "#B38600", "#6E6E6E", "#8CAFE6"],
    "Boardroom Blue": ["#2A4066", "#4682B4", "#B0C4DE", "#C0C0C0", "#87CEEB", "#1F2F4B", "#357ABD", "#9BAEBF", "#A6A6A6", "#6BAED6"],
    "Corporate Ivory": ["#F5F5F5", "#008080", "#800000", "#D3D3D3", "#CD853F", "#ECECEC", "#006666", "#660000", "#B0B0B0", "#B27A3D"],
}
if "theme" not in st.session_state:
    st.session_state["theme"] = "Modern Slate"
elif st.session_state["theme"] not in COLOR_THEMES:
    st.session_state["theme"] = "Modern Slate"

# ========================================
# AUTH FUNCTIONS
# ========================================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def check_credentials(username: str, password: str) -> bool:
    if not username:
        return False
    user = username.strip()
    if user in USERS:
        return hash_password(password) == USERS[user]
    return False

def login_ui():
    st.sidebar.subheader("Login")
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

# ========================================
# FILE I/O & GIT HELPERS
# ========================================
def save_csv(df: pd.DataFrame, date_obj: datetime.date, overwrite: bool = False) -> Path:
    fname = f"{date_obj.strftime('%Y-%m-%d')}.csv"
    p = DATA_DIR / fname
    if p.exists() and not overwrite:
        raise FileExistsError(f"{fname} already exists.")
    df.to_csv(p, index=False, float_format="%.3f")
    return p

def list_saved_dates() -> List[str]:
    return sorted([p.name.replace(".csv", "") for p in DATA_DIR.glob("*.csv")], reverse=True)

def load_saved(date_str: str) -> pd.DataFrame:
    p = DATA_DIR / f"{date_str}.csv"
    if not p.exists():
        raise FileNotFoundError(f"File not found: {date_str}")
    return pd.read_csv(p)

def delete_saved(date_str: str) -> bool:
    p = DATA_DIR / f"{date_str}.csv"
    if p.exists():
        p.unlink()
        return True
    return False

def attempt_git_push(file_path: Path, msg: str) -> Tuple[bool, str]:
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False, "GitHub not configured."
    try:
        repo = GITHUB_REPO.strip().replace("https://github.com/", "").replace(".git", "")
        url = f"https://api.github.com/repos/{repo}/contents/data/{file_path.name}"
        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        resp = requests.get(url, headers=headers)
        sha = resp.json().get("sha") if resp.status_code == 200 else None
        payload = {"message": msg, "content": b64, "branch": "main", "committer": {"name": GITHUB_USER, "email": GITHUB_EMAIL}}
        if sha: payload["sha"] = sha
        r = requests.put(url, headers=headers, json=payload)
        return r.status_code in [200, 201], ("Success" if r.ok else r.json().get("message", "Failed"))
    except Exception as e:
        return False, str(e)

# ========================================
# PLOT HELPERS
# ========================================
def pie_chart(df: pd.DataFrame, value_col: str, colors: list, title: str):
    df[value_col] = df[value_col].astype('float64')
    fig = px.pie(df, names="Plant", values=value_col, color_discrete_sequence=colors, title=title)
    fig.update_traces(textinfo="percent+label", textfont=dict(size=14, color="black"))
    fig.update_layout(title_font=dict(family="Arial", size=18), legend_font=dict(size=16), margin=dict(t=60, b=40, l=40, r=40))
    return fig

def bar_chart(df: pd.DataFrame, value_col: str, colors: list, title: str):
    df[value_col] = df[value_col].astype('float64')
    fig = px.bar(df, x="Plant", y=value_col, color="Plant", color_discrete_sequence=colors, title=title,
                 text=df[value_col].round(1))
    fig.update_traces(texttemplate="%{text:,.1f}", textposition="outside", textfont=dict(size=16, color="black", family="Arial"))
    fig.update_layout(title_font=dict(size=18), margin=dict(t=60, b=280, l=60, r=40), xaxis_tickangle=0)
    return fig

def aggregated_bar_chart(df: pd.DataFrame, value_col: str, group_col: str, colors: list, title: str):
    df[value_col] = df[value_col].astype('float64')
    agg_df = df.groupby([group_col, "Plant"], as_index=False)[value_col].sum()
    agg_df = agg_df.sort_values(value_col, ascending=False)
    fig = px.bar(agg_df, x="Plant", y=value_col, color=group_col, color_discrete_sequence=colors, title=title, text=agg_df[value_col].round(1))
    fig.update_traces(texttemplate="%{text:,.1f}", textposition="outside", textfont=dict(size=16, color="black", family="Arial"))
    fig.update_layout(title_font=dict(size=18), legend_font=dict(size=14), margin=dict(t=70, b=280, l=60, r=40), xaxis_tickangle=0)
    for trace in fig.data:
        if 'KABD' in trace.name:
            trace.marker.color = "#FF4500"
            trace.textfont.color = "#FF4500"
            trace.textfont.size = 16
            trace.textfont.family = "Arial Black"
    return fig

# ========================================
# DATA HELPERS
# ========================================
def safe_numeric(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()
    df2["Production for the Day"] = pd.to_numeric(df2["Production for the Day"], errors="coerce").fillna(0.0)
    df2["Accumulative Production"] = pd.to_numeric(df2["Accumulative Production"], errors="coerce").fillna(0.0)
    return df2

def generate_excel_report(df: pd.DataFrame, date_str: str):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Production Data', index=False, float_format="%.3f")
    output.seek(0)
    return output

# ========================================
# LOGIN CHECK
# ========================================
if not logged_in():
    st.title("Production Dashboard — Login required")
    login_ui()
    st.sidebar.write("---")
    st.sidebar.caption("Contact admin for credentials.")
    st.stop()

# ========================================
# MAIN UI
# ========================================
st.sidebar.title("Controls")
st.sidebar.write(f"Logged in as: **{st.session_state.get('username', '-')}**")
if st.sidebar.button("Logout"):
    logout()

mode = st.sidebar.radio("Mode", ["Upload New Data", "View Historical Data", "Manage Data", "Analytics"], index=3)
theme_choice = st.sidebar.selectbox("Theme", list(COLOR_THEMES.keys()), index=list(COLOR_THEMES.keys()).index(st.session_state["theme"]))
theme_colors = COLOR_THEMES[theme_choice]
alert_threshold = st.sidebar.number_input("Alert threshold (m³)", min_value=0.0, value=50.0, step=0.5)
st.sidebar.markdown("---")
st.sidebar.caption("Upload Excel: Plant | Production for the Day | Accumulative Production")
st.title("PRODUCTION DASHBOARD")

# ========================================
# UPLOAD, VIEW, MANAGE (unchanged)
# ... [same as your original] ...

# ========================================
# ANALYTICS — FINAL & CORRECT
# ========================================
elif mode == "Analytics":
    st.header("Analytics & Trends")
    saved = list_saved_dates()
    if len(saved) < 2:
        st.info("Need 2+ days of data.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", value=datetime.today() - timedelta(days=30))
        with col2:
            end_date = st.date_input("End Date", value=datetime.today())

        frames = [load_saved(d) for d in saved]
        all_df = pd.concat(frames, ignore_index=True)
        all_df['Date'] = pd.to_datetime(all_df['Date'])

        filtered_df = all_df[
            (all_df['Date'] >= pd.to_datetime(start_date)) &
            (all_df['Date'] <= pd.to_datetime(end_date))
        ].copy()

        if filtered_df.empty:
            st.warning("No data in selected range.")
            st.stop()

        filtered_df = safe_numeric(filtered_df)
        filtered_df = filtered_df.sort_values(['Plant', 'Date'])

        filtered_df['Month'] = filtered_df['Date'].dt.to_period('M').astype(str)
        filtered_df['Custom_Week'] = ((filtered_df['Date'] - pd.to_datetime(start_date)).dt.days // 7) + 1

        weekly_daily = filtered_df.groupby(['Custom_Week', 'Plant'], as_index=False)['Production for the Day'].sum()
        monthly_daily = filtered_df.groupby(['Month', 'Plant'], as_index=False)['Production for the Day'].sum()

        monthly_max_dates = filtered_df.groupby(['Month', 'Plant'])['Date'].max().reset_index()
        monthly_acc = pd.merge(
            filtered_df[['Date', 'Month', 'Plant', 'Accumulative Production']],
            monthly_max_dates,
            on=['Month', 'Plant', 'Date'],
            how='inner'
        )[['Month', 'Plant', 'Accumulative Production']]

        weekly_max_dates = filtered_df.groupby(['Custom_Week', 'Plant'])['Date'].max().reset_index()
        weekly_acc = pd.merge(
            filtered_df[['Date', 'Custom_Week', 'Plant', 'Accumulative Production']],
            weekly_max_dates,
            on=['Custom_Week', 'Plant', 'Date'],
            how='inner'
        )[['Custom_Week', 'Plant', 'Accumulative Production']]

        summary = pd.DataFrame({"Plant": filtered_df['Plant'].unique()})
        summary = summary.merge(weekly_daily.groupby('Plant')['Production for the Day'].sum().reset_index(), on='Plant', how='left').fillna(0)
        summary = summary.merge(weekly_acc.groupby('Plant')['Accumulative Production'].last().reset_index(), on='Plant', how='left').fillna(0)
        summary = summary.merge(monthly_daily.groupby('Plant')['Production for the Day'].sum().reset_index(), on='Plant', how='left').fillna(0)
        summary = summary.merge(monthly_acc.groupby('Plant')['Accumulative Production'].last().reset_index(), on='Plant', how='left').fillna(0)
        summary.rename(columns={
            'Production for the Day_x': 'Weekly Daily Total',
            'Accumulative Production_x': 'Weekly Accumulative',
            'Production for the Day_y': 'Monthly Daily Total',
            'Accumulative Production_y': 'Monthly Accumulative'
        }, inplace=True)
        summary = summary.sort_values("Monthly Daily Total", ascending=False)

        st.subheader("Weekly Production (Daily)")
        st.plotly_chart(aggregated_bar_chart(weekly_daily, "Production for the Day", "Custom_Week", theme_colors, "Weekly Daily"), use_container_width=True)
        st.subheader("Monthly Production (Daily)")
        st.plotly_chart(aggregated_bar_chart(monthly_daily, "Production for the Day", "Month", theme_colors, "Monthly Daily"), use_container_width=True)
        st.subheader("Weekly Accumulative (Final Day)")
        st.plotly_chart(aggregated_bar_chart(weekly_acc, "Accumulative Production", "Custom_Week", theme_colors, "Weekly Accumulative"), use_container_width=True)
        st.subheader("Monthly Accumulative (Final Day)")
        st.plotly_chart(aggregated_bar_chart(monthly_acc, "Accumulative Production", "Month", theme_colors, "Monthly Accumulative"), use_container_width=True)

        st.markdown("### DOWNLOAD FULL REPORT")
        excel = generate_excel_report(summary, f"{start_date}_to_{end_date}")
        st.download_button("DOWNLOAD EXCEL", excel, f"report_{start_date}_to_{end_date}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ========================================
# FOOTER
# ========================================
st.sidebar.markdown("---")
st.sidebar.write("GitHub auto-sync enabled")
st.sidebar.caption(f"Kuwait Time: {datetime.now().strftime('%I:%M %p')} | LIVE")
