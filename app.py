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
import plotly.graph_objects as go
import streamlit as st
import io
import xlsxwriter

# ========================================
# PAGE CONFIG & SETUP
# ========================================
st.set_page_config(page_title="Production Dashboard", layout="wide", page_icon="Chart")
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
# THEMES — 3 NEW: LAVA, NEON, GOLD
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
    # NEW THEMES
    "Lava Flow": ["#FF4500", "#FF6B35", "#F7931E", "#FFD23F", "#FF8C00", "#1A1A1A", "#FF5733", "#FFC300", "#FF5733", "#DAF7A6"],
    "Neon Pulse": ["#00FF00", "#00FFFF", "#FF00FF", "#FFFF00", "#00FF7F", "#1E1E1E", "#39FF14", "#00CED1", "#FF1493", "#FFD700"],
    "Gold Standard": ["#FFD700", "#FFA500", "#DAA520", "#B8860B", "#CD7F32", "#2F2F2F", "#FFCC00", "#FF9900", "#CC9900", "#996600"],
}
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
        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        resp = requests.get(url, headers=headers)
        sha = resp.json().get("sha") if resp.status_code == 200 else None
        payload = {"message": msg, "content": b64, "branch": "main", "committer": {"name": GITHUB_USER, "email": GITHUB_EMAIL}}
        if sha: payload["sha"] = sha
        r = requests.put(url, headers=headers, json=payload)
        return r.status_code in [200, 201], ("Success" if r.ok else r.json().get("message", "Failed"))
    except Exception as e:
        return False, str(e)

# ========================================
# PLOT HELPERS — CLEAN LABELS, EXACT VALUES
# ========================================
def pie_chart(df: pd.DataFrame, value_col: str, colors: list, title: str):
    df[value_col] = df[value_col].astype('float64')
    fig = px.pie(df, names="Plant", values=value_col, color_discrete_sequence=colors, title=title)
    fig.update_traces(textinfo="percent+label", textfont=dict(size=14, color="black"))
    fig.update_layout(title_font=dict(family="Arial", size=18), legend_font=dict(size=16), margin=dict(t=60, b=40, l=40, r=40))
    return fig

def bar_chart(df: pd.DataFrame, value_col: str, colors: list, title: str):
    df[value_col] = df[value_col].astype('float64')
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
    df[value_col] = df[value_col].astype('float64')
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
    df[value_col] = df[value_col].astype('float64')
    fig = px.area(df, x="Plant", y=value_col, color="Plant", color_discrete_sequence=colors, title=title)
    fig.update_traces(line=dict(width=2), opacity=0.8)
    fig.update_layout(
        title_font=dict(size=18),
        margin=dict(t=60, b=40, l=60, r=40),
        xaxis_gridcolor="#E0E0E0",
        yaxis_gridcolor="#E0E0E0"
    )
    return fig

def aggregated_bar_chart(df: pd.DataFrame, value_col: str, group_col: str, colors: list, title: str):
    df[value_col] = df[value_col].astype('float64')
    agg_df = df.groupby([group_col, "Plant"], as_index=False)[value_col].sum()
    agg_df = agg_df.sort_values(value_col, ascending=False)
    fig = px.bar(
        agg_df,
        x="Plant",
        y=value_col,
        color=group_col,
        color_discrete_sequence=colors,
        title=title,
        text=agg_df[value_col].round(1)
    )
    fig.update_traces(
        texttemplate="%{text:,.1f}",
        textposition="outside",
        textfont=dict(size=16, color="black", family="Arial"),
        cliponaxis=False,
        textangle=0
    )
    fig.update_layout(
        title_font=dict(size=18),
        legend_font=dict(size=14),
        margin=dict(t=70, b=280, l=60, r=40),
        xaxis_tickangle=0,
        xaxis_gridcolor="#E0E0E0",
        yaxis_gridcolor="#E0E0E0",
        xaxis_tickfont=dict(size=13),
        yaxis_tickfont=dict(size=12)
    )
    for trace in fig.data:
        if 'KABD' in trace.name:
            trace.marker.color = "#FF4500"
            trace.textfont.color = "#FF4500"
            trace.textfont.size = 16
            trace.textfont.family = "Arial Black"
            break
    return fig

