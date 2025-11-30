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
# PAGE CONFIG — FORCE SIDEBAR ALWAYS OPEN + REMOVE BRANDING
# ========================================
st.set_page_config(
    page_title="Production Dashboard",
    page_icon="Trophy",
    layout="wide",
    initial_sidebar_state="expanded"  # ← Sidebar always visible
)

# ========================================
# HIDE HAMBURGER MENU & COLLAPSE BUTTON COMPLETELY
# ========================================
st.markdown("""
<style>
    /* Hide hamburger menu & collapse button */
    .css-1d391kg {display: none !important;}
    .css-1v0mbdj {display: none !important;}
    .st-emotion-cache-1a6n9b8 {display: none !important;}
    section[data-testid="stSidebar"] > div:first-child {visibility: hidden !important;}
    
    /* Hide Streamlit branding */
    footer {visibility: hidden !important;}
    #MainMenu {visibility: hidden !important;}
    header {visibility: hidden !important;}
    .stAppDeployButton {display: none !important;}

    /* Wider, clean sidebar */
    section[data-testid="stSidebar"] {
        width: 380px !important;
        min-width: 380px !important;
        max-width: 380px !important;
        padding: 2rem 1rem;
        background: #0e1117;
        border-right: 3px solid #ff4500;
    }
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
except:
    try:
        SECRETS = dict(os.environ)
    except:
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
    "Lava Flow": ["#FF4500", "#FF6B35", "#FF8E53", "#FFB347", "#FFD700"],
    "Modern Slate": ["#4A6572", "#7D9D9C", "#A4C3B2", "#C9D7D6", "#E5ECE9"],
    "Sunset Glow": ["#F28C38", "#E96E5D", "#D66BA0", "#A56EC3", "#6B5B95"],
    "Ocean Breeze": ["#2E8B8B", "#48A9A6", "#73C2A5", "#9DE0A4", "#C5E8A3"],
    "Midnight Sky": ["#283593", "#3F51B5", "#673AB7", "#9C27B0", "#BA68C8"],
    "Arctic Ice": ["#00CED1", "#48D1CC", "#40E0D0", "#AFEEEE", "#E0FFFF"],
}

WEEKLY_PALETTES = [
    ["#FF6B6B", "#FF8E8E", "#FFB3B3", "#FFD1D1"],
    ["#4ECDC4", "#7FE0D8", "#A8E6E0", "#D1F2EF"],
    ["#45B7D1", "#6DC8E0", "#96D9F0", "#BFE9FF"],
    ["#96CEB4", "#B8E0D2", "#D9F2E9", "#F0F8F7"],
    ["#D4A5A5", "#E8C1C1", "#F5D8D8", "#FAE8E8"],
    ["#9B59B6", "#BB8FCE", "#D7BDE2", "#E8DAEF"],
    ["#3498DB", "#5DADE2", "#85C1E2", "#AED6F1"],
    ["#F1C40F", "#F4D03F", "#F7DC6F", "#F9E79F"],
]

if "theme" not in st.session_state:
    st.session_state.theme = "Lava Flow"

# ========================================
# AUTH FUNCTIONS
# ========================================
def check_credentials(u: str, p: str) -> bool:
    u = u.strip()
    return u in USERS and hashlib.sha256(p.encode()).hexdigest() == USERS[u]

def login_ui():
    st.sidebar.title("Login Required")
    with st.sidebar.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Sign In"):
            if check_credentials(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.rerun()
            else:
                st.sidebar.error("Wrong credentials")

def logout():
    st.session_state.clear()
    st.rerun()

def logged_in() -> bool:
    return st.session_state.get("logged_in", False)

# ========================================
# CRITICAL: MERGE MUTLA + MUTLA-2 INTO ONE PLANT
# ========================================
def merge_mutla_plants(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Plant"] = df["Plant"].astype(str).str.strip().str.upper()
    
    # Replace MUTLA-2 → MUTLA
    df["Plant"] = df["Plant"].replace({
        "MUTLA-2": "MUTLA",
        "MUTLA 2": "MUTLA",
        "MUTLA2": "MUTLA"
    })
    
    # Group by Plant and sum numeric columns
    df = df.groupby("Plant", as_index=False).agg({
        "Production for the Day": "sum",
        "Accumulative Production": "sum"
    })
    
    return df

# ========================================
# FILE HELPERS
# ========================================
def save_csv(df: pd.DataFrame, date_obj: datetime.date, overwrite=False):
    p = DATA_DIR / f"{date_obj:%Y-%m-%d}.csv"
    if p.exists() and not overwrite:
        raise FileExistsError("File exists")
    df.to_csv(p, index=False)
    return p

def list_saved_dates() -> List[str]:
    return sorted([f.stem for f in DATA_DIR.glob("*.csv")], reverse=True)

def load_saved(date_str: str) -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / f"{date_str}.csv")
    return merge_mutla_plants(df)  # ← MUTLA merged here too

def safe_numeric(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Production for the Day"] = pd.to_numeric(df["Production for the Day"], errors="coerce").fillna(0)
    df["Accumulative Production"] = pd.to_numeric(df["Accumulative Production"], errors="coerce").fillna(0)
    return df

def generate_excel_report(df: pd.DataFrame, date_str: str):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Production Data', index=False)
    output.seek(0)
    return output

# ========================================
# PLOT HELPERS (unchanged — KABD highlight preserved)
# ========================================
def pie_chart(df, val, colors, title):
    fig = px.pie(df, names="Plant", values=val, color_discrete_sequence=colors, title=title)
    fig.update_traces(textinfo="percent+label", textfont_size=14)
    fig.update_layout(margin=dict(t=60, b=40, l=40, r=40))
    return fig

def bar_chart(df, val, colors, title):
    df = df.sort_values(val, ascending=False)
    fig = px.bar(df, x="Plant", y=val, color="Plant", color_discrete_sequence=colors, title=title, text=df[val].round(1))
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside", textfont_size=16)
    fig.update_layout(margin=dict(t=60, b=280, l=60, r=40), xaxis_tickangle=0)
    return fig

def aggregated_bar_chart(df, val, group, colors, title):
    agg = df.groupby([group, "Plant"], as_index=False)[val].sum()
    agg = agg.sort_values([group, val], ascending=[True, False])
    fig = px.bar(agg, x="Plant", y=val, color=group, title=title, text=agg[val].round(0))
    fig.update_traces(textposition="outside")
    fig.update_layout(margin=dict(t=70, b=280), bargap=0.2)

    # KABD highlight
    current = 0
    for trace in fig.data:
        for i in range(len(trace.x)):
            if agg.iloc[current + i]["Plant"] == "KABD":
                trace.marker.color[i] = "#FF4500"
                trace.textfont.color[i] = "#FF4500"
                trace.textfont.size[i] = 16
        current += len(trace.x)
    return fig

# ========================================
# LOGIN CHECK
# ========================================
if not logged_in():
    st.title("Production Dashboard")
    st.markdown("### Please log in")
    login_ui()
    st.stop()

# ========================================
# SIDEBAR — ALWAYS OPEN
# ========================================
with st.sidebar:
    st.title("Controls")
    st.write(f"**{st.session_state.username}**")
    if st.button("Logout", type="primary"):
        logout()

    mode = st.radio("Mode", ["Upload New Data", "View Historical Data", "Manage Data", "Analytics"], index=1)
    theme_choice = st.selectbox("Theme", list(COLOR_THEMES.keys()), index=list(COLOR_THEMES.keys()).index(st.session_state.theme))
    if theme_choice != st.session_state.theme:
        st.session_state.theme = theme_choice
        st.rerun()

    alert_threshold = st.number_input("Alert threshold (m³)", 0.0, value=50.0, step=0.5)
    st.markdown("---")
    st.caption("MUTLA & MUTLA-2 are automatically merged")

theme_colors = COLOR_THEMES[st.session_state.theme]
st.title("PRODUCTION DASHBOARD")

# ========================================
# UPLOAD MODE
# ========================================
if mode == "Upload New Data":
    st.header("Upload Daily Production")
    uploaded = st.file_uploader("Excel file", type="xlsx")
    date = st.date_input("Date", datetime.today())

    if uploaded:
        df = pd.read_excel(uploaded)
        df.columns = df.columns.str.strip()
        missing = [c for c in REQUIRED_COLS if c not in df.columns]
        if missing:
            st.error(f"Missing: {missing}")
        else:
            df = merge_mutla_plants(df)  # ← MUTLA merged here
            df = safe_numeric(df)
            st.dataframe(df)

            if st.checkbox("Confirm & Save") and st.button("Upload"):
                df["Date"] = date.strftime("%Y-%m-%d")
                save_csv(df, date, overwrite=True)
                st.success("Saved!")

                total = df["Production for the Day"].sum()
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #7c3aed, #a78bfa); color:white; padding:70px; border-radius:40px; text-align:center; margin:40px 0; box-shadow:0 25px 60px rgba(0,0,0,0.4);">
                    <h1 style="margin:0; font-size:90px;">TOTAL: {total:,.0f} m³</h1>
                    <p style="margin:10px; font-size:28px;">{date.strftime('%A, %B %d, %Y')}</p>
                </div>
                """, unsafe_allow_html=True)

                st.plotly_chart(pie_chart(df, "Production for the Day", theme_colors, "Daily Share"), use_container_width=True)
                st.plotly_chart(bar_chart(df, "Production for the Day", theme_colors, "Daily Production"), use_container_width=True)

