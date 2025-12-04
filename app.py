import os
import hashlib
import base64
import requests
import csv
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
# 1. PAGE CONFIGURATION
# ========================================
st.set_page_config(
    page_title="KBRC Production Dashboard", 
    layout="wide", 
    page_icon="🏭",
    initial_sidebar_state="expanded"
)

# ========================================
# 2. PROFESSIONAL & ANIMATED CSS (THE "MAGIC")
# ========================================
st.markdown("""
<style>
    /* IMPORT FONTS */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap');
    
    /* GLOBAL RESET */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        scroll-behavior: smooth;
    }

    /* HIDE STREAMLIT BRANDING */
    footer {visibility: hidden !important;}
    #MainMenu {visibility: hidden;}
    header {visibility: hidden !important;}
    .stAppDeployButton {display: none !important;}
    
    /* FIX SIDEBAR (NON-COLLAPSIBLE) */
    [data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }
    
    /* ANIMATIONS: KEYFRAMES */
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
        100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }

    /* APPLY ANIMATIONS TO MAIN CONTAINERS */
    .block-container {
        animation: fadeInUp 0.8s ease-out;
    }

    /* LIVE STATUS INDICATOR */
    .live-indicator {
        width: 12px;
        height: 12px;
        background-color: #10B981;
        border-radius: 50%;
        display: inline-block;
        margin-right: 8px;
        animation: pulse 2s infinite;
    }

    /* MODERN CARD STYLING */
    .metric-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        border-color: #3b82f6;
    }

    /* HERO SECTION (GLASSMORPHISM) */
    .hero-banner {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        color: white;
        padding: 60px 40px;
        border-radius: 20px;
        text-align: center;
        margin-bottom: 30px;
        position: relative;
        overflow: hidden;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
    }
    .hero-banner::before {
        content: "";
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 60%);
        transform: rotate(30deg);
        pointer-events: none;
    }

    /* BIG NUMBER TYPOGRAPHY */
    .big-number {
        font-size: 4rem;
        font-weight: 800;
        background: linear-gradient(to right, #ffffff, #94a3b8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 10px 0;
    }

    /* RANKING CARDS */
    .rank-card {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: white;
        padding: 15px 20px;
        margin-bottom: 12px;
        border-radius: 10px;
        border-left-width: 6px;
        border-left-style: solid;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        transition: transform 0.2s;
    }
    .rank-card:hover {
        transform: scale(1.02);
    }
    
    /* CUSTOM BUTTONS */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s;
    }

    /* SIDEBAR STYLING */
    section[data-testid="stSidebar"] {
        background-color: #f8fafc;
        border-right: 1px solid #e2e8f0;
    }
</style>
""", unsafe_allow_html=True)

# ========================================
# 3. CONSTANTS & SETUP
# ========================================
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = DATA_DIR / "access_logs.csv"
REQUIRED_COLS = ["Plant", "Production for the Day", "Accumulative Production"]

# SECRETS
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

_default_users = {
    "admin": hashlib.sha256("kbrc123".encode()).hexdigest(),
    "manager": hashlib.sha256("sjk@2025".encode()).hexdigest()
}

USERS: Dict[str, str] = _default_users.copy()
if "USERS" in SECRETS and isinstance(SECRETS["USERS"], dict):
    for k, v in SECRETS["USERS"].items():
        USERS[k] = v

# ========================================
# 4. UTILITY FUNCTIONS (LOGIC)
# ========================================
def get_greeting():
    hour = datetime.now().hour
    if hour < 12: return "Good Morning"
    elif 12 <= hour < 18: return "Good Afternoon"
    else: return "Good Evening"

def format_m3(value):
    """Formats a number to 3 decimal places with m³ unit"""
    return f"{value:,.3f} m³"

def init_logs():
    if not LOG_FILE.exists():
        with open(LOG_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "User", "Event"])

def log_event(username: str, event: str):
    init_logs()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, username, event])
    except Exception as e:
        print(f"Logging error: {e}")

def get_logs() -> pd.DataFrame:
    init_logs()
    try:
        return pd.read_csv(LOG_FILE)
    except:
        return pd.DataFrame(columns=["Timestamp", "User", "Event"])

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def check_credentials(username: str, password: str) -> bool:
    if not username: return False
    user = username.strip()
    if user in USERS:
        is_valid = hash_password(password) == USERS[user]
        if is_valid: log_event(user, "Login Success")
        else: log_event(user, "Login Failed (Bad Password)")
        return is_valid
    return False

