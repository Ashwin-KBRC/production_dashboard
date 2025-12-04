import os
import hashlib
import base64
import requests
import csv
from pathlib import Path
from datetime import datetime, timedelta, date
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
# 2. PROFESSIONAL & ANIMATED CSS
# ========================================
st.markdown("""
<style>
    /* IMPORT FONTS - INTER for Clean, Professional look */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        scroll-behavior: smooth;
        color: #1e293b;
    }

    /* REMOVE BRANDING */
    footer {visibility: hidden !important;}
    #MainMenu {visibility: hidden;}
    header {visibility: hidden !important;}
    .stAppDeployButton {display: none !important;}
    
    /* SIDEBAR STYLING */
    [data-testid="stSidebar"] {
        background-color: #f8fafc;
        border-right: 1px solid #e2e8f0;
    }
    [data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }
    
    /* ANIMATIONS */
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .block-container {
        animation: fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1);
    }
    
    @keyframes pulse-green {
        0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
        70% { box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
        100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }

    .live-indicator {
        width: 10px;
        height: 10px;
        background-color: #10B981;
        border-radius: 50%;
        display: inline-block;
        margin-right: 8px;
        animation: pulse-green 2s infinite;
    }

    /* CARD DESIGN */
    .metric-card {
        background: white;
        border: 1px solid #f1f5f9;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 24px -6px rgba(0,0,0,0.08);
        border-color: #e2e8f0;
    }

    /* HERO BANNER - EXECUTIVE STYLE */
    .hero-banner {
        background: linear-gradient(120deg, #0f172a 0%, #334155 100%);
        color: white;
        padding: 40px;
        border-radius: 16px;
        margin-bottom: 30px;
        position: relative;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
    }

    .big-number {
        font-size: 3.5rem;
        font-weight: 800;
        letter-spacing: -1px;
        background: linear-gradient(to right, #ffffff, #cbd5e1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 5px 0;
    }
    
    .trend-badge {
        background: rgba(255,255,255,0.1);
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 500;
        backdrop-filter: blur(4px);
    }

    /* TABLE STYLING */
    .stDataFrame {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        overflow: hidden;
    }
    
    /* BUTTONS */
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        height: 45px;
        border: none;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        transition: all 0.2s;
    }
    .stButton>button:hover {
        transform: translateY(-1px);
    }
    
    /* TAB STYLING */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
        border-bottom: 1px solid #e2e8f0;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 4px 4px 0 0;
        color: #64748b;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        color: #0f172a;
        border-bottom: 2px solid #0f172a;
    }
</style>
""", unsafe_allow_html=True)

# ========================================
# 3. SETUP & AUTH
# ========================================
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = DATA_DIR / "access_logs.csv"
REQUIRED_COLS = ["Plant", "Production for the Day", "Accumulative Production"]

# CONFIGURATION
SECRETS = {}
try: SECRETS = dict(st.secrets)
except: SECRETS = {}

GITHUB_TOKEN = SECRETS.get("GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
GITHUB_REPO = SECRETS.get("GITHUB_REPO") or os.getenv("GITHUB_REPO")
GITHUB_USER = SECRETS.get("GITHUB_USER") or os.getenv("GITHUB_USER", "streamlit-bot")
GITHUB_EMAIL = SECRETS.get("GITHUB_EMAIL") or os.getenv("GITHUB_EMAIL", "streamlit@example.com")

# USERS - Added Production Profile
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
# 4. LOGIC FUNCTIONS
# ========================================
def get_greeting():
    h = datetime.now().hour
    if h < 12: return "Good Morning"
    elif 12 <= h < 18: return "Good Afternoon"
    else: return "Good Evening"

def format_m3(value):
    return f"{value:,.3f} m³"

def init_logs():
    if not LOG_FILE.exists():
        with open(LOG_FILE, 'w', newline='') as f:
            csv.writer(f).writerow(["Timestamp", "User", "Event"])

def log_event(username: str, event: str):
    init_logs()
    try:
        with open(LOG_FILE, 'a', newline='') as f:
            csv.writer(f).writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username, event])
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
        return r.ok, "Synced" if r.ok else "Sync Failed"
    except Exception as e: return False, str(e)

