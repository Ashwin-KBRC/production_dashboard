import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import os
from datetime import datetime, timedelta

# Set up the webpage
st.set_page_config(
    page_title="KBRC Production Analytics", 
    layout="wide",
    page_icon="📊"
)

# PROFESSIONAL CSS
st.markdown("""
<style>
    /* Main background */
    .main {
        background-color: #f8fafc;
    }
    
    /* Professional header */
    .header {
        background: linear-gradient(135deg, #2E8B57 0%, #1e5c3a 100%);
        padding: 2.5rem 2rem;
        border-radius: 0px 0px 15px 15px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        text-align: center;
        border-bottom: 4px solid #ffc107;
    }
    
    /* Company title with gold accent */
    .company-title {
        color: white;
        font-size: 2.8rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: 0.5px;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
    }
    
    .company-subtitle {
        color: rgba(255,255,255,0.9);
        font-size: 1.3rem;
        margin: 0.5rem 0 0 0;
        font-weight: 300;
        letter-spacing: 1px;
    }
    
    /* Professional metric cards */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
        border: 1px solid #e9ecef;
        transition: transform 0.2s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(0,0,0,0.08);
    }
    
    /* Section headers */
    .section-header {
        color: #2E8B57;
        font-size: 1.6rem;
        font-weight: 700;
        margin: 2.5rem 0 1.2rem 0;
        padding-bottom: 0.8rem;
        border-bottom: 2px solid #e9ecef;
        display: flex;
        align-items: center;
    }
    
    .section-header::before {
        content: "📈";
        margin-right: 10px;
        font-size: 1.4rem;
    }
    
    /* Professional tables */
    .dataframe {
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        border: 1px solid #e9ecef;
    }
    
    .dataframe thead th {
        background: linear-gradient(135deg, #2E8B57 0%, #3CB371 100%) !important;
        color: white !important;
        font-weight: 600 !important;
        text-align: center !important;
        padding: 12px !important;
    }
    
    .dataframe tbody td {
        padding: 10px !important;
        text-align: center !important;
    }
    
    .dataframe tbody tr:nth-child(even) {
        background-color: #f8f9fa;
    }
    
    .dataframe tbody tr:hover {
        background-color: #e8f5e8;
    }
    
    /* Footer */
    .footer {
        background: linear-gradient(135deg, #2E8B57 0%, #1e5c3a 100%);
        padding: 1.5rem;
        border-radius: 15px 15px 0 0;
        margin-top: 3rem;
        text-align: center;
        color: white;
        box-shadow: 0 -4px 20px rgba(0,0,0,0.08);
        border-top: 4px solid #ffc107;
    }
    
    /* Logo styling */
    .company-logo {
        font-size: 3rem;
        font-weight: 800;
        color: white;
        background: rgba(255,255,255,0.15);
        padding: 1rem 2rem;
        border-radius: 12px;
        display: inline-block;
        margin-bottom: 1rem;
        border: 2px solid rgba(255,255,255,0.3);
        letter-spacing: 2px;
    }
    
    /* Chart container */
    .chart-container {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        border: 1px solid #e9ecef;
        margin-bottom: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Function to display your KBRC logo
def display_logo():
    st.markdown("""
    <div class="header">
        <div class="company-logo">KBRC</div>
        <p style="color: rgba(255,255,255,0.8); font-style: italic; margin: 0.5rem 0 1.5rem 0; font-size: 1rem;">Established in 1980</p>
        <h1 class="company-title">KUWAITI BRITISH READYMIX CO.</h1>
        <p class="company-subtitle">Production Performance Analytics Dashboard</p>
    </div>
    """, unsafe_allow_html=True)

# Display header
display_logo()

# Main dashboard content
st.markdown("### 📊 Advanced Production Analytics - Financial Grade Reporting")
st.markdown("---")

# SIDEBAR CONTROLS
st.sidebar.markdown("### 🎛️ **Dashboard Controls**")
st.sidebar.markdown("---")

# DATE RANGE SELECTION
st.sidebar.markdown("#### 📅 **Date Range**")
date_option = st.sidebar.selectbox(
    "Select Date Range:",
    ['Last 7 Days', 'Last 15 Days', 'Last 30 Days', 'Last 90 Days', 'Custom Range']
)

if date_option == 'Custom Range':
    start_date = st.sidebar.date_input("Start Date", datetime.now() - timedelta(days=30))
    end_date = st.sidebar.date_input("End Date", datetime.now())
    days_range = (end_date - start_date).days
else:
    days_ranges = {
        'Last 7 Days': 7,
        'Last 15 Days': 15,
        'Last 30 Days': 30,
        'Last 90 Days': 90
    }
    days_range = days_ranges[date_option]

# CHART STYLE SELECTION
st.sidebar.markdown("#### 🎨 **Chart Style**")
chart_theme = st.sidebar.selectbox(
    "Chart Theme:",
    ['plotly_white', 'ggplot2', 'seaborn', 'simple_white', 'plotly']
)

show_annotations = st.sidebar.checkbox("Show Data Labels", True)
show_grid = st.sidebar.checkbox("Show Grid Lines", True)

# PRODUCTION TARGET SETTINGS
st.sidebar.markdown("#### 🎯 **Production Targets**")
expected_daily_growth = st.sidebar.slider("Expected Daily Growth (%)", 0.0, 10.0, 2.0, 0.1)
expected_weekly_growth = st.sidebar.slider("Expected Weekly Growth (%)", 0.0, 15.0, 5.0, 0.1)

st.sidebar.markdown("---")

# FILE STATUS
st.sidebar.markdown("#### 📁 **Data Status**")
file_path = 'data/daily_production.xlsx'
if os.path.exists(file_path):
    file_time = os.path.getmtime(file_path)
    last_updated = datetime.fromtimestamp(file_time).strftime('%Y-%m-%d %H:%M')
    st.sidebar.success(f"✅ **Last Updated:** {last_updated}")
else:
    st.sidebar.error("❌ **Excel File Missing**")

# PLANT SELECTION
st.sidebar.markdown("---")
st.sidebar.markdown("#### 🏭 **Plant Selection**")
plants = ['Kabed', 'Sulaibiya', 'Amgharah', 'Mutla_A', 'Mutla_B']
selected_plants = st.sidebar.multiselect(
    "Select Plants:",
    options=plants,
    default=plants
)

# GENERATE SAMPLE DATA
def generate_production_data(days=30):
    """Generate realistic production data with trends"""
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    
    base_production = {
        'Kabed': 600,
        'Sulaibiya': 550,
        'Amgharah': 500,
        'Mutla_A': 300,
        'Mutla_B': 280
    }
    
    data = {'Date': dates}
    
    for plant in plants:
        # Generate realistic production with trends
        base = base_production[plant]
        trend = np.linspace(0, days * (expected_daily_growth/100 * base), days)
        noise = np.random.normal(0, base * 0.1, days)  # 10% noise
        weekly_pattern = base * 0.15 * np.sin(np.arange(days) * 2 * np.pi / 7)  # Weekly cycle
        
        production = base + trend + noise + weekly_pattern
        production = np.maximum(production, base * 0.7)  # Minimum 70% of base
        
        data[plant] = production.round(0)
        
        # Add cumulative production
        data[f'{plant}_Cumulative'] = np.cumsum(production.round(0))
    
    return pd.DataFrame(data)

# Generate data
df = generate_production_data(days_range)
df['Week'] = df['Date'].dt.isocalendar().week
df['Month'] = df['Date'].dt.strftime('%Y-%m')

# WEEKLY AND MONTHLY AGGREGATIONS
weekly_data = df.groupby('Week').agg({plant: 'sum' for plant in selected_plants}).reset_index()
monthly_data = df.groupby('Month').agg({plant: 'sum' for plant in selected_plants}).reset_index()

# CALCULATE KPIs
st.markdown('<div class="section-header">📈 Key Performance Indicators</div>', unsafe_allow_html=True)

# Create KPI cards
cols = st.columns(5)

for i, plant in enumerate(selected_plants):
    with cols[i]:
        # Calculate metrics
        today_prod = df[plant].iloc[-1]
        avg_prod = df[plant].mean()
        total_prod = df[plant].sum()
        trend = "📈" if today_prod > avg_prod else "📉"
        trend_color = "normal" if today_prod > avg_prod else "inverse"
        
        # Display metric card
        st.markdown(f'<div class="metric-card">', unsafe_allow_html=True)
        st.metric(
            label=f"**{plant}**",
            value=f"{today_prod:,.0f} m³",
            delta=f"{trend} Today's Production",
            delta_color=trend_color
        )
        
        # Additional metrics
        st.caption(f"📊 Avg: {avg_prod:,.0f} m³")
        st.caption(f"📈 Total: {total_prod:,.0f} m³")
        
        # Efficiency indicator
        efficiency = (today_prod / avg_prod * 100) if avg_prod > 0 else 0
        if efficiency >= 100:
            st.success(f"✅ {efficiency:.1f}% of average")
        elif efficiency >= 80:
            st.info(f"⚠️ {efficiency:.1f}% of average")
        else:
            st.warning(f"⚠️ {efficiency:.1f}% of average")
        
        st.markdown('</div>', unsafe_allow_html=True)

# CHART 1: DAILY PRODUCTION BY PLANT (LINE CHART)
st.markdown('<div class="section-header">📊 Daily Production by Plant</div>', unsafe_allow_html=True)

st.markdown('<div class="chart-container">', unsafe_allow_html=True)

# Prepare data for line chart
line_data = df.melt(id_vars=['Date'], value_vars=selected_plants, 
                   var_name='Plant', value_name='Production')

fig1 = px.line(
    line_data, 
    x='Date', 
    y='Production', 
    color='Plant',
    title='<b>Daily Production Volume by Plant</b>',
    labels={'Production': 'Production (m³)', 'Date': 'Date'},
    height=500,
    template=chart_theme
)

# Enhance chart
fig1.update_layout(
    plot_bgcolor='white',
    paper_bgcolor='white',
    font=dict(size=12),
    hovermode='x unified',
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1
    ),
    title=dict(x=0.5, xanchor='center')
)

# Add annotations if enabled
if show_annotations:
    # Add average line for each plant
    for plant in selected_plants:
        avg_value = df[plant].mean()
        fig1.add_hline(
            y=avg_value, 
            line_dash="dash", 
            line_color="gray",
            annotation_text=f"Avg: {avg_value:.0f}",
            annotation_position="bottom right"
        )

# Add grid if enabled
if show_grid:
    fig1.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.05)')
    fig1.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.05)')

st.plotly_chart(fig1, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# TWO COLUMNS FOR WEEKLY AND MONTHLY VIEWS
col1, col2 = st.columns(2)

with col1:
    # CHART 2: WEEKLY PRODUCTION TREND
    st.markdown('<div class="section-header">📅 Weekly Production</div>', unsafe_allow_html=True)
    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
    
    weekly_melted = weekly_data.melt(id_vars=['Week'], value_vars=selected_plants,
                                     var_name='Plant', value_name='Production')
    
    fig2 = px.bar(
        weekly_melted,
        x='Week',
        y='Production',
        color='Plant',
        title='<b>Weekly Production by Plant</b>',
        labels={'Production': 'Production (m³)', 'Week': 'Week Number'},
        barmode='group',
        height=400,
        template=chart_theme
    )
    
    fig2.update_layout(
        plot_bgcolor='white',
        paper_bgcolor='white',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    if show_annotations:
        fig2.update_traces(texttemplate='%{y:,.0f}', textposition='outside')
    
    st.plotly_chart(fig2, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    # CHART 3: CUMULATIVE PRODUCTION
    st.markdown('<div class="section-header">📈 Cumulative Production</div>', unsafe_allow_html=True)
    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
    
    # Prepare cumulative data
    cum_data = []
    for plant in selected_plants:
        cum_col = f'{plant}_Cumulative'
        for i, date in enumerate(df['Date']):
            cum_data.append({
                'Date': date,
                'Plant': plant,
                'Cumulative_Production': df[cum_col].iloc[i]
            })
    
    cum_df = pd.DataFrame(cum_data)
    
    fig3 = px.area(
        cum_df,
        x='Date',
        y='Cumulative_Production',
        color='Plant',
        title='<b>Cumulative Production Over Time</b>',
        labels={'Cumulative_Production': 'Cumulative Production (m³)', 'Date': 'Date'},
        height=400,
        template=chart_theme
    )
    
    fig3.update_layout(
        plot_bgcolor='white',
        paper_bgcolor='white',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    if show_grid:
        fig3.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.05)')
        fig3.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.05)')
    
    st.plotly_chart(fig3, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# CHART 4: EXPECTED VS ACTUAL PRODUCTION (FINANCIAL-STYLE)
st.markdown('<div class="section-header">🎯 Expected vs Actual Production</div>', unsafe_allow_html=True)
st.markdown("""
<div style="background: linear-gradient(135deg, #f8fff8 0%, #f0f8f0 100%); 
            padding: 1.5rem; border-radius: 10px; margin-bottom: 1.5rem; border-left: 4px solid #2E8B57;">
    <p style="margin: 0; color: #2E8B57; font-weight: 600;">📊 Financial-Style Production Analysis</p>
    <p style="margin: 0.5rem 0 0 0; color: #666; font-size: 0.9rem;">
    Comparing actual production against expected targets with {expected_daily_growth}% daily growth target.
    </p>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="chart-container">', unsafe_allow_html=True)

# Calculate expected production
fig4 = go.Figure()

for plant in selected_plants:
    # Actual production
    fig4.add_trace(go.Scatter(
        x=df['Date'],
        y=df[plant],
        name=f'{plant} - Actual',
        mode='lines+markers',
        line=dict(width=3),
        marker=dict(size=6)
    ))
    
    # Expected production (with growth)
    initial_value = df[plant].iloc[0]
    expected = [initial_value * (1 + expected_daily_growth/100) ** i for i in range(len(df))]
    
    fig4.add_trace(go.Scatter(
        x=df['Date'],
        y=expected,
        name=f'{plant} - Expected',
        mode='lines',
        line=dict(width=2, dash='dash', color='gray'),
        opacity=0.7
    ))

# Update layout for financial style
fig4.update_layout(
    title='<b>Actual vs Expected Production Growth</b>',
    xaxis_title='Date',
    yaxis_title='Production (m³)',
    height=500,
    template=chart_theme,
    plot_bgcolor='white',
    paper_bgcolor='white',
    hovermode='x unified',
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        font=dict(size=11)
    )
)

