import streamlit as st
import pandas as pd
import os
import sys
import json
import csv
import time
import altair as alt
from datetime import datetime, timedelta

# --- Path Setup ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from agent import VendorResponseAgent
from ingest import create_vector_db

# --- CONFIGURATION & CONSTANTS ---
DATA_DIR = "data"
REGISTRY_FILE = os.path.join(DATA_DIR, "registry.json")
ANSWER_BANK_FILE = os.path.join(DATA_DIR, "answer_bank.json")
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

def load_answer_bank():
    if os.path.exists(ANSWER_BANK_FILE):
        with open(ANSWER_BANK_FILE, "r") as f:
            return json.load(f)
    return []

def save_to_answer_bank(question, answer, user, product, subsidiary):
    bank = load_answer_bank()
    bank.append({
        "question": question,
        "answer": answer,
        "product": product,
        "subsidiary": subsidiary,
        "verified_by": user,
        "date": datetime.now().strftime("%Y-%m-%d")
    })
    with open(ANSWER_BANK_FILE, "w") as f:
        json.dump(bank, f, indent=4)
    log_action(user, "VERIFY_ANSWER", f"Added Q&A for {product}")

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
    page_title="AuditFlow",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- THEME & SESSION STATE ---
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "Light Mode" # Default to Light Mode

# INITIALIZE SESSION STATE
if "auth_stage" not in st.session_state:
    st.session_state.auth_stage = "login"
if "user_profile" not in st.session_state or "first_name" not in st.session_state.user_profile:
    st.session_state.user_profile = {
        "first_name": "John",
        "last_name": "Smith",
        "email": "john.smith@auditflow.io",
        "phone": "555-0199",
        "title": "Sr. Security Analyst",
        "role": "Administrator"
    }

def get_theme_css(mode):
    base_css = """
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    /* Popover Menu Tightening */
    div[data-testid="stPopoverBody"] > div { padding: 10px !important; }
    div[data-testid="stPopoverBody"] hr { margin: 10px 0 !important; }
    """
    
    sidebar_btn_css = """
    section[data-testid="stSidebar"] button {
        background-color: #F3F4F6 !important;
        color: #111827 !important;
        font-weight: 600 !important;
        border: none !important;
    }
    section[data-testid="stSidebar"] button:hover {
        background-color: #E5E7EB !important;
        color: #000000 !important;
    }
    """

    if mode == "Pro (Default)":
        return base_css + sidebar_btn_css + """
        section[data-testid="stSidebar"] { background-color: #111827; color: white; }
        section[data-testid="stSidebar"] * { color: #E5E7EB !important; }
        .stApp { background-color: #F9FAFB; color: #111827; }
        div[data-testid="stMetric"] { background-color: #ffffff; border: 1px solid #E5E7EB; border-radius: 8px; padding: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        """
    elif mode == "Dark Mode":
        return base_css + sidebar_btn_css + """
        section[data-testid="stSidebar"] { background-color: #1f1f1f; }
        .stApp { background-color: #0E1117; color: #E0E0E0; }
        div[data-testid="stMetric"] { background-color: #262730; border: 1px solid #444; border-radius: 8px; padding: 15px; }
        """
    elif mode == "Light Mode":
        return base_css + sidebar_btn_css + """
        section[data-testid="stSidebar"] { background-color: #F0F2F6; }
        .stApp { background-color: #FFFFFF; color: #333; }
        """
    return base_css

st.markdown(f"<style>{get_theme_css(st.session_state.theme_mode)}</style>", unsafe_allow_html=True)

# --- CUSTOM HEADER FUNCTION ---
def show_header(title):
    col_title, col_profile = st.columns([6, 1])
    with col_title:
        st.markdown(f"# {title}")
    with col_profile:
        fname = st.session_state.user_profile.get('first_name', 'U')
        lname = st.session_state.user_profile.get('last_name', 'U')
        initials = f"{fname[0]}{lname[0]}"
        
        with st.popover(f"👤 {initials}", use_container_width=True):
            st.markdown(f"**{fname} {lname}**")
            st.caption(st.session_state.user_profile.get('title', 'User'))
            st.markdown("---")
            if st.button("Log Out", key="logout_top", use_container_width=True):
                st.session_state.auth_stage = "login"
                st.rerun()

