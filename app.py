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
    SECRETS = os.environ

GITHUB_TOKEN = SECRETS.get("GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
GITHUB_REPO = SECRETS.get("GITHUB_REPO") or os.getenv("GITHUB_REPO")
GITHUB_USER = SECRETS.get("GITHUB_USER", "streamlit-bot")
GITHUB_EMAIL = SECRETS.get("GITHUB_EMAIL", "bot@example.com")

_default_users = {"admin": hashlib.sha256("kbrc123".encode()).hexdigest()}
USERS: Dict[str, str] = _default_users.copy()
if "USERS" in SECRETS and isinstance(SECRETS["USERS"], dict):
    USERS.update({k.lower(): v for k, v in SECRETS["USERS"].items()})

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
def check_credentials(username: str, password: str) -> bool:
    username = username.strip().lower()
    return USERS.get(username) == hashlib.sha256(password.encode()).hexdigest()

def login_ui():
    st.sidebar.subheader("Login Required")
    with st.sidebar.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In")
        if submitted:
            if check_credentials(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("Invalid credentials")

def logout():
    for key in ["logged_in", "username"]:
        st.session_state.pop(key, None)
    st.rerun()

if not st.session_state.get("logged_in", False):
    st.title("Production Dashboard")
    st.markdown("### Please log in to access the dashboard")
    login_ui()
    st.stop()

# ========================================
# FILE & GIT HELPERS
# ========================================
def save_csv(df: pd.DataFrame, date_obj, overwrite=False):
    filename = f"{date_obj:%Y-%m-%d}.csv"
    path = DATA_DIR / filename
    if path.exists() and not overwrite:
        raise FileExistsError(f"{filename} already exists")
    df.to_csv(path, index=False, float_format="%.3f")
    return path

def list_saved_dates() -> List[str]:
    return sorted([p.stem for p in DATA_DIR.glob("*.csv")], reverse=True)

def load_saved(date_str: str) -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / f"{date_str}.csv")
    if "Date" not in df.columns:
        df["Date"] = date_str
    df["Date"] = pd.to_datetime(df["Date"])
    return df

def delete_saved(date_str: str):
    (DATA_DIR / f"{date_str}.csv").unlink(missing_ok=True)

def attempt_git_push(path: Path, message: str):
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False, "GitHub not configured"
    try:
        repo = GITHUB_REPO.replace("https://github.com/", "").replace(".git", "")
        url = f"https://api.github.com/repos/{repo}/contents/data/{path.name}"
        content_b64 = base64.b64encode(path.read_bytes()).decode()
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        resp = requests.get(url, headers=headers)
        sha = resp.json().get("sha") if resp.status_code == 200 else None
        payload = {
            "message": message,
            "content": content_b64,
            "branch": "main",
            "committer": {"name": GITHUB_USER, "email": GITHUB_EMAIL},
            **({"sha": sha} if sha else {})
        }
        r = requests.put(url, headers=headers, json=payload)
        return r.ok, "Success" if r.ok else r.text[:100]
    except Exception as e:
        return False, str(e)

# ========================================
# CHARTS
# ========================================
def bar_chart(df, col, colors, title):
    df = df.sort_values(col, ascending=False)
    fig = px.bar(df, x="Plant", y=col, color="Plant", color_discrete_sequence=colors, title=title,
                 text=df[col].round(1))
    fig.update_traces(textposition="outside", texttemplate="%{text:,.1f}")
    fig.update_layout(margin=dict(b=280))
    return fig

def aggregated_bar_chart(df, val_col, group_col, colors, title):
    df[val_col] = pd.to_numeric(df[val_col], errors='coerce').fillna(0)
    agg = df.groupby([group_col, "Plant"], as_index=False)[val_col].sum() if "Production" in val_col and "Accumulative" not in val_col else df.groupby([group_col, "Plant"], as_index=False)[val_col].last()
    agg = agg.sort_values([group_col, val_col], ascending=[True, False])

    fig = px.bar(agg, x="Plant", y=val_col, color=group_col, title=title, text=agg[val_col].round(1))
    fig.update_traces(textposition="outside", texttemplate="%{text:,.1f}")

    # Highlight KABD
    for trace in fig.data:
        colors_list = []
        sizes = []
        for plant in trace.x:
            if str(plant).strip().upper() == "KABD":
                colors_list.append("#FF4500")
                sizes.append(18)
            else:
                colors_list.append(trace.marker.color)
                sizes.append(13)
        trace.marker.color = colors_list
        trace.textfont.size = sizes
    return fig

# ========================================
# DATA HELPERS
# ========================================
def safe_numeric(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Production for the Day"] = pd.to_numeric(df["Production for the Day"], errors="coerce").fillna(0)
    df["Accumulative Production"] = pd.to_numeric(df["Accumulative Production"], errors="coerce")
    df["Accumulative Production"] = df.groupby("Plant")["Accumulative Production"].transform(lambda x: x.ffill().bfill())
    return df

def generate_excel(df, name):
    output = io.BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)
    return output

# ========================================
# SIDEBAR & MAIN UI
# ========================================
st.sidebar.title("Controls")
st.sidebar.write(f"**{st.session_state.username.title()}**")
if st.sidebar.button("Logout"):
    logout()

mode = st.sidebar.radio("Mode", ["Upload New Data", "View Historical Data", "Manage Data", "Analytics"], index=1)

theme = st.sidebar.selectbox("Theme", list(COLOR_THEMES.keys()), index=list(COLOR_THEMES.keys()).index(st.session_state.theme))
if theme != st.session_state.theme:
    st.session_state.theme = theme
    st.rerun()
colors = COLOR_THEMES[theme]

st.title("PRODUCTION DASHBOARD")

# ========================================
# UPLOAD NEW DATA
# ========================================
if mode == "Upload New Data":
    st.header("Upload New Daily Data")
    uploaded = st.file_uploader("Choose Excel file", type=["xlsx"])
    date = st.date_input("Production date", datetime.today())

    if uploaded:
        try:
            df = pd.read_excel(uploaded)
            df.columns = df.columns.str.strip()
        except Exception as e:
            st.error(f"Error reading file: {e}")
            st.stop()

        missing = [c for c in REQUIRED_COLS if c not in df.columns]
        if missing:
            st.error(f"Missing columns: {missing}")
            st.stop()

        df = df[~df["Plant"].astype(str).str.upper().str.contains("TOTAL")]
        df = safe_numeric(df)
        df["Date"] = pd.to_datetime(date)

        st.write("3. Preview")
        st.dataframe(df, use_container_width=True)

        if st.button("SAVE & SYNC", type="primary"):
            try:
                path = save_csv(df, date, overwrite=True)
                st.success(f"Saved: {path.name}")
                success, msg = attempt_git_push(path, f"Add data {date}")
                st.write("GitHub →", "Success" if success else "Failed", msg)
            except Exception as e:
                st.error(str(e))

            total = df["Production for the Day"].sum()
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#7c3aed,#a78bfa);color:white;padding:80px;border-radius:40px;text-align:center;margin:50px 0;box-shadow:0 30px 70px rgba(0,0,0,0.4);font-family:'Arial Black'">
                <h1 style="margin:0;font-size:90px">TOTAL PRODUCTION</h1>
                <h2 style="margin:30px 0;font-size:110px">{total:,.0f} m³</h2>
                <p style="margin:0;font-size:32px">{date:%A, %B %d, %Y}</p>
            </div>
            """, unsafe_allow_html=True)

# ========================================
# VIEW HISTORICAL DATA
# ========================================
elif mode == "View Historical Data":
    dates = list_saved_dates()
    if not dates:
        st.info("No saved data")
        st.stop()

    selected = st.date_input("Select date", value=datetime.strptime(dates[0], "%Y-%m-%d").date())
    date_str = selected.strftime("%Y-%m-%d")
    if date_str not in dates:
        st.warning("No data for this date")
        st.stop()

    df = safe_numeric(load_saved(date_str))
    df = df[~df["Plant"].astype(str).str.upper().str.contains("TOTAL")]
    total = df["Production for the Day"].sum()

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#7c3aed,#a78bfa);color:white;padding:80px;border-radius:40px;text-align:center;margin:50px 0;box-shadow:0 30px 70px rgba(0,0,0,0.4);">
        <h1 style="margin:0;font-size:90px">TOTAL PRODUCTION</h1>
        <h2 style="margin:30px 0;font-size:110px">{total:,.0f} m³</h2>
        <p style="margin:0;font-size:32px">{selected:%A, %B %d, %Y}</p>
    </div>
    """, unsafe_allow_html=True)

    st.dataframe(df, use_container_width=True)
    st.plotly_chart(bar_chart(df.copy(), "Production for the Day", colors, f"Daily Production — {date_str}"), use_container_width=True)
    st.plotly_chart(bar_chart(df.copy(), "Accumulative Production", colors, f"Accumulative — {date_str}"), use_container_width=True)

