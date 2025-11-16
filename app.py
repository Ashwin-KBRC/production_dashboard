import os
import hashlib
import base64
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict
import pandas as pd
import plotly.express as px
import streamlit as st
import io
import xlsxwriter

# ========================================
# CONFIG
# ========================================
st.set_page_config(page_title="Production Dashboard", layout="wide", page_icon="Chart")
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
REQUIRED_COLS = ["Plant", "Production for the Day", "Accumulative Production"]

# ========================================
# SECRETS & AUTH
# ========================================
SECRETS = {}
try: SECRETS = dict(st.secrets)
except: pass
try: SECRETS.update(dict(os.environ))
except: pass

GITHUB_TOKEN = SECRETS.get("GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
GITHUB_REPO = SECRETS.get("GITHUB_REPO") or os.getenv("GITHUB_REPO")

_default_users = {"admin": hashlib.sha256("kbrc123".encode()).hexdigest()}
USERS: Dict[str, str] = _default_users.copy()
if "USERS" in SECRETS and isinstance(SECRETS["USERS"], dict):
    USERS.update(SECRETS["USERS"])

# ========================================
# THEMES
# ========================================
COLOR_THEMES = {
    "Modern Slate": ["#4A6572", "#7D9D9C", "#A4C3B2", "#C9D7D6", "#E5ECE9"],
    "Corporate": ["#FF4040", "#4040FF", "#40FF40", "#FF8000", "#FFFF40"],
}
if "theme" not in st.session_state:
    st.session_state["theme"] = "Modern Slate"

# ========================================
# AUTH
# ========================================
def check_credentials(u, p): 
    u = u.strip()
    return u in USERS and hashlib.sha256(p.encode()).hexdigest() == USERS[u]

def login_ui():
    st.sidebar.subheader("Login")
    with st.sidebar.form("login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Sign in"):
            if check_credentials(u, p):
                st.session_state["logged_in"] = True
                st.session_state["username"] = u
                st.rerun()
            else:
                st.sidebar.error("Invalid")

def logout():
    for k in list(st.session_state.keys()): del st.session_state[k]
    st.rerun()

def logged_in(): return st.session_state.get("logged_in", False)

# ========================================
# FILE HELPERS
# ========================================
def save_csv(df, date_obj, overwrite=False):
    f = f"{date_obj:%Y-%m-%d}.csv"
    p = DATA_DIR / f
    if p.exists() and not overwrite: raise FileExistsError(f"{f} exists")
    df.to_csv(p, index=False, float_format="%.3f")
    return p

def list_saved_dates():
    return sorted([p.name.replace(".csv","") for p in DATA_DIR.glob("*.csv")], reverse=True)

def load_saved(d):
    p = DATA_DIR / f"{d}.csv"
    if not p.exists(): raise FileNotFoundError(d)
    return pd.read_csv(p)

def delete_saved(d):
    p = DATA_DIR / f"{d}.csv"
    if p.exists(): p.unlink(); return True
    return False

# ========================================
# PLOT HELPERS
# ========================================
def aggregated_bar_chart(df, val_col, group_col, colors, title):
    df[val_col] = pd.to_numeric(df[val_col], errors='coerce').fillna(0)
    agg = df.groupby([group_col,"Plant"], as_index=False)[val_col].sum()
    agg = agg.sort_values(val_col, ascending=False)
    fig = px.bar(agg, x="Plant", y=val_col, color=group_col, color_discrete_sequence=colors, title=title,
                 text=agg[val_col].round(1))
    fig.update_traces(texttemplate="%{text:,.1f}", textposition="outside", textfont_size=16)
    fig.update_layout(title_font_size=18, margin=dict(t=70,b=280,l=60,r=40), xaxis_tickangle=0)
    return fig

# ========================================
# DATA HELPERS
# ========================================
def safe_numeric(df):
    d = df.copy()
    d["Production for the Day"] = pd.to_numeric(d["Production for the Day"], errors="coerce").fillna(0)
    d["Accumulative Production"] = pd.to_numeric(d["Accumulative Production"], errors="coerce").fillna(0)
    return d

def generate_excel_report(df, name):
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='xlsxwriter') as w:
        df.to_excel(w, sheet_name='Data', index=False)
    out.seek(0)
    return out

# ========================================
# LOGIN
# ========================================
if not logged_in():
    st.title("Login Required")
    login_ui()
    st.stop()

# ========================================
# MAIN UI
# ========================================
st.sidebar.title("Controls")
st.sidebar.write(f"**{st.session_state['username']}**")
if st.sidebar.button("Logout"): logout()

mode = st.sidebar.radio("Mode", ["Upload","View","Manage","Analytics"], index=3)
theme_colors = COLOR_THEMES[st.session_state["theme"]]
st.title("PRODUCTION DASHBOARD")

