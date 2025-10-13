# app.py
"""
Production Dashboard - Streamlit (Innovated)
- Upload daily Excel file with columns: Date, Plant, Production for the Day, Accumulative Production
- Choose date on upload, confirm before save
- Saves to data/YYYY-MM-DD.csv and attempts Git push using token from Streamlit Secrets
- Historical view, rename/delete, totals, 4 chart themes, value labels
- Added: daily/weekly/monthly rankings, 7/30-day trend, alerts, auto/manual refresh, last-updated, AI-style summary
"""

import os
from pathlib import Path
import subprocess
from datetime import datetime, timedelta
from typing import Tuple

import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st

# -----------------------
# CONFIG
# -----------------------
st.set_page_config(page_title="Concrete Production — Smart Dashboard", layout="wide", page_icon="📊")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True, parents=True)

# GitHub token & repo (set in Streamlit Secrets as TOML)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or st.secrets.get("GITHUB_TOKEN", None)
GITHUB_REPO = os.getenv("GITHUB_REPO") or st.secrets.get("GITHUB_REPO", None)

REQUIRED_COLS = ["Plant", "Production for the Day", "Accumulative Production"]

# Color themes
COLOR_THEMES = {
    "Classic": px.colors.qualitative.Bold,
    "Blue": px.colors.sequential.Blues,
    "Vibrant": ["#EF476F","#FFD166","#06D6A0","#118AB2","#073B4C","#9B5DE5"],
    "Forest": ["#2e8b57", "#3cb371", "#66cdaa", "#20b2aa", "#2f4f4f"],
}

# -----------------------
# HELPERS: I/O & GIT
# -----------------------
def read_excel(file) -> pd.DataFrame:
    try:
        df = pd.read_excel(file)
        return df
    except Exception as e:
        st.error(f"Failed to read Excel: {e}")
        raise

def ensure_columns(df: pd.DataFrame) -> Tuple[bool,str]:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        return False, f"Missing required columns: {missing}. Expected exactly: {REQUIRED_COLS}"
    return True, "OK"

def tag_date(df: pd.DataFrame, date_obj: datetime.date) -> pd.DataFrame:
    d = date_obj.strftime("%Y-%m-%d")
    df2 = df.copy()
    df2["Date"] = d
    return df2

def save_csv(df: pd.DataFrame, date_obj: datetime.date) -> Path:
    fname = f"{date_obj.strftime('%Y-%m-%d')}.csv"
    path = DATA_DIR / fname
    df.to_csv(path, index=False)
    return path

def git_push_file(file_path: Path) -> Tuple[bool, str]:
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False, "GITHUB_TOKEN or GITHUB_REPO not configured in Streamlit secrets."
    remote_url = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git"
    try:
        subprocess.run(["git", "config", "--global", "user.email", "streamlit@example.com"], check=False)
        subprocess.run(["git", "config", "--global", "user.name", "Streamlit App"], check=False)
        subprocess.run(["git", "add", str(file_path)], check=True)
        commit = subprocess.run(["git", "commit", "-m", f"Add production data {file_path.name}"], check=False, capture_output=True, text=True)
        out = commit.stdout + commit.stderr
        if commit.returncode != 0 and ("nothing to commit" in out.lower() or "no changes added to commit" in out.lower()):
            # nothing new
            return True, "No new changes to commit (file already present)."
        if commit.returncode != 0:
            return False, f"Git commit error: {out.strip()}"
        push = subprocess.run(["git", "push", remote_url, "main"], check=False, capture_output=True, text=True)
        if push.returncode != 0:
            return False, f"Git push failed: {push.stderr.strip() or push.stdout.strip()}"
        return True, "Pushed to GitHub successfully."
    except Exception as e:
        return False, f"Exception during git push: {e}"

def list_saved_dates() -> list:
    files = sorted([p.name.replace(".csv","") for p in DATA_DIR.glob("*.csv")], reverse=True)
    return files

