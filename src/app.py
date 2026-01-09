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
    page_title="AuditFlow - Response Hub",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- THEME ENGINE ---
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "Pro (Default)"

# --- CUSTOM CSS GENERATOR ---
def get_theme_css(mode):
    # Base CSS (Fonts)
    base_css = """
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    """
    
    # 1. FIX: PREFERENCES BUTTON STYLING
    # This targets the button inside the sidebar to make it white with dark text
    popover_css = """
    /* Style the Preferences Button in Sidebar */
    section[data-testid="stSidebar"] button[kind="secondary"] {
        background-color: #F3F4F6 !important;
        color: #111827 !important;
        border: none !important;
        font-weight: 500 !important;
        width: 100% !important;
        text-align: left !important;
        padding-left: 15px !important;
    }
    section[data-testid="stSidebar"] button[kind="secondary"]:hover {
        background-color: #E5E7EB !important;
    }
    """
    
    if mode == "Pro (Default)":
        return base_css + popover_css + """
        /* Navy Sidebar / White Main */
        section[data-testid="stSidebar"] { background-color: #111827; color: white; }
        section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] span, section[data-testid="stSidebar"] p { color: #E5E7EB !important; }
        .stApp { background-color: #FFFFFF; color: #111827; }
        
        /* 2. FIX: METRIC CARD SPACING */
        div[data-testid="stMetric"] { 
            background-color: #ffffff; 
            border: 1px solid #e0e0e0; 
            border-left: 5px solid #2e7d32; 
            padding: 15px 20px !important; /* Added padding for breathing room */
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }
        
        .main-header { color: #111827; }
        """
        
    elif mode == "Dark Mode":
        return base_css + popover_css + """
        /* Full Dark */
        section[data-testid="stSidebar"] { background-color: #1f1f1f; }
        .stApp { background-color: #121212; color: #E0E0E0; }
        
        div[data-testid="stMetric"] { 
            background-color: #2D2D2D; 
            border: 1px solid #444; 
            border-left: 5px solid #00C853; 
            padding: 15px 20px !important;
            border-radius: 8px;
        }
        
        h1, h2, h3, p, span, div { color: #E0E0E0 !important; }
        .main-header { color: #ffffff !important; }
        """
        
    elif mode == "Light Mode":
        return base_css + popover_css + """
        /* Full Light */
        section[data-testid="stSidebar"] { background-color: #F0F2F6; }
        section[data-testid="stSidebar"] * { color: #333 !important; }
        .stApp { background-color: #FFFFFF; color: #333; }
        div[data-testid="stMetric"] { background-color: #F9F9F9; border: 1px solid #ddd; padding: 15px 20px; border-radius: 8px; }
        .main-header { color: #333; }
        """
    return base_css

