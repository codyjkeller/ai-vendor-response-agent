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
        box-shadow: 0px 1px 3px rgba(0,0,0,0.05);
    }
    
    /* Custom Header Style */
    .main-header {
        font-size: 24px;
        font-weight: 600;
        color: #111827;
        margin-bottom: 20px;
    }
    
    /* Green Progress Bars */
    .stProgress > div > div > div > div {
        background-color: #2e7d32;
    }
</style>
""", unsafe_allow_html=True)

# --- Sidebar ---
with st.sidebar:
    st.title("🔒 AuditFlow")
    st.caption("Integrated Compliance Suite")
    
    st.markdown("---")
    
    # Navigation
    page = st.radio(
        "Platform Navigation", 
        ["Dashboard", "Active Audits", "Task List", "AI Assistant", "Settings"],
        index=0
    )
    
    st.markdown("---")
    
    # Client Context
    st.selectbox("Organization", ["SoundThinking", "Internal Security", "Vendor A"])
    
    st.divider()
    
    # System Status
    api_key = os.getenv("OPENAI_API_KEY")
    status_icon = "🟢" if api_key else "🟡"
    st.caption(f"{status_icon} System: Online")

# --- Initialize Logic ---
if not os.path.exists("./chroma_db") and os.path.exists("./data"):
    try:
        create_vector_db()
    except:
        pass

if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent" not in st.session_state:
    st.session_state.agent = VendorResponseAgent()

# --- PAGE 1: DASHBOARD ---
if page == "Dashboard":
    st.markdown('<div class="main-header">Engagement Overview: SOC 2 Type II</div>', unsafe_allow_html=True)
    
    # KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Action Items", "0", delta=None)
    with col2:
        st.metric("Overdue Tasks", "0", delta=None)
    with col3:
        st.metric("New Comments", "0", delta=None)
    with col4:
        st.metric("Completion", "100%", "Ready for Review")

    st.markdown("### Engagement Timeline")
    st.progress(100)
    col_a, col_b, col_c = st.columns([1,1,1])
    with col_a:
        st.caption("✅ Kickoff (Aug 29)")
    with col_b:
        st.caption("✅ Evidence Collection (Oct 16)")
    with col_c:
        st.caption("✅ Final Review (Nov 12)")

    st.divider()
    
    # Request Table
    st.subheader("Recent Evidence Requests")
    data = {
        "Control ID": ["CC-1.1", "CC-6.1", "CC-6.3", "CC-8.1", "CC-9.2"],
        "Description": ["Code Change Authorization", "Backup Failure Logs", "Firewall Rules Review", "Access Control Review", "Incident Response Tickets"],
        "Status": ["Approved", "Approved", "In Review", "Collecting", "Approved"],
        "Assignee": ["Cody Keller", "Cody Keller", "AI Agent", "AI Agent", "Admin"]
    }
    df = pd.DataFrame(data)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Status": st.column_config.SelectboxColumn(
                "Status",
                width="medium",
                options=["Approved", "In Review", "Collecting", "Flagged"],
                required=True,
            ),
        }
    )

# --- PAGE 2: ACTIVE AUDITS ---
elif page == "Active Audits":
    st.markdown('<div class="main-header">Active Engagements</div>', unsafe_allow_html=True)
    st.info("Select an audit to view details.")
    
    # Mock Data
    eng_data = pd.DataFrame({
        "Audit Name": ["2025 SOC 2 Type II", "ISO 27001 Surveillance", "HIPAA Assessment"],
        "Progress": [100, 45, 10],
        "Stage": ["Reporting", "Fieldwork", "Scoping"]
    })
    
    st.dataframe(
        eng_data, 
        use_container_width=True,
        column_config={
            "Progress": st.column_config.ProgressColumn(
                "Progress",
                format="%d%%",
                min_value=0,
                max_value=100,
            ),
        },
        hide_index=True
    )

# --- PAGE 3: AI ASSISTANT ---
elif page == "AI Assistant":
    st.markdown('<div class="main-header">⚡ Audit Assistant</div>', unsafe_allow_html=True)

    # Chat Interface
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "evidence" in message and message["evidence"]:
                with st.expander("🔍 Verified Evidence"):
                    st.markdown(message["evidence"])

    if prompt := st.chat_input("Ex: What is our policy for terminating access?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analyzing controls..."):
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

# --- OTHER PAGES ---
elif page == "Task List":
    st.title("My Tasks")
    st.write("No pending tasks assigned to you.")

elif page == "Settings":
    st.title("Settings")
    st.write("System configuration.")
