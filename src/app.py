import streamlit as st
import pandas as pd
import os
import sys
import time

# --- Path Setup ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from agent import VendorResponseAgent
from ingest import create_vector_db

# --- Page Config (B2B Style) ---
st.set_page_config(
    page_title="VendorAI - Compliance Portal",
    page_icon="🛡️",
    layout="wide", # Critical for the "Dashboard" look
    initial_sidebar_state="expanded"
)

# --- Custom CSS for "Enterprise Look" ---
st.markdown("""
<style>
    /* Metric Cards */
    .stMetric {
        background-color: #f9f9f9;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    /* Green Accents (Matching A-LIGN) */
    .stProgress > div > div > div > div {
        background-color: #28a745;
    }
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #f0f2f6;
    }
</style>
""", unsafe_allow_html=True)

# --- Cloud Self-Healing ---
if not os.path.exists("./chroma_db"):
    if os.path.exists("./data"):
        with st.spinner("🤖 Initializing Knowledge Base..."):
            try:
                create_vector_db()
            except Exception as e:
                st.error(f"DB Build Failed: {e}")

# --- Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent" not in st.session_state:
    st.session_state.agent = VendorResponseAgent()

# --- SIDEBAR NAVIGATION ---
with st.sidebar:
    st.title("🛡️ VendorAI")
    st.caption("Automated Security Compliance")
    
    # Navigation Menu
    page = st.radio("Navigation", ["Dashboard", "Questionnaire Assistant", "Settings"])
    
    st.divider()
    
    # Status Indicators
    api_key = os.getenv("OPENAI_API_KEY")
    st.markdown("### System Status")
    if api_key:
        st.success("🟢 AI Engine: Online")
    else:
        st.warning("🟡 AI Engine: Offline")
        
    st.info(f"📚 Knowledge Base: { 'Active' if os.path.exists('./chroma_db') else 'Inactive'}")

# --- PAGE 1: DASHBOARD (The A-LIGN Look) ---
if page == "Dashboard":
    st.title("Compliance Dashboard")
    st.markdown("### Engagement Overview: SOC 2 Type II")
    
    # Top Row Metrics (Cards)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Completion Status", value="50%", delta="On Track")
    with col2:
        st.metric(label="Pending Questions", value="190", delta="-5 Today")
    with col3:
        st.metric(label="Action Required", value="0", delta_color="off")
    with col4:
        st.metric(label="Avg Response Time", value="1.2s", delta="AI Assisted")

    # Visual Progress Bar
    st.markdown("#### Engagement Milestones")
    st.progress(50)
    st.caption("Milestone: 50% Uploaded Evidence Reached on Oct 16, 2025")

    # Recent Activity Table (Dummy Data for look & feel)
    st.divider()
    st.subheader("Recent Requests")
    
    # Creating a fake B2B-style table
    data = {
        "Request ID": ["P-1", "P-101", "P-13", "P-135"],
        "Description": ["Application Code Changes", "Backup Failures List", "Network Security Rules", "Security Control Failures"],
        "Status": ["Accepted", "Accepted", "Review Pending", "In Progress"],
        "Owner": ["Cody Keller", "Cody Keller", "AI Agent", "AI Agent"]
    }
    df = pd.DataFrame(data)
    
    # Show dataframe with Streamlit's column config for badges
    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "Status": st.column_config.TextColumn(
                "Status",
                help="Current status of the request",
                validate="^Accepted|In Progress|Review Pending$",
            ),
        },
        hide_index=True
    )

# --- PAGE 2: THE AI ASSISTANT (Your Core Feature) ---
elif page == "Questionnaire Assistant":
    st.title("⚡ Rapid Response Agent")
    st.caption("Upload a questionnaire or ask specific security questions.")

    # Main Chat Interface
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

# --- PAGE 3: SETTINGS ---
elif page == "Settings":
    st.title("Settings")
    st.warning("This area is under construction.")
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.success("History Cleared!")
