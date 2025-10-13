# app.py - Enhanced Production Dashboard with AI Features
"""
Production Dashboard - Enhanced version with AI capabilities
Features:
- Upload daily Excel file (choose date)
- Confirmation before saving/uploading
- Save to data/YYYY-MM-DD.csv
- Attempt to push to GitHub using token from Streamlit Secrets
- Historical view (select any saved date)
- Rename/Delete saved date files (with confirmation)
- 4 chart themes
- Value labels on charts and top-producer highlight
- Ignores Fridays
- AI-Powered Anomaly Detection
- Predictive Analytics & Forecasting
- Real-time Performance Metrics
- Smart Recommendations Engine
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Tuple
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

# -------------------------------
# Configuration
# -------------------------------
st.set_page_config(page_title="Concrete Production Dashboard", layout="wide")

# Repo and data folder (adjust repo string if needed)
GITHUB_REPO = os.getenv("GITHUB_REPO", "Ashwin-KBRC/production_dashboard")
DATA_DIR = Path("data")
TOKEN = os.getenv("GITHUB_TOKEN")  # Set this in Streamlit Secrets as TOML: GITHUB_TOKEN="ghp_..."

# Required column names (exact)
REQUIRED_COLS = ["Plant", "Production for the Day", "Accumulative Production"]

# Color themes
COLOR_THEMES = {
    "Classic": px.colors.qualitative.Bold,
    "Ocean": px.colors.sequential.Plasma[::-1] if hasattr(px.colors, "sequential") else px.colors.qualitative.Plotly,
    "Sunset": ["#ff7c43", "#f95d6a", "#d45087", "#a05195", "#665191"],
    "Forest": ["#2e8b57", "#3cb371", "#66cdaa", "#20b2aa", "#2f4f4f"],
}

# Make sure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------------
# AI-Powered Helper Functions
# -------------------------------

def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """Detect anomalous production values using machine learning."""
    try:
        # Prepare features
        features = df[["Production for the Day", "Accumulative Production"]].copy()
        features = features.fillna(0)
        
        # Scale features
        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(features)
        
        # Train anomaly detection model
        iso_forest = IsolationForest(contamination=0.1, random_state=42)
        anomalies = iso_forest.fit_predict(scaled_features)
        
        # Add results to dataframe
        df_result = df.copy()
        df_result["Anomaly_Score"] = iso_forest.decision_function(scaled_features)
        df_result["Is_Anomaly"] = anomalies == -1
        df_result["Anomaly_Type"] = np.where(df_result["Is_Anomaly"], 
                                           "⚠️ Check Data", "✅ Normal")
        
        return df_result
    except Exception as e:
        st.warning(f"Anomaly detection skipped: {e}")
        df_result = df.copy()
        df_result["Anomaly_Type"] = "✅ Normal"
        return df_result

def forecast_next_day(df_historical: pd.DataFrame, plant: str) -> float:
    """Simple linear regression to forecast next day's production."""
    try:
        # Get historical data for specific plant
        plant_data = df_historical[df_historical["Plant"] == plant].copy()
        if len(plant_data) < 3:
            return None
            
        # Create sequential time feature
        plant_data = plant_data.sort_values("Date")
        plant_data["Day_Sequence"] = range(len(plant_data))
        
        # Train simple model
        X = plant_data[["Day_Sequence"]]
        y = plant_data["Production for the Day"]
        
        model = LinearRegression()
        model.fit(X, y)
        
        # Predict next day
        next_day_seq = len(plant_data)
        prediction = model.predict([[next_day_seq]])[0]
        
        return max(0, prediction)  # Ensure non-negative
    except:
        return None

def calculate_kpis(df: pd.DataFrame) -> dict:
    """Calculate Key Performance Indicators."""
    daily_prod = df["Production for the Day"].sum()
    accumulative = df["Accumulative Production"].sum()
    
    # Efficiency metrics
    avg_per_plant = daily_prod / len(df)
    max_production = df["Production for the Day"].max()
    min_production = df["Production for the Day"].min()
    variance = df["Production for the Day"].var()
    
    # Performance scores
    utilization = (daily_prod / (max_production * len(df))) * 100 if max_production > 0 else 0
    balance_score = (1 - (variance / (avg_per_plant + 0.001))) * 100
    
    return {
        "total_daily": daily_prod,
        "total_accumulative": accumulative,
        "avg_per_plant": avg_per_plant,
        "utilization_rate": utilization,
        "balance_score": balance_score,
        "max_producer": df.loc[df["Production for the Day"].idxmax(), "Plant"],
        "min_producer": df.loc[df["Production for the Day"].idxmin(), "Plant"]
    }

