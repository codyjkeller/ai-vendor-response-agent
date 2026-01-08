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
    page_title="VendorAI - Compliance Portal",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- THEME ENGINE (Dark/Light Mode) ---
# We use session state to track the theme
if "theme" not in st.session_state:
    st.session_state.theme = "light"

# Custom CSS for Fonts and Theme Toggling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Card Styling */
    div[data-testid="stMetricValue"] {
        font-size: 28px;
        color: #00C853; /* Brand Green */
    }
    
    /* Custom Table Headers */
    th {
        background-color: #f0f2f6 !important;
        color: #444 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Sidebar ---
with st.sidebar:
    st.title("🛡️ VendorAI")
    
    # Navigation
    page = st.radio("Navigation", ["Dashboard", "Questionnaire Assistant", "Settings"])
    st.divider()
    
    # Theme Toggle
    st.write("### 🎨 Appearance")
    is_dark = st.toggle("Dark Mode", value=False)
    
    # Dynamic CSS based on Toggle
    if is_dark:
        st.markdown("""
        <style>
            .stApp { background-color: #1E1E1E; color: white; }
            section[data-testid="stSidebar"] { background-color: #2D2D2D; }
            .stMetric { background-color: #2D2D2D !important; border: 1px solid #444; }
            h1, h2, h3, p { color: white !important; }
            div[data-testid="stMetricLabel"] { color: #aaa !important; }
        </style>
        """, unsafe_allow_html=True)

    st.divider()
    
    # System Status (Keep existing logic)
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        st.success("🟢 AI Engine: Online")
    else:
        st.warning("🟡 AI Engine: Offline")

# --- Initialize Logic (Keep existing logic) ---
# Cloud Self-Healing
if not os.path.exists("./chroma_db"):
    if os.path.exists("./data"):
        with st.spinner("🤖 Initializing Knowledge Base..."):
            try:
                create_vector_db()
            except Exception as e:
                st.error(f"DB Build Failed: {e}")

# Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent" not in st.session_state:
    st.session_state.agent = VendorResponseAgent()

# --- PAGE 1: DASHBOARD ---
if page == "Dashboard":
    st.title("Compliance Dashboard")
    st.caption("Real-time oversight of SOC 2 Type II Engagement")
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Completion Status", "50%", "On Track")
    with col2:
        st.metric("Pending Questions", "190", "-5 Today")
    with col3:
        st.metric("Action Required", "0", delta_color="off")
    with col4:
        st.metric("Avg Response Time", "1.2s", "AI Assisted")

    st.markdown("#### Engagement Progress")
    # Custom colored progress bar
    st.progress(50)

    st.divider()
    
    # --- UPGRADED TABLE ---
    st.subheader("Recent Requests")
    
    data = {
        "Request ID": ["P-1", "P-101", "P-13", "P-135", "P-14"],
        "Description": ["Application Code Changes", "Backup Failures List", "Network Security Rules", "Security Control Failures", "Incident Reports"],
        "Status": ["Accepted", "Accepted", "Review Pending", "In Progress", "Action Required"],
        "Owner": ["Cody Keller", "Cody Keller", "AI Agent", "AI Agent", "Admin"]
    }
    df = pd.DataFrame(data)

    # Display with "Pills" for Status
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Status": st.column_config.SelectboxColumn(
                "Status",
                help="Current status",
                width="medium",
                options=["Accepted", "In Progress", "Review Pending", "Action Required"],
                # This maps text to specific colors
                required=True,
            ),
            "Owner": st.column_config.TextColumn(
                "Owner",
                width="small"
            ),
            "Description": st.column_config.TextColumn(
                "Description",
                width="large"
            )
        }
    )

# --- PAGE 2: ASSISTANT ---
elif page == "Questionnaire Assistant":
    st.title("⚡ Rapid Response Agent")
    
    # Chat Interface
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "evidence" in message and message["evidence"]:
                with st.expander("🔍 Verified Evidence"):
                    st.markdown(message["evidence"])

    if prompt := st.chat_input("Ex: Describe our Change Management process for P-1"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Consulting security artifacts..."):
                try:
                    df = st.session_state.agent.generate_responses([prompt])
                    if not df.empty:
                        answer = df.iloc[0]['AI_Response']
                        evidence = df.iloc[0]['Evidence']
                        
                        st.markdown(answer)
                        if evidence and evidence != "No Source":
                            with st.expander("🔍 Verified Evidence"):
                                st.markdown(evidence)

                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": answer,
                            "evidence": evidence
                        })
                    else:
                        st.error("No response generated.")
                except Exception as e:
                    st.error(f"Error: {e}")

elif page == "Settings":
    st.title("Settings")
    st.info("User Management and Knowledge Base Uploads coming soon.")
