import os
import hashlib
import base64
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Tuple, List
import pandas as pd
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
    .stAppDeployButton {display: none !important;}
    .css-1d391kg {padding-top: 0 !important;}
    .st-emotion-cache-1v0mbdj {display: none !important;}
    .st-emotion-cache-1a6n9b8 {display: none !important;}
</style>
""", unsafe_allow_html=True)

DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
REQUIRED_COLS = ["Plant", "Production for the Day", "Accumulative Production"]

# ========================================
# SECRETS & AUTH
# ========================================
try:
    SECRETS = dict(st.secrets)
except:
    SECRETS = dict(os.environ)

GITHUB_TOKEN = SECRETS.get("GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
GITHUB_REPO = SECRETS.get("GITHUB_REPO") or os.getenv("GITHUB_REPO")
GITHUB_USER = SECRETS.get("GITHUB_USER", "streamlit-bot")
GITHUB_EMAIL = SECRETS.get("GITHUB_EMAIL", "streamlit@example.com")

_default_users = {"admin": hashlib.sha256("kbrc123".encode()).hexdigest()}
USERS = _default_users.copy()
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
    "Corporate": ["#FF4040", "#4040FF", "#40FF40", "#FF8000", "#FFFF40"],
    "Midnight Sky": ["#283593", "#3F51B5", "#673AB7", "#9C27B0", "#BA68C8"],
    "Executive Suite": ["#4A4A4A", "#1E3A8A", "#D4A017", "#8A8A8A", "#A3BFFA"],
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
    st.session_state.theme = "Lava Flow"

# ========================================
# AUTH
# ========================================
def check_credentials(u: str, p: str) -> bool:
    u = u.strip().lower()
    return USERS.get(u) == hashlib.sha256(p.encode()).hexdigest()

def login_ui():
    st.sidebar.subheader("Login")
    with st.sidebar.form("login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            if check_credentials(u, p):
                st.session_state.logged_in = True
                st.session_state.username = u
                st.rerun()
            else:
                st.sidebar.error("Wrong credentials")

def logout():
    for k in ["logged_in", "username"]:
        st.session_state.pop(k, None)
    st.rerun()

if not st.session_state.get("logged_in"):
    st.title("Production Dashboard")
    login_ui()
    st.stop()

# ========================================
# FILE & GIT
# ========================================
def save_csv(df: pd.DataFrame, date_obj, overwrite=False):
    f = DATA_DIR / f"{date_obj:%Y-%m-%d}.csv"
    if f.exists() and not overwrite:
        raise FileExistsError("File exists")
    df.to_csv(f, index=False, float_format="%.3f")
    return f

def list_saved_dates():
    return sorted([p.stem for p in DATA_DIR.glob("*.csv")], reverse=True)

def load_saved(date_str: str) -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / f"{date_str}.csv")
    if "Date" not in df.columns:
        df["Date"] = date_str
    df["Date"] = pd.to_datetime(df["Date"])
    return df

def delete_saved(date_str: str):
    (DATA_DIR / f"{date_str}.csv").unlink(missing_ok=True)

def attempt_git_push(path: Path, msg: str):
    if not (GITHUB_TOKEN and GITHUB_REPO):
        return False, "No GitHub config"
    try:
        repo = GITHUB_REPO.replace("https://github.com/", "").replace(".git", "")
        url = f"https://api.github.com/repos/{repo}/contents/data/{path.name}"
        content = base64.b64encode(path.read_bytes()).decode()
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        r = requests.get(url, headers=headers)
        sha = r.json().get("sha") if r.status_code == 200 else None
        payload = {
            "message": msg,
            "content": content,
            "branch": "main",
            "committer": {"name": GITHUB_USER, "email": GITHUB_EMAIL},
            "sha": sha
        }
        r = requests.put(url, headers=headers, json=payload)
        return r.ok, r.text[:100]
    except:
        return False, "GitHub error"

# ========================================
# CHARTS (all original + KABD red highlight)
# ========================================
def pie_chart(df, col, colors, title):
    fig = px.pie(df, names="Plant", values=col, color_discrete_sequence=colors, title=title)
    fig.update_traces(textinfo="percent+label", textfont_size=14)
    return fig

def bar_chart(df, col, colors, title):
    df = df.sort_values(col, ascending=False)
    fig = px.bar(df, x="Plant", y=col, color="Plant", color_discrete_sequence=colors,
                 text=df[col].round(1), title=title)
    fig.update_traces(textposition="outside", texttemplate="%{text:,.1f}")
    fig.update_layout(xaxis_tickangle=0, margin=dict(b=280))
    return fig

def line_chart(df, col, colors, title):
    fig = px.line(df, x="Plant", y=col, markers=True, color_discrete_sequence=colors, title=title)
    fig.update_traces(textposition="top center", texttemplate="%{y:,.1f}")
    return fig

def area_chart(df, col, colors, title):
    fig = px.area(df, x="Plant", y=col, color="Plant", color_discrete_sequence=colors, title=title)
    return fig

def aggregated_bar_chart(df, val_col, group_col, base_colors, title):
    df = df.copy()
    df[val_col] = pd.to_numeric(df[val_col], errors='coerce').fillna(0)
    agg = df.groupby([group_col, "Plant"], as_index=False)[val_col].sum()
    agg = agg.sort_values([group_col, val_col], ascending=[True, False])

    fig = px.bar(agg, x="Plant", y=val_col, color=group_col, title=title,
                 text=agg[val_col].round(1), color_discrete_sequence=base_colors[:len(agg[group_col].unique())])
    fig.update_traces(textposition="outside", texttemplate="%{text:,.1f}")

    # KABD RED HIGHLIGHT
    for trace in fig.data:
        colors = []
        sizes = []
        for plant in trace.x:
            if str(plant).strip().upper() == "KABD":
                colors.append("#FF4500")
                sizes.append(18)
            else:
                colors.append(trace.marker.color)
                sizes.append(13)
        trace.marker.color = colors
        trace.textfont.size = sizes

    return fig

# ========================================
# DATA HELPERS
# ========================================
def safe_numeric(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Production for the Day"] = pd.to_numeric(df["Production for the Day"], errors="coerce").fillna(0)
    df["Accumulative Production"] = pd.to_numeric(df["Accumulative Production"], errors="coerce")
    df["Accumulative Production"] = df.groupby("Plant")["Accumulative Production"].ffill().bfill()
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
    return df

def generate_excel(df, name):
    out = io.BytesIO()
    df.to_excel(out, index=False, engine='xlsxwriter')
    out.seek(0)
    return out

# ========================================
# SIDEBAR
# ========================================
st.sidebar.title("Controls")
st.sidebar.write(f"**{st.session_state.username}**")
if st.sidebar.button("Logout"):
    logout()

mode = st.sidebar.radio("Mode", ["Upload New Data", "View Historical Data", "Analytics", "Manage Data"], index=1)

theme = st.sidebar.selectbox("Theme", list(COLOR_THEMES.keys()), index=list(COLOR_THEMES.keys()).index(st.session_state.theme))
if theme != st.session_state.theme:
    st.session_state.theme = theme
    st.rerun()
colors = COLOR_THEMES[theme]

alert = st.sidebar.number_input("Alert threshold (m³)", 0.0, value=50.0, step=10.0)

st.title("PRODUCTION DASHBOARD")

# ========================================
# 1. UPLOAD MODE
# ========================================
if mode == "Upload New Data":
    st.header("Upload Daily Production")
    file = st.file_uploader("Excel file", type=["xlsx"])
    date = st.date_input("Date", datetime.today())

    if file:
        try:
            df = pd.read_excel(file)
            df.columns = df.columns.str.strip()
        except:
            st.error("Cannot read file")
            st.stop()

        missing = [c for c in REQUIRED_COLS if c not in df.columns]
        if missing:
            st.error(f"Missing: {missing}")
            st.stop()

        df = df[~df["Plant"].astype(str).str.upper().str.contains("TOTAL")]
        df = safe_numeric(df)
        df["Date"] = date

        st.write("Preview")
        st.dataframe(df)

        if st.button("SAVE & SYNC"):
            try:
                path = save_csv(df, date, overwrite=True)
                st.success(f"Saved {path.name}")
                ok, msg = attempt_git_push(path, f"Data {date}")
                st.write("GitHub:", "Success" if ok else "Failed", msg)
            except Exception as e:
                st.error(e)

            total = df["Production for the Day"].sum()
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#7c3aed,#a78bfa);color:white;padding:70px;border-radius:40px;text-align:center;margin:40px 0;box-shadow:0 20px 50px rgba(0,0,0,0.4);">
                <h1 style="margin:0;font-size:90px">TOTAL: {total:,.0f} m³</h1>
                <p style="margin:10px 0 0;font-size:30px">{date:%A, %B %d, %Y}</p>
            </div>
            """, unsafe_allow_html=True)

            st.plotly_chart(bar_chart(df, "Production for the Day", colors, "Daily Production"), use_container_width=True)

