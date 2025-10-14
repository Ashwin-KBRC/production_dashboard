# app.py
"""
Production Dashboard — Full Version
Features:
✅ Secure login (password)
✅ Upload Excel file & select date manually
✅ Save to data/YYYY-MM-DD.csv
✅ GitHub push using token from Streamlit secrets
✅ Historical data view, rename & delete
✅ Chart themes with value labels
✅ Clean modern UI
"""

import os
import io
import pandas as pd
import streamlit as st
import plotly.express as px
import datetime
import subprocess

# -------------------------------------------------
# 1️⃣ Page Config
# -------------------------------------------------
st.set_page_config(page_title="Production Dashboard", layout="wide")

# -------------------------------------------------
# 2️⃣ Login System
# -------------------------------------------------
PASSWORD = st.secrets.get("APP_PASSWORD", "kbrc123")  # default password
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.markdown("### 🔐 Login Required")
    password = st.text_input("Enter Password", type="password")
    if st.button("Login"):
        if password == PASSWORD:
            st.session_state["authenticated"] = True
            st.success("Login successful ✅")
            st.experimental_rerun()
        else:
            st.error("Incorrect password ❌")
    st.stop()

# -------------------------------------------------
# 3️⃣ GitHub Setup
# -------------------------------------------------
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN")
GITHUB_REPO = st.secrets.get("GITHUB_REPO")
GITHUB_USER = st.secrets.get("GITHUB_USER")
GITHUB_EMAIL = st.secrets.get("GITHUB_EMAIL")

data_dir = "data"
os.makedirs(data_dir, exist_ok=True)

# -------------------------------------------------
# 4️⃣ Helper Functions
# -------------------------------------------------
def push_to_github(csv_path, file_name, selected_date):
    """Push file to GitHub repo using HTTPS authentication."""
    try:
        subprocess.run(["git", "config", "user.name", GITHUB_USER], check=True)
        subprocess.run(["git", "config", "user.email", GITHUB_EMAIL], check=True)

        remote_url = f"https://{GITHUB_USER}:{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git"
        subprocess.run(["git", "remote", "set-url", "origin", remote_url], check=True)

        subprocess.run(["git", "add", csv_path], check=True)
        subprocess.run(["git", "commit", "-m", f"Add data for {selected_date}"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)

        st.success(f"✅ Successfully pushed `{file_name}` to GitHub!")
    except subprocess.CalledProcessError as e:
        st.error(f"❌ GitHub push failed: {e}")

def plot_chart(df, title, color_theme, y_col="Production for the Day", highlight=None):
    fig = px.bar(df, x="Product", y=y_col, title=title, color="Product", color_discrete_sequence=color_theme)
    fig.update_traces(texttemplate="%{y}", textposition="outside")
    fig.update_layout(showlegend=False, height=500)
    return fig

def plot_line(df, title, color_theme):
    fig = px.line(df, x="Product", y=["Production for the Day", "Accumulative"], title=title, markers=True,
                  color_discrete_sequence=color_theme)
    fig.update_traces(texttemplate="%{y}", textposition="top center")
    fig.update_layout(height=500)
    return fig

def plot_pie(df, title, color_theme):
    fig = px.pie(df, names="Product", values="Production for the Day", title=title,
                 color_discrete_sequence=color_theme)
    return fig

# -------------------------------------------------
# 5️⃣ Theme Selection
# -------------------------------------------------
themes = {
    "Default": px.colors.qualitative.Safe,
    "Vibrant": px.colors.qualitative.Bold,
    "Pastel": px.colors.qualitative.Pastel,
    "Dark": px.colors.qualitative.Dark2
}
theme_choice = st.sidebar.selectbox("🎨 Choose Chart Theme", list(themes.keys()))
theme_colors = themes[theme_choice]

# -------------------------------------------------
# 6️⃣ File Upload Section
# -------------------------------------------------
st.markdown("## 📤 Upload Daily Production File")
selected_date = st.date_input("📅 Select the date for this file", datetime.date.today())

uploaded_file = st.file_uploader("Upload Excel file (.xlsx)", type=["xlsx"])
if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        df.columns = [c.strip() for c in df.columns]
        st.write("✅ File loaded successfully!")

        if st.checkbox("Preview data"):
            st.dataframe(df)

        if st.button("💾 Save and Push to GitHub"):
            with st.spinner("Saving data..."):
                file_name = f"{selected_date}.csv"
                csv_path = os.path.join(data_dir, file_name)
                df.to_csv(csv_path, index=False)
                st.success(f"Data saved as `{file_name}` locally.")

                if all([GITHUB_TOKEN, GITHUB_REPO, GITHUB_USER, GITHUB_EMAIL]):
                    push_to_github(csv_path, file_name, selected_date)
                else:
                    st.warning("⚠️ GitHub credentials missing — file saved locally only.")
    except Exception as e:
        st.error(f"Error reading Excel file: {e}")

# -------------------------------------------------
# 7️⃣ Historical Data Viewer
# -------------------------------------------------
st.markdown("---")
st.markdown("## 📊 Historical Data")

files = sorted([f for f in os.listdir(data_dir) if f.endswith(".csv")])
if not files:
    st.info("No saved data yet.")
else:
    sel_file = st.selectbox("Select a saved date", files)
    df_hist = pd.read_csv(os.path.join(data_dir, sel_file))
    st.dataframe(df_hist)

    # Charts
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(plot_chart(df_hist, "Production for the Day", theme_colors), use_container_width=True)
    with col2:
        st.plotly_chart(plot_line(df_hist, "Accumulative vs Production", theme_colors), use_container_width=True)

    st.plotly_chart(plot_pie(df_hist, "Production Share", theme_colors), use_container_width=True)

    # Rename / Delete options
    st.markdown("### ⚙️ Manage Data File")
    new_name = st.text_input("Rename file (optional)", value=sel_file)
    colr1, colr2 = st.columns(2)

    with colr1:
        if st.button("✏️ Rename File"):
            os.rename(os.path.join(data_dir, sel_file), os.path.join(data_dir, new_name))
            st.success("Renamed successfully!")
            st.experimental_rerun()

    with colr2:
        if st.button("🗑️ Delete File"):
            os.remove(os.path.join(data_dir, sel_file))
            st.warning("File deleted!")
            st.experimental_rerun()

# -------------------------------------------------
# 8️⃣ Manual Push Test
# -------------------------------------------------
st.markdown("---")
if st.button("🚀 Test GitHub Push"):
    try:
        test_file = os.path.join(data_dir, "test_push.csv")
        pd.DataFrame({"Test": ["OK"], "Time": [str(datetime.datetime.now())]}).to_csv(test_file, index=False)
        push_to_github(test_file, "test_push.csv", "Manual test")
    except Exception as e:
        st.error(f"Test push failed: {e}")
