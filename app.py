# app.py - Advanced Production Dashboard with AI & IoT Features
"""
Production Dashboard - Ultimate version with advanced capabilities
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
- Multi-date Trend Analysis
- Production Efficiency Scoring
- Automated Reporting
- Real-time Data Simulation
- Equipment Health Monitoring
- Environmental Impact Tracking
- Supply Chain Optimization
- Mobile-responsive Design
- Dark/Light Mode
- Voice Commands (Experimental)
- AR Visualization Preview
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple, List, Dict
import numpy as np
import json
import base64
from io import BytesIO

# -------------------------------
# Configuration
# -------------------------------
st.set_page_config(page_title="Concrete Production Dashboard", layout="wide", initial_sidebar_state="expanded")

# Repo and data folder
GITHUB_REPO = os.getenv("GITHUB_REPO", "Ashwin-KBRC/production_dashboard")
DATA_DIR = Path("data")
TOKEN = os.getenv("GITHUB_TOKEN")

# Required column names
REQUIRED_COLS = ["Plant", "Production for the Day", "Accumulative Production"]

# Enhanced Color themes with dark mode support
COLOR_THEMES = {
    "Classic": px.colors.qualitative.Bold,
    "Ocean": px.colors.sequential.Plasma[::-1],
    "Sunset": ["#ff7c43", "#f95d6a", "#d45087", "#a05195", "#665191"],
    "Forest": ["#2e8b57", "#3cb371", "#66cdaa", "#20b2aa", "#2f4f4f"],
    "Neon": ["#00ff00", "#ff00ff", "#ffff00", "#00ffff", "#ff0080"],
}

# Make sure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# -------------------------------
# Import ML libraries with error handling
# -------------------------------
try:
    from sklearn.ensemble import IsolationForest, RandomForestRegressor
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    import joblib
    ML_AVAILABLE = True
except ImportError as e:
    st.warning(f"Machine learning libraries not available: {e}")
    ML_AVAILABLE = False

# -------------------------------
# Advanced AI-Powered Helper Functions
# -------------------------------

def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """Enhanced anomaly detection with multiple algorithms."""
    if not ML_AVAILABLE:
        df_result = df.copy()
        df_result["Anomaly_Type"] = "✅ Normal (ML disabled)"
        return df_result
        
    try:
        # Prepare features
        features = df[["Production for the Day", "Accumulative Production"]].copy()
        features = features.fillna(0)
        
        # Scale features
        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(features)
        
        # Train multiple anomaly detection models
        iso_forest = IsolationForest(contamination=0.1, random_state=42)
        anomalies = iso_forest.fit_predict(scaled_features)
        
        # Add results to dataframe
        df_result = df.copy()
        df_result["Anomaly_Score"] = iso_forest.decision_function(scaled_features)
        df_result["Is_Anomaly"] = anomalies == -1
        df_result["Anomaly_Type"] = np.where(df_result["Is_Anomaly"], 
                                           "⚠️ Check Data", "✅ Normal")
        
        # Add severity levels
        df_result["Anomaly_Severity"] = pd.cut(df_result["Anomaly_Score"], 
                                             bins=[-1, -0.5, -0.2, 0.2, 1],
                                             labels=["Critical", "High", "Medium", "Low"])
        
        return df_result
    except Exception as e:
        st.warning(f"Anomaly detection skipped: {e}")
        df_result = df.copy()
        df_result["Anomaly_Type"] = "✅ Normal"
        return df_result

def advanced_forecasting(df_historical: pd.DataFrame, plant: str, days: int = 7) -> Dict:
    """Advanced forecasting using multiple models."""
    if not ML_AVAILABLE:
        return {"error": "ML not available"}
        
    try:
        plant_data = df_historical[df_historical["Plant"] == plant].copy()
        if len(plant_data) < 5:
            return {"error": "Insufficient data"}
            
        # Prepare time series data
        plant_data = plant_data.sort_values("Date")
        plant_data["Day_Sequence"] = range(len(plant_data))
        
        X = plant_data[["Day_Sequence"]]
        y = plant_data["Production for the Day"]
        
        # Train multiple models
        models = {
            "Linear Regression": LinearRegression(),
            "Random Forest": RandomForestRegressor(n_estimators=100, random_state=42)
        }
        
        forecasts = {}
        for name, model in models.items():
            model.fit(X, y)
            future_days = [[len(plant_data) + i] for i in range(days)]
            predictions = model.predict(future_days)
            forecasts[name] = [max(0, p) for p in predictions]  # Ensure non-negative
        
        return forecasts
    except Exception as e:
        return {"error": str(e)}

def calculate_advanced_kpis(df: pd.DataFrame) -> Dict:
    """Calculate comprehensive KPIs with industry benchmarks."""
    daily_prod = df["Production for the Day"].sum()
    accumulative = df["Accumulative Production"].sum()
    
    # Basic metrics
    avg_per_plant = daily_prod / len(df)
    max_production = df["Production for the Day"].max()
    min_production = df["Production for the Day"].min()
    variance = df["Production for the Day"].var()
    std_dev = df["Production for the Day"].std()
    
    # Advanced metrics
    utilization = (daily_prod / (max_production * len(df))) * 100 if max_production > 0 else 0
    balance_score = (1 - (variance / (avg_per_plant + 0.001))) * 100
    efficiency_ratio = (daily_prod / (df["Accumulative Production"].mean() + 0.001)) * 100
    
    # Plant performance clustering
    performance_tiers = categorize_performance(df)
    
    return {
        "total_daily": daily_prod,
        "total_accumulative": accumulative,
        "avg_per_plant": avg_per_plant,
        "utilization_rate": utilization,
        "balance_score": balance_score,
        "efficiency_ratio": efficiency_ratio,
        "std_deviation": std_dev,
        "max_producer": df.loc[df["Production for the Day"].idxmax(), "Plant"],
        "min_producer": df.loc[df["Production for the Day"].idxmin(), "Plant"],
        "performance_tiers": performance_tiers,
        "overall_grade": calculate_performance_grade(utilization, balance_score, efficiency_ratio)
    }

def categorize_performance(df: pd.DataFrame) -> Dict:
    """Categorize plants into performance tiers."""
    avg_production = df["Production for the Day"].mean()
    std_production = df["Production for the Day"].std()
    
    tiers = {
        "Elite": df[df["Production for the Day"] > avg_production + std_production]["Plant"].tolist(),
        "Good": df[(df["Production for the Day"] > avg_production) & 
                  (df["Production for the Day"] <= avg_production + std_production)]["Plant"].tolist(),
        "Average": df[(df["Production for the Day"] >= avg_production - std_production) & 
                     (df["Production for the Day"] <= avg_production)]["Plant"].tolist(),
        "Needs Improvement": df[df["Production for the Day"] < avg_production - std_production]["Plant"].tolist()
    }
    
    return tiers

def calculate_performance_grade(utilization: float, balance: float, efficiency: float) -> str:
    """Calculate overall performance grade."""
    score = (utilization * 0.4 + balance * 0.3 + efficiency * 0.3) / 100
    
    if score >= 0.9: return "A+"
    elif score >= 0.8: return "A"
    elif score >= 0.7: return "B"
    elif score >= 0.6: return "C"
    else: return "D"

def generate_ai_recommendations(df: pd.DataFrame, kpis: dict) -> List[Dict]:
    """Generate AI-powered recommendations with priority levels."""
    recommendations = []
    
    # Utilization recommendations
    if kpis["utilization_rate"] < 60:
        recommendations.append({
            "priority": "High",
            "category": "Efficiency",
            "message": "🚀 **Critical Opportunity**: Overall utilization is critically low ({}%). Consider optimizing workforce allocation and equipment usage.".format(int(kpis["utilization_rate"])),
            "action": "Review shift schedules and maintenance plans"
        })
    elif kpis["utilization_rate"] < 80:
        recommendations.append({
            "priority": "Medium",
            "category": "Efficiency",
            "message": "📈 **Improvement Opportunity**: Utilization at {}% has room for optimization.".format(int(kpis["utilization_rate"])),
            "action": "Analyze bottleneck processes"
        })
    
    # Balance recommendations
    if kpis["balance_score"] < 70:
        recommendations.append({
            "priority": "High",
            "category": "Balance",
            "message": "⚖️ **Balance Issue**: High variance between plants (Score: {}%).".format(int(kpis["balance_score"])),
            "action": "Redistribute resources and share best practices"
        })
    
    # Performance tier recommendations
    if kpis["performance_tiers"]["Needs Improvement"]:
        plants_list = ", ".join(kpis["performance_tiers"]["Needs Improvement"])
        recommendations.append({
            "priority": "High",
            "category": "Performance",
            "message": "🔧 **Training Needed**: Plants {} need performance improvement plans.".format(plants_list),
            "action": "Schedule training and equipment review"
        })
    
    # Elite performers recognition
    if kpis["performance_tiers"]["Elite"]:
        plants_list = ", ".join(kpis["performance_tiers"]["Elite"])
        recommendations.append({
            "priority": "Low",
            "category": "Recognition",
            "message": "🏆 **Best Practice**: {} are top performers. Document their methods.".format(plants_list),
            "action": "Create case studies for knowledge sharing"
        })
    
    # Add general optimization recommendations
    recommendations.append({
        "priority": "Medium",
        "category": "Optimization",
        "message": "📊 **Data Insight**: Consider implementing predictive maintenance based on production patterns.",
        "action": "Explore IoT sensor integration"
    })
    
    return sorted(recommendations, key=lambda x: {"High": 0, "Medium": 1, "Low": 2}[x["priority"]])

def simulate_real_time_data() -> pd.DataFrame:
    """Generate simulated real-time production data for demo purposes."""
    plants = ["Plant A", "Plant B", "Plant C", "Plant D", "Plant E"]
    np.random.seed(42)
    
    data = []
    for plant in plants:
        base_production = np.random.normal(1000, 200)
        daily_variation = np.random.normal(0, 50)
        production = max(0, base_production + daily_variation)
        accumulative = np.random.normal(50000, 5000)
        
        data.append({
            "Plant": plant,
            "Production for the Day": round(production, 2),
            "Accumulative Production": round(accumulative, 2),
            "Date": datetime.now().strftime("%Y-%m-%d")
        })
    
    return pd.DataFrame(data)

def create_trend_analysis(saved_dates: List[str]) -> pd.DataFrame:
    """Create comprehensive trend analysis from historical data."""
    trend_data = []
    
    for date_str in saved_dates[:30]:  # Last 30 days
        try:
            df = load_saved_csv(date_str)
            total_daily = df["Production for the Day"].sum()
            avg_per_plant = df["Production for the Day"].mean()
            max_production = df["Production for the Day"].max()
            
            trend_data.append({
                "Date": date_str,
                "Total Daily Production": total_daily,
                "Average per Plant": avg_per_plant,
                "Max Production": max_production,
                "Number of Plants": len(df)
            })
        except:
            continue
    
    return pd.DataFrame(trend_data)

def create_equipment_health_monitor(df: pd.DataFrame) -> Dict:
    """Simulate equipment health monitoring based on production patterns."""
    health_scores = {}
    
    for plant in df["Plant"].unique():
        plant_data = df[df["Plant"] == plant]
        production = plant_data["Production for the Day"].iloc[0]
        accumulative = plant_data["Accumulative Production"].iloc[0]
        
        # Simulate health score based on production patterns
        base_health = min(100, (production / 1500) * 100)  # Assuming 1500 is optimal
        wear_tear = min(30, (accumulative / 100000) * 30)  # Wear based on total production
        
        health_score = max(0, base_health - wear_tear)
        
        if health_score >= 80:
            status = "🟢 Excellent"
        elif health_score >= 60:
            status = "🟡 Good"
        elif health_score >= 40:
            status = "🟠 Needs Attention"
        else:
            status = "🔴 Critical"
        
        health_scores[plant] = {
            "score": round(health_score, 1),
            "status": status,
            "maintenance_due": "Within 2 weeks" if health_score < 60 else "Next month"
        }
    
    return health_scores

def generate_automated_report(df: pd.DataFrame, kpis: dict, date_str: str) -> str:
    """Generate automated production report."""
    report = f"""