# ========================================
# ANIMATED PLOT HELPERS — FIXED & SMOOTH
# ========================================
def animated_pie(df: pd.DataFrame, value_col: str, colors: list, title: str):
    df[value_col] = df[value_col].astype('float64')
    fig = go.Figure()
    fig.add_trace(go.Pie(labels=df["Plant"], values=[0]*len(df), textinfo="percent+label", marker_colors=colors))
    fig.update_layout(
        title=title, title_font=dict(size=18), legend_font=dict(size=16),
        margin=dict(t=60, b=40, l=40, r=40),
        updatemenus=[dict(type="buttons", buttons=[dict(label="Play", method="animate", args=[None, {"frame": {"duration": 600}, "fromcurrent": True}])], direction="left", pad={"r": 10, "t": 87}, showactive=False, x=0.1, xanchor="right", y=1.1, yanchor="top")]
    )
    frames = [go.Frame(data=[go.Pie(labels=df["Plant"], values=df[value_col] * (i/10))]) for i in range(1, 11)]
    fig.frames = frames
    return fig

def animated_bar(df: pd.DataFrame, value_col: str, colors: list, title: str):
    df[value_col] = df[value_col].astype('float64')
    fig = go.Figure()
    for i, plant in enumerate(df["Plant"]):
        fig.add_trace(go.Bar(x=[plant], y=[0], name=plant, marker_color=colors[i % len(colors)], text=[0], textposition="outside"))
    fig.update_layout(
        title=title, xaxis_title="Plant", yaxis_title="m³", barmode='relative',
        updatemenus=[dict(type="buttons", buttons=[dict(label="Play", method="animate", args=[None, {"frame": {"duration": 100}, "fromcurrent": True}])], direction="left", pad={"r": 10, "t": 87}, showactive=False, x=0.1, xanchor="right", y=1.1, yanchor="top")]
    )
    frames = []
    for i in range(11):
        frame_data = [go.Bar(x=[p], y=[v * (i/10)], text=[f"{v * (i/10):.1f}"], textposition="outside") for p, v in zip(df["Plant"], df[value_col])]
        frames.append(go.Frame(data=frame_data))
    fig.frames = frames
    return fig

