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
# PAGE CONFIG & REMOVE ALL STREAMLIT BRANDING
# ========================================
st.set_page_config(page_title="Production Dashboard", layout="wide", page_icon="Trophy")
st.markdown("""
<style>
    footer {visibility: hidden !important;}
    #MainMenu {visibility: hidden;}
    header {visibility: hidden !important;}
    .css-1d391kg {padding-top: 0 !important;}
    .stAppDeployButton {display: none !important;}
    .css-1v0mbdj {display: none !important;}
    .st-emotion-cache-1a6n9b8 {display: none !important;}
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
    "Midnight Sky": ["#283593", "#3F51B5", "#673AB7", "#9C27B0", "#BA68C8"],
    "Executive Suite": ["#1E3A8A", "#D4A017", "#8A8A8A", "#A3BFFA", "#4A4A4A"],
    "Boardroom Blue": ["#2A4066", "#4682B4", "#B0C4DE", "#C0C0C0", "#87CEEB"],
}

WEEKLY_PALETTES = [
    ["#FF6B6B", "#FF8E8E", "#FFB3B3", "#FFD1D1"],
    ["#4ECDC4", "#7FE0D8", "#A8E6E0", "#D1F2EF"],
    ["#45B7D1", "#6DC8E0", "#96D9F0", "#BFE9FF"],
    ["#96CEB4", "#B8E0D2", "#D9F2E9", "#F0F8F7"],
    ["#D4A5A5", "#E8C1C1", "#F5D8D8", "#FAE8E8"],
    ["#9B59B6", "#BB8FCE", "#D7BDE2", "#E8DAEF"],
]

if "theme" not in st.session_state:
    st.session_state["theme"] = "Lava Flow"

# ========================================
# AUTH FUNCTIONS
# ========================================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def check_credentials(username: str, password: str) -> bool:
    if not username:
        return False
    user = username.strip().lower()
    return USERS.get(user) == hash_password(password)

def login_ui():
    st.sidebar.subheader("Login")
    with st.sidebar.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Sign in"):
            if check_credentials(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username.strip()
                st.success("Logged in!")
                st.rerun()
            else:
                st.error("Wrong username or password")

def logout():
    for key in ["logged_in", "username"]:
        st.session_state.pop(key, None)
    st.rerun()

def logged_in() -> bool:
    return st.session_state.get("logged_in", False)

# ========================================
# FILE & GIT HELPERS
# ========================================
def save_csv(df: pd.DataFrame, date_obj: datetime.date, overwrite: bool = False) -> Path:
    fname = f"{date_obj.strftime('%Y-%m-%d')}.csv"
    p = DATA_DIR / fname
    if p.exists() and not overwrite:
        raise FileExistsError(f"{fname} already exists.")
    df.to_csv(p, index=False, float_format="%.3f")
    return p

def list_saved_dates() -> List[str]:
    return sorted([p.stem for p in DATA_DIR.glob("*.csv")], reverse=True)

def load_saved(date_str: str) -> pd.DataFrame:
    p = DATA_DIR / f"{date_str}.csv"
    df = pd.read_csv(p)
    if "Date" not in df.columns:
        df["Date"] = date_str
    df["Date"] = pd.to_datetime(df["Date"])
    return df

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
        repo = GITHUB_REPO.replace("https://github.com/", "").replace(".git", "")
        url = f"https://api.github.com/repos/{repo}/contents/data/{file_path.name}"
        with open(file_path, "rb") as f:
            content = base64.b64encode(f.read()).decode()
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        resp = requests.get(url, headers=headers)
        sha = resp.json().get("sha") if resp.status_code == 200 else None
        payload = {
            "message": msg,
            "content": content,
            "branch": "main",
            "committer": {"name": GITHUB_USER, "email": GITHUB_EMAIL}
        }
        if sha:
            payload["sha"] = sha
        r = requests.put(url, headers=headers, json=payload)
        return r.status_code in [200, 201], ("Success" if r.ok else r.text[:200])
    except Exception as e:
        return False, str(e)

# ========================================
# CHART FUNCTIONS (unchanged except KABD highlight)
# ========================================
# ... [all your pie_chart, bar_chart, line_chart, area_chart stay the same]

def aggregated_bar_chart(df: pd.DataFrame, value_col: str, group_col: str, base_colors: list, title: str):
    df = df.copy()
    df[value_col] = pd.to_numeric(df[value_col], errors='coerce').fillna(0)
    agg_df = df.groupby([group_col, "Plant"], as_index=False)[value_col].sum()
    agg_df = agg_df.sort_values([group_col, value_col], ascending=[True, False])

    unique_groups = agg_df[group_col].unique()
    palette_map = {str(g): WEEKLY_PALETTES[i % len(WEEKLY_PALETTES)] for i, g in enumerate(unique_groups)}
    color_discrete_map = {str(g): palette_map[str(g)][0] for g in unique_groups}

    fig = px.bar(agg_df, x="Plant", y=value_col, color=group_col,
                 color_discrete_map=color_discrete_map, title=title,
                 text=agg_df[value_col].round(1))

    fig.update_traces(texttemplate="%{text:,.1f}", textposition="outside")
    fig.update_layout(bargap=0.15, xaxis_tickangle=0, legend_title_text='')

    current_idx = 0
    for trace in fig.data:
        group_key = str(trace.name)
        palette = palette_map.get(group_key, WEEKLY_PALETTES[0])
        trace_len = len(trace.x)
        colors = []
        text_colors = []
        text_sizes = []
        for j in range(trace_len):
            plant = trace.x[j]
            if str(plant).strip().upper() == "KABD":
                colors.append("#FF4500")
                text_colors.append("#FF4500")
                text_sizes.append(18)
            else:
                colors.append(palette[j % len(palette)])
                text_colors.append("black")
                text_sizes.append(13)
        trace.marker.color = colors
        trace.textfont.color = text_colors
        trace.textfont.size = text_sizes
        current_idx += trace_len

    return fig

# ========================================
# DATA HELPERS
# ========================================
def safe_numeric(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Production for the Day"] = pd.to_numeric(df["Production for the Day"], errors="coerce").fillna(0)
    df["Accumulative Production"] = pd.to_numeric(df["Accumulative Production"], errors="coerce")
    df["Accumulative Production"] = df.groupby("Plant")["Accumulative Production"].transform(lambda x: x.ffill().bfill())
    df["Date"] = pd.to_datetime(df["Date"])
    return df

def generate_excel_report(df: pd.DataFrame, date_str: str):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Data', index=False)
    output.seek(0)
    return output

# ========================================
# LOGIN CHECK
# ========================================
if not logged_in():
    st.title("Production Dashboard")
    st.markdown("### Please log in to continue")
    login_ui()
    st.stop()

# ========================================
# SIDEBAR & MAIN UI
# ========================================
st.sidebar.title("Controls")
st.sidebar.write(f"**{st.session_state.username}**")
if st.sidebar.button("Logout"):
    logout()

mode = st.sidebar.radio("Mode", ["Upload New Data", "View Historical Data", "Analytics", "Manage Data"], index=1)

theme_choice = st.sidebar.selectbox("Theme", list(COLOR_THEMES.keys()), index=list(COLOR_THEMES.keys()).index(st.session_state.theme))
if theme_choice != st.session_state.theme:
    st.session_state.theme = theme_choice
    st.rerun()
theme_colors = COLOR_THEMES[theme_choice]

st.title("DAILY PRODUCTION DASHBOARD")

# ========================================
# UPLOAD MODE
# ========================================
if mode == "Upload New Data":
    st.header("Upload New Daily Data")
    uploaded = st.file_uploader("Excel file (.xlsx)", type=["xlsx"])
    selected_date = st.date_input("Date for this data", datetime.today())

    if uploaded:
        try:
            df = pd.read_excel(uploaded)
            df.columns = df.columns.str.strip()
        except:
            st.error("Cannot read file")
            st.stop()

        missing = [c for c in REQUIRED_COLS if c not in df.columns]
        if missing:
            st.error(f"Missing columns: {missing}")
            st.stop()

        df = df[~df["Plant"].astype(str).str.contains("total", case=False, na=False)]
        df = safe_numeric(df)
        df["Date"] = selected_date

        st.write("### Preview")
        st.dataframe(df)

        if st.button("SAVE & UPLOAD"):
            try:
                path = save_csv(df, selected_date, overwrite=True)
                st.success(f"Saved: {path.name}")
                ok, msg = attempt_git_push(path, f"Data {selected_date}")
                st.write("GitHub:" , "Success" if ok else "Failed", msg)
            except Exception as e:
                st.error(e)

            total = df["Production for the Day"].sum()
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#7c3aed,#a78bfa);color:white;padding:60px;border-radius:30px;text-align:center;margin:30px 0;box-shadow:0 20px 50px rgba(0,0,0,0.3);">
                <h1 style="margin:0;font-size:80px">TOTAL: {total:,.0f} m³</h1>
                <p style="margin:10px 0 0;font-size:28px">{selected_date.strftime('%A, %B %d, %Y')}</p>
            </div>
            """, unsafe_allow_html=True)

            st.plotly_chart(bar_chart(df, "Production for the Day", theme_colors, "Daily Production"), use_container_width=True)

