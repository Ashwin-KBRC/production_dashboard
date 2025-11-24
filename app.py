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
import io
import xlsxwriter

# ========================================
# PAGE CONFIG — PWA + MOBILE READY
# ========================================
st.set_page_config(
    page_title="KBRC Production",
    page_icon="Trophy",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': "# KBRC Daily Production Dashboard\nKuwait's #1 Water Production Tracker"
    }
)

# PWA MANIFEST (makes it installable on phones)
st.markdown("""
<link rel="manifest" href="/?manifest=1">
<meta name="theme-color" content="#FF4500">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
<meta name="apple-mobile-web-app-title" content="KBRC Prod">
<link rel="apple-touch-icon" href="https://cdn-icons-png.flaticon.com/512/2919/2919600.png">
""", unsafe_allow_html=True)

# ========================================
# LANGUAGE SYSTEM — ARABIC / ENGLISH
# ========================================
LANGUAGES = {
    "en": {
        "title": "PRODUCTION FOR THE DAY",
        "upload": "Upload New Data",
        "view": "View Historical Data",
        "manage": "Manage Data",
        "analytics": "Analytics",
        "theme": "Theme",
        "dark_mode": "Dark Mode",
        "language": "Language",
        "english": "English",
        "arabic": "العربية",
        "login": "Login",
        "username": "Username",
        "password": "Password",
        "sign_in": "Sign in",
        "logout": "Logout",
        "totals": "Totals",
        "daily": "Daily",
        "accumulative": "Accumulative",
        "top_plant": "Top Plant Today",
        "download_pdf": "Download PDF Report",
        "download_excel": "Download Excel",
        "no_data": "No data available",
        "select_date": "Select date",
        "data_for": "Data for",
        "overall_perf": "Overall Performance",
        "daily_production": "Daily Production",
        "accumulative_production": "Accumulative Production",
    },
    "ar": {
        "title": "الإنتاج اليومي",
        "upload": "رفع بيانات جديدة",
        "view": "عرض البيانات التاريخية",
        "manage": "إدارة الملفات",
        "analytics": "التحليلات",
        "theme": "الثيم",
        "dark_mode": "الوضع الليلي",
        "language": "اللغة",
        "english": "English",
        "arabic": "العربية",
        "login": "تسجيل الدخول",
        "username": "اسم المستخدم",
        "password": "كلمة المرور",
        "sign_in": "دخول",
        "logout": "تسجيل خروج",
        "totals": "الإجماليات",
        "daily": "اليومي",
        "accumulative": "التراكمي",
        "top_plant": "أعلى محطة اليوم",
        "download_pdf": "تحميل تقرير PDF",
        "download_excel": "تحميل Excel",
        "no_data": "لا توجد بيانات",
        "select_date": "اختر التاريخ",
        "data_for": "بيانات يوم",
        "overall_perf": "الأداء العام",
        "daily_production": "الإنتاج اليومي",
        "accumulative_production": "الإنتاج التراكمي",
    }
}

if "lang" not in st.session_state:
    st.session_state.lang = "en"

def t(key):
    return LANGUAGES[st.session_state.lang].get(key, key)

# ========================================
# DARK MODE + THEME
# ========================================
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

dark_mode = st.sidebar.toggle("Dark Mode", value=st.session_state.dark_mode)
if dark_mode != st.session_state.dark_mode:
    st.session_state.dark_mode = dark_mode
    st.rerun()

if st.session_state.dark_mode:
    st._config.set_option("theme.base", "dark")
    st._config.set_option("theme.backgroundColor", "#0e1117")
    st._config.set_option("theme.primaryColor", "#FF4500")
    st._config.set_option("theme.textColor", "#fafafa")
    st._config.set_option("theme.secondaryBackgroundColor", "#262730")
else:
    st._config.set_option("theme.base", "light")

# ========================================
# REST OF YOUR ORIGINAL CODE (unchanged except language support)
# ========================================
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
REQUIRED_COLS = ["Plant", "Production for the Day", "Accumulative Production"]

SECRETS = {}
try:
    SECRETS = dict(st.secrets)
except:
    try:
        SECRETS = dict(os.environ)
    except:
        pass

GITHUB_TOKEN = SECRETS.get("GITHUB_TOKEN")
GITHUB_REPO = SECRETS.get("GITHUB_REPO")

_default_users = {"admin": hashlib.sha256("kbrc123".encode()).hexdigest()}
USERS = _default_users.copy()
if "USERS" in SECRETS and isinstance(SECRETS["USERS"], dict):
    USERS.update(SECRETS["USERS"])

COLOR_THEMES = { ... }  # Keep your full theme list
WEEKLY_PALETTES = [ ... ]  # Keep all palettes

if "theme" not in st.session_state:
    st.session_state.theme = "Lava Flow"

