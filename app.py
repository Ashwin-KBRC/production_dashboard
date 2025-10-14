"""
Production Dashboard - Full long version (fixed rerun)
- Secure login (hashed default user, fallback to Streamlit Secrets if available)
- Upload Excel, choose date, confirm, save to data/YYYY-MM-DD.csv
- Attempt automatic push to GitHub via REST API
- Historical viewer, rename/delete, charts, themes, alerts, AI-style summary
- New: Custom date range filters, PDF export with charts, weekly/monthly charts in Analytics
- Uses st.rerun() (not deprecated experimental_rerun)
"""

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
import streamlit as st

# For PDF export with charts (using browser renderer)
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, Image
from reportlab.lib.styles import getSampleStyleSheet
import plotly.io as pio
import psutil

# Explicitly set Plotly renderer to browser (no external binaries)
pio.renderers.default = "browser"

# ----------------------------
# Page config
# ----------------------------
st.set_page_config(page_title="Production Dashboard", layout="wide", page_icon="📊")

# ----------------------------
# Ensure data dir
# ----------------------------
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------
# Required columns
# ----------------------------
REQUIRED_COLS = ["Plant", "Production for the Day", "Accumulative Production"]

# ----------------------------
# Read secrets / env
# ----------------------------
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

# ----------------------------
# Default users (hashed)
# ----------------------------
_default_users = {
    "admin": hashlib.sha256("kbrc123".encode()).hexdigest()
}
USERS: Dict[str, str] = _default_users.copy()
if "USERS" in SECRETS and isinstance(SECRETS["USERS"], dict):
    for k, v in SECRETS["USERS"].items():
        USERS[k] = v

# ----------------------------
# Color themes
# ----------------------------
COLOR_THEMES = {
    "Classic": px.colors.qualitative.Bold,
    "Blue": px.colors.sequential.Blues,
    "Vibrant": ["#EF476F", "#FFD166", "#06D6A0", "#118AB2", "#073B4C"],
    "Forest": ["#2e8b57", "#3cb371", "#66cdaa", "#20b2aa", "#2f4f4f"],
}

if "theme" not in st.session_state:
    st.session_state["theme"] = "Classic"

# ----------------------------
# Helper: hashing and auth
# ----------------------------
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
    st.sidebar.subheader("🔐 Login")
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

# ----------------------------
# File I/O and Git helpers
# ----------------------------
def save_csv(df: pd.DataFrame, date_obj: datetime.date, overwrite: bool=False) -> Path:
    fname = f"{date_obj.strftime('%Y-%m-%d')}.csv"
    p = DATA_DIR / fname
    if p.exists() and not overwrite:
        raise FileExistsError(f"{fname} already exists. Set overwrite=True to replace.")
    df.to_csv(p, index=False)
    return p

def list_saved_dates() -> List[str]:
    files = sorted([p.name.replace(".csv","") for p in DATA_DIR.glob("*.csv")], reverse=True)
    return files

def load_saved(date_str: str) -> pd.DataFrame:
    p = DATA_DIR / f"{date_str}.csv"
    if not p.exists():
        raise FileNotFoundError(f"Saved file for {date_str} not found.")
    return pd.read_csv(p)

def rename_saved(old_date: str, new_date: str) -> bool:
    old = DATA_DIR / f"{old_date}.csv"
    new = DATA_DIR / f"{new_date}.csv"
    if old.exists():
        old.rename(new)
        return True
    return False

def delete_saved(date_str: str) -> bool:
    p = DATA_DIR / f"{date_str}.csv"
    if p.exists():
        p.unlink()
        return True
    return False

def attempt_git_push(file_path: Path, commit_message: str) -> Tuple[bool, str]:
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False, "GITHUB_TOKEN or GITHUB_REPO not configured in app secrets."

    try:
        repo = GITHUB_REPO.strip().replace("https://github.com/", "").replace(".git", "")
        api_url = f"https://api.github.com/repos/{repo}/contents/data/{file_path.name}"

        with open(file_path, "rb") as f:
            content_b64 = base64.b64encode(f.read()).decode("utf-8")

        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        resp = requests.get(api_url, headers=headers)
        sha = resp.json().get("sha") if resp.status_code == 200 else None

        payload = {
            "message": commit_message,
            "content": content_b64,
            "branch": "main",
            "committer": {"name": GITHUB_USER, "email": GITHUB_EMAIL}
        }
        if sha:
            payload["sha"] = sha

        r = requests.put(api_url, headers=headers, json=payload)
        if r.status_code in [200, 201]:
            return True, f"✅ Successfully uploaded to GitHub: data/{file_path.name}"
        else:
            err = r.json().get("message", r.text)
            return False, f"❌ GitHub upload failed: {err}"

    except Exception as e:
        return False, f"Exception during GitHub upload: {e}"