def generate_recommendations(df: pd.DataFrame, kpis: dict) -> list:
    """Generate AI-powered recommendations."""
    recommendations = []
    
    # Analyze data and generate suggestions
    if kpis["utilization_rate"] < 60:
        recommendations.append("🚀 **Opportunity**: Overall utilization is low. Consider optimizing resource allocation.")
    
    if kpis["balance_score"] < 70:
        recommendations.append("⚖️ **Balance Issue**: Production variance between plants is high. Review distribution.")
    
    # Check for underperforming plants
    avg_production = df["Production for the Day"].mean()
    underperformers = df[df["Production for the Day"] < avg_production * 0.7]
    if not underperformers.empty:
        plants_list = ", ".join(underperformers["Plant"].tolist())
        recommendations.append(f"🔧 **Training Needed**: Plants {plants_list} are performing below 70% of average.")
    
    # Check if any plant is over capacity
    if df["Production for the Day"].max() > avg_production * 2:
        top_plant = df.loc[df["Production for the Day"].idxmax(), "Plant"]
        recommendations.append(f"📈 **Best Practice**: {top_plant} is performing exceptionally well. Consider sharing their methods.")
    
    if not recommendations:
        recommendations.append("✅ **Excellent**: All plants are performing optimally. Maintain current operations.")
    
    return recommendations


# -------------------------------
# Original Helper functions
# -------------------------------
def read_excel_to_df(file) -> pd.DataFrame:
    """Read uploaded excel file into pandas DataFrame."""
    try:
        df = pd.read_excel(file)
        return df
    except Exception as e:
        st.error(f"Unable to read Excel file: {e}")
        raise

def validate_dataframe(df: pd.DataFrame) -> Tuple[bool, str]:
    """Check for required columns and return (valid, message)."""
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        return False, f"Missing required columns: {missing}. Expected exactly: {REQUIRED_COLS}"
    return True, "OK"

def ensure_date_column(df: pd.DataFrame, date_obj: datetime.date) -> pd.DataFrame:
    """Ensure the Date column exists and is standardized to YYYY-MM-DD strings."""
    df = df.copy()
    df["Date"] = pd.to_datetime(date_obj).strftime("%Y-%m-%d")
    return df

def save_csv_and_attempt_push(df: pd.DataFrame, date_obj: datetime.date) -> Tuple[bool, str]:
    """
    Save the df to data/YYYY-MM-DD.csv.
    Attempt to push to GitHub via git commands using TOKEN if present.
    Returns: (pushed_boolean, message)
    """
    date_str = date_obj.strftime("%Y-%m-%d")
    file_path = DATA_DIR / f"{date_str}.csv"
    df.to_csv(file_path, index=False)

    # Try to commit & push
    if not TOKEN:
        return False, "GITHUB_TOKEN not configured in environment (Streamlit Secrets). File saved locally."

    # Use the token in the remote URL for push
    remote_url = f"https://{TOKEN}@github.com/{GITHUB_REPO}.git"

    try:
        # Configure git user (local config in container)
        subprocess.run(["git", "config", "--global", "user.email", "streamlit@example.com"], check=False)
        subprocess.run(["git", "config", "--global", "user.name", "Streamlit App"], check=False)

        # Add file
        subprocess.run(["git", "add", str(file_path)], check=True)

        # Commit - may fail if no changes; capture output
        commit_proc = subprocess.run(["git", "commit", "-m", f"Add production data for {date_str}"], check=False, capture_output=True, text=True)
        if commit_proc.returncode != 0:
            stdout = commit_proc.stdout + commit_proc.stderr
            # If nothing to commit, treat as OK (not an error)
            if "nothing to commit" in stdout.lower() or "no changes added to commit" in stdout.lower():
                # No new changes - still treated as success but nothing pushed
                return True, "File saved; no new changes to commit (already present)."
            else:
                return False, f"Git commit failed: {stdout.strip()}"

        # Push
        push_proc = subprocess.run(["git", "push", remote_url, "main"], check=False, capture_output=True, text=True)
        if push_proc.returncode != 0:
            return False, f"Git push failed: {push_proc.stderr.strip() or push_proc.stdout.strip()}"
        return True, "File saved and pushed to GitHub successfully."

    except Exception as ex:
        return False, f"Exception while pushing: {ex}"

