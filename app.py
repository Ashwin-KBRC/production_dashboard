import os
import hashlib
import base64
import requests
import csv
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
# PAGE CONFIG & PROFESSIONAL STYLING
# ========================================
st.set_page_config(page_title="Production Dashboard", layout="wide", page_icon="🏆")

# PROFESSIONAL UI CSS
st.markdown("""
<style>
    /* 1. HIDE STREAMLIT BRANDING */
    footer {visibility: hidden !important;}
    #MainMenu {visibility: hidden;}
    header {visibility: hidden !important;}
    .stAppDeployButton {display: none !important;}
    
    /* 2. FIX SIDEBAR (Make it non-collapsible) */
    [data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }
    
    /* 3. PROFESSIONAL FONTS & UI ELEVATION */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Headings */
    h1, h2, h3 {
        font-weight: 800;
        color: #00BFFF; /* Primary color for headers */
    }
    
    /* Buttons */
    .stButton>button {
        border-radius: 8px;
        border: 1px solid #00BFFF;
        color: #00BFFF;
        background-color: #2E3B4E;
        padding: 10px 20px;
        font-weight: 600;
        transition: all 0.2s;
    }
    .stButton>button:hover {
        background-color: #00BFFF;
        color: white;
        box-shadow: 0 4px 8px rgba(0, 191, 255, 0.4);
    }

    /* Input Fields */
    .stTextInput>div>div>input, .stDateInput>div>div>input {
        border-radius: 8px;
        border: 1px solid #4D5E78;
        padding: 10px;
        background-color: #1E2733;
        color: white;
    }

    /* Card/Metric Styling */
    [data-testid="stMetricValue"] {
        font-size: 2.5rem;
        font-weight: 800;
        color: #FFD700; /* Gold for metrics */
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.9rem;
        color: #BBBBBB;
        font-weight: 600;
    }
    
    /* Sidebar styling for professional look */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1C242F 0%, #2E3B4E 100%);
    }

    /* --- DARK MODE FIXES (NEW) --- */
    /* Ensure all sidebar text is white in dark mode */
    .stApp.dark [data-testid="stSidebar"] * {
        color: #FFFFFF !important;
    }
    /* Ensure main app text is white in dark mode */
    .stApp.dark {
        color: #FFFFFF;
    }
    
</style>
""", unsafe_allow_html=True)


# ========================================
# DATA SIMULATION & UTILITIES
# ========================================

# Theme colors for charts
theme_colors = {
    'primary': '#00BFFF',  # Deep Sky Blue
    'secondary': '#FFD700',  # Gold
    'tertiary': '#FF4500',  # Orange Red
    'quaternary': '#7CFC00', # Lawn Green
    'background': '#1E2733', # Dark background
}

def load_data() -> pd.DataFrame:
    """Creates or loads simulated production data."""
    if 'production_data' not in st.session_state:
        # Simulate data for 365 days
        start_date = datetime.now() - timedelta(days=365)
        dates = [start_date + timedelta(days=i, hours=np.random.randint(0, 24)) 
                 for i in range(365) for _ in range(np.random.randint(2, 5))]
        
        data = {
            'Timestamp': dates,
            'Product Name': np.random.choice(['Product A', 'Product B', 'Product C', 'Product D', 'Product E'], size=len(dates)),
            'Machine ID': np.random.choice(['M-001', 'M-002', 'M-003', 'M-004', 'M-005'], size=len(dates)),
            'Shift': np.random.choice(['Morning', 'Afternoon', 'Night'], size=len(dates)),
            'Quantity': np.random.randint(50, 500, size=len(dates)),
            'Quality Score': np.random.uniform(90.0, 100.0, size=len(dates)).round(2)
        }
        df = pd.DataFrame(data)
        df = df.set_index('Timestamp').sort_index()
        st.session_state['production_data'] = df
    return st.session_state['production_data']

def save_log(action: str):
    """Saves user actions to a log file."""
    log_path = Path('access_logs.csv')
    if not log_path.exists():
        with open(log_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Timestamp', 'User', 'Action'])
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    user = st.session_state.get('current_user', 'anonymous')
    
    with open(log_path, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, user, action])

def get_logs() -> pd.DataFrame:
    """Reads the access logs."""
    log_path = Path('access_logs.csv')
    if log_path.exists():
        return pd.read_csv(log_path, index_col='Timestamp', parse_dates=True)
    return pd.DataFrame()

