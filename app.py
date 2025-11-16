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
import xlsxwriter

# ========================================
# CONFIG & PATHS
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
def hash_password(p): return hashlib.sha256(p.encode()).hexdigest()
def check_credentials(u, p): 
    return u.strip() in USERS and hash_password(p) == USERS[u.strip()]
def login_ui():
    st.sidebar.subheader("Login")
    with st.sidebar.form("login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Sign in"):
            if check_credentials(u, p):
                st.session_state["logged_in"] = True
                st.session_state["username"] = u.strip()
                st.rerun()
            else:
                st.sidebar.error("Invalid")
def logout():
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()
def logged_in(): return st.session_state.get("logged_in", False)

# ========================================
# FILE HELPERS
# ========================================
def save_csv(df, date_obj, overwrite=False):
    f = f"{date_obj:%Y-%m-%d}.csv"
    p = DATA_DIR / f
    if p.exists() and not overwrite:
        raise FileExistsError(f"{f} exists")
    df.to_csv(p, index=False, float_format="%.3f")
    return p

def list_saved_dates():
    return sorted([p.name.replace(".csv","") for p in DATA_DIR.glob("*.csv")], reverse=True)

def load_saved(d):
    p = DATA_DIR / f"{d}.csv"
    if not p.exists():
        raise FileNotFoundError(d)
    return pd.read_csv(p)

def delete_saved(d):
    p = DATA_DIR / f"{d}.csv"
    if p.exists():
        p.unlink()
        return True
    return False