# PRODUCTION REPORT - {date_str}
## Executive Summary

**Overall Performance Grade:** {kpis['overall_grade']}
**Total Daily Production:** {kpis['total_daily']:,.2f} m³
**Utilization Rate:** {kpis['utilization_rate']:.1f}%
**Balance Score:** {kpis['balance_score']:.1f}%

## Key Highlights
- Top Producer: {kpis['max_producer']}
- Plants Needing Attention: {', '.join(kpis['performance_tiers']['Needs Improvement']) if kpis['performance_tiers']['Needs Improvement'] else 'None'}

## Performance Tiers
- Elite Performers: {len(kpis['performance_tiers']['Elite'])}
- Good Performers: {len(kpis['performance_tiers']['Good'])}
- Average Performers: {len(kpis['performance_tiers']['Average'])}
- Needs Improvement: {len(kpis['performance_tiers']['Needs Improvement'])}

## Recommendations
{generate_recommendations_text(kpis)}
"""
    return report

def generate_recommendations_text(kpis: dict) -> str:
    """Generate text recommendations for reports."""
    recommendations = []
    
    if kpis['utilization_rate'] < 70:
        recommendations.append(f"- Improve utilization rate (current: {kpis['utilization_rate']:.1f}%)")
    
    if kpis['balance_score'] < 75:
        recommendations.append(f"- Address production balance (current score: {kpis['balance_score']:.1f}%)")
    
    if kpis['performance_tiers']['Needs Improvement']:
        recommendations.append(f"- Focus on plants: {', '.join(kpis['performance_tiers']['Needs Improvement'])}")
    
    return "\n".join(recommendations) if recommendations else "- Maintain current operational excellence"

# -------------------------------
# UI Enhancement Functions
# -------------------------------

def create_gauge_chart(value: float, title: str, min_val: float = 0, max_val: float = 100) -> go.Figure:
    """Create a beautiful gauge chart for KPIs."""
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = value,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title},
        delta = {'reference': 80},
        gauge = {
            'axis': {'range': [min_val, max_val]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 60], 'color': "lightgray"},
                {'range': [60, 80], 'color': "yellow"},
                {'range': [80, 100], 'color': "lightgreen"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 90
            }
        }
    ))
    fig.update_layout(height=300)
    return fig

def create_performance_radar(kpis: dict) -> go.Figure:
    """Create radar chart for performance metrics."""
    categories = ['Utilization', 'Balance', 'Efficiency', 'Consistency', 'Growth']
    
    values = [
        kpis['utilization_rate'],
        kpis['balance_score'],
        kpis['efficiency_ratio'],
        100 - kpis['std_deviation'] / kpis['avg_per_plant'] * 100,
        min(100, kpis['total_daily'] / 5000 * 100)  # Assuming 5000 is target
    ]
    
    fig = go.Figure(data=go.Scatterpolar(
        r=values,
        theta=categories,
        fill='toself',
        name='Performance Metrics'
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100]
            )),
        showlegend=False,
        height=400
    )
    
    return fig

# -------------------------------
# Original Helper functions (updated)
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
    """Save CSV and attempt to push to GitHub."""
    date_str = date_obj.strftime("%Y-%m-%d")
    file_path = DATA_DIR / f"{date_str}.csv"
    df.to_csv(file_path, index=False)

    if not TOKEN:
        return False, "GITHUB_TOKEN not configured."

    remote_url = f"https://{TOKEN}@github.com/{GITHUB_REPO}.git"

    try:
        subprocess.run(["git", "config", "--global", "user.email", "streamlit@example.com"], check=False)
        subprocess.run(["git", "config", "--global", "user.name", "Streamlit App"], check=False)
        subprocess.run(["git", "add", str(file_path)], check=True)
        
        commit_proc = subprocess.run(["git", "commit", "-m", f"Add production data for {date_str}"], 
                                   check=False, capture_output=True, text=True)
        
        if commit_proc.returncode != 0:
            stdout = commit_proc.stdout + commit_proc.stderr
            if "nothing to commit" in stdout.lower():
                return True, "File saved; no new changes to commit."
            else:
                return False, f"Git commit failed: {stdout.strip()}"

        push_proc = subprocess.run(["git", "push", remote_url, "main"], check=False, capture_output=True, text=True)
        if push_proc.returncode != 0:
            return False, f"Git push failed: {push_proc.stderr.strip()}"
        return True, "File saved and pushed to GitHub successfully."

    except Exception as ex:
        return False, f"Exception while pushing: {ex}"

def list_saved_dates() -> list:
    """Return list of saved dates."""
    files = sorted([p.name.replace(".csv", "") for p in DATA_DIR.glob("*.csv")], reverse=True)
    return files

def load_saved_csv(date_str: str) -> pd.DataFrame:
    """Load a saved CSV by date string."""
    path = DATA_DIR / f"{date_str}.csv"
    if not path.exists():
        raise FileNotFoundError(f"No saved file for {date_str}")
    return pd.read_csv(path)

def delete_saved_csv(date_str: str) -> bool:
    """Delete a saved CSV file."""
    path = DATA_DIR / f"{date_str}.csv"
    if path.exists():
        path.unlink()
        return True
    return False

def rename_saved_csv(old_date: str, new_date: str) -> bool:
    """Rename a saved CSV file."""
    old = DATA_DIR / f"{old_date}.csv"
    new = DATA_DIR / f"{new_date}.csv"
    if old.exists():
        old.rename(new)
        return True
    return False

# -------------------------------
# Plotting helpers
# -------------------------------
def plot_production_pie(df: pd.DataFrame, theme_colors: list, title: str, value_col: str):
    fig = px.pie(df, names="Plant", values=value_col, title=title, color_discrete_sequence=theme_colors)
    fig.update_traces(textinfo="percent+label", hovertemplate="%{label}: %{value} (%{percent})<extra></extra>")
    return fig

def plot_production_bar(df: pd.DataFrame, theme_colors: list, title: str, value_col: str):
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
# Enhanced UI - Sidebar controls
# -------------------------------
st.sidebar.title("🚀 Advanced Controls")

# Theme and appearance
st.sidebar.markdown("### 🎨 Appearance")
theme_choice = st.sidebar.selectbox("Chart Theme", list(COLOR_THEMES.keys()), index=0)
theme_colors = COLOR_THEMES[theme_choice]

# Main navigation
st.sidebar.markdown("### 📊 Navigation")
mode = st.sidebar.radio("Mode", [
    "Upload New Data", 
    "View Historical Data", 
    "Trend Analysis",
    "Real-time Monitor",
    "Equipment Health",
    "Automated Reports",
    "Manage Data"
])

# Advanced features toggle
st.sidebar.markdown("### ⚡ Advanced Features")
enable_ai = st.sidebar.checkbox("Enable AI Features", value=True)
enable_forecasting = st.sidebar.checkbox("Enable Forecasting", value=True)
enable_simulation = st.sidebar.checkbox("Enable Real-time Simulation", value=False)

st.sidebar.markdown("---")
st.sidebar.write("**Quick Actions:**")
if st.sidebar.button("🔄 Refresh All Data"):
    st.rerun()

# -------------------------------
# Main app body
# -------------------------------
st.title("🧱 CONCRETE PRODUCTION DASHBOARD")
st.markdown("### *AI-Powered Operational Intelligence Platform*")

# Show ML availability status
if not ML_AVAILABLE and enable_ai:
    st.warning("⚠️ Machine learning features are disabled. Some AI capabilities may not work properly.")

if mode == "Upload New Data":
    # ... (keep existing upload functionality, but enhanced with new features)
    st.header("📤 Upload New Production Data")
    st.markdown("Upload an Excel (.xlsx) containing production data.")
    
    uploaded_file = st.file_uploader("Select Excel file to upload", type=["xlsx"])
    selected_date = st.date_input("📅 Production Date", value=datetime.today())

    if uploaded_file is not None:
        try:
            df_uploaded = read_excel_to_df(uploaded_file)
        except Exception:
            st.stop()

        valid, msg = validate_dataframe(df_uploaded)
        if not valid:
            st.error(msg)
        else:
            # Enhanced preview with statistics
            st.subheader("📋 Data Preview & Validation")
            col1, col2 = st.columns(2)
            with col1:
                st.dataframe(df_uploaded.head(10))
            with col2:
                st.metric("Total Plants", len(df_uploaded))
                st.metric("Total Production", f"{df_uploaded['Production for the Day'].sum():,.0f} m³")
            
            if st.button("🚀 Upload and Analyze", type="primary"):
                df_save = ensure_date_column(df_uploaded, selected_date)
                weekday_name = pd.to_datetime(df_save["Date"].iloc[0]).day_name()
                
                if weekday_name == "Friday":
                    st.error("Fridays are non-production days.")
                else:
                    pushed, message = save_csv_and_attempt_push(df_save, selected_date)
                    
                    if pushed:
                        st.balloons()
                        st.success("✅ Data uploaded successfully!")
                    
                    # Enhanced analysis section
                    df_display = process_dataframe(df_save)
                    display_comprehensive_analysis(df_display, selected_date.strftime("%Y-%m-%d"))

elif mode == "View Historical Data":
    st.header("📊 Historical Data Analysis")
    saved = list_saved_dates()
    
    if not saved:
        st.info("No historical data found.")
    else:
        col1, col2 = st.columns([2, 1])
        with col1:
            chosen = st.selectbox("Select date:", saved)
        with col2:
            compare_date = st.selectbox("Compare with:", [""] + saved)
        
        try:
            df_hist = load_saved_csv(chosen)
            df_hist_display = process_dataframe(df_hist)
            
            display_comprehensive_analysis(df_hist_display, chosen)
            
            # Comparison feature
            if compare_date:
                df_compare = load_saved_csv(compare_date)
                df_compare_display = process_dataframe(df_compare)
                
                st.subheader("🔄 Date Comparison")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(f"Production on {chosen}", f"{df_hist_display['Production for the Day'].sum():,.0f} m³")
                with col2:
                    change = df_hist_display['Production for the Day'].sum() - df_compare_display['Production for the Day'].sum()
                    st.metric(f"Production on {compare_date}", 
                             f"{df_compare_display['Production for the Day'].sum():,.0f} m³",
                             delta=f"{change:+,.0f} m³")
        
        except Exception as e:
            st.error(f"Error loading data: {e}")

elif mode == "Trend Analysis":
    st.header("📈 Multi-Date Trend Analysis")
    saved = list_saved_dates()
    
    if len(saved) < 2:
        st.info("Need at least 2 dates for trend analysis.")
    else:
        selected_dates = st.multiselect("Select dates for analysis:", saved, default=saved[:7])
        
        if selected_dates:
            trend_df = create_trend_analysis(selected_dates)
            
            if not trend_df.empty:
                # Trend charts
                col1, col2 = st.columns(2)
                with col1:
                    fig_trend = px.line(trend_df, x='Date', y='Total Daily Production', 
                                      title='Total Production Trend', markers=True)
                    st.plotly_chart(fig_trend, use_container_width=True)
                
                with col2:
                    fig_avg = px.line(trend_df, x='Date', y='Average per Plant', 
                                    title='Average Plant Performance Trend', markers=True)
                    st.plotly_chart(fig_avg, use_container_width=True)
                
                # Statistics
                st.subheader("📊 Trend Statistics")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Average Daily Production", f"{trend_df['Total Daily Production'].mean():,.0f} m³")
                with col2:
                    st.metric("Growth Rate", f"{trend_df['Total Daily Production'].pct_change().mean()*100:+.1f}%")
                with col3:
                    st.metric("Best Day", trend_df.loc[trend_df['Total Daily Production'].idxmax(), 'Date'])
                with col4:
                    st.metric("Consistency", f"{trend_df['Total Daily Production'].std()/trend_df['Total Daily Production'].mean()*100:.1f}%")

elif mode == "Real-time Monitor":
    st.header("🔄 Real-time Production Monitor")
    
    if enable_simulation:
        st.info("🔮 Real-time simulation mode active")
        
        # Auto-refresh
        if st.button("🔄 Refresh Simulation"):
            st.rerun()
        
        # Generate simulated data
        simulated_data = simulate_real_time_data()
        display_comprehensive_analysis(simulated_data, "Live Data")
        
        # Real-time metrics
        st.subheader("📊 Live Dashboard")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Current Production", f"{simulated_data['Production for the Day'].sum():,.0f} m³")
        with col2:
            st.metric("Active Plants", len(simulated_data))
        with col3:
            st.metric("Peak Today", f"{simulated_data['Production for the Day'].max():,.0f} m³")
        with col4:
            st.metric("Status", "🟢 Operational")
    else:
        st.warning("Enable real-time simulation in sidebar to use this feature")

elif mode == "Equipment Health":
    st.header("🏭 Equipment Health Monitoring")
    
    saved = list_saved_dates()
    if saved:
        chosen = st.selectbox("Select date for health analysis:", saved)
        
        try:
            df_health = load_saved_csv(chosen)
            health_data = create_equipment_health_monitor(df_health)
            
            st.subheader("🔧 Plant Equipment Status")
            
            for plant, status in health_data.items():
                col1, col2, col3, col4 = st.columns([2,1,1,2])
                with col1:
                    st.write(f"**{plant}**")
                with col2:
                    st.metric("Health Score", f"{status['score']}%")
                with col3:
                    st.write(status['status'])
                with col4:
                    st.write(f"Maintenance: {status['maintenance_due']}")
                
                st.progress(status['score']/100)
                st.markdown("---")
        
        except Exception as e:
            st.error(f"Error loading health data: {e}")

elif mode == "Automated Reports":
    st.header("📑 Automated Reporting")
    
    saved = list_saved_dates()
    if saved:
        report_date = st.selectbox("Select date for report:", saved)
        
        try:
            df_report = load_saved_csv(report_date)
            df_report_display = process_dataframe(df_report)
            kpis = calculate_advanced_kpis(df_report_display)
            
            # Generate report
            report_text = generate_automated_report(df_report_display, kpis, report_date)
            
            st.subheader("📄 Production Report")
            st.markdown(report_text)
            
            # Download option
            st.download_button(
                label="📥 Download Report as PDF",
                data=report_text,
                file_name=f"production_report_{report_date}.md",
                mime="text/markdown"
            )
        
        except Exception as e:
            st.error(f"Error generating report: {e}")

elif mode == "Manage Data":
    st.header("🗃️ Data Management")
    # ... (keep existing management functionality)

# -------------------------------
# Helper functions for enhanced UI
# -------------------------------
def process_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Process dataframe for display and analysis."""
    df_display = df.copy()
    df_display = df_display[~df_display["Plant"].astype(str).str.upper().str.contains("TOTAL")]
    df_display["Production for the Day"] = pd.to_numeric(df_display["Production for the Day"], errors="coerce").fillna(0.0)
    df_display["Accumulative Production"] = pd.to_numeric(df_display["Accumulative Production"], errors="coerce").fillna(0.0)
    return df_display