# --- AUTHENTICATION FLOW ---
if st.session_state.auth_stage != "authenticated":
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        
        # 1. LOGIN SCREEN
        if st.session_state.auth_stage == "login":
            st.markdown("## 🛡️ AuditFlow Secure Login")
            st.info("Identity Provider: Azure AD")
            
            with st.form("login_form"):
                st.text_input("Username", value="john.smith@auditflow.io")
                st.text_input("Password", type="password", value="password123")
                if st.form_submit_button("Sign In", type="primary", use_container_width=True):
                    with st.spinner("Verifying Credentials..."):
                        time.sleep(0.5)
                        st.session_state.auth_stage = "mfa"
                        st.rerun()
            
            if st.button("Forgot Password?", type="tertiary"):
                st.session_state.auth_stage = "forgot_password"
                st.rerun()

        # 2. MFA SCREEN
        elif st.session_state.auth_stage == "mfa":
            st.markdown("## 🔐 MFA Challenge")
            st.warning("Enter the code sent to +1 (555) ***-0199")
            
            with st.form("mfa_form"):
                code = st.text_input("Authentication Code", placeholder="123456")
                if st.form_submit_button("Verify", type="primary", use_container_width=True):
                    with st.spinner("Verifying Token..."):
                        time.sleep(1)
                        st.session_state.auth_stage = "authenticated"
                        log_action("System", "USER_LOGIN", "MFA Verified Successfully")
                        st.rerun()
            
            if st.button("← Back to Login"):
                st.session_state.auth_stage = "login"
                st.rerun()

        # 3. FORGOT PASSWORD
        elif st.session_state.auth_stage == "forgot_password":
            st.markdown("## 🔑 Password Reset")
            st.write("Enter your email to receive a secure reset link.")
            email = st.text_input("Email Address")
            if st.button("Send Reset Link", type="primary", use_container_width=True):
                if email:
                    st.success(f"Reset link sent to {email}!")
                    time.sleep(2)
                    st.session_state.auth_stage = "login"
                    st.rerun()
            
            if st.button("← Back"):
                st.session_state.auth_stage = "login"
                st.rerun()

    st.stop() 

# --- MAIN APP START ---

# --- SIDEBAR ---
with st.sidebar:
    st.title("🛡️ AuditFlow")
    st.caption("Enterprise Compliance")
    st.markdown("---")
    
    # POP-OUT MENU (Selectbox)
    page = st.selectbox("Navigation", [
        "Executive Dashboard", 
        "Auto-Fill (Beta)", 
        "Answer Bank", 
        "Gap Analysis",
        "My Projects", 
        "Questionnaire Agent", 
        "Knowledge Base", 
        "Settings"
    ])
    
    st.markdown("---")
    api_key = os.getenv("OPENAI_API_KEY")
    status_icon = "🟢" if api_key else "🟡"
    st.caption(f"{status_icon} AI Engine: Online")

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
    show_header("Executive Dashboard")
    st.markdown(f"Welcome back, **{st.session_state.user_profile.get('first_name', 'User')}**. Here is your compliance posture for today.")
    st.markdown("<br>", unsafe_allow_html=True)
    
    reg = load_registry()
    files_count = len(reg)
    pending_tasks = 12 
    
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Security Posture", "Secure", "No Critical Flags")
    with col2: st.metric("Active Audits", "3", "+1 This Month")
    with col3: st.metric("KB Assets Indexed", f"{files_count}", "Live Documents")
    with col4: st.metric("Pending Tasks", f"{pending_tasks}", "-2 Since Yesterday", delta_color="inverse")

    st.divider()

    col_left, col_right = st.columns([2, 1])
    with col_left:
        st.subheader("📊 Audit Readiness Status")
        chart_data = pd.DataFrame({'Status': ['Completed', 'In Review', 'Drafting', 'Not Started'], 'Items': [85, 12, 15, 8]})
        c = alt.Chart(chart_data).mark_bar().encode(x='Items', y=alt.Y('Status', sort=None), color=alt.Color('Status', scale=alt.Scale(scheme='greens'))).properties(height=250)
        st.altair_chart(c, use_container_width=True)

    with col_right:
        st.subheader("⚡ Activity Feed")
        if os.path.exists(AUDIT_LOG_FILE):
            df_log = pd.read_csv(AUDIT_LOG_FILE).tail(5).sort_values(by="Timestamp", ascending=False)
            for index, row in df_log.iterrows():
                icon = "🤖" if row['User'] == "System" else "👤"
                st.markdown(f"**{icon} {row['Action']}**")
                st.caption(f"{row['Details']}")
                st.markdown("---")
        else:
            st.info("No recent activity.")

