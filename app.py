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
import plotly.graph_objects as go
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
# PLOT HELPERS — EXACT FLOATS, CLEAN
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
    fig.update_traces(
        texttemplate="%{text:,.1f}",
        textposition="outside",
        textfont=dict(size=16, color="black", family="Arial"),
        cliponaxis=False,
        textangle=0
    )
    fig.update_layout(
        title_font=dict(size=18),
        margin=dict(t=60, b=280, l=60, r=40),
        xaxis_tickangle=0,
        xaxis_gridcolor="#E0E0E0",
        yaxis_gridcolor="#E0E0E0",
        xaxis_tickfont=dict(size=13),
        yaxis_tickfont=dict(size=12)
    )
    return fig

def line_chart(df: pd.DataFrame, value_col: str, colors: list, title: str):
    df[value_col] = df[value_col].astype('float64')
    fig = px.line(df, x="Plant", y=value_col, markers=True, title=title, color_discrete_sequence=colors,
                  text=df[value_col].round(1))
    fig.update_traces(
        marker=dict(size=10, line=dict(width=2, color="DarkSlateGrey")),
        line=dict(width=3),
        textposition="top center",
        texttemplate="%{text:,.1f}",
        textfont=dict(size=10, color="black")
    )
    fig.update_layout(
        title_font=dict(size=18),
        margin=dict(t=60, b=40, l=60, r=40),
        xaxis_gridcolor="#E0E0E0",
        yaxis_gridcolor="#E0E0E0"
    )
    return fig

def area_chart(df: pd.DataFrame, value_col: str, colors: list, title: str):
    df[value_col] = df[value_col].astype('float64')
    fig = px.area(df, x="Plant", y=value_col, color="Plant", color_discrete_sequence=colors, title=title)
    fig.update_traces(line=dict(width=2), opacity=0.8)
    fig.update_layout(
        title_font=dict(size=18),
        margin=dict(t=60, b=40, l=60, r=40),
        xaxis_gridcolor="#E0E0E0",
        yaxis_gridcolor="#E0E0E0"
    )
    return fig

def aggregated_bar_chart(df: pd.DataFrame, value_col: str, group_col: str, colors: list, title: str):
    df[value_col] = df[value_col].astype('float64')
    agg_df = df.groupby([group_col, "Plant"], as_index=False)[value_col].sum()
    agg_df = agg_df.sort_values(value_col, ascending=False)

    fig = px.bar(
        agg_df,
        x="Plant",
        y=value_col,
        color=group_col,
        color_discrete_sequence=colors,
        title=title,
        text=agg_df[value_col].round(1)
    )

    fig.update_traces(
        texttemplate="%{text:,.1f}",
        textposition="outside",
        textfont=dict(size=16, color="black", family="Arial"),
        cliponaxis=False,
        textangle=0
    )

    fig.update_layout(
        title_font=dict(size=18),
        legend_font=dict(size=14),
        margin=dict(t=70, b=280, l=60, r=40),
        xaxis_tickangle=0,
        xaxis_gridcolor="#E0E0E0",
        yaxis_gridcolor="#E0E0E0",
        xaxis_tickfont=dict(size=13),
        yaxis_tickfont=dict(size=12)
    )

    for trace in fig.data:
        if 'KABD' in trace.name:
            trace.marker.color = "#FF4500"
            trace.textfont.color = "#FF4500"
            trace.textfont.size = 16
            trace.textfont.family = "Arial Black"
            break

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
    st.sidebar.caption("If you don't have credentials, please contact the admin.")
    st.stop()

# ========================================
# MAIN UI
# ========================================
st.sidebar.title("Controls")
st.sidebar.write(f"Logged in as: **{st.session_state.get('username', '-')}**")
if st.sidebar.button("Logout"):
    logout()

