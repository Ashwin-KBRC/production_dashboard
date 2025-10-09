# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime
import traceback

# Optional Git push support (GitPython)
try:
    from git import Repo
    GITPYTHON_AVAILABLE = True
except Exception:
    GITPYTHON_AVAILABLE = False

# -----------------------
# Config
# -----------------------
st.set_page_config(page_title="Concrete Production Dashboard", layout="wide")
DATA_DIR = "data"  # folder in repo where historical CSVs are stored
os.makedirs(DATA_DIR, exist_ok=True)

REQUIRED_COLS = ["Plant", "Production for the Day", "Accumulative Production"]

# -----------------------
# Helper functions
# -----------------------
def read_saved_dates():
    files = [f for f in os.listdir(DATA_DIR) if f.endswith(".csv")]
    # filenames assumed like YYYY-MM-DD.csv or YYYY-MM-DD_production.csv
    dates = []
    for f in files:
        name = f.replace(".csv", "")
        # if name includes extra suffix, take the leading date part
        parts = name.split("_")
        dates.append(parts[0])
    # sort descending
    dates = sorted(list(set(dates)), reverse=True)
    return dates

def load_data_for_date(date_str):
    # look for file matching date_str (either exact or starting with date_str_)
    candidates = [f for f in os.listdir(DATA_DIR) if f.endswith(".csv") and f.startswith(date_str)]
    if not candidates:
        return None, None
    path = os.path.join(DATA_DIR, candidates[0])
    df = pd.read_csv(path)
    # convert Date column to datetime if exists
    if "Date" in df.columns:
        try:
            df["Date"] = pd.to_datetime(df["Date"]).dt.date
        except Exception:
            pass
    return df, path

def save_upload_df(df, date_obj):
    date_str = date_obj.strftime("%Y-%m-%d")
    filename = f"{date_str}.csv"
    save_path = os.path.join(DATA_DIR, filename)
    # ensure date column stored as ISO string
    df_to_save = df.copy()
    df_to_save["Date"] = date_obj.strftime("%Y-%m-%d")
    df_to_save.to_csv(save_path, index=False)
    return save_path

def attempt_push_to_github(file_path, commit_message="Add production data"):
    """
    Attempts to commit & push the file to the repo using GitPython.
    This will only succeed if the deployed environment has git credentials configured.
    If GitPython is not available or push fails, we return False and the error.
    """
    if not GITPYTHON_AVAILABLE:
        return False, "GitPython not installed in environment."
    try:
        repo = Repo(".")
        repo.git.add(file_path)
        repo.index.commit(commit_message)
        origin = repo.remote(name="origin")
        origin.push()
        return True, "Pushed to GitHub."
    except Exception as e:
        return False, str(e)

# -----------------------
# Theme presets (color palettes)
# -----------------------
COLOR_THEMES = {
    "Default": px.colors.qualitative.Bold,
    "Blue": px.colors.sequential.Blues[3:] if hasattr(px.colors, "sequential") else px.colors.qualitative.Plotly,
    "Dark": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"],
    "Vibrant": ["#EF476F","#FFD166","#06D6A0","#118AB2","#073B4C","#9B5DE5"]
}

# -----------------------
# UI - Sidebar
# -----------------------
st.sidebar.title("Controls")
mode = st.sidebar.radio("Mode", ["View Historical Data", "Upload New Data"])

st.sidebar.markdown("---")
st.sidebar.subheader("Chart Theme")
theme_choice = st.sidebar.selectbox("Choose a color theme", list(COLOR_THEMES.keys()))
color_sequence = COLOR_THEMES.get(theme_choice, COLOR_THEMES["Default"])

st.sidebar.markdown("---")
st.sidebar.info("Fridays are non-production days and will be ignored automatically.")

# -----------------------
# Historical dates available
# -----------------------
available_dates = read_saved_dates()