def list_saved_dates() -> list:
    """Return list of YYYY-MM-DD strings saved in data folder sorted descending."""
    files = sorted([p.name.replace(".csv", "") for p in DATA_DIR.glob("*.csv")], reverse=True)
    return files

def load_saved_csv(date_str: str) -> pd.DataFrame:
    """Load a saved CSV by date string."""
    path = DATA_DIR / f"{date_str}.csv"
    if not path.exists():
        raise FileNotFoundError(f"No saved file for {date_str}")
    return pd.read_csv(path)

def delete_saved_csv(date_str: str) -> bool:
    path = DATA_DIR / f"{date_str}.csv"
    if path.exists():
        path.unlink()
        return True
    return False

def rename_saved_csv(old_date: str, new_date: str) -> bool:
    old = DATA_DIR / f"{old_date}.csv"
    new = DATA_DIR / f"{new_date}.csv"
    if old.exists():
        old.rename(new)
        return True
    return False


# -------------------------------
# Plotting helpers (plotly)
# -------------------------------
def plot_production_pie(df: pd.DataFrame, theme_colors: list, title: str, value_col: str):
    """Return a plotly pie figure with labels and hover that includes value labels in the hover."""
    fig = px.pie(df, names="Plant", values=value_col, title=title, color_discrete_sequence=theme_colors)
    # show percentage + value in hover
    fig.update_traces(textinfo="percent+label", hovertemplate="%{label}: %{value} (%{percent})<extra></extra>")
    return fig

def plot_production_bar(df: pd.DataFrame, theme_colors: list, title: str, value_col: str):
    """Return a plotly bar figure with values displayed on top of bars."""
    fig = px.bar(df, x="Plant", y=value_col, title=title, color="Plant", color_discrete_sequence=theme_colors, text=value_col)
    fig.update_traces(textposition="outside")
    fig.update_layout(uniformtext_minsize=8, uniformtext_mode="hide", xaxis_title=None, yaxis_title="m³")
    return fig

def plot_production_line(df: pd.DataFrame, theme_colors: list, title: str, value_col: str):
    fig = px.line(df, x="Plant", y=value_col, title=title, markers=True, color_discrete_sequence=theme_colors)
    return fig

def plot_production_area(df: pd.DataFrame, theme_colors: list, title: str, value_col: str):
    fig = px.area(df, x="Plant", y=value_col, title=title, color="Plant", color_discrete_sequence=theme_colors)
    return fig


# -------------------------------
# UI - Sidebar controls
# -------------------------------
st.sidebar.title("Controls")
mode = st.sidebar.radio("Mode", ["Upload New Data", "View Historical Data", "Manage Data"])

st.sidebar.markdown("---")
theme_choice = st.sidebar.selectbox("Chart Theme", list(COLOR_THEMES.keys()), index=0)
theme_colors = COLOR_THEMES[theme_choice]

st.sidebar.markdown("---")
st.sidebar.write("Notes:")
st.sidebar.write("- Upload an Excel (.xlsx) with columns: Plant, Production for the Day, Accumulative Production")
st.sidebar.write("- Select the date for the upload (this tags every row with the chosen date).")
st.sidebar.write("- Fridays are non-production days and will be ignored.")


# -------------------------------
# Main app body
# -------------------------------
st.title("🧱 PRODUCTION FOR THE DAY — AI-Enhanced Dashboard")