# ========================================
# UPLOAD
# ========================================
if mode == "Upload":
    st.header("Upload Daily Data")
    file = st.file_uploader("Excel (.xlsx)", type=["xlsx"])
    date = st.date_input("Date", datetime.today())
    if file:
        df = pd.read_excel(file); df.columns = df.columns.str.strip()
        miss = [c for c in REQUIRED_COLS if c not in df.columns]
        if miss: st.error(f"Missing: {miss}"); st.stop()
        st.dataframe(df.head(20))
        ow = st.checkbox("Overwrite?", False)
        ok = st.checkbox("Confirm")
        if ok and st.button("Save"):
            df["Date"] = date.strftime("%Y-%m-%d")
            p = save_csv(df, date, ow)
            st.success(f"Saved: {p.name}")
            disp = df[~df["Plant"].str.upper().str.contains("TOTAL")]
            disp = safe_numeric(disp)
            st.write(f"**Daily:** {disp['Production for the Day'].sum():,.1f} m³")
            st.write(f"**Accumulative:** {disp['Accumulative Production'].sum():,.1f} m³")
            st.plotly_chart(px.bar(disp, x="Plant", y="Accumulative Production", color="Plant", color_discrete_sequence=theme_colors, title="Accumulative"), use_container_width=True)

# ========================================
# VIEW
# ========================================
elif mode == "View":
    dates = list_saved_dates()
    if not dates: st.info("No data"); st.stop()
    sel_date = st.date_input("Select", datetime.strptime(dates[0], "%Y-%m-%d").date())
    sel = sel_date.strftime("%Y-%m-%d")
    if sel not in dates: st.warning("No data"); st.stop()
    df = load_saved(sel)
    df = df[~df["Plant"].str.upper().str.contains("TOTAL")]
    df = safe_numeric(df)
    st.dataframe(df)
    st.write(f"**Accumulative:** {df['Accumulative Production'].sum():,.1f} m³")
    st.plotly_chart(px.bar(df, x="Plant", y="Accumulative Production", color="Plant", color_discrete_sequence=theme_colors, title="Accumulative"), use_container_width=True)

# ========================================
# MANAGE
# ========================================
elif mode == "Manage":
    dates = list_saved_dates()
    if not dates: st.info("No files"); st.stop()
    for d in dates:
        c1,c2,c3 = st.columns([2,1,1])
        with c1: st.write(f"**{d}**")
        with c2:
            if st.button("Delete", key=f"del_{d}"):
                delete_saved(d)
                st.success(f"Deleted {d}")
                st.rerun()
        with c3:
            if st.button("Download", key=f"dl_{d}"):
                df = load_saved(d)
                excel = generate_excel_report(df, d)
                st.download_button("Get", excel, f"{d}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"btn_{d}")

# ========================================
# ANALYTICS — FINAL: 100% FROM "Accumulative Production"
# ========================================
elif mode == "Analytics":
    st.header("Analytics")
    dates = list_saved_dates()
    if len(dates) < 2: st.info("Need 2+ days"); st.stop()

    c1,c2 = st.columns(2)
    with c1: start = st.date_input("Start", datetime.today() - timedelta(days=30))
    with c2: end = st.date_input("End", datetime.today())

    frames = [load_saved(d) for d in dates]
    all_df = pd.concat(frames, ignore_index=True)
    all_df['Date'] = pd.to_datetime(all_df['Date'])
    df = all_df[(all_df['Date'] >= pd.to_datetime(start)) & (all_df['Date'] <= pd.to_datetime(end))].copy()
    if df.empty: st.warning("No data"); st.stop()

    df = safe_numeric(df)
    df = df.sort_values(['Plant','Date'])
    df['Month'] = df['Date'].dt.to_period('M').astype(str)

    # DAILY PRODUCTION SUM
    monthly_daily = df.groupby(['Month','Plant'], as_index=False)['Production for the Day'].sum()

    # ACCUMULATIVE = LAST DAY OF MONTH → FROM "Accumulative Production"
    monthly_max = df.groupby(['Month','Plant'])['Date'].max().reset_index()
    monthly_acc = pd.merge(
        df[['Date','Month','Plant','Accumulative Production']],
        monthly_max,
        on=['Month','Plant','Date'],
        how='inner'
    )[['Month','Plant','Accumulative Production']].copy()

    # CHART: MONTHLY ACCUMULATIVE — 100% FROM "Accumulative Production"
    st.subheader("Monthly Accumulative Production (Final Day Value)")
    st.plotly_chart(
        aggregated_bar_chart(monthly_acc, "Accumulative Production", "Month", theme_colors, "Monthly Accumulative"),
        use_container_width=True
    )

    # DEBUG: SHOW EXACT VALUES FROM EXCEL
    st.markdown("### DEBUG: Raw Accumulative Values (Last Day of Month)")
    debug_df = monthly_acc.sort_values(['Month','Plant']).copy()
    debug_df['Accumulative Production'] = debug_df['Accumulative Production'].round(1)
    st.dataframe(debug_df, use_container_width=True)

    # DOWNLOAD
    excel = generate_excel_report(debug_df, f"{start}_to_{end}")
    st.download_button("Download Accumulative Report", excel, f"monthly_accumulative_{start}_to_{end}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ========================================
# FOOTER
# ========================================
st.sidebar.caption(f"Kuwait Time: {datetime.now().strftime('%I:%M %p')} | LIVE")