# -----------------------
# Mode: View Historical Data
# -----------------------
if mode == "View Historical Data":
    st.sidebar.markdown("### Historical Data")
    if not available_dates:
        st.sidebar.warning("No historical files found. Switch to 'Upload New Data' to add the first file.")
    else:
        selected_date = st.sidebar.selectbox("Select date to view", available_dates, index=0)
        df, path = load_data_for_date(selected_date)
        if df is None:
            st.error("Failed to load data for selected date.")
        else:
            st.success(f"Loaded historical data for {selected_date}")
            # The app expects the three columns present; if a Date column exists, ensure it's date type
            if "Date" in df.columns:
                try:
                    df["Date"] = pd.to_datetime(df["Date"]).dt.date
                except:
                    pass

            # Filter out Friday rows (defensive)
            try:
                if "Date" in df.columns:
                    df = df[df["Date"].apply(lambda d: pd.to_datetime(d).day_name() != "Friday")]
            except Exception:
                pass

            # Drop any TOTAL row if present
            df_display = df[~df["Plant"].astype(str).str.upper().str.contains("TOTAL")]

            # Validate columns
            if not all(col in df_display.columns for col in REQUIRED_COLS):
                st.error(f"Historical file for {selected_date} is missing required columns: {REQUIRED_COLS}")
            else:
                # Show totals
                total_daily = df_display["Production for the Day"].astype(float).sum()
                total_acc = df_display["Accumulative Production"].astype(float).sum()

                st.markdown(f"## 🔹 Totals for {selected_date}")
                st.markdown(f"**Total Production for the Day:** {total_daily:,.2f} m³")
                st.markdown(f"**Total Accumulative Production:** {total_acc:,.2f} m³")

                # Show table
                st.subheader("📋 Production Data Table")
                st.dataframe(df_display.reset_index(drop=True), use_container_width=True)

                # Charts
                st.subheader("🌈 Production Charts")
                try:
                    pie = px.pie(df_display, names="Plant", values="Production for the Day",
                                 title=f"Production Share — {selected_date}",
                                 color_discrete_sequence=color_sequence)
                    st.plotly_chart(pie, use_container_width=True)
                except Exception as e:
                    st.warning("Could not create pie chart: " + str(e))

                try:
                    bar = px.bar(df_display, x="Plant", y="Production for the Day", color="Plant",
                                 title=f"Production per Plant — {selected_date}",
                                 color_discrete_sequence=color_sequence, text_auto=True)
                    st.plotly_chart(bar, use_container_width=True)
                except Exception as e:
                    st.warning("Could not create bar chart: " + str(e))

                try:
                    line = px.line(df_display, x="Plant", y="Production for the Day", markers=True,
                                   title=f"Production Trend — {selected_date}", color_discrete_sequence=color_sequence)
                    st.plotly_chart(line, use_container_width=True)
                except Exception as e:
                    st.warning("Could not create line chart: " + str(e))

                try:
                    area = px.area(df_display, x="Plant", y="Production for the Day", color="Plant",
                                   title=f"Production Flow — {selected_date}", color_discrete_sequence=color_sequence)
                    st.plotly_chart(area, use_container_width=True)
                except Exception as e:
                    st.warning("Could not create area chart: " + str(e))

                # Accumulative chart
                try:
                    acc = px.bar(df_display, x="Plant", y="Accumulative Production", color="Plant",
                                 title=f"Accumulative Production — {selected_date}", color_discrete_sequence=color_sequence)
                    st.plotly_chart(acc, use_container_width=True)
                except Exception as e:
                    st.warning("Could not create accumulative chart: " + str(e))

                # Top producer
                try:
                    top = df_display.loc[df_display["Production for the Day"].astype(float).idxmax()]
                    st.success(f"🏆 Highest Producer for {selected_date}: **{top['Plant']}** ({float(top['Production for the Day']):,.2f} m³)")
                except Exception:
                    pass