# ----------------------------
# Plot helpers
# ----------------------------
def pie_chart(df: pd.DataFrame, value_col: str, colors: list, title: str):
    fig = px.pie(df, names="Plant", values=value_col, color_discrete_sequence=colors, title=title)
    fig.update_traces(textinfo="percent+label")
    fig.update_layout(title_x=0.5)
    return fig

def bar_chart(df: pd.DataFrame, value_col: str, colors: list, title: str):
    fig = px.bar(df, x="Plant", y=value_col, color="Plant", color_discrete_sequence=colors, title=title, text=value_col)
    fig.update_traces(texttemplate="%{text:.2s}", textposition="outside")
    fig.update_layout(xaxis_tickangle=-45, title_x=0.5)
    return fig

def line_chart(df: pd.DataFrame, value_col: str, colors: list, title: str):
    fig = px.line(df, x="Plant", y=value_col, markers=True, title=title, color_discrete_sequence=colors)
    fig.update_layout(title_x=0.5)
    return fig

def area_chart(df: pd.DataFrame, value_col: str, colors: list, title: str):
    fig = px.area(df, x="Plant", y=value_col, color="Plant", color_discrete_sequence=colors, title=title)
    fig.update_layout(title_x=0.5)
    return fig

# New: Weekly/Monthly bar chart helper
def aggregated_bar_chart(df: pd.DataFrame, value_col: str, group_col: str, colors: list, title: str):
    agg_df = df.groupby(group_col)[value_col].sum().reset_index().sort_values(value_col, ascending=False)
    fig = px.bar(agg_df, x=group_col, y=value_col, color=group_col, color_discrete_sequence=colors, title=title, text=value_col)
    fig.update_traces(texttemplate="%{text:.2s}", textposition="outside")
    fig.update_layout(xaxis_tickangle=-45, title_x=0.5)
    return fig