if mode == "Upload New Data":
    st.header("Upload new daily production file")
    st.markdown("Upload an Excel (.xlsx) containing the columns: `Plant`, `Production for the Day`, `Accumulative Production`.")
    uploaded_file = st.file_uploader("Select Excel file to upload", type=["xlsx"])
    selected_date = st.date_input("📅 On which date is this file for?", value=datetime.today())

    if uploaded_file is not None:
        try:
            df_uploaded = read_excel_to_df(uploaded_file)
        except Exception:
            st.stop()

        valid, msg = validate_dataframe(df_uploaded)
        if not valid:
            st.error(msg)
            st.info("Make sure the Excel has exact headers and no merged cells. Example headers: Date, Plant, Production for the Day, Accumulative Production")
        else:
            # show preview
            st.subheader("Preview of uploaded data (first rows)")
            st.dataframe(df_uploaded.head(20))

            # Confirm checkbox & upload button
            st.write("Please confirm the data and then click upload.")
            confirm = st.checkbox("I confirm this data is correct and ready to upload")
            if confirm:
                if st.button("Upload and Save to History"):
                    # prepare df to save
                    df_save = ensure_date_column(df_uploaded, selected_date)
                    # skip if date is Friday
                    weekday_name = pd.to_datetime(df_save["Date"].iloc[0]).day_name()
                    if weekday_name == "Friday":
                        st.error("Selected date is a Friday — Fridays are non-production days and will be ignored. Change the date or cancel.")
                    else:
                        pushed, message = save_csv_and_attempt_push(df_save, selected_date)
                        # show clear messages
                        st.success(f"✅ Saved data to {DATA_DIR}/{selected_date.strftime('%Y-%m-%d')}.csv")
                        if pushed:
                            st.success(f"🚀 {message}")
                        else:
                            st.warning(f"⚠️ Could not push to GitHub automatically. {message}")
                            st.info("If you want automatic pushes, ensure your GITHUB_TOKEN and GITHUB_REPO are set in Streamlit Secrets (TOML). Otherwise you can manually upload the CSV file from the app container to your repo's data/ folder.")

                        # Show totals and charts immediately
                        df_display = df_save.copy()
                        # Remove any TOTAL row if exists
                        df_display = df_display[~df_display["Plant"].astype(str).str.upper().str.contains("TOTAL")]
                        # Convert numeric columns defensively
                        df_display["Production for the Day"] = pd.to_numeric(df_display["Production for the Day"], errors="coerce").fillna(0.0)
                        df_display["Accumulative Production"] = pd.to_numeric(df_display["Accumulative Production"], errors="coerce").fillna(0.0)

                        st.markdown("---")
                        st.subheader(f"🔹 Totals for {selected_date.strftime('%Y-%m-%d')}")
                        total_daily = df_display["Production for the Day"].sum()
                        total_acc = df_display["Accumulative Production"].sum()
                        st.write(f"**Total Production for the Day:** {total_daily:,.2f} m³")
                        st.write(f"**Total Accumulative Production:** {total_acc:,.2f} m³")

                        st.subheader("📋 Uploaded Production Table")
                        st.dataframe(df_display, use_container_width=True)

                        # Charts
                        st.subheader("🌈 Production Charts (Uploaded)")
                        col1, col2 = st.columns(2)
                        with col1:
                            try:
                                fig_pie = plot_production_pie(df_display, theme_colors, "Plant-wise Production (Pie)", "Production for the Day")
                                st.plotly_chart(fig_pie, use_container_width=True)
                            except Exception as e:
                                st.error(f"Could not create pie chart: {e}")
                        with col2:
                            try:
                                fig_bar = plot_production_bar(df_display, theme_colors, "Production per Plant (Bar)", "Production for the Day")
                                st.plotly_chart(fig_bar, use_container_width=True)
                            except Exception as e:
                                st.error(f"Could not create bar chart: {e}")

                        # Additional charts
                        try:
                            fig_line = plot_production_line(df_display, theme_colors, "Production Trend (Line)", "Production for the Day")
                            st.plotly_chart(fig_line, use_container_width=True)
                        except Exception as e:
                            st.error(f"Could not create line chart: {e}")

                        try:
                            fig_area = plot_production_area(df_display, theme_colors, "Production Flow (Area)", "Production for the Day")
                            st.plotly_chart(fig_area, use_container_width=True)
                        except Exception as e:
                            st.error(f"Could not create area chart: {e}")

                        # Accumulative chart
                        try:
                            fig_acc = plot_production_bar(df_display, theme_colors, "Accumulative Production per Plant", "Accumulative Production")
                            st.plotly_chart(fig_acc, use_container_width=True)
                        except Exception as e:
                            st.error(f"Could not create accumulative chart: {e}")

                        # Highest producer
                        try:
                            top = df_display.loc[df_display["Production for the Day"].astype(float).idxmax()]
                            st.success(f"🏆 Highest Producer: **{top['Plant']}** with {float(top['Production for the Day']):,.2f} m³")
                        except Exception:
                            pass

                        # -------------------------------
                        # AI-Powered Features Section
                        # -------------------------------
                        st.markdown("---")
                        st.header("🚀 AI-Powered Insights")

                        # Anomaly Detection
                        with st.expander("🔍 Smart Anomaly Detection", expanded=True):
                            df_with_anomalies = detect_anomalies(df_display)
                            st.dataframe(df_with_anomalies[["Plant", "Production for the Day", "Anomaly_Type"]])
                            
                            anomalies_found = df_with_anomalies["Is_Anomaly"].sum() if "Is_Anomaly" in df_with_anomalies else 0
                            if anomalies_found > 0:
                                st.warning(f"⚠️ {anomalies_found} potential anomaly(s) detected. Please review data quality.")
                            else:
                                st.success("✅ No anomalies detected in the data.")

                        # KPIs Dashboard
                        with st.expander("📊 Performance Dashboard", expanded=True):
                            kpis = calculate_kpis(df_display)
                            
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Total Daily Production", f"{kpis['total_daily']:,.1f} m³")
                            with col2:
                                st.metric("Avg per Plant", f"{kpis['avg_per_plant']:,.1f} m³")
                            with col3:
                                st.metric("Utilization Rate", f"{kpis['utilization_rate']:.1f}%")
                            with col4:
                                st.metric("Balance Score", f"{kpis['balance_score']:.1f}%")
                            
                            st.write(f"**Top Producer:** {kpis['max_producer']}")
                            st.write(f"**Needs Attention:** {kpis['min_producer']}")

                        # Recommendations
                        with st.expander("💡 Smart Recommendations", expanded=True):
                            recommendations = generate_recommendations(df_display, kpis)
                            for rec in recommendations:
                                st.write(rec)

                        # Forecasting
                        with st.expander("🔮 Production Forecast", expanded=True):
                            st.write("Next day production forecasts:")
                            forecast_data = []
                            for plant in df_display["Plant"].unique():
                                prediction = forecast_next_day(df_display, plant)
                                if prediction is not None:
                                    forecast_data.append({"Plant": plant, "Predicted Production": prediction})
                            
                            if forecast_data:
                                forecast_df = pd.DataFrame(forecast_data)
                                st.dataframe(forecast_df)
                                
                                # Visualize forecast
                                fig_forecast = px.bar(forecast_df, x="Plant", y="Predicted Production", 
                                                    title="Next Day Production Forecast", color="Plant")
                                st.plotly_chart(fig_forecast, use_container_width=True)
                            else:
                                st.info("Need more historical data for accurate forecasting.")