def safe_numeric(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()
    df2["Production for the Day"] = pd.to_numeric(df2["Production for the Day"], errors="coerce").fillna(0.0)
    df2["Accumulative Production"] = pd.to_numeric(df2["Accumulative Production"], errors="coerce")
    # Intelligent fill for accumulative: Group by plant, then fill forward
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

# ========================================
# 5. CHARTING ENGINE (PROFESSIONAL)
# ========================================
def get_theme_colors(theme_name):
    # Professional, High-Contrast Palettes
    themes = {
        "KBRC Corporate": ["#1e3a8a", "#3b82f6", "#60a5fa", "#93c5fd", "#bfdbfe"], # Professional Blue
        "Executive Obsidian": ["#0f172a", "#334155", "#475569", "#64748b", "#94a3b8"], # Grayscale/Slate
        "Swiss Clean": ["#ef4444", "#171717", "#525252", "#a3a3a3", "#d4d4d4"], # Red/Black/Grey
        "Neon Cyber": ["#f72585", "#7209b7", "#3a0ca3", "#4361ee", "#4cc9f0"], # The requested neon
        "Nature": ["#15803d", "#22c55e", "#86efac", "#166534", "#dcfce7"]
    }
    return themes.get(theme_name, themes["KBRC Corporate"])

def clean_chart_layout(fig):
    fig.update_layout(
        font=dict(family="Inter", size=12, color="#1e293b"),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=40, b=40, l=40, r=20),
        xaxis=dict(showgrid=False, linecolor='#cbd5e1'),
        yaxis=dict(showgrid=True, gridcolor='#f1f5f9', linecolor='#cbd5e1'),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified"
    )
    return fig

def create_bar_chart(df, x, y, title, colors, group=None):
    if group:
        fig = px.bar(df, x=x, y=y, color=group, barmode='group', 
                     color_discrete_sequence=colors, title=title)
    else:
        fig = px.bar(df, x=x, y=y, color=x, 
                     color_discrete_sequence=colors, title=title)
    
    fig.update_traces(
        texttemplate="%{y:,.0f}", textposition="outside",
        cliponaxis=False, width=0.6 if not group else None
    )
    return clean_chart_layout(fig)

def create_line_chart(df, x, y, title, colors, group=None):
    fig = px.line(df, x=x, y=y, color=group if group else None, 
                  color_discrete_sequence=colors, markers=True, title=title)
    fig.update_traces(line=dict(width=3), marker=dict(size=8, line=dict(width=2, color='white')))
    return clean_chart_layout(fig)

def create_pie_chart(df, names, values, title, colors):
    fig = px.pie(df, names=names, values=values, color_discrete_sequence=colors, hole=0.4, title=title)
    fig.update_traces(textposition='outside', textinfo='percent+label')
    fig.update_layout(showlegend=False, font=dict(family="Inter", size=13))
    return fig

# ========================================
# 6. MAIN APP LOGIC
# ========================================

# THEME MANAGER
if "theme" not in st.session_state: st.session_state["theme"] = "KBRC Corporate"
current_theme_colors = get_theme_colors(st.session_state["theme"])