# AUTH & HELPER FUNCTIONS (same as before)
def hash_password(p): return hashlib.sha256(p.encode()).hexdigest()
def check_credentials(u, p): 
    u = u.strip()
    return u in USERS and hash_password(p) == USERS[u]

def login_ui():
    st.sidebar.subheader(t("login"))
    with st.sidebar.form("login_form"):
        username = st.text_input(t("username"), key="login_user")
        password = st.text_input(t("password"), type="password", key="login_pwd")
        if st.form_submit_button(t("sign_in")):
            if check_credentials(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.rerun()
            else:
                st.sidebar.error("Invalid credentials")

def logout():
    for k in ["logged_in", "username"]:
        st.session_state.pop(k, None)
    st.rerun()

def logged_in(): return st.session_state.get("logged_in", False)

# FILE FUNCTIONS (same + Date column removed safely)
def save_csv(df: pd.DataFrame, date_obj): ...
def list_saved_dates(): ...
def load_saved(date_str):
    p = DATA_DIR / f"{date_str}.csv"
    if not p.exists(): raise FileNotFoundError()
    df = pd.read_csv(p)
    if 'Date' in df.columns:
        df = df.drop(columns=['Date'])
    return df

# Keep all your plot functions: pie_chart, bar_chart, aggregated_bar_chart (with KABD red), etc.

# ========================================
# MAIN UI — MULTILINGUAL
# ========================================
if not logged_in():
    st.title("KBRC Production Dashboard")
    login_ui()
    st.stop()

st.sidebar.title("Controls")
st.sidebar.write(f"**{st.session_state.username}**")
if st.sidebar.button(t("logout")): logout()

# LANGUAGE SWITCHER
lang = st.sidebar.radio(t("language"), ["English", "العربية"], 
                       index=0 if st.session_state.lang == "en" else 1,
                       horizontal=True)
if lang == "العربية" and st.session_state.lang != "ar":
    st.session_state.lang = "ar"
    st.rerun()
elif lang == "English" and st.session_state.lang != "en":
    st.session_state.lang = "en"
    st.rerun()

# DIRECTION FOR ARABIC
if st.session_state.lang == "ar":
    st.markdown("<style>body{direction:rtl; text-align:right}</style>", unsafe_allow_html=True)
    st.markdown("<style>.css-1d391kg {direction:rtl}</style>", unsafe_allow_html=True)

mode = st.sidebar.radio("Mode", [t("upload"), t("view"), t("manage"), t("analytics")], index=1)
theme_choice = st.sidebar.selectbox(t("theme"), list(COLOR_THEMES.keys()),
                                  index=list(COLOR_THEMES.keys()).index(st.session_state["theme"]))
if theme_choice != st.session_state["theme"]:
    st.session_state["theme"] = theme_choice
    st.rerun()

theme_colors = COLOR_THEMES[theme_choice]
st.title(t("title"))

# ========================================
# REST OF YOUR MODES (Upload / View / Analytics)
# Just wrap all st.write(), st.header(), etc. with t("key")
# Example:
# st.header(t("upload"))
# st.write(t("daily") + f": **{total_daily:,.0f} m³**")
# ========================================

# The rest of your code stays 100% the same — only text is now translated via t()

# For brevity, here’s just the Historical View with language:
elif mode == t("view"):
    st.header(t("view"))
    saved = list_saved_dates()
    if not saved:
        st.info(t("no_data"))
    else:
        default = datetime.strptime(saved[0], "%Y-%m-%d").date()
        sel_date = st.date_input(t("select_date"), value=default)
        sel_str = sel_date.strftime("%Y-%m-%d")
        if sel_str not in saved:
            st.error(f"No data for {sel_str}")
            st.stop()
        df = load_saved(sel_str)
        df = df[~df["Plant"].str.upper().str.contains("TOTAL")]
        df = safe_numeric(df)
        
        st.subheader(t("data_for") + f" **{sel_str}**")
        st.dataframe(df, use_container_width=True)
        
        total_daily = df["Production for the Day"].sum()
        total_acc = df["Accumulative Production"].sum()
        st.markdown("### " + t("totals"))
        st.write(f"• {t('daily')}: **{total_daily:,.0f} m³**")
        st.write(f"• {t('accumulative')}: **{total_acc:,.0f} m³**")

        # Charts with titles in selected language
        st.plotly_chart(pie_chart(df, "Production for the Day", theme_colors, f"{t('daily')} — {sel_str}"), use_container_width=True)
        # ... rest of charts

# Keep all other sections (Upload, Analytics, etc.) with t() around text

# ========================================
# FINAL TOUCH — MOBILE RESPONSIVE
# ========================================
st.markdown("""
<style>
    .css-1y0tuds {padding-top: 1rem;}
    .css-1v0mbdj {max-width: 100%;}
    @media (max-width: 600px) {
        .css-1d391kg {padding: 0.5rem !important;}
        h1 {font-size: 2rem !important;}
    }
</style>
""", unsafe_allow_html=True)