def load_saved(date_str: str) -> pd.DataFrame:
    p = DATA_DIR / f"{date_str}.csv"
    if not p.exists():
        raise FileNotFoundError(f"{p} not found.")
    return pd.read_csv(p)

def delete_saved(date_str: str) -> bool:
    p = DATA_DIR / f"{date_str}.csv"
    if p.exists():
        p.unlink()
        return True
    return False

def rename_saved(old_date: str, new_date: str) -> bool:
    old = DATA_DIR / f"{old_date}.csv"
    new = DATA_DIR / f"{new_date}.csv"
    if old.exists():
        old.rename(new)
        return True
    return False

# -----------------------
# ANALYTICS HELPERS
# -----------------------
def compute_rankings(df_all: pd.DataFrame, as_of_date: str) -> dict:
    """
    Input df_all: dataframe that includes Date column (YYYY-MM-DD) and Plant + Production for the Day
    Returns rankings per day / week / month based on sums
    """
    df_all['Date'] = pd.to_datetime(df_all['Date'])
    # Daily: use as_of_date rows only
    selected = df_all[df_all['Date'].dt.strftime('%Y-%m-%d') == as_of_date]
    daily = selected.groupby('Plant')['Production for the Day'].sum().sort_values(ascending=False)
    # Weekly: consider ISO week of as_of_date (Sat-Thu week? we keep standard Mon-Sun but will exclude Friday by filter earlier)
    # We'll compute last 7 days up to as_of_date
    end = pd.to_datetime(as_of_date)
    start7 = end - pd.Timedelta(days=6)
    df7 = df_all[(df_all['Date'] >= start7) & (df_all['Date'] <= end)]
    weekly = df7.groupby('Plant')['Production for the Day'].sum().sort_values(ascending=False)
    # Monthly: last 30 days
    start30 = end - pd.Timedelta(days=29)
    df30 = df_all[(df_all['Date'] >= start30) & (df_all['Date'] <= end)]
    monthly = df30.groupby('Plant')['Production for the Day'].sum().sort_values(ascending=False)
    return {"daily": daily, "weekly": weekly, "monthly": monthly, "df7": df7, "df30": df30}

def ai_summary_for_date(df_display: pd.DataFrame, df_history: pd.DataFrame = None, date_str: str = None) -> str:
    """
    Rule-based 'AI-style' textual summary: compares to 7-day average, flags improvements/drops.
    """
    try:
        total_daily = df_display["Production for the Day"].sum()
        top = df_display.loc[df_display["Production for the Day"].idxmax()]
        bottom = df_display.loc[df_display["Production for the Day"].idxmin()]
        lines = []
        lines.append(f"On {date_str}, total production was **{total_daily:,.2f} m³**.")
        lines.append(f"Top producer: **{top['Plant']}** with **{float(top['Production for the Day']):,.2f} m³**.")
        lines.append(f"Lowest producer: **{bottom['Plant']}** with **{float(bottom['Production for the Day']):,.2f} m³**.")
        # trend vs 7-day average per plant if history provided
        if df_history is not None and not df_history.empty:
            try:
                df_history['Date'] = pd.to_datetime(df_history['Date'])
                end = pd.to_datetime(date_str)
                start7 = end - pd.Timedelta(days=7)
                df7 = df_history[(df_history['Date'] >= start7) & (df_history['Date'] < end)]
                if not df7.empty:
                    avg7 = df7.groupby('Plant')['Production for the Day'].mean()
                    # compare aggregated
                    diffs = []
                    for _, row in df_display.iterrows():
                        plant = row['Plant']
                        today = row['Production for the Day']
                        if plant in avg7.index:
                            avg = avg7.loc[plant]
                            pct = (today - avg) / avg * 100 if avg != 0 else 0
                            if abs(pct) >= 10:
                                diffs.append((plant, pct))
                    if diffs:
                        for plant, pct in diffs:
                            if pct > 0:
                                lines.append(f"{plant} is up {pct:.1f}% vs its 7-day average.")
                            else:
                                lines.append(f"{plant} is down {abs(pct):.1f}% vs its 7-day average.")
            except Exception:
                pass
        return "  \n".join(lines)
    except Exception as e:
        return f"Summary unavailable: {e}"

