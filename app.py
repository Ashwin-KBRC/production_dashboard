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
import calendar
from dateutil.relativedelta import relativedelta

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
        
        /* NEW TOTAL PRODUCTION BIG BOX */
        .total-production-box {{
            background: linear-gradient(135deg, #1e3a8a 0%, #172554 100%);
            color: white;
            padding: 40px;
            border-radius: 16px;
            margin-bottom: 30px;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
            text-align: center;
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
        
        /* FORECAST UPLOAD BOX */
        .forecast-upload-box {{
            background-color: {card_bg};
            padding: 20px;
            border-radius: 12px;
            border: 2px dashed {border_color};
            margin-bottom: 20px;
            text-align: center;
        }}
    </style>
    """, unsafe_allow_html=True)

inject_css()

# ========================================
# 4. SETUP & AUTHENTICATION
# ========================================
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = DATA_DIR / "access_logs.csv"
FORECAST_DIR = DATA_DIR / "forecasts"
# Ensure forecasts directory exists
FORECAST_DIR.mkdir(parents=True, exist_ok=True)
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

# --- FORECAST FUNCTIONS (UPDATED - TEXT FILE BASED) ---
def get_forecast_file_path(year: int, month: int) -> Path:
    """Get the forecast text file path for a specific month and year"""
    # Ensure forecasts directory exists
    FORECAST_DIR.mkdir(parents=True, exist_ok=True)
    return FORECAST_DIR / f"forecast-{month:02d}-{year}.txt"

def save_forecast_value(year: int, month: int, forecast_value: float) -> Tuple[bool, str]:
    """Save forecast value as text file"""
    try:
        # Ensure forecasts directory exists
        FORECAST_DIR.mkdir(parents=True, exist_ok=True)
        
        file_path = get_forecast_file_path(year, month)
        with open(file_path, 'w') as f:
            f.write(str(forecast_value))
        
        st.info(f"Forecast saved locally at: {file_path}")
        
        # Attempt to push to GitHub
        if GITHUB_TOKEN and GITHUB_REPO:
            success, message = attempt_git_push(file_path, f"Add/Update forecast for {calendar.month_name[month]} {year}")
            if success:
                return True, f"Forecast saved for {calendar.month_name[month]} {year} and pushed to GitHub"
            else:
                return False, f"Saved locally but GitHub push failed: {message}"
        else:
            return True, f"Forecast saved locally for {calendar.month_name[month]} {year} (GitHub not configured)"
    except Exception as e:
        return False, f"Error saving forecast: {str(e)}"

def get_forecast(year: int, month: int) -> float:
    """Get forecast value for specific month and year from text file"""
    try:
        file_path = get_forecast_file_path(year, month)
        if not file_path.exists():
            return 0.0
        
        with open(file_path, 'r') as f:
            content = f.read().strip()
            if content:
                return float(content)
            else:
                return 0.0
    except Exception as e:
        print(f"Error reading forecast: {e}")
        return 0.0

def get_current_month_forecast() -> float:
    """Get forecast for current month"""
    now = get_kuwait_time()
    return get_forecast(now.year, now.month)

def list_available_forecasts() -> List[Tuple[int, int, float]]:
    """List all available forecasts with values"""
    forecasts = []
    # Ensure directory exists
    FORECAST_DIR.mkdir(parents=True, exist_ok=True)
    
    for file_path in FORECAST_DIR.glob("forecast-*.txt"):
        try:
            parts = file_path.stem.split('-')
            if len(parts) == 3:
                month = int(parts[1])
                year = int(parts[2])
                forecast_val = get_forecast(year, month)
                forecasts.append((year, month, forecast_val))
        except:
            continue
    return sorted(forecasts, key=lambda x: (x[0], x[1]), reverse=True)

def get_forecast_for_date_range(start_date: date, end_date: date) -> Dict[str, float]:
    """Get forecast values for a date range"""
    forecasts = {}
    current = start_date.replace(day=1)
    
    while current <= end_date:
        forecast_val = get_forecast(current.year, current.month)
        month_key = f"{current.year}-{current.month:02d}"
        forecasts[month_key] = forecast_val
        current += relativedelta(months=1)
    
    return forecasts

def calculate_daily_target(monthly_forecast: float, year: int, month: int) -> float:
    """Calculate daily target based on monthly forecast"""
    days_in_month = calendar.monthrange(year, month)[1]
    if days_in_month > 0 and monthly_forecast > 0:
        return monthly_forecast / days_in_month
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
    """List all saved dates, filtering only valid YYYY-MM-DD format files"""
    valid_dates = []
    for p in DATA_DIR.glob("*.csv"):
        if "access_logs" in p.name or p.parent == FORECAST_DIR:
            continue
        
        # Extract date from filename
        date_str = p.name.replace(".csv", "")
        
        # Validate YYYY-MM-DD format
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            valid_dates.append(date_str)
        except ValueError:
            # Skip files that don't match the date format
            continue
    
    return sorted(valid_dates, reverse=True)

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
    if not GITHUB_TOKEN or not GITHUB_REPO: 
        return False, "Git not configured"
    
    try:
        repo = GITHUB_REPO.strip().replace("https://github.com/", "").replace(".git", "")
        
        # Determine the path relative to data directory
        if "forecasts" in str(file_path.parent):
            # Forecasts are in data/forecasts/
            relative_path = f"data/forecasts/{file_path.name}"
        else:
            # Regular data files are in data/
            relative_path = f"data/{file_path.name}"
        
        url = f"https://api.github.com/repos/{repo}/contents/{relative_path}"
        
        # Read file content
        if file_path.exists():
            with open(file_path, "rb") as f: 
                content = base64.b64encode(f.read()).decode()
        else: 
            return False, f"File missing: {file_path}"
        
        # Check if file exists in GitHub
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        resp = requests.get(url, headers=headers)
        sha = resp.json().get("sha") if resp.status_code == 200 else None
        
        # Prepare payload
        payload = {
            "message": msg,
            "content": content,
            "branch": "main",
            "committer": {
                "name": GITHUB_USER, 
                "email": GITHUB_EMAIL
            }
        }
        
        if sha: 
            payload["sha"] = sha
        
        # Upload to GitHub
        r = requests.put(url, headers=headers, json=payload)
        
        if r.status_code == 201 or r.status_code == 200:
            return True, f"Successfully pushed to GitHub: {relative_path}"
        else:
            error_data = r.json()
            error_msg = error_data.get('message', 'Unknown error')
            return False, f"GitHub error: {error_msg}"
            
    except Exception as e: 
        return False, f"Error pushing to GitHub: {str(e)}"

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

def get_week_range(date_obj):
    """Get week range string (Dec 1 - Dec 7 format)"""
    start_of_week = date_obj - timedelta(days=date_obj.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    start_str = start_of_week.strftime('%b %d')
    end_str = end_of_week.strftime('%b %d')
    return f"{start_str} - {end_str}"

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

def create_forecast_vs_actual_chart(daily_data, forecast_data, title="Actual vs Expected Production"):
    """
    Create a line chart comparing actual production vs expected production
    """
    fig = go.Figure()
    
    # Add actual production line (Blue)
    fig.add_trace(go.Scatter(
        x=daily_data['Date'],
        y=daily_data['Total Production'],
        mode='lines+markers',
        name='Actual Production',
        line=dict(color='#3b82f6', width=3),
        marker=dict(size=8, color='#3b82f6'),
        hovertemplate='<b>%{x|%b %d, %Y}</b><br>Actual: %{y:,.3f} m³<extra></extra>'
    ))
    
    # Add expected production line (Red)
    fig.add_trace(go.Scatter(
        x=daily_data['Date'],
        y=forecast_data['Expected Production'],
        mode='lines+markers',
        name='Expected Production',
        line=dict(color='#ef4444', width=3, dash='dash'),
        marker=dict(size=6, color='#ef4444'),
        hovertemplate='<b>%{x|%b %d, %Y}</b><br>Expected: %{y:,.3f} m³<extra></extra>'
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Production Volume (m³)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
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

# --- FORECAST DISPLAY (ALL USERS) ---
current_time = get_kuwait_time()
current_month_forecast = get_forecast(current_time.year, current_time.month)
current_month_name = calendar.month_name[current_time.month]

if current_month_forecast > 0:
    daily_target = calculate_daily_target(current_month_forecast, current_time.year, current_time.month)
    st.sidebar.markdown(f"""
    <div class="forecast-upload-box">
        <div style="font-size:0.9rem; color:#64748b; margin-bottom:5px;">📊 Current Month Forecast</div>
        <div style="font-size:1.8rem; font-weight:800; color:#3b82f6;">{format_m3(current_month_forecast)}</div>
        <div style="font-size:0.9rem; color:#64748b; margin-top:5px;">{current_month_name} {current_time.year}</div>
        <div style="font-size:0.8rem; color:#10b981; font-weight:600; margin-top:8px;">
            <strong>Expected Average: {format_m3(daily_target)}/day</strong>
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    # Show placeholder if no forecast
    st.sidebar.markdown(f"""
    <div class="forecast-upload-box">
        <div style="font-size:0.9rem; color:#64748b; margin-bottom:5px;">📊 Current Month Forecast</div>
        <div style="font-size:1.2rem; color:#ef4444; font-weight:600;">Not Set</div>
        <div style="font-size:0.9rem; color:#64748b; margin-top:5px;">{current_month_name} {current_time.year}</div>
        <div style="font-size:0.8rem; color:#94a3b8; margin-top:8px;">
            Manager can set forecast
        </div>
    </div>
    """, unsafe_allow_html=True)

# --- MANAGER ONLY: FORECAST SETTING ---
if user == "manager":
    with st.sidebar.expander("🎯 Manager Forecast Controls", expanded=False):
        st.markdown("### Set Monthly Forecast")
        
        # Year and month selection
        current_year = current_time.year
        f_year = st.selectbox("Forecast Year", 
                             [current_year - 1, current_year, current_year + 1],
                             index=1)
        
        f_month = st.selectbox("Forecast Month", 
                              list(calendar.month_name)[1:],  # Skip empty first element
                              index=current_time.month - 1)
        
        month_num = list(calendar.month_name).index(f_month)
        
        # Get current forecast value if exists
        current_val = get_forecast(f_year, month_num)
        
        # Forecast value input
        f_target = st.number_input(
            "Monthly Forecast Target (m³)", 
            min_value=0.0, 
            value=float(current_val) if current_val > 0 else 0.0,
            step=100.0,
            format="%.3f"
        )
        
        # Display GitHub status
        if GITHUB_TOKEN and GITHUB_REPO:
            st.info("✅ GitHub integration is active")
        else:
            st.warning("⚠️ GitHub not configured - forecasts will only be saved locally")
        
        # Save forecast button
        if st.button("💾 Save Forecast", type="primary", use_container_width=True):
            if f_target > 0:
                success, message = save_forecast_value(f_year, month_num, f_target)
                if success:
                    st.success(message)
                    # Show file path
                    file_path = get_forecast_file_path(f_year, month_num)
                    st.info(f"File saved at: {file_path}")
                    
                    # Refresh the page to show updated forecast
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.warning("Please enter a forecast value greater than 0")
        
        # Show existing forecasts
        available_forecasts = list_available_forecasts()
        if available_forecasts:
            st.markdown("---")
            st.markdown("### Existing Forecasts")
            for year, month, forecast_val in available_forecasts[:5]:  # Show last 5
                if forecast_val > 0:
                    st.markdown(f"**{calendar.month_name[month]} {year}:** {format_m3(forecast_val)}")
        else:
            st.markdown("---")
            st.markdown("### No forecasts saved yet")

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
    
    # Calculate total production for the BIG BOX
    total_production = df_filtered['Production for the Day'].sum()
    
    # --- BIG TOTAL PRODUCTION BOX ---
    st.markdown(f"""
    <div class="total-production-box">
        <div style="font-size:1.2rem; opacity:0.9; margin-bottom:10px;">📊 TOTAL PRODUCTION</div>
        <div style="font-size:4rem; font-weight:900; margin:20px 0;">{format_m3(total_production)}</div>
        <div style="font-size:1rem; opacity:0.8;">
            Date Range: {start_d.strftime('%b %d, %Y')} to {end_d.strftime('%b %d, %Y')}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- FORECAST CALCULATION ---
    # Get forecasts for the selected date range
    forecasts = get_forecast_for_date_range(start_d, end_d)
    
    # Calculate expected production for each day based on monthly forecasts
    daily_expected = []
    current_date = start_d
    
    while current_date <= end_d:
        monthly_forecast = get_forecast(current_date.year, current_date.month)
        days_in_month = calendar.monthrange(current_date.year, current_date.month)[1]
        daily_target = monthly_forecast / days_in_month if days_in_month > 0 else 0
        
        daily_expected.append({
            'Date': pd.Timestamp(current_date),
            'Expected Production': daily_target
        })
        current_date += timedelta(days=1)
    
    daily_expected_df = pd.DataFrame(daily_expected)
    
    # Calculate actual daily totals
    daily_actual_df = df_filtered.groupby('Date')['Production for the Day'].sum().reset_index()
    daily_actual_df.columns = ['Date', 'Total Production']
    
    # Merge actual and expected
    daily_comparison = pd.merge(daily_actual_df, daily_expected_df, on='Date', how='left')
    daily_comparison['Expected Production'] = daily_comparison['Expected Production'].fillna(0)
    
    # --- TOP 3 LEADERBOARD CALCULATION ---
    # Top 3 by Sum
    top_sum = df_filtered.groupby("Plant")["Production for the Day"].sum().sort_values(ascending=False).head(3)
    # Top 3 by Average
    top_avg = df_filtered.groupby("Plant")["Production for the Day"].mean().sort_values(ascending=False).head(3)

    # --- FORECAST HERO SECTION ---
    # Determine the "Dominant" month in selection
    if not daily_comparison.empty:
        dom_month_idx = daily_comparison['Date'].dt.month.mode()[0]
        dom_year_idx = daily_comparison['Date'].dt.year.mode()[0]
        month_name = calendar.month_name[dom_month_idx]
        
        monthly_target = get_forecast(dom_year_idx, dom_month_idx)
        total_vol = daily_comparison['Total Production'].sum()
        avg_daily = daily_comparison['Total Production'].mean()
        expected_avg = daily_comparison['Expected Production'].mean()
        
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
                    <div style="font-size:0.8rem; opacity:0.8;">Actual Production</div>
                </div>
                <div style="border-left:1px solid rgba(255,255,255,0.2); border-right:1px solid rgba(255,255,255,0.2);">
                    <div style="font-size:0.9rem; opacity:0.8; text-transform:uppercase;">Forecast ({month_name})</div>
                    <div style="font-size:3rem; font-weight:800;">{monthly_target:,.0f} m³</div>
                    <div style="font-size:0.8rem; opacity:0.8; font-weight:600; color:#fbbf24;">
                        <strong>Expected Average: {format_m3(expected_avg)}/day</strong>
                    </div>
                </div>
                <div>
                    <div style="font-size:0.9rem; opacity:0.8; text-transform:uppercase;">Forecast Variance</div>
                    <div style="font-size:3rem; font-weight:800; color:{var_color};">{var_icon} {abs(variance):,.0f} m³</div>
                    <div style="font-size:0.8rem; opacity:0.8;">Actual: {total_vol:,.0f} m³</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ------------------ LEADERBOARDS ------------------
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

    # ------------------ ACTUAL VS EXPECTED CHART ------------------
    st.markdown("### 📈 Actual vs Expected Production")
    if not daily_comparison.empty:
        fig_comparison = create_forecast_vs_actual_chart(daily_comparison, daily_comparison)
        st.plotly_chart(apply_chart_theme(fig_comparison), use_container_width=True)

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
        
        # Format Date Label with Week Range (Dec 1 - Dec 7 format)
        week_agg['Week Range'] = week_agg['Date'].apply(lambda x: get_week_range(x))
        week_agg['Week Label'] = week_agg['Week Range']
        
        # Post-Aggregation Filter (Double Check)
        week_agg = week_agg[(week_agg['Date'] >= pd.to_datetime(start_d)) & (week_agg['Date'] <= pd.to_datetime(end_d))]

        # NEW: Additional charts for Production of the Day
        st.markdown("#### 📊 Weekly Production Analysis")
        
        # Create 4 charts in a 2x2 grid
        col1, col2 = st.columns(2)
        
        with col1:
            # Chart 1: Weekly Total Production (Sum)
            fig1 = px.bar(week_agg, x='Week Label', y='Total Production', color='Plant', 
                         title="Weekly Total Production (Sum)", barmode='group',
                         text='Plant',
                         color_discrete_sequence=current_theme_colors)
            fig1.update_traces(
                hovertemplate='<b>Week: %{x}</b><br>Plant: %{text}<br>Total: %{y:,.3f} m³<extra></extra>'
            )
            st.plotly_chart(apply_chart_theme(fig1), use_container_width=True)
            
            # NEW Chart 3: Weekly Production Trend (Line)
            fig3 = px.line(week_agg, x='Week Label', y='Total Production', color='Plant', markers=True,
                          title="Weekly Production Trend",
                          text='Plant',
                          color_discrete_sequence=current_theme_colors)
            fig3.update_traces(
                hovertemplate='<b>Week: %{x}</b><br>Plant: %{text}<br>Total: %{y:,.3f} m³<extra></extra>'
            )
            st.plotly_chart(apply_chart_theme(fig3), use_container_width=True)
            
        with col2:
            # Chart 2: Weekly Average Production (Mean)
            fig2 = px.bar(week_agg, x='Week Label', y='Avg Production', color='Plant', 
                         title="Weekly Average Production (Mean)", barmode='group',
                         text='Plant',
                         color_discrete_sequence=current_theme_colors)
            fig2.update_traces(
                hovertemplate='<b>Week: %{x}</b><br>Plant: %{text}<br>Average: %{y:,.3f} m³<extra></extra>'
            )
            st.plotly_chart(apply_chart_theme(fig2), use_container_width=True)
            
            # NEW Chart 4: Weekly Production Distribution (Area)
            fig4 = px.area(week_agg, x='Week Label', y='Total Production', color='Plant',
                          title="Weekly Production Distribution",
                          text='Plant',
                          color_discrete_sequence=current_theme_colors)
            fig4.update_traces(
                hovertemplate='<b>Week: %{x}</b><br>Plant: %{text}<br>Total: %{y:,.3f} m³<extra></extra>'
            )
            st.plotly_chart(apply_chart_theme(fig4), use_container_width=True)
        
        # Weekly Accumulative Trend
        st.markdown("#### 📈 Weekly Accumulative Trend")
        fig_acc = px.line(week_agg, x='Week Label', y='Accumulative', color='Plant', markers=True,
                          title="Weekly Accumulative Production",
                          text='Plant',
                          color_discrete_sequence=current_theme_colors)
        fig_acc.update_traces(
            hovertemplate='<b>Week: %{x}</b><br>Plant: %{text}<br>Accumulative: %{y:,.3f} m³<extra></extra>'
        )
        st.plotly_chart(apply_chart_theme(fig_acc), use_container_width=True)

    # --- MONTHLY ANALYSIS ---
    with tab_month:
        st.subheader("Monthly Analytics")
        
        # Monthly Trajectory Chart
        st.markdown("#### 🎯 Monthly Trajectory: Actual vs Forecast")
        if not daily_comparison.empty:
            # Calculate monthly cumulative
            daily_comparison['Month'] = daily_comparison['Date'].dt.strftime('%B %Y')
            monthly_cum = daily_comparison.groupby('Month').agg({
                'Total Production': 'sum',
                'Expected Production': 'sum'
            }).reset_index()
            
            fig_traj = go.Figure()
            fig_traj.add_trace(go.Bar(
                x=monthly_cum['Month'],
                y=monthly_cum['Total Production'],
                name='Actual Production',
                marker_color='#3b82f6',
                text=monthly_cum['Total Production'].apply(lambda x: f"{x:,.0f}"),
                textposition='outside'
            ))
            fig_traj.add_trace(go.Bar(
                x=monthly_cum['Month'],
                y=monthly_cum['Expected Production'],
                name='Expected Production',
                marker_color='#ef4444',
                text=monthly_cum['Expected Production'].apply(lambda x: f"{x:,.0f}"),
                textposition='outside'
            ))
            
            fig_traj.update_layout(
                title="Monthly Actual vs Expected Production",
                barmode='group',
                yaxis_title="Production Volume (m³)"
            )
            st.plotly_chart(apply_chart_theme(fig_traj), use_container_width=True)
        
        # Standard Monthly Charts
        month_agg = df_filtered.groupby(['Plant', pd.Grouper(key='Date', freq='M')]).agg({
            'Production for the Day': ['sum', 'mean'],
            'Accumulative Production': 'max'
        }).reset_index()
        month_agg.columns = ['Plant', 'Date', 'Total Production', 'Avg Production', 'Accumulative']
        month_agg['Month Label'] = month_agg['Date'].dt.strftime('%B %Y')
        
        month_agg = month_agg[(month_agg['Date'] >= pd.to_datetime(start_d)) & (month_agg['Date'] <= pd.to_datetime(end_d))]

        # NEW: Additional charts for Monthly analysis
        st.markdown("#### 📊 Monthly Production Analysis")
        
        col_m1, col_m2 = st.columns(2)
        
        with col_m1:
            # Chart 1: Monthly Total Production (Sum)
            fig_m1 = px.bar(month_agg, x='Month Label', y='Total Production', color='Plant', 
                           title="Monthly Total Production (Sum)", barmode='group',
                           text='Plant',
                           color_discrete_sequence=current_theme_colors)
            fig_m1.update_traces(
                hovertemplate='<b>Month: %{x}</b><br>Plant: %{text}<br>Total: %{y:,.3f} m³<extra></extra>'
            )
            st.plotly_chart(apply_chart_theme(fig_m1), use_container_width=True)
            
            # NEW Chart 3: Monthly Production Stacked Area
            fig_m3 = px.area(month_agg, x='Month Label', y='Total Production', color='Plant',
                            title="Monthly Production Distribution (Stacked)",
                            text='Plant',
                            color_discrete_sequence=current_theme_colors)
            fig_m3.update_traces(
                hovertemplate='<b>Month: %{x}</b><br>Plant: %{text}<br>Total: %{y:,.3f} m³<extra></extra>'
            )
            st.plotly_chart(apply_chart_theme(fig_m3), use_container_width=True)
            
        with col_m2:
            # Chart 2: Monthly Average Production (Mean)
            fig_m2 = px.bar(month_agg, x='Month Label', y='Avg Production', color='Plant', 
                           title="Monthly Average Production (Mean)", barmode='group',
                           text='Plant',
                           color_discrete_sequence=current_theme_colors)
            fig_m2.update_traces(
                hovertemplate='<b>Month: %{x}</b><br>Plant: %{text}<br>Average: %{y:,.3f} m³<extra></extra>'
            )
            st.plotly_chart(apply_chart_theme(fig_m2), use_container_width=True)
            
            # NEW Chart 4: Monthly Production Heatmap
            # Create pivot table for heatmap
            pivot_df = month_agg.pivot_table(
                index='Plant', 
                columns='Month Label', 
                values='Total Production',
                aggfunc='sum'
            ).fillna(0)
            
            fig_m4 = px.imshow(
                pivot_df,
                labels=dict(x="Month", y="Plant", color="Production"),
                title="Monthly Production Heatmap by Plant",
                aspect="auto"
            )
            fig_m4.update_xaxes(side="top")
            st.plotly_chart(apply_chart_theme(fig_m4), use_container_width=True)
        
        # Monthly Accumulative Trend
        st.markdown("#### 📈 Monthly Accumulative Trend")
        fig_acc_m = px.line(month_agg, x='Month Label', y='Accumulative', color='Plant', markers=True,
                            title="Monthly Accumulative Production",
                            text='Plant',
                            color_discrete_sequence=current_theme_colors)
        fig_acc_m.update_traces(
            hovertemplate='<b>Month: %{x}</b><br>Plant: %{text}<br>Accumulative: %{y:,.3f} m³<extra></extra>'
        )
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
    
    if not files: 
        st.info("No historical records found.")
        st.stop()
    
    # Initialize session state with proper error handling
    if "hist_d" not in st.session_state:
        try:
            # Try to parse the first valid date
            st.session_state.hist_d = datetime.strptime(files[0], "%Y-%m-%d").date()
        except (ValueError, IndexError):
            # If parsing fails, use today's date
            st.session_state.hist_d = datetime.today().date()
    
    # Create a dropdown with formatted dates for better UX
    formatted_dates = []
    for f in files:
        try:
            dt = datetime.strptime(f, "%Y-%m-%d")
            formatted_dates.append((dt, f"{dt.strftime('%B %d, %Y')} ({f})"))
        except ValueError:
            continue
    
    if not formatted_dates:
        st.error("No valid date files found.")
        st.stop()
    
    # Sort by date descending
    formatted_dates.sort(key=lambda x: x[0], reverse=True)
    
    # Create dropdown options
    date_options = [fd[1] for fd in formatted_dates]
    date_values = [fd[0].date() for fd in formatted_dates]
    
    # Find current selection index
    current_index = 0
    for i, (dt, _) in enumerate(formatted_dates):
        if dt.date() == st.session_state.hist_d:
            current_index = i
            break
    
    # Date selection with dropdown
    selected_option = st.selectbox(
        "Select Date", 
        options=date_options,
        index=current_index,
        key="hist_date_select"
    )
    
    # Find the selected date
    sel_d = None
    for dt, option in formatted_dates:
        if option == selected_option:
            sel_d = dt.date()
            break
    
    if sel_d is None:
        sel_d = formatted_dates[0][0].date()
    
    st.session_state.hist_d = sel_d
    d_str = sel_d.strftime("%Y-%m-%d")
    
    if d_str in files:
        df = load_saved(d_str)
        df = df[~df["Plant"].astype(str).str.upper().str.contains("TOTAL")]
        df = safe_numeric(df)
        tot = df["Production for the Day"].sum()
        
        # Get forecast for this day's month
        month_forecast = get_forecast(sel_d.year, sel_d.month)
        days_in_month = calendar.monthrange(sel_d.year, sel_d.month)[1]
        expected_daily = month_forecast / days_in_month if days_in_month > 0 else 0
        
        st.markdown(f"""
        <div style="background:{'#1e293b' if st.session_state['dark_mode'] else '#1e3a8a'}; color:white; padding:30px; border-radius:12px; margin-bottom:20px;">
            <h2 style="margin:0; color:white !important;">{sel_d.strftime('%A, %B %d, %Y')}</h2>
            <div style="font-size:3rem; font-weight:800;">{format_m3(tot)}</div>
            <div style="font-size:1rem; margin-top:10px;">
                Expected Daily: <span style="font-weight:600;">{format_m3(expected_daily)}</span> | 
                Monthly Forecast: <span style="font-weight:600;">{format_m3(month_forecast)}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True)
        
        st.markdown("### 📊 Daily Analysis")
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
        c3, c4 = st.columns(2)
        with c3:
            st.markdown("**Accumulative by Plant**")
            fig_acc_bar = px.bar(df, x='Plant', y='Accumulative Production', color='Plant', text='Plant', color_discrete_sequence=current_theme_colors)
            st.plotly_chart(apply_chart_theme(fig_acc_bar), use_container_width=True)
        with c4:
            st.markdown("**Accumulative Share**")
            fig_acc_pie = px.pie(df, names='Plant', values='Accumulative Production', color_discrete_sequence=current_theme_colors)
            st.plotly_chart(apply_chart_theme(fig_acc_pie), use_container_width=True)
        
        # NEW: Actual vs Expected Chart for Historical View
        st.markdown("### 🎯 Actual vs Expected Production")
        
        # Create comparison data
        comparison_data = pd.DataFrame({
            'Metric': ['Actual Production', 'Expected Production'],
            'Value': [tot, expected_daily],
            'Color': ['#3b82f6', '#ef4444']
        })
        
        fig_comparison = px.bar(
            comparison_data, 
            x='Metric', 
            y='Value', 
            color='Metric',
            title=f"Daily Production Comparison for {sel_d.strftime('%B %d, %Y')}",
            color_discrete_map={'Actual Production': '#3b82f6', 'Expected Production': '#ef4444'},
            text=comparison_data['Value'].apply(lambda x: format_m3(x))
        )
        fig_comparison.update_traces(textposition='outside')
        fig_comparison.update_layout(showlegend=False)
        st.plotly_chart(apply_chart_theme(fig_comparison), use_container_width=True)

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

# Debug information (only show if needed)
if st.sidebar.checkbox("Show Debug Info", False):
    st.sidebar.write("Data Directory:", DATA_DIR)
    st.sidebar.write("Forecast Directory:", FORECAST_DIR)
    st.sidebar.write("GitHub Token:", "Set" if GITHUB_TOKEN else "Not Set")
    st.sidebar.write("GitHub Repo:", GITHUB_REPO if GITHUB_REPO else "Not Set")
    
    if FORECAST_DIR.exists():
        forecast_files = list(FORECAST_DIR.glob("*.txt"))
        st.sidebar.write(f"Forecast files: {len(forecast_files)}")
        for f in forecast_files:
            st.sidebar.write(f"- {f.name}")