# --- PAGE 2: AUTO-FILL WIZARD ---
elif page == "Auto-Fill (Beta)":
    show_header("Auto-Fill Assistant")
    st.markdown("Upload a raw vendor questionnaire (Excel/CSV) to automatically answer all questions.")
    
    uploaded_file = st.file_uploader("1. Upload Questionnaire", type=["xlsx", "csv"])
    
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'): df = pd.read_csv(uploaded_file)
            else: df = pd.read_excel(uploaded_file)
            
            st.success(f"Loaded {len(df)} rows.")
            st.markdown("#### 2. Map Columns")
            cols = df.columns.tolist()
            question_col = st.selectbox("Which column contains the Questions?", cols)
            
            if st.button("🚀 Auto-Fill Answers", type="primary"):
                if not st.session_state.agent.vector_db:
                    st.error("Knowledge Base is empty!")
                else:
                    questions = df[question_col].astype(str).tolist()
                    with st.spinner("Analyzing questions against Knowledge Base..."):
                        results_df = st.session_state.agent.generate_responses(questions)
                    
                    df["AI_Response"] = results_df["AI_Response"]
                    df["Evidence_Source"] = results_df["Evidence"]
                    df["Status"] = results_df["AI_Response"].apply(lambda x: "Review" if "Review Required" in str(x) else "Draft")
                    
                    st.success("Processing Complete!")
                    st.dataframe(df)
                    
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Download Completed Questionnaire", csv, "completed_questionnaire.csv", "text/csv", key='download-csv')
                    log_action("User", "AUTO_FILL", f"Processed {len(df)} questions from {uploaded_file.name}")
        except Exception as e: st.error(f"Error reading file: {e}")

# --- PAGE 3: ANSWER BANK ---
elif page == "Answer Bank":
    show_header("Answer Bank")
    st.info("Verified 'Golden Record' answers. The AI checks here first before searching documents.")
    
    bank = load_answer_bank()
    
    col1, col2 = st.columns([4, 1])
    with col1:
        search_term = st.text_input("🔎 Search known answers...", placeholder="e.g. MFA, Encryption, Backup")
    with col2:
        if st.button("➕ Add New", use_container_width=True):
            st.session_state.adding_new = True

    if bank:
        df_bank = pd.DataFrame(bank)
        if search_term:
            df_bank = df_bank[
                df_bank['question'].str.contains(search_term, case=False) | 
                df_bank['answer'].str.contains(search_term, case=False) |
                df_bank['product'].str.contains(search_term, case=False)
            ]
        
        st.dataframe(
            df_bank, 
            use_container_width=True, 
            column_config={
                "question": "Standard Question", 
                "answer": "Verified Answer",
                "product": "Product",
                "subsidiary": "Subsidiary",
                "verified_by": "Owner",
                "date": "Last Updated"
            },
            hide_index=True
        )
    else:
        st.info("Answer Bank is empty. Verify AI responses to add them here.")

    if st.session_state.get("adding_new", False):
        st.divider()
        with st.form("new_entry"):
            st.markdown("#### Add Trusted Answer")
            col_a, col_b = st.columns(2)
            with col_a:
                prod = st.text_input("Product", placeholder="e.g. Cloud Platform")
            with col_b:
                sub = st.text_input("Subsidiary", placeholder="e.g. North America")
            
            q = st.text_input("Question")
            a = st.text_area("Approved Answer")
            
            if st.form_submit_button("Save to Bank"):
                save_to_answer_bank(q, a, st.session_state.user_profile["last_name"], prod, sub)
                st.success("Added!")
                st.session_state.adding_new = False
                st.rerun()