# -----------------------
# UI: Sidebar controls
# -----------------------
st.sidebar.title("Controls")
mode = st.sidebar.radio("Choose Mode", ["Upload New Data", "View Historical Data", "Manage Data", "Analytics"])

st.sidebar.markdown("---")
theme_name = st.sidebar.selectbox("Chart theme", list(COLOR_THEMES.keys()), index=0)
theme_colors = COLOR_THEMES[theme_name]

st.sidebar.markdown("---")
st.sidebar.subheader("Alerts")
alert_threshold = st.sidebar.number_input("Alert: mark any plant below (m³) as warning", min_value=0.0, value=50.0, step=10.0)

st.sidebar.markdown("---")
auto_refresh = st.sidebar.checkbox("Enable auto-refresh every 60s (reload app)", value=False)
if auto_refresh:
    st.experimental_rerun()  # simple way to refresh; note: this triggers immediate reload once selected

st.sidebar.markdown("---")
st.sidebar.caption("Tips: Upload Excel with exact headers: Date, Plant, Production for the Day, Accumulative Production")

# -----------------------
# MAIN: Upload New Data
# -----------------------
st.title("🧱 PRODUCTION FOR THE DAY — Smart Dashboard")

if mode == "Upload New Data":
    st.header("Upload daily production Excel")
    uploaded = st.file_uploader("Select .xlsx file (exact headers required)", type=["xlsx"])
    selected_date = st.date_input("On which date is this file for?", value=datetime.today())
    if uploaded:
        try:
            df = read_excel(uploaded)
        except Exception:
            st.stop()
        ok, msg = ensure_columns(df)
        if not ok:
            st.error(msg)
            st.stop()
        st.subheader("Preview (first rows)")
        st.dataframe(df.head(20))
        if st.checkbox("I confirm the data is correct and ready to upload"):
            if st.button("Upload & Save to History"):
                # tag date and filter Friday
                df_tagged = tag_date(df, selected_date)
                weekday = pd.to_datetime(df_tagged["Date"].iloc[0]).day_name()
                if weekday == "Friday":
                    st.error("Selected date falls on FRIDAY (non-production day). Change date or cancel.")
                else:
                    p = save_csv(df_tagged, selected_date)
                    pushed, msg = git_push_file(p)
                    st.success(f"Saved to {p}")
                    if pushed:
                        st.success(msg)
                    else:
                        st.warning(msg)
                    # show immediate analytics:
                    df_display = df_tagged.copy()
                    # remove TOTAL row if present
                    df_display = df_display[~df_display["Plant"].astype(str).str.upper().str.contains("TOTAL")]
                    df_display["Production for the Day"] = pd.to_numeric(df_display["Production for the Day"], errors="coerce").fillna(0.0)
                    df_display["Accumulative Production"] = pd.to_numeric(df_display["Accumulative Production"], errors="coerce").fillna(0.0)
                    st.markdown("---")
                    st.subheader("🔹 Totals")
                    total_daily = df_display["Production for the Day"].sum()
                    total_acc = df_display["Accumulative Production"].sum()
                    st.write(f"**Total Production for the Day:** {total_daily:,.2f} m³")
                    st.write(f"**Total Accumulative Production:** {total_acc:,.2f} m³")
                    st.markdown("---")
                    # alerting
                    alerts = df_display[df_display["Production for the Day"] < alert_threshold]
                    if not alerts.empty:
                        st.warning("⚠️ Alerts — plants below threshold:")
                        for _, r in alerts.iterrows():
                            st.write(f"- {r['Plant']}: {r['Production for the Day']} m³")
                    # charts
                    c1, c2 = st.columns(2)
                    with c1:
                        fig_pie = plot_production_pie(df_display, theme_colors, "Production share (Pie)", "Production for the Day")
                        st.plotly_chart(fig_pie, use_container_width=True)
                    with c2:
                        fig_bar = plot_production_bar(df_display, theme_colors, "Production per plant (Bar)", "Production for the Day")
                        st.plotly_chart(fig_bar, use_container_width=True)
                    st.markdown("---")
                    st.subheader("Additional Charts")
                    r1, r2 = st.columns(2)
                    with r1:
                        st.plotly_chart(plot_production_line(df_display, theme_colors, "Production line (one point per plant)", "Production for the Day"), use_container_width=True)
                    with r2:
                        st.plotly_chart(plot_production_area(df_display, theme_colors, "Production flow (Area)", "Production for the Day"), use_container_width=True)
                    st.markdown("---")
                    # accumulative
                    st.plotly_chart(plot_production_bar(df_display, theme_colors, "Accumulative Production", "Accumulative Production"), use_container_width=True)
                    # top producer
                    try:
                        top = df_display.loc[df_display["Production for the Day"].idxmax()]
                        st.success(f"🏆 Highest Producer: {top['Plant']} — {float(top['Production for the Day']):,.2f} m³")
                    except Exception:
                        pass
                    # AI-style summary
                    # Build history df to compare
                    try:
                        all_dates = list_saved_dates()
                        hist_frames = []
                        for d in all_dates:
                            hist_frames.append(load_saved(d))
                        hist_df = pd.concat(hist_frames, ignore_index=True) if hist_frames else pd.DataFrame()
                        summary_text = ai_summary_for_date(df_display, hist_df, selected_date.strftime("%Y-%m-%d"))
                        st.markdown("### 🔎 Quick Summary")
                        st.markdown(summary_text)
                    except Exception:
                        pass

