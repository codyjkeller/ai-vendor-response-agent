import streamlit as st
import pandas as pd
import os
import sys
import json
import csv
import time
import altair as alt
import openpyxl
from io import BytesIO
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
    if not any(entry['question'] == question for entry in bank):
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
        return True
    return False

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

def navigate_to(page_name):
    st.session_state.page_selection = page_name
    st.rerun()

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="AuditFlow",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- THEME & SESSION STATE ---
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "Light Mode"

if "auth_stage" not in st.session_state:
    st.session_state.auth_stage = "login"
if "page_selection" not in st.session_state:
    st.session_state.page_selection = "Executive Dashboard"
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

# --- HEADER ---
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

# --- AUTH FLOW ---
if st.session_state.auth_stage != "authenticated":
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        if st.session_state.auth_stage == "login":
            st.markdown("## AuditFlow Secure Login")
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

        elif st.session_state.auth_stage == "mfa":
            st.markdown("## MFA Challenge")
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

        elif st.session_state.auth_stage == "forgot_password":
            st.markdown("## Password Reset")
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

# --- MAIN APP ---
with st.sidebar:
    st.title("AuditFlow")
    st.caption("Enterprise Compliance")
    st.markdown("---")
    
    nav_options = [
        "Executive Dashboard", "Auto-Fill (Beta)", "Answer Bank", "Gap Analysis",
        "My Projects", "Questionnaire Agent", "Knowledge Base", "Settings"
    ]
    
    try:
        current_index = nav_options.index(st.session_state.page_selection)
    except ValueError:
        current_index = 0
        st.session_state.page_selection = nav_options[0]

    selected_page = st.selectbox("Navigation", nav_options, index=current_index)
    if selected_page != st.session_state.page_selection:
        st.session_state.page_selection = selected_page
        st.rerun()
    
    st.markdown("---")
    api_key = os.getenv("OPENAI_API_KEY")
    status_icon = "🟢" if api_key else "🟡"
    st.caption(f"{status_icon} AI Engine: Online")

# --- INIT ---
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

# --- DASHBOARD ---
if st.session_state.page_selection == "Executive Dashboard":
    show_header("Executive Dashboard")
    st.markdown(f"Welcome back, **{st.session_state.user_profile.get('first_name', 'User')}**. Compliance status is **Nominal**.")
    st.markdown("<br>", unsafe_allow_html=True)
    
    reg = load_registry()
    files_count = len(reg)
    pending_tasks = 12 
    
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Security Posture", "Secure", "No Critical Flags")
    with col2: st.metric("Active Audits", "3", "+1 This Month")
    with col3: st.metric("KB Assets Indexed", f"{files_count}", "Live Documents")
    with col4: st.metric("Pending Tasks", f"{pending_tasks}", "-2 Since Yesterday", delta_color="inverse")

    st.markdown("### Quick Actions")
    qa_col1, qa_col2, qa_col3, qa_col4 = st.columns(4)
    with qa_col1:
        if st.button("📄 Start Auto-Fill", use_container_width=True): navigate_to("Auto-Fill (Beta)")
    with qa_col2:
        if st.button("📤 Upload Policy", use_container_width=True): navigate_to("Knowledge Base")
    with qa_col3:
        if st.button("🔍 Run Gap Analysis", use_container_width=True): navigate_to("Gap Analysis")
    with qa_col4:
        if st.button("🧠 Search Knowledge", use_container_width=True): navigate_to("Questionnaire Agent")

    st.divider()

    col_left, col_right = st.columns([2, 1])
    with col_left:
        st.subheader("Audit Readiness Status")
        chart_data = pd.DataFrame({'Status': ['Completed', 'In Review', 'Drafting', 'Not Started'], 'Items': [85, 12, 15, 8]})
        c = alt.Chart(chart_data).mark_bar().encode(x='Items', y=alt.Y('Status', sort=None), color=alt.Color('Status', scale=alt.Scale(scheme='greens'))).properties(height=250)
        st.altair_chart(c, use_container_width=True)

    with col_right:
        st.subheader("Activity Feed")
        if os.path.exists(AUDIT_LOG_FILE):
            df_log = pd.read_csv(AUDIT_LOG_FILE).tail(5).sort_values(by="Timestamp", ascending=False)
            for index, row in df_log.iterrows():
                icon = "🤖" if row['User'] == "System" else "👤"
                st.markdown(f"**{icon} {row['Action']}**")
                st.caption(f"{row['Details']}")
                st.markdown("---")
        else:
            st.info("No recent activity.")

