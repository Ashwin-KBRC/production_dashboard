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
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet
import psutil

# === Page Config ===
st.set_page_config(page_title="Production Dashboard", layout="wide", page_icon="Chart")

# === CSS for Dark Mode & Polish ===
def apply_theme():
    if st.session_state.get("dark_mode", False):
        st.markdown("""
        <style>
            .block-container { padding-top: 2rem; }
            .stApp { background-color: #0e1117; color: #fafafa; }
            .css-1d391kg { background-color: #262730; }
            .stSelectbox > div > div { background-color: #262730; color: #fafafa; border: 1px solid #444; }
            .stButton > button { background-color: #1f77b4; color: white; border-radius: 8px; font-weight: bold; }
            .stButton > button:hover { background-color: #155a87; }
            .stTextInput > div > div > input { background-color: #262730; color: #fafafa; border: 1px solid #444; }
            .stDataFrame { border: 1px solid #444; }
            h1, h2, h3, h4 { color: #ffffff !important; }
            .css-1y0t9x4 { color: #fafafa; }
        </style>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <style>
            .block-container { padding-top: 2rem; }
            .stButton > button { background-color: #4A6572; color: white; border-radius: 8px; font-weight: bold; }
            .stButton > button:hover { background-color: #7D9D9C; }
            .stSelectbox > div > div { background-color: #f0f2f6; border-radius: 8px; }
        </style>
        """, unsafe_allow_html=True)

apply_theme()

# === Data Directory ===
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# === Required Columns ===
REQUIRED_COLS = ["Plant", "Production for the Day", "Accumulative Production"]

# === Secrets & GitHub ===
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

# === Users (hashed) ===
_default_users = {"admin": hashlib.sha256("kbrc123".encode()).hexdigest()}
USERS: Dict[str, str] = _default_users.copy()
if "USERS" in SECRETS and isinstance(SECRETS["USERS"], dict):
    for k, v in SECRETS["USERS"].items():
        USERS[k] = v

# === Color Themes (Extended) ===
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

# === Session State Init ===
if "theme" not in st.session_state:
    st.session_state["theme"] = "Modern Slate"
if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = False

# === Auth Helpers ===
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def check_credentials(username: str, password: str) -> bool:
    user = username.strip()
    return user in USERS and hash_password(password) == USERS[user]

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
                st.sidebar.error("Invalid credentials")

def logout():
    for key in ["logged_in", "username"]:
        st.session_state.pop(key, None)
    st.rerun()

def logged_in() -> bool:
    return st.session_state.get("logged_in", False)

# === File I/O ===
def save_csv(df: pd.DataFrame, date_obj: datetime.date, overwrite: bool = False) -> Path:
    fname = f"{date_obj.strftime('%Y-%m-%d')}.csv"
    p = DATA_DIR / fname
    if p.exists() and not overwrite:
        raise FileExistsError(f"{fname} already exists.")
    df.to_csv(p, index=False)
    return p

def list_saved_dates() -> List[str]:
    return sorted([p.name.replace(".csv", "") for p in DATA_DIR.glob("*.csv")], reverse=True)

def load_saved(date_str: str) -> pd.DataFrame:
    p = DATA_DIR / f"{date_str}.csv"
    if not p.exists():
        raise FileNotFoundError(f"File for {date_str} not found.")
    return pd.read_csv(p)

def rename_saved(old: str, new: str) -> bool:
    old_p = DATA_DIR / f"{old}.csv"
    new_p = DATA_DIR / f"{new}.csv"
    if old_p.exists():
        old_p.rename(new_p)
        return True
    return False

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
        api_url = f"https://api.github.com/repos/{repo}/contents/data/{file_path.name}"
        with open(file_path, "rb") as f:
            content = base64.b64encode(f.read()).decode()
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        resp = requests.get(api_url, headers=headers)
        sha = resp.json().get("sha") if resp.status_code == 200 else None
        payload = {"message": msg, "content": content, "branch": "main", "committer": {"name": GITHUB_USER, "email": GITHUB_EMAIL}}
        if sha:
            payload["sha"] = sha
        r = requests.put(api_url, headers=headers, json=payload)
        return r.status_code in [200, 201], "Success" if r.ok else r.json().get("message", "Failed")
    except Exception as e:
        return False, str(e)

# === Plot Helpers ===
def safe_numeric(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Production for the Day"] = pd.to_numeric(df["Production for the Day"], errors="coerce").fillna(0)
    df["Accumulative Production"] = pd.to_numeric(df["Accumulative Production"], errors="coerce").fillna(0)
    return df

def pie_chart(df, col, colors, title):
    fig = px.pie(df, names="Plant", values=col, color_discrete_sequence=colors, title=title)
    fig.update_traces(textinfo="percent+label", textfont_size=14)
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), margin=dict(t=60, b=40))
    return fig

def bar_chart(df, col, colors, title):
    fig = px.bar(df, x="Plant", y=col, color="Plant", color_discrete_sequence=colors, title=title, text=col)
    fig.update_traces(texttemplate="%{text:.2s}", textposition="outside")
    fig.update_layout(margin=dict(t=60, b=80), xaxis_title="Plant", yaxis_title=col)
    return fig

