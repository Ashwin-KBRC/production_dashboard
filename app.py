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
# 2. SESSION STATE SETUP
# ========================================
if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = False
if "theme" not in st.session_state:
    st.session_state["theme"] = "Executive Blue"

# ========================================
# 3. PROFESSIONAL STYLING (CSS)
# ========================================
def inject_css():
    if st.session_state["dark_mode"]:
        bg_color = "#0f172a"
        text_color = "#f8fafc"
        card_bg = "#1e293b"
        border_color = "#334155"
        sidebar_bg = "#111827"
        secondary_text = "#94a3b8"
    else:
        bg_color = "#f8fafc"
        text_color = "#1e293b"
        card_bg = "#ffffff"
        border_color = "#e2e8f0"
        sidebar_bg = "#ffffff"
        secondary_text = "#64748b"

    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
        
        html, body, [class*="css"], .stApp {{
            font-family: 'Inter', sans-serif;
            color: {text_color};
            background-color: {bg_color};
        }}

        /* HIDE BRANDING */
        footer {{visibility: hidden !important;}}
        #MainMenu {{visibility: hidden;}}
        header {{visibility: hidden !important;}}
        .stAppDeployButton {{display: none !important;}}
        
        /* SIDEBAR */
        [data-testid="stSidebar"] {{
            background-color: {sidebar_bg};
            border-right: 1px solid {border_color};
        }}
        [data-testid="stSidebarCollapseButton"] {{display: none !important;}}

        /* CARDS */
        .metric-card {{
            background: {card_bg};
            border: 1px solid {border_color};
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            transition: transform 0.2s;
            color: {text_color};
        }}
        .metric-card:hover {{
            transform: translateY(-4px);
            border-color: #3b82f6;
        }}
        
        /* HERO BANNER */
        .hero-banner {{
            background: linear-gradient(135deg, #1e3a8a 0%, #172554 100%);
            color: white;
            padding: 30px;
            border-radius: 16px;
            margin-bottom: 30px;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        }}
        
        /* TABS */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 10px;
            background-color: transparent;
        }}
        .stTabs [data-baseweb="tab"] {{
            border-radius: 6px;
            color: {secondary_text};
            font-weight: 600;
        }}
        .stTabs [aria-selected="true"] {{
            background-color: {card_bg};
            border: 1px solid {border_color};
            border-bottom: 2px solid #3b82f6;
            color: #3b82f6;
        }}

        /* LEADERBOARD BOXES */
        .leaderboard-box {{
            background-color: {card_bg};
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 10px;
            border-left-width: 5px;
            border-left-style: solid;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .leaderboard-rank {{ font-weight: 800; font-size: 1.1em; opacity: 0.8; margin-right: 10px; }}
        .leaderboard-val {{ font-weight: 700; font-size: 1.1em; }}

        /* HEADERS */
        h1, h2, h3, h4, h5, h6 {{ color: {text_color} !important; font-weight: 700; }}
        
        /* DARK MODE INPUT FIXES */
        .stTextInput input, .stDateInput input, .stNumberInput input {{
            color: {text_color} !important;
        }}
    </style>
    """, unsafe_allow_html=True)

inject_css()

# ========================================
# 4. DATA SETUP & UTILS
# ========================================
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = DATA_DIR / "access_logs.csv"
FORECAST_FILE = DATA_DIR / "monthly_targets.csv"
REQUIRED_COLS = ["Plant", "Production for the Day", "Accumulative Production"]

# AUTH SECRETS (Defaulting for safety)
SECRETS = {}
try: SECRETS = dict(st.secrets)
except: SECRETS = {}

_default_users = {
    "admin": hashlib.sha256("kbrc123".encode()).hexdigest(),
    "manager": hashlib.sha256("sjk@2025".encode()).hexdigest(),
    "production": hashlib.sha256("Production@123".encode()).hexdigest()
}
USERS = _default_users.copy()

# TIME UTILS
def get_kuwait_time():
    return datetime.now(timezone.utc) + timedelta(hours=3)

def get_greeting():
    h = get_kuwait_time().hour
    if h < 12: return "Good Morning"
    elif 12 <= h < 18: return "Good Afternoon"
    else: return "Good Evening"

def format_m3(value):
    return f"{value:,.3f} m³"

# LOGGING
def init_logs():
    if not LOG_FILE.exists():
        with open(LOG_FILE, 'w', newline='') as f:
            csv.writer(f).writerow(["Timestamp", "User", "Event"])

def log_event(username: str, event: str):
    init_logs()
    try:
        ts = get_kuwait_time().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, 'a', newline='') as f:
            csv.writer(f).writerow([ts, username, event])
    except: pass

def get_logs() -> pd.DataFrame:
    init_logs()
    try: return pd.read_csv(LOG_FILE)
    except: return pd.DataFrame(columns=["Timestamp", "User", "Event"])

# FORECAST MANAGEMENT
def init_forecasts():
    if not FORECAST_FILE.exists():
        with open(FORECAST_FILE, 'w', newline='') as f:
            csv.writer(f).writerow(["Year", "Month", "Target"])

def save_forecast_from_upload(year: int, month: str, target: float):
    """Saves the uploaded forecast target to the CSV database."""
    init_forecasts()
    try:
        df = pd.read_csv(FORECAST_FILE)
    except:
        df = pd.DataFrame(columns=["Year", "Month", "Target"])
    
    # Remove existing entry for this month/year to overwrite
    df = df[~((df['Year'] == year) & (df['Month'] == month))]
    
    new_entry = pd.DataFrame([{"Year": year, "Month": month, "Target": target}])
    df = pd.concat([df, new_entry], ignore_index=True)
    df.to_csv(FORECAST_FILE, index=False)

def get_forecast(year: int, month: str) -> float:
    """Retrieves target for specific month/year."""
    init_forecasts()
    try:
        df = pd.read_csv(FORECAST_FILE)
        row = df[(df['Year'] == int(year)) & (df['Month'] == month)]
        if not row.empty:
            return float(row.iloc[0]['Target'])
    except:
        pass
    return 0.0

# AUTH
def check_credentials(username: str, password: str) -> bool:
    if not username: return False
    user = username.strip()
    if user in USERS:
        v = hashlib.sha256(password.encode()).hexdigest() == USERS[user]
        log_event(user, "Login Success" if v else "Login Failed")
        return v
    return False

# FILE OPERATIONS
def save_csv(df: pd.DataFrame, date_obj: date, overwrite: bool = False) -> Path:
    fname = f"{date_obj.strftime('%Y-%m-%d')}.csv"
    p = DATA_DIR / fname
    if p.exists() and not overwrite: raise FileExistsError(f"{fname} exists.")
    df.to_csv(p, index=False, float_format="%.3f")
    return p

def list_saved_dates() -> List[str]:
    # Exclude system files
    return sorted([p.name.replace(".csv", "") for p in DATA_DIR.glob("*.csv") 
                   if "access_logs" not in p.name and "monthly_targets" not in p.name], reverse=True)

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
    output.seek(0)
    return output

# ========================================
# 5. CHARTING ENGINE
# ========================================
def get_theme_colors(theme_name):
    themes = {
        "Neon Cyber": ["#F72585", "#7209B7", "#3A0CA3", "#4361EE", "#4CC9F0"],
        "Executive Blue": ["#1E40AF", "#3B82F6", "#60A5FA", "#93C5FD", "#BFDBFE"],
        "Emerald City": ["#065F46", "#10B981", "#34D399", "#6EE7B7", "#A7F3D0"],
        "Royal Purple": ["#581C87", "#7C3AED", "#8B5CF6", "#A78BFA", "#C4B5FD"],
        "Crimson Tide": ["#991B1B", "#DC2626", "#EF4444", "#F87171", "#FCA5A5"]
    }
    return themes.get(theme_name, themes["Executive Blue"])

def apply_chart_theme(fig, x_title=None, y_title=None):
    """
    Applies professional styling to all charts.
    Ensures labels/legends are readable in dark/light mode.
    """
    dark = st.session_state["dark_mode"]
    text_col = "#ffffff" if dark else "#1e293b"
    grid_col = "rgba(255, 255, 255, 0.1)" if dark else "rgba(0, 0, 0, 0.05)"
    
    fig.update_layout(
        font=dict(family="Inter", size=12, color=text_col),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=30, b=10, l=10, r=10),
        xaxis=dict(showgrid=False, linecolor=grid_col, tickfont=dict(color=text_col), title=x_title),
        yaxis=dict(showgrid=True, gridcolor=grid_col, linecolor=grid_col, tickfont=dict(color=text_col), title=y_title, tickformat=',.0f'),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color=text_col)),
        hovermode="x unified"
    )
    return fig

# ========================================
# 6. MAIN APP LOGIC
# ========================================

# --- LOGIN SCREEN ---
if not st.session_state.get("logged_in", False):
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<div style='height: 100px;'></div>", unsafe_allow_html=True)
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

# --- SIDEBAR CONFIG ---
user = st.session_state["username"]
text_col = "#f8fafc" if st.session_state["dark_mode"] else "#0f172a"

st.sidebar.markdown(f"""
<div style="padding:20px; border-radius:12px; border:1px solid #e2e8f0; margin-bottom:20px; background-color: {'#1e293b' if st.session_state['dark_mode'] else '#ffffff'};">
    <div style="color:#64748b; font-size:0.8rem; font-weight:600; text-transform:uppercase;">{get_greeting()}</div>
    <div style="color:{text_col}; font-size:1.4rem; font-weight:800; margin-top:4px;">{user.title()}</div>
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

# --- FORECAST UPLOAD SECTION (Manager Only) ---
if user == "manager":
    st.sidebar.markdown("### 🎯 Monthly Targets")
    with st.sidebar.expander("Upload Forecast", expanded=False):
        f_year = st.selectbox("Year", [datetime.now().year, datetime.now().year + 1])
        f_month = st.selectbox("Month", ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], index=datetime.now().month - 1)
        
        # User requested to upload an excel file for forecast
        f_file = st.file_uploader("Upload Forecast File (Excel)", type=["xlsx", "xls"])
        
        if f_file and st.button("Save Forecast Target"):
            try:
                # Read the excel file to get the value
                f_df = pd.read_excel(f_file)
                # Assuming the value is in the first row, first column or a column named "Target"
                # We'll try to look for a numeric value
                val = 0.0
                if not f_df.empty:
                    # simplistic extraction: first numeric cell found
                    for col in f_df.columns:
                        if pd.to_numeric(f_df[col], errors='coerce').notnull().all():
                            val = float(f_df[col].iloc[0])
                            break
                
                if val > 0:
                    save_forecast_from_upload(f_year, f_month, val)
                    st.sidebar.success(f"Target of {format_m3(val)} saved for {f_month} {f_year}")
                else:
                    st.sidebar.error("Could not find a valid target number in file.")
            except Exception as e:
                st.sidebar.error(f"Error reading file: {e}")

st.sidebar.markdown("---")

# --- SETTINGS ---
is_dark = st.sidebar.toggle("🌙 Dark Mode", value=st.session_state["dark_mode"])
if is_dark != st.session_state["dark_mode"]:
    st.session_state["dark_mode"] = is_dark
    st.rerun()

theme_list = ["Executive Blue", "Neon Cyber", "Emerald City", "Royal Purple", "Crimson Tide"]
theme_sel = st.sidebar.selectbox("Theme", theme_list, index=0)
if theme_sel != st.session_state.get("theme"):
    st.session_state["theme"] = theme_sel
    st.rerun()

current_theme_colors = get_theme_colors(st.session_state.get("theme", "Executive Blue"))

if st.sidebar.button("Logout"):
    log_event(user, "Logout")
    st.session_state.clear()
    st.rerun()

# ========================================
# MODULE: EXECUTIVE ANALYTICS
# ========================================
if mode == "Analytics":
    st.title("Executive Analytics")
    
    saved = list_saved_dates()
    if len(saved) < 2:
        st.warning("Insufficient data. Please upload at least 2 days of production records.")
        st.stop()
    
    # --- DATE CONTROLS ---
    c1, c2 = st.columns(2)
    # Bounds
    try:
        min_date = datetime.strptime(saved[-1], "%Y-%m-%d").date()
        max_date = datetime.strptime(saved[0], "%Y-%m-%d").date()
    except:
        min_date = datetime.today().date()
        max_date = datetime.today().date()

    if "start_d" not in st.session_state: st.session_state.start_d = max(min_date, max_date - timedelta(days=30))
    if "end_d" not in st.session_state: st.session_state.end_d = max_date

    with c1: 
        start_d = st.date_input("Start Date", value=st.session_state.start_d, min_value=min_date, max_value=max_date)
        st.session_state.start_d = start_d
    with c2: 
        end_d = st.date_input("End Date", value=st.session_state.end_d, min_value=min_date, max_value=max_date)
        st.session_state.end_d = end_d

    # --- DATA ENGINE ---
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
    
    mask = (full_df['Date'] >= pd.to_datetime(start_d)) & (full_df['Date'] <= pd.to_datetime(end_d))
    df_filtered = full_df[mask].copy().sort_values('Date')
    
    if df_filtered.empty: st.info("No data in range."); st.stop()
    
    df_filtered = safe_numeric(df_filtered)
    df_filtered = df_filtered.drop_duplicates(subset=['Date', 'Plant'], keep='last')

    # --- METRICS CALCULATIONS ---
    total_vol = df_filtered['Production for the Day'].sum()
    avg_daily = df_filtered.groupby('Date')['Production for the Day'].sum().mean()
    
    # Forecast Logic: Get forecast for the START date's month (or dominant month)
    forecast_month = start_d.strftime("%B")
    forecast_year = start_d.year
    monthly_target_val = get_forecast(forecast_year, forecast_month)
    
    # If range is less than a month, prorate the target for fair comparison? 
    # Or just show full month target vs full month actual projection?
    # User asked for "Forecast for the month".
    
    # Calculate Variance
    variance = total_vol - monthly_target_val
    var_color = "#10b981" if variance >= 0 else "#ef4444" # Green if above, Red if below
    var_symbol = "+" if variance >= 0 else ""
    
    # Expected Average (Target / Days in Month)
    # Simple logic: 30 days
    expected_daily_avg = monthly_target_val / 30 if monthly_target_val > 0 else 0

    # --- HERO SECTION (UPDATED LAYOUT) ---
    st.markdown(f"""
    <div class="hero-banner">
        <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:20px; text-align:center;">
            <!-- BOX 1: TOTAL PRODUCTION (BOLD) -->
            <div>
                <div style="font-size:0.9rem; opacity:0.8; text-transform:uppercase;">Total Production</div>
                <div style="font-size:3.5rem; font-weight:800; color: white;">{total_vol:,.0f}</div>
                <div style="font-size:0.8rem; opacity:0.8;">m³</div>
            </div>
            
            <!-- BOX 2: FORECAST & VARIANCE -->
            <div style="border-left:1px solid rgba(255,255,255,0.2); border-right:1px solid rgba(255,255,255,0.2);">
                <div style="font-size:0.9rem; opacity:0.8; text-transform:uppercase;">Forecast ({forecast_month})</div>
                <div style="font-size:3rem; font-weight:800; color:{var_color};">{monthly_target_val:,.0f}</div>
                <div style="font-size:1rem; font-weight:600; margin-top:5px;">
                    Var: <span style="color:{var_color}">{var_symbol}{variance:,.0f} m³</span>
                </div>
            </div>
            
            <!-- BOX 3: AVERAGES -->
            <div>
                <div style="font-size:0.9rem; opacity:0.8; text-transform:uppercase;">Expected Avg / Actual Avg</div>
                <div style="font-size:2.5rem; font-weight:800; margin-bottom:5px;">{expected_daily_avg:,.0f} <span style="font-size:1.5rem; opacity:0.6;">/</span> {avg_daily:,.0f}</div>
                <div style="font-size:0.8rem; font-weight:bold; color:#fbbf24;">Daily Efficiency Gap: {(avg_daily - expected_daily_avg):,.0f} m³</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- TOP 3 BOXES (PROFESSIONAL & COLORED) ---
    st.markdown("### 🏆 Top 3 Performance Leaders")
    
    # Logic for Top 3
    plant_grp = df_filtered.groupby("Plant")["Production for the Day"]
    top_total = plant_grp.sum().sort_values(ascending=False).head(3)
    top_avg = plant_grp.mean().sort_values(ascending=False).head(3)
    
    c_lead1, c_lead2 = st.columns(2)
    
    with c_lead1:
        st.markdown("**Top 3 Plants (Highest Total Production)**")
        for i, (p_name, p_val) in enumerate(top_total.items()):
            # Cycle through theme colors
            border_col = current_theme_colors[i % len(current_theme_colors)]
            st.markdown(f"""
            <div class="leaderboard-box" style="border-left-color: {border_col};">
                <div>
                    <span class="leaderboard-rank" style="color:{border_col}">#{i+1}</span>
                    <span style="font-weight:600;">{p_name}</span>
                </div>
                <span class="leaderboard-val">{format_m3(p_val)}</span>
            </div>
            """, unsafe_allow_html=True)
            
    with c_lead2:
        st.markdown("**Top 3 Plants (Highest Average Production)**")
        for i, (p_name, p_val) in enumerate(top_avg.items()):
            border_col = current_theme_colors[-(i+1)] # Reverse colors for variety
            st.markdown(f"""
            <div class="leaderboard-box" style="border-left-color: {border_col};">
                <div>
                    <span class="leaderboard-rank" style="color:{border_col}">#{i+1}</span>
                    <span style="font-weight:600;">{p_name}</span>
                </div>
                <span class="leaderboard-val">{format_m3(p_val)} / day</span>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # --- PRODUCTION VS EXPECTED GRAPH (BRAND NEW) ---
    st.subheader(f"📈 Production Trajectory vs Forecast ({start_d.strftime('%b %d')} - {end_d.strftime('%b %d')})")
    
    # Prepare Daily Data
    daily_sums = df_filtered.groupby("Date")["Production for the Day"].sum().reset_index()
    daily_sums['Target'] = expected_daily_avg # The flat line target
    
    fig_target = go.Figure()
    # Actual Production (Blue)
    fig_target.add_trace(go.Scatter(
        x=daily_sums['Date'], 
        y=daily_sums['Production for the Day'],
        mode='lines+markers',
        name='Actual Production',
        line=dict(color='#3b82f6', width=3),
        marker=dict(size=8),
        hovertemplate="<b>Date:</b> %{x}<br><b>Actual:</b> %{y:,.3f} m³<extra></extra>"
    ))
    # Expected Production (Red)
    fig_target.add_trace(go.Scatter(
        x=daily_sums['Date'], 
        y=daily_sums['Target'],
        mode='lines',
        name='Expected Target',
        line=dict(color='#ef4444', width=2, dash='dash'),
        hovertemplate="<b>Date:</b> %{x}<br><b>Target:</b> %{y:,.3f} m³<extra></extra>"
    ))
    
    fig_target = apply_chart_theme(fig_target, x_axis_title="Date", y_title="Volume (m³)")
    st.plotly_chart(fig_target, use_container_width=True)

    # --- WEEKLY & MONTHLY TABS ---
    t_week, t_month = st.tabs(["📅 Weekly Performance", "📆 Monthly Performance"])
    
    # 1. WEEKLY
    with t_week:
        # Helper to convert Week Num to Date Range (e.g. Dec 1 - Dec 7)
        # We group by Week Start Date
        df_filtered['Week_Start'] = df_filtered['Date'].apply(lambda x: x - timedelta(days=x.weekday()))
        
        wk_agg = df_filtered.groupby(['Plant', 'Week_Start']).agg({
            'Production for the Day': ['sum', 'mean'],
            'Accumulative Production': 'max'
        }).reset_index()
        wk_agg.columns = ['Plant', 'Week_Start', 'Total', 'Avg', 'Accum']
        
        # Create friendly Label: "Dec 02 - Dec 08"
        wk_agg['Week_Label'] = wk_agg['Week_Start'].apply(lambda d: f"{d.strftime('%b %d')} - {(d + timedelta(days=6)).strftime('%b %d')}")
        
        c_w1, c_w2 = st.columns(2)
        with c_w1:
            st.markdown("**Weekly Total (Sum)**")
            fig = px.bar(wk_agg, x='Week_Label', y='Total', color='Plant', barmode='group',
                         color_discrete_sequence=current_theme_colors,
                         hover_name='Plant')
            # Fix Tooltip to show Plant Name properly
            fig.update_traces(hovertemplate="<b>%{x}</b><br>Plant: %{hovertext}<br>Total: %{y:,.3f} m³<extra></extra>")
            st.plotly_chart(apply_chart_theme(fig, x_axis_title="Week Range"), use_container_width=True)
            
        with c_w2:
            st.markdown("**Weekly Average**")
            fig = px.bar(wk_agg, x='Week_Label', y='Avg', color='Plant', barmode='group',
                         color_discrete_sequence=current_theme_colors,
                         hover_name='Plant')
            fig.update_traces(hovertemplate="<b>%{x}</b><br>Plant: %{hovertext}<br>Avg: %{y:,.3f} m³<extra></extra>")
            st.plotly_chart(apply_chart_theme(fig, x_axis_title="Week Range"), use_container_width=True)
            
        st.markdown("**Weekly Accumulative Trend**")
        fig = px.line(wk_agg, x='Week_Label', y='Accum', color='Plant', markers=True,
                      color_discrete_sequence=current_theme_colors, hover_name='Plant')
        fig.update_traces(hovertemplate="<b>%{x}</b><br>Plant: %{hovertext}<br>Accum: %{y:,.3f} m³<extra></extra>")
        st.plotly_chart(apply_chart_theme(fig, x_axis_title="Week Range"), use_container_width=True)

    # 2. MONTHLY
    with t_month:
        # Simplier Month Chart as requested (Trajectory)
        st.markdown("**Monthly Accumulative Trajectory (By Plant)**")
        # Just plot the accumulative line over time for the filtered period
        fig_traj = px.line(df_filtered, x='Date', y='Accumulative Production', color='Plant',
                           color_discrete_sequence=current_theme_colors, hover_name='Plant')
        fig_traj.update_traces(hovertemplate="<b>%{x}</b><br>Plant: %{hovertext}<br>Accum: %{y:,.3f} m³<extra></extra>")
        st.plotly_chart(apply_chart_theme(fig_traj, x_axis_title="Date"), use_container_width=True)
        
        # Monthly Sum Bars
        mo_agg = df_filtered.groupby(['Plant', pd.Grouper(key='Date', freq='M')])['Production for the Day'].sum().reset_index()
        mo_agg['Month_Label'] = mo_agg['Date'].dt.strftime('%B %Y')
        
        c_m1, c_m2 = st.columns(2)
        with c_m1:
            st.markdown("**Monthly Total Production**")
            fig = px.bar(mo_agg, x='Month_Label', y='Production for the Day', color='Plant', barmode='group',
                         color_discrete_sequence=current_theme_colors, hover_name='Plant')
            fig.update_traces(hovertemplate="<b>%{x}</b><br>Plant: %{hovertext}<br>Total: %{y:,.3f} m³<extra></extra>")
            st.plotly_chart(apply_chart_theme(fig, x_axis_title="Month"), use_container_width=True)

# ========================================
# MODULE 2: UPLOAD
# ========================================
elif mode == "Upload New Data":
    st.title("Daily Production Entry")
    
    c1, c2 = st.columns([2, 1])
    with c1: uploaded = st.file_uploader("Upload Excel File (Daily Data)", type=["xlsx"])
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
    st.title("Historical Data Viewer")
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
        
        # --- NEW HISTORICAL CHARTS ---
        st.markdown("### 📊 Daily Production Breakdown")
        c1, c2 = st.columns(2)
        with c1:
            fig = px.pie(df, names='Plant', values='Production for the Day', color_discrete_sequence=current_theme_colors)
            st.plotly_chart(apply_chart_theme(fig), use_container_width=True)
        with c2:
            fig = px.bar(df, x='Plant', y='Production for the Day', color='Plant', color_discrete_sequence=current_theme_colors)
            fig.update_traces(hovertemplate="<b>Plant:</b> %{x}<br><b>Vol:</b> %{y:,.3f} m³<extra></extra>")
            st.plotly_chart(apply_chart_theme(fig, x_axis_title="Plant"), use_container_width=True)
            
        st.markdown("### 📈 Accumulative Production Analysis")
        # Add 2-3 charts for accumulative
        c3, c4 = st.columns(2)
        with c3:
            st.markdown("**Accumulative Totals**")
            fig = px.bar(df, x='Plant', y='Accumulative Production', color='Plant', 
                         color_discrete_sequence=current_theme_colors)
            fig.update_traces(hovertemplate="<b>Plant:</b> %{x}<br><b>Accum:</b> %{y:,.3f} m³<extra></extra>")
            st.plotly_chart(apply_chart_theme(fig, x_axis_title="Plant"), use_container_width=True)
        with c4:
            st.markdown("**Accumulative Share**")
            fig = px.pie(df, names='Plant', values='Accumulative Production', hole=0.4,
                         color_discrete_sequence=current_theme_colors)
            st.plotly_chart(apply_chart_theme(fig), use_container_width=True)
            
        st.markdown("### 🎯 Actual vs Expected (Daily)")
        # Calculate expected for this specific day based on the monthly target
        hist_month = sel_d.strftime("%B")
        hist_year = sel_d.year
        m_target = get_forecast(hist_year, hist_month)
        daily_target = m_target / 30 if m_target > 0 else 0
        
        # Create comparison DF
        comp_df = df[['Plant', 'Production for the Day']].copy()
        # Distribute daily target evenly across plants? Or just show total line?
        # Let's show Total Actual vs Total Expected for the whole site on this day
        
        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(x=['Total Site'], y=[tot], name='Actual', marker_color='#3b82f6'))
        fig_comp.add_trace(go.Bar(x=['Total Site'], y=[daily_target], name='Expected', marker_color='#ef4444'))
        
        st.plotly_chart(apply_chart_theme(fig_comp, x_axis_title="Metric", y_title="Volume"), use_container_width=True)

# ========================================
# MODULE 5: LOGS
# ========================================
elif mode == "Audit Logs":
    if user != "manager": st.error("Access Restricted"); st.stop()
    st.title("Security Audit Logs")
    
    log_date = st.date_input("Filter by Date", value=datetime.today())
    logs = get_logs()
    
    if not logs.empty:
        logs['Timestamp'] = pd.to_datetime(logs['Timestamp'])
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