# ========================================
# 2. VIEW HISTORICAL
# ========================================
elif mode == "View Historical Data":
    dates = list_saved_dates()
    if not dates:
        st.info("No data yet")
        st.stop()

    sel = st.date_input("Select date", value=datetime.strptime(dates[0], "%Y-%m-%d"))
    sel_str = sel.strftime("%Y-%m-%d")
    if sel_str not in dates:
        st.warning("No data")
        st.stop()

    df = safe_numeric(load_saved(sel_str))
    df = df[~df["Plant"].astype(str).str.upper().str.contains("TOTAL")]

    total = df["Production for the Day"].sum()
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#7c3aed,#a78bfa);color:white;padding:70px;border-radius:40px;text-align:center;margin:40px 0;">
        <h1 style="margin:0;font-size:85px">TOTAL PRODUCTION</h1>
        <h2 style="margin:30px 0;font-size:100px">{total:,.0f} m³</h2>
        <p style="margin:0;font-size:32px">{sel:%A, %B %d, %Y}</p>
    </div>
    """, unsafe_allow_html=True)

    st.dataframe(df, use_container_width=True)
    for chart_func, col, title in [
        (pie_chart, "Production for the Day", "Share"),
        (bar_chart, "Production for the Day", "Daily"),
        (line_chart, "Production for the Day", "Trend"),
        (area_chart, "Production for the Day", "Flow"),
        (bar_chart, "Accumulative Production", "Accumulative"),
    ]:
        st.plotly_chart(chart_func(df, col, colors, f"{title} — {sel_str}"), use_container_width=True)

# ========================================
# 3. ANALYTICS — MUTLA BUG FIXED HERE
# ========================================
elif mode == "Analytics":
    dates = list_saved_dates()
    if len(dates) < 2:
        st.info("Need more data")
        st.stop()

    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("From", datetime.today() - timedelta(days=30))
    with col2:
        end = st.date_input("To", datetime.today())

    dfs = [safe_numeric(load_saved(d)) for d in dates]
    all_df = pd.concat(dfs, ignore_index=True)
    mask = (all_df['Date'].dt.date >= start) & (all_df['Date'].dt.date <= end)
    df = all_df[mask].copy()

    if df.empty:
        st.warning("No data")
        st.stop()

    total_all = df["Production for the Day"].sum()
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1e40af,#3b82f6);color:white;padding:70px;border-radius:40px;text-align:center;margin:40px 0;">
        <h1 style="margin:0;font-size:85px">TOTAL PRODUCTION</h1>
        <h2 style="margin:30px 0;font-size:100px">{total_all:,.0f} m³</h2>
        <p style="margin:0;font-size:32px">{start:%b %d} → {end:%b %d, %Y}</p>
    </div>
    """, unsafe_allow_html=True)

    # FIXED: Correct latest cumulative per plant
    latest_cum = df.loc[df.groupby("Plant")["Date"].idxmax()][["Plant", "Accumulative Production"]]
    latest_cum = latest_cum.sort_values("Accumulative Production", ascending=False).reset_index(drop=True)

    avg_daily = df.groupby("Plant")["Production for the Day"].mean().round(1).sort_values(ascending=False).reset_index()

    st.markdown("## TOP 3 LEADERS")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Average Daily")
        for i, r in avg_daily.head(3).iterrows():
            medal = ["#FFD700", "#C0C0C0", "#CD7F32"][i]
            st.markdown(f"""
            <div style="background:white;padding:30px;border-radius:20px;margin:15px 0;border-left:12px solid {medal};box-shadow:0 10px 25px rgba(0,0,0,0.2);text-align:center">
                <h3 style="margin:0;color:{medal}">{['1st','2nd','3rd'][i]} • {r.Plant}</h3>
                <h2 style="margin:10px 0 0">{r['Production for the Day']:,.1f} m³/day</h2>
            </div>
            """, unsafe_allow_html=True)
    with c2:
        st.markdown("### Latest Accumulative")
        for i, r in latest_cum.head(3).iterrows():
            color = ["#1E90FF", "#4682B4", "#5F9EA0"][i]
            st.markdown(f"""
            <div style="background:white;padding:30px;border-radius:20px;margin:15px 0;border-left:12px solid {color};box-shadow:0 10px 25px rgba(0,0,0,0.2);text-align:center">
                <h3 style="margin:0;color:{color}">{['1st','2nd','3rd'][i]} • {r.Plant}</h3>
                <h2 style="margin:10px 0 0">{r['Accumulative Production']:,.0f} m³</h2>
            </div>
            """, unsafe_allow_html=True)

    df['Week'] = ((df['Date'] - df['Date'].min()).dt.days // 7) + 1
    df['Month'] = df['Date'].dt.to_period('M').astype(str)
    for data, col, name in [
        (df.groupby(['Week','Plant'])['Production for the Day'].sum().reset_index(), "Production for the Day", "Weekly"),
        (df.groupby(['Month','Plant'])['Production for the Day'].sum().reset_index(), "Production for the Day", "Monthly"),
    ]:
        st.plotly_chart(aggregated_bar_chart(data, col, data.columns[0], colors, f"{name} Production"), use_container_width=True)

# ========================================
# 4. MANAGE DATA
# ========================================
elif mode == "Manage Data":
    st.header("Manage Files")
    for d in list_saved_dates():
        c1, c2, c3 = st.columns([3,1,1])
        c1.write(f"**{d}**")
        ")
        if c2.button("Delete", key=f"del_{d}"):
            delete_saved(d)
            st.success("Deleted")
            st.rerun()
        if c3.button("Download", key=f"dl_{d}"):
            df = load_saved(d)
            st.download_button("Download Excel", generate_excel(df, d), f"{d}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.sidebar.markdown("---")
st.sidebar.caption("Auto-sync with GitHub enabled • Contact admin for access")