# --- AUTO-FILL (TRUE EXCEL) ---
elif st.session_state.page_selection == "Auto-Fill (Beta)":
    show_header("Auto-Fill Assistant")
    st.markdown("Upload a raw vendor questionnaire (.xlsx) to automatically answer all questions while preserving formatting.")
    
    uploaded_file = st.file_uploader("1. Upload Excel File", type=["xlsx"])
    
    if uploaded_file:
        try:
            # Load workbook using openpyxl for preservation
            wb = openpyxl.load_workbook(uploaded_file)
            sheet_names = wb.sheetnames
            selected_sheet = st.selectbox("Select Sheet", sheet_names)
            ws = wb[selected_sheet]
            
            # Preview Data to pick columns
            data = ws.values
            cols = next(data) # Get headers
            df_preview = pd.DataFrame(data, columns=cols)
            
            st.markdown("#### 2. Map Columns")
            question_col_name = st.selectbox("Column with Questions", cols)
            answer_col_name = st.selectbox("Column for Answers (Target)", cols)
            
            # Find column indices (1-based for openpyxl)
            q_idx = None
            a_idx = None
            for idx, col in enumerate(cols, 1):
                if col == question_col_name: q_idx = idx
                if col == answer_col_name: a_idx = idx
            
            if st.button("🚀 Run Auto-Fill", type="primary"):
                if not st.session_state.agent.vector_db:
                    st.error("Knowledge Base is empty!")
                else:
                    progress_bar = st.progress(0)
                    total_rows = ws.max_row
                    
                    # Iterate rows starting after header
                    for i, row in enumerate(ws.iter_rows(min_row=2, max_row=total_rows), 2):
                        cell_q = row[q_idx-1] # 0-based index for row tuple
                        cell_a = row[a_idx-1]
                        
                        question_text = str(cell_q.value) if cell_q.value else ""
                        
                        if question_text and len(question_text) > 5:
                            # Generate Answer
                            response_df = st.session_state.agent.generate_responses([question_text])
                            if not response_df.empty:
                                ai_answer = response_df.iloc[0]['AI_Response']
                                # Write to cell directly
                                ws.cell(row=i, column=a_idx, value=ai_answer)
                        
                        progress_bar.progress(min(i / total_rows, 1.0))
                    
                    # Save to BytesIO
                    output = BytesIO()
                    wb.save(output)
                    output.seek(0)
                    
                    st.success("Processing Complete! Formatting Preserved.")
                    st.download_button(
                        label="📥 Download Filled Excel",
                        data=output,
                        file_name=f"filled_{uploaded_file.name}",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    log_action("User", "AUTO_FILL", f"Processed {uploaded_file.name}")

        except Exception as e: st.error(f"Error reading file: {e}")

# --- ANSWER BANK ---
elif st.session_state.page_selection == "Answer Bank":
    show_header("Answer Bank")
    st.info("Verified 'Golden Record' answers.")
    
    bank = load_answer_bank()
    col1, col2 = st.columns([4, 1])
    with col1: search_term = st.text_input("🔎 Search...", placeholder="e.g. MFA")
    with col2: 
        if st.button("➕ Add New", use_container_width=True): st.session_state.adding_new = True

    if bank:
        df_bank = pd.DataFrame(bank)
        if search_term:
            df_bank = df_bank[
                df_bank['question'].str.contains(search_term, case=False) | 
                df_bank['answer'].str.contains(search_term, case=False) |
                df_bank['product'].str.contains(search_term, case=False)
            ]
        st.dataframe(df_bank, use_container_width=True, hide_index=True)
    else: st.info("Answer Bank is empty.")

    if st.session_state.get("adding_new", False):
        st.divider()
        with st.form("new_entry"):
            st.markdown("#### Add Trusted Answer")
            col_a, col_b = st.columns(2)
            with col_a: prod = st.text_input("Product")
            with col_b: sub = st.text_input("Subsidiary")
            q = st.text_input("Question")
            a = st.text_area("Approved Answer")
            if st.form_submit_button("Save"):
                save_to_answer_bank(q, a, st.session_state.user_profile["last_name"], prod, sub)
                st.success("Added!")
                st.session_state.adding_new = False
                st.rerun()

# --- GAP ANALYSIS ---
elif st.session_state.page_selection == "Gap Analysis":
    show_header("Gap Analysis")
    framework = st.selectbox("Select Framework", ["SOC 2 Type II", "ISO 27001:2022", "NIST 800-53"])
    if st.button("🔍 Run Scan", type="primary"):
        with st.spinner(f"Scanning against {framework}..."):
            time.sleep(2)
            col1, col2, col3 = st.columns(3)
            with col1: st.metric("Coverage", "85%", "+5%")
            with col2: st.metric("Missing", "3", "Critical")
            with col3: st.metric("Strength", "Medium", "Needs Improvement")
            st.divider()
            issues = [
                {"Control": "CC-6.1", "Area": "Vuln Mgmt", "Status": "Missing", "Suggestion": "Upload 'Vuln Scan Policy'"},
                {"Control": "CC-8.1", "Area": "Change Mgmt", "Status": "Partial", "Suggestion": "Missing rollback procedures."},
            ]
            st.dataframe(pd.DataFrame(issues), use_container_width=True, hide_index=True)

# --- PROJECTS ---
elif st.session_state.page_selection == "My Projects":
    show_header("Active Questionnaires")
    projects = pd.DataFrame({
        "Project Name": ["SoundThinking SIG 2026", "Internal ISO Audit", "Vendor A - CAIQ Lite"],
        "Due Date": ["Feb 28, 2026", "Mar 15, 2026", "Jan 10, 2026"],
        "Progress": [65, 20, 90],
        "Type": ["SIG Core", "ISO 27001", "CAIQ"]
    })
    event = st.dataframe(projects, use_container_width=True, hide_index=True, selection_mode="single-row", on_select="rerun", column_config={"Progress": st.column_config.ProgressColumn("Completion", format="%d%%", min_value=0, max_value=100)})
    if len(event.selection.rows) > 0:
        st.info(f"Selected: {projects.iloc[event.selection.rows[0]]['Project Name']}")

# --- AGENT ---
elif st.session_state.page_selection == "Questionnaire Agent":
    show_header("Vendor Response Agent")
    if len(st.session_state.messages) > 0:
        col_export, _ = st.columns([1, 5])
        with col_export:
            export_data = [{"Role": m["role"], "Content": m["content"], "Evidence": m.get("evidence", "")} for m in st.session_state.messages]
            st.download_button(label="📥 Download Report", data=pd.DataFrame(export_data).to_csv(index=False).encode('utf-8'), file_name="audit_report.csv", mime="text/csv")
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("evidence"): with st.expander("🔍 Source"): st.markdown(message["evidence"])

    if prompt := st.chat_input("Ask a question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    df = st.session_state.agent.generate_responses([prompt])
                    if not df.empty:
                        answer, evidence = df.iloc[0]['AI_Response'], df.iloc[0]['Evidence']
                        st.markdown(answer)
                        if evidence and evidence != "No Source": 
                            with st.expander("🔍 Source"): st.markdown(evidence)
                            if st.button("💾 Save to Bank"):
                                save_to_answer_bank(prompt, answer, st.session_state.user_profile["last_name"], "General", "All")
                                st.success("Saved!")
                        st.session_state.messages.append({"role": "assistant", "content": answer, "evidence": evidence})
                        log_action("User", "QUERY_AI", prompt[:50] + "...")
                    else: st.error("No response.")
                except Exception as e: st.error(f"Error: {e}")

# --- KB ---
elif st.session_state.page_selection == "Knowledge Base":
    show_header("Knowledge Base")
    with st.expander("📤 Upload Documents", expanded=False):
        uploaded_files = st.file_uploader("Select Files", accept_multiple_files=True)
        if uploaded_files:
            review_date = st.date_input("Next Review Date", value=datetime.now() + timedelta(days=365))
            file_meta = {}
            for f in uploaded_files: file_meta[f.name] = st.text_input(f"Desc: {f.name}", key=f"d_{f.name}")
            if st.button("Process Files", type="primary"):
                os.makedirs("data", exist_ok=True)
                registry = load_registry()
                for f in uploaded_files:
                    with open(os.path.join("data", f.name), "wb") as w: w.write(f.getbuffer())
                    registry[f.name] = {"description": file_meta[f.name], "upload_date": datetime.now().strftime("%Y-%m-%d"), "review_date": str(review_date)}
                save_registry(registry)
                create_vector_db()
                st.session_state.agent = VendorResponseAgent()
                st.rerun()

    st.divider()
    registry = load_registry()
    if os.path.exists("data"):
        files = [f for f in os.listdir("data") if f.endswith(('.pdf', '.docx', '.xlsx', '.txt'))]
        if files:
            for f in files:
                meta = registry.get(f, {})
                c1, c2, c3 = st.columns([3, 2, 1])
                with c1: st.markdown(f"**{f}**\n<small>{meta.get('description', '')}</small>", unsafe_allow_html=True)
                with c2: st.caption(f"📅 {meta.get('upload_date', 'N/A')} | ⏰ {meta.get('review_date', 'N/A')}")
                with c3: 
                    if st.button("🗑️", key=f"del_{f}"):
                        delete_file(f)
                        create_vector_db()
                        st.session_state.agent = VendorResponseAgent()
                        st.rerun()
        else: st.info("No documents found.")

# --- SETTINGS ---
elif st.session_state.page_selection == "Settings":
    show_header("Settings")
    tab1, tab2, tab3 = st.tabs(["Theme", "Logs", "Profile"])
    with tab1:
        st.radio("Theme", ["Pro (Default)", "Dark Mode", "Light Mode"], key="theme_selector")
        if st.session_state.theme_selector != st.session_state.theme_mode:
            st.session_state.theme_mode = st.session_state.theme_selector
            st.rerun()
    with tab2:
        if os.path.exists(AUDIT_LOG_FILE): st.dataframe(pd.read_csv(AUDIT_LOG_FILE).sort_values(by="Timestamp", ascending=False), use_container_width=True)
    with tab3:
        st.text_input("First Name", value=st.session_state.user_profile.get("first_name"))
        st.text_input("Last Name", value=st.session_state.user_profile.get("last_name"))
        st.button("Save Profile")