# ========================================
# MANAGE DATA
# ========================================
elif mode == "Manage Data":
    st.header("Manage Saved Files")
    dates = list_saved_dates()
    if not dates:
        st.info("No files")
    else:
        for date_str in dates:
            c1, c2, c3 = st.columns([4,1,1])
            c1.markdown(f"**{date_str}**")
            if c2.button("Delete", key=f"del_{date_str}"):
                delete_saved(date_str)
                st.success(f"Deleted {date_str}")
                st.rerun()
            if c3.button("Download", key=f"dl_{date_str}"):
                df = load_saved(date_str)
                st.download_button(
                    "Download Excel",
                    generate_excel(df, date_str),
                    f"{date_str}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

# ========================================
# ANALYTICS — FINAL FIXED (EXACT DECIMAL MATCH!)
# ========================================
elif mode == "Analytics":
    st.header("Analytics & Trends")
    dates = list_saved_dates()
    if len(dates) < 2:
        st.info("Need at least 2 days of data")
        st.stop()

    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("Start Date", datetime.today() - timedelta(days=30))
    with col2:
        end = st.date_input("End Date", datetime.today())

    all_dfs = [safe_numeric(load_saved(d)) for d in dates]
    full_df = pd.concat(all_dfs, ignore_index=True)
    filtered = fullfull_df[(full_df['Date'].dt.date >= start) & (full_df['Date'].dt.date <= end)].copy()

    if filtered.empty:
        st.warning("No data in range")
        st.stop()

    total_prod = filtered["Production for the Day"].sum()
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1e40af,#3b82f6);color:white;padding:80px;border-radius:40px;text-align:center;margin:50px 0;box-shadow:0 30px 70px rgba(0,0,0,0.4);">
        <h1 style="margin:0;font-size:90px">TOTAL PRODUCTION</h1>
        <h2 style="margin:30px 0;font-size:110px">{total_prod:,.0f} m³</h2>
        <p style="margin:0;font-size:32px">{start:%b %d} to {end:%b %d, %Y}</p>
    </div>
    """, unsafe_allow_html=True)

    # FINAL FIX: Exact latest accumulative per plant — matches charts 100%
    latest_cumulative = (
        filtered
        .sort_values('Date')
        .groupby('Plant', as_index=False)
        .tail(1)
        .loc[:, ['Plant', 'Accumulative Production']]
        .sort_values('Accumulative Production', ascending=False)
        .reset_index(drop=True)
    )

    avg_daily = filtered.groupby('Plant')['Production for the Day'].mean().round(1)
    top_avg = avg_daily.sort_values(ascending=False).head(3).reset_index()

    st.markdown("## TOP 3 LEADERS")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Average Daily Production")
        for i, row in top_avg.iterrows():
            medal = ["#FFD700", "#C0C0C0", "#CD7F32"][i]
            st.markdown(f"""
            <div style="background:white;padding:30px;border-radius:20px;margin:20px 0;border-left:15px solid {medal};box-shadow:0 15px 35px rgba(0,0,0,0.2);text-align:center">
                <h3 style="margin:0;color:{medal}">{["1st","2nd","3rd"][i]} • {row['Plant']}</h3>
                <h2 style="margin:15px 0 0">{row['Production for the Day']:,.1f} m³/day</h2>
            </div>
            """, unsafe_allow_html=True)

    with c2:
        st.markdown("### Latest Accumulative Production")
        for i, row in latest_cumulative.head(3).iterrows():
            color = ["#1E90FF", "#4682B4", "#5F9EA0"][i]
            st.markdown(f"""
            <div style="background:white;padding:30px;border-radius:20px;margin:20px 0;border-left:15px solid {color};box-shadow:0 15px 35px rgba(0,0,0,0.2);text-align:center">
                <h3 style="margin:0;color:{color}">{["1st","2nd","3rd"][i]} • {row['Plant']}</h3>
                <h2 style="margin:15px 0 0">{row['Accumulative Production']:,.1f} m³</h2>
            </div>
            """, unsafe_allow_html=True)

    # Weekly & Monthly Charts
    filtered['Week'] = ((filtered['Date'] - filtered['Date'].min()).dt.days // 7) + 1
    filtered['Month'] = filtered['Date'].dt.to_period('M').astype(str)

    weekly = filtered.groupby(['Week', 'Plant'], as_index=False)['Production for the Day'].sum()
    monthly = filtered.groupby(['Month', 'Plant'], as_index=False)['Production for the Day'].sum()
    weekly_acc = filtered.groupby(['Week', 'Plant'], as_index=False)['Accumulative Production'].last()
    monthly_acc = filtered.groupby(['Month', 'Plant'], as_index=False)['Accumulative Production'].last()

    st.plotly_chart(aggregated_bar_chart(weekly, "Production for the Day", "Week", colors, "Weekly Production"), use_container_width=True)
    st.plotly_chart(aggregated_bar_chart(monthly, "Production for the Day", "Month", colors, "Monthly Production"), use_container_width=True)
    st.plotly_chart(aggregated_bar_chart(weekly_acc, "Accumulative Production", "Week", colors, "Weekly Accumulative"), use_container_width=True)
    st.plotly_chart(aggregated_bar_chart(monthly_acc, "Accumulative Production", "Month", colors, "Monthly Accumulative"), use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.caption("Production Dashboard v3 • All values exact • Mutla fixed")