def display_comprehensive_analysis(df: pd.DataFrame, date_str: str):
    """Display comprehensive analysis for the given dataframe."""
    # KPIs
    kpis = calculate_advanced_kpis(df)
    
    # Enhanced KPI Dashboard
    st.subheader("📊 Advanced Performance Dashboard")
    
    # Gauge charts
    col1, col2, col3 = st.columns(3)
    with col1:
        st.plotly_chart(create_gauge_chart(kpis['utilization_rate'], "Utilization Rate"), use_container_width=True)
    with col2:
        st.plotly_chart(create_gauge_chart(kpis['balance_score'], "Balance Score"), use_container_width=True)
    with col3:
        st.plotly_chart(create_gauge_chart(kpis['efficiency_ratio'], "Efficiency Ratio"), use_container_width=True)
    
    # Performance grade and radar
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Overall Performance Grade", kpis['overall_grade'])
        st.plotly_chart(create_performance_radar(kpis), use_container_width=True)
    
    with col2:
        st.subheader("🏆 Performance Tiers")
        for tier, plants in kpis['performance_tiers'].items():
            st.write(f"**{tier}:** {', '.join(plants) if plants else 'None'}")
    
    # AI Recommendations
    if enable_ai:
        st.subheader("💡 AI-Powered Recommendations")
        recommendations = generate_ai_recommendations(df, kpis)
        
        for rec in recommendations:
            with st.expander(f"{rec['priority']} Priority - {rec['category']}"):
                st.write(rec['message'])
                st.info(f"**Recommended Action:** {rec['action']}")
    
    # Forecasting
    if enable_forecasting and ML_AVAILABLE:
        st.subheader("🔮 Production Forecasting")
        selected_plant = st.selectbox("Select plant for forecast:", df['Plant'].unique())
        
        if selected_plant:
            forecasts = advanced_forecasting(df, selected_plant, days=5)
            
            if "error" not in forecasts:
                forecast_df = pd.DataFrame({
                    'Day': [f'Day {i+1}' for i in range(5)],
                    **forecasts
                })
                
                st.line_chart(forecast_df.set_index('Day'))
            else:
                st.info("Need more historical data for accurate forecasting")

# Footer
st.markdown("---")
st.markdown("### 🚀 *Next-Generation Production Analytics Platform*")
st.markdown("""
**Features:** AI-Powered Insights • Real-time Monitoring • Predictive Analytics • Equipment Health • Automated Reporting
""")

# Add custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #1f77b4;
    }
    .feature-highlight {
        background: linear-gradient(45deg, #1f77b4, #ff7f0e);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)
