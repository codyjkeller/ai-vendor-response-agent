import streamlit as st
import pandas as pd
import os
import sys
import time
import html
import openpyxl
import altair as alt
from io import BytesIO
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session

# --- Path Setup ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from agent import VendorResponseAgent
from ingest import create_vector_db
from database import init_db, SessionLocal, User, Document, AnswerBank
from config import (
    DEMO_MODE, ADMIN_EMAILS, ALLOWED_UPLOAD_EXTENSIONS,
    ROLES, DEFAULT_ROLE, ADMIN_ROLES, WRITE_ROLES,
)
from security import sanitize_filename, safe_data_path, append_audit_log
from autofill import fill_worksheet

# --- CONFIGURATION ---
DATA_DIR = "data"
AUDIT_LOG_FILE = "audit_log.csv"
# Pages that show illustrative figures only. Hidden unless demo mode is on.
DEMO_ONLY_PAGES = ["Gap Analysis", "My Projects"]
os.makedirs(DATA_DIR, exist_ok=True)

# --- DATABASE INITIALIZATION ---
if "db_initialized" not in st.session_state:
    init_db()
    st.session_state.db_initialized = True

# --- HELPER FUNCTIONS ---

def get_db():
    return SessionLocal()

def log_action(user, action, details):
    # Quoted CSV with formula characters neutralized (see security.py)
    append_audit_log(AUDIT_LOG_FILE, user, action, details)

def current_user():
    """E-mail of the signed-in user, used for audit entries and attribution."""
    return st.session_state.get("user_profile", {}).get("email", "unknown")

def current_role():
    return st.session_state.get("user_profile", {}).get("role", DEFAULT_ROLE)

def can_write():
    return current_role() in WRITE_ROLES

def can_admin():
    return current_role() in ADMIN_ROLES

def is_overdue(doc):
    """True when a document's review date has passed (it is then not indexed)."""
    try:
        return date.fromisoformat(str(doc.review_date)) < date.today()
    except ValueError:
        return False

def oidc_configured():
    """True when an [auth] section exists in .streamlit/secrets.toml."""
    try:
        return "auth" in st.secrets
    except Exception:
        return False

# --- DB OPERATIONS ---

def db_get_answer_bank(search_term=None):
    db = get_db()
    query = db.query(AnswerBank)
    if search_term:
        search = f"%{search_term}%"
        query = query.filter(
            (AnswerBank.question.like(search)) | 
            (AnswerBank.answer.like(search)) | 
            (AnswerBank.product.like(search))
        )
    results = query.all()
    db.close()
    return [{
        "question": r.question, "answer": r.answer, 
        "product": r.product, "subsidiary": r.subsidiary, 
        "verified_by": r.verified_by, "date": r.date_added
    } for r in results]

def db_save_answer(question, answer, user, product, subsidiary):
    db = get_db()
    exists = db.query(AnswerBank).filter(AnswerBank.question == question).first()
    if not exists:
        new_entry = AnswerBank(
            question=question, answer=answer, 
            product=product, subsidiary=subsidiary,
            verified_by=user, date_added=datetime.now().strftime("%Y-%m-%d")
        )
        db.add(new_entry)
        db.commit()
        db.close()
        return True
    db.close()
    return False

def db_save_document(filename, desc, review_date, uploader):
    db = get_db()
    doc = db.query(Document).filter(Document.filename == filename).first()
    if not doc:
        doc = Document(
            filename=filename, description=desc,
            upload_date=datetime.now().strftime("%Y-%m-%d"),
            review_date=str(review_date), uploaded_by=uploader
        )
        db.add(doc)
    else:
        doc.description = desc
        doc.review_date = str(review_date)
    db.commit()
    db.close()

def db_get_documents():
    db = get_db()
    docs = db.query(Document).all()
    db.close()
    return docs

def db_delete_document(filename):
    db = get_db()
    doc = db.query(Document).filter(Document.filename == filename).first()
    if doc:
        db.delete(doc)
        db.commit()
    db.close()
    try:
        path = safe_data_path(DATA_DIR, filename)
    except ValueError:
        return
    if os.path.exists(path):
        os.remove(path)

