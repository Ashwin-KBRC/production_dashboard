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
if "theme" not in st.session_state: # Initialize theme state safely
    st.session_state["theme"] = "Executive Blue"

# ========================================
# 3. CSS STYLING (DYNAMIC LIGHT/DARK)
# ========================================
def inject_css():
    """
    Injects professional CSS based on the current Light/Dark mode state.
    Ensures all text is white in dark mode for maximum readability.
    """
    if st.session_state["dark_mode"]:
        # DARK MODE PALETTE
        bg_color = "#0f172a"          # Slate 900
        text_color = "#f8fafc"        # Slate 50 (White)
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
            background-color: {bg_color};
            color: {text_color}; /* Base text color */
        }}

        /* HIDE DEFAULT STREAMLIT BRANDING */
        footer, #MainMenu, header, .stAppDeployButton {{ visibility: hidden !important; height: 0 !important; }}
        
        /* SIDEBAR STYLING */
        [data-testid="stSidebar"] {{
            background-color: {sidebar_bg};
            border-right: 1px solid {border_color};
        }}
        [data-testid="stSidebarCollapseButton"] {{display: none !important;}}

        /* UNIVERSAL TEXT AND INPUT COLOR OVERRIDE (CRITICAL FOR DARK MODE) */
        /* Targets all Streamlit text, markdown, captions, labels */
        .stMarkdown, .stText, .stAlert, .stSelectbox label, .stDateInput label, .stNumberInput label, .stRadio label,
        [data-testid*="stCaption"], [data-testid*="stInput"], [data-testid*="stSelectbox"] div[role="listbox"],
        [data-testid*="stTextarea"] textarea, 
        h1, h2, h3, h4, h5, h6 {{ 
            color: {text_color} !important; 
        }}

        /* Fix for input field backgrounds and text */
        div[data-baseweb="select"] input, div[data-baseweb="input"] input, div[data-baseweb="textarea"] textarea,
        div[data-baseweb="select"], [data-baseweb="input"] {{
            color: {text_color} !important;
            background-color: {card_bg} !important;
            border-color: {border_color} !important;
        }}
        
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
        
        /* INSIGHT BOX */
        .insight-box {{
            background: rgba(59, 130, 246, 0.1);
            border-left: 4px solid #3b82f6;
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 20px;
            color: {text_color};
        }}
        
        /* ADD SPACE BETWEEN HEADERS AND CHARTS/CONTENT */
        .stPlotlyChart {{ margin-top: 15px; }}
        /* Ensure spacing after markdown headers and before the next element (like a chart or table) */
        .stMarkdown h4 + div, .stMarkdown h3 + div, .stMarkdown h2 + div, .stMarkdown h1 + div {{ margin-top: 15px; }}
        
    </style>
    """, unsafe_allow_html=True)

inject_css()

# ========================================
# 4. SETUP & AUTHENTICATION
# ========================================
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = DATA_DIR / "access_logs.csv"
REQUIRED_COLS = ["Plant", "Production for the Day", "Accumulative Production"]

# CONFIGURATION SECRETS
SECRETS = {}
try: SECRETS = dict(st.secrets)
except: SECRETS = {}

# Use default values if running outside of a secrets environment
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
    """Standardized formatting for Cubic Meters to ensure exact values"""
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
    return sorted([p.name.replace(".csv", "") for p in DATA_DIR.glob("*.csv") if "access_logs" not in p.name], reverse=True)

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
        return r.ok, "Synced" if r.ok else f"Sync Failed: {r.status_code} - {r.text}"
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
    Generates text-based insights for the Executive Summary.
    """
    if df.empty: return "No data available to generate insights."
    
    total = df['Production for the Day'].sum()
    
    if 'Plant' in df.columns and not df['Plant'].empty:
        plant_totals = df.groupby('Plant')['Production for the Day'].sum()
        if not plant_totals.empty:
            top_plant = plant_totals.idxmax()
            top_val = plant_totals.max()
        else:
            top_plant, top_val = "N/A", 0
    else:
        top_plant, top_val = "N/A", 0
        
    avg = df['Production for the Day'].mean()
    
    insight = f"**Executive Summary:** The total production for this period stands at **{format_m3(total)}**. "
    if top_plant != "N/A":
        insight += f"The leading facility is **{top_plant}**, contributing **{format_m3(top_val)}** to the total output. "
    insight += f"On average, daily plant production is tracking at **{format_m3(avg)}**."
    return insight