# ----------------------------
# Analytics helpers
# ----------------------------
def safe_numeric(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()
    df2["Production for the Day"] = pd.to_numeric(df2["Production for the Day"], errors="coerce").fillna(0.0)
    df2["Accumulative Production"] = pd.to_numeric(df2["Accumulative Production"], errors="coerce").fillna(0.0)
    return df2

def compute_rankings(all_df: pd.DataFrame, as_of_date: str) -> Dict[str, Any]:
    all_df = all_df.copy()
    all_df['Date'] = pd.to_datetime(all_df['Date'])
    as_dt = pd.to_datetime(as_of_date)
    daily = all_df[all_df['Date'].dt.strftime("%Y-%m-%d") == as_of_date].groupby('Plant')['Production for the Day'].sum().sort_values(ascending=False)
    start7 = as_dt - pd.Timedelta(days=6)
    weekly = all_df[(all_df['Date']>=start7) & (all_df['Date']<=as_dt)].groupby('Plant')['Production for the Day'].sum().sort_values(ascending=False)
    start30 = as_dt - pd.Timedelta(days=29)
    monthly = all_df[(all_df['Date']>=start30) & (all_df['Date']<=as_dt)].groupby('Plant')['Production for the Day'].sum().sort_values(ascending=False)
    return {"daily": daily, "weekly": weekly, "monthly": monthly}

def ai_summary(df_display: pd.DataFrame, history: pd.DataFrame, date_str: str) -> str:
    try:
        total = df_display["Production for the Day"].sum()
        top = df_display.loc[df_display["Production for the Day"].idxmax()]
        bottom = df_display.loc[df_display["Production for the Day"].idxmin()]
        lines = []
        lines.append(f"On {date_str}, total production was **{total:,.2f} m³**.")
        lines.append(f"Top producer: **{top['Plant']}** with **{float(top['Production for the Day']):,.2f} m³**.")
        lines.append(f"Lowest producer: **{bottom['Plant']}** with **{float(bottom['Production for the Day']):,.2f} m³**.")
        if history is not None and not history.empty:
            hist = history.copy()
            hist['Date'] = pd.to_datetime(hist['Date'])
            as_dt = pd.to_datetime(date_str)
            prev7 = hist[(hist['Date'] >= as_dt - pd.Timedelta(days=7)) & (hist['Date'] < as_dt)]
            if not prev7.empty:
                avg7 = prev7.groupby('Plant')['Production for the Day'].mean()
                notes = []
                for _, row in df_display.iterrows():
                    plant = row['Plant']
                    today = row['Production for the Day']
                    if plant in avg7.index:
                        avg = avg7.loc[plant]
                        if avg != 0:
                            pct = (today - avg) / avg * 100
                            if abs(pct) >= 10:
                                if pct > 0:
                                    notes.append(f"{plant} is up {pct:.1f}% vs its 7-day avg.")
                                else:
                                    notes.append(f"{plant} is down {abs(pct):.1f}% vs its 7-day avg.")
                lines.extend(notes)
        return "  \n".join(lines)
    except Exception as e:
        return f"Summary unavailable: {e}"

# Updated: PDF Report Generator with Charts (using browser renderer)
def generate_pdf_report(df: pd.DataFrame, date_str: str, charts=None):
    filename = f"production_report_{date_str}.pdf"
    buffer = Path(filename)
    doc = SimpleDocTemplate(str(buffer), pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph(f"Production Report - {date_str}", styles['Title']))
    story.append(Spacer(1, 12))
    
    # Add table of data
    data = [df.columns.tolist()] + df.values.tolist()
    table = Table(data)
    story.append(table)
    story.append(Spacer(1, 12))
    
    # Add summary text
    total = df["Production for the Day"].sum()
    story.append(Paragraph(f"Total Production: {total:,.2f} m³", styles['Normal']))
    story.append(Spacer(1, 12))
    
    # Add charts if provided
    if charts:
        for chart_type, fig in charts.items():
            try:
                # Explicitly use browser renderer for image export
                img_data = fig.to_image(format="png", width=400, height=300, scale=2, engine="browser")
                img_path = f"temp_{chart_type}.png"
                with open(img_path, "wb") as f:
                    f.write(img_data)
                story.append(Image(img_path, width=400, height=300))
                story.append(Spacer(1, 12))
                # Clean up temporary file
                os.remove(img_path)
            except Exception as e:
                st.warning(f"Failed to add {chart_type} chart to PDF: {e}")
                # Fallback: Add text note
                story.append(Paragraph(f"{chart_type} Chart: Export failed. See app logs for details.", styles['Normal']))
                story.append(Spacer(1, 12))
    
    doc.build(story)
    with open(buffer, "rb") as f:
        st.download_button("Download PDF Report", f.read(), file_name=filename, mime="application/pdf")

# ----------------------------
# UI: Login handling
# ----------------------------
if not logged_in():
    st.title("Production Dashboard — Login required")
    login_ui()
    st.sidebar.write("---")
    st.sidebar.caption("If you don't have credentials, please contact the admin.")
    st.stop()

# ----------------------------
# Main UI controls and header
# ----------------------------
st.sidebar.title("Controls")
st.sidebar.write(f"Logged in as: **{st.session_state.get('username','-')}**")
if st.sidebar.button("Logout"):
    logout()

mode = st.sidebar.radio("Mode", ["Upload New Data", "View Historical Data", "Manage Data", "Analytics"], index=1)
theme_choice = st.sidebar.selectbox("Theme", list(COLOR_THEMES.keys()), index=list(COLOR_THEMES.keys()).index(st.session_state.get("theme","Classic")))
st.session_state["theme"] = theme_choice
theme_colors = COLOR_THEMES[theme_choice]

alert_threshold = st.sidebar.number_input("Alert threshold (m³)", min_value=0.0, value=50.0, step=10.0)
st.sidebar.markdown("---")
st.sidebar.caption("Upload Excel with exact columns: Plant, Production for the Day, Accumulative Production.")

st.title("PRODUCTION FOR THE DAY")

# ----------------------------
# Upload mode
# ----------------------------
if mode == "Upload New Data":
    st.header("Upload new daily production file")
    uploaded = st.file_uploader("Upload Excel (.xlsx) containing: Plant, Production for the Day, Accumulative Production", type=["xlsx"])
    selected_date = st.date_input("Which date is this file for?", value=datetime.today())

    if uploaded:
        try:
            df_uploaded = pd.read_excel(uploaded)
            df_uploaded.columns = df_uploaded.columns.str.strip().str.replace("\n"," ").str.replace("  "," ")
        except Exception as e:
            st.error(f"Failed to read: {e}")
            st.stop()

        # Validate
        missing = [c for c in REQUIRED_COLS if c not in df_uploaded.columns]
        if missing:
            st.error(f"Missing columns: {missing}. Expected: {REQUIRED_COLS}")
        else:
            st.subheader("Preview")
            st.dataframe(df_uploaded.head(20))
            target_path = DATA_DIR / f"{selected_date.strftime('%Y-%m-%d')}.csv"
            overwrite = False
            if target_path.exists():
                overwrite = st.checkbox("File for this date already exists — check to overwrite", value=False)
            confirm = st.checkbox("I confirm this data is correct and ready to upload")
            if confirm and st.button("Upload & Save to History"):
                df_save = df_uploaded.copy()
                df_save["Date"] = selected_date.strftime("%Y-%m-%d")
                if pd.to_datetime(df_save["Date"].iloc[0]).day_name() == "Friday":
                    st.error("Selected date is Friday (non-production). Change date or cancel.")
                else:
                    try:
                        saved_path = save_csv(df_save, selected_date, overwrite=overwrite)
                    except FileExistsError as e:
                        st.error(str(e))
                        st.stop()
                    st.success(f"Saved to {saved_path}")
                    pushed, message = attempt_git_push(saved_path, f"Add production data for {selected_date.strftime('%Y-%m-%d')}")
                    if pushed:
                        st.success(message)
                    else:
                        st.warning(message)
                        st.info("If push failed, manually upload the CSV into your repo's data/ folder via GitHub UI.")

                    df_display = df_save[~df_save["Plant"].astype(str).str.upper().str.contains("TOTAL")]
                    df_display = safe_numeric(df_display)
                    st.markdown("### Totals")
                    total_daily = df_display["Production for the Day"].sum()
                    total_acc = df_display["Accumulative Production"].sum()
                    st.write(f"- Total Production for the Day: **{total_daily:,.2f} m³**")
                    st.write(f"- Total Accumulative Production: **{total_acc:,.2f} m³**")

                    alerts = df_display[df_display["Production for the Day"] < alert_threshold]
                    if not alerts.empty:
                        st.warning("⚠️ Plants below threshold:")
                        for _, r in alerts.iterrows():
                            st.write(f"- {r['Plant']}: {r['Production for the Day']} m³")

                    st.markdown("### Charts")
                    c1, c2 = st.columns(2)
                    with c1:
                        pie_fig = pie_chart(df_display, "Production for the Day", theme_colors, "Production share (Pie)")
                        st.plotly_chart(pie_fig, use_container_width=True)
                    with c2:
                        bar_fig = bar_chart(df_display, "Production for the Day", theme_colors, "Production per Plant (Bar)")
                        st.plotly_chart(bar_fig, use_container_width=True)
                    try:
                        line_fig = line_chart(df_display, "Production for the Day", theme_colors, "Production trend (Line)")
                        area_fig = area_chart(df_display, "Production for the Day", theme_colors, "Production flow (Area)")
                        st.plotly_chart(line_fig, use_container_width=True)
                        st.plotly_chart(area_fig, use_container_width=True)
                    except Exception as e:
                        st.warning(f"Additional charts error: {e}")

                    try:
                        acc_fig = bar_chart(df_display, "Accumulative Production", theme_colors, "Accumulative Production")
                        st.plotly_chart(acc_fig, use_container_width=True)
                    except Exception:
                        st.info("No accumulative chart available.")

                    try:
                        top = df_display.loc[df_display["Production for the Day"].idxmax()]
                        st.success(f"🏆 Highest Producer: {top['Plant']} — {float(top['Production for the Day']):,.2f} m³")
                    except Exception:
                        pass

                    # New: PDF Export with Charts in Upload mode
                    st.markdown("### Export Report")
                    charts = {"Pie": pie_fig, "Bar": bar_fig, "Line": line_fig, "Area": area_fig, "Accumulative": acc_fig}
                    generate_pdf_report(df_display, selected_date.strftime("%Y-%m-%d"), charts)

# ----------------------------
# View Historical Data
# ----------------------------
elif mode == "View Historical Data":
    st.header("Historical Data Viewer")
    saved_list = list_saved_dates()
    if not saved_list:
        st.info("No saved history yet.")
    else:
        selected = st.selectbox("Select date to view", saved_list, index=0)
        try:
            df_hist = load_saved(selected)
        except Exception as e:
            st.error(f"Unable to load: {e}")
            st.stop()

        if "Date" in df_hist.columns:
            try:
                df_hist["Date"] = pd.to_datetime(df_hist["Date"]).dt.strftime("%Y-%m-%d")
            except Exception:
                pass

        df_hist_disp = df_hist[~df_hist["Plant"].astype(str).str.upper().str.contains("TOTAL")]
        df_hist_disp = safe_numeric(df_hist_disp)

        st.subheader(f"Data for {selected}")
        st.dataframe(df_hist_disp, use_container_width=True)

        total_daily = df_hist_disp["Production for the Day"].sum()
        total_acc = df_hist_disp["Accumulative Production"].sum()
        st.markdown("### Totals")
        st.write(f"- Total: **{total_daily:,.2f} m³** — Accumulative: **{total_acc:,.2f} m³**")

        st.markdown("### Charts")
        c1, c2 = st.columns(2)
        with c1:
            pie_fig = pie_chart(df_hist_disp, "Production for the Day", theme_colors, f"Production share — {selected}")
            st.plotly_chart(pie_fig, use_container_width=True)
        with c2:
            bar_fig = bar_chart(df_hist_disp, "Production for the Day", theme_colors, f"Production per Plant — {selected}")
            st.plotly_chart(bar_fig, use_container_width=True)
        try:
            line_fig = line_chart(df_hist_disp, "Production for the Day", theme_colors, f"Production trend — {selected}")
            area_fig = area_chart(df_hist_disp, "Production for the Day", theme_colors, f"Production flow — {selected}")
            st.plotly_chart(line_fig, use_container_width=True)
            st.plotly_chart(area_fig, use_container_width=True)
        except Exception as e:
            st.warning(f"Chart error: {e}")

        if "Accumulative Production" in df_hist_disp.columns:
            try:
                acc_fig = bar_chart(df_hist_disp, "Accumulative Production", theme_colors, f"Accumulative — {selected}")
                st.plotly_chart(acc_fig, use_container_width=True)
            except Exception as e:
                st.warning(f"Acc cumulative chart error: {e}")
        else:
            st.warning("No 'Accumulative Production' column in this file.")

        try:
            frames = [load_saved(d) for d in list_saved_dates()]
            all_df = pd.concat(frames, ignore_index=True)
            ranks = compute_rankings(all_df, selected)
            st.markdown("### Rankings")
            ra, rb, rc = st.columns(3)
            with ra:
                st.write("Daily")
                st.dataframe(ranks['daily'].reset_index().rename(columns={'index':'Plant','Production for the Day':'Total'}))
            with rb:
                st.write("Weekly (last 7 days)")
                st.dataframe(ranks['weekly'].reset_index().rename(columns={'index':'Plant','Production for the Day':'Total'}))
            with rc:
                st.write("Monthly (last 30 days)")
                st.dataframe(ranks['monthly'].reset_index().rename(columns={'index':'Plant','Production for the Day':'Total'}))
        except Exception:
            st.info("Not enough data for rankings.")

        try:
            frames = [load_saved(d) for d in list_saved_dates()]
            all_hist = pd.concat(frames, ignore_index=True)
            summary_md = ai_summary(df_hist_disp, all_hist, selected)
            st.markdown("### Quick Summary")
            st.markdown(summary_md)
        except Exception:
            pass

        # New: PDF Export with Charts in Historical mode
        st.markdown("### Export Report")
        charts = {"Pie": pie_fig, "Bar": bar_fig, "Line": line_fig, "Area": area_fig, "Accumulative": acc_fig}
        generate_pdf_report(df_hist_disp, selected, charts)

# ----------------------------
# Manage Data
# ----------------------------
elif mode == "Manage Data":
    st.header("Manage saved files (rename / delete)")
    saved_list = list_saved_dates()
    if not saved_list:
        st.info("No saved files.")
    else:
        chosen = st.selectbox("Select date", saved_list)
        action = st.radio("Action", ["Rename", "Delete"])

        if action == "Rename":
            new_date = st.date_input("Choose new date", value=datetime.today())
            if st.button("Confirm rename"):
                try:
                    ok = rename_saved(chosen, new_date.strftime("%Y-%m-%d"))
                    if ok:
                        st.success(f"Renamed {chosen} → {new_date.strftime('%Y-%m-%d')}")
                    else:
                        st.error("Rename failed.")
                except Exception as e:
                    st.error(f"Rename error: {e}")
        else:
            st.warning("This will permanently delete the selected file.")
            if st.button("Confirm delete"):
                try:
                    if delete_saved(chosen):
                        st.success("Deleted.")
                    else:
                        st.error("Delete failed.")
                except Exception as e:
                    st.error(f"Delete error: {e}")

# ----------------------------
# Analytics
# ----------------------------
elif mode == "Analytics":
    st.header("Analytics & trends (multi-day)")
    saved = list_saved_dates()
    if len(saved) < 2:
        st.info("Upload at least two days to see multi-day analytics.")
    else:
        # Custom date range filter
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", value=datetime.today() - timedelta(days=30))
        with col2:
            end_date = st.date_input("End Date", value=datetime.today())
        
        frames = [load_saved(d) for d in saved]
        all_df = pd.concat(frames, ignore_index=True)
        all_df['Date'] = pd.to_datetime(all_df['Date'])
        
        # Filter data
        filtered_df = all_df[(all_df['Date'] >= pd.to_datetime(start_date)) & (all_df['Date'] <= pd.to_datetime(end_date))]
        if filtered_df.empty:
            st.warning("No data in selected range.")
        else:
            totals = filtered_df.groupby('Date')['Production for the Day'].sum().reset_index().sort_values('Date')
            totals['7d_ma'] = totals['Production for the Day'].rolling(7, min_periods=1).mean()
            trend_fig = px.line(totals, x='Date', y=['Production for the Day','7d_ma'], labels={'value':'m³','variable':'Metric'}, title=f"Production Trend ({start_date} to {end_date}")
            st.plotly_chart(trend_fig, use_container_width=True)
            
            # Weekly and Monthly Analysis
            filtered_df['Week'] = filtered_df['Date'].dt.isocalendar().week
            filtered_df['Month'] = filtered_df['Date'].dt.month
            weekly_fig = aggregated_bar_chart(filtered_df, "Production for the Day", "Week", theme_colors, "Weekly Production Totals")
            monthly_fig = aggregated_bar_chart(filtered_df, "Production for the Day", "Month", theme_colors, "Monthly Production Totals")
            st.plotly_chart(weekly_fig, use_container_width=True)
            st.plotly_chart(monthly_fig, use_container_width=True)
            
            # Top plants over the range
            st.markdown("Top plants over the selected range")
            pivot = filtered_df.groupby(['Date','Plant'])['Production for the Day'].sum().reset_index()
            topplants = pivot.groupby('Plant')['Production for the Day'].sum().nlargest(5).index.tolist()
            if topplants:
                top_fig = px.line(pivot[pivot['Plant'].isin(topplants)], x='Date', y='Production for the Day', color='Plant')
                st.plotly_chart(top_fig, use_container_width=True)

            # New: PDF Export with Charts in Analytics mode
            st.markdown("### Export Report")
            charts = {"Trend": trend_fig, "Weekly": weekly_fig, "Monthly": monthly_fig, "Top Plants": top_fig}
            generate_pdf_report(filtered_df, f"{start_date} to {end_date}", charts)

# ----------------------------
# Sidebar help & closing
# ----------------------------
st.sidebar.markdown("---")
st.sidebar.write("If Git push fails: set GITHUB_TOKEN & GITHUB_REPO in Streamlit Secrets (TOML), then restart app.")
st.sidebar.write("Or manually download CSV from the app container and upload to your repo's data/ folder.")
