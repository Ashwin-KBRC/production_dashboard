import os
import hashlib
import base64
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, List, Optional
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import io
import xlsxwriter
import logging

# ========================================
# CONFIGURATION & LOGGING
# ========================================
st.set_page_config(page_title="Production Dashboard", layout="wide", page_icon="Fire")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================================
# PATHS & CONSTANTS
# ========================================
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
REQUIRED_COLS = ["Plant", "Production for the Day", "Accumulative Production"]
MAX_FILE_AGE_DAYS = 365

# ========================================
# SECRETS & AUTHENTICATION
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
# COLOR THEMES — LAVA FLOW DEFAULT
# ========================================
COLOR_THEMES = {
    "Modern Slate": ["#4A6572", "#7D9D9C", "#A4C3B2", "#C9D7D6", "#E5ECE9", "#6B7280", "#9CA3AF", "#D1D5DB", "#E5E7EB", "#F9FAFB"],
    "Sunset Glow": ["#F28C38", "#E96E5D", "#D66BA0", "#A56EC3", "#6B5B95", "#F1A340", "#E76F51", "#D15B8A", "#9F5DBB", "#5F5290"],
    "Ocean Breeze": ["#2E8B8B", "#48A9A6", "#73C2A5", "#9DE0A4", "#C5E8A3", "#3A9D9D", "#54B5B2", "#7FCEB1", "#A9EBAF", "#D1F4B7"],
    "Corporate": ["#FF4040", "#4040FF", "#40FF40", "#FF8000", "#FFFF40", "#CC0000", "#0000CC", "#00CC00", "#CC6600", "#CCCC00"],
    "Midnight Sky": ["#283593", "#3F51B5", "#673AB7", "#9C27B0", "#BA68C8", "#1A237E", "#303F9F", "#512DA8", "#8E24AA", "#AB47BC"],
    "Spring Bloom": ["#D4A59A", "#C2D4B7", "#A9C5A7", "#8DB596", "#71A684", "#D8A08D", "#B6C8A9", "#9DB99A", "#82A98B", "#669A7A"],
    "Executive Suite": ["#4A4A4A", "#1E3A8A", "#D4A017", "#8A8A8A", "#A3BFFA", "#333333", "#172F6E", "#B38600", "#6E6E6E", "#8CAFE6"],
    "Boardroom Blue": ["#2A4066", "#4682B4", "#B0C4DE", "#C0C0C0", "#87CEEB", "#1F2F4B", "#357ABD", "#9BAEBF", "#A6A6A6", "#6BAED6"],
    "Corporate Ivory": ["#F5F5F5", "#008080", "#800000", "#D3D3D3", "#CD853F", "#ECECEC", "#006666", "#660000", "#B0B0B0", "#B27A3D"],
    "Lava Flow": ["#FF4500", "#FF6B35", "#F7931E", "#FFD23F", "#FF8C00", "#1A1A1A", "#FF5733", "#FFC300", "#FF5733", "#DAF7A6"],
    "Neon Pulse": ["#00FF00", "#00FFFF", "#FF00FF", "#FFFF00", "#00FF7F", "#1E1E1E", "#39FF14", "#00CED1", "#FF1493", "#FFD700"],
    "Gold Standard": ["#FFD700", "#FFA500", "#DAA520", "#B8860B", "#CD7F32", "#2F2F2F", "#FFCC00", "#FF9900", "#CC9900", "#996600"],
}
if "theme" not in st.session_state:
    st.session_state["theme"] = "Lava Flow"
elif st.session_state["theme"] not in COLOR_THEMES:
    st.session_state["theme"] = "Lava Flow"

# ========================================
# AUTHENTICATION FUNCTIONS
# ========================================
def hash_password(password: str) -> str:
    """Hash password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def check_credentials(username: str, password: str) -> bool:
    """Validate user credentials."""
    if not username or not password:
        return False
    user = username.strip()
    return user in USERS and hash_password(password) == USERS[user]

def login_ui():
    """Display login form in sidebar."""
    st.sidebar.subheader("Login Required")
    with st.sidebar.form("login_form"):
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pwd")
        submitted = st.form_submit_button("Sign In")
        if submitted:
            if check_credentials(username, password):
                st.session_state["logged_in"] = True
                st.session_state["username"] = username.strip()
                st.success("Login successful!")
                st.rerun()
            else:
                st.sidebar.error("Invalid username or password")

def logout():
    """Clear session and log out."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def logged_in() -> bool:
    """Check if user is logged in."""
    return st.session_state.get("logged_in", False)