def line_chart(df, col, colors, title):
    fig = px.line(df, x="Plant", y=col, markers=True, color_discrete_sequence=colors, title=title, text=col)
    fig.update_traces(textposition="top center", texttemplate="%{text:.1f}")
    return fig

def area_chart(df, col, colors, title):
    fig = px.area(df, x="Plant", y=col, color="Plant", color_discrete_sequence=colors, title=title)
    fig.update_traces(line_width=2, opacity=0.8)
    return fig

def aggregated_bar_chart(df, val_col, group_col, colors, title):
    agg = df.groupby([group_col, "Plant"])[val_col].sum().reset_index()
    unique = agg[group_col].unique()
    color_map = {g: colors[i % len(colors)] for i, g in enumerate(unique)}
    fig = px.bar(agg, x="Plant", y=val_col, color=group_col, color_discrete_map=color_map, title=title, text=val_col)
    fig.update_traces(texttemplate="%{text:.2s}", textposition="outside")
    return fig

def plant_trend_chart(all_df: pd.DataFrame, theme_colors):
    df = all_df.copy()
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date')
    fig = px.line(df, x='Date', y='Production for the Day', color='Plant',
                  color_discrete_sequence=theme_colors, title="Plant Production Trend Over Time",
                  markers=True)
    fig.update_layout(xaxis_title="Date", yaxis_title="Production (m³)", hovermode="x unified")
    fig.update_traces(line=dict(width=2), marker=dict(size=6))
    return fig

# === Excel Export ===
def generate_excel_report(df: pd.DataFrame, name: str):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Data', index=False)
    output.seek(0)
    return output

# === Login Check ===
if not logged_in():
    st.title("Production Dashboard — Login Required")
    login_ui()
    st.stop()

# === Sidebar ===
st.sidebar.title("Controls")
st.sidebar.write(f"**{st.session_state['username']}**")

if st.sidebar.button("Logout"):
    logout()

# Dark Mode Toggle
if st.sidebar.checkbox("Dark Mode", value=st.session_state["dark_mode"]):
    st.session_state["dark_mode"] = True
else:
    st.session_state["dark_mode"] = False
apply_theme()  # Re-apply after toggle

mode = st.sidebar.radio("Mode", ["Upload New Data", "View Historical Data", "Manage Data", "Analytics"], index=1)
theme_choice = st.sidebar.selectbox("Theme", list(COLOR_THEMES.keys()), index=list(COLOR_THEMES.keys()).index(st.session_state["theme"]))
st.session_state["theme"] = theme_choice
theme_colors = COLOR_THEMES[theme_choice]
alert_threshold = st.sidebar.number_input("Alert Threshold (m³)", min_value=0.0, value=50.0, step=10.0)

st.sidebar.markdown("---")
st.sidebar.caption("Upload Excel: **Plant**, **Production for the Day**, **Accumulative Production**")

st.title("PRODUCTION DASHBOARD")

