import os
import hashlib
import base64
import requests
import csv
from pathlib import Path
from datetime import datetime, timedelta, date, timezone
from typing import Dict, Any, Tuple, List, Optional
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import plotly.subplots as sp
import streamlit as st
import io
import xlsxwriter
import calendar
from dateutil.relativedelta import relativedelta
import json

# ========================================
# 1. ENTERPRISE PAGE CONFIGURATION
# ========================================
st.set_page_config(
    page_title="KBRC Executive Production Dashboard", 
    layout="wide", 
    page_icon="🏭",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'mailto:Ashwin.IT@kbrc.com.kw',
        'Report a bug': 'mailto:Ashwin.IT@kbrc.com.kw',
        'About': "Kuwait Building Readymix Company - Executive Production Dashboard v3.0"
    }
)

# ========================================
# 2. ENTERPRISE SESSION STATE MANAGEMENT
# ========================================
class SessionStateManager:
    """Centralized session state management"""
    @staticmethod
    def initialize():
        defaults = {
            "dark_mode": False,
            "theme": "executive_blue",
            "logged_in": False,
            "username": None,
            "selected_plant": "All Plants",
            "date_range": "last_30_days",
            "chart_style": "modern"
        }
        
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

SessionStateManager.initialize()

# ========================================
# 3. PROFESSIONAL CSS & THEMING SYSTEM
# ========================================
class ThemeManager:
    """Enterprise theming system with light/dark modes"""
    
    @staticmethod
    def get_current_theme():
        theme_name = st.session_state.get("theme", "executive_blue")
        is_dark = st.session_state.get("dark_mode", False)
        
        themes = {
            "executive_blue": {
                "light": {
                    "primary": "#1e3a8a",
                    "secondary": "#3b82f6",
                    "accent": "#10b981",
                    "background": "#f8fafc",
                    "surface": "#ffffff",
                    "text": "#1e293b",
                    "text_secondary": "#64748b",
                    "border": "#e2e8f0",
                    "success": "#10b981",
                    "warning": "#f59e0b",
                    "error": "#ef4444"
                },
                "dark": {
                    "primary": "#1e3a8a",
                    "secondary": "#3b82f6",
                    "accent": "#10b981",
                    "background": "#0f172a",
                    "surface": "#1e293b",
                    "text": "#f1f5f9",
                    "text_secondary": "#94a3b8",
                    "border": "#334155",
                    "success": "#10b981",
                    "warning": "#f59e0b",
                    "error": "#ef4444"
                }
            },
            "professional_green": {
                "light": {
                    "primary": "#065f46",
                    "secondary": "#10b981",
                    "accent": "#3b82f6",
                    "background": "#f0fdfa",
                    "surface": "#ffffff",
                    "text": "#064e3b",
                    "text_secondary": "#6b7280",
                    "border": "#d1d5db",
                    "success": "#10b981",
                    "warning": "#f59e0b",
                    "error": "#ef4444"
                },
                "dark": {
                    "primary": "#065f46",
                    "secondary": "#10b981",
                    "accent": "#3b82f6",
                    "background": "#111827",
                    "surface": "#1f2937",
                    "text": "#f9fafb",
                    "text_secondary": "#9ca3af",
                    "border": "#374151",
                    "success": "#10b981",
                    "warning": "#f59e0b",
                    "error": "#ef4444"
                }
            }
        }
        
        theme = themes.get(theme_name, themes["executive_blue"])
        return theme["dark"] if is_dark else theme["light"]
    
    @staticmethod
    def inject_css():
        """Inject professional, enterprise-grade CSS"""
        theme = ThemeManager.get_current_theme()
        
        css = f"""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
            
            /* Base Styling */
            html, body, [class*="css"], .stApp {{
                font-family: 'Inter', sans-serif;
                color: {theme['text']};
                background-color: {theme['background']};
            }}
            
            /* Hide Streamlit Branding */
            footer {{visibility: hidden !important;}}
            #MainMenu {{visibility: hidden;}}
            header {{visibility: hidden !important;}}
            .stAppDeployButton {{display: none !important;}}
            
            /* Sidebar Styling */
            [data-testid="stSidebar"] {{
                background-color: {theme['surface']};
                border-right: 1px solid {theme['border']};
            }}
            
            /* Professional Cards */
            .enterprise-card {{
                background: {theme['surface']};
                border: 1px solid {theme['border']};
                border-radius: 12px;
                padding: 24px;
                margin-bottom: 20px;
                transition: all 0.3s ease;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            }}
            
            .enterprise-card:hover {{
                box-shadow: 0 10px 25px rgba(0,0,0,0.1);
                border-color: {theme['secondary']};
            }}
            
            .enterprise-card .card-title {{
                font-size: 0.875rem;
                font-weight: 600;
                color: {theme['text_secondary']};
                text-transform: uppercase;
                letter-spacing: 0.05em;
                margin-bottom: 8px;
            }}
            
            .enterprise-card .card-value {{
                font-size: 2rem;
                font-weight: 700;
                color: {theme['text']};
                margin-bottom: 4px;
            }}
            
            .enterprise-card .card-subtitle {{
                font-size: 0.875rem;
                color: {theme['text_secondary']};
            }}
            
            /* Hero Banner */
            .hero-banner {{
                background: linear-gradient(135deg, {theme['primary']} 0%, {theme['secondary']} 100%);
                color: white;
                padding: 40px;
                border-radius: 16px;
                margin-bottom: 30px;
                box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
            }}
            
            /* Metric Highlight */
            .metric-highlight {{
                background: linear-gradient(135deg, {theme['success']}15 0%, {theme['accent']}15 100%);
                border-left: 4px solid {theme['success']};
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
            }}
            
            /* Status Indicator */
            .status-indicator {{
                display: inline-flex;
                align-items: center;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 0.75rem;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }}
            
            .status-online {{
                background-color: {theme['success']}20;
                color: {theme['success']};
            }}
            
            .status-warning {{
                background-color: {theme['warning']}20;
                color: {theme['warning']};
            }}
            
            .status-offline {{
                background-color: {theme['error']}20;
                color: {theme['error']};
            }}
            
            /* Table Styling */
            .data-table {{
                border-radius: 8px;
                overflow: hidden;
                border: 1px solid {theme['border']};
            }}
            
            /* Progress Bar */
            .progress-container {{
                height: 8px;
                background-color: {theme['border']};
                border-radius: 4px;
                overflow: hidden;
                margin: 8px 0;
            }}
            
            .progress-bar {{
                height: 100%;
                background: linear-gradient(90deg, {theme['secondary']}, {theme['accent']});
                border-radius: 4px;
            }}
            
            /* Button Enhancements */
            .stButton > button {{
                border-radius: 8px;
                font-weight: 600;
                transition: all 0.2s ease;
            }}
            
            .stButton > button:hover {{
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            }}
            
            /* Tab Styling */
            .stTabs [data-baseweb="tab-list"] {{
                gap: 8px;
                background-color: transparent;
            }}
            
            .stTabs [data-baseweb="tab"] {{
                border-radius: 8px;
                padding: 12px 24px;
                font-weight: 600;
                color: {theme['text_secondary']};
                border: 1px solid transparent;
            }}
            
            .stTabs [aria-selected="true"] {{
                background-color: {theme['surface']};
                border-color: {theme['border']};
                color: {theme['primary']};
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            }}
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)

ThemeManager.inject_css()

# ========================================
# 4. ENTERPRISE DATA MANAGEMENT
# ========================================
class DataManager:
    """Centralized data management system"""
    
    def __init__(self):
        self.DATA_DIR = Path("data")
        self.FORECAST_DIR = self.DATA_DIR / "forecasts"
        self.CONFIG_FILE = self.DATA_DIR / "config.json"
        self.setup_directories()
        
    def setup_directories(self):
        """Create necessary directories"""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.FORECAST_DIR.mkdir(parents=True, exist_ok=True)
    
    def save_config(self, config: Dict):
        """Save configuration to JSON"""
        with open(self.CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    
    def load_config(self) -> Dict:
        """Load configuration from JSON"""
        if self.CONFIG_FILE.exists():
            with open(self.CONFIG_FILE, 'r') as f:
                return json.load(f)
        return {}

# Initialize Data Manager
data_manager = DataManager()

# ========================================
# 5. AUTHENTICATION & SECURITY
# ========================================
class AuthManager:
    """Enterprise authentication system"""
    
    def __init__(self):
        self.LOG_FILE = data_manager.DATA_DIR / "audit_log.csv"
        self.setup_logs()
        
        # Load users from secrets/config
        self.users = self.load_users()
    
    def setup_logs(self):
        """Initialize audit logs"""
        if not self.LOG_FILE.exists():
            with open(self.LOG_FILE, 'w', newline='') as f:
                csv.writer(f).writerow(["timestamp", "user", "ip", "event", "details"])
    
    def load_users(self) -> Dict[str, str]:
        """Load users from configuration"""
        default_users = {
            "admin": hashlib.sha256("kbrc@2024".encode()).hexdigest(),
            "executive": hashlib.sha256("executive@kbrc".encode()).hexdigest(),
            "manager": hashlib.sha256("manager@kbrc".encode()).hexdigest(),
            "analyst": hashlib.sha256("analyst@kbrc".encode()).hexdigest()
        }
        
        # Load additional users from secrets
        try:
            secrets = dict(st.secrets)
            if "USERS" in secrets:
                default_users.update(secrets["USERS"])
        except:
            pass
        
        return default_users
    
    def authenticate(self, username: str, password: str) -> Tuple[bool, str]:
        """Authenticate user with audit logging"""
        if not username or not password:
            self.log_event("system", "AUTH_FAILED", "Empty credentials")
            return False, "Please enter credentials"
        
        if username in self.users:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            if password_hash == self.users[username]:
                self.log_event(username, "LOGIN_SUCCESS", "User authenticated")
                return True, "Authentication successful"
        
        self.log_event(username, "LOGIN_FAILED", "Invalid credentials")
        return False, "Invalid username or password"
    
    def log_event(self, user: str, event: str, details: str = ""):
        """Log security event"""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        # Note: In production, get actual IP from request
        ip_address = "127.0.0.1"
        
        with open(self.LOG_FILE, 'a', newline='') as f:
            csv.writer(f).writerow([timestamp, user, ip_address, event, details])

# Initialize Auth Manager
auth_manager = AuthManager()

# ========================================
# 6. UTILITY FUNCTIONS
# ========================================
class Utilities:
    """Collection of utility functions"""
    
    @staticmethod
    def get_kuwait_time() -> datetime:
        """Get current time in Kuwait (UTC+3)"""
        return datetime.now(timezone.utc) + timedelta(hours=3)
    
    @staticmethod
    def format_volume(value: float) -> str:
        """Format volume with appropriate unit"""
        if value >= 1000000:
            return f"{value/1000000:.2f}M m³"
        elif value >= 1000:
            return f"{value/1000:.2f}K m³"
        return f"{value:,.2f} m³"
    
    @staticmethod
    def format_currency(value: float) -> str:
        """Format currency value"""
        return f"KWD {value:,.2f}"
    
    @staticmethod
    def calculate_percentage_change(current: float, previous: float) -> Tuple[float, str]:
        """Calculate percentage change with trend indicator"""
        if previous == 0:
            return 0, "neutral"
        
        change = ((current - previous) / previous) * 100
        
        if change > 5:
            trend = "positive"
        elif change < -5:
            trend = "negative"
        else:
            trend = "neutral"
        
        return change, trend
    
    @staticmethod
    def get_date_ranges() -> Dict[str, Tuple[date, date]]:
        """Get predefined date ranges"""
        today = Utilities.get_kuwait_time().date()
        
        return {
            "today": (today, today),
            "yesterday": (today - timedelta(days=1), today - timedelta(days=1)),
            "last_7_days": (today - timedelta(days=7), today),
            "last_30_days": (today - timedelta(days=30), today),
            "this_month": (today.replace(day=1), today),
            "last_month": (
                (today.replace(day=1) - timedelta(days=1)).replace(day=1),
                today.replace(day=1) - timedelta(days=1)
            ),
            "this_quarter": (
                today.replace(month=((today.month-1)//3)*3+1, day=1),
                today
            )
        }

# ========================================
# 7. FORECAST MANAGEMENT SYSTEM
# ========================================
class ForecastManager:
    """Enterprise forecast management system"""
    
    def __init__(self):
        self.forecast_dir = data_manager.FORECAST_DIR
    
    def save_forecast(self, year: int, month: int, value: float) -> Tuple[bool, str]:
        """Save monthly forecast"""
        try:
            file_path = self.forecast_dir / f"forecast_{year}_{month:02d}.json"
            forecast_data = {
                "year": year,
                "month": month,
                "value": value,
                "updated_at": Utilities.get_kuwait_time().isoformat(),
                "updated_by": st.session_state.get("username", "system")
            }
            
            with open(file_path, 'w') as f:
                json.dump(forecast_data, f, indent=2)
            
            return True, "Forecast saved successfully"
        except Exception as e:
            return False, f"Error saving forecast: {str(e)}"
    
    def get_forecast(self, year: int, month: int) -> float:
        """Get monthly forecast"""
        try:
            file_path = self.forecast_dir / f"forecast_{year}_{month:02d}.json"
            if file_path.exists():
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    return data.get("value", 0.0)
        except:
            pass
        return 0.0
    
    def get_all_forecasts(self) -> List[Dict]:
        """Get all available forecasts"""
        forecasts = []
        for file_path in self.forecast_dir.glob("forecast_*.json"):
            try:
                with open(file_path, 'r') as f:
                    forecasts.append(json.load(f))
            except:
                continue
        return sorted(forecasts, key=lambda x: (x["year"], x["month"]), reverse=True)

# Initialize Forecast Manager
forecast_manager = ForecastManager()

# ========================================
# 8. DATA PROCESSING ENGINE
# ========================================
class DataProcessor:
    """Data processing and analysis engine"""
    
    @staticmethod
    def process_uploaded_file(uploaded_file, selected_date: date) -> pd.DataFrame:
        """Process uploaded Excel file"""
        try:
            df = pd.read_excel(uploaded_file)
            
            # Standardize column names
            df.columns = [col.strip().title() for col in df.columns]
            
            # Required columns
            required = ["Plant", "Production For The Day", "Accumulative Production"]
            
            # Check required columns
            missing = [col for col in required if col not in df.columns]
            if missing:
                raise ValueError(f"Missing required columns: {missing}")
            
            # Add date column
            df["Date"] = selected_date
            
            # Convert numeric columns
            df["Production For The Day"] = pd.to_numeric(df["Production For The Day"], errors="coerce")
            df["Accumulative Production"] = pd.to_numeric(df["Accumulative Production"], errors="coerce")
            
            return df
            
        except Exception as e:
            raise ValueError(f"Error processing file: {str(e)}")
    
    @staticmethod
    def analyze_daily_data(df: pd.DataFrame) -> Dict:
        """Analyze daily production data"""
        analysis = {
            "total_production": df["Production For The Day"].sum(),
            "average_production": df["Production For The Day"].mean(),
            "top_plant": df.loc[df["Production For The Day"].idxmax(), "Plant"] if not df.empty else "N/A",
            "top_value": df["Production For The Day"].max() if not df.empty else 0,
            "plant_count": df["Plant"].nunique(),
            "data_points": len(df)
        }
        return analysis
    
    @staticmethod
    def generate_insights(df: pd.DataFrame, forecast: float = 0) -> List[str]:
        """Generate business insights"""
        insights = []
        
        if df.empty:
            return ["No data available for analysis"]
        
        total = df["Production For The Day"].sum()
        avg = df["Production For The Day"].mean()
        
        # Basic insights
        insights.append(f"**Total Production:** {Utilities.format_volume(total)}")
        
        if forecast > 0:
            variance = total - forecast
            variance_pct = (variance / forecast * 100) if forecast > 0 else 0
            if variance > 0:
                insights.append(f"**Above Forecast:** +{Utilities.format_volume(abs(variance))} ({variance_pct:.1f}%)")
            else:
                insights.append(f"**Below Forecast:** -{Utilities.format_volume(abs(variance))} ({abs(variance_pct):.1f}%)")
        
        # Top performer insight
        top_plant = df.loc[df["Production For The Day"].idxmax()]
        insights.append(f"**Top Performer:** {top_plant['Plant']} ({Utilities.format_volume(top_plant['Production For The Day'])})")
        
        # Efficiency insight
        if avg > 0:
            insights.append(f"**Average Plant Output:** {Utilities.format_volume(avg)}")
        
        return insights

# ========================================
# 9. VISUALIZATION ENGINE
# ========================================
class VisualizationEngine:
    """Professional visualization engine"""
    
    @staticmethod
    def create_metric_card(title: str, value: str, subtitle: str = "", trend: str = "neutral"):
        """Create a professional metric card"""
        theme = ThemeManager.get_current_theme()
        
        if trend == "positive":
            trend_icon = "📈"
            trend_color = theme["success"]
        elif trend == "negative":
            trend_icon = "📉"
            trend_color = theme["error"]
        else:
            trend_icon = "📊"
            trend_color = theme["text_secondary"]
        
        html = f"""
        <div class="enterprise-card">
            <div class="card-title">{title}</div>
            <div class="card-value">{trend_icon} {value}</div>
            <div class="card-subtitle" style="color: {trend_color}">{subtitle}</div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)
    
    @staticmethod
    def create_production_chart(df: pd.DataFrame, title: str = "Production Overview"):
        """Create production chart"""
        theme = ThemeManager.get_current_theme()
        
        fig = go.Figure()
        
        # Add bar chart for daily production
        fig.add_trace(go.Bar(
            x=df["Date"],
            y=df["Total Production"],
            name="Daily Production",
            marker_color=theme["secondary"],
            opacity=0.8
        ))
        
        # Add line for trend
        if len(df) > 1:
            fig.add_trace(go.Scatter(
                x=df["Date"],
                y=df["Total Production"].rolling(window=3, center=True).mean(),
                name="Trend",
                mode="lines",
                line=dict(color=theme["accent"], width=3),
                opacity=0.7
            ))
        
        fig.update_layout(
            title=dict(
                text=title,
                font=dict(size=18, color=theme["text"])
            ),
            xaxis=dict(
                title="Date",
                gridcolor=theme["border"],
                tickformat="%b %d"
            ),
            yaxis=dict(
                title="Production Volume (m³)",
                gridcolor=theme["border"]
            ),
            plot_bgcolor=theme["surface"],
            paper_bgcolor=theme["background"],
            font=dict(color=theme["text"]),
            hovermode="x unified",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        return fig
    
    @staticmethod
    def create_performance_chart(plant_data: pd.DataFrame):
        """Create plant performance comparison chart"""
        theme = ThemeManager.get_current_theme()
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=plant_data["Plant"],
            y=plant_data["Production"],
            name="Production",
            marker_color=theme["secondary"],
            text=plant_data["Production"].apply(lambda x: f"{x:,.0f}"),
            textposition="outside"
        ))
        
        fig.update_layout(
            title=dict(
                text="Plant Performance Comparison",
                font=dict(size=18, color=theme["text"])
            ),
            xaxis=dict(
                title="Plant",
                tickangle=45
            ),
            yaxis=dict(
                title="Production Volume (m³)",
                gridcolor=theme["border"]
            ),
            plot_bgcolor=theme["surface"],
            paper_bgcolor=theme["background"],
            font=dict(color=theme["text"]),
            showlegend=False
        )
        
        return fig

