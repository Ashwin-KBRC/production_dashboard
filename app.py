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
# PAGE CONFIG & HIDE STREAMLIT BRANDING
# ========================================
st.set_page_config(page_title="Production Dashboard", layout="wide", page_icon="Trophy")
st.markdown("""
<style>
    footer {visibility: hidden !important;}
    #MainMenu {visibility: hidden;}
    header {visibility: hidden !important;}
    .stAppDeployButton {display: none !important;}
</style>
""", unsafe_allow_html=True)

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
    "Lava Flow": ["#FF4500", "#FF6B35", "#FF8E53", "#FFB347", "#FFD700"],
    "Modern Slate": ["#4A6572", "#7D9D9C", "#A4C3B2", "#C9D7D6", "#E5ECE9"],
    "Sunset Glow": ["#F28C38", "#E96E5D", "#D66BA0", "#A56EC3", "#6B5B95"],
    "Ocean Breeze": ["#2E8B8B", "#48A9A6", "#73C2A5", "#9DE0A4", "#C5E8A3"],
    "Corporate": ["#FF4040", "#4040FF", "#40FF40", "#FF8000", "#FFFF40"],
}
if "theme" not in st.session_state:
    st.session_state["theme"] = "Lava Flow"

# ========================================
# AUTH
# ========================================
def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def check_credentials(u: str, p: str) -> bool:
    u = u.strip()
    return u in USERS and hash_password(p) == USERS[u]

def login_ui():
    st.sidebar.subheader("Login")
    with st.sidebar.form("login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Sign in"):
            if check_credentials(u, p):
                st.session_state["logged_in"] = True
                st.session_state["username"] = u
                st.rerun()
            else:
                st.sidebar.error("Wrong credentials")

def logout():
    for k in ["logged_in", "username"]:
        st.session_state.pop(k, None)
    st.rerun()

def logged_in() -> bool:
    return st.session_state.get("logged_in", False)

# ========================================
# FILE HELPERS
# ========================================
def save_csv(df: pd.DataFrame, date_obj: datetime.date, overwrite=False) -> Path:
    f = DATA_DIR / f"{date_obj:%Y-%m-%d}.csv"
    if f.exists() and not overwrite:
        raise FileExistsError(f"{f.name} already exists")
    df.to_csv(f, index=False, float_format="%.3f")
    return f

def list_saved_dates() -> List[str]:
    return sorted([p.stem for p in DATA_DIR.glob("*.csv")], reverse=True)

def load_saved(date_str: str) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / f"{date_str}.csv")

def delete_saved(date_str: str) -> bool:
    p = DATA_DIR / f"{date_str}.csv"
    if p.exists():
        p.unlink()
        return True
    return False