# === UPLOAD MODE ===
if mode == "Upload New Data":
    st.header("Upload Daily Production")
    uploaded = st.file_uploader("Choose .xlsx file", type=["xlsx"])
    selected_date = st.date_input("Date for this data", value=datetime.today())

    if uploaded:
        try:
            df = pd.read_excel(uploaded)
            df.columns = df.columns.str.strip()
        except Exception as e:
            st.error(f"Read error: {e}")
            st.stop()

        missing = [c for c in REQUIRED_COLS if c not in df.columns]
        if missing:
            st.error(f"Missing: {missing}")
        else:
            st.subheader("Preview")
            st.dataframe(df.head(20))

            overwrite = st.checkbox("Overwrite existing?", value=False) if (DATA_DIR / f"{selected_date:%Y-%m-%d}.csv").exists() else False
            confirm = st.checkbox("Confirm data is correct")

            if confirm and st.button("Upload & Save"):
                df_save = df.copy()
                df_save["Date"] = selected_date.strftime("%Y-%m-%d")
                try:
                    path = save_csv(df_save, selected_date, overwrite)
                    st.success(f"Saved: {path.name}")
                    pushed, msg = attempt_git_push(path, f"Add {selected_date:%Y-%m-%d}")
                    st.write("Success" if pushed else "Warning", msg)
                except Exception as e:
                    st.error(e)
                    st.stop()

                df_disp = safe_numeric(df_save[~df_save["Plant"].str.upper().str.contains("TOTAL")])
                total = df_disp["Production for the Day"].sum()
                acc = df_disp["Accumulative Production"].sum()
                st.write(f"**Total:** {total:,.2f} m³ | **Accumulative:** {acc:,.2f} m³")

                if (df_disp["Production for the Day"] < alert_threshold).any():
                    st.warning("Low production alerts:")
                    for _, r in df_disp[df_disp["Production for the Day"] < alert_threshold].iterrows():
                        st.write(f"- {r['Plant']}: {r['Production for the Day']:.1f} m³")

                col1, col2 = st.columns(2)
                with col1: st.plotly_chart(pie_chart(df_disp, "Production for the Day", theme_colors, "Share"), use_container_width=True)
                with col2: st.plotly_chart(bar_chart(df_disp, "Production for the Day", theme_colors, "Per Plant"), use_container_width=True)
                st.plotly_chart(area_chart(df_disp, "Production for the Day", theme_colors, "Production Flow"), use_container_width=True)
                st.plotly_chart(bar_chart(df_disp, "Accumulative Production", theme_colors, "Accumulative"), use_container_width=True)

                top = df_disp.loc[df_disp["Production for the Day"].idxmax()]
                st.success(f"Top: **{top['Plant']}** — {top['Production for the Day']:,.1f} m³")

                excel = generate_excel_report(df_disp, selected_date.strftime("%Y-%m-%d"))
                st.download_button("Download Excel", excel, f"report_{selected_date:%Y-%m-%d}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# === VIEW HISTORICAL ===
elif mode == "View Historical Data":
    st.header("Historical Data")
    dates = list_saved_dates()
    if not dates:
        st.info("No data yet.")
    else:
        with st.container():
            st.markdown("### Select Date")
            col1, col2 = st.columns([3, 1])
            with col1:
                selected = st.selectbox(
                    "View production data for",
                    dates,
                    format_func=lambda x: datetime.strptime(x, "%Y-%m-%d").strftime("%A, %B %d, %Y")
                )
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                st.button("Refresh", on_click=st.rerun)

        df = load_saved(selected)
        df_disp = safe_numeric(df[~df["Plant"].str.upper().str.contains("TOTAL")])
        display_date = datetime.strptime(selected, "%Y-%m-%d").strftime("%A, %B %d, %Y")
        st.markdown(f"### Data for **{display_date}**")
        st.dataframe(df_disp, use_container_width=True)

        total = df_disp["Production for the Day"].sum()
        acc = df_disp["Accumulative Production"].sum()
        st.write(f"**Total:** {total:,.2f} m³ | **Accumulative:** {acc:,.2f} m³")

        col1, col2 = st.columns(2)
        with col1: st.plotly_chart(pie_chart(df_disp, "Production for the Day", theme_colors, "Share"), use_container_width=True)
        with col2: st.plotly_chart(bar_chart(df_disp, "Production for the Day", theme_colors, "Per Plant"), use_container_width=True)
        st.plotly_chart(area_chart(df_disp, "Production for the Day", theme_colors, "Flow"), use_container_width=True)

        excel = generate_excel_report(df_disp, selected)
        st.download_button("Download Excel", excel, f"report_{selected}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# === MANAGE DATA ===
elif mode == "Manage Data":
    st.header("Manage Files")
    dates = list_saved_dates()
    if not dates:
        st.info("No files.")
    else:
        chosen = st.selectbox("Select file", dates)
        action = st.radio("Action", ["Rename", "Delete"])
        if action == "Rename":
            new_date = st.date_input("New date", value=datetime.today())
            if st.button("Rename"):
                if rename_saved(chosen, new_date.strftime("%Y-%m-%d")):
                    st.success("Renamed!")
                    st.rerun()
                else:
                    st.error("Failed.")
        else:
            if st.button("Delete Permanently"):
                if delete_saved(chosen):
                    st.success("Deleted.")
                    st.rerun()
                else:
                    st.error("Failed.")

# === ANALYTICS ===
elif mode == "Analytics":
    st.header("Multi-Day Analytics")
    dates = list_saved_dates()
    if len(dates) < 2:
        st.info("Need 2+ days.")
    else:
        with st.expander("Date Range", expanded=True):
            c1, c2, c3 = st.columns([3, 3, 1])
            with c1:
                start = st.date_input("Start", value=datetime.today() - timedelta(days=30))
            with c2:
                end = st.date_input("End", value=datetime.today())
            with c3:
                st.markdown("<br>", unsafe_allow_html=True)
                apply = st.button("Apply")

        if start > end:
            st.error("Start > End")
            st.stop()

        frames = [load_saved(d) for d in dates if start <= datetime.strptime(d, "%Y-%m-%d").date() <= end]
        if not frames:
            st.warning("No data in range.")
        else:
            df = pd.concat(frames, ignore_index=True)
            df['Date'] = pd.to_datetime(df['Date'])
            df = safe_numeric(df)
            df['Week'] = df['Date'].dt.isocalendar().week
            df['Month'] = df['Date'].dt.month

            # Weekly & Monthly Aggregates
            st.plotly_chart(aggregated_bar_chart(df.groupby(['Week', 'Plant'])['Production for the Day'].sum().reset_index(), "Production for the Day", "Week", theme_colors, "Weekly Total"), use_container_width=True)
            st.plotly_chart(aggregated_bar_chart(df.groupby(['Month', 'Plant'])['Production for the Day'].sum().reset_index(), "Production for the Day", "Month", theme_colors, "Monthly Total"), use_container_width=True)

            # Plant Trend Lines
            st.markdown("### Plant Production Trend")
            st.plotly_chart(plant_trend_chart(df, theme_colors), use_container_width=True)

            excel = generate_excel_report(df, f"{start}_to_{end}")
            st.download_button("Download Report", excel, f"analytics_{start}_to_{end}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