def get_current_user() -> str:
    """Simulates user authentication status."""
    return st.session_state.get('current_user', 'guest')

def create_chart(df: pd.DataFrame, y_col: str, x_col: str, color_map: Dict[str, str], title: str, chart_type: str = 'bar'):
    """
    Creates a standardized Plotly chart with dark mode compatibility.
    Updated to enforce dark chart backgrounds.
    """
    
    if df.empty:
        return px.bar(title="No Data Available")

    if chart_type == 'bar':
        fig = px.bar(
            df, 
            x=x_col, 
            y=y_col, 
            color_discrete_sequence=[color_map['primary'], color_map['secondary']],
            title=title
        )
    elif chart_type == 'line':
        fig = px.line(
            df, 
            x=x_col, 
            y=y_col, 
            line_shape='spline',
            color_discrete_sequence=[color_map['primary']],
            title=title
        )
        fig.update_traces(mode='lines+markers', marker=dict(size=6, line=dict(width=2)))
    elif chart_type == 'pie':
        fig = px.pie(
            df,
            names=x_col,
            values=y_col,
            color_discrete_sequence=list(color_map.values()),
            title=title,
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
    else:
        # Default to bar chart if type is unknown
        return create_chart(df, y_col, x_col, color_map, title, chart_type='bar')

    # Apply Dark Mode Styling for Chart Background and Text
    fig.update_layout(
        # Set background colors to dark/transparent for dark mode compatibility
        paper_bgcolor='rgba(0,0,0,0)', # Transparent paper background
        plot_bgcolor='#1E1E1E', # Dark plot background (from the custom CSS background)
        font=dict(color='#FFFFFF'), # White text for dark mode
        title=dict(font=dict(size=20, color='#FFFFFF')),
        xaxis=dict(showgrid=False, linecolor='#555555', mirror=True, title_font=dict(color='#FFFFFF'), tickfont=dict(color='#FFFFFF')),
        yaxis=dict(showgrid=True, gridcolor='#333333', linecolor='#555555', mirror=True, title_font=dict(color='#FFFFFF'), tickfont=dict(color='#FFFFFF')),
        legend_title_font_color="#FFFFFF",
        legend=dict(font=dict(color="#FFFFFF")),
        template="plotly_dark" # Use dark template for better contrast
    )
    
    return fig

# ========================================
# AUTHENTICATION SIMULATION
# ========================================

# Simple user dictionary
USERS = {
    "admin": {"password": "admin"},
    "manager": {"password": "manager"},
    "operator": {"password": "operator"}
}

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'current_user' not in st.session_state:
    st.session_state['current_user'] = 'guest'

def handle_login():
    username = st.session_state.username
    password = st.session_state.password
    
    if username in USERS and USERS[username]["password"] == password:
        st.session_state['logged_in'] = True
        st.session_state['current_user'] = username
        save_log(f"User '{username}' logged in.")
        st.success(f"Welcome back, {username.capitalize()}!")
        st.experimental_rerun()
    else:
        st.error("Invalid username or password.")

# ========================================
# MAIN APP STRUCTURE
# ========================================

current_user = get_current_user()
production_df = load_data()

# --- SIDEBAR & AUTHENTICATION ---
with st.sidebar:
    st.image("https://placehold.co/100x30/00BFFF/FFFFFF?text=FACTORY+HUB", width=180)
    st.markdown("## Production Dashboard")
    
    if not st.session_state['logged_in']:
        st.markdown("### 🔑 Login")
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.button("Login", on_click=handle_login)
    else:
        st.success(f"Signed in as: **{current_user.capitalize()}**")
        
        mode = st.radio(
            "Navigation",
            ["Analytics", "Data Entry", "Historical Archives", "Logs"],
            index=0,
            key="app_mode"
        )
        
        def logout():
            save_log(f"User '{current_user}' logged out.")
            st.session_state['logged_in'] = False
            st.session_state['current_user'] = 'guest'
            st.experimental_rerun()
            
        st.button("Logout", on_click=logout)

# --- MAIN CONTENT ---

if not st.session_state['logged_in']:
    st.title("Access Denied - Please Log In")
    st.info("Log in using one of the demo accounts:\n- **admin** / admin\n- **manager** / manager\n- **operator** / operator")
    
elif mode == "Data Entry":
    if current_user not in ["admin", "operator"]:
        st.error("Access Denied. Only Admins and Operators can enter data.")
    else:
        st.header("New Production Record Entry")
        
        with st.form("production_form"):
            col1, col2, col3 = st.columns(3)
            
            product = col1.selectbox("Product Name", production_df['Product Name'].unique())
            machine = col2.selectbox("Machine ID", production_df['Machine ID'].unique())
            shift = col3.selectbox("Shift", ['Morning', 'Afternoon', 'Night'])
            
            quantity = st.number_input("Quantity Produced", min_value=1, value=100)
            quality_score = st.slider("Quality Score (%)", min_value=90.0, max_value=100.0, value=99.5, step=0.1)
            
            submitted = st.form_submit_button("Submit Record")
            
            if submitted:
                # Add new record
                new_index = datetime.now()
                new_record = pd.Series({
                    'Product Name': product,
                    'Machine ID': machine,
                    'Shift': shift,
                    'Quantity': quantity,
                    'Quality Score': quality_score
                }, name=new_index)
                
                # Use pd.concat for non-mutating update
                production_df = pd.concat([production_df, new_record.to_frame().T]).sort_index()
                st.session_state['production_data'] = production_df # Update session state
                
                save_log(f"User '{current_user}' submitted {quantity} units of {product}.")
                st.success("Production record submitted successfully!")

# ========================================
# ANALYTICS DASHBOARD
# ========================================
elif mode == "Analytics":
    st.header("Real-Time Production Analytics")
    
    # Date Range Selector
    max_date = production_df.index.max().date()
    min_date = production_df.index.min().date()

    with st.expander("Date Range & Analysis Type Selector", expanded=True):
        col_p1, col_p2 = st.columns([1, 3])
        
        selected_period = col_p1.radio(
            "Select Analysis Period",
            ["Selected Date Range Analysis", "Monthly Analytics"],
            key="analysis_period_radio"
        )
        
        if selected_period == "Selected Date Range Analysis":
            start_date = col_p2.date_input("Start Date", min_value=min_date, max_value=max_date, value=max_date - timedelta(days=7))
            end_date = col_p2.date_input("End Date", min_value=min_date, max_value=max_date, value=max_date)
            
            # Filter the dataframe based on the selected date range
            filtered_df = production_df.loc[start_date.strftime('%Y-%m-%d'):end_date.strftime('%Y-%m-%d')]
            
        else: # Monthly Analytics
            # Get unique year-month periods
            periods = sorted(production_df.index.to_period('M').unique(), reverse=True)
            if periods:
                selected_month = col_p2.selectbox("Select Month to Analyze", periods, format_func=lambda x: x.strftime('%B %Y'))
                month_to_analyze = selected_month
                
                # Filter data for the selected month
                filtered_df = production_df[production_df.index.to_period('M') == month_to_analyze]
            else:
                st.info("No data available for monthly analysis.")
                filtered_df = pd.DataFrame() # Empty dataframe to avoid errors

    if filtered_df.empty:
        st.warning("No data found for the selected date range/month.")
    else:
        
        # --- KEY PERFORMANCE INDICATORS ---
        total_production = filtered_df['Quantity'].sum()
        avg_quality = filtered_df['Quality Score'].mean()
        num_records = len(filtered_df)
        
        col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
        
        col_kpi1.metric("Total Production (Units)", f"{total_production:,}", delta="Daily Target +20%")
        col_kpi2.metric("Average Quality Score", f"{avg_quality:.2f}%", delta=f"{avg_quality - 99.0:.2f}%")
        col_kpi3.metric("Records Processed", f"{num_records:,}")
        col_kpi4.metric("Most Active Machine", filtered_df['Machine ID'].mode().iloc[0] if not filtered_df.empty else "N/A")


        # ========================================
        # SELECTED DATE RANGE ANALYSIS
        # ========================================
        if selected_period == "Selected Date Range Analysis":
            st.markdown("---")
            st.subheader(f"Analysis from {start_date} to {end_date}")

            # --- TOP PERFORMANCE HEADLINES (NEW) ---
            st.markdown("### 🏆 Top Performance Analysis (Machines in Selected Range)")
            col1, col2 = st.columns(2)

            # Top 3 Max Production (By Machine)
            # Group by machine and sum quantity to find total production per machine
            top_max_prod = filtered_df.groupby('Machine ID')['Quantity'].sum().nlargest(3).reset_index()
            with col1:
                st.markdown("#### Top 3 Total Production")
                if not top_max_prod.empty:
                    for i, row in top_max_prod.iterrows():
                        # Using custom markdown for professional box look
                        st.markdown(f"""
                        <div style='background-color: #2E3B4E; padding: 10px; border-radius: 8px; margin-bottom: 8px; border-left: 5px solid {theme_colors['primary']}; box-shadow: 2px 2px 5px rgba(0,0,0,0.2);'>
                            <span style='font-size: 1.1em; font-weight: 600; color: #FFFFFF;'>
                                #{i+1}: {row['Machine ID']}
                            </span>
                            <span style='float: right; font-size: 1.1em; font-weight: 800; color: {theme_colors['primary']};'>
                                {row['Quantity']:,}
                            </span>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("No data to calculate Top 3 Total Production.")


            # Top 3 Average Production (By Machine)
            # Calculate the average production per record/entry in the filtered data per machine
            top_avg_prod = filtered_df.groupby('Machine ID')['Quantity'].mean().nlargest(3).reset_index()
            top_avg_prod['Quantity'] = top_avg_prod['Quantity'].round(2)

            with col2:
                st.markdown("#### Top 3 Average Production (Per Record)")
                if not top_avg_prod.empty:
                    for i, row in top_avg_prod.iterrows():
                        st.markdown(f"""
                        <div style='background-color: #2E3B4E; padding: 10px; border-radius: 8px; margin-bottom: 8px; border-left: 5px solid {theme_colors['secondary']}; box-shadow: 2px 2px 5px rgba(0,0,0,0.2);'>
                            <span style='font-size: 1.1em; font-weight: 600; color: #FFFFFF;'>
                                #{i+1}: {row['Machine ID']}
                            </span>
                            <span style='float: right; font-size: 1.1em; font-weight: 800; color: {theme_colors['secondary']};'>
                                {row['Quantity']:,} (Avg)
                            </span>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("No data to calculate Top 3 Average Production.")
            
            st.markdown("---")

            col_chart1, col_chart2 = st.columns(2)
            
            # Chart 1: Production by Shift
            shift_prod = filtered_df.groupby('Shift')['Quantity'].sum().reset_index()
            with col_chart1:
                st.plotly_chart(create_chart(shift_prod, "Quantity", "Shift", theme_colors, "Production by Shift"), use_container_width=True)
                
            # Chart 2: Quality Distribution by Product
            product_quality = filtered_df.groupby('Product Name')['Quality Score'].mean().reset_index()
            with col_chart2:
                st.plotly_chart(create_chart(product_quality, "Quality Score", "Product Name", theme_colors, "Average Quality by Product", chart_type='bar'), use_container_width=True)
                
            # Chart 3: Daily Production Trend
            daily_trend = filtered_df.groupby(filtered_df.index.date)['Quantity'].sum().reset_index()
            daily_trend.columns = ['Date', 'Daily Production']
            st.plotly_chart(create_chart(daily_trend, "Daily Production", "Date", theme_colors, "Daily Production Trend (Selected Range)", chart_type='line'), use_container_width=True)

        # ========================================
        # MONTHLY ANALYTICS
        # ========================================
        elif selected_period == "Monthly Analytics":
            st.markdown("---")
            st.subheader(f"Monthly Trajectory for {month_to_analyze.strftime('%B %Y')}")

            # CHART: Daily Production Trajectory for Selected Month (Line Graph)
            daily_prod_in_month = filtered_df.groupby(filtered_df.index.date)['Quantity'].sum().reset_index()
            daily_prod_in_month.columns = ['Date', 'Daily Production']

            if not daily_prod_in_month.empty:
                # Create the line chart showing trajectory
                st.plotly_chart(create_chart(daily_prod_in_month, 'Daily Production', 'Date', theme_colors, f"Daily Production Trajectory for {month_to_analyze.strftime('%B %Y')}", chart_type='line'), use_container_width=True)
            else:
                st.info(f"No production data available for {month_to_analyze.strftime('%B %Y')}.")
            
            st.markdown("### Monthly Breakdowns")
            
            col_m1, col_m2 = st.columns(2)
            
            # Breakdown 1: Production by Machine
            monthly_machine = filtered_df.groupby('Machine ID')['Quantity'].sum().reset_index()
            with col_m1:
                st.plotly_chart(create_chart(monthly_machine, "Quantity", "Machine ID", theme_colors, "Monthly Production by Machine"), use_container_width=True)
            
            # Breakdown 2: Production by Product
            monthly_product = filtered_df.groupby('Product Name')['Quantity'].sum().reset_index()
            with col_m2:
                st.plotly_chart(create_chart(monthly_product, "Quantity", "Product Name", theme_colors, "Monthly Production by Product"), use_container_width=True)


# ========================================
# HISTORICAL ARCHIVES
# ========================================
elif mode == "Historical Archives":
    st.header("Comprehensive Historical Archives")
    
    st.markdown("### All-Time Production Summary")

    # Group by month for historical analysis
    historical_monthly = production_df.groupby(production_df.index.to_period('M'))['Quantity'].sum().reset_index()
    historical_monthly['Month'] = historical_monthly['Timestamp'].astype(str)
    
    # Chart 1: Monthly Production Trend (Bar Chart)
    st.plotly_chart(create_chart(historical_monthly, "Quantity", "Month", theme_colors, "Monthly Production Trend (All-Time)", chart_type='bar'), use_container_width=True)

    
    # --- ACCUMULATIVE & BREAKDOWN CHARTS ---
    
    st.subheader("Accumulative Production Insights (All-Time)")
    col_h1, col_h2 = st.columns(2)

    # Chart 2: Total Production by Machine (Accumulative)
    machine_prod = production_df.groupby('Machine ID')['Quantity'].sum().reset_index()
    machine_prod.columns = ['Machine ID', 'Total Quantity']
    with col_h1:
        st.plotly_chart(create_chart(machine_prod, 'Total Quantity', 'Machine ID', theme_colors, "Total Production by Machine (All-Time)", chart_type='bar'), use_container_width=True)

    # Chart 3: Total Production by Product (Accumulative)
    product_prod = production_df.groupby('Product Name')['Quantity'].sum().reset_index()
    product_prod.columns = ['Product Name', 'Total Quantity']
    with col_h2:
        st.plotly_chart(create_chart(product_prod, 'Total Quantity', 'Product Name', theme_colors, "Total Production by Product (All-Time)", chart_type='bar'), use_container_width=True)

    st.subheader("Daily & Shift-Based Trends")

    # Prepare daily data
    daily_trend = production_df.groupby(production_df.index.date)['Quantity'].sum().reset_index()
    daily_trend.columns = ['Date', 'Quantity']

    # Chart 4: Cumulative Daily Production Trend (Accumulative Line Graph)
    daily_trend['Cumulative Quantity'] = daily_trend['Quantity'].cumsum()
    st.plotly_chart(create_chart(daily_trend, 'Cumulative Quantity', 'Date', theme_colors, "Cumulative Daily Production Trend", chart_type='line'), use_container_width=True)

    # Chart 5: Production by Shift Distribution (Pie Chart)
    shift_distribution = production_df.groupby('Shift')['Quantity'].sum().reset_index()
    st.plotly_chart(create_chart(shift_distribution, 'Quantity', 'Shift', theme_colors, "Shift Production Distribution (All-Time)", chart_type='pie'), use_container_width=True)


# ========================================
# LOGS VIEWER (MANAGER ONLY)
# ========================================
elif mode == "Logs":
    if current_user != "manager":
        st.error("Access Denied.")
    else:
        st.header("Security & Access Logs")
        
        logs_df = get_logs()
        if logs_df.empty:
            st.info("No logs recorded yet.")
        else:
            # Sort by timestamp descending
            logs_df = logs_df.sort_index(ascending=False)
            
            st.markdown("### Recent Activity")
            st.dataframe(logs_df, use_container_width=True, height=500)
            
            csv = logs_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Download Logs CSV",
                csv,
                "access_logs.csv",
                "text/csv",
                key='download-logs'
            )

# ========================================
# FOOTER
# ========================================
st.sidebar.markdown("---")
st.sidebar.caption("Support")
st.sidebar.markdown("""
<div style="font-size:0.85rem;">
    <strong>Eng. Ashwin Joseph Mathew</strong><br>
    Head of IT<br>
    <a href="mailto:ashwin.mathew@example.com" style="color:#00BFFF; text-decoration:none;">ashwin.mathew@example.com</a>
</div>
""", unsafe_allow_html=True)