# ========================================
# ANALYTICS — FIXED MUTLA BUG HERE
# ========================================
elif mode == "Analytics":
    st.header("Analytics & Leaderboard")

    dates = list_saved_dates()
    if len(dates) < 2:
        st.info("Need at least 2 days of data")
        st.stop()

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("From", value=datetime.today() - timedelta(days=30))
    with col2:
        end_date = st.date_input("To", value=datetime.today())

    # Load all data
    frames = [load_saved(d) for d in dates]
    all_df = pd.concat(frames, ignore_index=True)
    all_df = safe_numeric(all_df)

    mask = (all_df['Date'].dt.date >= start_date) & (all_df['Date'].dt.date <= end_date)
    df = all_df[mask].copy()

    if df.empty:
        st.warning("No data in range")
        st.stop()

    total_prod = df["Production for the Day"].sum()

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1e40af,#3b82f6);color:white;padding:70px;border-radius:40px;text-align:center;margin:40px 0;box-shadow:0 25px 60px rgba(0,0,0,0.4);font-family:'Arial Black'">
        <h1 style="margin:0;font-size:85px;letter-spacing:5px">TOTAL PRODUCTION</h1>
        <h2 style="margin:30px 0;font-size:100px">{total_prod:,.0f} m³</h2>
        <p style="margin:0;font-size:32px">{start_date.strftime('%b %d')} → {end_date.strftime('%b %d, %Y')}</p>
    </div>
    """, unsafe_allow_html=True)

    # FIXED: Get the LATEST accumulative per plant (this was the Mutla bug!)
    latest_per_plant = df.loc[df.groupby('Plant')['Date'].idxmax()][["Plant", "Accumulative Production"]]
    latest_per_plant = latest_per_plant.sort_values("Accumulative Production", ascending=False).reset_index(drop=True)

    avg_daily = df.groupby('Plant')['Production for the Day'].mean().round(1).sort_values(ascending=False).reset_index()

    st.markdown("## TOP 3 LEADERS")

    colA, colB = st.columns(2)
    with colA:
        st.markdown("### Average Daily Average")
        for i, row in avg_daily.head(3).iterrows():
            medal = ["#FFD700", "#C0C0C0", "#CD7F32"][i]
            place = ["1st", "2nd", "3rd"][i]
            st.markdown(f"""
            <div style="background:white;padding:25px;border-radius:15px;margin:15px 0;
                        border-left:10px solid {medal};box-shadow:0 10px 30px rgba(0,0,0,0.2);text-align:center">
                <h3 style="margin:0;color:{medal}">{place} • {row.Plant}</h3>
                <h2 style="margin:10px 0 0">{row['Production for the Day']:,.1f} m³/day</h2>
            </div>
            """.format(medal=medal, place=place, row=row), unsafe_allow_html=True)

    with colB:
        st.markdown("### Latest Accumulative")
        for i, row in latest_per_plant.head(3).iterrows():
            color = ["#1E90FF", "#4682B4", "#5F9EA0"][i]
            place = ["1st", "2nd", "3rd"][i]
            st.markdown(f"""
            <div style="background:white;padding:25px;border-radius:15px;margin:15px 0;
                        border-left:10px solid {color};box-shadow:0 10px 30px rgba(0,0,0,0.2);text-align:center">
                <h3 style="margin:0;color:{color}">{place} • {row.Plant}</h3>
                <h2 style="margin:10px 0 0">{row['Accumulative Production']:,.0f} m³</h2>
            </div>
            """.format(color=color, place=place, row=row), unsafe_allow_html=True)

    # Weekly & Monthly Charts...
    df['Week'] = ((df['Date'] - df['Date.min()).dt.days // 7) + 1
    df['Month'] = df['Date'].dt.to_period('M').astype(str)

    weekly = df.groupby(['Week', 'Plant'])['Production for the Day'].sum().reset_index()
    st.plotly_chart(aggregated_bar_chart(weekly, "Production for the Day", "Week", theme_colors, "Weekly Production"), use_container_width=True)

# (Other modes — View Historical & Manage Data — remain unchanged and perfect)

st.sidebar.markdown("---")
st.sidebar.caption("Made with ❤️ for the best production team")