# -----------------------
# Mode: Upload New Data
# -----------------------
elif mode == "Upload New Data":
    st.header("Upload new daily production file")
    st.markdown("Upload an Excel (.xlsx) containing the columns: `Plant`, `Production for the Day`, `Accumulative Production`.")
    uploaded_file = st.file_uploader("Select Excel file to upload", type=["xlsx"], key="uploader")

    selected_date = st.date_input("📅 On which date is this file for?", value=datetime.today())

    if uploaded_file is not None:
        try:
            # Read excel
            df = pd.read_excel(uploaded_file)
        except Exception as e:
            st.error("Unable to read the Excel file. Make sure it is a valid .xlsx. Error: " + str(e))
            st.stop()

        # Validate columns
        if not all(col in df.columns for col in REQUIRED_COLS):
            st.error(f"File must contain columns exactly: {REQUIRED_COLS}")
            st.info("If your file is exported from another report, you can paste the data into this exact format in Excel and re-upload.")
        else:
            # Add/overwrite Date column with selected date (so user controls the date)
            df["Date"] = pd.to_datetime(selected_date).strftime("%Y-%m-%d")

            # Exclude Fridays (if date is Friday, we treat as non-production day)
            try:
                if pd.to_datetime(df["Date"].iloc[0]).day_name() == "Friday":
                    st.warning("Selected date is a Friday — Fridays are non-production days and will be ignored.")
                    st.stop()
            except Exception:
                pass

            # Remove TOTAL row if present
            df = df[~df["Plant"].astype(str).str.upper().str.contains("TOTAL")]

            # Convert numeric columns to float (defensive)
            df["Production for the Day"] = pd.to_numeric(df["Production for the Day"], errors="coerce").fillna(0.0)
            df["Accumulative Production"] = pd.to_numeric(df["Accumulative Production"], errors="coerce").fillna(0.0)

            # Save CSV for history
            save_path = save_upload_df(df, selected_date)
            st.success(f"Saved data to {save_path}")

            # Attempt to push to GitHub
            push_ok, push_msg = attempt_push_to_github(save_path, commit_message=f"Add production data for {selected_date.strftime('%Y-%m-%d')}")
            if push_ok:
                st.success("✅ Successfully pushed saved file to GitHub.")
            else:
                st.warning("Could not push to GitHub automatically.")
                st.info("Reason / hint: " + str(push_msg))
                st.write("If you want automatic Git pushes from Streamlit Cloud, the environment must be configured with git credentials or a token. Otherwise you can manually upload the CSV into the `data/` folder in your repository (instructions below).")

            # Display uploaded day immediately
            df_display = df.copy()
            # Display totals and charts below (same as historical view)
            total_daily = df_display["Production for the Day"].sum()
            total_acc = df_display["Accumulative Production"].sum()

            st.markdown(f"## 🔹 Totals for {selected_date.strftime('%Y-%m-%d')}")
            st.markdown(f"**Total Production for the Day:** {total_daily:,.2f} m³")
            st.markdown(f"**Total Accumulative Production:** {total_acc:,.2f} m³")

            st.subheader("📋 Production Data Table (Uploaded)")
            st.dataframe(df_display, use_container_width=True)

            st.subheader("🌈 Production Charts (Uploaded)")
            try:
                pie = px.pie(df_display, names="Plant", values="Production for the Day",
                             title=f"Production Share — {selected_date.strftime('%Y-%m-%d')}",
                             color_discrete_sequence=color_sequence)
                st.plotly_chart(pie, use_container_width=True)
            except Exception as e:
                st.warning("Could not create pie chart: " + str(e))

            try:
                bar = px.bar(df_display, x="Plant", y="Production for the Day", color="Plant",
                             title=f"Production per Plant — {selected_date.strftime('%Y-%m-%d')}",
                             color_discrete_sequence=color_sequence, text_auto=True)
                st.plotly_chart(bar, use_container_width=True)
            except Exception as e:
                st.warning("Could not create bar chart: " + str(e))

            try:
                line = px.line(df_display, x="Plant", y="Production for the Day", markers=True,
                               title=f"Production Trend — {selected_date.strftime('%Y-%m-%d')}", color_discrete_sequence=color_sequence)
                st.plotly_chart(line, use_container_width=True)
            except Exception as e:
                st.warning("Could not create line chart: " + str(e))

            try:
                area = px.area(df_display, x="Plant", y="Production for the Day", color="Plant",
                               title=f"Production Flow — {selected_date.strftime('%Y-%m-%d')}", color_discrete_sequence=color_sequence)
                st.plotly_chart(area, use_container_width=True)
            except Exception as e:
                st.warning("Could not create area chart: " + str(e))

            # Accumulative chart
            try:
                acc = px.bar(df_display, x="Plant", y="Accumulative Production", color="Plant",
                             title=f"Accumulative Production — {selected_date.strftime('%Y-%m-%d')}", color_discrete_sequence=color_sequence)
                st.plotly_chart(acc, use_container_width=True)
            except Exception as e:
                st.warning("Could not create accumulative chart: " + str(e))

            # Top producer
            try:
                top = df_display.loc[df_display["Production for the Day"].astype(float).idxmax()]
                st.success(f"🏆 Highest Producer: **{top['Plant']}** ({float(top['Production for the Day']):,.2f} m³)")
            except Exception:
                pass

            # Helpful manual instructions if auto-push failed
            if not push_ok:
                st.markdown("---")
                st.info("Manual backup step (if auto-push failed):")
                st.write("1. Download the saved CSV file from the app container (or copy it locally).")
                st.write("2. In GitHub, open your repository and upload the CSV to the `data/` folder.")
                st.write("3. Commit changes — the file will then be available in the historical dropdown.")

# -----------------------
# Footer / Help
# -----------------------
st.sidebar.markdown("---")
st.sidebar.markdown("**Help / Notes**")
st.sidebar.write("- Upload Excel files containing columns: Plant, Production for the Day, Accumulative Production.")
st.sidebar.write("- Use the date picker so the app tags the upload to the correct day.")
st.sidebar.write("- Friday is an off day and such uploads will be ignored.")
st.sidebar.write("- The app will save files to the `data/` folder. If automatic Git push is not available, upload CSVs manually to the repo.")