elif mode == "View Historical Data":
    st.header("Historical Data Viewer")
    saved = list_saved_dates()
    if not saved:
        st.info("No historical data found yet. Upload a file first.")
    else:
        chosen = st.selectbox("Select a date to view:", saved, index=0)
        try:
            df_hist = load_saved_csv(chosen)
        except Exception as e:
            st.error(f"Unable to load saved file: {e}")
            df_hist = None

        if df_hist is not None:
            # Defensive: ensure Date column is standardized
            if "Date" in df_hist.columns:
                try:
                    df_hist["Date"] = pd.to_datetime(df_hist["Date"]).dt.strftime("%Y-%m-%d")
                except Exception:
                    pass

            # Remove TOTAL row if present
            df_hist_display = df_hist[~df_hist["Plant"].astype(str).str.upper().str.contains("TOTAL")]

            # Convert numeric columns defensively
            df_hist_display["Production for the Day"] = pd.to_numeric(df_hist_display["Production for the Day"], errors="coerce").fillna(0.0)
            df_hist_display["Accumulative Production"] = pd.to_numeric(df_hist_display["Accumulative Production"], errors="coerce").fillna(0.0)

            st.subheader(f"Data for {chosen}")
            st.dataframe(df_hist_display, use_container_width=True)

            # Totals
            total_daily = df_hist_display["Production for the Day"].sum()
            total_acc = df_hist_display["Accumulative Production"].sum()
            st.markdown("#### 🔹 Totals")
            st.write(f"**Total Production for the Day:** {total_daily:,.2f} m³")
            st.write(f"**Total Accumulative Production:** {total_acc:,.2f} m³")

            # Charts
            st.subheader("🌈 Production Charts (Historical)")
            try:
                fig_pie = plot_production_pie(df_hist_display, theme_colors, f"Plant-wise Production — {chosen}", "Production for the Day")
                st.plotly_chart(fig_pie, use_container_width=True)
            except Exception as e:
                st.error(f"Error creating pie chart: {e}")

            try:
                fig_bar = plot_production_bar(df_hist_display, theme_colors, f"Production per Plant — {chosen}", "Production for the Day")
                st.plotly_chart(fig_bar, use_container_width=True)
            except Exception as e:
                st.error(f"Error creating bar chart: {e}")

            try:
                fig_line = plot_production_line(df_hist_display, theme_colors, f"Production Trend — {chosen}", "Production for the Day")
                st.plotly_chart(fig_line, use_container_width=True)
            except Exception as e:
                st.warning(f"Line chart error: {e}")

            try:
                fig_area = plot_production_area(df_hist_display, theme_colors, f"Production Flow — {chosen}", "Production for the Day")
                st.plotly_chart(fig_area, use_container_width=True)
            except Exception as e:
                st.warning(f"Area chart error: {e}")

            # Accumulative
            try:
                fig_acc = plot_production_bar(df_hist_display, theme_colors, f"Accumulative Production — {chosen}", "Accumulative Production")
                st.plotly_chart(fig_acc, use_container_width=True)
            except Exception as e:
                st.error(f"Accumulative chart error: {e}")

            # Top producer
            try:
                top = df_hist_display.loc[df_hist_display["Production for the Day"].astype(float).idxmax()]
                st.success(f"🏆 Highest Producer for {chosen}: **{top['Plant']}** ({float(top['Production for the Day']):,.2f} m³)")
            except Exception:
                pass

            # -------------------------------
            # AI-Powered Features for Historical Data
            # -------------------------------
            st.markdown("---")
            st.header("🚀 Historical Insights")
            
            # Anomaly Detection
            with st.expander("🔍 Historical Anomaly Detection", expanded=False):
                df_hist_anomalies = detect_anomalies(df_hist_display)
                st.dataframe(df_hist_anomalies[["Plant", "Production for the Day", "Anomaly_Type"]])
                
                anomalies_found = df_hist_anomalies["Is_Anomaly"].sum() if "Is_Anomaly" in df_hist_anomalies else 0
                if anomalies_found > 0:
                    st.warning(f"⚠️ {anomalies_found} historical anomaly(s) detected in this dataset.")
                else:
                    st.success("✅ No historical anomalies detected.")

            # KPIs for Historical Data
            with st.expander("📊 Historical Performance Dashboard", expanded=False):
                kpis_hist = calculate_kpis(df_hist_display)
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Daily Production", f"{kpis_hist['total_daily']:,.1f} m³")
                with col2:
                    st.metric("Avg per Plant", f"{kpis_hist['avg_per_plant']:,.1f} m³")
                with col3:
                    st.metric("Utilization Rate", f"{kpis_hist['utilization_rate']:.1f}%")
                with col4:
                    st.metric("Balance Score", f"{kpis_hist['balance_score']:.1f}%")

            # Historical Recommendations
            with st.expander("💡 Historical Recommendations", expanded=False):
                recommendations_hist = generate_recommendations(df_hist_display, kpis_hist)
                for rec in recommendations_hist:
                    st.write(rec)