# ========================================
# FILE I/O & GIT HELPERS
# ========================================
def save_csv(df: pd.DataFrame, date_obj: datetime.date, overwrite: bool = False) -> Path:
    """Save DataFrame to CSV with date-based filename."""
    fname = f"{date_obj.strftime('%Y-%m-%d')}.csv"
    p = DATA_DIR / fname
    if p.exists() and not overwrite:
        raise FileExistsError(f"File {fname} already exists. Use overwrite=True.")
    df.to_csv(p, index=False, float_format="%.3f")
    logger.info(f"Saved data to {p}")
    return p

def list_saved_dates() -> List[str]:
    """List all saved dates in descending order."""
    files = [p.name.replace(".csv", "") for p in DATA_DIR.glob("*.csv")]
    return sorted(files, reverse=True)

def load_saved(date_str: str) -> pd.DataFrame:
    """Load CSV data for a specific date."""
    p = DATA_DIR / f"{date_str}.csv"
    if not p.exists():
        raise FileNotFoundError(f"Data not found for {date_str}")
    df = pd.read_csv(p)
    df['Date'] = pd.to_datetime(df['Date']).dt.date
    return df

def delete_saved(date_str: str) -> bool:
    """Delete a saved CSV file."""
    p = DATA_DIR / f"{date_str}.csv"
    if p.exists():
        p.unlink()
        logger.info(f"Deleted {p}")
        return True
    return False

def attempt_git_push(file_path: Path, msg: str) -> Tuple[bool, str]:
    """Push file to GitHub if credentials provided."""
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
        logger.error(f"Git push failed: {e}")
        return False, str(e)

# ========================================
# DATA PROCESSING HELPERS
# ========================================
def safe_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Convert production columns to numeric with error handling."""
    df = df.copy()
    df["Production for the Day"] = pd.to_numeric(df["Production for the Day"], errors="coerce").fillna(0.0)
    df["Accumulative Production"] = pd.to_numeric(df["Accumulative Production"], errors="coerce").fillna(0.0)
    return df

def generate_excel_report(df: pd.DataFrame, date_str: str) -> io.BytesIO:
    """Generate Excel report in memory."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Production Data', index=False, float_format="%.3f")
        workbook = writer.book
        worksheet = writer.sheets['Production Data']
        format_bold = workbook.add_format({'bold': True, 'font_color': '#FFD700'})
        worksheet.set_column('A:D', 20, format_bold)
    output.seek(0)
    return output

# ========================================
# CHART: CLEAN STATIC BAR — BOLD & PROFESSIONAL
# ========================================
def clean_bar_chart(df: pd.DataFrame, value_col: str, group_col: str, colors: list, title: str):
    """Generate clean, bold, static bar chart."""
    if df.empty or value_col not in df.columns:
        fig = go.Figure()
        fig.add_annotation(text="No data available", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                           font=dict(size=20, color="white"))
        fig.update_layout(title=title, title_font=dict(size=22, family="Arial Black", color="#FFD700"),
                          plot_bgcolor="#1a1a1a", paper_bgcolor="#111")
        return fig

    df = df.copy()
    df[value_col] = df[value_col].astype('float64')
    df = df.sort_values(value_col, ascending=False)

    fig = go.Figure()
    for i, plant in enumerate(df["Plant"].unique()):
        sub = df[df["Plant"] == plant]
        val = sub[value_col].sum()
        group = sub[group_col].iloc[0] if group_col in sub.columns and not sub[group_col].empty else ""
        fig.add_trace(go.Bar(
            x=[plant], y=[val], name=f"{group} - {plant}",
            marker_color=colors[i % len(colors)],
            text=f"{val:,.1f}", textposition="outside",
            textfont=dict(size=16, family="Arial Black", color="white"),
            marker=dict(line=dict(width=3, color="white"))
        ))

    fig.update_layout(
        title=title,
        title_font=dict(size=22, family="Arial Black", color="#FFD700"),
        barmode='stack',
        plot_bgcolor="#1a1a1a",
        paper_bgcolor="#111111",
        font=dict(color="white", size=14, family="Arial"),
        legend=dict(font=dict(size=14, family="Arial Black"), bgcolor="#333", bordercolor="#FFD700", borderwidth=1),
        margin=dict(t=100, b=100, l=80, r=80),
        xaxis=dict(
            title="Plant", title_font=dict(size=18, family="Arial Black"),
            tickfont=dict(size=14, family="Arial Black"), gridcolor="#444"
        ),
        yaxis=dict(
            title="m³", title_font=dict(size=18, family="Arial Black"),
            tickfont=dict(size=14, family="Arial"), gridcolor="#444"
        )
    )

    # Highlight KABD
    for trace in fig.data:
        if 'KABD' in trace.name.upper():
            trace.marker.color = "#FF4500"
            trace.textfont.color = "#FFD700"
            trace.textfont.size = 18
            trace.textfont.family = "Arial Black"

    return fig