# --- PAGE 4: GAP ANALYSIS ---
elif page == "Gap Analysis":
    show_header("Strategic Gap Analysis")
    st.markdown("Scan your knowledge base against common compliance frameworks.")
    
    framework = st.selectbox("Select Framework", ["SOC 2 Type II", "ISO 27001:2022", "NIST 800-53"])
    
    if st.button("🔍 Run Gap Analysis", type="primary"):
        with st.spinner(f"Scanning documents against {framework} controls..."):
            time.sleep(2)
            col1, col2, col3 = st.columns(3)
            with col1: st.metric("Controls Covered", "85%", "+5% vs Last Scan")
            with col2: st.metric("Missing Policies", "3", "Critical")
            with col3: st.metric("Evidence Strength", "Medium", "Needs Improvement")
            
            st.divider()
            st.subheader("⚠️ Missing or Weak Controls")
            issues = [
                {"Control": "CC-6.1", "Area": "Vulnerability Management", "Status": "Missing", "Suggestion": "Upload a 'Vulnerability Scanning Policy'"},
                {"Control": "CC-8.1", "Area": "Change Management", "Status": "Partial", "Suggestion": "Current 'DevOps Guide' lacks rollback procedures."},
                {"Control": "A.12.3", "Area": "Backup", "Status": "Verified", "Suggestion": "None. 'Backup_Policy_2025.pdf' covers this."}
            ]
            st.dataframe(pd.DataFrame(issues), use_container_width=True, hide_index=True)

# --- PAGE 5: ACTIVE QUESTIONNAIRES ---
elif page == "My Projects":
    show_header("Active Questionnaires")
    st.info("Select a project below to view details and manage status.")
    
    projects = pd.DataFrame({
        "Project Name": ["SoundThinking SIG 2026", "Internal ISO Audit", "Vendor A - CAIQ Lite"],
        "Due Date": ["Feb 28, 2026", "Mar 15, 2026", "Jan 10, 2026"],
        "Progress": [65, 20, 90],
        "Type": ["SIG Core", "ISO 27001", "CAIQ"]
    })
    
    event = st.dataframe(projects, use_container_width=True, hide_index=True, selection_mode="single-row", on_select="rerun", column_config={"Progress": st.column_config.ProgressColumn("Completion", format="%d%%", min_value=0, max_value=100)})
    
    if len(event.selection.rows) > 0:
        selected_index = event.selection.rows[0]
        selected_project = projects.iloc[selected_index]
        st.divider()
        st.subheader(f"📂 Managing: {selected_project['Project Name']}")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"**Due Date:** {selected_project['Due Date']}")
            st.button("📅 Change Deadline", key="btn_date")
        with c2:
            st.markdown(f"**Type:** {selected_project['Type']}")
            st.button("📤 Export Draft", key="btn_export")
        with c3:
            st.markdown(f"**Status:** {selected_project['Progress']}% Complete")
            if st.button("✅ Mark Complete", key="btn_complete", type="primary"):
                st.balloons()
                st.success("Project marked as complete!")

# --- PAGE 6: AI AGENT ---
elif page == "Questionnaire Agent":
    show_header("Vendor Response Agent")
    
    with st.expander("ℹ️ How to use this Agent"):
        st.markdown("""
        1. **Ask a question:** Type naturally (e.g., "Do we encrypt data at rest?").
        2. **Review Evidence:** The AI cites the specific document name. Click "Verified Source" to see details.
        3. **Save to Answer Bank:** If the answer is perfect, add it to the "Answer Bank" so the AI remembers it for next time.
        """)

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
                        if evidence and evidence != "No Source": 
                            with st.expander("🔍 Verified Source"): 
                                st.markdown(evidence)
                            # Button to Add to Bank
                            if st.button("💾 Verified? Add to Answer Bank"):
                                # Default generic product/sub for quick add
                                save_to_answer_bank(prompt, answer, st.session_state.user_profile["last_name"], "General", "All")
                                st.success("Saved to Golden Record!")
                        st.session_state.messages.append({"role": "assistant", "content": answer, "evidence": evidence})
                        log_action("User", "QUERY_AI", prompt[:50] + "...")
                    else: st.error("No response generated.")
                except Exception as e: st.error(f"Error: {e}")

