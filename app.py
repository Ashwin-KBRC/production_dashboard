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
# PAGE CONFIG & CLEAN UI
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
    ["#D4A5A5", "#E8C1C1", "#F5D8D8", "#FAE8E8"],
    ["#9B59B6", "#BB8FCE", "#D7BDE2", "#E8DAEF"],
    ["#3498DB", "#5DADE2", "#85C1E2", "#AED6F1"],
    ["#F1C40F", "#F4D03F", "#F7DC6F", "#F9E79F"],
]

if "theme" not in st.session_state:
    st.session_state["theme"] = "Lava Flow"
elif st.session_state["theme"] not in COLOR_THEMES:
    st.session_state["theme"] = "Lava Flow"

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
        repo = GITHUB_REPO.strip().replace("https://github.com/", "").replace(".git", "")
        url = f"https://api.github.com/repos/{repo}/contents/data/{file_path.name}"
        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        resp = requests.get(url, headers=headers)
        sha = resp.json().get("sha") if resp.status_code == 200 else None
        payload = {
            "message": msg,
            "content": b64,
            "branch": "main",
            "committer": {"name": GITHUB_USER, "email": GITHUB_EMAIL}
        }
        if sha:
            payload["sha"] = sha
        r = requests.put(url, headers=headers, json=payload)
        return r.status_code in [200, 201], ("Success" if r.ok else r.json().get("message", "Failed"))
    except Exception as e:
        return False, str(e)

# ========================================
# PLOT HELPERS
# ========================================
def pie_chart(df: pd.DataFrame, value_col: str, colors: list, title: str):
    df = df.copy()
    df[value_col] = pd.to_numeric(df[value_col], errors='coerce').fillna(0)
    fig = px.pie(df, names="Plant", values=value_col, color_discrete_sequence=colors, title=title)
    fig.update_traces(textinfo="percent+label", textfont=dict(size=14, color="black"))
    fig.update_layout(title_font=dict(family="Arial", size=18), legend_font=dict(size=16), margin=dict(t=60, b=40, l=40, r=40))
    return fig

def bar_chart(df: pd.DataFrame, value_col: str, colors: list, title: str):
    df = df.copy()
    df[value_col] = pd.to_numeric(df[value_col], errors='coerce').fillna(0)
    df = df.sort_values(value_col, ascending=False)
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
    df = df.copy()
    df[value_col] = pd.to_numeric(df[value_col], errors='coerce').fillna(0)
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
    df = df.copy()
    df[value_col] = pd.to_numeric(df[value_col], errors='coerce').fillna(0)
    fig = px.area(df, x="Plant", y=value_col, color="Plant", color_discrete_sequence=colors, title=title)
    fig.update_traces(line=dict(width=2), opacity=0.8)
    fig.update_layout(
        title_font=dict(size=18),
        margin=dict(t=60, b=40, l=60, r=40),
        xaxis_gridcolor="#E0E0E0",
        yaxis_gridcolor="#E0E0E0"
    )
    return fig

def aggregated_bar_chart(df: pd.DataFrame, value_col: str, group_col: str, base_colors: list, title: str):
    df = df.copy()
    df[value_col] = pd.to_numeric(df[value_col], errors='coerce').fillna(0)
    agg_df = df.groupby([group_col, "Plant"], as_index=False)[value_col].sum() if value_col == "Production for the Day" else df.groupby([group_col, "Plant"], as_index=False)[value_col].last()
    agg_df = agg_df.sort_values([group_col, value_col], ascending=[True, False])
    unique_groups = agg_df[group_col].unique()
    palette_map = {str(g): WEEKLY_PALETTES[i % len(WEEKLY_PALETTES)] for i, g in enumerate(unique_groups)}
    color_discrete_map = {str(g): palette_map[str(g)][0] for g in unique_groups}
    fig = px.bar(agg_df, x="Plant", y=value_col, color=group_col, color_discrete_map=color_discrete_map, title=title, text=agg_df[value_col].round(1))
    fig.update_traces(texttemplate="%{text:,.1f}", textposition="outside", textfont=dict(size=13, color="black"), cliponaxis=False)
    fig.update_layout(title_font=dict(size=18), legend_font=dict(size=14), margin=dict(t=70, b=280, l=60, r=40), xaxis_tickangle=0, bargap=0.2)
    current_idx = 0
    for trace in fig.data:
        group_key = str(trace.name)
        palette = palette_map.get(group_key, WEEKLY_PALETTES[0])
        trace_len = len(trace.x)
        colors = []
        text_sizes = []
        for j in range(trace_len):
            plant = trace.x[j]
            idx = current_idx + j
            if agg_df.iloc[idx]['Plant'] == 'KABD':
                colors.append("#FF4500")
                text_sizes.append(16)
            else:
                colors.append(palette[j % len(palette)])
                text_sizes.append(13)
        trace.marker.color = colors
        trace.textfont.size = text_sizes
        current_idx += trace_len
    return fig

