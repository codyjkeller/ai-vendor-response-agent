import streamlit as st
import pandas as pd
import os
import sys
import json
import csv
from datetime import datetime

# --- Path Setup ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from agent import VendorResponseAgent
from ingest import create_vector_db

# --- CONFIGURATION & CONSTANTS ---
DATA_DIR = "data"
REGISTRY_FILE = os.path.join(DATA_DIR, "registry.json")
AUDIT_LOG_FILE = "audit_log.csv"

# Ensure data dir exists
os.makedirs(DATA_DIR, exist_ok=True)

# --- HELPER FUNCTIONS ---

def log_action(user, action, details):
    """Logs user actions to a CSV file for compliance."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not os.path.exists(AUDIT_LOG_FILE):
        with open(AUDIT_LOG_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "User", "Action", "Details"])
            
    with open(AUDIT_LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, user, action, details])

def load_registry():
    if os.path.exists(REGISTRY_FILE):
        with open(REGISTRY_FILE, "r") as f:
            return json.load(f)
    return {}

def save_registry(registry):
    with open(REGISTRY_FILE, "w") as f:
        json.dump(registry, f, indent=4)

def update_file_meta(filename, new_desc):
    """Updates the description of an existing file."""
    reg = load_registry()
    if filename in reg:
        reg[filename]["description"] = new_desc
        save_registry(reg)
        log_action("User", "UPDATE_META", f"Updated description for {filename}")
        return True
    return False

def delete_file(filename):
    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    
    reg = load_registry()
    if filename in reg:
        del reg[filename]
        save_registry(reg)
    
    log_action("Admin", "DELETE_FILE", f"Deleted {filename}")

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="AuditFlow - Response Hub",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- THEME ENGINE ---
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "Pro (Default)"
if "user_profile" not in st.session_state:
    st.session_state.user_profile = {"name": "Cody Keller", "email": "cody@example.com", "role": "Security Analyst"}

def get_theme_css(mode):
    base_css = """
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    """
    if mode == "Pro (Default)":
        return base_css + """
        section[data-testid="stSidebar"] { background-color: #111827; color: white; }
        section[data-testid="stSidebar"] * { color: #E5E7EB !important; }
        .stApp { background-color: #FFFFFF; color: #111827; }
        div[data-testid="stMetric"] { background-color: #ffffff; border: 1px solid #e0e0e0; border-left: 5px solid #2e7d32; padding: 15px 20px !important; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
        .main-header { color: #111827; }
        """
    elif mode == "Dark Mode":
        return base_css + """
        section[data-testid="stSidebar"] { background-color: #1f1f1f; }
        .stApp { background-color: #121212; color: #E0E0E0; }
        div[data-testid="stMetric"] { background-color: #2D2D2D; border: 1px solid #444; border-left: 5px solid #00C853; padding: 15px 20px !important; border-radius: 8px; }
        h1, h2, h3, p, span, div { color: #E0E0E0 !important; }
        .main-header { color: #ffffff !important; }
        """
    elif mode == "Light Mode":
        return base_css + """
        section[data-testid="stSidebar"] { background-color: #F0F2F6; }
        section[data-testid="stSidebar"] * { color: #333 !important; }
        .stApp { background-color: #FFFFFF; color: #333; }
        div[data-testid="stMetric"] { background-color: #F9F9F9; border: 1px solid #ddd; padding: 15px 20px; border-radius: 8px; }
        .main-header { color: #333; }
        """
    return base_css

st.markdown(f"<style>{get_theme_css(st.session_state.theme_mode)}</style>", unsafe_allow_html=True)
st.markdown("""
<style>
    .main-header { font-size: 26px; font-weight: 600; margin-bottom: 25px; }
    .stProgress > div > div > div > div { background-color: #2e7d32; height: 12px; border-radius: 6px; }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.title("🛡️ AuditFlow")
    st.caption("Security Questionnaire Assistant")
    st.markdown("---")
    
    # NAVIGATION
    page = st.radio("Menu", ["Dashboard", "My Projects", "Questionnaire Agent", "Knowledge Base", "Settings"], index=0)
    
    st.markdown("---")
    api_key = os.getenv("OPENAI_API_KEY")
    status_icon = "🟢" if api_key else "🟡"
    st.caption(f"{status_icon} Engine: Online")

# --- INITIALIZATION ---
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
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Completion", "65%", "In Progress")
    with col2: st.metric("Pending Review", "12", "Needs Attention")
    with col3: st.metric("Flagged Items", "3", delta=None)
    with col4: st.metric("AI Confidence", "94%", "High Accuracy")

    st.markdown("### Progress: SoundThinking SIG 2026")
    st.progress(65)
    st.divider()
    
    st.subheader("Latest Questionnaire Items")
    data = {
        "Q-ID": ["3.1", "3.2", "4.5", "5.1", "5.2"],
        "Category": ["Access Control", "Access Control", "Data Encryption", "Incident Mgmt", "Incident Mgmt"],
        "Question": ["Do you use MFA?", "Is MFA enforced for all users?", "Is data encrypted at rest?", "Do you have an IR Plan?", "Is the IR Plan tested?"],
        "Status": ["Drafted", "Drafted", "Review Pending", "Approved", "Empty"],
        "Confidence": ["High", "High", "Medium", "High", "-"]
    }
    st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True, column_config={"Status": st.column_config.SelectboxColumn("Status", width="small", options=["Approved", "Drafted", "Review Pending", "Empty"], required=True)})

# --- PAGE 2: PROJECTS ---
elif page == "My Projects":
    st.markdown('<div class="main-header">Active Questionnaires</div>', unsafe_allow_html=True)
    projects = pd.DataFrame({
        "Project Name": ["SoundThinking SIG 2026", "Internal ISO Audit", "Vendor A - CAIQ Lite"],
        "Due Date": ["Feb 28, 2026", "Mar 15, 2026", "Jan 10, 2026"],
        "Progress": [65, 20, 90],
        "Type": ["SIG Core", "ISO 27001", "CAIQ"]
    })
    st.dataframe(projects, use_container_width=True, column_config={"Progress": st.column_config.ProgressColumn("Completion", format="%d%%", min_value=0, max_value=100)}, hide_index=True)

# --- PAGE 3: AI AGENT ---
elif page == "Questionnaire Agent":
    st.markdown('<div class="main-header">⚡ Vendor Response Agent</div>', unsafe_allow_html=True)
    if len(st.session_state.messages) > 0:
        col_export, _ = st.columns([1, 5])
        with col_export:
            export_data = [{"Role": m["role"], "Content": m["content"], "Evidence": m.get("evidence", "")} for m in st.session_state.messages]
            st.download_button(label="📥 Download Report", data=pd.DataFrame(export_data).to_csv(index=False).encode('utf-8'), file_name="audit_report.csv", mime="text/csv")

    st.info("Paste a question from any Excel/Portal (SIG, CAIQ, VSA) to get an instant answer.")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("evidence"):
                with st.expander("🔍 Verified Source"): st.markdown(message["evidence"])

    if prompt := st.chat_input("Ex: How do we handle data backups?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Searching knowledge base..."):
                try:
                    df = st.session_state.agent.generate_responses([prompt])
                    if not df.empty:
                        answer, evidence = df.iloc[0]['AI_Response'], df.iloc[0]['Evidence']
                        st.markdown(answer)
                        if evidence and evidence != "No Source": 
                            with st.expander("🔍 Verified Source"): 
                                st.markdown(evidence)
                        st.session_state.messages.append({"role": "assistant", "content": answer, "evidence": evidence})
                        log_action("User", "QUERY_AI", prompt[:50] + "...")
                    else: st.error("No response generated.")
                except Exception as e: st.error(f"Error: {e}")

# --- PAGE 4: KNOWLEDGE BASE ---
elif page == "Knowledge Base":
    st.markdown('<div class="main-header">📚 Knowledge Base</div>', unsafe_allow_html=True)
    st.write("Manage security policies. Changes here automatically update the AI.")

    # UPLOAD SECTION
    with st.expander("📤 Upload New Documents", expanded=False):
        uploaded_files = st.file_uploader("Select Files (PDF, DOCX, XLSX)", accept_multiple_files=True)
        if uploaded_files:
            st.markdown("#### 📝 Document Details")
            file_meta = {}
            for f in uploaded_files:
                col1, col2 = st.columns([1, 2])
                with col1: st.markdown(f"**{f.name}**")
                with col2: file_meta[f.name] = st.text_input(f"Description", placeholder="Ex: Policy 2025", key=f"desc_{f.name}")
            
            if st.button("⚡ Process & Index Files", type="primary"):
                os.makedirs("data", exist_ok=True)
                registry = load_registry()
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i, uploaded_file in enumerate(uploaded_files):
                    status_text.text(f"Saving {uploaded_file.name}...")
                    with open(os.path.join("data", uploaded_file.name), "wb") as f: f.write(uploaded_file.getbuffer())
                    registry[uploaded_file.name] = {
                        "description": file_meta[uploaded_file.name],
                        "upload_date": datetime.now().strftime("%Y-%m-%d"),
                        "uploaded_by": st.session_state.user_profile["name"]
                    }
                    progress_bar.progress((i + 1) / len(uploaded_files) * 0.5)
                
                save_registry(registry)
                log_action("User", "UPLOAD_BATCH", f"Uploaded {len(uploaded_files)} files")
                status_text.text("🧠 Rebuilding Brain...")
                try:
                    create_vector_db()
                    progress_bar.progress(100)
                    status_text.success("✅ Complete!")
                    st.session_state.agent = VendorResponseAgent()
                    st.rerun()
                except Exception as e: st.error(f"Failed: {e}")

    # FILE LIST
    st.divider()
    st.subheader("🗄️ Indexed Documents")
    registry = load_registry()
    if os.path.exists("data"):
        files = [f for f in os.listdir("data") if f != "registry.json"]
        if files:
            for f in files:
                meta = registry.get(f, {"description": "No description", "upload_date": "Unknown"})
                
                with st.container():
                    c1, c2, c3, c4, c5 = st.columns([0.5, 2, 3, 1.5, 1])
                    with c1: st.markdown("📄")
                    with c2: 
                        st.markdown(f"**{f}**")
                        st.caption(f"📅 {meta['upload_date']}")
                    with c3:
                        # EDITABLE DESCRIPTION
                        new_desc = st.text_input("Description", value=meta['description'], key=f"edit_{f}", label_visibility="collapsed")
                    with c4:
                        if new_desc != meta['description']:
                            if st.button("💾 Save", key=f"save_{f}"):
                                update_file_meta(f, new_desc)
                                st.success("Saved!")
                                st.rerun()
                    with c5:
                        if st.button("🗑️", key=f"del_{f}"):
                            delete_file(f)
                            st.toast(f"Deleted {f}")
                            create_vector_db()
                            st.session_state.agent = VendorResponseAgent()
                            st.rerun()
                    st.divider()
        else: st.info("No documents found.")

# --- PAGE 5: SETTINGS ---
elif page == "Settings":
    st.markdown('<div class="main-header">⚙️ Settings</div>', unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["Appearance", "Audit Log", "User Profile"])
    
    with tab1:
        st.subheader("🎨 Interface Theme")
        selected_theme = st.radio("Choose Theme", ["Pro (Default)", "Dark Mode", "Light Mode"], index=["Pro (Default)", "Dark Mode", "Light Mode"].index(st.session_state.theme_mode))
        if selected_theme != st.session_state.theme_mode:
            st.session_state.theme_mode = selected_theme
            st.rerun()
            
    with tab2:
        st.subheader("📜 System Audit Logs")
        if os.path.exists(AUDIT_LOG_FILE):
            df_log = pd.read_csv(AUDIT_LOG_FILE).sort_values(by="Timestamp", ascending=False)
            st.dataframe(df_log, use_container_width=True, height=400)
            st.download_button("📥 Download Logs (CSV)", df_log.to_csv(index=False).encode('utf-8'), "audit_logs.csv", "text/csv")
        else:
            st.info("No logs recorded yet.")
            
    with tab3:
        st.subheader("👤 User Profile")
        col1, col2 = st.columns(2)
        with col1:
            new_name = st.text_input("Full Name", value=st.session_state.user_profile["name"])
            new_email = st.text_input("Email Address", value=st.session_state.user_profile["email"])
        with col2:
            new_role = st.text_input("Role", value=st.session_state.user_profile["role"])
            st.text_input("Organization", value="SoundThinking", disabled=True)
            
        if st.button("Update Profile"):
            st.session_state.user_profile = {"name": new_name, "email": new_email, "role": new_role}
            st.success("Profile Updated!")