def attempt_git_push(file_path, msg):
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False, "No GitHub"
    try:
        repo = GITHUB_REPO.replace("https://github.com/","").replace(".git","")
        url = f"https://api.github.com/repos/{repo}/contents/data/{file_path.name}"
        with open(file_path,"rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        h = {"Authorization": f"token {GITHUB_TOKEN}"}
        r = requests.get(url, headers=h)
        sha = r.json().get("sha") if r.status_code==200 else None
        payload = {"message":msg,"content":b64,"branch":"main","committer":{"name":GITHUB_USER,"email":GITHUB_EMAIL}}
        if sha: payload["sha"]=sha
        resp = requests.put(url, headers=h, json=payload)
        return resp.status_code in [200,201], ("OK" if resp.ok else resp.json().get("message","Failed"))
    except: return False, "Error"

# ========================================
# PLOT HELPERS
# ========================================
def bar_chart(df, col, colors, title):
    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    fig = px.bar(df, x="Plant", y=col, color="Plant", color_discrete_sequence=colors, title=title,
                 text=df[col].round(1))
    fig.update_traces(texttemplate="%{text:,.1f}", textposition="outside")
    fig.update_layout(title_font_size=18, margin=dict(t=60,b=280,l=60,r=40), xaxis_tickangle=0)
    return fig

def aggregated_bar_chart(df, val_col, group_col, colors, title):
    df[val_col] = pd.to_numeric(df[val_col], errors='coerce').fillna(0)
    agg = df.groupby([group_col,"Plant"], as_index=False)[val_col].sum()
    agg = agg.sort_values(val_col, ascending=False)
    fig = px.bar(agg, x="Plant", y=val_col, color=group_col, color_discrete_sequence=colors, title=title,
                 text=agg[val_col].round(1))
    fig.update_traces(texttemplate="%{text:,.1f}", textposition="outside")
    fig.update_layout(title_font_size=18, margin=dict(t=70,b=280,l=60,r=40), xaxis_tickangle=0)
    for t in fig.data:
        if 'KABD' in t.name:
            t.marker.color = "#FF4500"
            t.textfont.color = "#FF4500"
            t.textfont.size = 16
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
# LOGIN CHECK
# ========================================
if not logged_in():
    st.title("Login Required")
    login_ui()
    st.stop()

# ========================================
# MAIN UI
# ========================================
st.sidebar.title("Controls")
st.sidebar.write(f"**{st.session_state.get('username','-')}**")
if st.sidebar.button("Logout"): logout()

mode = st.sidebar.radio("Mode", ["Upload","View","Manage","Analytics"], index=3)
theme_colors = COLOR_THEMES[st.session_state["theme"]]
alert = st.sidebar.number_input("Alert (m³)", 0.0, value=50.0, step=0.5)
st.sidebar.caption("Excel: Plant | Production for the Day | Accumulative Production")
st.title("PRODUCTION DASHBOARD")

# ========================================
# UPLOAD MODE
# ========================================
if mode == "Upload":
    st.header("Upload Daily Data")
    file = st.file_uploader("Excel (.xlsx)", type=["xlsx"])
    date = st.date_input("Date", datetime.today())
    if file:
        try: df = pd.read_excel(file); df.columns = df.columns.str.strip()
        except Exception as e: st.error(e); st.stop()
        miss = [c for c in REQUIRED_COLS if c not in df.columns]
        if miss: st.error(f"Missing: {miss}")
        else:
            st.subheader("Preview")
            st.dataframe(df.head(20))
            ow = st.checkbox("Overwrite?", False)
            ok = st.checkbox("Confirm")
            if ok and st.button("Save"):
                df["Date"] = date.strftime("%Y-%m-%d")
                try: p = save_csv(df, date, ow)
                except Exception as e: st.error(e); st.stop()
                st.success(f"Saved: {p.name}")
                pushed,msg = attempt_git_push(p, f"Add {date}")
                st.write("GitHub:" if pushed else "GitHub: Failed", msg)
                disp = df[~df["Plant"].str.upper().str.contains("TOTAL")]
                disp = safe_numeric(disp)
                st.markdown("### Summary")
                st.write(f"**Daily:** {disp['Production for the Day'].sum():,.1f} m³")
                st.write(f"**Accumulative:** {disp['Accumulative Production'].sum():,.1f} m³")
                low = disp[disp["Production for the Day"] < alert]
                if not low.empty:
                    st.warning("Below threshold:")
                    for _,r in low.iterrows():
                        st.write(f"- {r['Plant']}: {r['Production for the Day']:.1f}")
                c1,c2 = st.columns(2)
                with c1: st.plotly_chart(px.pie(disp, names="Plant", values="Production for the Day", color_discrete_sequence=theme_colors), use_container_width=True)
                with c2: st.plotly_chart(bar_chart(disp, "Production for the Day", theme_colors, "Daily"), use_container_width=True)
                top = disp.loc[disp["Production for the Day"].idxmax()]
                st.success(f"**Top:** {top['Plant']} — {top['Production for the Day']:.1f} m³")
                excel = generate_excel_report(disp, date.strftime("%Y-%m-%d"))
                st.download_button("Download Excel", excel, f"report_{date}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ========================================
# VIEW MODE
# ========================================
elif mode == "View":
    st.header("Historical Data")
    dates = list_saved_dates()
    if not dates: st.info("No data")
    else:
        sel_date = st.date_input("Select", datetime.strptime(dates[0], "%Y-%m-%d").date())
        sel = sel_date.strftime("%Y-%m-%d")
        if sel not in dates: st.warning("No data"); st.stop()
        df = load_saved(sel)
        df = df[~df["Plant"].str.upper().str.contains("TOTAL")]
        df = safe_numeric(df)
        st.subheader(f"Data — {sel}")
        st.dataframe(df, use_container_width=True)
        st.write(f"**Daily:** {df['Production for the Day'].sum():,.1f} m³")
        st.write(f"**Accumulative:** {df['Accumulative Production'].sum():,.1f} m³")
        st.plotly_chart(bar_chart(df, "Production for the Day", theme_colors, "Daily"), use_container_width=True)
        st.plotly_chart(bar_chart(df, "Accumulative Production", theme_colors, "Accumulative"), use_container_width=True)
        excel = generate_excel_report(df, sel)
        st.download_button("Download", excel, f"{sel}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ========================================
# MANAGE MODE
# ========================================
elif mode == "Manage":
    st.header("Manage Files")
    dates = list_saved_dates()
    if not dates: st.info("No files")
    else:
        for d in dates:
            c1,c2,c3 = st.columns([2,1,1])
            with c1: st.write(f"**{d}**")
            with c2:
                if st.button("Delete", key=f"del_{d}"):
                    if delete_saved(d):
                        st.success(f"Deleted {d}")
                        st.rerun()
            with c3:
                if st.button("Download", key=f"dl_{d}"):
                    df = load_saved(d)
                    excel = generate_excel_report(df, d)
                    st.download_button("Get", excel, f"{d}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"btn_{d}")

# ========================================
# ANALYTICS — FINAL FIX: ACCUMULATIVE FROM LAST DAY
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
    df['Week'] = ((df['Date'] - pd.to_datetime(start)).dt.days // 7) + 1

    # DAILY
    weekly_daily = df.groupby(['Week','Plant'], as_index=False)['Production for the Day'].sum()
    monthly_daily = df.groupby(['Month','Plant'], as_index=False)['Production for the Day'].sum()

    # ACCUMULATIVE = LAST DAY OF PERIOD
    monthly_max = df.groupby(['Month','Plant'])['Date'].max().reset_index()
    monthly_acc = pd.merge(df[['Date','Month','Plant','Accumulative Production']], monthly_max,
                          on=['Month','Plant','Date'], how='inner')[['Month','Plant','Accumulative Production']]

    weekly_max = df.groupby(['Week','Plant'])['Date'].max().reset_index()
    weekly_acc = pd.merge(df[['Date','Week','Plant','Accumulative Production']], weekly_max,
                         on=['Week','Plant','Date'], how='inner')[['Week','Plant','Accumulative Production']]

    # CHARTS
    st.subheader("Weekly Production")
    st.plotly_chart(aggregated_bar_chart(weekly_daily, "Production for the Day", "Week", theme_colors, "Weekly"), use_container_width=True)

    st.subheader("Monthly Production")
    st.plotly_chart(aggregated_bar_chart(monthly_daily, "Production for the Day", "Month", theme_colors, "Monthly"), use_container_width=True)

    st.subheader("Weekly Accumulative (Final Day)")
    st.plotly_chart(aggregated_bar_chart(weekly_acc, "Accumulative Production", "Week", theme_colors, "Weekly Acc"), use_container_width=True)

    st.subheader("Monthly Accumulative (Final Day)")
    st.plotly_chart(aggregated_bar_chart(monthly_acc, "Accumulative Production", "Month", theme_colors, "Monthly Acc"), use_container_width=True)

    # SUMMARY & DOWNLOAD
    summary = pd.DataFrame({"Plant": df['Plant'].unique()})
    summary = summary.merge(weekly_daily.groupby('Plant')['Production for the Day'].sum().reset_index(), how='left').fillna(0)
    summary = summary.merge(weekly_acc.groupby('Plant')['Accumulative Production'].last().reset_index(), how='left').fillna(0)
    summary = summary.merge(monthly_daily.groupby('Plant')['Production for the Day'].sum().reset_index(), how='left').fillna(0)
    summary = summary.merge(monthly_acc.groupby('Plant')['Accumulative Production'].last().reset_index(), how='left').fillna(0)
    summary.columns = ['Plant','Weekly Daily','Weekly Acc','Monthly Daily','Monthly Acc']
    summary = summary.sort_values('Monthly Daily', ascending=False)

    excel = generate_excel_report(summary, f"{start}_to_{end}")
    st.download_button("Download Report", excel, f"report_{start}_to_{end}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ========================================
# FOOTER
# ========================================
st.sidebar.markdown("---")
st.sidebar.caption(f"Kuwait Time: {datetime.now().strftime('%I:%M %p')} | LIVE")