elif mode == "Manage Data":
    st.header("Data Management (Rename / Delete)")
    saved = list_saved_dates()
    if not saved:
        st.info("No saved files found.")
    else:
        chosen = st.selectbox("Select a saved date", saved)
        st.write("⚠️ Please be careful. These actions are permanent.")
        action = st.radio("Action", ["Rename", "Delete"])
        if action == "Rename":
            new_date_obj = st.date_input("Choose new date for this file")
            new_date_str = new_date_obj.strftime("%Y-%m-%d")
            if st.button("Confirm Rename"):
                if rename_saved_csv(chosen, new_date_str):
                    st.success(f"Renamed {chosen} → {new_date_str}")
                else:
                    st.error("Rename failed (file may not exist).")
        elif action == "Delete":
            if st.button("Confirm Delete"):
                if delete_saved_csv(chosen):
                    st.success(f"Deleted {chosen}")
                else:
                    st.error("Delete failed (file may not exist).")

# Footer help
st.sidebar.markdown("---")
st.sidebar.write("If auto-push to GitHub fails, make sure:")
st.sidebar.write("1) You added the token to Streamlit Secrets as TOML: `GITHUB_TOKEN = \"ghp_xxx\"`")
st.sidebar.write(f"2) You set repo name as TOML: `GITHUB_REPO = \"{GITHUB_REPO}\"` (or set GITHUB_REPO env var).")
st.sidebar.write("3) The app must have network/git access to push changes. Manual upload to repo/data is always an option.")

# Add AI capabilities info to sidebar
st.sidebar.markdown("---")
st.sidebar.header("🤖 AI Features")
st.sidebar.write("- **Anomaly Detection**: Identifies unusual production patterns")
st.sidebar.write("- **Performance KPIs**: Real-time metrics and scoring")
st.sidebar.write("- **Smart Recommendations**: Actionable insights")
st.sidebar.write("- **Production Forecasting**: Predicts next day output")