def save_csv(df: pd.DataFrame, date_obj: datetime.date, overwrite: bool = False) -> Path:
    fname = f"{date_obj.strftime('%Y-%m-%d')}.csv"
    p = DATA_DIR / fname
    if p.exists() and not overwrite:
        raise FileExistsError(f"{fname} already exists.")
    df.to_csv(p, index=False, float_format="%.3f")
    return p

def list_saved_dates() -> List[str]:
    return sorted([p.name.replace(".csv", "") for p in DATA_DIR.glob("*.csv") if "access_logs" not in p.name], reverse=True)

def load_saved(date_str: str) -> pd.DataFrame:
    p = DATA_DIR / f"{date_str}.csv"
    if not p.exists(): raise FileNotFoundError(f"File not found: {date_str}")
    return pd.read_csv(p)

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
        content = ""
        if file_path.exists():
             with open(file_path, "rb") as f:
                content = base64.b64encode(f.read()).decode()
        else: return False, "File does not exist"
             
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        resp = requests.get(url, headers=headers)
        sha = resp.json().get("sha") if resp.status_code == 200 else None
        payload = {
            "message": msg, "content": content, "branch": "main",
            "committer": {"name": GITHUB_USER, "email": GITHUB_EMAIL}
        }
        if sha: payload["sha"] = sha
        r = requests.put(url, headers=headers, json=payload)
        return r.status_code in [200, 201], ("Success" if r.ok else r.json().get("message", "Failed"))
    except Exception as e:
        return False, str(e)

def safe_numeric(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()
    # Ensure numeric types
    df2["Production for the Day"] = pd.to_numeric(df2["Production for the Day"], errors="coerce").fillna(0.0)
    df2["Accumulative Production"] = pd.to_numeric(df2["Accumulative Production"], errors="coerce")
    # Forward fill/Back fill accumulative if missing for same plant
    df2["Accumulative Production"] = df2.groupby("Plant")["Accumulative Production"].transform(lambda x: x.ffill().bfill())
    return df2

def generate_excel_report(df: pd.DataFrame, date_str: str):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Production Data', index=False, float_format="%.3f")
        workbook = writer.book
        worksheet = writer.sheets['Production Data']
        format_num = workbook.add_format({'num_format': '#,##0.000 "m³"'})
        worksheet.set_column('B:C', 18, format_num)
    output.seek(0)
    return output

# ========================================
# 5. CHARTS (UPDATED FOR PRECISION)
# ========================================
# Common layout updates for a professional look
def update_fig_layout(fig):
    fig.update_layout(
        font=dict(family="Inter, Arial", size=12),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=50, b=40, l=40, r=40),
        xaxis_gridcolor="#F1F5F9",
        yaxis_gridcolor="#F1F5F9",
        hovermode="x unified"
    )
    return fig

def pie_chart(df: pd.DataFrame, value_col: str, colors: list, title: str):
    fig = px.pie(df, names="Plant", values=value_col, color_discrete_sequence=colors, title=title)
    fig.update_traces(
        textinfo="percent+label", 
        textfont=dict(size=14, color="black"),
        hovertemplate="<b>%{label}</b><br>%{value:,.3f} m³<br>(%{percent})"
    )
    fig.update_layout(title_font=dict(size=18, family="Inter"))
    return fig

def bar_chart(df: pd.DataFrame, value_col: str, colors: list, title: str):
    df = df.sort_values(value_col, ascending=False)
    fig = px.bar(df, x="Plant", y=value_col, color="Plant", color_discrete_sequence=colors, title=title,
                 text=df[value_col]) # Text handled in traces
    fig.update_traces(
        texttemplate="%{y:,.3f} m³",
        textposition="outside",
        textfont=dict(size=12, color="#334155"),
        cliponaxis=False,
        hovertemplate="<b>%{x}</b><br>%{y:,.3f} m³"
    )
    return update_fig_layout(fig)

