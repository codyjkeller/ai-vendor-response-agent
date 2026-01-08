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
if "theme" not in st.session_state:
    st.session_state.theme = "light"

# --- CUSTOM CSS (The "Polish" Layer) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Navbar / Header Style */
    .header-container {
        background-color: #00C853;
        padding: 1.5rem;
        border-radius: 0px 0px 10px 10px;
        margin-bottom: 2rem;
        color: white;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Metric Cards with Colored Borders */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border-left: 5px solid #00C853; /* Green accent on left */
        padding: 15px;
        border-radius: 5px;
        box-shadow: 1px 1px 3px rgba(0,0,0,0.1);
    }

    /* Footer Style */
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #F0F2F6;
        color: #666;
        text-align: center;
        padding: 10px;
        font-size: 12px;
        border-top: 1px solid #ddd;
        z-index: 100;
    }
    
    /* Dark Mode Overrides */
    .dark-mode-metric {
        background-color: #2D2D2D !important;
        color: white !important;
        border-left: 5px solid #00C853;
    }

</style>
""", unsafe_allow_html=True)

# --- UI COMPONENTS ---

def make_footer():
    st.markdown("""
    <div class="footer">
        <p>VendorAI v1.0 | Authorized Use Only | © 2026 Security Operations</p>
    </div>
    """, unsafe_allow_html=True)

# --- Sidebar ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9663/9663853.png", width=50) # Placeholder Logo
    st.title("VendorAI")
    
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
            div[data-testid="stMetric"] { background-color: #2D2D2D !important; border: 1px solid #444; border-left: 5px solid #00C853; }
            h1, h2, h3, h4, p, span { color: white !important; }
            .header-container { background-color: #1b5e20; } /* Darker green header */
            .footer { background-color: #2D2D2D; color: #aaa; border-top: 1px solid #444; }
        </style>
        """, unsafe_allow_html=True)

    st.divider()
    
    # System Status
    api_key = os.getenv("OPENAI_API_KEY")
    st.caption("SYSTEM STATUS")
    if api_key:
        st.markdown("🟢 **AI Engine:** Online")
    else:
        st.markdown("🟡 **AI Engine:** Offline")
    
    db_status = "Active" if os.path.exists("./chroma_db") else "Building..."
    st.markdown(f"📚 **Knowledge Base:** {db_status}")

# --- Initialize Logic ---
if not os.path.exists("./chroma_db") and os.path.exists("./data"):
    with st.spinner("🤖 Initializing Knowledge Base..."):
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
    # Custom Header Banner
    st.markdown('<div class="header-container"><h1>Compliance Dashboard</h1><p>Real-time oversight of SOC 2 Type II Engagement</p></div>', unsafe_allow_html=True)
    
    # Metrics with accent borders
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
    st.progress(50)
    st.caption("📅 Deadline: Feb 28, 2026 | Milestone: Evidence Collection Phase")

    st.divider()
    
    # Table Section
    st.subheader("📋 Recent Requests")
    
    data = {
        "Request ID": ["P-1", "P-101", "P-13", "P-135", "P-14"],
        "Description": ["Application Code Changes", "Backup Failures List", "Network Security Rules", "Security Control Failures", "Incident Reports"],
        "Status": ["Accepted", "Accepted", "Review Pending", "In Progress", "Action Required"],
        "Owner": ["Cody Keller", "Cody Keller", "AI Agent", "AI Agent", "Admin"]
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
                options=["Accepted", "In Progress", "Review Pending", "Action Required"],
                required=True,
            ),
        }
    )

# --- PAGE 2: ASSISTANT ---
elif page == "Questionnaire Assistant":
    st.markdown('<div class="header-container"><h1>⚡ Rapid Response Agent</h1><p>Upload questionnaires or ask security questions directly.</p></div>', unsafe_allow_html=True)

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

# Inject Footer
make_footer()