def animated_line(df: pd.DataFrame, value_col: str, colors: list, title: str):
    df = df.copy()
    df[value_col] = df[value_col].astype('float64')
    if 'Date' not in df.columns:
        df['Date'] = pd.date_range(start='2025-01-01', periods=len(df), freq='D')
    df = df.sort_values("Date").reset_index(drop=True)
    fig = go.Figure()
    plants = df["Plant"].unique()
    for i, plant in enumerate(plants):
        sub = df[df["Plant"] == plant]
        fig.add_trace(go.Scatter(x=sub["Date"], y=[0]*len(sub), mode='lines+markers', name=plant, line=dict(color=colors[i % len(colors)])))
    fig.update_layout(
        title=title, xaxis_title="Date", yaxis_title="m³",
        updatemenus=[dict(type="buttons", buttons=[dict(label="Play", method="animate", args=[None, {"frame": {"duration": 400}, "fromcurrent": True}])], direction="left", pad={"r": 10, "t": 87}, showactive=False, x=0.1, xanchor="right", y=1.1, yanchor="top")]
    )
    max_frames = min(10, len(df))
    frames = []
    step = max(1, len(df) // max_frames)
    for i in range(1, max_frames + 1):
        idx = i * step
        frame_data = []
        for plant in plants:
            sub = df[df["Plant"] == plant].iloc[:idx]
            frame_data.append(go.Scatter(x=sub["Date"], y=sub[value_col], mode='lines+markers'))
        frames.append(go.Frame(data=frame_data))
    fig.frames = frames
    return fig

def animated_aggregated_bar(df: pd.DataFrame, value_col: str, group_col: str, colors: list, title: str):
    df = df[df[value_col] > 0].copy()  # REMOVE ZEROS
    if df.empty:
        return go.Figure().add_annotation(text="No data", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
    df[value_col] = df[value_col].astype('float64')
903    groups = sorted(df[group_col].unique())
    fig = go.Figure()
    for i, group in enumerate(groups):
        sub = df[df[group_col] == group]
        for j, plant in enumerate(sub["Plant"]):
            fig.add_trace(go.Bar(x=[plant], y=[0], name=f"{group} - {plant}", marker_color=colors[i % len(colors)]))
    fig.update_layout(
        title=title, barmode='stack',
        updatemenus=[dict(type="buttons", buttons=[dict(label="Play", method="animate", args=[None, {"frame": {"duration": 500}, "fromcurrent": True}])], direction="left", pad={"r": 10, "t": 87}, showactive=False, x=0.1, xanchor="right", y=1.1, yanchor="top")]
    )
    frames = []
    for i in range(11):
        frame_data = []
        for trace in fig.data:
            group = trace.name.split(" - ")[0]
            plant = trace.name.split(" - ")[1]
            full_val = df[(df[group_col] == group) & (df["Plant"] == plant)][value_col].sum()
            val = full_val * (i / 10)
            frame_data.append(go.Bar(x=[plant], y=[val], text=[f"{val:.1f}"] if val > 0 else [""], textposition="outside"))
        frames.append(go.Frame(data=frame_data))
    fig.frames = frames
    for trace in fig.data:
        if 'KABD' in trace.name:
            trace.marker.color = "#FF4500"
            trace.textfont = dict(color="#FF4500", size=16, family="Arial Black")
    return fig

# ========================================
# DATA HELPERS
# ========================================
def safe_numeric(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()
    df2["Production for the Day"] = pd.to_numeric(df2["Production for the Day"], errors="coerce").fillna(0.0)
    df2["Accumulative Production"] = pd.to_numeric(df2["Accumulative Production"], errors="coerce").fillna(0.0)
    return df2

def generate_excel_report(df: pd.DataFrame, date_str: str):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Production Data', index=False, float_format="%.3f")
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

mode = st.sidebar.radio("Mode", ["Upload New Data", "View Historical Data", "Manage Data", "Analytics"], index=3)
theme_choice = st.sidebar.selectbox("Theme", list(COLOR_THEMES.keys()), index=list(COLOR_THEMES.keys()).index(st.session_state["theme"]))
theme_colors = COLOR_THEMES[theme_choice]
alert_threshold = st.sidebar.number_input("Alert threshold (m³)", min_value=0.0, value=50.0, step=0.5)
st.sidebar.markdown("---")
st.sidebar.caption("Upload Excel with exact columns: Plant, Production for the Day, Accumulative Production.")
st.title("PRODUCTION FOR THE DAY")

# ========================================
# UPLOAD MODE
# ========================================
if mode == "Upload New Data":
    st.header("Upload new daily production file")
    uploaded = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx"])
    selected_date = st.date_input("Which date is this file for?", value=datetime.today())
    if uploaded:
        try:
            df_uploaded = pd.read_excel(uploaded)
            df_uploaded.columns = df_uploaded.columns.str.strip()
        except Exception as e:
            st.error(f"Failed to read: {e}")
            st.stop()
        missing = [c for c in REQUIRED_COLS if c not in df_uploaded.columns]
        if missing:
            st.error(f"Missing columns: {missing}")
        else:
            st.subheader("Preview")
            st.dataframe(df_uploaded.head(20))
            overwrite = st.checkbox("Overwrite existing?", value=False)
            confirm = st.checkbox("Confirm data is correct")
            if confirm and st.button("Upload & Save"):
                df_save = df_uploaded.copy()
                df_save["Date"] = selected_date.strftime("%Y-%m-%d")
                try:
                    saved_path = save_csv(df_save, selected_date, overwrite=overwrite)
                except FileExistsError as e:
                    st.error(str(e))
                    st.stop()
                st.success(f"Saved to {saved_path}")
                pushed, message = attempt_git_push(saved_path, f"Add data for {selected_date}")
                if pushed: st.success(message)
                else: st.warning(message)
                df_display = df_save[~df_save["Plant"].astype(str).str.upper().str.contains("TOTAL")]
                df_display = safe_numeric(df_display)
                st.markdown("### Totals")
                total_daily = df_display["Production for the Day"].sum()
                total_acc = df_display["Accumulative Production"].sum()
                st.write(f"- Daily: **{total_daily:,.1f} m³**")
                st.write(f"- Accumulative: **{total_acc:,.1f} m³**")
                alerts = df_display[df_display["Production for the Day"] < alert_threshold]
                if not alerts.empty:
                    st.warning("Below threshold:")
                    for _, r in alerts.iterrows():
                        st.write(f"- {r['Plant']}: {r['Production for the Day']:.1f} m³")
                st.markdown("### Charts")
                c1, c2 = st.columns(2)
                with c1:
                    st.plotly_chart(pie_chart(df_display, "Production for the Day", theme_colors, "Share"), use_container_width=True)
                with c2:
                    st.plotly_chart(bar_chart(df_display, "Production for the Day", theme_colors, "Per Plant"), use_container_width=True)
                st.plotly_chart(line_chart(df_display, "Production for the Day", theme_colors, "Trend"), use_container_width=True)
                st.plotly_chart(area_chart(df_display, "Production for the Day", theme_colors, "Flow"), use_container_width=True)
                st.plotly_chart(bar_chart(df_display, "Accumulative Production", theme_colors, "Accumulative"), use_container_width=True)
                top = df_display.loc[df_display["Production for the Day"].idxmax()]
                st.success(f"Top: {top['Plant']} — {top['Production for the Day']:.1f} m³")
                excel_file = generate_excel_report(df_display, selected_date.strftime("%Y-%m-%d"))
                st.download_button("Download Excel", excel_file, f"report_{selected_date.strftime('%Y-%m-%d')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ========================================
# VIEW HISTORICAL
# ========================================
elif mode == "View Historical Data":
    st.header("Historical Data Viewer")
    saved_list = list_saved_dates()
    if not saved_list:
        st.info("No data.")
    else:
        default_date = datetime.strptime(saved_list[0], "%Y-%m-%d").date()
        selected_date = st.date_input("Select date", value=default_date)
        selected = selected_date.strftime("%Y-%m-%d")
        if selected not in saved_list:
            st.warning("No data.")
            st.stop()
        df_hist = load_saved(selected)
        df_hist_disp = df_hist[~df_hist["Plant"].astype(str).str.upper().str.contains("TOTAL")]
        df_hist_disp = safe_numeric(df_hist_disp)
        st.subheader(f"Data for {selected}")
        st.dataframe(df_hist_disp, use_container_width=True)
        total_daily = df_hist_disp["Production for the Day"].sum()
        total_acc = df_hist_disp["Accumulative Production"].sum()
        st.markdown("### Totals")
        st.write(f"- Daily: **{total_daily:,.1f} m³**")
        st.write(f"- Accumulative: **{total_acc:,.1f} m³**")
        st.markdown("### 7 Charts — Daily & Accumulative")
        st.plotly_chart(pie_chart(df_hist_disp, "Production for the Day", theme_colors, f"Share — {selected}"), use_container_width=True)
        st.plotly_chart(bar_chart(df_hist_disp, "Production for the Day", theme_colors, f"Daily Production — {selected}"), use_container_width=True)
        st.plotly_chart(line_chart(df_hist_disp, "Production for the Day", theme_colors, f"Daily Trend — {selected}"), use_container_width=True)
        st.plotly_chart(area_chart(df_hist_disp, "Production for the Day", theme_colors, f"Daily Flow — {selected}"), use_container_width=True)
        st.markdown("#### Accumulative Production")
        st.plotly_chart(bar_chart(df_hist_disp, "Accumulative Production", theme_colors, f"Accumulative — {selected}"), use_container_width=True)
        st.plotly_chart(line_chart(df_hist_disp, "Accumulative Production", theme_colors, f"Accumulative Trend — {selected}"), use_container_width=True)
        st.plotly_chart(area_chart(df_hist_disp, "Accumulative Production", theme_colors, f"Accumulative Flow — {selected}"), use_container_width=True)
        excel_file = generate_excel_report(df_hist_disp, selected)
        st.download_button("Download Excel", excel_file, f"report_{selected}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ========================================
# MANAGE DATA
# ========================================
elif mode == "Manage Data":
    st.header("Manage Saved Files")
    saved_list = list_saved_dates()
    if not saved_list:
        st.info("No saved files.")
    else:
        st.write(f"Found {len(saved_list)} file(s):")
        for date_str in saved_list:
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.write(f"**{date_str}**")
            with col2:
                if st.button("Delete", key=f"del_{date_str}"):
                    if delete_saved(date_str):
                        st.success(f"Deleted {date_str}")
                        st.rerun()
                    else:
                        st.error("Failed to delete.")
            with col3:
                if st.button("Download", key=f"dl_{date_str}"):
                    try:
                        df = load_saved(date_str)
                        excel = generate_excel_report(df, date_str)
                        st.download_button(
                            label="Download",
                            data=excel,
                            file_name=f"{date_str}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"dl_btn_{date_str}"
                        )
                    except Exception as e:
                        st.error(f"Error: {e}")

# ========================================
# ANALYTICS — FULLY FIXED + WEEKLY + FILTER ZEROS
# ========================================
elif mode == "Analytics":
    st.header("Analytics & Trends")
    saved = list_saved_dates()
    if len(saved) < 2:
        st.info("Need 2+ days of data.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", value=datetime.today() - timedelta(days=30))
        with col2:
            end_date = st.date_input("End Date", value=datetime.today())
        frames = [load_saved(d) for d in saved]
        all_df = pd.concat(frames, ignore_index=True)
        all_df['Date'] = pd.to_datetime(all_df['Date'])
        filtered_df = all_df[(all_df['Date'] >= pd.to_datetime(start_date)) & (all_df['Date'] <= pd.to_datetime(end_date))]
        if filtered_df.empty:
            st.warning("No data in selected range.")
        else:
            filtered_df = safe_numeric(filtered_df)
            filtered_df = filtered_df.sort_values(['Plant', 'Date'])
            filtered_df['Month'] = filtered_df['Date'].dt.to_period('M').astype(str)
            filtered_df['Custom_Week'] = filtered_df['Date'].apply(lambda x: (x - pd.to_datetime(start_date)).days // 7 + 1)

            # === DAILY PRODUCTION ===
            monthly_daily = filtered_df.groupby(['Month', 'Plant'], as_index=False)['Production for the Day'].sum()
            weekly_daily = filtered_df.groupby(['Custom_Week', 'Plant'], as_index=False)['Production for the Day'].sum()

            # === ACCUMULATIVE (FINAL DAY) ===
            monthly_acc = filtered_df.groupby(['Month', 'Plant'], as_index=False)['Accumulative Production'].last()
            weekly_acc = filtered_df.groupby(['Custom_Week', 'Plant'], as_index=False)['Accumulative Production'].last()

            # === MAIN BOX: FILTER UNDERPERFORMERS (>10 m³ total) ===
            total_by_plant = monthly_daily.groupby('Plant')['Production for the Day'].sum().reset_index()
            active_plants = total_by_plant[total_by_plant['Production for the Day'] > 10]['Plant'].tolist()

            total_monthly = monthly_daily['Production for the Day'].sum()
            top_plant_row = monthly_daily.loc[monthly_daily['Production for the Day'].idxmax()]
            top_plant = top_plant_row['Plant']
            top_value = top_plant_row['Production for the Day']
            kabd_value = monthly_daily[monthly_daily['Plant'].str.contains('KABD', case=False, na=False)]['Production for the Day'].sum() if any(monthly_daily['Plant'].str.contains('KABD', case=False, na=False)) else 0

            # === BIG BOLD BOX ===
            st.markdown(f"""
            <div style='text-align: center; padding: 30px; background: linear-gradient(45deg, #1a1a1a, #333); border-radius: 20px; margin: 30px 0; box-shadow: 0 0 20px rgba(255,69,0,0.5);'>
                <h1 style='color: #FFD700; font-size: 52px; margin: 0; text-shadow: 0 0 10px #FFD700;'>TOTAL MONTHLY PRODUCTION</h1>
                <h1 style='color: #00FF00; font-size: 72px; margin: 15px 0; text-shadow: 0 0 15px #00FF00;'>{total_monthly:,.1f} m³</h1>
                <h2 style='color: #FF4500; font-size: 40px; margin: 20px 0;'>TOP PERFORMER: <span style='color: #FFD700;'>{top_plant}</span> — {top_value:,.1f} m³</h2>
                {f'<h2 style=\"color: {"#00FF00" if kabd_value > 400 else "#FF4500"}; font-size: 36px; text-shadow: 0 0 10px;\">KABD: {kabd_value:,.1f} m³ {"ON FIRE" if kabd_value > 400 else "NEEDS BOOST"}</h2>' if kabd_value > 0 else ''}
            </div>
            """, unsafe_allow_html=True)

            # === CHARTS ===
            st.markdown("### Monthly Production (Daily)")
            st.plotly_chart(animated_aggregated_bar(monthly_daily, "Production for the Day", "Month", theme_colors, "Monthly"), use_container_width=True, config={"staticPlot": False})

            st.markdown("### Weekly Production (Daily)")
            st.plotly_chart(animated_aggregated_bar(weekly_daily, "Production for the Day", "Custom_Week", theme_colors, "Weekly"), use_container_width=True, config={"staticPlot": False})

            st.markdown("### Monthly Accumulative (Final Day)")
            st.plotly_chart(animated_aggregated_bar(monthly_acc, "Accumulative Production", "Month", theme_colors, "Monthly Accumulative"), use_container_width=True, config={"staticPlot": False})

            st.markdown("### Weekly Accumulative (Final Day)")
            st.plotly_chart(animated_aggregated_bar(weekly_acc, "Accumulative Production", "Custom_Week", theme_colors, "Weekly Accumulative"), use_container_width=True, config={"staticPlot": False})

            st.markdown("### Download Full Report")
            summary_df = monthly_daily.copy()
            summary_df = summary_df.merge(monthly_acc[['Month', 'Plant', 'Accumulative Production']], on=['Month', 'Plant'], how='left')
            excel = generate_excel_report(summary_df, f"{start_date}_to_{end_date}")
            st.download_button("DOWNLOAD FULL REPORT", excel, f"report_{start_date}_to_{end_date}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ========================================
# FOOTER
# ========================================
st.sidebar.markdown("---")
st.sidebar.write("Set GITHUB_TOKEN & GITHUB_REPO in secrets for auto-push.")