def line_chart(df: pd.DataFrame, value_col: str, colors: list, title: str):
    fig = px.line(df, x="Plant", y=value_col, markers=True, title=title, color_discrete_sequence=colors)
    fig.update_traces(
        marker=dict(size=8, line=dict(width=2, color="white")),
        line=dict(width=3),
        texttemplate="%{y:,.3f} m³",
        textposition="top center",
        hovertemplate="<b>%{x}</b><br>%{y:,.3f} m³"
    )
    return update_fig_layout(fig)

def area_chart(df: pd.DataFrame, value_col: str, colors: list, title: str):
    fig = px.area(df, x="Plant", y=value_col, color="Plant", color_discrete_sequence=colors, title=title)
    fig.update_traces(
        line=dict(width=2), opacity=0.7,
        hovertemplate="<b>%{x}</b><br>%{y:,.3f} m³"
    )
    return update_fig_layout(fig)

def aggregated_bar_chart(df: pd.DataFrame, value_col: str, group_col: str, base_colors: list, title: str):
    # Sort and color logic similar to before, but with updated precision
    agg_df = df.sort_values([group_col, value_col], ascending=[True, False])
    
    unique_groups = agg_df[group_col].unique()
    palette_map = {}
    
    # Generate palettes - Using the base_colors passed from the selected theme to keep it consistent
    # We will create variations of the theme colors for the groups
    
    # If base_colors is small, extend it
    extended_colors = base_colors * 5
    
    for i, group in enumerate(unique_groups):
        # Assign a slice of colors to each group to ensure variety but within theme
        start_idx = (i * 2) % len(extended_colors)
        palette = extended_colors[start_idx:start_idx+3]
        if not palette: palette = base_colors # Fallback
        palette_map[str(group)] = palette
    
    color_discrete_map = {str(g): palette_map[str(g)][0] for g in unique_groups}

    fig = px.bar(
        agg_df, x="Plant", y=value_col, color=group_col,
        color_discrete_map=color_discrete_map, title=title,
        barmode='group'
    )
    
    fig.update_traces(
        texttemplate="%{y:,.3f} m³",
        textposition="outside",
        textfont=dict(size=11, color="black"),
        cliponaxis=False,
        hovertemplate="<b>%{x}</b><br>%{y:,.3f} m³"
    )

    # Manual color override for KABD specific request if needed, but keeping theme consistent is requested
    # We will prioritize the theme colors as requested "let whatever theme i set be applied"

    return update_fig_layout(fig)

# ========================================
# 6. THEMES
# ========================================
COLOR_THEMES = {
    "Modern Slate": ["#475569", "#64748b", "#94a3b8", "#cbd5e1", "#f1f5f9"],
    "Ocean Breeze": ["#0ea5e9", "#38bdf8", "#7dd3fc", "#bae6fd", "#e0f2fe"],
    "Sunset Glow": ["#ea580c", "#f97316", "#fb923c", "#fdba74", "#ffedd5"],
    "Nature": ["#16a34a", "#22c55e", "#4ade80", "#86efac", "#dcfce7"],
    "Corporate Blue": ["#1e40af", "#3b82f6", "#60a5fa", "#93c5fd", "#dbeafe"],
    "Neon Cyber": ["#f72585", "#7209b7", "#3a0ca3", "#4361ee", "#4cc9f0"],
    "Forest Rain": ["#2d6a4f", "#40916c", "#52b788", "#74c69d", "#95d5b2"],
    "Cherry Blossom": ["#590d22", "#800f2f", "#a4133c", "#c9184a", "#ff4d6d"],
    "Royal Purple": ["#240046", "#3c096c", "#5a189a", "#7b2cbf", "#9d4edd"],
    "Earth & Sky": ["#8d6e63", "#a1887f", "#bcaaa4", "#81d4fa", "#4fc3f7"],
}

if "theme" not in st.session_state: st.session_state["theme"] = "Corporate Blue"
theme_colors = COLOR_THEMES.get(st.session_state["theme"], COLOR_THEMES["Corporate Blue"])

# ========================================
# 7. MAIN UI & AUTH
# ========================================