# LOGIN SCREEN
if not st.session_state.get("logged_in", False):
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<div style='height: 100px;'></div>", unsafe_allow_html=True)
        st.markdown(f"""
        <div style="background:white; padding:40px; border-radius:20px; box-shadow:0 20px 40px -10px rgba(0,0,0,0.1); text-align:center; border:1px solid #e2e8f0;">
            <h1 style="color:#0f172a; margin-bottom:0;">KBRC</h1>
            <p style="color:#64748b; font-size:0.9rem; letter-spacing:1px; margin-bottom:30px;">PRODUCTION INTELLIGENCE</p>
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

# SIDEBAR
user = st.session_state["username"]
st.sidebar.markdown(f"""
<div style="background:white; padding:20px; border-radius:12px; border:1px solid #e2e8f0; margin-bottom:20px;">
    <div style="color:#64748b; font-size:0.8rem; font-weight:600; text-transform:uppercase;">{get_greeting()}</div>
    <div style="color:#0f172a; font-size:1.4rem; font-weight:800; margin-top:4px;">{user.title()}</div>
    <div style="margin-top:10px; display:flex; align-items:center;">
        <span class="live-indicator"></span>
        <span style="color:#10b981; font-size:0.8rem; font-weight:600;">System Active</span>
    </div>
</div>
""", unsafe_allow_html=True)

menu = ["Analytics", "Upload New Data", "Historical Archives", "Data Management"]
if user == "manager": menu.append("Audit Logs")
mode = st.sidebar.radio("Navigation", menu)

st.sidebar.markdown("---")
theme_sel = st.sidebar.selectbox("Dashboard Theme", 
                                 ["KBRC Corporate", "Executive Obsidian", "Swiss Clean", "Neon Cyber", "Nature"],
                                 index=["KBRC Corporate", "Executive Obsidian", "Swiss Clean", "Neon Cyber", "Nature"].index(st.session_state["theme"]))

if theme_sel != st.session_state["theme"]:
    st.session_state["theme"] = theme_sel
    st.rerun()

alert_threshold = st.sidebar.number_input("Alert Threshold (m³)", 50.0, step=10.0)
if st.sidebar.button("Secure Logout"):
    log_event(user, "Logout")
    st.session_state.clear()
    st.rerun()

# ========================================
# MODULE: ANALYTICS (The Innovation Hub)
# ========================================
if mode == "Analytics":
    st.title("Executive Analytics")
    
    saved = list_saved_dates()
    if len(saved) < 2:
        st.warning("Insufficient data. Please upload at least 2 days of production records.")
        st.stop()
        
    # CONTROLS
    c1, c2 = st.columns(2)
    with c1: start_d = st.date_input("Start Date", value=datetime.today() - timedelta(days=30))
    with c2: end_d = st.date_input("End Date", value=datetime.today())
    
    # DATA ENGINE
    frames = []
    for d in saved:
        try:
            df = load_saved(d)
            df['Date'] = pd.to_datetime(df['Date'])
            df = df[~df['Plant'].astype(str).str.upper().str.contains("TOTAL")] # Strict filtering
            frames.append(df)
        except: continue
        
    if not frames: st.stop()
    
    full_df = pd.concat(frames, ignore_index=True)
    mask = (full_df['Date'] >= pd.to_datetime(start_d)) & (full_df['Date'] <= pd.to_datetime(end_d))
    df_filtered = full_df[mask].copy().sort_values('Date')
    
    if df_filtered.empty:
        st.info("No data in selected range.")
        st.stop()
        
    df_filtered = safe_numeric(df_filtered)
    # Innovation: Ensure precise math by dropping duplicates
    df_filtered = df_filtered.drop_duplicates(subset=['Date', 'Plant'], keep='last')
    
    # ------------------
    # INNOVATION: KPI CALCULATIONS
    # ------------------
    total_vol = df_filtered['Production for the Day'].sum()
    avg_daily = df_filtered.groupby('Date')['Production for the Day'].sum().mean()
    days_count = df_filtered['Date'].nunique()
    
    # FORECASTING LOGIC (Simple Linear Projection)
    current_day = datetime.now().day
    days_in_month = (datetime.now().replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    days_in_month = days_in_month.day
    remaining_days = max(0, days_in_month - current_day)
    projected_total = total_vol + (avg_daily * remaining_days) if end_d.month == datetime.now().month else total_vol

    # DATA COMPLETENESS
    completeness = (days_count / ((end_d - start_d).days + 1)) * 100
    
    # HERO SECTION
    st.markdown(f"""
    <div class="hero-banner">
        <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:20px; text-align:center;">
            <div>
                <div style="font-size:0.9rem; opacity:0.8; text-transform:uppercase; letter-spacing:1px;">Total Volume</div>
                <div class="big-number">{total_vol:,.0f}</div>
                <div class="trend-badge">Period: {days_count} Days</div>
            </div>
            <div style="border-left:1px solid rgba(255,255,255,0.2); border-right:1px solid rgba(255,255,255,0.2);">
                <div style="font-size:0.9rem; opacity:0.8; text-transform:uppercase; letter-spacing:1px;">Daily Average</div>
                <div class="big-number" style="font-size:3rem;">{avg_daily:,.0f}</div>
                <div class="trend-badge">m³ / day</div>
            </div>
            <div>
                <div style="font-size:0.9rem; opacity:0.8; text-transform:uppercase; letter-spacing:1px;">Month-End Projection</div>
                <div class="big-number" style="font-size:3rem; background:linear-gradient(to right, #4ade80, #22c55e); -webkit-background-clip:text;">{projected_total:,.0f}</div>
                <div class="trend-badge">Based on avg trend</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if completeness < 90:
        st.warning(f"⚠️ Data Completeness: {completeness:.1f}%. Some days are missing from the upload history.")

    # ------------------
    # ROW 1: MARKET SHARE & TOTALS
    # ------------------
    c1, c2 = st.columns([1, 1.5])
    
    with c1:
        st.markdown("### 🥧 Production Share")
        # Aggregated by Plant
        plant_share = df_filtered.groupby('Plant')['Production for the Day'].sum().reset_index()
        fig_pie = create_pie_chart(plant_share, 'Plant', 'Production for the Day', 
                                 'Total Volume Distribution', current_theme_colors)
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with c2:
        st.markdown("### 📊 Plant Performance")
        # Horizontal bar for cleaner look
        fig_bar = px.bar(plant_share.sort_values('Production for the Day', ascending=True), 
                         x='Production for the Day', y='Plant', orientation='h',
                         color='Plant', color_discrete_sequence=current_theme_colors,
                         title="Total Production by Plant")
        fig_bar = clean_chart_layout(fig_bar)
        fig_bar.update_traces(texttemplate="%{x:,.0f}", textposition="outside")
        st.plotly_chart(fig_bar, use_container_width=True)

    # ------------------
    # ROW 2: AGGREGATION ENGINE (FIXED LOGIC)
    # ------------------
    st.markdown("---")
    st.markdown("### 📅 Temporal Aggregation")
    
    # Precise Date Grouper
    # Weekly: Sum of Daily, Max of Accumulative
    # Monthly: Sum of Daily, Max of Accumulative
    
    week_agg = df_filtered.groupby(['Plant', pd.Grouper(key='Date', freq='W-MON')]).agg({
        'Production for the Day': 'sum',
        'Accumulative Production': 'max'
    }).reset_index()
    week_agg['Period'] = week_agg['Date'].dt.strftime('Wk %W - %b')
    
    month_agg = df_filtered.groupby(['Plant', pd.Grouper(key='Date', freq='M')]).agg({
        'Production for the Day': 'sum',
        'Accumulative Production': 'max'
    }).reset_index()
    month_agg['Period'] = month_agg['Date'].dt.strftime('%B %Y')

    tab_w, tab_m = st.tabs(["Weekly Analysis", "Monthly Analysis"])
    
    with tab_w:
        c_w1, c_w2 = st.columns(2)
        with c_w1:
            st.markdown("#### Weekly Production (Sum)")
            fig_w1 = create_bar_chart(week_agg, 'Period', 'Production for the Day', 
                                    'Total Weekly Output', current_theme_colors, group='Plant')
            st.plotly_chart(fig_w1, use_container_width=True)
        with c_w2:
            st.markdown("#### Weekly Accumulative (End of Week)")
            fig_w2 = create_line_chart(week_agg, 'Period', 'Accumulative Production', 
                                     'Cumulative Reading', current_theme_colors, group='Plant')
            st.plotly_chart(fig_w2, use_container_width=True)

    with tab_m:
        c_m1, c_m2 = st.columns(2)
        with c_m1:
            st.markdown("#### Monthly Production (Sum)")
            fig_m1 = create_bar_chart(month_agg, 'Period', 'Production for the Day', 
                                    'Total Monthly Output', current_theme_colors, group='Plant')
            st.plotly_chart(fig_m1, use_container_width=True)
        with c_m2:
            st.markdown("#### Monthly Accumulative (End of Month)")
            fig_m2 = create_line_chart(month_agg, 'Period', 'Accumulative Production', 
                                     'Cumulative Reading', current_theme_colors, group='Plant')
            st.plotly_chart(fig_m2, use_container_width=True)

# ========================================
# MODULE: UPLOAD
# ========================================
elif mode == "Upload New Data":
    st.title("Daily Production Entry")
    
    c1, c2 = st.columns([2, 1])
    with c1:
        uploaded = st.file_uploader("Upload Excel File", type=["xlsx"])
    with c2:
        if "up_date" not in st.session_state: st.session_state.up_date = datetime.today()
        sel_date = st.date_input("Production Date", value=st.session_state.up_date)
        st.session_state.up_date = sel_date
        
    if uploaded:
        try:
            df = pd.read_excel(uploaded)
            df.columns = df.columns.str.strip()
            
            # Validation
            missing = [c for c in REQUIRED_COLS if c not in df.columns]
            if missing:
                st.error(f"Missing Columns: {missing}")
            else:
                st.markdown("### 📝 Preview")
                st.dataframe(df.head(), use_container_width=True)
                
                if st.button("✅ Approve & Save to Database", type="primary"):
                    df_clean = df.copy()
                    df_clean['Date'] = sel_date.strftime("%Y-%m-%d")
                    save_path = save_csv(df_clean, sel_date, overwrite=True)
                    
                    log_event(user, f"Uploaded {sel_date}")
                    attempt_git_push(save_path, f"Add {sel_date}")
                    
                    # Immediate Feedback
                    df_disp = df_clean[~df_clean["Plant"].astype(str).str.upper().str.contains("TOTAL")]
                    df_disp = safe_numeric(df_disp)
                    tot = df_disp["Production for the Day"].sum()
                    
                    st.success(f"Successfully Saved! Total Production: {format_m3(tot)}")
                    st.balloons()
                    
        except Exception as e:
            st.error(f"File Error: {e}")

# ========================================
# MODULE: DATA MANAGEMENT
# ========================================
elif mode == "Data Management":
    st.title("Database Management")
    files = list_saved_dates()
    
    if not files:
        st.info("No records found.")
    else:
        # Innovation: Data Grid Management
        records = []
        for f in files:
            try:
                # Basic metadata read
                path = DATA_DIR / f"{f}.csv"
                size = path.stat().st_size / 1024
                records.append({"Date": f, "Size (KB)": f"{size:.1f}"})
            except: pass
            
        st.markdown(f"**{len(files)}** Records Available")
        
        for f in files:
            with st.expander(f"📂 {f}", expanded=False):
                c1, c2, c3 = st.columns([1, 1, 2])
                with c1:
                    if st.button("Download", key=f"d_{f}"):
                        df = load_saved(f)
                        xl = generate_excel_report(df, f)
                        st.download_button("Save .xlsx", xl, f"{f}.xlsx")
                with c2:
                    if st.button("Delete", key=f"del_{f}", type="primary"):
                        if delete_saved(f):
                            log_event(user, f"Deleted {f}")
                            st.rerun()

# ========================================
# MODULE: HISTORICAL
# ========================================
elif mode == "Historical Archives":
    st.title("Historical Data")
    files = list_saved_dates()
    
    if not files: st.info("No data."); st.stop()
    
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
        <div style="background:{current_theme_colors[0]}; color:white; padding:30px; border-radius:12px; margin-bottom:20px;">
            <h2 style="margin:0;">{sel_d.strftime('%A, %B %d, %Y')}</h2>
            <div style="font-size:3rem; font-weight:800;">{format_m3(tot)}</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.dataframe(df, use_container_width=True)
        
        # Simple Charts for History
        c1, c2 = st.columns(2)
        with c1:
            fig = px.pie(df, names='Plant', values='Production for the Day', color_discrete_sequence=current_theme_colors)
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = px.bar(df, x='Plant', y='Production for the Day', color='Plant', color_discrete_sequence=current_theme_colors)
            st.plotly_chart(clean_chart_layout(fig), use_container_width=True)
    else:
        st.warning("No record for this date.")

# ========================================
# MODULE: LOGS
# ========================================
elif mode == "Audit Logs":
    if user != "manager": st.error("Access Restricted"); st.stop()
    st.title("Security Audit Logs")
    logs = get_logs().sort_index(ascending=False)
    st.dataframe(logs, use_container_width=True, height=500)
    st.download_button("Export CSV", logs.to_csv(index=False).encode(), "logs.csv", "text/csv")

# ========================================
# SIDEBAR FOOTER
# ========================================
st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style="font-size:0.75rem; color:#64748b; line-height:1.4;">
    <strong>Eng. Ashwin Joseph Mathew</strong><br>
    Head of IT<br>
    <a href="mailto:Ashwin.IT@kbrc.com.kw" style="color:#3b82f6; text-decoration:none;">Ashwin.IT@kbrc.com.kw</a>
</div>
""", unsafe_allow_html=True)