# --- PAGE 7: KNOWLEDGE BASE ---
elif page == "Knowledge Base":
    show_header("Knowledge Base")
    st.write("Manage security policies. Changes here automatically update the AI.")

    with st.expander("📤 Upload New Documents", expanded=False):
        uploaded_files = st.file_uploader("Select Files (PDF, DOCX, XLSX)", accept_multiple_files=True)
        if uploaded_files:
            st.markdown("#### 📝 Document Details")
            
            # Global Review Date for the batch
            review_date = st.date_input("Next Review Date", value=datetime.now() + timedelta(days=365))
            
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
                        "review_date": str(review_date),
                        "uploaded_by": st.session_state.user_profile.get("last_name", "Admin")
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
        files = [f for f in os.listdir("data") if f != "registry.json" and f != "answer_bank.json"]
        if files:
            for f in files:
                meta = registry.get(f, {"description": "No description", "upload_date": "Unknown", "review_date": "Unknown"})
                with st.container():
                    c1, c2, c3, c4, c5 = st.columns([0.5, 2, 3, 1.5, 1])
                    with c1: st.markdown("📄")
                    with c2: 
                        st.markdown(f"**{f}**")
                        st.caption(f"📅 Uploaded: {meta['upload_date']}")
                        if 'review_date' in meta:
                            st.caption(f"⏰ Review By: {meta['review_date']}")
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

# --- PAGE 8: SETTINGS ---
elif page == "Settings":
    show_header("Settings")
    tab1, tab2, tab3, tab4 = st.tabs(["Appearance", "Audit Log", "User Profile", "Roles & Permissions"])
    
    with tab1:
        st.markdown("### 🎨 Interface Theme")
        selected_theme = st.radio("Choose Theme", ["Pro (Default)", "Dark Mode", "Light Mode"], index=["Pro (Default)", "Dark Mode", "Light Mode"].index(st.session_state.theme_mode))
        if selected_theme != st.session_state.theme_mode:
            st.session_state.theme_mode = selected_theme
            st.rerun()
            
    with tab2:
        st.markdown("### 📜 System Audit Logs")
        st.caption("Immutable record of system actions.")
        if os.path.exists(AUDIT_LOG_FILE):
            df_log = pd.read_csv(AUDIT_LOG_FILE).sort_values(by="Timestamp", ascending=False)
            log_text = ""
            for index, row in df_log.iterrows():
                log_text += f"[{row['Timestamp']}] {row['User']} performed {row['Action']}: {row['Details']}\n"
            st.code(log_text, language="log")
            st.download_button("📥 Download Logs (CSV)", df_log.to_csv(index=False).encode('utf-8'), "audit_logs.csv", "text/csv")
        else: st.info("No logs recorded yet.")
            
    with tab3:
        st.markdown("### 👤 User Profile")
        c1, c2 = st.columns(2)
        with c1:
            new_fname = st.text_input("First Name", value=st.session_state.user_profile.get("first_name", ""))
            new_lname = st.text_input("Last Name", value=st.session_state.user_profile.get("last_name", ""))
            new_email = st.text_input("Email", value=st.session_state.user_profile.get("email", ""))
        with c2:
            new_title = st.text_input("Job Title", value=st.session_state.user_profile.get("title", ""))
            new_phone = st.text_input("Phone Number", value=st.session_state.user_profile.get("phone", ""))
            new_role = st.text_input("System Role", value=st.session_state.user_profile.get("role", "Viewer"), disabled=True)
            
        if st.button("Update Profile"):
            st.session_state.user_profile.update({"first_name": new_fname, "last_name": new_lname, "email": new_email, "title": new_title, "phone": new_phone})
            st.success("Profile Updated!")
            st.rerun()

    with tab4:
        st.markdown("### 🔑 Role Management")
        st.caption("Manage access levels for the organization.")
        if "role_data" not in st.session_state:
            st.session_state.role_data = pd.DataFrame({"Role": ["Administrator", "Analyst", "Auditor", "Viewer"], "Write Access": [True, True, False, False], "Delete Access": [True, False, False, False], "AI Access": [True, True, True, False]})
        edited_df = st.data_editor(st.session_state.role_data, num_rows="dynamic", use_container_width=True, key="role_editor")
        if st.button("💾 Save Permission Changes", type="primary"):
            st.session_state.role_data = edited_df
            st.success("Permissions updated successfully!")
            log_action("Admin", "UPDATE_ROLES", "Modified system role permissions")
