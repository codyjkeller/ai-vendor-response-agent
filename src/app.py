import streamlit as st
import pandas as pd
import os
import sys

# --- Path Setup ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from agent import VendorResponseAgent
from ingest import create_vector_db

# --- Page Config ---
st.set_page_config(
    page_title="AuditFlow - Compliance Platform",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- THEME ENGINE ---
if "theme" not in st.session_state:
    st.session_state.theme = "light"

# --- CUSTOM CSS (Professional Dark/Green Theme) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* DARK SIDEBAR */
    section[data-testid="stSidebar"] {
        background-color: #111827; /* Dark Navy/Black */
        color: white;
    }
    
    /* Sidebar Text Overrides */
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3, 
    section[data-testid="stSidebar"] p, 
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] div {
        color: #E5E7EB !important; /* Light Grey Text */
    }
    
    /* Metrics Cards */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 20px;
        border-radius: 8px;
        box-shadow:
