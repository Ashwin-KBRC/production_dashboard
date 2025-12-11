import os
import hashlib
import base64
import requests
import csv
from pathlib import Path
from datetime import datetime, timedelta, date, timezone
from typing import Dict, Any, Tuple, List
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import io
import xlsxwriter

# ========================================
# 1. PAGE CONFIGURATION
# ========================================
st.set_page_config(
    page_title="KBRC Executive Dashboard", 
    layout="wide", 
    page_icon="🏭",
    initial_sidebar_state="expanded"
)

# ========================================
# 2. SESSION STATE & DARK MODE SETUP
# ========================================
if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = False

# ========================================
# 3. CSS STYLING (DYNAMIC LIGHT/DARK)
# ========================================
def inject_css():
    """
    Injects professional CSS based on the current Light/Dark mode state.
    Handles all UI elements including Cards, Tables, Tabs, and Text.
    """
    if st.session_state["dark_mode"]:
        # DARK MODE PALETTE
        bg_color = "#0f172a"          # Slate 900
        text_color = "#f8fafc"        # Slate 50
        card_bg = "#1e293b"           # Slate 800
        border_color = "#334155"      # Slate 700
        sidebar_bg = "#111827"        # Gray 900
        secondary_text = "#94a3b8"    # Slate 400
    else:
        # LIGHT MODE PALETTE
        bg_color = "#f8fafc"          # Slate 50
        text_color = "#1e293b"        # Slate 800
        card_bg = "#ffffff"           # White
        border_color = "#e2e8f0"      # Slate 200
        sidebar_bg = "#ffffff"        # White
        secondary_text = "#64748b"    # Slate 500

    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
        
        html, body, [class*="css"], .stApp {{
            font-family: 'Inter', sans-serif;
            color: {text_color};
            background-color: {bg_color};
        }}

        /* HIDE DEFAULT STREAMLIT BRANDING */
        footer {{visibility: hidden !important;}}
        #MainMenu {{visibility: hidden;}}
        header {{visibility: hidden !important;}}
        .stAppDeployButton {{display: none !important;}}
        
        /* SIDEBAR STYLING */
        [data-testid="stSidebar"] {{
            background-color: {sidebar_bg};
            border-right: 1px solid {border_color};
        }}
        [data-testid="stSidebarCollapseButton"] {{display: none !important;}}

        /* PROFESSIONAL METRIC CARDS */
        .metric-card {{
            background: {card_bg};
            border: 1px solid {border_color};
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            transition: transform 0.2s, box-shadow 0.2s;
            color: {text_color};
        }}
        .metric-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
            border-color: #3b82f6;
        }}
        
        /* HERO BANNER GRADIENT */
        .hero-banner {{
            background: linear-gradient(135deg, #1e3a8a 0%, #172554 100%);
            color: white;
            padding: 40px;
            border-radius: 16px;
            margin-bottom: 30px;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
        }}
        
        /* CUSTOM TAB STYLING */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 10px;
            background-color: transparent;
        }}
        .stTabs [data-baseweb="tab"] {{
            border-radius: 6px;
            color: {secondary_text};
            font-weight: 600;
            padding: 10px 20px;
        }}
        .stTabs [aria-selected="true"] {{
            background-color: {card_bg};
            border: 1px solid {border_color};
            border-bottom: 2px solid #3b82f6;
            color: #3b82f6;
        }}

        /* DATAFRAME & TABLE STYLING */
        .stDataFrame {{ border: 1px solid {border_color}; border-radius: 8px; overflow: hidden; }}
        
        /* HEADERS */
        h1, h2, h3, h4, h5, h6 {{ color: {text_color} !important; font-weight: 700; }}
        
        /* INSIGHT BOX */
        .insight-box {{
            background: rgba(59, 130, 246, 0.1);
            border-left: 4px solid #3b82f6;
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 20px;
            color: {text_color};
        }}

        /* LEADERBOARD BOXES */
        .leaderboard-box {{
            background-color: {card_bg};
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 10px;
            border-left-width: 5px;
            border-left-style: solid;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: transform 0.2s;
        }}
        .leaderboard-box:hover {{
            transform: scale(1.01);
        }}
        .lb-rank {{ font-size: 1.1em; font-weight: 700; opacity: 0.8; }}
        .lb-name {{ font-weight: 600; font-size: 1.05em; margin-left: 10px; }}
        .lb-val {{ font-weight: 800; font-size: 1.1em; }}
    </style>
    """, unsafe_allow_html=True)

inject_css()

# ========================================
# 4. SETUP & AUTHENTICATION
# ========================================
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = DATA_DIR / "access_logs.csv"
FORECAST_FILE = DATA_DIR / "monthly_targets.csv" # NEW: File to store forecasts
REQUIRED_COLS = ["Plant", "Production for the Day", "Accumulative Production"]

# CONFIGURATION SECRETS
SECRETS = {}
try: SECRETS = dict(st.secrets)
except: SECRETS = {}

GITHUB_TOKEN = SECRETS.get("GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
GITHUB_REPO = SECRETS.get("GITHUB_REPO") or os.getenv("GITHUB_REPO")
GITHUB_USER = SECRETS.get("GITHUB_USER") or os.getenv("GITHUB_USER", "streamlit-bot")
GITHUB_EMAIL = SECRETS.get("GITHUB_EMAIL") or os.getenv("GITHUB_EMAIL", "streamlit@example.com")

_default_users = {
    "admin": hashlib.sha256("kbrc123".encode()).hexdigest(),
    "manager": hashlib.sha256("sjk@2025".encode()).hexdigest(),
    "production": hashlib.sha256("Production@123".encode()).hexdigest()
}

USERS: Dict[str, str] = _default_users.copy()
if "USERS" in SECRETS and isinstance(SECRETS["USERS"], dict):
    for k, v in SECRETS["USERS"].items():
        USERS[k] = v

# ========================================
# 5. LOGIC & UTILITY FUNCTIONS
# ========================================
def get_kuwait_time():
    """Returns current time in Kuwait (UTC+3)"""
    return datetime.now(timezone.utc) + timedelta(hours=3)

def get_greeting():
    h = get_kuwait_time().hour
    if h < 12: return "Good Morning"
    elif 12 <= h < 18: return "Good Afternoon"
    else: return "Good Evening"

def format_m3(value):
    """Standardized formatting for Cubic Meters"""
    return f"{value:,.3f} m³"

def init_logs():
    if not LOG_FILE.exists():
        with open(LOG_FILE, 'w', newline='') as f:
            csv.writer(f).writerow(["Timestamp", "User", "Event"])

def log_event(username: str, event: str):
    init_logs()
    try:
        # Use Kuwait Time for logging
        ts = get_kuwait_time().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, 'a', newline='') as f:
            csv.writer(f).writerow([ts, username, event])
    except: pass

def get_logs() -> pd.DataFrame:
    init_logs()
    try: return pd.read_csv(LOG_FILE)
    except: return pd.DataFrame(columns=["Timestamp", "User", "Event"])

# --- FORECAST FUNCTIONS (NEW) ---
def init_forecasts():
    if not FORECAST_FILE.exists():
        with open(FORECAST_FILE, 'w', newline='') as f:
            csv.writer(f).writerow(["Year", "Month", "Target"])

def save_forecast(year: int, month: str, target: float):
    init_forecasts()
    # Read existing
    try:
        df = pd.read_csv(FORECAST_FILE)
    except:
        df = pd.DataFrame(columns=["Year", "Month", "Target"])
    
    # Update or Append
    # Remove old entry for this Y/M if exists
    df = df[~((df['Year'] == year) & (df['Month'] == month))]
    # Add new
    new_row = pd.DataFrame([{"Year": year, "Month": month, "Target": target}])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(FORECAST_FILE, index=False)

def get_forecast(year: int, month: str) -> float:
    init_forecasts()
    try:
        df = pd.read_csv(FORECAST_FILE)
        row = df[(df['Year'] == year) & (df['Month'] == month)]
        if not row.empty:
            return float(row.iloc[0]['Target'])
    except:
        pass
    return 0.0

def check_credentials(username: str, password: str) -> bool:
    if not username: return False
    user = username.strip()
    if user in USERS:
        v = hashlib.sha256(password.encode()).hexdigest() == USERS[user]
        log_event(user, "Login Success" if v else "Login Failed")
        return v
    return False

def save_csv(df: pd.DataFrame, date_obj: date, overwrite: bool = False) -> Path:
    fname = f"{date_obj.strftime('%Y-%m-%d')}.csv"
    p = DATA_DIR / fname
    if p.exists() and not overwrite: raise FileExistsError(f"{fname} exists.")
    df.to_csv(p, index=False, float_format="%.3f")
    return p

def list_saved_dates() -> List[str]:
    return sorted([p.name.replace(".csv", "") for p in DATA_DIR.glob("*.csv") if "access_logs" not in p.name and "monthly_targets" not in p.name], reverse=True)

def load_saved(date_str: str) -> pd.DataFrame:
    p = DATA_DIR / f"{date_str}.csv"
    if not p.exists(): raise FileNotFoundError("File missing")
    return pd.read_csv(p)

def delete_saved(date_str: str) -> bool:
    p = DATA_DIR / f"{date_str}.csv"
    if p.exists():
        p.unlink()
        return True
    return False

def attempt_git_push(file_path: Path, msg: str) -> Tuple[bool, str]:
    if not GITHUB_TOKEN or not GITHUB_REPO: return False, "Git not configured"
    try:
        repo = GITHUB_REPO.strip().replace("https://github.com/", "").replace(".git", "")
        url = f"https://api.github.com/repos/{repo}/contents/data/{file_path.name}"
        if file_path.exists():
             with open(file_path, "rb") as f: content = base64.b64encode(f.read()).decode()
        else: return False, "File missing"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        resp = requests.get(url, headers=headers)
        sha = resp.json().get("sha") if resp.status_code == 200 else None
        payload = {"message": msg, "content": content, "branch": "main", "committer": {"name": GITHUB_USER, "email": GITHUB_EMAIL}}
        if sha: payload["sha"] = sha
        r = requests.put(url, headers=headers, json=payload)
        return r.ok, "Synced" if r.ok else "Sync Failed"
    except Exception as e: return False, str(e)

def safe_numeric(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()
    df2["Production for the Day"] = pd.to_numeric(df2["Production for the Day"], errors="coerce").fillna(0.0)
    df2["Accumulative Production"] = pd.to_numeric(df2["Accumulative Production"], errors="coerce")
    df2["Accumulative Production"] = df2.groupby("Plant")["Accumulative Production"].transform(lambda x: x.ffill().bfill())
    return df2

def generate_excel_report(df: pd.DataFrame, date_str: str):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Data', index=False, float_format="%.3f")
        workbook = writer.book
        worksheet = writer.sheets['Data']
        format_num = workbook.add_format({'num_format': '#,##0.000 "m³"'})
        worksheet.set_column('B:C', 18, format_num)
    output.seek(0)
    return output

def generate_smart_insights(df):
    """
    INNOVATION: Automatically generates text-based insights for the Executive Summary.
    """
    total = df['Production for the Day'].sum()
    top_plant = df.groupby('Plant')['Production for the Day'].sum().idxmax() if not df.empty else "N/A"
    top_val = df.groupby('Plant')['Production for the Day'].sum().max() if not df.empty else 0
    avg = df['Production for the Day'].mean() if not df.empty else 0
    
    insight = f"**Executive Summary:** The total production for this period stands at **{format_m3(total)}**. "
    insight += f"The leading facility is **{top_plant}**, contributing **{format_m3(top_val)}** to the total output. "
    insight += f"On average, daily plant production is tracking at **{format_m3(avg)}**."
    return insight

# ========================================
# 6. CHARTING ENGINE
# ========================================
def get_theme_colors(theme_name):
    # Professional Solid Colors
    themes = {
        "Neon Cyber": ["#F72585", "#7209B7", "#3A0CA3", "#4361EE", "#4CC9F0"], # Bright/Neon
        "Executive Blue": ["#1E40AF", "#3B82F6", "#60A5FA", "#93C5FD", "#BFDBFE"], # Solid Blues
        "Emerald City": ["#065F46", "#10B981", "#34D399", "#6EE7B7", "#A7F3D0"], # Solid Greens
        "Royal Purple": ["#581C87", "#7C3AED", "#8B5CF6", "#A78BFA", "#C4B5FD"], # Solid Purples
        "Crimson Tide": ["#991B1B", "#DC2626", "#EF4444", "#F87171", "#FCA5A5"]  # Solid Reds
    }
    return themes.get(theme_name, themes["Neon Cyber"])

def apply_chart_theme(fig, x_axis_title="Date Range"):
    """
    Applies the professional layout to charts.
    Ensures labels/legends are readable in both Dark and Light modes.
    """
    dark = st.session_state["dark_mode"]
    # Dynamic text color based on mode
    text_col = "#ffffff" if dark else "#1e293b"
    # Subtle grid lines
    grid_col = "rgba(255, 255, 255, 0.1)" if dark else "rgba(0, 0, 0, 0.05)"
    
    fig.update_layout(
        font=dict(family="Inter", size=12, color=text_col),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=30, b=10, l=10, r=10),
        xaxis=dict(showgrid=False, linecolor=grid_col, tickfont=dict(color=text_col), title=x_axis_title),
        yaxis=dict(showgrid=True, gridcolor=grid_col, linecolor=grid_col, tickfont=dict(color=text_col), 
                   # Ensure exact values for Y-axis (Production/Volume)
                   tickformat=',.3f', title="Production Volume (m³)"), 
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color=text_col)),
        hovermode="x unified"
    )
    
    # Force tooltip to show Plant Name instead of just date or index
    # We update traces to look for customdata or specific text
    fig.update_traces(
        hovertemplate="<b>%{x}</b><br>Value: %{y:,.3f} m³<br>Plant: %{text}<extra></extra>" if 'text' in fig.data[0] else None
    )
    return fig

# ========================================
# 7. MAIN APPLICATION LOGIC
# ========================================

# LOGIN SCREEN
if not st.session_state.get("logged_in", False):
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<div style='height: 100px;'></div>", unsafe_allow_html=True)
        # Dynamic Card for Login
        st.markdown(f"""
        <div style="background:{'#1e293b' if st.session_state.get('dark_mode') else 'white'}; padding:40px; border-radius:20px; box-shadow:0 20px 40px -10px rgba(0,0,0,0.2); text-align:center; border:1px solid #334155;">
            <h1 style="color:{'#f8fafc' if st.session_state.get('dark_mode') else '#0f172a'}; margin-bottom:0;">KBRC DASHBOARD</h1>
            <p style="color:#64748b; font-size:0.9rem; letter-spacing:1px; margin-bottom:30px;">SECURE LOGIN</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Access Dashboard", type="primary", use_container_width=True):
                if check_credentials(u, p):
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = u
                    st.rerun()
                else: st.error("Access Denied")
    st.stop()

# SIDEBAR CONFIGURATION
user = st.session_state["username"]
st.sidebar.markdown(f"""
<div style="padding:20px; border-radius:12px; border:1px solid #e2e8f0; margin-bottom:20px; background-color: {'#1e293b' if st.session_state['dark_mode'] else '#ffffff'};">
    <div style="color:#64748b; font-size:0.8rem; font-weight:600; text-transform:uppercase;">{get_greeting()}</div>
    <div style="color:{'#f8fafc' if st.session_state['dark_mode'] else '#0f172a'}; font-size:1.4rem; font-weight:800; margin-top:4px;">{user.title()}</div>
    <div style="margin-top:10px; display:flex; align-items:center;">
        <span style="height:10px; width:10px; background-color:#10b981; border-radius:50%; margin-right:8px; display:inline-block;"></span>
        <span style="color:#10b981; font-size:0.8rem; font-weight:600;">System Active</span>
    </div>
</div>
""", unsafe_allow_html=True)

menu = ["Analytics", "Upload New Data", "Historical Archives", "Data Management"]
if user == "manager": menu.append("Audit Logs")
mode = st.sidebar.radio("Navigation", menu)

st.sidebar.markdown("---")

# --- MANAGER ONLY: FORECAST SETTING ---
if user == "manager":
    with st.sidebar.expander("🎯 Manager Forecast Controls"):
        f_year = st.selectbox("Forecast Year", [datetime.now().year, datetime.now().year + 1])
        f_month = st.selectbox("Forecast Month", ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], index=datetime.now().month - 1)
        f_target = st.number_input("Monthly Target (m³)", min_value=0.0, step=100.0)
        if st.button("Save Forecast"):
            save_forecast(f_year, f_month, f_target)
            st.success(f"Target saved for {f_month} {f_year}")
            st.rerun()

st.sidebar.markdown("---")

# DARK MODE TOGGLE
is_dark = st.sidebar.toggle("🌙 Dark Mode", value=st.session_state["dark_mode"])
if is_dark != st.session_state["dark_mode"]:
    st.session_state["dark_mode"] = is_dark
    st.rerun()

# THEME SELECTOR
theme_sel = st.sidebar.selectbox("Chart Theme", 
                                 ["Neon Cyber", "Executive Blue", "Emerald City", "Royal Purple", "Crimson Tide"],
                                 index=["Neon Cyber", "Executive Blue", "Emerald City", "Royal Purple", "Crimson Tide"].index(st.session_state.get("theme", "Neon Cyber")))
if theme_sel != st.session_state.get("theme"):
    st.session_state["theme"] = theme_sel
    st.rerun()

current_theme_colors = get_theme_colors(st.session_state.get("theme", "Neon Cyber"))
alert_threshold = st.sidebar.number_input("Alert Threshold (m³)", 50.0, step=10.0)

if st.sidebar.button("Logout"):
    log_event(user, "Logout")
    st.session_state.clear()
    st.rerun()

# ========================================
# MODULE 1: EXECUTIVE ANALYTICS
# ========================================
if mode == "Analytics":
    st.title("Executive Analytics")
    
    saved = list_saved_dates()
    if len(saved) < 2:
        st.warning("Insufficient data. Please upload at least 2 days of production records.")
        st.stop()
        
    # DATE FILTERING
    c1, c2 = st.columns(2)
    with c1: start_d = st.date_input("Start Date", value=datetime.today() - timedelta(days=30))
    with c2: end_d = st.date_input("End Date", value=datetime.today())
    
    # DATA LOADING
    frames = []
    for d in saved:
        try:
            df = load_saved(d)
            df['Date'] = pd.to_datetime(df['Date'])
            df = df[~df['Plant'].astype(str).str.upper().str.contains("TOTAL")] 
            frames.append(df)
        except: continue
        
    if not frames: st.stop()
    full_df = pd.concat(frames, ignore_index=True)
    
    # STRICT FILTERING (Removes unwanted dates from Oct if not selected)
    mask = (full_df['Date'] >= pd.to_datetime(start_d)) & (full_df['Date'] <= pd.to_datetime(end_d))
    df_filtered = full_df[mask].copy().sort_values('Date')
    
    if df_filtered.empty:
        st.info("No data available for the selected date range.")
        st.stop()
        
    df_filtered = safe_numeric(df_filtered)
    # Deduplicate to prevent math errors
    df_filtered = df_filtered.drop_duplicates(subset=['Date', 'Plant'], keep='last')

    # --- TOP 3 LEADERBOARD CALCULATION ---
    # Top 3 by Sum
    top_sum = df_filtered.groupby("Plant")["Production for the Day"].sum().sort_values(ascending=False).head(3)
    # Top 3 by Average
    top_avg = df_filtered.groupby("Plant")["Production for the Day"].mean().sort_values(ascending=False).head(3)

    # --- FORECAST LOGIC (New Feature) ---
    # Determine the "Dominant" month in selection to pick which forecast to show
    dom_month_idx = df_filtered['Date'].dt.month.mode()[0]
    dom_year_idx = df_filtered['Date'].dt.year.mode()[0]
    month_name = date(1900, dom_month_idx, 1).strftime('%B')
    
    monthly_target = get_forecast(dom_year_idx, month_name)
    total_vol = df_filtered['Production for the Day'].sum()
    avg_daily = df_filtered.groupby('Date')['Production for the Day'].sum().mean()
    
    # Calculate Variance
    variance = total_vol - monthly_target
    var_color = "#10b981" if variance >= 0 else "#ef4444"
    var_icon = "▲" if variance >= 0 else "▼"
    
    # ------------------ HERO SECTION ------------------
    st.markdown(f"""
    <div class="hero-banner">
        <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:20px; text-align:center;">
            <div>
                <div style="font-size:0.9rem; opacity:0.8; text-transform:uppercase;">Daily Average</div>
                <div style="font-size:3rem; font-weight:800;">{avg_daily:,.0f} m³</div>
            </div>
            <div style="border-left:1px solid rgba(255,255,255,0.2); border-right:1px solid rgba(255,255,255,0.2);">
                <div style="font-size:0.9rem; opacity:0.8; text-transform:uppercase;">Forecast ({month_name})</div>
                <div style="font-size:3rem; font-weight:800;">{monthly_target:,.0f} m³</div>
            </div>
            <div>
                <div style="font-size:0.9rem; opacity:0.8; text-transform:uppercase;">Forecast Variance</div>
                <div style="font-size:3rem; font-weight:800; color:{var_color};">{var_icon} {abs(variance):,.0f} m³</div>
                <div style="font-size:0.8rem; opacity:0.8;">Actual: {total_vol:,.0f} m³</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ------------------ LEADERBOARDS (New Feature) ------------------
    st.markdown("### 🏆 Top Performance Leaders")
    col_l1, col_l2 = st.columns(2)
    
    with col_l1:
        st.markdown("**Highest Total Production**")
        for i, (plant, val) in enumerate(top_sum.items()):
            color = current_theme_colors[i % len(current_theme_colors)]
            st.markdown(f"""
            <div class="leaderboard-box" style="border-left-color: {color};">
                <div>
                    <span class="lb-rank" style="color:{color}">#{i+1}</span>
                    <span class="lb-name">{plant}</span>
                </div>
                <span class="lb-val">{format_m3(val)}</span>
            </div>
            """, unsafe_allow_html=True)
            
    with col_l2:
        st.markdown("**Highest Average Efficiency**")
        for i, (plant, val) in enumerate(top_avg.items()):
            color = current_theme_colors[-(i+1) % len(current_theme_colors)] # Reverse colors for distinction
            st.markdown(f"""
            <div class="leaderboard-box" style="border-left-color: {color};">
                <div>
                    <span class="lb-rank" style="color:{color}">#{i+1}</span>
                    <span class="lb-name">{plant}</span>
                </div>
                <span class="lb-val">{format_m3(val)}/day</span>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # TABS FOR WEEKLY / MONTHLY SPLIT
    tab_week, tab_month = st.tabs(["📅 Weekly Performance", "📆 Monthly Performance"])

    # --- WEEKLY ANALYSIS ---
    with tab_week:
        st.subheader("Weekly Analytics")
        # Aggregation Logic
        week_agg = df_filtered.groupby(['Plant', pd.Grouper(key='Date', freq='W-MON')]).agg({
            'Production for the Day': ['sum', 'mean'],
            'Accumulative Production': 'max'
        }).reset_index()
        week_agg.columns = ['Plant', 'Date', 'Total Production', 'Avg Production', 'Accumulative']
        
        # Format Date Label
        week_agg['Week Label'] = week_agg['Date'].dt.strftime('Wk %W (%d %b)')
        week_agg['FullRange'] = week_agg['Date'].apply(lambda x: f"Week ending {x.strftime('%Y-%m-%d')}")
        
        # Post-Aggregation Filter (Double Check)
        week_agg = week_agg[(week_agg['Date'] >= pd.to_datetime(start_d)) & (week_agg['Date'] <= pd.to_datetime(end_d))]

        c_w1, c_w2 = st.columns(2)
        with c_w1:
            fig = px.bar(week_agg, x='Week Label', y='Total Production', color='Plant', 
                         title="Weekly Total Production (Sum)", barmode='group',
                         text='Plant', # For tooltip identification
                         color_discrete_sequence=current_theme_colors)
            st.plotly_chart(apply_chart_theme(fig), use_container_width=True)
            
        with c_w2:
            fig = px.bar(week_agg, x='Week Label', y='Avg Production', color='Plant', 
                         title="Weekly Average Production (Mean)", barmode='group',
                         text='Plant',
                         color_discrete_sequence=current_theme_colors)
            st.plotly_chart(apply_chart_theme(fig), use_container_width=True)
            
        st.markdown("#### Weekly Accumulative Trend")
        fig_acc = px.line(week_agg, x='Week Label', y='Accumulative', color='Plant', markers=True,
                          text='Plant',
                          color_discrete_sequence=current_theme_colors)
        st.plotly_chart(apply_chart_theme(fig_acc), use_container_width=True)

    # --- MONTHLY ANALYSIS ---
    with tab_month:
        st.subheader("Monthly Analytics")
        
        # 1. Forecast Trajectory Chart (Replaces complex graph)
        # Calculate daily cumulative sum for the filtered period
        daily_cum = df_filtered.groupby('Date')['Production for the Day'].sum().cumsum().reset_index()
        daily_cum.columns = ['Date', 'Actual Cumulative']
        
        # Create Target Line (Linear projection for the month)
        days_in_view = (df_filtered['Date'].max() - df_filtered['Date'].min()).days + 1
        daily_target_rate = monthly_target / 30 # Approx daily target
        daily_cum['Target Trend'] = [daily_target_rate * (i+1) for i in range(len(daily_cum))]
        
        fig_traj = go.Figure()
        fig_traj.add_trace(go.Scatter(x=daily_cum['Date'], y=daily_cum['Actual Cumulative'], mode='lines+markers', name='Actual Production', line=dict(color='#10b981', width=4)))
        fig_traj.add_trace(go.Scatter(x=daily_cum['Date'], y=daily_cum['Target Trend'], mode='lines', name='Target Trajectory', line=dict(color='#ef4444', dash='dot')))
        
        fig_traj.update_layout(title=f"Monthly Trajectory: Actual vs Forecast ({month_name})")
        st.plotly_chart(apply_chart_theme(fig_traj), use_container_width=True)
        
        # Standard Monthly Charts
        month_agg = df_filtered.groupby(['Plant', pd.Grouper(key='Date', freq='M')]).agg({
            'Production for the Day': ['sum', 'mean'],
            'Accumulative Production': 'max'
        }).reset_index()
        month_agg.columns = ['Plant', 'Date', 'Total Production', 'Avg Production', 'Accumulative']
        month_agg['Month Label'] = month_agg['Date'].dt.strftime('%B %Y')
        
        month_agg = month_agg[(month_agg['Date'] >= pd.to_datetime(start_d)) & (month_agg['Date'] <= pd.to_datetime(end_d))]

        c_m1, c_m2 = st.columns(2)
        with c_m1:
            fig = px.bar(month_agg, x='Month Label', y='Total Production', color='Plant', 
                         title="Monthly Total Production (Sum)", barmode='group',
                         text='Plant',
                         color_discrete_sequence=current_theme_colors)
            st.plotly_chart(apply_chart_theme(fig), use_container_width=True)
            
        with c_m2:
            fig = px.bar(month_agg, x='Month Label', y='Avg Production', color='Plant', 
                         title="Monthly Average Production (Mean)", barmode='group',
                         text='Plant',
                         color_discrete_sequence=current_theme_colors)
            st.plotly_chart(apply_chart_theme(fig), use_container_width=True)
            
        st.markdown("#### Monthly Accumulative Trend")
        fig_acc_m = px.line(month_agg, x='Month Label', y='Accumulative', color='Plant', markers=True,
                            text='Plant',
                            color_discrete_sequence=current_theme_colors)
        st.plotly_chart(apply_chart_theme(fig_acc_m), use_container_width=True)

# ========================================
# MODULE 2: UPLOAD DATA
# ========================================
elif mode == "Upload New Data":
    st.title("Daily Production Entry")
    c1, c2 = st.columns([2, 1])
    with c1: uploaded = st.file_uploader("Upload Excel File", type=["xlsx"])
    with c2:
        if "up_date" not in st.session_state: st.session_state.up_date = datetime.today()
        sel_date = st.date_input("Production Date", value=st.session_state.up_date)
        st.session_state.up_date = sel_date
        
    if uploaded:
        try:
            df = pd.read_excel(uploaded)
            df.columns = df.columns.str.strip()
            missing = [c for c in REQUIRED_COLS if c not in df.columns]
            if missing: st.error(f"Missing Columns: {missing}")
            else:
                st.dataframe(df.head(), use_container_width=True)
                if st.button("✅ Approve & Save", type="primary"):
                    df_clean = df.copy()
                    df_clean['Date'] = sel_date.strftime("%Y-%m-%d")
                    save_path = save_csv(df_clean, sel_date, overwrite=True)
                    log_event(user, f"Uploaded {sel_date}")
                    attempt_git_push(save_path, f"Add {sel_date}")
                    
                    # Show Success
                    df_disp = df_clean[~df_clean["Plant"].astype(str).str.upper().str.contains("TOTAL")]
                    df_disp = safe_numeric(df_disp)
                    tot = df_disp["Production for the Day"].sum()
                    st.success(f"Saved! Total: {format_m3(tot)}")
        except Exception as e: st.error(f"Error: {e}")

# ========================================
# MODULE 3: DATA MANAGEMENT
# ========================================
elif mode == "Data Management":
    st.title("Database Management")
    files = list_saved_dates()
    if not files: st.info("No records.")
    else:
        for f in files:
            with st.expander(f"📂 {f}", expanded=False):
                c1, c2 = st.columns(2)
                with c1:
                    df = load_saved(f)
                    xl = generate_excel_report(df, f)
                    st.download_button("Download", xl, f"{f}.xlsx", key=f"d_{f}")
                with c2:
                    if st.button("Delete", key=f"del_{f}", type="primary"):
                        if delete_saved(f):
                            log_event(user, f"Deleted {f}")
                            st.rerun()

# ========================================
# MODULE 4: HISTORICAL ARCHIVES
# ========================================
elif mode == "Historical Archives":
    st.title("Historical Data")
    files = list_saved_dates()
    if not files: st.stop()
    if "hist_d" not in st.session_state: st.session_state.hist_d = datetime.strptime(files[0], "%Y-%m-%d").date()
    sel_d = st.date_input("Select Date", value=st.session_state.hist_d)
    st.session_state.hist_d = sel_d
    d_str = sel_d.strftime("%Y-%m-%d")
    
    if d_str in files:
        df = load_saved(d_str)
        df = df[~df["Plant"].astype(str).str.upper().str.contains("TOTAL")]
        df = safe_numeric(df)
        tot = df["Production for the Day"].sum()
        
        st.markdown(f"""
        <div style="background:{'#1e293b' if st.session_state['dark_mode'] else '#1e3a8a'}; color:white; padding:30px; border-radius:12px; margin-bottom:20px;">
            <h2 style="margin:0; color:white !important;">{sel_d.strftime('%A, %B %d, %Y')}</h2>
            <div style="font-size:3rem; font-weight:800;">{format_m3(tot)}</div>
        </div>
        """, unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True)
        
        st.markdown("### 📊 Daily Breakdown")
        # Added New Charts as requested
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Production Share**")
            fig = px.pie(df, names='Plant', values='Production for the Day', color_discrete_sequence=current_theme_colors)
            st.plotly_chart(apply_chart_theme(fig), use_container_width=True)
        with c2:
            st.markdown("**Production Volume**")
            fig = px.bar(df, x='Plant', y='Production for the Day', color='Plant', text='Plant', color_discrete_sequence=current_theme_colors)
            st.plotly_chart(apply_chart_theme(fig), use_container_width=True)
            
        st.markdown("### 📈 Accumulative Analysis")
        # Accumulative Charts for the specific day
        c3, c4 = st.columns(2)
        with c3:
            st.markdown("**Accumulative by Plant**")
            fig_acc_bar = px.bar(df, x='Plant', y='Accumulative Production', color='Plant', text='Plant', color_discrete_sequence=current_theme_colors)
            st.plotly_chart(apply_chart_theme(fig_acc_bar), use_container_width=True)
        with c4:
            st.markdown("**Accumulative Share**")
            fig_acc_pie = px.pie(df, names='Plant', values='Accumulative Production', color_discrete_sequence=current_theme_colors)
            st.plotly_chart(apply_chart_theme(fig_acc_pie), use_container_width=True)

# ========================================
# MODULE 5: AUDIT LOGS (MANAGER ONLY)
# ========================================
elif mode == "Audit Logs":
    if user != "manager": st.error("Access Restricted"); st.stop()
    st.title("Security Audit Logs")
    
    # Filter Controls
    log_date = st.date_input("Filter by Date", value=datetime.today())
    
    logs = get_logs()
    if not logs.empty:
        logs['Timestamp'] = pd.to_datetime(logs['Timestamp'])
        # Filter Logic
        start_ts = pd.to_datetime(log_date)
        end_ts = start_ts + timedelta(days=1)
        daily_logs = logs[(logs['Timestamp'] >= start_ts) & (logs['Timestamp'] < end_ts)].sort_values('Timestamp', ascending=False)
        
        st.markdown(f"**Showing logs for: {log_date.strftime('%Y-%m-%d')}**")
        st.dataframe(daily_logs, use_container_width=True, height=500)
        st.download_button("Export CSV", daily_logs.to_csv(index=False).encode(), "logs.csv", "text/csv")
    else:
        st.info("No logs found.")

# ========================================
# FOOTER
# ========================================
st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style="font-size:0.75rem; color:#64748b; line-height:1.4;">
    <strong>Eng. Ashwin Joseph Mathew</strong><br>
    Head of IT<br>
    <a href="mailto:Ashwin.IT@kbrc.com.kw" style="color:#3b82f6; text-decoration:none;">Ashwin.IT@kbrc.com.kw</a>
</div>
""", unsafe_allow_html=True)
