import streamlit as st
import pandas as pd
import os
import sys
import json
import csv
import time
import altair as alt
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
    page_title="AuditFlow - Secure Access",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- THEME ENGINE ---
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "Pro (Default)"
if "user_profile" not in st.session_state:
    st.session_state.user_profile = {"name": "Cody Keller", "email": "cody@auditflow.io", "role": "CISO"}
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

def get_theme_css(mode):
    base_css = """
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    """
    if mode == "Pro (Default)":
        return base_css + """
        section[data-testid="stSidebar"] { background-color: #111827; color: white; }
        section[data-testid="stSidebar"] * { color: #E5E7EB !important; }
        .stApp { background-color: #F9FAFB; color: #111827; }
        div[data-testid="stMetric"] { background-color: #ffffff; border: 1px solid #E5E7EB; border-radius: 8px; padding: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .metric-label { font-size: 0.875rem; color: #6B7280; }
        .metric-value { font-size: 1.5rem; font-weight: 600; color: #111827; }
        """
    elif mode == "Dark Mode":
        return base_css + """
        section[data-testid="stSidebar"] { background-color: #1f1f1f; }
        .stApp { background-color: #0E1117; color: #E0E0E0; }
        div[data-testid="stMetric"] { background-color: #262730; border: 1px solid #444; border-radius: 8px; padding: 15px; }
        """
    elif mode == "Light Mode":
        return base_css + """
        section[data-testid="stSidebar"] { background-color: #F0F2F6; }
        .stApp { background-color: #FFFFFF; color: #333; }
        """
    return base_css

st.markdown(f"<style>{get_theme_css(st.session_state.theme_mode)}</style>", unsafe_allow_html=True)

# --- LOGIN SCREEN LOGIC ---
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("## 🛡️ AuditFlow Secure Login")
        st.info("Identity Provider: SoundThinking SSO")
        
        with st.form("login_form"):
            st.text_input("Username", value="cody.keller@auditflow.io")
            st.text_input("Password", type="password", value="password123")
            submitted = st.form_submit_button("Sign In", type="primary", use_container_width=True)
            
            if submitted:
                with st.spinner("Authenticating..."):
                    time.sleep(1) # Fake delay for realism
                    st.session_state.logged_in = True
                    log_action("System", "USER_LOGIN", "User logged in successfully")
                    st.rerun()
    st.stop() # Stop execution here if not logged in

# --- MAIN APP START ---

# --- SIDEBAR ---
with st.sidebar:
    st.title("🛡️ AuditFlow")
    st.caption("Enterprise Compliance")
    st.markdown("---")
    
    # NAVIGATION
    page = st.radio("Navigation", ["Executive Dashboard", "My Projects", "Questionnaire Agent", "Knowledge Base", "Settings"], index=0)
    
    st.markdown("---")
    api_key = os.getenv("OPENAI_API_KEY")
    status_icon = "🟢" if api_key else "🟡"
    st.caption(f"{status_icon} AI Engine: Online")
    
    if st.button("Log Out", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()

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

# --- PAGE 1: EXECUTIVE DASHBOARD ---
if page == "Executive Dashboard":
    st.title("Executive Dashboard")
    st.markdown("Welcome back, **Cody**. Here is your compliance posture for today.")
    st.markdown("<br>", unsafe_allow_html=True)
    
    # DYNAMIC METRICS
    reg = load_registry()
    files_count = len(reg)
    
    # Calculate "Pending" based on dummy logic for now
    pending_tasks = 12 
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Security Posture", "Secure", "No Critical Flags")
    with col2:
        st.metric("Active Audits", "3", "+1 This Month")
    with col3:
        st.metric("KB Assets Indexed", f"{files_count}", "Live Documents")
    with col4:
        st.metric("Pending Tasks", f"{pending_tasks}", "-2 Since Yesterday", delta_color="inverse")

    st.divider()

    # CHARTS & ACTIVITY
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.subheader("📊 Audit Readiness Status")
        # Mock Data for Chart
        chart_data = pd.DataFrame({
            'Status': ['Completed', 'In Review', 'Drafting', 'Not Started'],
            'Items': [85, 12, 15, 8]
        })
        
        c = alt.Chart(chart_data).mark_bar().encode(
            x='Items',
            y=alt.Y('Status', sort=None),
            color=alt.Color('Status', scale=alt.Scale(scheme='greens'))
        ).properties(height=250)
        
        st.altair_chart(c, use_container_width=True)

    with col_right:
        st.subheader("⚡ Live Activity Feed")
        if os.path.exists(AUDIT_LOG_FILE):
            df_log = pd.read_csv(AUDIT_LOG_FILE).tail(5).sort_values(by="Timestamp", ascending=False)
            for index, row in df_log.iterrows():
                icon = "🤖" if row['User'] == "System" else "👤"
                st.markdown(f"**{icon} {row['Action']}**")
                st.caption(f"{row['Details']} • {row['Timestamp']}")
                st.markdown("---")
        else:
            st.info("No recent activity.")

    # REQUESTS TABLE
    st.subheader("📋 Priority Action Items")
    request_data = {
        "Control ID": ["CC-1.4", "CC-2.1", "CC-3.5", "CC-6.1", "CC-8.2"],
        "Description": ["Board of Directors Review", "User Access Reviews", "Change Management Tickets", "Vulnerability Scans", "Incident Response Test"],
        "Status": ["In Progress", "Review Pending", "Approved", "Action Required", "Approved"],
        "Owner": ["Cody Keller", "AI Agent", "Jane Doe", "Cody Keller", "SecOps"]
    }
    df_requests = pd.DataFrame(request_data)
    
    st.dataframe(
        df_requests,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Status": st.column_config.SelectboxColumn(
                "Status",
                width="small",
                options=["Approved", "In Progress", "Review Pending", "Action Required"],
                required=True,
            ),
             "Control ID": st.column_config.TextColumn(
                "Control ID",
                width="small"
            ),
        }
    )

# --- PAGE 2: PROJECTS ---
elif page == "My Projects":
    st.title("Active Questionnaires")
    projects = pd.DataFrame({
        "Project Name": ["SoundThinking SIG 2026", "Internal ISO Audit", "Vendor A - CAIQ Lite"],
        "Due Date": ["Feb 28, 2026", "Mar 15, 2026", "Jan 10, 2026"],
        "Progress": [65, 20, 90],
        "Type": ["SIG Core", "ISO 27001", "CAIQ"]
    })
    st.dataframe(projects, use_container_width=True, column_config={"Progress": st.column_config.ProgressColumn("Completion", format="%d%%", min_value=0, max_value=100)}, hide_index=True)

# --- PAGE 3: AI AGENT ---
elif page == "Questionnaire Agent":
    st.title("⚡ Vendor Response Agent")
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
                with st.expander("🔍 Verified Source"): 
                    st.markdown(message["evidence"])

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
                        # FIXED: Split logic to multi-line for valid Python syntax
                        if evidence and evidence != "No Source": 
                            with st.expander("🔍 Verified Source"): 
                                st.markdown(evidence)
                        
                        st.session_state.messages.append({"role": "assistant", "content": answer, "evidence": evidence})
                        log_action("User", "QUERY_AI", prompt[:50] + "...")
                    else: st.error("No response generated.")
                except Exception as e: st.error(f"Error: {e}")

# --- PAGE 4: KNOWLEDGE BASE ---
elif page == "Knowledge Base":
    st.title("📚 Knowledge Base")
    st.write("Manage security policies. Changes here automatically update the AI.")

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
    st.title("⚙️ Settings")
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