# --- PAGE CONFIG ---
st.set_page_config(page_title="AuditFlow Enterprise", page_icon="🛡️", layout="wide", initial_sidebar_state="expanded")

# --- SESSION STATE ---
if "theme_mode" not in st.session_state: st.session_state.theme_mode = "Light Mode"
if "auth_stage" not in st.session_state: st.session_state.auth_stage = "login"
if "page_selection" not in st.session_state: st.session_state.page_selection = "Executive Dashboard"

# --- AUTHENTICATION GATE ---
# Outside demo mode the app fails closed: no identity provider, no access.
if not DEMO_MODE:
    if not oidc_configured():
        st.error("Authentication is not configured.")
        st.markdown(
            "Configure an OpenID Connect provider in `.streamlit/secrets.toml` "
            "(see the README section *Authentication*), or set "
            "`AUDITFLOW_DEMO_MODE=true` to run the demo with simulated sign-in and sample data."
        )
        st.stop()
    if not st.user.is_logged_in:
        _, c, _ = st.columns([1,1,1])
        with c:
            st.markdown("<br><br>## AuditFlow Sign In", unsafe_allow_html=True)
            st.button("Sign in with your identity provider", type="primary", use_container_width=True, on_click=st.login)
        st.stop()
    signed_in_email = str(st.user.get("email") or "").strip().lower()
    if not signed_in_email:
        st.error("Your identity provider did not return an e-mail address. Add the `email` scope.")
        st.stop()
    st.session_state.auth_stage = "authenticated"
    # A different person signed in during this browser session
    if st.session_state.get("user_profile", {}).get("email") != signed_in_email:
        st.session_state.pop("user_profile", None)