# ========================================
# LOGIN VALIDATION
# ========================================
if not logged_in():
    st.title("Production Dashboard — Login Required")
    login_ui()
    st.sidebar.write("---")
    st.sidebar.caption("Contact admin for credentials.")
    st.stop()

# ========================================
# MAIN UI & SIDEBAR
# ========================================
st.sidebar.title("Dashboard Controls")
st.sidebar.write(f"**Logged in as:** {st.session_state.get('username', 'User')}")
if st.sidebar.button("Logout", use_container_width=True):
    logout()

mode = st.sidebar.radio("Select Mode", ["Upload New Data", "View Historical Data", "Manage Data", "Analytics"], index=3)
theme_choice = st.sidebar.selectbox("Theme", list(COLOR_THEMES.keys()), 
                                   index=list(COLOR_THEMES.keys()).index(st.session_state["theme"]))
theme_colors = COLOR_THEMES[theme_choice]
alert_threshold = st.sidebar.number_input("Alert Threshold (m³)", min_value=0.0, value=50.0, step=0.5)
st.sidebar.markdown("---")
st.sidebar.caption("Upload Excel: Plant | Production for the Day | Accumulative Production")
st.title("PRODUCTION DASHBOARD")

# ========================================
# MODE: UPLOAD NEW DATA
# ========================================
if mode == "Upload New Data":
    st.header("Upload Daily Production Data")
    uploaded = st.file_uploader("Choose Excel file (.xlsx)", type=["xlsx"])
    selected_date = st.date_input("Date for this data", value=datetime.today())

    if uploaded:
        try:
            df_uploaded = pd.read_excel(uploaded)
            df_uploaded.columns = df_uploaded.columns.str.strip()
        except Exception as e:
            st.error(f"Failed to read file: {e}")
            st.stop()

        missing = [c for c in REQUIRED_COLS if c not in df_uploaded.columns]
        if missing:
            st.error(f"Missing required columns: {', '.join(missing)}")
        else:
            st.subheader("Data Preview")
            st.dataframe(df_uploaded.head(20), use_container_width=True)

            overwrite = st.checkbox("Overwrite existing file?", value=False)
            confirm = st.checkbox("I confirm the data is correct and ready to save")

            if confirm and st.button("Save & Upload", type="primary"):
                df_save = df_uploaded.copy()
                df_save["Date"] = selected_date.strftime("%Y-%m-%d")
                try:
                    saved_path = save_csv(df_save, selected_date, overwrite=overwrite)
                    st.success(f"Data saved: `{saved_path.name}`")
                except FileExistsError as e:
                    st.error(str(e))
                    st.stop()

                pushed, msg = attempt_git_push(saved_path, f"Add production data for {selected_date}")
                if pushed:
                    st.success(f"GitHub sync: {msg}")
                else:
                    st.warning(f"GitHub sync failed: {msg}")

                df_display = df_save[~df_save["Plant"].astype(str).str.upper().str.contains("TOTAL")]
                df_display = safe_numeric(df_display)

                st.markdown("### Summary")
                total_daily = df_display["Production for the Day"].sum()
                total_acc = df_display["Accumulative Production"].sum()
                st.write(f"- **Daily Production:** {total_daily:,.1f} m³")
                st.write(f"- **Accumulative:** {total_acc:,.1f} m³")

                alerts = df_display[df_display["Production for the Day"] < alert_threshold]
                if not alerts.empty:
                    st.warning("Plants below threshold:")
                    for _, r in alerts.iterrows():
                        st.write(f"• {r['Plant']}: {r['Production for the Day']:.1f} m³")

                st.markdown("### Charts")
                c1, c2 = st.columns(2)
                with c1:
                    fig_pie = px.pie(df_display, names="Plant", values="Production for the Day",
                                     color_discrete_sequence=theme_colors, title="Production Share")
                    fig_pie.update_traces(textinfo="percent+label", textfont_size=14)
                    st.plotly_chart(fig_pie, use_container_width=True)
                with c2:
                    fig_bar = px.bar(df_display, x="Plant", y="Production for the Day",
                                     color="Plant", color_discrete_sequence=theme_colors,
                                     text=df_display["Production for the Day"].round(1))
                    fig_bar.update_traces(texttemplate="%{text:,.1f}", textposition="outside")
                    st.plotly_chart(fig_bar, use_container_width=True)

                top_plant = df_display.loc[df_display["Production for the Day"].idxmax(), "Plant"]
                top_value = df_display["Production for the Day"].max()
                st.success(f"**Top Performer:** {top_plant} — {top_value:,.1f} m³")

                excel_file = generate_excel_report(df_display, selected_date.strftime("%Y-%m-%d"))
                st.download_button("Download Excel Report", excel_file,
                                   f"production_report_{selected_date}.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ========================================
# MODE: VIEW HISTORICAL DATA
# ========================================
elif mode == "View Historical Data":
    st.header("View Historical Production")
    saved_dates = list_saved_dates()
    if not saved_dates:
        st.info("No historical data available.")
    else:
        default_date = datetime.strptime(saved_dates[0], "%Y-%m-%d").date()
        selected_date = st.date_input("Select Date", value=default_date)
        date_str = selected_date.strftime("%Y-%m-%d")

        if date_str not in saved_dates:
            st.warning("No data for selected date.")
        else:
            df = load_saved(date_str)
            df_disp = df[~df["Plant"].astype(str).str.upper().str.contains("TOTAL")]
            df_disp = safe_numeric(df_disp)

            st.subheader(f"Production Data — {date_str}")
            st.dataframe(df_disp, use_container_width=True)

            total_daily = df_disp["Production for the Day"].sum()
            total_acc = df_disp["Accumulative Production"].sum()
            st.markdown("### Summary")
            st.write(f"- **Daily:** {total_daily:,.1f} m³")
            st.write(f"- **Accumulative:** {total_acc:,.1f} m³")

            st.markdown("### Visualization")
            fig = px.bar(df_disp, x="Plant", y="Production for the Day", color="Plant",
                         color_discrete_sequence=theme_colors, title=f"Daily Production — {date_str}")
            st.plotly_chart(fig, use_container_width=True)

            excel = generate_excel_report(df_disp, date_str)
            st.download_button("Download Excel", excel, f"report_{date_str}.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ========================================
# MODE: MANAGE DATA
# ========================================
elif mode == "Manage Data":
    st.header("Manage Saved Files")
    saved_dates = list_saved_dates()
    if not saved_dates:
        st.info("No files to manage.")
    else:
        st.write(f"**{len(saved_dates)}** file(s) found:")
        for date_str in saved_dates:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"**{date_str}**")
            with col2:
                if st.button("Delete", key=f"del_{date_str}"):
                    if delete_saved(date_str):
                        st.success(f"Deleted {date_str}")
                        st.rerun()
                    else:
                        st.error("Delete failed.")
            with col3:
                if st.button("Download", key=f"dl_{date_str}"):
                    df = load_saved(date_str)
                    excel = generate_excel_report(df, date_str)
                    st.download_button("Get File", excel, f"{date_str}.xlsx",
                                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                       key=f"dl_btn_{date_str}")

# ========================================
# MODE: ANALYTICS — FINAL & CORRECT
# ========================================
elif mode == "Analytics":
    st.header("Analytics & Performance Trends")
    saved_dates = list_saved_dates()
    if len(saved_dates) < 2:
        st.info("Need at least 2 days of data for analytics.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", value=datetime.today() - timedelta(days=30))
        with col2:
            end_date = st.date_input("End Date", value=datetime.today())

        # Load and filter data
        frames = [load_saved(d) for d in saved_dates]
        all_df = pd.concat(frames, ignore_index=True)
        all_df['Date'] = pd.to_datetime(all_df['Date'])

        filtered_df = all_df[
            (all_df['Date'] >= pd.to_datetime(start_date)) &
            (all_df['Date'] <= pd.to_datetime(end_date))
        ].copy()

        if filtered_df.empty:
            st.warning("No data in selected date range.")
            st.stop()

        filtered_df = safe_numeric(filtered_df)
        filtered_df = filtered_df.sort_values(['Plant', 'Date'])

        # === MONTH: Only full months in range ===
        filtered_df['Month'] = filtered_df['Date'].dt.to_period('M').astype(str)
        valid_months = filtered_df['Month'].unique()

        # === WEEK: Only from start_date onward ===
        filtered_df['Custom_Week'] = ((filtered_df['Date'] - pd.to_datetime(start_date)).dt.days // 7) + 1
        filtered_df = filtered_df[filtered_df['Custom_Week'] >= 1]

        # Daily totals
        monthly_daily = filtered_df.groupby(['Month', 'Plant'], as_index=False)['Production for the Day'].sum()
        weekly_daily = filtered_df.groupby(['Custom_Week', 'Plant'], as_index=False)['Production for the Day'].sum()

        # === ACCUMULATIVE = FINAL DAY IN PERIOD ===
        monthly_max_dates = filtered_df.groupby(['Month', 'Plant'])['Date'].max().reset_index()
        weekly_max_dates = filtered_df.groupby(['Custom_Week', 'Plant'])['Date'].max().reset_index()

        monthly_acc = pd.merge(
            filtered_df[['Date', 'Month', 'Plant', 'Accumulative Production']],
            monthly_max_dates,
            on=['Month', 'Plant', 'Date'], how='inner'
        )[['Month', 'Plant', 'Accumulative Production']]

        weekly_acc = pd.merge(
            filtered_df[['Date', 'Custom_Week', 'Plant', 'Accumulative Production']],
            weekly_max_dates,
            on=['Custom_Week', 'Plant', 'Date'], how='inner'
        )[['Custom_Week', 'Plant', 'Accumulative Production']]

        # Filter out underperformers
        total_by_plant = monthly_daily.groupby('Plant')['Production for the Day'].sum().reset_index()
        active_plants = total_by_plant[total_by_plant['Production for the Day'] > 10]['Plant'].tolist()

        # Main summary box
        total_monthly = monthly_daily['Production for the Day'].sum()
        top_row = monthly_daily.loc[monthly_daily['Production for the Day'].idxmax()]
        top_plant = top_row['Plant']
        top_value = top_row['Production for the Day']
        kabd_value = monthly_daily[monthly_daily['Plant'].str.contains('KABD', case=False, na=False)]['Production for the Day'].sum()

        st.markdown(f"""
        <div style='text-align: center; padding: 30px; background: linear-gradient(45deg, #1a1a1a, #333); 
                    border-radius: 20px; margin: 30px 0; box-shadow: 0 0 20px rgba(255,69,0,0.5);'>
            <h1 style='color: #FFD700; font-size: 52px; margin: 0; text-shadow: 0 0 10px #FFD700;'>TOTAL MONTHLY PRODUCTION</h1>
            <h1 style='color: #00FF00; font-size: 72px; margin: 15px 0; text-shadow: 0 0 15px #00FF00;'>{total_monthly:,.1f} m³</h1>
            <h2 style='color: #FF4500; font-size: 40px; margin: 20px 0;'>
                TOP: <span style='color: #FFD700;'>{top_plant}</span> — {top_value:,.1f} m³
            </h2>
            {f'<h2 style="color: {"#00FF00" if kabd_value > 400 else "#FF4500"}; font-size: 36px;">KABD: {kabd_value:,.1f} m³ {"ON FIRE" if kabd_value > 400 else "NEEDS BOOST"}</h2>' if kabd_value > 0 else ''}
        </div>
        """, unsafe_allow_html=True)

        # Charts
        st.markdown("### Monthly Production (Daily)")
        st.plotly_chart(clean_bar_chart(monthly_daily, "Production for the Day", "Month", theme_colors, "Monthly Production"), use_container_width=True)

        st.markdown("### Weekly Production (Daily)")
        st.plotly_chart(clean_bar_chart(weekly_daily, "Production for the Day", "Custom_Week", theme_colors, "Weekly Production"), use_container_width=True)

        st.markdown("### Monthly Accumulative (Final Day)")
        st.plotly_chart(clean_bar_chart(monthly_acc, "Accumulative Production", "Month", theme_colors, "Monthly Accumulative"), use_container_width=True)

        st.markdown("### Weekly Accumulative (Final Day)")
        st.plotly_chart(clean_bar_chart(weekly_acc, "Accumulative Production", "Custom_Week", theme_colors, "Weekly Accumulative"), use_container_width=True)

        # Export
        summary = monthly_daily.merge(monthly_acc, on=['Month', 'Plant'], how='left')
        excel = generate_excel_report(summary, f"{start_date}_to_{end_date}")
        st.download_button("DOWNLOAD FULL REPORT", excel, f"analytics_{start_date}_to_{end_date}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ========================================
# FOOTER
# ========================================
st.sidebar.markdown("---")
st.sidebar.write("GitHub auto-sync enabled")
st.sidebar.caption(f"Kuwait Time: {datetime.now().strftime('%I:%M %p')} | Dashboard LIVE")