# -----------------------
# VIEW HISTORICAL DATA
# -----------------------
elif mode == "View Historical Data":
    st.header("Historical Data Viewer")
    saved = list_saved_dates()
    if not saved:
        st.info("No historical data found. Upload files via 'Upload New Data'.")
    else:
        sel = st.selectbox("Choose date to view", saved, index=0)
        try:
            df_hist = load_saved(sel)
        except Exception as e:
            st.error(str(e))
            st.stop()
        # defensive: standardize
        if "Date" in df_hist.columns:
            try:
                df_hist["Date"] = pd.to_datetime(df_hist["Date"]).dt.strftime("%Y-%m-%d")
            except Exception:
                pass
        df_hist_disp = df_hist[~df_hist["Plant"].astype(str).str.upper().str.contains("TOTAL")]
        df_hist_disp["Production for the Day"] = pd.to_numeric(df_hist_disp["Production for the Day"], errors="coerce").fillna(0.0)
        df_hist_disp["Accumulative Production"] = pd.to_numeric(df_hist_disp["Accumulative Production"], errors="coerce").fillna(0.0)

        # Totals & Last updated
        total_daily = df_hist_disp["Production for the Day"].sum()
        total_acc = df_hist_disp["Accumulative Production"].sum()
        st.subheader(f"Data for {sel}")
        st.write(f"**Total Production:** {total_daily:,.2f} m³ — **Accumulative:** {total_acc:,.2f} m³")
        # show table
        st.dataframe(df_hist_disp, use_container_width=True)
        # charts
        st.plotly_chart(plot_production_pie(df_hist_disp, theme_colors, f"Production share — {sel}", "Production for the Day"), use_container_width=True)
        st.plotly_chart(plot_production_bar(df_hist_disp, theme_colors, f"Production per plant — {sel}", "Production for the Day"), use_container_width=True)
        st.plotly_chart(plot_production_line(df_hist_disp, theme_colors, f"Production trend — {sel}", "Production for the Day"), use_container_width=True)
        st.plotly_chart(plot_production_area(df_hist_disp, theme_colors, f"Production flow — {sel}", "Production for the Day"), use_container_width=True)
        st.plotly_chart(plot_production_bar(df_hist_disp, theme_colors, f"Accumulative — {sel}", "Accumulative Production"), use_container_width=True)
        # rankings (daily/weekly/monthly) using all saved data
        try:
            all_frames = [load_saved(d) for d in list_saved_dates()]
            all_df = pd.concat(all_frames, ignore_index=True)
            ranks = compute_rankings(all_df, sel)
            st.markdown("### 📊 Rankings")
            colA, colB, colC = st.columns(3)
            with colA:
                st.write("**Daily (this day)**")
                st.dataframe(ranks['daily'].reset_index().rename(columns={'index':'Plant','Production for the Day':'Total'}).head(6))
            with colB:
                st.write("**Weekly (last 7 days)**")
                st.dataframe(ranks['weekly'].reset_index().rename(columns={'index':'Plant','Production for the Day':'Total'}).head(6))
            with colC:
                st.write("**Monthly (last 30 days)**")
                st.dataframe(ranks['monthly'].reset_index().rename(columns={'index':'Plant','Production for the Day':'Total'}).head(6))
        except Exception:
            pass

