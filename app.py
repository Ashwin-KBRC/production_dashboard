import streamlit as st
import pandas as pd
import plotly.express as px
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Tuple

# =========================================
# Configuration and Secrets
# =========================================
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
GITHUB_REPO = st.secrets.get("GITHUB_REPO", "")
GITHUB_USER = st.secrets.get("GITHUB_USER", "")
GITHUB_EMAIL = st.secrets.get("GITHUB_EMAIL", "")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# =========================================
# 1. PASSWORD LOGIN
# =========================================
def login_ui():
    st.title("🔒 Secure Production Dashboard Login")
    password = st.text_input("Enter password:", type="password")
    if st.button("Login"):
        if password == "kbrc@2025":  # You can change this password
            st.session_state.logged_in = True
            st.experimental_rerun()
        else:
            st.error("Incorrect password. Try again.")

if "logged_in" not in st.session_state or not st.session_state.logged_in:
    login_ui()
    st.stop()

# =========================================
# 2. App Layout
# =========================================
st.title("🏭 Production Dashboard")

tab1, tab2, tab3 = st.tabs(["📤 Upload & Save", "📊 View History", "⚙️ Settings"])

# =========================================
# Helper Functions
# =========================================
def save_uploaded_file(uploaded_file, selected_date):
    """Save uploaded Excel data to CSV."""
    df = pd.read_excel(uploaded_file)
    save_path = DATA_DIR / f"{selected_date}.csv"
    df.to_csv(save_path, index=False)
    return save_path

def load_data(file_path):
    """Load CSV data."""
    return pd.read_csv(file_path)

# =========================================
# 3. Upload and Save Tab
# =========================================
with tab1:
    st.header("📅 Upload Daily Production File")

    uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx", "xls"])
    selected_date = st.date_input("Select Date")
    confirm = st.checkbox("I confirm this data is correct and ready to upload")

    if uploaded_file and confirm:
        if st.button("Upload & Save to History"):
            save_path = save_uploaded_file(uploaded_file, selected_date)
            st.success(f"✅ Saved data to {save_path}")

            ok, msg = attempt_git_push(save_path, f"Add production data for {selected_date}")
            if ok:
                st.success(msg)
            else:
                st.warning(msg)
    else:
        st.info("Please upload a file and confirm before saving.")

# =========================================
# 4. Historical Data Viewer
# =========================================
with tab2:
    st.header("📈 Production History")
    files = sorted(DATA_DIR.glob("*.csv"))

    if not files:
        st.warning("No saved data yet.")
    else:
        file_dates = [f.stem for f in files]
        sel = st.selectbox("Select a date to view:", file_dates)

        if sel:
            df_hist = load_data(DATA_DIR / f"{sel}.csv")
            st.dataframe(df_hist)

            st.subheader("Production Summary")
            try:
                # Pie Chart of Production Share
                fig = px.pie(df_hist, names=df_hist.columns[0], values=df_hist.columns[1],
                             title=f"Production Share — {sel}")
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Error generating chart: {e}")

# =========================================
# 5. Settings / Maintenance Tab
# =========================================
with tab3:
    st.header("⚙️ Data Management")
    files = sorted(DATA_DIR.glob("*.csv"))
    if files:
        selected_file = st.selectbox("Select a file to rename or delete", [f.name for f in files])
        new_name = st.text_input("Rename to (YYYY-MM-DD):", "")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Rename"):
                if new_name:
                    os.rename(DATA_DIR / selected_file, DATA_DIR / f"{new_name}.csv")
                    st.success(f"Renamed {selected_file} → {new_name}.csv")
                    st.experimental_rerun()
        with col2:
            if st.button("Delete"):
                os.remove(DATA_DIR / selected_file)
                st.warning(f"Deleted {selected_file}")
                st.experimental_rerun()
    else:
        st.info("No files found in data/ folder.")


# =========================================
# 6. GitHub Auto Push Function (Fixed)
# =========================================
def attempt_git_push(file_path: Path, commit_message: str) -> Tuple[bool, str]:
    """Push file to GitHub repo using personal access token (HTTPS method)."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False, "Missing GitHub configuration in Streamlit Secrets."

    remote = f"https://{GITHUB_USER}:{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git"

    try:
        subprocess.run(["git", "config", "--global", "user.email", GITHUB_EMAIL], check=False)
        subprocess.run(["git", "config", "--global", "user.name", GITHUB_USER], check=False)
        subprocess.run(["git", "add", str(file_path)], check=True)

        commit = subprocess.run(
            ["git", "commit", "-m", commit_message],
            capture_output=True, text=True
        )
        if commit.returncode != 0 and "nothing to commit" not in commit.stderr.lower():
            return False, f"Commit failed: {commit.stderr}"

        subprocess.run(["git", "remote", "remove", "origin"], capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", remote], check=True)

        push = subprocess.run(["git", "push", "-u", "origin", "main"], capture_output=True, text=True)
        if push.returncode != 0:
            return False, f"Push failed: {push.stderr}"

        return True, "✅ Successfully pushed data to GitHub."
    except Exception as e:
        return False, str(e)