# ========================================
# MUTLA MERGE
# ========================================
def merge_mutla_plants(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Plant"] = df["Plant"].astype(str).str.strip()
    mask = df["Plant"].str.contains("mutla", case=False, na=False)
    if mask.sum() > 1:
        mutla = df[mask]
        others = df[~mask]
        combined = pd.DataFrame([{
            "Plant": "Mutla",
            "Production for the Day": mutla["Production for the Day"].sum(),
            "Accumulative Production": mutla["Accumulative Production"].sum(),
            "Date": mutla["Date"].iloc[0] if "Date" in mutla.columns else None
        }])
        df = pd.concat([others, combined], ignore_index=True)
    return df

# ========================================
# DATA HELPERS
# ========================================
def safe_numeric(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["Production for the Day"] = pd.to_numeric(d["Production for the Day"], errors="coerce").fillna(0.0)
    d["Accumulative Production"] = pd.to_numeric(d["Accumulative Production"], errors="coerce")
    d["Accumulative Production"] = d["Accumulative Production"].fillna(method='ffill').fillna(0)
    return d

def generate_excel_report(df: pd.DataFrame, date_str: str):
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Production Data', index=False, float_format="%.3f")
    out.seek(0)
    return out

# ========================================
# PLOT HELPERS (unchanged – you already love them)
# ========================================
def pie_chart(df, col, colors, title):
    fig = px.pie(df, names="Plant", values=col, color_discrete_sequence=colors, title=title)
    fig.update_traces(textinfo="percent+label")
    return fig

def bar_chart(df, col, colors, title):
    df = df.sort_values(col, ascending=False)
    fig = px.bar(df, x="Plant", y=col, color="Plant", color_discrete_sequence=colors,
                 text=df[col].round(1), title=title)
    fig.update_traces(texttemplate="%{text:,.1f}", textposition="outside")
    return fig

def line_chart(df, col, colors, title):
    fig = px.line(df, x="Plant", y=col, markers=True, color_discrete_sequence=colors,
                  text=df[col].round(1), title=title)
    fig.update_traces(textposition="top center", texttemplate="%{text:,.1f}")
    return fig

def area_chart(df, col, colors, title):
    fig = px.area(df, x="Plant", y=col, color="Plant", color_discrete_sequence=colors, title=title)
    return fig

def aggregated_bar_chart(df, val_col, group_col, colors, title):
    # (your original beautiful function – unchanged)
    # ... [paste your full aggregated_bar_chart function here exactly as before]
    # For brevity I kept it out, but just copy-paste your original one
    pass  # ← replace with your full function

# ========================================
# LOGIN CHECK
# ========================================
if not logged_in():
    st.title("Production Dashboard – Login required")
    login_ui()
    st.stop()

st.sidebar.title("Controls")
st.sidebar.write(f"**{st.session_state['username']}**")
if st.sidebar.button("Logout"): logout()

mode = st.sidebar.radio("Mode", ["Upload New Data", "View Historical Data", "Manage Data", "Analytics"], index=1)
theme_choice = st.sidebar.selectbox("Theme", list(COLOR_THEMES.keys()),
                                   index=list(COLOR_THEMES.keys()).index(st.session_state["theme"]))
if theme_choice != st.session_state["theme"]:
    st.session_state["theme"] = theme_choice
    st.rerun()
theme_colors = COLOR_THEMES[theme_choice]
alert_threshold = st.sidebar.number_input("Alert threshold (m³)", 0.0, value=50.0, step=0.5)

st.title("PRODUCTION FOR THE DAY")

# ========================================
# UPLOAD NEW DATA
# ========================================
if mode == "Upload New Data":
    st.header("Upload new daily production file")
    uploaded = st.file_uploader("Excel file", type=["xlsx"])
    selected_date = st.date_input("Date for this file", datetime.today())

    if uploaded:
        df_up = pd.read_excel(uploaded)
        df_up.columns = df_up.columns.str.strip()

        missing = [c for c in REQUIRED_COLS if c not in df_up.columns]
        if missing:
            st.error(f"Missing columns: {missing}")
            st.stop()

        st.subheader("Preview")
        st.dataframe(df_up)

        if st.checkbox("Confirm data is correct") and st.button("Save"):
            df_up["Date"] = selected_date.strftime("%Y-%m-%d")
            save_csv(df_up, selected_date, overwrite=st.checkbox("Overwrite if exists"))

            df_disp = df_up[~df_up["Plant"].astype(str).str.upper().str.contains("TOTAL")]
            df_disp = safe_numeric(df_disp)
            df_disp = merge_mutla_plants(df_disp)

            total_daily = df_disp["Production for the Day"].sum()

            st.markdown(f"""
            <div style="background: linear-gradient(135deg,#7c3aed,#a78bfa);color:white;padding:70px;border-radius:40px;text-align:center;margin:40px 0;box-shadow:0 25px 60px rgba(0,0,0,0.4);font-family:'Arial Black'">
                <h1 style="margin:0;font-size:85px;letter-spacing:4px">TOTAL PRODUCTION</h1>
                <h2 style="margin:35px 0;font-size:100px">{total_daily:,.1f} m³</h2>
                <p style="margin:0;font-size:32px">{selected_date:%A, %B %d, %Y}</p>
            </div>
            """, unsafe_allow_html=True)

            # charts, alerts, download button etc. (same as before)
            # ... [rest of your upload section]

# ========================================
# VIEW HISTORICAL DATA
# ========================================
elif mode == "View Historical Data":
    dates = list_saved_dates()
    if not dates:
        st.info("No data yet")
    else:
        sel_date = st.date_input("Select date", datetime.strptime(dates[0], "%Y-%m-%d"))
        sel_str = sel_date.strftime("%Y-%m-%d")
        if sel_str not in dates:
            st.warning("No data")
            st.stop()

        df = load_saved(sel_str)
        df = df[~df["Plant"].astype(str).str.upper().str.contains("TOTAL")]
        df = safe_numeric(df)
        df = merge_mutla_plants(df)

        total = df["Production for the Day"].sum()

        st.markdown(f"""
        <div style="background: linear-gradient(135deg,#7c3aed,#a78bfa);color:white;padding:70px;border-radius:40px;text-align:center;margin:40px 0;box-shadow:0 25px 60px rgba(0,0,0,0.4);font-family:'Arial Black'">
            <h1 style="margin:0;font-size:85px;letter-spacing:4px">TOTAL PRODUCTION</h1>
            <h2 style="margin:35px 0;font-size:100px">{total:,.1f} m³</h2>
            <p style="margin:0;font-size:32px">{sel_date:%A, %B %d, %Y}</p>
        </div>
        """, unsafe_allow_html=True)

        st.dataframe(df, use_container_width=True)
        # charts etc. same as before

# ========================================
# ANALYTICS – FIXED LINE
# ========================================
elif mode == "Analytics":
    st.header("Analytics & Trends")
    dates = list_saved_dates()
    if len(dates) < 2:
        st.info("Need at least 2 days")
    else:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start", datetime.today() - timedelta(days=30))
        with col2:
            end_date = st.date_input("End", datetime.today())

        dfs = [load_saved(d) for d in dates]
        all_df = pd.concat(dfs, ignore_index=True)
        all_df["Date"] = pd.to_datetime(all_df["Date"])

        # FIXED LINE
        filtered_df = all_df[(all_df["Date"] >= pd.to_datetime(start_date)) &
                            (all_df["Date"] <= pd.to_datetime(end_date))]

        if filtered_df.empty:
            st.warning("No data in range")
        else:
            filtered_df = safe_numeric(filtered_df)
            filtered_df = merge_mutla_plants(filtered_df)

            total = filtered_df["Production for the Day"].sum()

            st.markdown(f"""
            <div style="background: linear-gradient(135deg,#1e40af,#3b82f6);color:white;padding:70px;border-radius:40px;text-align:center;margin:40px 0;box-shadow:0 25px 60px rgba(0,0,0,0.45);font-family:'Arial Black'">
                <h1 style="margin:0;font-size:85px;letter-spacing:4px">TOTAL PRODUCTION</h1>
                <h2 style="margin:35px 0;font-size:100px">{total:,.1f} m³</h2>
                <p style="margin:0;font-size:32px">
                    {start_date:%b %d} → {end_date:%b %d, %Y}
                </p>
            </div>
            """, unsafe_allow_html=True)

            # Top 3 with decimals
            avg_daily = filtered_df.groupby('Plant')['Production for the Day'].mean().round(1)
            top_avg = avg_daily.sort_values(ascending=False).head(3)
            latest_acc = filtered_df.groupby('Plant')['Accumulative Production'].last()
            top_acc = latest_acc.sort_values(ascending=False).head(3)

            st.markdown("## TOP 3 LEADERS")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("### Avg Daily")
                for i, (plant, val) in enumerate(top_avg.items()):
                    rank = ["1st", "2nd", "3rd"][i]
                    colr = ["#FFD700", "#C0C0C0", "#CD7F32"][i]
                    st.markdown(f"""
                    <div style="background:white;padding:30px;border-radius:20px;margin:15px 0;border-left:12px solid {colr};box-shadow:0 10px 25px rgba(0,0,0,0.15)">
                        <h3 style="margin:0;color:{colr}">{rank} • {plant}</h3>
                        <h2 style="margin:10px 0 0">{val:,.1f} m³/day</h2>
                    </div>
                    """, unsafe_allow_html=True)
            with c2:
                st.markdown("### Latest Accumulative")
                for i, (plant, val) in enumerate(top_acc.items()):
                    rank = ["1st", "2nd", "3rd"][i]
                    colr = ["#1E90FF", "#4682B4", "#5F9EA0"][i]
                    st.markdown(f"""
                    <div style="background:white;padding:30px;border-radius:20px;margin:15px 0;border-left:12px solid {colr};box-shadow:0 10px 25px rgba(0,0,0,0.15)">
                        <h3 style="margin:0;color:{colr}">{rank} • {plant}</h3>
                        <h2 style="margin:10px 0 0">{val:,.1f} m³</h2>
                    </div>
                    """, unsafe_allow_html=True)

            # weekly / monthly charts etc. (same as before)

# ========================================
# MANAGE DATA (unchanged)
# ========================================
elif mode == "Manage Data":
    # ... your existing manage section

st.sidebar.markdown("---")
st.sidebar.caption("Set GITHUB_TOKEN & GITHUB_REPO in secrets for auto-push")