# ========================================
# 6. CHARTING ENGINE
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

def apply_chart_theme(fig, x_axis_title="Date Range"):
    """
    Applies the professional layout to charts, ensuring readability and exact value formatting.
    """
    dark = st.session_state["dark_mode"]
    text_col = "#ffffff" if dark else "#1e293b"
    grid_col = "rgba(255, 255, 255, 0.1)" if dark else "rgba(0, 0, 0, 0.05)"
    
    # Custom hover template for all volume charts to ensure exact values
    custom_hovertemplate = (
        "<b>Date:</b> %{x}<br>" +
        "<b>Plant:</b> %{customdata[0]}<br>" +
        "<b>Volume:</b> %{y:,.3f} m³<extra></extra>"
    )

    fig.update_layout(
        font=dict(family="Inter", size=12, color=text_col),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=30, b=10, l=10, r=10),
        xaxis=dict(showgrid=False, linecolor=grid_col, tickfont=dict(color=text_col), title=x_axis_title),
        yaxis=dict(showgrid=True, gridcolor=grid_col, linecolor=grid_col, tickfont=dict(color=text_col), 
                   # FIX: Ensure exact values for Y-axis (Production/Volume)
                   tickformat=',.3f', title="Production Volume (m³)"), 
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color=text_col)),
        hovermode="x unified"
    )
    
    # Apply custom hover for scatter/bar charts that use the standard x/y
    fig.update_traces(hovertemplate=custom_hovertemplate)
    
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
            # Ensure text inputs adapt to dark mode
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

# DARK MODE TOGGLE
is_dark = st.sidebar.toggle("🌙 Dark Mode", value=st.session_state["dark_mode"])
if is_dark != st.session_state["dark_mode"]:
    st.session_state["dark_mode"] = is_dark
    st.rerun()

# THEME SELECTOR
theme_list = ["Neon Cyber", "Executive Blue", "Emerald City", "Royal Purple", "Crimson Tide"]
theme_sel = st.sidebar.selectbox("Chart Theme", theme_list,
                                 index=theme_list.index(st.session_state.get("theme", "Executive Blue")))

if theme_sel != st.session_state.get("theme"):
    st.session_state["theme"] = theme_sel
    st.rerun()

