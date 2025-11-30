import os
import hashlib
import base64
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import pandas as pd
import plotly.express as px
import streamlit as st
import io

# ========================================
# PAGE CONFIG & REMOVE STREAMLIT BRANDING
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
        pass

GITHUB_TOKEN = SECRETS.get("GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
GITHUB_REPO = SECRETS.get("GITHUB_REPO") or os.getenv("GITHUB_REPO")
GITHUB_USER = SECRETS.get("GITHUB_USER") or os.getenv("GITHUB_USER", "streamlit-bot")
GITHUB_EMAIL = SECRETS.get("GITHUB_EMAIL") or os.getenv("GITHUB_EMAIL", "streamlit@example.com")

_default_users = {"admin": hashlib.sha256("kbrc123".encode()).hexdigest()}
USERS: Dict[str, str] = _default_users.copy()
if "USERS" in SECRETS and isinstance(SECRETS["USERS"], dict):
    USERS.update(SECRETS["USERS"])

# ========================================
# THEMES
# ========================================
COLOR_THEMES = {
    "Modern Slate": ["#4A6572", "#7D9D9C", "#A4C3B2", "#C9D7D6", "#E5ECE9"],
    "Sunset Glow": ["#F28C38", "#E96E5D", "#D66BA0", "#A56EC3", "#6B5B95"],
    "Ocean Breeze": ["#2E8B8B", "#48A9A6", "#73C2A5", "#9DE0A4", "#C5E8A3"],
    "Corporate": ["#FF4040", "#4040FF", "#40FF40", "#FF8000", "#FFFF40"],
    "Midnight Sky": ["#283593", "#3F51B5", "#673AB7", "#9C27B0", "#BA68C8"],
    "Spring Bloom": ["#D4A59A", "#C2D4B7", "#A9C5A7", "#8DB596", "#71A684"],
    "Executive Suite": ["#4A4A4A", "#1E3A8A", "#D4A017", "#8A8A8A", "#A3BFFA"],
    "Boardroom Blue": ["#2A4066", "#4682B4", "#B0C4DE", "#C0C0C0", "#87CEEB"],
    "Corporate Ivory": ["#F5F5F5", "#008080", "#800000", "#D3D3D3", "#CD853F"],
    "Lava Flow": ["#FF4500", "#FF6B35", "#FF8E53", "#FFB347", "#FFD700"],
    "Desert Storm": ["#8B4513", "#D2691E", "#CD853F", "#DEB887", "#F4A460"],
    "Arctic Ice": ["#00CED1", "#48D1CC", "#40E0D0", "#AFEEEE", "#E0FFFF"],
}

WEEKLY_PALETTES = [
    ["#FF6B6B", "#FF8E8E", "#FFB3B3", "#FFD1D1"],
    ["#4ECDC4", "#7FE0D8", "#A8E6E0", "#D1F2EF"],
    ["#45B7D1", "#6DC8E0", "#96D9F0", "#BFE9FF"],
    ["#96CEB4", "#B8E0D2", "#D9F2E9", "#F0F8F7"],
    ["D4A5A5", "#E8C1C1", "#F5D8D8", "#FAE8E8"],
    ["#9B59B6", "#BB8FCE", "#D7BDE2", "#E8DAEF"],
    ["#3498DB", "#5DADE2", "#85C1E2", "#AED6F1"],
    ["#F1C40F", "#F4D03F", "#F7DC6F", "#F9E79F"],
]

if "theme" not in st.session_state:
    st.session_state.theme = "Lava Flow"

# ========================================
# AUTH FUNCTIONS
# ========================================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def check_credentials(username: str, password: str) -> bool:
    user = username.strip()
    return user in USERS and hash_password(password) == USERS[user]

def login_ui():
    st.sidebar.subheader("Login Required")
    with st.sidebar.form("login_form"):
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pwd")
        submitted = st.form_submit_button("Sign In")
        if submitted:
            if check_credentials(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username.strip()
                st.rerun()
            else:
                st.sidebar.error("Invalid credentials")

def logout():
    for key in ["logged_in", "username"]:
        st.session_state.pop(key, None)
    st.rerun()

def logged_in() -> bool:
    return st.session_state.get("logged_in", False)

# ========================================
# SIDEBAR RENDERER (CLEAN & REUSABLE)
# ========================================
def render_sidebar() -> Tuple[str, str, float]:
    st.sidebar.title("Controls")
    st.sidebar.write(f"**{st.session_state.get('username', 'User')}**")

    if st.sidebar.button("Logout", type="primary"):
        logout()

    mode = st.sidebar.radio("Mode", [
        "Upload New Data",
        "View Historical Data",
        "Manage Data",
        "Analytics"
    ], index=1)

    theme_choice = st.sidebar.selectbox(
        "Theme",
        options=list(COLOR_THEMES.keys()),
        index=list(COLOR_THEMES.keys()).index(st.session_state.theme)
    )
    if theme_choice != st.session_state.theme:
        st.session_state.theme = theme_choice
        st.rerun()

    alert_threshold = st.sidebar.number_input(
        "Alert threshold (m³)", min_value=0.0, value=50.0, step=0.5
    )

    st.sidebar.markdown("---")
    st.sidebar.caption("Required columns: Plant, Production for the Day, Accumulative Production")
    st.sidebar.markdown("---")
    st.sidebar.caption("Set `GITHUB_TOKEN` & `GITHUB_REPO` in secrets for auto-sync")

    return mode, theme_choice, alert_threshold

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
    if not p.exists():
        raise FileNotFoundError(f"No data for {date_str}")
    return pd.read_csv(p)

def delete_saved(date_str: str) -> bool:
    p = DATA_DIR / f"{date_str}.csv"
    if p.exists():
        p.unlink()
        return True
    return False

def attempt_git_push(file_path: Path, msg: str) -> Tuple[bool, str]:
    if not all([GITHUB_TOKEN, GITHUB_REPO]):
        return False, "GitHub not configured"
    try:
        repo = GITHUB_REPO.strip().replace("https://github.com/", "").replace(".git", "")
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
        return r.ok, ("Success" if r.ok else r.json().get("message", "Failed"))
    except Exception as e:
        return False, str(e)

# ========================================
# PLOT & DATA HELPERS
# ========================================
def safe_numeric(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Production for the Day"] = pd.to_numeric(df["Production for the Day"], errors="coerce").fillna(0)
    df["Accumulative Production"] = pd.to_numeric(df["Accumulative Production"], errors="coerce")
    df["Accumulative Production"] = df["Accumulative Production"].ffill().fillna(0)
    return df

def generate_excel_report(df: pd.DataFrame, name: str):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Production Data', index=False)
    output.seek(0)
    return output

# Plot functions (unchanged — pie_chart, bar_chart, line_chart, area_chart, aggregated_bar_chart)
# ... [Keep all your existing plot functions here exactly as before]

# ========================================
# LOGIN CHECK
# ========================================
if not logged_in():
    st.title("Production Dashboard")
    st.markdown("### Please log in to continue")
    login_ui()
    st.stop()

# ========================================
# RENDER SIDEBAR & GET SETTINGS
# ========================================
mode, theme_choice, alert_threshold = render_sidebar()
theme_colors = COLOR_THEMES[theme_choice]
st.title("PRODUCTION DASHBOARD")

# ========================================
# MODE: UPLOAD NEW DATA
# ========================================
if mode == "Upload New Data":
    st.header("Upload New Daily Data")
    uploaded = st.file_uploader("Choose Excel file", type=["xlsx"])
    selected_date = st.date_input("Date for this data", datetime.today())

    if uploaded:
        try:
            df = pd.read_excel(uploaded)
            df.columns = df.columns.str.strip()
        except Exception as e:
            st.error(f"Error reading file: {e}")
            st.stop()

        missing = [c for c in REQUIRED_COLS if c not in df.columns]
        if missing:
            st.error(f"Missing columns: {', '.join(missing)}")
        else:
            st.success("File valid!")
            st.dataframe(df.head(20))
            overwrite = st.checkbox("Overwrite if exists")
            confirm = st.checkbox("I confirm data is correct", value=False)

            if confirm and st.button("Save & Upload", type="primary"):
                df["Date"] = selected_date.strftime("%Y-%m-%d")
                path = save_csv(df, selected_date, overwrite)
                st.success(f"Saved: {path.name}")

                pushed, msg = attempt_git_push(path, f"Add data {selected_date}")
                st.write("GitHub:" if pushed else "GitHub (failed):", msg if pushed else msg)

                df_disp = df[~df["Plant"].astype(str).str.upper().str.contains("TOTAL")]
                df_disp = safe_numeric(df_disp)

                total = df_disp["Production for the Day"].sum()
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #7c3aed, #a78bfa); color:white; padding:60px; border-radius:30px; text-align:center; margin:30px 0;">
                    <h1 style="margin:0; font-size:80px;">{total:,.0f} m³</h1>
                    <p style="margin:10px 0 0; font-size:28px;">Total Production • {selected_date.strftime('%A, %B %d, %Y')}</p>
                </div>
                """, unsafe_allow_html=True)

                # Charts + download...
                # (rest of upload logic same as before)

# ========================================
# MODE: VIEW HISTORICAL DATA (WITH BIG BOX)
# ========================================
elif mode == "View Historical Data":
    st.header("Historical Data")
    dates = list_saved_dates()
    if not dates:
        st.info("No saved data yet.")
    else:
        default = datetime.strptime(dates[0], "%Y-%m-%d").date()
        selected_date = st.date_input("Select date", default)
        date_str = selected_date.strftime("%Y-%m-%d")
        if date_str not in dates:
            st.warning("No data for selected date.")
        else:
            df = safe_numeric(load_saved(date_str))
            df = df[~df["Plant"].astype(str).str.upper().str.contains("TOTAL")]
            total = df["Production for the Day"].sum()

            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #7c3aed, #a78bfa); color:white; padding:70px; border-radius:40px; text-align:center; margin:40px 0; box-shadow:0 20px 50px rgba(0,0,0,0.3);">
                <h1 style="margin:0; font-size:90px; letter-spacing:3px;">TOTAL PRODUCTION</h1>
                <h2 style="margin:30px 0; font-size:110px;">{total:,.0f} m³</h2>
                <p style="margin:0; font-size:32px;">{selected_date.strftime('%A, %B %d, %Y')}</p>
            </div>
            """, unsafe_allow_html=True)

            st.dataframe(df, use_container_width=True)
            # Charts + download (same as before)

# ========================================
# MODE: MANAGE DATA
# ========================================
elif mode == "Manage Data":
    st.header("Manage Saved Files")
    dates = list_saved_dates()
    if not dates:
        st.info("No files.")
    else:
        for d in dates:
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.write(f"**{d}**")
            if c2.button("Delete", key=f"del_{d}"):
                delete_saved(d)
                st.success(f"Deleted {d}")
                st.rerun()
            if c3.button("Download", key=f"dl_{d}"):
                df = load_saved(d)
                excel = generate_excel_report(df, d)
                st.download_button("Download XLSX", excel, f"{d}.xlsx", key=f"dlbtn_{d}")

# ========================================
# MODE: ANALYTICS (WITH BIG TOTAL BOX)
# ========================================
elif mode == "Analytics":
    st.header("Analytics & Trends")
    dates = list_saved_dates()
    if len(dates) < 2:
        st.info("Need at least 2 days of data.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            start = st.date_input("Start", datetime.today() - timedelta(days=30))
        with col2:
            end = st.date_input("End", datetime.today())

        dfs = [load_saved(d) for d in dates]
        all_df = pd.concat(dfs, ignore_index=True)
        all_df['Date'] = pd.to_datetime(all_df['Date'])
        df = all_df[(all_df['Date'].dt.date >= start) & (all_df['Date'].dt.date <= end)]
        if df.empty:
            st.warning("No data in range.")
        else:
            df = safe_numeric(df)
            total = df["Production for the Day"].sum()

            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #1e40af, #3b82f6); color:white; padding:70px; border-radius:40px; text-align:center; margin:40px 0; box-shadow:0 25px 60px rgba(0,0,0,0.4);">
                <h1 style="margin:0; font-size:85px; letter-spacing:4px;">TOTAL PRODUCTION</h1>
                <h2 style="margin:35px 0; font-size:100px;">{total:,.0f} m³</h2>
                <p style="margin:0; font-size:32px;">{start.strftime('%b %d')} → {end.strftime('%b %d, %Y')}</p>
            </div>
            """, unsafe_allow_html=True)

            # Top performers, charts, etc. (same as your latest version)