# Add performance bands
for plant in selected_plants:
    avg_value = df[plant].mean()
    fig4.add_hline(
        y=avg_value, 
        line_dash="dot", 
        line_color="rgba(0,0,0,0.2)",
        annotation_text=f"Avg Line",
        annotation_position="bottom right"
    )

# Add grid
if show_grid:
    fig4.update_xaxes(
        showgrid=True, 
        gridwidth=1, 
        gridcolor='rgba(0,0,0,0.05)',
        showline=True,
        linewidth=1,
        linecolor='rgba(0,0,0,0.1)'
    )
    fig4.update_yaxes(
        showgrid=True, 
        gridwidth=1, 
        gridcolor='rgba(0,0,0,0.05)',
        showline=True,
        linewidth=1,
        linecolor='rgba(0,0,0,0.1)'
    )

st.plotly_chart(fig4, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# CHART 5: PRODUCTION DISTRIBUTION (PIE CHART)
st.markdown('<div class="section-header">📊 Production Distribution</div>', unsafe_allow_html=True)

col3, col4 = st.columns(2)

with col3:
    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
    
    # Today's distribution
    today_data = df[selected_plants].iloc[-1]
    
    fig5 = px.pie(
        values=today_data.values,
        names=today_data.index,
        title='<b>Today\'s Production Distribution</b>',
        hole=0.4,
        height=350
    )
    
    fig5.update_traces(
        textposition='inside',
        textinfo='percent+label',
        marker=dict(line=dict(color='white', width=2))
    )
    
    fig5.update_layout(
        showlegend=True,
        annotations=[dict(
            text=f"Total\n{today_data.sum():,.0f} m³", 
            x=0.5, y=0.5, 
            font_size=16, 
            showarrow=False,
            font_color='#2E8B57'
        )]
    )
    
    st.plotly_chart(fig5, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with col4:
    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
    
    # Total production distribution
    total_data = df[selected_plants].sum()
    
    fig6 = px.pie(
        values=total_data.values,
        names=total_data.index,
        title='<b>Total Production Distribution</b>',
        hole=0.4,
        height=350
    )
    
    fig6.update_traces(
        textposition='inside',
        textinfo='percent+label',
        marker=dict(line=dict(color='white', width=2))
    )
    
    fig6.update_layout(
        showlegend=True,
        annotations=[dict(
            text=f"Total\n{total_data.sum():,.0f} m³", 
            x=0.5, y=0.5, 
            font_size=16, 
            showarrow=False,
            font_color='#2E8B57'
        )]
    )
    
    st.plotly_chart(fig6, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# PERFORMANCE SUMMARY TABLE
st.markdown('<div class="section-header">📋 Production Performance Summary</div>', unsafe_allow_html=True)

# Create comprehensive summary
summary_data = []
for plant in selected_plants:
    plant_data = df[plant]
    
    # Calculate growth rates
    if len(plant_data) > 1:
        daily_growth = ((plant_data.iloc[-1] / plant_data.iloc[-2]) - 1) * 100
        total_growth = ((plant_data.iloc[-1] / plant_data.iloc[0]) - 1) * 100
    else:
        daily_growth = total_growth = 0
    
    summary_data.append({
        'Plant': plant,
        'Today (m³)': f"{plant_data.iloc[-1]:,.0f}",
        'Avg Daily (m³)': f"{plant_data.mean():,.0f}",
        'Total (m³)': f"{plant_data.sum():,.0f}",
        'Daily Growth': f"{daily_growth:+.1f}%" if plant_data.iloc[-2] != 0 else "N/A",
        'Total Growth': f"{total_growth:+.1f}%" if plant_data.iloc[0] != 0 else "N/A",
        'Status': '✅ Above Target' if daily_growth >= expected_daily_growth else '⚠️ Below Target'
    })

summary_df = pd.DataFrame(summary_data)

# Display styled table
st.dataframe(summary_df, use_container_width=True)

# REFRESH BUTTON
st.markdown("---")
col_refresh, col_space = st.columns([1, 3])

with col_refresh:
    if st.button("🔄 **Refresh Dashboard**", type="primary", use_container_width=True):
        st.rerun()

# FOOTER
st.markdown("""
<div class="footer">
    <div style="display: flex; align-items: center; justify-content: center; margin-bottom: 1rem;">
        <div style="font-size: 2.5rem; font-weight: 800; color: white; background: rgba(255,255,255,0.15); 
                    padding: 0.8rem 1.5rem; border-radius: 10px; border: 2px solid rgba(255,255,255,0.3);">
            KBRC
        </div>
    </div>
    <h3 style="color: white; margin: 0 0 0.5rem 0; font-weight: 600;">KUWAITI BRITISH READYMIX CO.</h3>
    <p style="color: rgba(255,255,255,0.9); margin: 0 0 0.5rem 0; font-size: 1.1rem;">
        Production Analytics Dashboard • Financial Grade Reporting
    </p>
    <p style="color: rgba(255,255,255,0.7); margin: 0; font-size: 0.9rem;">
        © 2025 KBRC • Established in 1980 • All Rights Reserved
    </p>
</div>
""", unsafe_allow_html=True)