# Apply CSS
st.markdown(f"<style>{get_theme_css(st.session_state.theme_mode)}</style>", unsafe_allow_html=True)
st.markdown("""
<style>
    /* Global Helpers */
    .main-header { font-size: 26px; font-weight: 600; margin-bottom: 25px; }
    
    /* Thicker Progress Bar */
    .stProgress > div > div > div > div { 
        background-color: #2e7d32; 
        height: 12px; 
        border-radius: 6px;
    }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.title("🛡️ AuditFlow")
    st.caption("Security Questionnaire Assistant")
    
    st.markdown("---")
    
    # Navigation
    page = st.radio(
        "Menu", 
        ["Dashboard", "My Projects", "Questionnaire Agent", "Knowledge Base"],
        index=0
    )
    
    st.markdown("---")
    
    # POP-OUT PREFERENCES MENU (Fixed Styling)
    # The CSS above will now make this button white with dark text
    with st.popover("⚙️ Preferences", use_container_width=True):
        st.markdown("### 🎨 Appearance")
        selected_theme = st.radio(
            "Interface Theme", 
            ["Pro (Default)", "Dark Mode", "Light Mode"],
            index=["Pro (Default)", "Dark Mode", "Light Mode"].index(st.session_state.theme_mode),
            key="theme_selector"
        )
        if selected_theme != st.session_state.theme_mode:
            st.session_state.theme_mode = selected_theme
            st.rerun()

    st.divider()
    
    # System Status
    api_key = os.getenv("OPENAI_API_KEY")
    status_icon = "🟢" if api_key else "🟡"
    st.caption(f"{status_icon} Engine: Online")

# --- INITIALIZE LOGIC ---
if not os.path.exists("./chroma_db") and os.path.exists("./data"):
    try:
        if "db_built" not in st.session_state:
            create_vector_db()
            st.session_state.db_built = True
    except:
        pass

if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent" not in st.session_state:
    st.session_state.agent = VendorResponseAgent()

# --- PAGE 1: DASHBOARD ---
if page == "Dashboard":
    st.markdown('<div class="main-header">Current Assessment Overview</div>', unsafe_allow_html=True)
    
    # Fixed Metrics with Padding
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Completion", "65%", "In Progress")
    with col2:
        st.metric("Pending Review", "12", "Needs Attention")
    with col3:
        st.metric("Flagged Items", "3", delta=None)
    with col4:
        st.metric("AI Confidence", "94%", "High Accuracy")

    st.markdown("### Progress: SoundThinking SIG 2026")
    st.progress(65)
    
    st.divider()
    
    # Generic Request Table
    st.subheader("Latest Questionnaire Items")
    data = {
        "Q-ID": ["3.1", "3.2", "4.5", "5.1", "5.2"],
        "Category": ["Access Control", "Access Control", "Data Encryption", "Incident Mgmt", "Incident Mgmt"],
        "Question": ["Do you use MFA?", "Is MFA enforced for all users?", "Is data encrypted at rest?", "Do you have an IR Plan?", "Is the IR Plan tested?"],
        "Status": ["Drafted", "Drafted", "Review Pending", "Approved", "Empty"],
        "Confidence": ["High", "High", "Medium", "High", "-"]
    }
    df = pd.DataFrame(data)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Status": st.column_config.SelectboxColumn(
                "Status",
                width="small",
                options=["Approved", "Drafted", "Review Pending", "Empty"],
                required=True,
            ),
             "Confidence": st.column_config.TextColumn(
                "AI Conf.",
                width="small"
            ),
        }
    )

# --- PAGE 2: PROJECTS ---
elif page == "My Projects":
    st.markdown('<div class="main-header">Active Questionnaires</div>', unsafe_allow_html=True)
    
    projects = pd.DataFrame({
        "Project Name": ["SoundThinking SIG 2026", "Internal ISO Audit", "Vendor A - CAIQ Lite"],
        "Due Date": ["Feb 28, 2026", "Mar 15, 2026", "Jan 10, 2026"],
        "Progress": [65, 20, 90],
        "Type": ["SIG Core", "ISO 27001", "CAIQ"]
    })
    
    st.dataframe(
        projects, 
        use_container_width=True,
        column_config={
            "Progress": st.column_config.ProgressColumn(
                "Completion",
                format="%d%%",
                min_value=0,
                max_value=100,
            ),
        },
        hide_index=True
    )

# --- PAGE 3: AI AGENT (Export Fix) ---
elif page == "Questionnaire Agent":
    st.markdown('<div class="main-header">⚡ Vendor Response Agent</div>', unsafe_allow_html=True)
    
    if len(st.session_state.messages) > 0:
        col_export, col_dummy = st.columns([1, 5])
        with col_export:
            export_data = []
            for msg in st.session_state.messages:
                if msg["role"] == "assistant":
                    export_data.append({
                        "Role": "AI", 
                        "Content": msg["content"], 
                        "Evidence": msg.get("evidence", "N/A")
                    })
                else:
                    export_data.append({
                        "Role": "User", 
                        "Content": msg["content"], 
                        "Evidence": ""
                    })
            
            df_export = pd.DataFrame(export_data)
            csv = df_export.to_csv(index=False).encode('utf-8')
            
            st.download_button(
                label="📥 Download Report (CSV)",
                data=csv,
                file_name="audit_response_report.csv",
                mime="text/csv",
            )

    st.info("Paste a question from any Excel/Portal (SIG, CAIQ, VSA) to get an instant answer.")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "evidence" in message and message["evidence"]:
                with st.expander("🔍 Verified Source"):
                    st.markdown(message["evidence"])

    if prompt := st.chat_input("Ex: How do we handle data backups?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Searching knowledge base..."):
                try:
                    df = st.session_state.agent.generate_responses([prompt])
                    if not df.empty:
                        answer = df.iloc[0]['AI_Response']
                        evidence = df.iloc[0]['Evidence']
                        
                        st.markdown(answer)
                        if evidence and evidence != "No Source":
                            with st.expander("🔍 Verified Source"):
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

# --- PAGE 4: KNOWLEDGE BASE ---
elif page == "Knowledge Base":
    st.markdown('<div class="main-header">📚 Knowledge Base</div>', unsafe_allow_html=True)
    st.write("Upload your security policies and past questionnaires here to update the AI's brain.")
    
    uploaded_files = st.file_uploader(
        "📂 Drag and drop Policy PDFs or Excel files", 
        type=["pdf", "docx", "xlsx"], 
        accept_multiple_files=True
    )
    
    if uploaded_files:
        if st.button("⚡ Process and Index Files"):
            os.makedirs("data", exist_ok=True)
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"Saving {uploaded_file.name}...")
                with open(os.path.join("data", uploaded_file.name), "wb") as f:
                    f.write(uploaded_file.getbuffer())
                progress_bar.progress((i + 1) / len(uploaded_files) * 0.5)
            
            status_text.text("🧠 Rebuilding Knowledge Base (This may take a moment)...")
            try:
                create_vector_db()
                progress_bar.progress(100)
                status_text.success("✅ Indexing Complete! The AI is now updated.")
                st.session_state.agent = VendorResponseAgent()
            except Exception as e:
                st.error(f"Ingestion failed: {e}")

    st.divider()
    
    st.subheader("Current Index Status")
    col1, col2 = st.columns(2)
    with col1:
        if os.path.exists("./chroma_db"):
            st.success("✅ **Active Database:** `chroma_db`")
        else:
            st.warning("⚠️ **Database Missing**")
            
    with col2:
        if os.path.exists("data"):
            files = os.listdir("data")
            st.caption(f"**Indexed Files ({len(files)}):**")
            for f in files:
                st.code(f"📄 {f}")
        else:
            st.caption("No files found in /data")