current_theme_colors = get_theme_colors(st.session_state["theme"])
alert_threshold = st.sidebar.number_input("Alert Threshold (m³)", 50.0, step=10.0, format="%.3f")

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
    min_date = datetime.strptime(saved[-1], "%Y-%m-%d").date()
    max_date = datetime.strptime(saved[0], "%Y-%m-%d").date()
    
    # Initialize date state safely
    if "start_d" not in st.session_state:
        st.session_state.start_d = min(max_date, datetime.today().date() - timedelta(days=30))
    if "end_d" not in st.session_state:
        st.session_state.end_d = max_date
    
    with c1: 
        start_d = st.date_input("Start Date", value=st.session_state.start_d, min_value=min_date, max_value=max_date)
        st.session_state.start_d = start_d
    with c2: 
        end_d = st.date_input("End Date", value=st.session_state.end_d, min_value=min_date, max_value=max_date)
        st.session_state.end_d = end_d
    
    if start_d > end_d:
        st.error("Start Date cannot be after End Date.")
        st.stop()
        
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
    
    # STRICT FILTERING 
    mask = (full_df['Date'] >= pd.to_datetime(start_d)) & (full_df['Date'] <= pd.to_datetime(end_d))
    df_filtered = full_df[mask].copy().sort_values('Date')
    
    if df_filtered.empty:
        st.info("No data available for the selected date range.")
        st.stop()
        
    df_filtered = safe_numeric(df_filtered)
    df_filtered = df_filtered.drop_duplicates(subset=['Date', 'Plant'], keep='last')

    # KEY METRICS HEADER
    total_vol = df_filtered['Production for the Day'].sum()
    avg_daily = df_filtered.groupby('Date')['Production for the Day'].sum().mean()
    
    st.markdown(f"""
    <div class="hero-banner">
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px; text-align:center;">
            <div>
                <div style="font-size:0.9rem; opacity:0.8; text-transform:uppercase;">Selected Period Volume</div>
                <div style="font-size:3rem; font-weight:800;">{total_vol:,.3f} m³</div>
            </div>
            <div style="border-left:1px solid rgba(255,255,255,0.2);">
                <div style="font-size:0.9rem; opacity:0.8; text-transform:uppercase;">Daily Average</div>
                <div style="font-size:3rem; font-weight:800;">{avg_daily:,.3f} m³</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # INNOVATION: SMART INSIGHTS
    st.markdown(f"""<div class="insight-box">{generate_smart_insights(df_filtered)}</div>""", unsafe_allow_html=True)

    # TABS FOR WEEKLY / MONTHLY SPLIT
    tab_week, tab_month = st.tabs(["📅 Weekly Performance", "📆 Monthly Performance"])

    # --- WEEKLY ANALYSIS ---
    with tab_week:
        st.subheader("Weekly Analytics and Trend Analysis")
        # Aggregation Logic
        week_agg = df_filtered.groupby(['Plant', pd.Grouper(key='Date', freq='W-MON')]).agg(
            Total_Production=('Production for the Day', 'sum'),
            Avg_Production=('Production for the Day', 'mean'),
            Accumulative=('Accumulative Production', 'max') 
        ).reset_index()
        
        # Calculate start of the week and format the label/range for tooltip
        week_agg['Week Start'] = week_agg['Date'] - pd.Timedelta(days=6)
        week_agg['X Label'] = week_agg.apply(lambda row: f"{row['Week Start'].strftime('%d %b')} - {row['Date'].strftime('%d %b')}", axis=1)
        week_agg['Date Range'] = week_agg.apply(lambda row: f"{row['Week Start'].strftime('%Y-%m-%d')} to {row['Date'].strftime('%Y-%m-%d')}", axis=1)
        
        # Post-Aggregation Filter (Ensure we only show data within the selection)
        week_agg = week_agg[(week_agg['Date'] >= pd.to_datetime(start_d)) & (week_agg['Date'] <= pd.to_datetime(end_d))]

        c_w1, c_w2 = st.columns(2)
        
        # --- CHART 1: WEEKLY TOTAL PRODUCTION (SUM) ---
        with c_w1:
            st.markdown("#### Weekly Total Production (Sum) by Plant")
            fig = px.bar(week_agg, x='X Label', y='Total_Production', color='Plant', 
                         barmode='group',
                         custom_data=[week_agg['Date Range'], week_agg['Plant']],
                         color_discrete_sequence=current_theme_colors)
            fig.update_traces(
                hovertemplate="""<b>Date Range:</b> %{customdata[0]}<br>""" +
                              """<b>Plant:</b> %{customdata[1]}<br>""" +
                              """<b>Total Volume:</b> %{y:,.3f} m³<extra></extra>"""
            )
            st.plotly_chart(apply_chart_theme(fig, x_axis_title="Week Ending Date Range"), use_container_width=True)
            
        # --- CHART 2: WEEKLY AVERAGE PRODUCTION (MEAN) ---
        with c_w2:
            st.markdown("#### Weekly Average Production (Mean) by Plant")
            fig = px.bar(week_agg, x='X Label', y='Avg_Production', color='Plant', 
                         barmode='group',
                         custom_data=[week_agg['Date Range'], week_agg['Plant']],
                         color_discrete_sequence=current_theme_colors)
            fig.update_traces(
                hovertemplate="""<b>Date Range:</b> %{customdata[0]}<br>""" +
                              """<b>Plant:</b> %{customdata[1]}<br>""" +
                              """<b>Average Volume:</b> %{y:,.3f} m³<extra></extra>"""
            )
            st.plotly_chart(apply_chart_theme(fig, x_axis_title="Week Ending Date Range"), use_container_width=True)
            
        # --- CHART 3: WEEKLY ACCUMULATIVE TREND ---
        st.markdown("#### Weekly Accumulative Production Trend")
        fig_acc = px.line(week_agg, x='X Label', y='Accumulative', color='Plant', markers=True,
                          title="Plant Accumulative Production over Selected Weeks",
                          custom_data=[week_agg['Date Range'], week_agg['Plant']],
                          color_discrete_sequence=current_theme_colors)
        fig_acc.update_traces(
            hovertemplate="""<b>Date Range:</b> %{customdata[0]}<br>""" +
                          """<b>Plant:</b> %{customdata[1]}<br>""" +
                          """<b>Accumulative Volume:</b> %{y:,.3f} m³<extra></extra>"""
        )
        st.plotly_chart(apply_chart_theme(fig_acc, x_axis_title="Week Ending Date Range"), use_container_width=True)

    # --- MONTHLY ANALYSIS ---
    with tab_month:
        st.subheader("Monthly Analytics and Trend Analysis")
        # Aggregation Logic for Monthly data
        month_agg = df_filtered.groupby(['Plant', pd.Grouper(key='Date', freq='M')]).agg(
            Total_Production=('Production for the Day', 'sum'),
            Avg_Production=('Production for the Day', 'mean'),
            Accumulative=('Accumulative Production', 'max')
        ).reset_index()
        month_agg['X Label'] = month_agg['Date'].dt.strftime('%B %Y')
        month_agg['Date Range'] = month_agg['Date'].dt.to_period('M').apply(lambda x: f"{x.start_time.strftime('%Y-%m-%d')} to {x.end_time.strftime('%Y-%m-%d')}")
        
        # Post-Aggregation Filter
        month_agg = month_agg[(month_agg['Date'] >= pd.to_datetime(start_d)) & (month_agg['Date'] <= pd.to_datetime(end_d))]

        c_m1, c_m2 = st.columns(2)
        
        # --- CHART 4: MONTHLY TOTAL PRODUCTION (SUM) ---
        with c_m1:
            st.markdown("#### Monthly Total Production (Sum) by Plant")
            fig = px.bar(month_agg, x='X Label', y='Total_Production', color='Plant', 
                         barmode='group',
                         custom_data=[month_agg['Date Range'], month_agg['Plant']],
                         color_discrete_sequence=current_theme_colors)
            fig.update_traces(
                hovertemplate="""<b>Date Range:</b> %{customdata[0]}<br>""" +
                              """<b>Plant:</b> %{customdata[1]}<br>""" +
                              """<b>Total Volume:</b> %{y:,.3f} m³<extra></extra>"""
            )
            st.plotly_chart(apply_chart_theme(fig, x_axis_title="Month"), use_container_width=True)
            
        # --- CHART 5: MONTHLY AVERAGE PRODUCTION (MEAN) ---
        with c_m2:
            st.markdown("#### Monthly Average Production (Mean) by Plant")
            fig = px.bar(month_agg, x='X Label', y='Avg_Production', color='Plant', 
                         barmode='group',
                         custom_data=[month_agg['Date Range'], month_agg['Plant']],
                         color_discrete_sequence=current_theme_colors)
            fig.update_traces(
                hovertemplate="""<b>Date Range:</b> %{customdata[0]}<br>""" +
                              """<b>Plant:</b> %{customdata[1]}<br>""" +
                              """<b>Average Volume:</b> %{y:,.3f} m³<extra></extra>"""
            )
            st.plotly_chart(apply_chart_theme(fig, x_axis_title="Month"), use_container_width=True)
            
        # --- CHART 6: MONTHLY ACCUMULATIVE TREND ---
        st.markdown("#### Monthly Accumulative Production Trend (End-of-Month Snapshot)")
        fig_acc_m = px.line(month_agg, x='X Label', y='Accumulative', color='Plant', markers=True,
                            title="Plant Accumulative Production Trend by Month",
                            custom_data=[month_agg['Date Range'], month_agg['Plant']],
                            color_discrete_sequence=current_theme_colors)
        fig_acc_m.update_traces(
            hovertemplate="""<b>Date Range:</b> %{customdata[0]}<br>""" +
                          """<b>Plant:</b> %{customdata[1]}<br>""" +
                          """<b>Accumulative Volume:</b> %{y:,.3f} m³<extra></extra>"""
        )
        st.plotly_chart(apply_chart_theme(fig_acc_m, x_axis_title="Month"), use_container_width=True)

# ========================================
# MODULE 2: UPLOAD DATA
# ========================================
elif mode == "Upload New Data":
    st.title("Daily Production Entry")
    c1, c2 = st.columns([2, 1])
    with c1: uploaded = st.file_uploader("Upload Excel File", type=["xlsx"])
    
    # Initialize 'up_date' safely
    if "up_date" not in st.session_state: 
        st.session_state.up_date = datetime.today().date()

    with c2:
        sel_date = st.date_input("Production Date", value=st.session_state.up_date)
        if sel_date != st.session_state.up_date:
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
                    
                    # Git push attempt
                    success, message = attempt_git_push(save_path, f"Upload daily data for {sel_date}")
                    if success:
                        st.sidebar.success("Data synced to remote repository.")
                    else:
                        st.sidebar.warning(f"Data saved locally. Git sync failed: {message}")
                    
                    df_disp = df_clean[~df_clean["Plant"].astype(str).str.upper().str.contains("TOTAL")]
                    df_disp = safe_numeric(df_disp)
                    tot = df_disp["Production for the Day"].sum()
                    st.success(f"Saved! Total Daily Production: {format_m3(tot)}")
                    st.rerun()

        except FileExistsError:
             st.error(f"Error: Data for {sel_date.strftime('%Y-%m-%d')} already exists. Please delete it in 'Data Management' or change the date.")
        except Exception as e: 
             st.error(f"Error processing file: {e}")

# ========================================
# MODULE 3: DATA MANAGEMENT
# ========================================
elif mode == "Data Management":
    st.title("Database Management")
    files = list_saved_dates()
    if not files: st.info("No records.")
    else:
        st.markdown("### Manage Saved Production Records")
        for f in files:
            with st.expander(f"📂 Record for {f}", expanded=False):
                c1, c2, c3 = st.columns([1, 1, 1])
                with c1:
                    df = load_saved(f)
                    xl = generate_excel_report(df, f)
                    st.download_button("Download Excel Report", xl, f"KBRC_Report_{f}.xlsx", key=f"d_{f}", use_container_width=True)
                
                with c2:
                    if st.button("Delete Record", key=f"del_{f}", type="primary", use_container_width=True):
                        if delete_saved(f):
                            log_event(user, f"Deleted {f}")
                            attempt_git_push(Path(DATA_DIR / f"{f}.csv"), f"Delete data for {f}")
                            st.toast(f"Successfully deleted record for {f}.")
                            st.rerun()
                        else:
                            st.error(f"Failed to delete record for {f}.")

                with c3:
                    try:
                        st.info(f"File Size: {os.path.getsize(DATA_DIR / f'{f}.csv') / 1024:.2f} KB")
                    except:
                        st.info("Size N/A")

# ========================================
# MODULE 4: HISTORICAL ARCHIVES
# ========================================
elif mode == "Historical Archives":
    st.title("Historical Daily Data Viewer")
    files = list_saved_dates()
    if not files: st.info("No historical records available."); st.stop()
    
    latest_date = datetime.strptime(files[0], "%Y-%m-%d").date()
    
    if "hist_d" not in st.session_state: 
        st.session_state.hist_d = latest_date
        
    sel_d = st.date_input("Select Date", 
                          value=st.session_state.hist_d, 
                          min_value=datetime.strptime(files[-1], "%Y-%m-%d").date(),
                          max_value=latest_date
    )
    if sel_d != st.session_state.hist_d:
        st.session_state.hist_d = sel_d
    
    d_str = sel_d.strftime("%Y-%m-%d")
    
    if d_str in files:
        df = load_saved(d_str)
        df = df[~df["Plant"].astype(str).str.upper().str.contains("TOTAL")]
        df = safe_numeric(df)
        tot = df["Production for the Day"].sum()
        
        st.markdown(f"""
        <div style="background:{'#1e293b' if st.session_state['dark_mode'] else '#1e3a8a'}; color:white; padding:30px; border-radius:12px; margin-bottom:20px;">
            <h2 style="margin:0; color:white !important;">Production Overview for {sel_d.strftime('%A, %B %d, %Y')}</h2>
            <div style="font-size:3rem; font-weight:800;">{format_m3(tot)}</div>
            <p style="font-size:0.9rem; opacity:0.9;">Total Daily Volume</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### Raw Data Table")
        st.dataframe(df, use_container_width=True)
        
        st.markdown("### Daily Performance Charts")
        # Quick Charts (RESTORING ORIGINAL CHARTS)
        c1, c2 = st.columns(2)
        
        # --- CHART 7: PRODUCTION DISTRIBUTION (PIE CHART) ---
        with c1:
            st.markdown("#### Production Distribution by Plant")
            fig = px.pie(df, names='Plant', values='Production for the Day', 
                         color_discrete_sequence=current_theme_colors,
                         title="Distribution of Daily Production Volume")
            fig.update_traces(textposition='inside', textinfo='percent+label', 
                              hovertemplate="Plant: %{label}<br>Volume: %{value:,.3f} m³<br>Percentage: %{percent}<extra></extra>")
            fig.update_layout(showlegend=True, margin=dict(t=30, b=10, l=10, r=10)) # Ensure margins are applied
            st.plotly_chart(fig, use_container_width=True) # Pie charts don't need apply_chart_theme for axis formatting
            
        # --- CHART 8: DAILY PRODUCTION VOLUME (BAR CHART) ---
        with c2:
            st.markdown("#### Daily Production Volume by Plant")
            # Create a column for custom hover data (just the plant name, as date is obvious)
            df['Custom Plant'] = df['Plant'] 
            fig = px.bar(df, x='Plant', y='Production for the Day', color='Plant', 
                         custom_data=['Custom Plant'],
                         color_discrete_sequence=current_theme_colors,
                         title="Production for the Day Across All Plants")
            fig.update_traces(
                hovertemplate="""<b>Plant:</b> %{customdata[0]}<br>""" +
                              """<b>Daily Volume:</b> %{y:,.3f} m³<extra></extra>"""
            )
            st.plotly_chart(apply_chart_theme(fig, x_axis_title="Plant Name"), use_container_width=True)
            
    else:
        st.error(f"No record found for the date: {d_str}")

# ========================================
# MODULE 5: AUDIT LOGS (MANAGER ONLY)
# ========================================
elif mode == "Audit Logs":
    if user != "manager": 
        st.error("Access Restricted. Only managers can view audit logs.")
        log_event(user, "Unauthorized access attempt to Audit Logs")
        st.stop()
        
    st.title("Security Audit Logs")
    
    if "log_date" not in st.session_state:
        st.session_state.log_date = datetime.today().date()
        
    log_date = st.date_input("Filter by Date", value=st.session_state.log_date)
    
    logs = get_logs()
    if not logs.empty:
        logs['Timestamp'] = pd.to_datetime(logs['Timestamp'])
        
        start_ts = pd.to_datetime(log_date)
        end_ts = start_ts + timedelta(days=1) - timedelta(seconds=1)
        
        daily_logs = logs[(logs['Timestamp'] >= start_ts) & (logs['Timestamp'] <= end_ts)].sort_values('Timestamp', ascending=False)
        
        st.markdown(f"**Showing {len(daily_logs)} log events for: {log_date.strftime('%Y-%m-%d')}**")
        st.dataframe(daily_logs, use_container_width=True, height=500)
        
        st.download_button("Export Daily Log", daily_logs.to_csv(index=False).encode(), f"audit_log_{log_date}.csv", "text/csv")
        st.download_button("Export Full History", logs.to_csv(index=False).encode(), "full_audit_history.csv", "text/csv")
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