mode = st.sidebar.radio("Mode", ["Upload New Data", "View Historical Data", "Manage Data", "Analytics"], index=1)
theme_choice = st.sidebar.selectbox("Theme", list(COLOR_THEMES.keys()), index=list(COLOR_THEMES.keys()).index(st.session_state["theme"]))
theme_colors = COLOR_THEMES[theme_choice]
alert_threshold = st.sidebar.number_input("Alert threshold (m³)", min_value=0.0, value=50.0, step=0.5)
st.sidebar.markdown("---")
st.sidebar.caption("Upload Excel with exact columns: Plant, Production for the Day, Accumulative Production.")
st.title("PRODUCTION FOR THE DAY")

# ========================================
# UPLOAD MODE
# ========================================
if mode == "Upload New Data":
    st.header("Upload new daily production file")
    uploaded = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx"])
    selected_date = st.date_input("Which date is this file for?", value=datetime.today())
    if uploaded:
        try:
            df_uploaded = pd.read_excel(uploaded)
            df_uploaded.columns = df_uploaded.columns.str.strip()
        except Exception as e:
            st.error(f"Failed to read: {e}")
            st.stop()
        missing = [c for c in REQUIRED_COLS if c not in df_uploaded.columns]
        if missing:
            st.error(f"Missing columns: {missing}")
        else:
            st.subheader("Preview")
            st.dataframe(df_uploaded.head(20))
            overwrite = st.checkbox("Overwrite existing?", value=False)
            confirm = st.checkbox("Confirm data is correct")
            if confirm and st.button("Upload & Save"):
                df_save = df_uploaded.copy()
                df_save["Date"] = selected_date.strftime("%Y-%m-%d")
                try:
                    saved_path = save_csv(df_save, selected_date, overwrite=overwrite)
                except FileExistsError as e:
                    st.error(str(e))
                    st.stop()
                st.success(f"Saved to {saved_path}")
                pushed, message = attempt_git_push(saved_path, f"Add data for {selected_date}")
                if pushed: st.success(message)
                else: st.warning(message)
                df_display = df_save[~df_save["Plant"].astype(str).str.upper().str.contains("TOTAL")]
                df_display = safe_numeric(df_display)
                st.markdown("### Totals")
                total_daily = df_display["Production for the Day"].sum()
                total_acc = df_display["Accumulative Production"].sum()
                st.write(f"- Daily: **{total_daily:,.1f} m³**")
                st.write(f"- Accumulative: **{total_acc:,.1f} m³**")
                alerts = df_display[df_display["Production for the Day"] < alert_threshold]
                if not alerts.empty:
                    st.warning("Below threshold:")
                    for _, r in alerts.iterrows():
                        st.write(f"- {r['Plant']}: {r['Production for the Day']:.1f} m³")
                st.markdown("### Charts")
                c1, c2 = st.columns(2)
                with c1:
                    st.plotly_chart(pie_chart(df_display, "Production for the Day", theme_colors, "Share"), use_container_width=True)
                with c2:
                    st.plotly_chart(bar_chart(df_display, "Production for the Day", theme_colors, "Per Plant"), use_container_width=True)
                st.plotly_chart(line_chart(df_display, "Production for the Day", theme_colors, "Trend"), use_container_width=True)
                st.plotly_chart(area_chart(df_display, "Production for the Day", theme_colors, "Flow"), use_container_width=True)
                st.plotly_chart(bar_chart(df_display, "Accumulative Production", theme_colors, "Accumulative"), use_container_width=True)
                top = df_display.loc[df_display["Production for the Day"].idxmax()]
                st.success(f"Top: {top['Plant']} — {top['Production for the Day']:.1f} m³")
                excel_file = generate_excel_report(df_display, selected_date.strftime("%Y-%m-%d"))
                st.download_button("Download Excel", excel_file, f"report_{selected_date.strftime('%Y-%m-%d')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ========================================
# VIEW HISTORICAL
# ========================================
elif mode == "View Historical Data":
    st.header("Historical Data Viewer")
    saved_list = list_saved_dates()
    if not saved_list:
        st.info("No data.")
    else:
        default_date = datetime.strptime(saved_list[0], "%Y-%m-%d").date()
        selected_date = st.date_input("Select date", value=default_date)
        selected
