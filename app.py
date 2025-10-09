import streamlit as st
import pandas as pd
import os
from datetime import datetime
import matplotlib.pyplot as plt
import subprocess

# ------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------
st.set_page_config(page_title="Production Dashboard", layout="wide")

# GitHub Repo details
GITHUB_REPO = "Ashwin-KBRC/production_dashboard"   # <-- your repo path
DATA_FOLDER = "data"
TOKEN = os.getenv("GITHUB_TOKEN")  # loaded from Streamlit Secrets

# ------------------------------------------------------------
# THEMES
# ------------------------------------------------------------
THEMES = {
    "Classic": {"pie_colors": ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f"]},
    "Ocean": {"pie_colors": ["#003f5c", "#2f4b7c", "#665191", "#a05195", "#d45087"]},
    "Sunset": {"pie_colors": ["#ff7c43", "#f95d6a", "#d45087", "#a05195", "#665191"]},
    "Forest": {"pie_colors": ["#2e8b57", "#3cb371", "#66cdaa", "#20b2aa", "#2f4f4f"]},
}

# ------------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------------
def load_data(file):
    """Load Excel data into a pandas DataFrame."""
    return pd.read_excel(file)

def save_to_csv(df, date_str):
    """Save data to /data folder and push to GitHub."""
    os.makedirs(DATA_FOLDER, exist_ok=True)
    filename = f"{DATA_FOLDER}/{date_str}.csv"
    df.to_csv(filename, index=False)
    st.success(f"✅ Saved data to {filename}")

    if TOKEN:
        try:
            subprocess.run(["git", "config", "--global", "user.email", "you@example.com"])
            subprocess.run(["git", "config", "--global", "user.name", "Streamlit App"])
            subprocess.run(["git", "add", filename])
            subprocess.run(["git", "commit", "-m", f"Add data for {date_str}"], check=True)
            subprocess.run(
                [
                    "git",
                    "push",
                    f"https://{TOKEN}@github.com/{GITHUB_REPO}.git",
                    "main",
                ],
                check=True,
            )
            st.success("🚀 Pushed to GitHub successfully!")
        except Exception as e:
            st.warning(f"⚠️ Could not push to GitHub automatically.\n\nReason: {e}")
    else:
        st.info("ℹ️ GitHub token not found. File saved locally but not pushed.")

def list_available_dates():
    """List all available dates in /data folder."""
    if not os.path.exists(DATA_FOLDER):
        return []
    return sorted([f.replace(".csv", "") for f in os.listdir(DATA_FOLDER) if f.endswith(".csv")])

def plot_pie(df, theme):
    """Generate pie charts for ACCU and FOR THE DAY with value labels."""
    colors = THEMES[theme]["pie_colors"]
    cols = st.columns(2)
    try:
        # Accumulative chart
        with cols[0]:
            st.subheader("Accumulated Production")
            df_accu = df[["Machines", "ACCU"]]
            fig, ax = plt.subplots()
            wedges, texts, autotexts = ax.pie(
                df_accu["ACCU"],
                labels=df_accu["Machines"],
                autopct="%1.1f%%",
                colors=colors,
                startangle=90,
            )
            for i, w in enumerate(wedges):
                x, y = w.center
                ang = (w.theta2 - w.theta1) / 2.0 + w.theta1
                ax.text(
                    x + 0.5 * w.r,
                    y + 0.5 * w.r,
                    f"{df_accu['ACCU'][i]}",
                    ha="center",
                    va="center",
                    fontsize=9,
                    color="black",
                )
            st.pyplot(fig)

        # Daily production chart
        with cols[1]:
            st.subheader("Production for the Day")
            df_day = df[["Machines", "FOR THE DAY"]]
            fig, ax = plt.subplots()
            wedges, texts, autotexts = ax.pie(
                df_day["FOR THE DAY"],
                labels=df_day["Machines"],
                autopct="%1.1f%%",
                colors=colors,
                startangle=90,
            )
            for i, w in enumerate(wedges):
                x, y = w.center
                ang = (w.theta2 - w.theta1) / 2.0 + w.theta1
                ax.text(
                    x + 0.5 * w.r,
                    y + 0.5 * w.r,
                    f"{df_day['FOR THE DAY'][i]}",
                    ha="center",
                    va="center",
                    fontsize=9,
                    color="black",
                )
            st.pyplot(fig)
    except Exception as e:
        st.error(f"Error creating charts: {e}")

def delete_or_rename_option():
    """Allow renaming or deleting data files."""
    st.subheader("🧹 Manage Uploaded Data")
    available = list_available_dates()
    if not available:
        st.info("No files to manage yet.")
        return
    choice = st.selectbox("Select a file to manage:", available)
    action = st.radio("Choose an action:", ["Rename", "Delete"])
    if action == "Rename":
        new_date = st.date_input("Select new date for this file")
        if st.button("✅ Confirm Rename"):
            os.rename(f"{DATA_FOLDER}/{choice}.csv", f"{DATA_FOLDER}/{new_date}.csv")
            st.success(f"Renamed {choice} → {new_date}")
    elif action == "Delete":
        if st.button("🗑️ Confirm Delete"):
            os.remove(f"{DATA_FOLDER}/{choice}.csv")
            st.success(f"Deleted {choice}.csv")

# ------------------------------------------------------------
# MAIN APP
# ------------------------------------------------------------
st.title("🏭 Production Dashboard")

# 1️⃣ Date input before upload
selected_date = st.date_input("📅 On which date is this file for?")
date_str = selected_date.strftime("%Y-%m-%d")

uploaded_file = st.file_uploader("📤 Upload Excel File", type=["xlsx"])

# Theme selector
selected_theme = st.selectbox("🎨 Choose Chart Theme", list(THEMES.keys()))

# Confirmation dialog before saving
if uploaded_file:
    st.subheader("Preview of Uploaded Data:")
    df = load_data(uploaded_file)
    st.dataframe(df)

    if st.checkbox("✅ Confirm this data is correct and ready to upload"):
        if st.button("🚀 Upload to Dashboard"):
            save_to_csv(df, date_str)

# 3️⃣ Historical data viewer
st.divider()
st.header("📆 Historical Data Viewer")

available_dates = list_available_dates()
if available_dates:
    view_date = st.selectbox("Select a date to view data:", available_dates)
    if view_date:
        df_old = pd.read_csv(f"{DATA_FOLDER}/{view_date}.csv")
        st.write(f"### Data for {view_date}")
        st.dataframe(df_old)
        plot_pie(df_old, selected_theme)
else:
    st.info("No historical data found yet.")

# 4️⃣ File management section
st.divider()
delete_or_rename_option()