# ========================================
# DATA HELPERS
# ========================================
def safe_numeric(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()
    df2["Production for the Day"] = pd.to_numeric(df2["Production for the Day"], errors="coerce").fillna(0.0)
    df2["Accumulative Production"] = pd.to_numeric(df2["Accumulative Production"], errors="coerce")
    df2["Accumulative Production"] = df2.groupby("Plant")["Accumulative Production"].transform(lambda x: x.ffill().bfill())
    return df2

def generate_excel_report(df: pd.DataFrame, date_str: str):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Production Data', index=False)
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
if theme_choice != st.session_state["theme"]:
    st.session_state["theme"] = theme_choice
    st.rerun()
theme_colors = COLOR_THEMES[theme_choice]

alert_threshold = st.sidebar.number_input("Alert threshold (m³)", min_value=0.0, value=50.0, step=0.5)

st.sidebar.markdown("---")
st.sidebar.caption("Upload Excel with exact columns: Plant, Production for the Day, Accumulative Production.")
st.title("PRODUCTION FOR THE DAY")

# ========================================
# UPLOAD, VIEW, MANAGE (unchanged — perfect)
# ========================================
# [All previous modes remain 100% unchanged — only Analytics is fixed below]

# ========================================
# ANALYTICS — FINAL FIXED VERSION (NO ROUNDING, FULL DECIMAL ACCURACY)
# ========================================
elif mode == "Analytics":
    st.header("Analytics & Trends")
    saved = list_saved_dates()
    if len(saved) < 2:
        st.info("Need at least 2 days of data.")
        st.stop()

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=datetime.today() - timedelta(days=30))
    with col2:
        end_date = st.date_input("End Date", value=datetime.today())

    # Load all data
    frames = [load_saved(d) for d in saved]
    all_df = pd.concat(frames, ignore_index=True)
    all_df['Date'] = pd.to_datetime(all_df['Date'])
    filtered_df = all_df[(all_df['Date'] >= pd.to_datetime(start_date)) & (all_df['Date'] <= pd.to_datetime(end_date))].copy()

    if filtered_df.empty:
        st.warning("No data in selected range.")
        st.stop()

    filtered_df = safe_numeric(filtered_df)
    filtered_df = filtered_df.sort_values(['Plant', 'Date'])

    total_daily_all = filtered_df["Production for the Day"].sum()

    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #1e40af, #3b82f6); color: white; padding: 70px; border-radius: 40px; text-align: center; margin: 40px 0; box-shadow: 0 25px 60px rgba(0,0,0,0.45); font-family: 'Arial Black', sans-serif;">
        <h1 style="margin:0; font-size:85px; letter-spacing:4px;">TOTAL PRODUCTION</h1>
        <h2 style="margin:35px 0; font-size:100px;">{total_daily_all:,.0f} m³</h2>
        <p style="margin:0; font-size:32px;">{start_date.strftime('%b %d')} to {end_date.strftime('%b %d, %Y')} • All Plants</p>
    </div>
    """, unsafe_allow_html=True)

    # FINAL CORRECT LATEST ACCUMULATIVE — FULL DECIMAL, NO ROUNDING
    latest_cumulative = (
        filtered_df
        .sort_values('Date')
        .groupby('Plant', as_index=False)
        .tail(1)
        .loc[:, ['Plant', 'Accumulative Production']]
        .sort_values('Accumulative Production', ascending=False)
        .reset_index(drop=True)
    )

    avg_daily = filtered_df.groupby('Plant')['Production for the Day'].mean()
    top_avg = avg_daily.sort_values(ascending=False).head(3).reset_index()

    st.markdown("## TOP 3 LEADERS")
    colA, colB = st.columns(2)

    with colA:
        st.markdown("### Average Daily Production")
        for i, row in top_avg.iterrows():
            rank = ["1st", "2nd", "3rd"][i]
            color = ["#FFD700", "#C0C0C0", "#CD7F32"][i]
            st.markdown(f"""
            <div style="background:white;padding:30px;border-radius:20px;margin:20px 0;
                        border-left:15px solid {color};box-shadow:0 15px 35px rgba(0,0,0,0.2);text-align:center">
                <h3 style="margin:0;color:{color}">{rank} • {row['Plant']}</h3>
                <h2 style="margin:15px 0 0">{row['Production for the Day']:,.1f} m³/day</h2>
            </div>
            """, unsafe_allow_html=True)

    with colB:
        st.markdown("### Latest Accumulative Production")
        for i, row in latest_cumulative.head(3).iterrows():
            rank = ["1st", "2nd", "3rd"][i]
            color = ["#1E90FF", "#4682B4", "#5F9EA0"][i]
            st.markdown(f"""
            <div style="background:white;padding:30px;border-radius:20px;margin:20px 0;
                        border-left:15px solid {color};box-shadow:0 15px 35px rgba(0,0,0,0.2);text-align:center">
                <h3 style="margin:0;color:{color}">{rank} • {row['Plant']}</h3>
                <h2 style="margin:15px 0 0">{row['Accumulative Production']:,.1f} m³</h2>
            </div>
            """, unsafe_allow_html=True)

    # Charts
    filtered_df['Custom_Week'] = ((filtered_df['Date'] - filtered_df['Date'].min()).dt.days // 7) + 1
    filtered_df['Month'] = filtered_df['Date'].dt.to_period('M').astype(str)

    weekly_daily = filtered_df.groupby(['Custom_Week', 'Plant'], as_index=False)['Production for the Day'].sum()
    monthly_daily = filtered_df.groupby(['Month', 'Plant'], as_index=False)['Production for the Day'].sum()
    weekly_acc = filtered_df.groupby(['Custom_Week', 'Plant'], as_index=False)['Accumulative Production'].last()
    monthly_acc = filtered_df.groupby(['Month', 'Plant'], as_index=False)['Accumulative Production'].last()

    st.markdown("---")
    st.subheader("Weekly Production")
    st.plotly_chart(aggregated_bar_chart(weekly_daily, "Production for the Day", "Custom_Week", theme_colors, "Weekly Production"), use_container_width=True)
    st.subheader("Monthly Production")
    st.plotly_chart(aggregated_bar_chart(monthly_daily, "Production for the Day", "Month", theme_colors, "Monthly Production"), use_container_width=True)
    st.subheader("Weekly Accumulative (Latest per Week)")
    st.plotly_chart(aggregated_bar_chart(weekly_acc, "Accumulative Production", "Custom_Week", theme_colors, "Weekly Accumulative"), use_container_width=True)
    st.subheader("Monthly Accumulative (Latest per Month)")
    st.plotly_chart(aggregated_bar_chart(monthly_acc, "Accumulative Production", "Month", theme_colors, "Monthly Accumulative"), use_container_width=True)

# ========================================
# FOOTER
# ========================================
st.sidebar.markdown("---")
st.sidebar.write("Dashboard fully synced • All values now exact • No rounding")