# Sync Session User with Database
if "user_profile" not in st.session_state:
    db = get_db()
    default_email = "john.smith@auditflow.io" if DEMO_MODE else signed_in_email
    user = db.query(User).filter(User.email == default_email).first()
    
    if not user and DEMO_MODE:
        user = User(
            email=default_email, first_name="John", last_name="Smith",
            title="Sr. Security Analyst", phone="555-0199", role="Administrator"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user:
        # First sign-in: least privilege unless listed in AUDITFLOW_ADMIN_EMAILS
        user = User(
            email=default_email,
            first_name=str(st.user.get("given_name") or ""), last_name=str(st.user.get("family_name") or ""),
            title="", phone="",
            role="Administrator" if default_email in ADMIN_EMAILS else DEFAULT_ROLE
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not DEMO_MODE and default_email in ADMIN_EMAILS and user.role != "Administrator":
        user.role = "Administrator"
        db.commit()
        db.refresh(user)
    
    st.session_state.user_profile = {
        "id": user.id, "first_name": user.first_name, "last_name": user.last_name,
        "email": user.email, "title": user.title, "phone": user.phone, "role": user.role
    }
    db.close()
else:
    # Pick up role changes made by an administrator since the last interaction
    db = get_db()
    user = db.query(User).filter(User.id == st.session_state.user_profile["id"]).first()
    if user: st.session_state.user_profile["role"] = user.role
    db.close()

def navigate_to(page_name):
    st.session_state.page_selection = page_name
    st.rerun()

def get_theme_css(mode):
    base = """
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    div[data-testid="stPopoverBody"] > div { padding: 10px !important; }
    .role-badge { background-color: #E0F2F1; color: #00695C; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; margin-top: 4px; margin-bottom: 8px; display: inline-block; }
    """
    sidebar = """
    section[data-testid="stSidebar"] button { background-color: #F3F4F6 !important; color: #111827 !important; font-weight: 600 !important; border: none !important; }
    section[data-testid="stSidebar"] button:hover { background-color: #E5E7EB !important; color: #000000 !important; }
    """
    if mode == "Dark Mode":
        return base + sidebar + """section[data-testid="stSidebar"] { background-color: #1f1f1f; } .stApp { background-color: #0E1117; color: #E0E0E0; } div[data-testid="stMetric"] { background-color: #262730; border: 1px solid #444; border-radius: 8px; padding: 15px; }"""
    else:
        return base + sidebar + """section[data-testid="stSidebar"] { background-color: #111827; color: white; } section[data-testid="stSidebar"] * { color: #E5E7EB !important; } .stApp { background-color: #F9FAFB; color: #111827; } div[data-testid="stMetric"] { background-color: #ffffff; border: 1px solid #E5E7EB; border-radius: 8px; padding: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }"""

st.markdown(f"<style>{get_theme_css(st.session_state.theme_mode)}</style>", unsafe_allow_html=True)

# --- HEADER ---
def show_header(title):
    c1, c2 = st.columns([6, 1])
    with c1: st.markdown(f"# {title}")
    with c2:
        u = st.session_state.user_profile
        initials = (f"{(u['first_name'] or '')[:1]}{(u['last_name'] or '')[:1]}" or u['email'][:1]).upper()
        with st.popover(f"👤 {initials}", use_container_width=True):
            st.markdown(f"**{u['first_name']} {u['last_name']}**")
            st.markdown(f"<span class='role-badge'>{html.escape(str(u['role']))}</span>", unsafe_allow_html=True)
            st.caption(u['title'])
            st.markdown("---")
            if st.button("⚙️ Manage Profile", use_container_width=True): navigate_to("Settings")
            if st.button("Log Out", key="logout_top", use_container_width=True):
                if not DEMO_MODE:
                    st.session_state.pop("user_profile", None)
                    st.logout()
                st.session_state.auth_stage = "login"
                st.rerun()

# --- AUTH FLOW ---
if st.session_state.auth_stage == "login":
    _, c, _ = st.columns([1,1,1])
    with c:
        st.markdown("<br><br>## AuditFlow Secure Login", unsafe_allow_html=True)
        st.warning("Demo mode: sign-in is simulated and no credentials are checked.")
        with st.form("login"):
            st.text_input("Username", value="john.smith@auditflow.io")
            st.text_input("Password", type="password")
            if st.form_submit_button("Sign In", type="primary", use_container_width=True):
                st.session_state.auth_stage = "mfa"
                st.rerun()
    st.stop()
elif st.session_state.auth_stage == "mfa":
    _, c, _ = st.columns([1,1,1])
    with c:
        st.markdown("<br><br>## MFA Challenge", unsafe_allow_html=True)
        st.warning("Enter code sent to +1 (555) ***-0199")
        if st.button("Verify 123456", type="primary", use_container_width=True):
            st.session_state.auth_stage = "authenticated"
            st.rerun()
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.title("AuditFlow")
    st.caption("Enterprise Compliance")
    st.markdown("---")
    pages = ["Executive Dashboard", "Auto-Fill (Beta)", "Answer Bank", "Gap Analysis", "My Projects", "Questionnaire Agent", "Knowledge Base", "Settings"]
    if not DEMO_MODE:
        pages = [p for p in pages if p not in DEMO_ONLY_PAGES]
    else:
        st.warning("Demo mode: simulated sign-in and sample data.")
    try: idx = pages.index(st.session_state.page_selection)
    except: idx = 0
    sel = st.selectbox("Navigation", pages, index=idx)
    if sel != st.session_state.page_selection:
        st.session_state.page_selection = sel
        st.rerun()
    st.markdown("---")
    st.caption(f"🟢 User: {st.session_state.user_profile['last_name'] or st.session_state.user_profile['email']}")

# --- INITIALIZATION ---
if "agent" not in st.session_state: st.session_state.agent = VendorResponseAgent()
if "messages" not in st.session_state: st.session_state.messages = []

# --- PAGE 1: DASHBOARD ---
if st.session_state.page_selection == "Executive Dashboard":
    show_header("Executive Dashboard")
    docs = db_get_documents()
    bank = db_get_answer_bank()
    
    c1, c2, c3, c4 = st.columns(4)
    if DEMO_MODE:
        # Illustrative figures, labelled as such
        with c1: st.metric("Security Posture (sample)", "Secure", "No Critical Flags")
        with c2: st.metric("Active Audits (sample)", "3", "+1 This Month")
    else:
        with c1: st.metric("Docs Past Review Date", sum(1 for d in docs if is_overdue(d)), "Not indexed", delta_color="off")
        with c2: st.metric("Answer Mode", "Search only" if st.session_state.agent.provider == "local" else st.session_state.agent.provider.title())
    with c3: st.metric("Indexed Docs", len(docs), "Live")
    with c4: st.metric("Answer Bank", len(bank), "Verified Q&A")

    st.markdown("### Quick Actions")
    q1, q2, q3, q4 = st.columns(4)
    with q1: 
        if st.button("📄 Start Auto-Fill", use_container_width=True): navigate_to("Auto-Fill (Beta)")
    with q2:
        if st.button("📤 Upload Policy", use_container_width=True): navigate_to("Knowledge Base")
    with q3:
        if DEMO_MODE and st.button("🔍 Run Gap Analysis", use_container_width=True): navigate_to("Gap Analysis")
    with q4:
        if st.button("🧠 Search Knowledge", use_container_width=True): navigate_to("Questionnaire Agent")

    st.divider()
    c_left, c_right = st.columns([2,1])
    with c_left:
        if DEMO_MODE:
            st.subheader("Audit Readiness (sample data)")
            chart_data = pd.DataFrame({'Status': ['Completed', 'In Review', 'Drafting', 'Not Started'], 'Items': [85, 12, 15, 8]})
            st.altair_chart(alt.Chart(chart_data).mark_bar().encode(x='Items', y=alt.Y('Status', sort=None), color='Status').properties(height=250), use_container_width=True)
        else:
            st.subheader("Knowledge Base Review Status")
            if docs:
                st.dataframe(pd.DataFrame([{"Document": d.filename, "Review Date": d.review_date, "Status": "Overdue (not indexed)" if is_overdue(d) else "Current"} for d in docs]), use_container_width=True, hide_index=True)
            else: st.info("No documents registered.")
    with c_right:
        st.subheader("Recent Activity")
        if os.path.exists(AUDIT_LOG_FILE):
            st.dataframe(pd.read_csv(AUDIT_LOG_FILE).tail(5).sort_values(by="Timestamp", ascending=False), use_container_width=True, hide_index=True)

# --- PAGE 2: AUTO-FILL (TRUE EXCEL) ---
elif st.session_state.page_selection == "Auto-Fill (Beta)":
    show_header("Auto-Fill Assistant")
    up_file = st.file_uploader("Upload Excel Questionnaire", type=["xlsx"])
    if up_file:
        try:
            wb = openpyxl.load_workbook(up_file)
            sheet = st.selectbox("Select Sheet", wb.sheetnames)
            ws = wb[sheet]
            rows = list(ws.values)
            if len(rows) > 0:
                cols = [str(c) for c in rows[0]]
                st.markdown("#### Map Columns")
                q_col = st.selectbox("Question Column", cols)
                a_col = st.selectbox("Answer Column", cols)
                st.markdown("#### Scope (optional)")
                sc1, sc2 = st.columns(2)
                with sc1: af_product = st.text_input("Product", help="Limits Answer Bank matches to this product and general entries.")
                with sc2: af_subsidiary = st.text_input("Subsidiary", help="Limits Answer Bank matches to this subsidiary and general entries.")
                
                if st.button("🚀 Run Auto-Fill", type="primary"):
                    if not st.session_state.agent.vector_db: st.error("KB Empty!")
                    elif q_col == a_col: st.error("Question and Answer columns must be different.")
                    else:
                        prog = st.progress(0)
                        q_idx = cols.index(q_col)
                        a_idx = cols.index(a_col)
                        # Only real answers go into the questionnaire (see autofill.py)
                        review_rows = fill_worksheet(ws, st.session_state.agent, q_idx, a_idx, product=af_product.strip() or None, subsidiary=af_subsidiary.strip() or None, on_progress=prog.progress)
                        
                        out = BytesIO()
                        wb.save(out)
                        out.seek(0)
                        n_filled = sum(1 for r in review_rows if not r["Result"].startswith("Left blank"))
                        st.success(f"Done! Formatting Preserved. {n_filled} answered, {len(review_rows) - n_filled} left blank for manual review.")
                        st.caption("AI Generated answers are drafts. Check each against its evidence before sending.")
                        if review_rows: st.dataframe(pd.DataFrame(review_rows), use_container_width=True, hide_index=True)
                        st.download_button("Download Result", out, f"filled_{up_file.name}", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                        log_action(current_user(), "AUTO_FILL", f"Processed {up_file.name}")
        except Exception as e: st.error(f"Error: {e}")

# --- PAGE 3: ANSWER Bank ---
elif st.session_state.page_selection == "Answer Bank":
    show_header("Answer Bank")
    c1, c2 = st.columns([4,1])
    with c1: search = st.text_input("Search...")
    with c2: 
        if can_write() and st.button("➕ Add New", use_container_width=True): st.session_state.adding_new = True
    
    bank_data = db_get_answer_bank(search)
    if bank_data:
        st.dataframe(bank_data, use_container_width=True)
    else: st.info("No entries found.")

    if st.session_state.get("adding_new") and can_write():
        st.divider()
        with st.form("new_ans"):
            st.write("Add Verified Answer")
            c_a, c_b = st.columns(2)
            with c_a: p = st.text_input("Product")
            with c_b: s = st.text_input("Subsidiary")
            q = st.text_input("Question")
            a = st.text_area("Answer")
            if st.form_submit_button("Save"):
                if db_save_answer(q, a, current_user(), p, s):
                    log_action(current_user(), "ADD_ANSWER", q[:50])
                    st.success("Saved!")
                    st.session_state.adding_new = False
                    st.rerun()
                else: st.warning("Duplicate question.")

# --- PAGE 4: GAP ANALYSIS (FULL RESTORED) ---
elif st.session_state.page_selection == "Gap Analysis" and DEMO_MODE:
    show_header("Strategic Gap Analysis")
    st.warning("Sample output. These results are illustrative and are not computed from your documents.")
    st.markdown("Scan your knowledge base against common compliance frameworks.")
    
    framework = st.selectbox("Select Framework", ["SOC 2 Type II", "ISO 27001:2022", "NIST 800-53"])
    
    if st.button("🔍 Run Gap Analysis", type="primary"):
        with st.spinner(f"Scanning documents against {framework} controls..."):
            time.sleep(1.5) # Simulation
            
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

# --- PAGE 5: ACTIVE PROJECTS (FULL RESTORED) ---
elif st.session_state.page_selection == "My Projects" and DEMO_MODE:
    show_header("Active Questionnaires")
    st.warning("Sample projects. Nothing on this page is stored.")
    st.info("Select a project below to view details and manage status.")
    
    projects = pd.DataFrame({
        "Project Name": ["Acme Corp SIG 2026", "Internal ISO Audit", "Vendor A - CAIQ Lite"],
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

# --- PAGE 6: AGENT (FULL RESTORED) ---
elif st.session_state.page_selection == "Questionnaire Agent":
    show_header("Vendor Response Agent")
    with st.expander("ℹ️ How to use this Agent"):
        st.markdown("1. **Ask a question:** Type naturally.\n2. **Review Evidence:** Click 'Verified Source'.\n3. **Save to Answer Bank:** Add good answers to the memory.")

    if len(st.session_state.messages) > 0:
        col_export, _ = st.columns([1, 5])
        with col_export:
            export_data = [{"Role": m["role"], "Content": m["content"], "Evidence": m.get("evidence", "")} for m in st.session_state.messages]
            st.download_button(label="📥 Download Report", data=pd.DataFrame(export_data).to_csv(index=False).encode('utf-8'), file_name="audit_report.csv", mime="text/csv")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("evidence"): 
                with st.expander("🔍 Source"): st.markdown(message["evidence"])

    if prompt := st.chat_input("Ask a question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    df = st.session_state.agent.generate_responses([prompt])
                    if not df.empty:
                        answer, evidence = df.iloc[0]['AI_Response'], df.iloc[0].get('Evidence')
                        if not isinstance(evidence, str): evidence = ""
                        st.markdown(answer)
                        st.session_state.pending_save = None
                        if evidence and evidence != "No Source": 
                            with st.expander("🔍 Source"): st.markdown(evidence)
                            # Offered below, outside this block: a button here never fires
                            # because the click reruns the script with no chat input.
                            if df.iloc[0]['Status'] == "🤖 AI Generated":
                                st.session_state.pending_save = {"question": prompt, "answer": answer}
                        st.session_state.messages.append({"role": "assistant", "content": answer, "evidence": evidence})
                        log_action(current_user(), "QUERY_AI", prompt[:50] + "...")
                    else: st.error("No response.")
                except Exception as e: st.error(f"Error: {e}")

    pending = st.session_state.get("pending_save")
    if pending and can_write():
        with st.form("save_to_bank"):
            st.markdown("**Save the last answer to the Answer Bank**")
            st.caption("Bank answers are reused as verified. Check the answer against its source and correct it here before saving.")
            reviewed_answer = st.text_area("Answer", pending["answer"])
            reviewed = st.checkbox("I have reviewed this answer and confirm it is accurate.")
            if st.form_submit_button("💾 Save to Bank"):
                if not reviewed: st.warning("Confirm you have reviewed the answer before saving.")
                # FIXED: Updated function name to match the DB helper
                elif db_save_answer(pending["question"], reviewed_answer, current_user(), "General", "All"):
                    log_action(current_user(), "SAVE_TO_BANK", pending["question"][:50])
                    st.session_state.pending_save = None
                    st.success("Saved to Answer Bank!")
                else: st.warning("Duplicate question.")

# --- PAGE 7: KNOWLEDGE BASE ---
elif st.session_state.page_selection == "Knowledge Base":
    show_header("Knowledge Base")
    if not can_write(): st.info("Your role is read-only. Uploading and deleting documents is disabled.")
    with st.expander("Upload Documents"):
        up_files = st.file_uploader("Select Files", accept_multiple_files=True, type=list(ALLOWED_UPLOAD_EXTENSIONS), disabled=not can_write())
        if up_files and can_write():
            r_date = st.date_input("Review Date", value=datetime.now() + timedelta(days=365))
            desc_map = {f.name: st.text_input(f"Desc: {f.name}") for f in up_files}
            if st.button("Process"):
                os.makedirs("data", exist_ok=True)
                rejected = []
                for f in up_files:
                    # The browser supplies the file name: strip any path and unsafe characters
                    try:
                        safe_name = sanitize_filename(f.name)
                        target = safe_data_path("data", safe_name)
                    except ValueError as e:
                        rejected.append(str(e))
                        continue
                    with open(target, "wb") as w: w.write(f.getbuffer())
                    db_save_document(safe_name, desc_map[f.name], r_date, current_user())
                    log_action(current_user(), "UPLOAD_DOC", safe_name)
                create_vector_db()
                st.session_state.agent = VendorResponseAgent()
                if rejected:
                    for msg in rejected: st.error(msg)
                else: st.rerun()
    
    st.divider()
    docs = db_get_documents()
    if docs:
        for d in docs:
            c1, c2, c3 = st.columns([3,2,1])
            with c1: st.write(f"**{html.escape(str(d.filename))}**\n<small>{html.escape(str(d.description or ''))}</small>", unsafe_allow_html=True)
            with c2: st.caption(f"Review: {d.review_date}" + (" (OVERDUE, not indexed)" if is_overdue(d) else ""))
            with c3:
                if can_admin() and st.button("🗑️", key=f"del_{d.id}"):
                    db_delete_document(d.filename)
                    log_action(current_user(), "DELETE_DOC", d.filename)
                    create_vector_db()
                    # The rebuild replaces the collection the old agent was bound to
                    st.session_state.agent = VendorResponseAgent()
                    st.rerun()
    else: st.info("No documents.")

# --- PAGE 8: SETTINGS (FULL RESTORED) ---
elif st.session_state.page_selection == "Settings":
    show_header("Settings")
    t1, t2, t3, t4 = st.tabs(["Profile", "Roles & Permissions", "Theme", "Logs"])
    
    with t1:
        u = st.session_state.user_profile
        c1, c2 = st.columns(2)
        with c1:
            fn = st.text_input("First Name", u['first_name'])
            ln = st.text_input("Last Name", u['last_name'])
            em = st.text_input("Email", u['email'], disabled=not DEMO_MODE, help=None if DEMO_MODE else "Set by your identity provider.")
        with c2:
            ti = st.text_input("Title", u['title'])
            ph = st.text_input("Phone", u['phone'])
            # Explicit Role Toggle
            rl = st.selectbox("Role", ROLES, index=ROLES.index(u['role']) if u['role'] in ROLES else ROLES.index(DEFAULT_ROLE), disabled=not can_admin(), help=None if can_admin() else "Only an Administrator can change roles.")
        
        if st.button("Save Profile"):
            # Enforced here as well as in the widgets: role and identity are not self-service
            if not can_admin(): rl = u['role']
            if not DEMO_MODE: em = u['email']
            # Update Session
            st.session_state.user_profile.update({"first_name": fn, "last_name": ln, "email": em, "title": ti, "phone": ph, "role": rl})
            # Update DB
            db = get_db()
            user_rec = db.query(User).filter(User.id == u['id']).first()
            if user_rec:
                user_rec.first_name = fn; user_rec.last_name = ln; user_rec.email = em
                user_rec.title = ti; user_rec.phone = ph; user_rec.role = rl
                db.commit()
            db.close()
            log_action(current_user(), "UPDATE_PROFILE", f"role={rl}")
            st.success("Updated!")
            st.rerun()

    with t2:
        st.markdown("### Role Management")
        st.caption("Manage access levels for the organization.")
        st.caption("This table is a reference and is not stored. Enforced rules: Read Only users cannot upload documents or add answers; only Administrators can delete documents, change roles, or edit this table.")
        if "role_data" not in st.session_state:
            st.session_state.role_data = pd.DataFrame({"Role": ["Administrator", "Analyst", "Auditor", "Viewer"], "Write Access": [True, True, False, False], "Delete Access": [True, False, False, False], "AI Access": [True, True, True, False]})
        edited_df = st.data_editor(st.session_state.role_data, num_rows="dynamic", use_container_width=True, key="role_editor", disabled=not can_admin())
        if can_admin() and st.button("💾 Save Permission Changes", type="primary"):
            st.session_state.role_data = edited_df
            st.success("Permissions updated successfully!")
            log_action(current_user(), "UPDATE_ROLES", "Modified system role permissions")

        if can_admin():
            st.divider()
            st.markdown("### User Roles")
            st.caption("New users start as Read Only. Changes apply on the user's next interaction. Change your own role on the Profile tab.")
            db = get_db()
            for usr in db.query(User).order_by(User.email).all():
                uc1, uc2 = st.columns([3,2])
                with uc1: st.write(usr.email)
                with uc2: new_role = st.selectbox("Role", ROLES, index=ROLES.index(usr.role) if usr.role in ROLES else ROLES.index(DEFAULT_ROLE), key=f"user_role_{usr.id}", label_visibility="collapsed", disabled=usr.id == st.session_state.user_profile["id"])
                if usr.id != st.session_state.user_profile["id"] and new_role != usr.role:
                    usr.role = new_role
                    db.commit()
                    log_action(current_user(), "CHANGE_USER_ROLE", f"{usr.email} -> {new_role}")
            db.close()

    with t3:
        st.radio("Theme", ["Pro (Default)", "Dark Mode", "Light Mode"], key="theme_sel")
        if st.session_state.theme_sel != st.session_state.theme_mode:
            st.session_state.theme_mode = st.session_state.theme_sel
            st.rerun()

    with t4:
        st.markdown("### System Audit Logs")
        if os.path.exists(AUDIT_LOG_FILE): st.dataframe(pd.read_csv(AUDIT_LOG_FILE).sort_values(by="Timestamp", ascending=False), use_container_width=True)