# ========================================
# 10. ENTERPRISE LOGIN SCREEN
# ========================================
def render_login_screen():
    """Render professional login screen"""
    
    # Create centered layout
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<div style='height: 80px;'></div>", unsafe_allow_html=True)
        
        # Login Card
        theme = ThemeManager.get_current_theme()
        
        st.markdown(f"""
        <div style="
            background: {theme['surface']};
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.1);
            border: 1px solid {theme['border']};
            text-align: center;
        ">
            <div style="margin-bottom: 30px;">
                <h1 style="
                    color: {theme['primary']};
                    font-size: 2rem;
                    font-weight: 700;
                    margin-bottom: 8px;
                ">KBRC</h1>
                <p style="
                    color: {theme['text_secondary']};
                    font-size: 0.9rem;
                    letter-spacing: 3px;
                    text-transform: uppercase;
                    margin-bottom: 30px;
                ">EXECUTIVE DASHBOARD</p>
            </div>
            
            <div style="
                background: linear-gradient(135deg, {theme['primary']}15 0%, {theme['secondary']}15 100%);
                border-radius: 12px;
                padding: 20px;
                margin-bottom: 30px;
            ">
                <p style="
                    color: {theme['text']};
                    font-size: 0.9rem;
                    margin: 0;
                ">Secure access to production analytics and management</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Login Form
        with st.form("login_form"):
            username = st.text_input(
                "Username",
                placeholder="Enter your username"
            )
            
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password"
            )
            
            submit = st.form_submit_button(
                "Access Dashboard",
                type="primary",
                use_container_width=True
            )
            
            if submit:
                authenticated, message = auth_manager.authenticate(username, password)
                if authenticated:
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = username
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error(message)
        
        # Footer
        st.markdown("""
        <div style="
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e2e8f0;
            text-align: center;
        ">
            <p style="
                color: #64748b;
                font-size: 0.8rem;
                margin: 0;
            ">
                Need assistance? Contact IT Support
            </p>
        </div>
        """, unsafe_allow_html=True)

# ========================================
# 11. MAIN APPLICATION
# ========================================

# Check authentication
if not st.session_state.get("logged_in", False):
    render_login_screen()
    st.stop()

# ========================================
# 12. SIDEBAR CONFIGURATION
# ========================================
with st.sidebar:
    # User Profile Section
    theme = ThemeManager.get_current_theme()
    
    st.markdown(f"""
    <div style="
        padding: 20px;
        border-radius: 12px;
        background: {theme['surface']};
        border: 1px solid {theme['border']};
        margin-bottom: 20px;
    ">
        <div style="
            display: flex;
            align-items: center;
            margin-bottom: 16px;
        ">
            <div style="
                width: 40px;
                height: 40px;
                border-radius: 50%;
                background: linear-gradient(135deg, {theme['primary']}, {theme['secondary']});
                display: flex;
                align-items: center;
                justify-content: center;
                margin-right: 12px;
                color: white;
                font-weight: 600;
            ">
                {st.session_state['username'][0].upper()}
            </div>
            <div>
                <div style="
                    color: {theme['text']};
                    font-weight: 600;
                    font-size: 1rem;
                ">
                    {st.session_state['username'].title()}
                </div>
                <div style="
                    color: {theme['text_secondary']};
                    font-size: 0.8rem;
                ">
                    {Utilities.get_kuwait_time().strftime('%I:%M %p')}
                </div>
            </div>
        </div>
        
        <div style="display: flex; align-items: center;">
            <span class="status-indicator status-online">Online</span>
            <div style="flex-grow: 1;"></div>
            <span style="
                color: {theme['text_secondary']};
                font-size: 0.8rem;
            ">
                Kuwait Time
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Navigation
    st.markdown("### Navigation")
    
    # Define navigation based on user role
    user_role = st.session_state["username"]
    
    if user_role == "admin":
        pages = ["Dashboard", "Production Analytics", "Forecast Management", 
                "Data Management", "User Management", "System Settings", "Audit Logs"]
    elif user_role == "executive":
        pages = ["Dashboard", "Production Analytics", "Forecast Management", "Reports"]
    elif user_role == "manager":
        pages = ["Dashboard", "Production Analytics", "Data Upload", "Forecast Management"]
    else:
        pages = ["Dashboard", "Production Analytics"]
    
    selected_page = st.radio(
        "",
        pages,
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    # Quick Stats
    st.markdown("### Quick Stats")
    
    # Placeholder for quick stats - in production, these would be loaded from data
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Today's Target", "25,000 m³")
    with col2:
        st.metric("Achieved", "23,456 m³", "-6.2%")
    
    st.markdown("---")
    
    # Theme Controls
    st.markdown("### Appearance")
    
    col1, col2 = st.columns(2)
    with col1:
        dark_mode = st.toggle("Dark Mode", value=st.session_state.get("dark_mode", False))
        if dark_mode != st.session_state.get("dark_mode"):
            st.session_state["dark_mode"] = dark_mode
            st.rerun()
    
    with col2:
        theme_option = st.selectbox(
            "Theme",
            ["Executive Blue", "Professional Green"],
            index=0 if st.session_state.get("theme") == "executive_blue" else 1,
            label_visibility="collapsed"
        )
        theme_key = "executive_blue" if theme_option == "Executive Blue" else "professional_green"
        if theme_key != st.session_state.get("theme"):
            st.session_state["theme"] = theme_key
            st.rerun()
    
    st.markdown("---")
    
    # Logout Button
    if st.button("Logout", use_container_width=True):
        auth_manager.log_event(st.session_state["username"], "LOGOUT", "User logged out")
        st.session_state.clear()
        st.rerun()
    
    # Footer
    st.markdown("""
    <div style="
        margin-top: 40px;
        padding-top: 20px;
        border-top: 1px solid #e2e8f0;
    ">
        <p style="
            color: #64748b;
            font-size: 0.75rem;
            margin: 0 0 8px 0;
        ">
            <strong>Kuwait Building Readymix Co.</strong>
        </p>
        <p style="
            color: #64748b;
            font-size: 0.7rem;
            margin: 0;
            line-height: 1.4;
        ">
            Version 3.0 • © 2024 KBRC<br>
            IT Support: Ashwin.IT@kbrc.com.kw
        </p>
    </div>
    """, unsafe_allow_html=True)

# ========================================
# 13. PAGE ROUTING
# ========================================

# Re-inject CSS after theme changes
ThemeManager.inject_css()

if selected_page == "Dashboard":
    # Dashboard Page
    st.title("Executive Dashboard")
    
    # Welcome Message
    current_time = Utilities.get_kuwait_time()
    greeting = "Good Morning" if current_time.hour < 12 else "Good Afternoon" if current_time.hour < 18 else "Good Evening"
    
    st.markdown(f"""
    <div style="margin-bottom: 30px;">
        <h1 style="font-size: 2.5rem; margin-bottom: 8px;">{greeting}, {st.session_state['username'].title()}!</h1>
        <p style="color: #64748b; font-size: 1.1rem;">
            Welcome to the KBRC Executive Production Dashboard
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # KPI Cards
    st.markdown("### Key Performance Indicators")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        VisualizationEngine.create_metric_card(
            "Total Production",
            "245,678 m³",
            "↑ 12.5% from last month",
            "positive"
        )
    
    with col2:
        VisualizationEngine.create_metric_card(
            "Daily Average",
            "8,189 m³",
            "↓ 3.2% from target",
            "negative"
        )
    
    with col3:
        VisualizationEngine.create_metric_card(
            "Plant Efficiency",
            "94.2%",
            "Within optimal range",
            "neutral"
        )
    
    with col4:
        VisualizationEngine.create_metric_card(
            "Forecast Variance",
            "+2.3%",
            "Above monthly target",
            "positive"
        )
    
    # Charts Section
    st.markdown("### Production Overview")
    
    # Sample data for demonstration
    dates = pd.date_range(end=current_time, periods=30, freq='D')
    sample_data = pd.DataFrame({
        'Date': dates,
        'Total Production': np.random.randint(7000, 9000, 30) + np.random.randn(30) * 500
    })
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Production Trend Chart
        fig = VisualizationEngine.create_production_chart(sample_data, "30-Day Production Trend")
        st.plotly_chart(fig, use_container
