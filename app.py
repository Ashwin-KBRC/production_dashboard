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
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Plant Performance
        plant_data = pd.DataFrame({
            'Plant': ['Plant A', 'Plant B', 'Plant C', 'Plant D', 'Plant E'],
            'Production': np.random.randint(1500, 3000, 5)
        })
        
        st.markdown("#### Top Performing Plants")
        for _, row in plant_data.iterrows():
            st.metric(row['Plant'], Utilities.format_volume(row['Production']))
        
        st.markdown("---")
        st.markdown("#### System Status")
        st.markdown("✅ **All systems operational**")
        st.markdown("📊 **Data updated:** Today, 08:00")
        st.markdown("🔒 **Security:** High")
    
    # Recent Activity
    st.markdown("### Recent Activity")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="enterprise-card">
            <div class="card-title">Latest Data Upload</div>
            <div class="card-value">Today, 07:45</div>
            <div class="card-subtitle">By Production Manager</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="enterprise-card">
            <div class="card-title">Next Forecast Review</div>
            <div class="card-value">Tomorrow, 10:00</div>
            <div class="card-subtitle">Monthly Planning Meeting</div>
        </div>
        """, unsafe_allow_html=True)

elif selected_page == "Production Analytics":
    st.title("Production Analytics")
    
    # Date Range Selector
    date_ranges = Utilities.get_date_ranges()
    selected_range = st.selectbox(
        "Select Date Range",
        list(date_ranges.keys()),
        format_func=lambda x: x.replace("_", " ").title(),
        index=3  # Default to last_30_days
    )
    
    start_date, end_date = date_ranges[selected_range]
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=start_date)
    with col2:
        end_date = st.date_input("End Date", value=end_date)
    
    # Filter Options
    st.markdown("### Filters")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        plants = ["All Plants", "Plant A", "Plant B", "Plant C", "Plant D", "Plant E"]
        selected_plant = st.selectbox("Plant", plants)
    
    with col2:
        metrics = ["Production Volume", "Efficiency", "Target Achievement", "Cost Analysis"]
        selected_metric = st.selectbox("Metric", metrics)
    
    with col3:
        chart_types = ["Line Chart", "Bar Chart", "Area Chart", "Scatter Plot"]
        chart_type = st.selectbox("Chart Type", chart_types)
    
    # Analytics Dashboard
    st.markdown("### Analytics Dashboard")
    
    # Sample Analytics Data
    analytics_dates = pd.date_range(start=start_date, end=end_date, freq='D')
    analytics_data = pd.DataFrame({
        'Date': analytics_dates,
        'Production': np.random.randint(7000, 9000, len(analytics_dates)) + np.random.randn(len(analytics_dates)) * 500,
        'Target': np.full(len(analytics_dates), 8500),
        'Efficiency': np.random.uniform(0.85, 0.98, len(analytics_dates))
    })
    
    # KPI Cards for Analytics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_production = analytics_data['Production'].sum()
        VisualizationEngine.create_metric_card(
            "Total Production",
            Utilities.format_volume(total_production),
            f"{len(analytics_data)} days"
        )
    
    with col2:
        avg_production = analytics_data['Production'].mean()
        target_avg = analytics_data['Target'].mean()
        variance_pct = ((avg_production - target_avg) / target_avg * 100)
        
        VisualizationEngine.create_metric_card(
            "Average Daily",
            Utilities.format_volume(avg_production),
            f"{variance_pct:+.1f}% vs target",
            "positive" if variance_pct >= 0 else "negative"
        )
    
    with col3:
        avg_efficiency = analytics_data['Efficiency'].mean() * 100
        VisualizationEngine.create_metric_card(
            "Average Efficiency",
            f"{avg_efficiency:.1f}%",
            "Industry avg: 92%",
            "positive" if avg_efficiency >= 92 else "negative"
        )
    
    # Main Analytics Chart
    st.markdown("#### Production Trend")
    
    fig = go.Figure()
    
    # Add actual production
    fig.add_trace(go.Scatter(
        x=analytics_data['Date'],
        y=analytics_data['Production'],
        mode='lines+markers',
        name='Actual Production',
        line=dict(color='#3b82f6', width=3),
        marker=dict(size=6)
    ))
    
    # Add target line
    fig.add_trace(go.Scatter(
        x=analytics_data['Date'],
        y=analytics_data['Target'],
        mode='lines',
        name='Daily Target',
        line=dict(color='#ef4444', width=2, dash='dash')
    ))
    
    # Apply theme
    theme = ThemeManager.get_current_theme()
    fig.update_layout(
        title=dict(
            text=f"Production Analysis: {start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}",
            font=dict(size=16, color=theme['text'])
        ),
        xaxis=dict(
            title="Date",
            gridcolor=theme['border'],
            tickformat="%b %d"
        ),
        yaxis=dict(
            title="Production Volume (m³)",
            gridcolor=theme['border']
        ),
        plot_bgcolor=theme['surface'],
        paper_bgcolor=theme['background'],
        font=dict(color=theme['text']),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Additional Analytics
    st.markdown("#### Detailed Analysis")
    
    tab1, tab2, tab3 = st.tabs(["Performance Metrics", "Plant Comparison", "Forecast Analysis"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            # Efficiency Distribution
            fig_eff = px.histogram(
                analytics_data, 
                x='Efficiency',
                title="Efficiency Distribution",
                nbins=20,
                color_discrete_sequence=[theme['secondary']]
            )
            fig_eff.update_layout(
                plot_bgcolor=theme['surface'],
                paper_bgcolor=theme['background'],
                font=dict(color=theme['text'])
            )
            st.plotly_chart(fig_eff, use_container_width=True)
        
        with col2:
            # Daily Variance
            analytics_data['Variance'] = analytics_data['Production'] - analytics_data['Target']
            fig_var = px.bar(
                analytics_data,
                x='Date',
                y='Variance',
                title="Daily Target Variance",
                color=analytics_data['Variance'] >= 0,
                color_discrete_map={True: theme['success'], False: theme['error']}
            )
            fig_var.update_layout(
                plot_bgcolor=theme['surface'],
                paper_bgcolor=theme['background'],
                font=dict(color=theme['text']),
                showlegend=False
            )
            st.plotly_chart(fig_var, use_container_width=True)
    
    with tab2:
        # Plant comparison (sample data)
        plant_comparison = pd.DataFrame({
            'Plant': ['Plant A', 'Plant B', 'Plant C', 'Plant D', 'Plant E'],
            'Production': np.random.randint(1500, 3000, 5),
            'Efficiency': np.random.uniform(0.85, 0.98, 5),
            'Uptime': np.random.uniform(0.92, 0.99, 5)
        })
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig_plant = px.bar(
                plant_comparison,
                x='Plant',
                y='Production',
                title="Production by Plant",
                color='Plant',
                text_auto='.2s'
            )
            fig_plant.update_layout(
                plot_bgcolor=theme['surface'],
                paper_bgcolor=theme['background'],
                font=dict(color=theme['text'])
            )
            st.plotly_chart(fig_plant, use_container_width=True)
        
        with col2:
            fig_eff_plant = px.bar(
                plant_comparison,
                x='Plant',
                y='Efficiency',
                title="Efficiency by Plant",
                color='Plant',
                text_auto='.1%'
            )
            fig_eff_plant.update_layout(
                plot_bgcolor=theme['surface'],
                paper_bgcolor=theme['background'],
                font=dict(color=theme['text'])
            )
            st.plotly_chart(fig_eff_plant, use_container_width=True)
    
    with tab3:
        # Forecast analysis
        current_month = current_time.month
        current_year = current_time.year
        
        # Get current month forecast
        current_forecast = forecast_manager.get_forecast(current_year, current_month)
        days_so_far = current_time.day
        expected_so_far = (current_forecast / calendar.monthrange(current_year, current_month)[1]) * days_so_far
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            VisualizationEngine.create_metric_card(
                "Monthly Forecast",
                Utilities.format_volume(current_forecast),
                f"{calendar.month_name[current_month]} {current_year}"
            )
        
        with col2:
            VisualizationEngine.create_metric_card(
                "Expected to Date",
                Utilities.format_volume(expected_so_far),
                f"{days_so_far} days elapsed"
            )
        
        with col3:
            # Calculate actual vs expected (using sample data)
            actual_so_far = analytics_data['Production'].sum() / len(analytics_data) * days_so_far
            variance = actual_so_far - expected_so_far
            variance_pct = (variance / expected_so_far * 100) if expected_so_far > 0 else 0
            
            VisualizationEngine.create_metric_card(
                "Variance",
                f"{variance_pct:+.1f}%",
                f"{Utilities.format_volume(abs(variance))} {'above' if variance >= 0 else 'below'}",
                "positive" if variance >= 0 else "negative"
            )

elif selected_page == "Forecast Management":
    st.title("Forecast Management")
    
    # Current Forecast Overview
    current_time = Utilities.get_kuwait_time()
    current_forecast = forecast_manager.get_forecast(current_time.year, current_time.month)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"""
        <div class="enterprise-card">
            <div class="card-title">Current Month Forecast</div>
            <div class="card-value">{Utilities.format_volume(current_forecast)}</div>
            <div class="card-subtitle">{calendar.month_name[current_time.month]} {current_time.year}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        days_in_month = calendar.monthrange(current_time.year, current_time.month)[1]
        daily_target = current_forecast / days_in_month if days_in_month > 0 else 0
        
        st.markdown(f"""
        <div class="enterprise-card">
            <div class="card-title">Daily Target</div>
            <div class="card-value">{Utilities.format_volume(daily_target)}</div>
            <div class="card-subtitle">{days_in_month} days in month</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Forecast Management
    st.markdown("### Manage Forecasts")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Year selection
        years = [current_time.year - 1, current_time.year, current_time.year + 1]
        selected_year = st.selectbox("Select Year", years, index=1)
    
    with col2:
        # Month selection
        months = list(calendar.month_name)[1:]  # Skip empty first element
        selected_month = st.selectbox("Select Month", months, index=current_time.month - 1)
    
    # Get current forecast for selected month
    month_number = list(calendar.month_name).index(selected_month)
    existing_forecast = forecast_manager.get_forecast(selected_year, month_number)
    
    # Forecast Input
    st.markdown("#### Set Forecast Value")
    
    forecast_value = st.number_input(
        "Monthly Forecast Volume (m³)",
        min_value=0.0,
        value=float(existing_forecast) if existing_forecast > 0 else 0.0,
        step=1000.0,
        format="%.2f"
    )
    
    if st.button("Save Forecast", type="primary", use_container_width=True):
        if forecast_value > 0:
            success, message = forecast_manager.save_forecast(selected_year, month_number, forecast_value)
            if success:
                st.success(f"Forecast saved successfully for {selected_month} {selected_year}")
                st.rerun()
            else:
                st.error(message)
        else:
            st.warning("Please enter a forecast value greater than 0")
    
    # Existing Forecasts
    st.markdown("### Existing Forecasts")
    
    forecasts = forecast_manager.get_all_forecasts()
    
    if forecasts:
        forecast_df = pd.DataFrame(forecasts)
        forecast_df['Month_Name'] = forecast_df['month'].apply(lambda x: calendar.month_name[x])
        forecast_df['Date'] = pd.to_datetime(forecast_df[['year', 'month']].assign(day=1))
        forecast_df = forecast_df.sort_values('Date', ascending=False)
        
        # Display as cards
        for _, forecast in forecast_df.head(10).iterrows():
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                st.write(f"**{forecast['Month_Name']} {forecast['year']}**")
            
            with col2:
                st.write(f"{Utilities.format_volume(forecast['value'])}")
            
            with col3:
                if st.button("Edit", key=f"edit_{forecast['year']}_{forecast['month']}"):
                    st.session_state['edit_forecast'] = forecast
                    st.rerun()
        
        # Show all in a table
        with st.expander("View All Forecasts"):
            display_df = forecast_df[['year', 'month', 'value', 'updated_at', 'updated_by']].copy()
            display_df['month'] = display_df['month'].apply(lambda x: calendar.month_name[x])
            display_df['value'] = display_df['value'].apply(Utilities.format_volume)
            st.dataframe(display_df, use_container_width=True)
    else:
        st.info("No forecasts have been created yet.")

elif selected_page == "Data Upload":
    st.title("Data Upload")
    
    # Upload Section
    st.markdown("### Upload Daily Production Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Date selection
        upload_date = st.date_input(
            "Production Date",
            value=Utilities.get_kuwait_time().date()
        )
    
    with col2:
        # File upload
        uploaded_file = st.file_uploader(
            "Choose Excel file",
            type=["xlsx", "xls"],
            help="Upload Excel file with production data"
        )
    
    # Template Download
    st.markdown("---")
    st.markdown("### Need a Template?")
    
    # Create sample template
    template_data = pd.DataFrame({
        'Plant': ['Plant A', 'Plant B', 'Plant C', 'Plant D'],
        'Production For The Day': [2500.50, 1800.75, 2200.25, 1950.00],
        'Accumulative Production': [52500.50, 41800.75, 52200.25, 39500.00]
    })
    
    # Convert to Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        template_data.to_excel(writer, sheet_name='Production Data', index=False)
        
        # Get workbook and worksheet
        workbook = writer.book
        worksheet = writer.sheets['Production Data']
        
        # Add formatting
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#1e3a8a',
            'font_color': 'white',
            'border': 1
        })
        
        # Write headers
        for col_num, value in enumerate(template_data.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # Set column widths
        worksheet.set_column('A:A', 15)
        worksheet.set_column('B:C', 25)
    
    output.seek(0)
    
    # Download button
    st.download_button(
        label="Download Template",
        data=output,
        file_name="KBRC_Production_Template.xlsx",
        mime="application/vnd.ms-excel",
        use_container_width=True
    )
    
    # Process uploaded file
    if uploaded_file is not None:
        st.markdown("---")
        st.markdown("### File Preview & Validation")
        
        try:
            # Process the file
            df = DataProcessor.process_uploaded_file(uploaded_file, upload_date)
            
            # Display preview
            st.success("✅ File validated successfully!")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### Data Preview")
                st.dataframe(df.head(), use_container_width=True)
            
            with col2:
                st.markdown("#### Data Summary")
                analysis = DataProcessor.analyze_daily_data(df)
                
                st.metric("Total Production", Utilities.format_volume(analysis['total_production']))
                st.metric("Number of Plants", analysis['plant_count'])
                st.metric("Top Plant", analysis['top_plant'])
                st.metric("Top Plant Production", Utilities.format_volume(analysis['top_value']))
            
            # Generate insights
            st.markdown("#### Insights")
            insights = DataProcessor.generate_insights(df)
            for insight in insights:
                st.markdown(f"- {insight}")
            
            # Save data
            st.markdown("---")
            st.markdown("### Save to Database")
            
            if st.button("Save Data", type="primary", use_container_width=True):
                # Save file
                filename = f"{upload_date.strftime('%Y-%m-%d')}.xlsx"
                filepath = data_manager.DATA_DIR / filename
                
                df.to_excel(filepath, index=False)
                
                # Log the event
                auth_manager.log_event(
                    st.session_state['username'],
                    "DATA_UPLOAD",
                    f"Uploaded production data for {upload_date}"
                )
                
                st.success(f"✅ Data saved successfully for {upload_date}")
                st.balloons()
                
        except Exception as e:
            st.error(f"❌ Error processing file: {str(e)}")

elif selected_page == "Data Management":
    st.title("Data Management")
    
    # List existing data files
    data_files = list(data_manager.DATA_DIR.glob("*.xlsx"))
    
    if not data_files:
        st.info("No data files found in the system.")
    else:
        st.markdown(f"### Found {len(data_files)} Data Files")
        
        # Create a DataFrame of files
        files_data = []
        for file_path in data_files:
            try:
                # Extract date from filename
                date_str = file_path.stem
                file_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                
                # Get file info
                size_kb = file_path.stat().st_size / 1024
                
                files_data.append({
                    "Date": file_date,
                    "Filename": file_path.name,
                    "Size (KB)": f"{size_kb:.1f}",
                    "Path": str(file_path)
                })
            except:
                continue
        
        if files_data:
            files_df = pd.DataFrame(files_data)
            files_df = files_df.sort_values("Date", ascending=False)
            
            # Display table
            st.dataframe(
                files_df[["Date", "Filename", "Size (KB)"]],
                use_container_width=True,
                hide_index=True
            )
            
            # File operations
            st.markdown("### File Operations")
            
            selected_file = st.selectbox(
                "Select a file to manage",
                files_df["Filename"].tolist()
            )
            
            if selected_file:
                file_path = data_manager.DATA_DIR / selected_file
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("View Data", use_container_width=True):
                        try:
                            df = pd.read_excel(file_path)
                            st.dataframe(df, use_container_width=True)
                        except Exception as e:
                            st.error(f"Error reading file: {e}")
                
                with col2:
                    # Download button
                    with open(file_path, "rb") as f:
                        file_data = f.read()
                    
                    st.download_button(
                        label="Download",
                        data=file_data,
                        file_name=selected_file,
                        mime="application/vnd.ms-excel",
                        use_container_width=True
                    )
                
                with col3:
                    if st.button("Delete", type="secondary", use_container_width=True):
                        # Confirm deletion
                        if st.checkbox("Confirm deletion"):
                            file_path.unlink()
                            auth_manager.log_event(
                                st.session_state['username'],
                                "DATA_DELETE",
                                f"Deleted file: {selected_file}"
                            )
                            st.success(f"Deleted {selected_file}")
                            st.rerun()

elif selected_page == "Audit Logs":
    if st.session_state['username'] not in ['admin', 'manager']:
        st.error("Access denied. This section requires administrative privileges.")
        st.stop()
    
    st.title("Security Audit Logs")
    
    # Date filter
    col1, col2 = st.columns(2)
    
    with col1:
        log_start_date = st.date_input("Start Date", value=Utilities.get_kuwait_time().date() - timedelta(days=7))
    
    with col2:
        log_end_date = st.date_input("End Date", value=Utilities.get_kuwait_time().date())
    
    # Load logs
    log_file = data_manager.DATA_DIR / "audit_log.csv"
    
    if log_file.exists():
        logs_df = pd.read_csv(log_file)
        logs_df['timestamp'] = pd.to_datetime(logs_df['timestamp'])
        
        # Filter by date
        mask = (logs_df['timestamp'].dt.date >= log_start_date) & (logs_df['timestamp'].dt.date <= log_end_date)
        filtered_logs = logs_df[mask].copy()
        
        # Sort by timestamp
        filtered_logs = filtered_logs.sort_values('timestamp', ascending=False)
        
        # Display stats
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Events", len(filtered_logs))
        
        with col2:
            unique_users = filtered_logs['user'].nunique()
            st.metric("Unique Users", unique_users)
        
        with col3:
            failed_logins = len(filtered_logs[filtered_logs['event'] == 'LOGIN_FAILED'])
            st.metric("Failed Logins", failed_logins)
        
        with col4:
            success_logins = len(filtered_logs[filtered_logs['event'] == 'LOGIN_SUCCESS'])
            st.metric("Successful Logins", success_logins)
        
        # Display logs
        st.markdown("### Audit Trail")
        
        # Event type filter
        event_types = filtered_logs['event'].unique()
        selected_events = st.multiselect(
            "Filter by Event Type",
            event_types,
            default=event_types[:5] if len(event_types) > 0 else []
        )
        
        if selected_events:
            filtered_logs = filtered_logs[filtered_logs['event'].isin(selected_events)]
        
        # Display table
        display_cols = ['timestamp', 'user', 'event', 'details']
        st.dataframe(
            filtered_logs[display_cols],
            use_container_width=True,
            column_config={
                'timestamp': st.column_config.DatetimeColumn(
                    "Timestamp",
                    format="YYYY-MM-DD HH:mm:ss"
                ),
                'user': "User",
                'event': "Event",
                'details': "Details"
            }
        )
        
        # Export option
        csv_data = filtered_logs.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Export as CSV",
            data=csv_data,
            file_name=f"audit_logs_{log_start_date}_{log_end_date}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.info("No audit logs found.")

elif selected_page == "System Settings":
    if st.session_state['username'] != 'admin':
        st.error("Access denied. Admin privileges required.")
        st.stop()
    
    st.title("System Settings")
    
    tab1, tab2, tab3 = st.tabs(["General", "Security", "Integration"])
    
    with tab1:
        st.markdown("### General Settings")
        
        # System name
        system_name = st.text_input(
            "System Name",
            value="KBRC Production Dashboard",
            help="Display name for the dashboard"
        )
        
        # Timezone
        timezone = st.selectbox(
            "System Timezone",
            ["Asia/Kuwait", "UTC", "America/New_York", "Europe/London"],
            index=0
        )
        
        # Data retention
        retention_days = st.slider(
            "Data Retention Period (days)",
            min_value=30,
            max_value=365,
            value=90,
            help="How long to keep historical data"
        )
        
        if st.button("Save General Settings", type="primary"):
            st.success("Settings saved successfully!")
    
    with tab2:
        st.markdown("### Security Settings")
        
        # Session timeout
        timeout_minutes = st.slider(
            "Session Timeout (minutes)",
            min_value=15,
            max_value=240,
            value=30,
            help="Automatic logout after inactivity"
        )
        
        # Password policy
        st.markdown("#### Password Policy")
        
        min_length = st.slider(
            "Minimum Password Length",
            min_value=8,
            max_value=20,
            value=12
        )
        
        require_numbers = st.checkbox("Require numbers", value=True)
        require_special = st.checkbox("Require special characters", value=True)
        
        if st.button("Save Security Settings", type="primary"):
            st.success("Security settings updated!")
    
    with tab3:
        st.markdown("### Integration Settings")
        
        # GitHub integration
        st.markdown("#### GitHub Integration")
        
        github_repo = st.text_input(
            "GitHub Repository",
            placeholder="username/repository",
            help="Format: username/repository-name"
        )
        
        github_token = st.text_input(
            "GitHub Token",
            type="password",
            help="Personal access token for GitHub API"
        )
        
        # Email notifications
        st.markdown("#### Email Notifications")
        
        smtp_server = st.text_input("SMTP Server")
        smtp_port = st.number_input("SMTP Port", value=587)
        notification_email = st.text_input("Notification Email")
        
        if st.button("Save Integration Settings", type="primary"):
            st.success("Integration settings saved!")

elif selected_page == "User Management":
    if st.session_state['username'] != 'admin':
        st.error("Access denied. Admin privileges required.")
        st.stop()
    
    st.title("User Management")
    
    # Display current users
    st.markdown("### Current Users")
    
    users_list = list(auth_manager.users.keys())
    user_df = pd.DataFrame({
        'Username': users_list,
        'Role': ['Admin' if user == 'admin' else 'Manager' if user == 'manager' else 'User' for user in users_list]
    })
    
    st.dataframe(user_df, use_container_width=True)
    
    # Add new user
    st.markdown("### Add New User")
    
    with st.form("add_user_form"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            new_username = st.text_input("Username")
        
        with col2:
            new_password = st.text_input("Password", type="password")
        
        with col3:
            new_role = st.selectbox("Role", ["Admin", "Manager", "Analyst"])
        
        if st.form_submit_button("Add User", type="primary"):
            if new_username and new_password:
                # In production, you would save this to a secure database
                st.success(f"User {new_username} added successfully!")
            else:
                st.warning("Please fill in all fields")

elif selected_page == "Reports":
    st.title("Reports & Exports")
    
    # Report types
    report_type = st.selectbox(
        "Select Report Type",
        ["Daily Production Report", "Monthly Summary", "Forecast Analysis", "Plant Performance", "Custom Report"]
    )
    
    # Date range for report
    col1, col2 = st.columns(2)
    
    with col1:
        report_start = st.date_input("Report Start Date")
    
    with col2:
        report_end = st.date_input("Report End Date")
    
    # Report options
    st.markdown("### Report Options")
    
    options_col1, options_col2 = st.columns(2)
    
    with options_col1:
        include_charts = st.checkbox("Include Charts", value=True)
        include_summary = st.checkbox("Include Executive Summary", value=True)
    
    with options_col2:
        format_type = st.selectbox("Format", ["PDF", "Excel", "HTML", "CSV"])
        detail_level = st.select_slider("Detail Level", ["Summary", "Standard", "Detailed"])
    
    # Generate report
    st.markdown("### Generate Report")
    
    if st.button("Generate Report", type="primary", use_container_width=True):
        # Placeholder for report generation
        st.info(f"Generating {report_type} for {report_start} to {report_end}...")
        
        # Simulate report generation
        import time
        with st.spinner("Creating report..."):
            time.sleep(2)
            
            # Create sample report data
            sample_report = pd.DataFrame({
                'Date': pd.date_range(start=report_start, end=report_end, freq='D'),
                'Production': np.random.randint(7000, 9000, (report_end - report_start).days + 1),
                'Target': np.full((report_end - report_start).days + 1, 8500)
            })
            
            # Create download button
            csv_data = sample_report.to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"Download {report_type} ({format_type})",
                data=csv_data,
                file_name=f"KBRC_Report_{report_start}_{report_end}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            st.success("Report generated successfully!")
    
    # Recent reports
    st.markdown("### Recent Reports")
    
    recent_reports = [
        {"name": "Monthly Production Summary - Nov 2024", "date": "2024-12-01", "type": "Monthly"},
        {"name": "Plant Efficiency Analysis", "date": "2024-11-28", "type": "Analysis"},
        {"name": "Q4 Forecast Review", "date": "2024-11-25", "type": "Forecast"},
        {"name": "Daily Production - Week 48", "date": "2024-11-22", "type": "Weekly"}
    ]
    
    for report in recent_reports:
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.write(f"**{report['name']}**")
        with col2:
            st.write(report['type'])
        with col3:
            st.write(report['date'])

else:
    # Default page (Dashboard if none selected)
    st.title("Welcome to KBRC Dashboard")
    st.info("Select a page from the sidebar to get started.")

# ========================================
# 14. FOOTER
# ========================================
st.markdown("""
<div style="
    margin-top: 50px;
    padding-top: 20px;
    border-top: 1px solid #e2e8f0;
    text-align: center;
    color: #64748b;
    font-size: 0.8rem;
">
    <p>
        Kuwait Building Readymix Company • Production Dashboard v3.0 •
        Last Updated: 2024
    </p>
    <p style="font-size: 0.7rem;">
        For technical support: <a href="mailto:Ashwin.IT@kbrc.com.kw" style="color: #3b82f6;">Ashwin.IT@kbrc.com.kw</a> •
        Confidential & Proprietary
    </p>
</div>
""", unsafe_allow_html=True)