# ========================================
# VIEW HISTORICAL
# ========================================
elif mode == "View Historical Data":
    dates = list_saved_dates()
    if not dates:
        st.info("No data")
    else:
        date = st.date_input("Select date", datetime.strptime(dates[0], "%Y-%m-%d"))
        date_str = date.strftime("%Y-%m-%d")
        if date_str not in dates:
            st.warning("No data")
        else:
            df = safe_numeric(load_saved(date_str))
            total = df["Production for the Day"].sum()

            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #7c3aed, #a78bfa); color:white; padding:70px; border-radius:40px; text-align:center; margin:40px 0; box-shadow:0 25px 60px rgba(0,0,0,0.4);">
                <h1 style="margin:0; font-size:90px;">TOTAL PRODUCTION</h1>
                <h2 style="margin:30px; font-size:110px;">{total:,.0f} m³</h2>
                <p style="font-size:32px;">{date.strftime('%A, %B %d, %Y')}</p>
            </div>
            """, unsafe_allow_html=True)

            st.dataframe(df, use_container_width=True)
            st.plotly_chart(bar_chart(df, "Production for the Day", theme_colors, "Daily Production"), use_container_width=True)

# ========================================
# MANAGE & ANALYTICS (same logic with MUTLA merged automatically)
# ========================================
elif mode == "Analytics":
    dates = list_saved_dates()
    if len(dates) < 2:
        st.info("Need more data")
    else:
        start = st.date_input("Start", datetime.today() - timedelta(days=30))
        end = st.date_input("End", datetime.today())

        dfs = [safe_numeric(load_saved(d)) for d in dates
               if start <= datetime.strptime(d, "%Y-%m-%d").date() <= end]
        if not dfs:
            st.warning("No data")
        else:
            df = pd.concat(dfs)
            total = df["Production for the Day"].sum()

            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #1e40af, #3b82f6); color:white; padding:70px; border-radius:40px; text-align:center; margin:40px 0;">
                <h1 style="margin:0; font-size:90px;">TOTAL: {total:,.0f} m³</h1>
                <p style="font-size:32px;">{start.strftime('%b %d')} → {end.strftime('%b %d, %Y')}</p>
            </div>
            """, unsafe_allow_html=True)

            # Top 3 leaders
            avg = df.groupby("Plant")["Production for the Day"].mean().round(1).sort_values(ascending=False).head(3)
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### Top Average Daily")
                for i, (plant, val) in enumerate(avg.items()):
                    color = ["#FFD700", "#C0C0C0", "#CD7F32"][i]
                    st.markdown(f"<div style='background:white;padding:20px;border-left:10px solid {color};margin:10px 0;border-radius:10px;'><h3>{i+1}. {plant}</h3><h2>{val:,.0f} m³/day</h2></div>", unsafe_allow_html=True)

            st.plotly_chart(aggregated_bar_chart(df, "Production for the Day", df["Date"].dt.to_period("W").astype(str), theme_colors, "Weekly Production"), use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.caption("MUTLA + MUTLA-2 merged automatically | GitHub sync enabled")