# LOGIN UI
if not st.session_state.get("logged_in", False):
    st.markdown("""
    <div style='text-align: center; margin-top: 100px; animation: fadeInUp 1s ease-out;'>
        <h1 style='color:#1e293b; font-size: 3rem;'>KBRC Production</h1>
        <p style='color:#64748b; font-size: 1.2rem;'>Secure Dashboard Access</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<div style='background:white; padding:40px; border-radius:15px; box-shadow:0 20px 25px -5px rgba(0,0,0,0.1); border:1px solid #e2e8f0;'>", unsafe_allow_html=True)
        with st.form("login_form"):
            username = st.text_input("Username", key="login_user")
            password = st.text_input("Password", type="password", key="login_pwd")
            if st.form_submit_button("🔒 Sign in", type="primary"):
                if check_credentials(username, password):
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = username.strip()
                    st.rerun()
                else:
                    st.error("Invalid credentials")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# LOGGED IN UI
current_user = st.session_state.get('username', 'User')

# Sidebar
st.sidebar.markdown(f"""
<div style="background: white; padding: 20px; border-radius: 10px; border: 1px solid #e2e8f0; margin-bottom: 20px;">
    <div style="font-size: 0.9rem; color: #64748b; margin-bottom: 5px;">{get_greeting()}</div>
    <div style="font-size: 1.5rem; font-weight: 800; color: #1e293b;">{current_user.title()}</div>
    <div style="margin-top: 10px; display: flex; align-items: center; font-size: 0.8rem; color: #10B981;">
        <span class="live-indicator"></span> System Online
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.title("Navigation")

available_modes = ["Upload New Data", "View Historical Data", "Manage Data", "Analytics"]
if current_user == "manager":
    available_modes.append("Logs")

mode = st.sidebar.radio("Select Module", available_modes)

st.sidebar.markdown("---")
theme_choice = st.sidebar.selectbox("🎨 UI Theme", list(COLOR_THEMES.keys()), index=list(COLOR_THEMES.keys()).index(st.session_state["theme"]))
if theme_choice != st.session_state["theme"]:
    st.session_state["theme"] = theme_choice
    st.rerun()
theme_colors = COLOR_THEMES[theme_choice]

alert_threshold = st.sidebar.number_input("Alert threshold (m³)", min_value=0.0, value=50.0, step=0.5)

if st.sidebar.button("Logout"):
    log_event(current_user, "Logout")
    del st.session_state["logged_in"]
    del st.session_state["username"]
    st.rerun()

# ========================================
# 8. APP MODES
# ========================================

# --- UPLOAD MODE ---
if mode == "Upload New Data":
    st.title("Daily Entry")
    st.markdown("Upload the daily production Excel sheet. The system will automatically calculate totals and check against thresholds.")
    
    uploaded = st.file_uploader("Drop Excel file here", type=["xlsx"])
    
    if "upload_date" not in st.session_state: st.session_state.upload_date = datetime.today()
    selected_date = st.date_input("Date of Record", value=st.session_state.upload_date)
    st.session_state.upload_date = selected_date

    if uploaded:
        try:
            df_uploaded = pd.read_excel(uploaded)
            df_uploaded.columns = df_uploaded.columns.str.strip()
        except Exception as e:
            st.error(f"Error reading file: {e}")
            st.stop()
            
        missing = [c for c in REQUIRED_COLS if c not in df_uploaded.columns]
        if missing:
            st.error(f"Missing columns: {missing}")
        else:
            st.info("Previewing Data...")
            st.dataframe(df_uploaded.head(), use_container_width=True)
            
            col_save1, col_save2 = st.columns([1, 4])
            with col_save1:
                overwrite = st.checkbox("Overwrite?")
            
            if st.button("🚀 Process & Save Data", type="primary"):
                df_save = df_uploaded.copy()
                df_save["Date"] = selected_date.strftime("%Y-%m-%d")
                
                try:
                    saved_path = save_csv(df_save, selected_date, overwrite=overwrite)
                    log_event(current_user, f"Uploaded file for {selected_date}") # Log upload
                    attempt_git_push(saved_path, f"Add {selected_date}")
                    
                    st.success("Data successfully saved and synced!")
                    
                    # Process for Display
                    df_display = df_save[~df_save["Plant"].astype(str).str.upper().str.contains("TOTAL")]
                    df_display = safe_numeric(df_display)
                    
                    total_daily = df_display["Production for the Day"].sum()
                    total_acc = df_display["Accumulative Production"].sum()

                    # DISPLAY RESULTS
                    st.markdown("---")
                    col_m1, col_m2 = st.columns(2)
                    with col_m1:
                        st.markdown(f"""
                        <div class="metric-card">
                            <h3 style="margin:0; color:#64748b; font-size:1rem;">Daily Total</h3>
                            <div style="font-size:2.5rem; font-weight:800; color:#0f172a;">{format_m3(total_daily)}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with col_m2:
                         st.markdown(f"""
                        <div class="metric-card">
                            <h3 style="margin:0; color:#64748b; font-size:1rem;">Accumulative Total</h3>
                            <div style="font-size:2.5rem; font-weight:800; color:#3b82f6;">{format_m3(total_acc)}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # ALERTS
                    alerts = df_display[df_display["Production for the Day"] < alert_threshold]
                    if not alerts.empty:
                        st.warning("⚠️ Production Alerts (Below Threshold)")
                        for _, r in alerts.iterrows():
                            st.write(f"• **{r['Plant']}**: {format_m3(r['Production for the Day'])}")
                    
                    # CHARTS
                    c1, c2 = st.columns(2)
                    with c1: st.plotly_chart(pie_chart(df_display, "Production for the Day", theme_colors, "Daily Share"), use_container_width=True)
                    with c2: st.plotly_chart(bar_chart(df_display, "Production for the Day", theme_colors, "Daily Production"), use_container_width=True)
                    
                    st.plotly_chart(line_chart(df_display, "Production for the Day", theme_colors, "Trend Line"), use_container_width=True)
                    st.plotly_chart(area_chart(df_display, "Production for the Day", theme_colors, "Flow Area"), use_container_width=True)

                    st.markdown("#### Accumulative Charts")
                    acc_df = df_display[["Plant", "Accumulative Production"]].copy()
                    st.plotly_chart(bar_chart(acc_df, "Accumulative Production", theme_colors, "Accumulative Total"), use_container_width=True)
                    st.plotly_chart(line_chart(acc_df, "Accumulative Production", theme_colors, "Accumulative Trend"), use_container_width=True)
                    st.plotly_chart(area_chart(acc_df, "Accumulative Production", theme_colors, "Accumulative Flow"), use_container_width=True)

                    # DOWNLOAD
                    excel_file = generate_excel_report(df_display, selected_date.strftime("%Y-%m-%d"))
                    st.download_button("📥 Download Official Report", excel_file, f"Production_{selected_date}.xlsx", type="secondary")
                    
                except Exception as e:
                    st.error(f"Error: {e}")

# --- HISTORICAL MODE ---
elif mode == "View Historical Data":
    st.title("Historical Archives")
    saved_list = list_saved_dates()
    
    if not saved_list:
        st.info("No archives found.")
        st.stop()
        
    if "hist_date" not in st.session_state: st.session_state.hist_date = datetime.strptime(saved_list[0], "%Y-%m-%d").date()
    
    selected_date = st.date_input("Select Date", value=st.session_state.hist_date)
    st.session_state.hist_date = selected_date
    selected = selected_date.strftime("%Y-%m-%d")
    
    if selected not in saved_list:
        st.warning("No record for this date.")
    else:
        df_hist = load_saved(selected)
        df_hist = df_hist[~df_hist["Plant"].astype(str).str.upper().str.contains("TOTAL")]
        df_hist = safe_numeric(df_hist)
        total_daily = df_hist["Production for the Day"].sum()
        
        # HERO BANNER
        st.markdown(f"""
        <div class="hero-banner">
            <h2 style="font-weight: 300; opacity: 0.9; margin:0;">TOTAL PRODUCTION</h2>
            <div class="big-number">{format_m3(total_daily)}</div>
            <p style="font-weight: 600; opacity: 0.8;">{selected_date.strftime('%A, %B %d, %Y')}</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.dataframe(df_hist, use_container_width=True)
        
        tab1, tab2 = st.tabs(["Daily Analysis", "Accumulative Analysis"])
        
        with tab1:
            c1, c2 = st.columns(2)
            with c1: st.plotly_chart(pie_chart(df_hist, "Production for the Day", theme_colors, "Share"), use_container_width=True)
            with c2: st.plotly_chart(bar_chart(df_hist, "Production for the Day", theme_colors, "Production Levels"), use_container_width=True)
            st.plotly_chart(line_chart(df_hist, "Production for the Day", theme_colors, "Daily Trend"), use_container_width=True)
            st.plotly_chart(area_chart(df_hist, "Production for the Day", theme_colors, "Flow Volume"), use_container_width=True)
            
        with tab2:
            acc_hist = df_hist.sort_values("Accumulative Production", ascending=False)
            st.plotly_chart(bar_chart(acc_hist, "Accumulative Production", theme_colors, "Total Accumulative"), use_container_width=True)
            st.plotly_chart(line_chart(acc_hist, "Accumulative Production", theme_colors, "Accumulative Trend"), use_container_width=True)
            st.plotly_chart(area_chart(acc_hist, "Accumulative Production", theme_colors, "Accumulative Flow"), use_container_width=True)

        excel_file = generate_excel_report(df_hist, selected)
        st.download_button("📥 Download Report", excel_file, f"Archive_{selected}.xlsx")

# --- ANALYTICS MODE ---
elif mode == "Analytics":
    st.title("Performance Analytics")
    
    saved = list_saved_dates()
    if len(saved) < 2:
        st.warning("Insufficient data. Please upload at least 2 days of records.")
        st.stop()
        
    # Date Range
    if "an_start" not in st.session_state: st.session_state.an_start = datetime.today() - timedelta(days=30)
    if "an_end" not in st.session_state: st.session_state.an_end = datetime.today()
    
    c1, c2 = st.columns(2)
    with c1: start = st.date_input("Start", value=st.session_state.an_start)
    with c2: end = st.date_input("End", value=st.session_state.an_end)
    st.session_state.an_start = start
    st.session_state.an_end = end
    
    # Process All Data
    frames = []
    for d in saved:
        try:
            df = load_saved(d)
            df["Date"] = pd.to_datetime(df["Date"])
            df = df[~df["Plant"].astype(str).str.upper().str.contains("TOTAL")]
            frames.append(df)
        except: continue
        
    if not frames: st.stop()
    
    all_df = pd.concat(frames, ignore_index=True)
    mask = (all_df['Date'] >= pd.to_datetime(start)) & (all_df['Date'] <= pd.to_datetime(end))
    filtered = all_df[mask].copy()
    
    if filtered.empty:
        st.warning("No data in range.")
        st.stop()
        
    filtered = safe_numeric(filtered)
    # Deduplicate based on Date/Plant to ensure precise math
    filtered = filtered.drop_duplicates(subset=['Date', 'Plant'], keep='last')
    
    total_period = filtered["Production for the Day"].sum()
    
    # HERO STAT
    st.markdown(f"""
    <div class="hero-banner">
        <h2 style="font-weight: 300; opacity: 0.9; margin:0;">PERIOD AGGREGATE</h2>
        <div class="big-number">{format_m3(total_period)}</div>
        <p style="font-weight: 600; opacity: 0.8;">All Plants • {start.strftime('%b %d')} - {end.strftime('%b %d, %Y')}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # TOP PERFORMERS LOGIC
    avg_daily = filtered.groupby('Plant')['Production for the Day'].mean()
    top_avg = avg_daily.sort_values(ascending=False).head(3).reset_index()
    
    # Get latest accumulative for period
    latest_date = filtered['Date'].max()
    latest_acc = filtered[filtered['Date'] == latest_date][['Plant', 'Accumulative Production']]
    top_acc = latest_acc.sort_values('Accumulative Production', ascending=False).head(3).reset_index(drop=True)
    
    colA, colB = st.columns(2)
    
    with colA:
        st.subheader("🏆 Top Avg Daily Output")
        for i, row in top_avg.iterrows():
            rank = i + 1
            color = "#F59E0B" if rank == 1 else ("#94A3B8" if rank == 2 else "#B45309")
            st.markdown(f"""
            <div class="rank-card" style="border-left-color: {color};">
                <div>
                    <span style="font-weight:800; color:{color}; font-size:1.2rem; margin-right:10px;">#{rank}</span>
                    <span style="font-weight:600; color:#334155;">{row['Plant']}</span>
                </div>
                <div style="font-weight:700; color:#1e293b;">{format_m3(row['Production for the Day'])}</div>
            </div>
            """, unsafe_allow_html=True)

    with colB:
        st.subheader("📦 Top Accumulative Total")
        for i, row in top_acc.iterrows():
            rank = i + 1
            color = "#3B82F6" if rank == 1 else ("#60A5FA" if rank == 2 else "#93C5FD")
            st.markdown(f"""
            <div class="rank-card" style="border-left-color: {color};">
                <div>
                    <span style="font-weight:800; color:{color}; font-size:1.2rem; margin-right:10px;">#{rank}</span>
                    <span style="font-weight:600; color:#334155;">{row['Plant']}</span>
                </div>
                <div style="font-weight:700; color:#1e293b;">{format_m3(row['Accumulative Production'])}</div>
            </div>
            """, unsafe_allow_html=True)

    # AGGREGATION CHARTS
    st.markdown("---")
    filtered['Week'] = filtered['Date'].dt.to_period('W').apply(lambda r: r.start_time)
    filtered['Month'] = filtered['Date'].dt.to_period('M').astype(str)
    filtered['Custom_Week'] = ((filtered['Date'] - filtered['Date'].min()).dt.days // 7) + 1
    
    # Production Data
    wk_prod = filtered.groupby(['Week', 'Plant'], as_index=False)['Production for the Day'].sum()
    mo_prod = filtered.groupby(['Month', 'Plant'], as_index=False)['Production for the Day'].sum()
    
    # Accumulative Data (Latest in period)
    wk_acc = filtered.groupby(['Week', 'Plant'], as_index=False)['Accumulative Production'].last()
    mo_acc = filtered.groupby(['Month', 'Plant'], as_index=False)['Accumulative Production'].last()
    
    tab_prod, tab_acc = st.tabs(["📊 Weekly/Monthly Production", "📈 Weekly/Monthly Accumulative"])
    
    with tab_prod:
        st.subheader("Weekly Sums")
        st.plotly_chart(aggregated_bar_chart(wk_prod, "Production for the Day", "Week", theme_colors, ""), use_container_width=True)
        
        st.subheader("Monthly Sums")
        st.plotly_chart(aggregated_bar_chart(mo_prod, "Production for the Day", "Month", theme_colors, ""), use_container_width=True)

    with tab_acc:
        st.subheader("Weekly Accumulative Snapshot")
        st.plotly_chart(aggregated_bar_chart(wk_acc, "Accumulative Production", "Week", theme_colors, ""), use_container_width=True)
        
        st.subheader("Monthly Accumulative Snapshot")
        st.plotly_chart(aggregated_bar_chart(mo_acc, "Accumulative Production", "Month", theme_colors, ""), use_container_width=True)

# --- MANAGE MODE ---
elif mode == "Manage Data":
    st.title("Data Management")
    saved_list = list_saved_dates()
    
    if not saved_list: st.info("No files found.")
    else:
        st.markdown("Manage your uploaded datasets here. You can download backups or remove incorrect entries.")
        for date_str in saved_list:
            with st.expander(f"📄 {date_str}"):
                c1, c2 = st.columns([1, 1])
                with c1:
                    if st.button("Download File", key=f"dl_{date_str}"):
                        df = load_saved(date_str)
                        excel = generate_excel_report(df, date_str)
                        st.download_button("Click to Save", excel, f"{date_str}.xlsx")
                with c2:
                    if st.button("Delete File", key=f"del_{date_str}", type="primary"):
                        if delete_saved(date_str):
                            log_event(current_user, f"Deleted {date_str}")
                            st.rerun()

# --- LOGS MODE ---
elif mode == "Logs":
    if current_user != "manager":
        st.error("Restricted Area")
    else:
        st.title("System Audit Logs")
        logs = get_logs().sort_index(ascending=False)
        st.dataframe(logs, use_container_width=True, height=600)
        st.download_button("Download CSV", logs.to_csv(index=False).encode('utf-8'), "logs.csv", "text/csv")

# ========================================
# 9. FOOTER
# ========================================
st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style="font-size:0.85rem; color:#64748b;">
    <strong>Eng. Ashwin Joseph Mathew</strong><br>
    Head of IT<br>For any assistance or Technical issues<br>
    <a href="mailto:Ashwin.IT@kbrc.com.kw" style="text-decoration:none; color:#3b82f6;">Ashwin.IT@kbrc.com.kw</a>
</div>
""", unsafe_allow_html=True)