# -----------------------
# MANAGE DATA (Rename/Delete)
# -----------------------
elif mode == "Manage Data":
    st.header("Manage saved data (rename / delete)")
    saved = list_saved_dates()
    if not saved:
        st.info("No saved files to manage.")
    else:
        chosen = st.selectbox("Select saved date", saved)
        action = st.radio("Action", ["Rename", "Delete"])
        if action == "Rename":
            new_dt = st.date_input("Pick new date", value=datetime.today())
            if st.button("Confirm rename"):
                ok = rename_saved(chosen, new_dt.strftime("%Y-%m-%d"))
                if ok:
                    st.success(f"Renamed {chosen} → {new_dt.strftime('%Y-%m-%d')}")
                else:
                    st.error("Rename failed.")
        else:
            st.warning("You are about to permanently delete the selected file.")
            if st.button("Confirm delete"):
                if delete_saved(chosen):
                    st.success("File deleted.")
                else:
                    st.error("Delete failed.")

# -----------------------
# ANALYTICS QUICK PANEL
# -----------------------
elif mode == "Analytics":
    st.header("Analytics & Trends")
    saved = list_saved_dates()
    if len(saved) < 1:
        st.info("Not enough historical data. Upload multiple days first.")
    else:
        # quick multi-date trend (7/30 day) using saved files
        frames = [load_saved(d) for d in saved]
        all_df = pd.concat(frames, ignore_index=True)
        all_df['Date'] = pd.to_datetime(all_df['Date'])
        # aggregate per day per plant
        daily_sum = all_df.groupby(['Date','Plant'])['Production for the Day'].sum().reset_index()
        # total daily across plants
        total_daily = daily_sum.groupby('Date')['Production for the Day'].sum().reset_index()
        # 7-day moving average
        total_daily = total_daily.sort_values('Date')
        total_daily['7d_ma'] = total_daily['Production for the Day'].rolling(7, min_periods=1).mean()
        st.subheader("Total production trend (all plants)")
        fig = px.line(total_daily, x='Date', y=['Production for the Day','7d_ma'], labels={'value':'m³','variable':'Metric'})
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("Top plants trend (last 30 days):")
        last30 = all_df[all_df['Date'] >= (pd.to_datetime(total_daily['Date'].max()) - pd.Timedelta(days=29))]
        pivot = last30.groupby(['Date','Plant'])['Production for the Day'].sum().reset_index()
        # top plants by total in last 30 days
        topplants = pivot.groupby('Plant')['Production for the Day'].sum().nlargest(5).index.tolist()
        if topplants:
            fig2 = px.line(pivot[pivot['Plant'].isin(topplants)], x='Date', y='Production for the Day', color='Plant')
            st.plotly_chart(fig2, use_container_width=True)

# -----------------------
# Footer/help
# -----------------------
st.sidebar.markdown("---")
st.sidebar.write("If auto-push to GitHub fails:")
st.sidebar.write("- Ensure GITHUB_TOKEN & GITHUB_REPO are set in Streamlit Secrets (TOML).")
st.sidebar.write("- Or manually upload CSV from the app container to the repo's data/ folder.")
