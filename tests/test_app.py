"""End-to-end checks of src/app.py using Streamlit's headless AppTest runner."""
import os

import pytest
import streamlit
from streamlit.testing.v1 import AppTest

import agent
import config
import ingest
from database import Document as DocumentRecord, User

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "app.py")


class FakeIdentity(dict):
    """Stands in for st.user after an OIDC sign-in."""
    is_logged_in = True


@pytest.fixture(autouse=True)
def isolated_app(tmp_path, monkeypatch):
    # The app writes data/, audit_log.csv and chroma_db/ relative to the cwd.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(agent, "get_embeddings", lambda provider: None)
    monkeypatch.setattr(ingest, "get_embeddings", lambda: None)
    monkeypatch.setattr(agent, "OPENAI_KEY", None)
    monkeypatch.setattr(agent, "ANTHROPIC_KEY", None)
    monkeypatch.setattr(agent, "LLM_PROVIDER", "")


def run_app(**session):
    at = AppTest.from_file(APP_PATH, default_timeout=60)
    for key, value in session.items():
        at.session_state[key] = value
    return at


def demo_app(monkeypatch, **session):
    monkeypatch.setattr(config, "DEMO_MODE", True)
    return run_app(auth_stage="authenticated", **session).run()


def signed_in_app(monkeypatch, email, admins=(), **session):
    monkeypatch.setattr(config, "DEMO_MODE", False)
    monkeypatch.setattr(config, "ADMIN_EMAILS", set(admins))
    monkeypatch.setattr(streamlit, "user", FakeIdentity(email=email, given_name="Ada", family_name="Lovelace"))
    at = run_app(**session)
    at.secrets["auth"] = {"redirect_uri": "http://localhost:8501/oauth2callback"}
    return at.run()


def texts(elements):
    return " ".join(str(e.value) for e in elements)


def navigation(at):
    return at.sidebar.selectbox[0]


# --- authentication ---

def test_fails_closed_without_identity_provider(monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", False)
    at = run_app().run()
    assert not at.exception
    assert "Authentication is not configured" in texts(at.error)
    assert len(at.sidebar.selectbox) == 0


def test_preset_session_state_does_not_bypass_sign_in(monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", False)
    at = run_app(auth_stage="authenticated").run()
    assert "Authentication is not configured" in texts(at.error)
    assert len(at.sidebar.selectbox) == 0


def test_demo_mode_sign_in_is_labelled_as_simulated(monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", True)
    at = run_app().run()
    assert not at.exception
    assert "sign-in is simulated" in texts(at.warning)
    assert all(not field.value for field in at.text_input if field.label == "Password")


def test_signed_in_user_starts_read_only(monkeypatch, db_session):
    at = signed_in_app(monkeypatch, "ada@example.com")
    assert not at.exception
    assert db_session.query(User).filter(User.email == "ada@example.com").one().role == "Read Only"


def test_admin_email_list_grants_administrator(monkeypatch, db_session):
    at = signed_in_app(monkeypatch, "ada@example.com", admins={"ada@example.com"})
    assert not at.exception
    assert db_session.query(User).filter(User.email == "ada@example.com").one().role == "Administrator"


# --- demo-only content ---

def test_sample_pages_hidden_outside_demo_mode(monkeypatch):
    at = signed_in_app(monkeypatch, "ada@example.com")
    assert "Gap Analysis" not in navigation(at).options
    assert "My Projects" not in navigation(at).options
    assert "(sample)" not in " ".join(m.label for m in at.metric)


def test_sample_figures_are_labelled_in_demo_mode(monkeypatch):
    at = demo_app(monkeypatch)
    assert not at.exception
    assert "Gap Analysis" in navigation(at).options
    labels = " ".join(m.label for m in at.metric)
    assert "Security Posture (sample)" in labels
    assert "Active Audits (sample)" in labels


def test_gap_analysis_carries_sample_warning(monkeypatch):
    at = demo_app(monkeypatch, page_selection="Gap Analysis")
    assert "not computed from your documents" in texts(at.warning)


# --- authorization ---

def test_read_only_user_cannot_change_own_role(monkeypatch, db_session):
    at = signed_in_app(monkeypatch, "ada@example.com", page_selection="Settings")
    assert not at.exception
    role_box = next(box for box in at.selectbox if box.label == "Role")
    assert role_box.disabled

    next(b for b in at.button if b.label == "Save Profile").click()
    at.run()
    assert not at.exception
    assert db_session.query(User).filter(User.email == "ada@example.com").one().role == "Read Only"


def test_administrator_can_change_another_users_role(monkeypatch, db_session):
    db_session.add(User(email="bob@example.com", role="Read Only"))
    db_session.commit()
    bob_id = db_session.query(User).filter(User.email == "bob@example.com").one().id

    at = signed_in_app(monkeypatch, "ada@example.com", admins={"ada@example.com"}, page_selection="Settings")
    at.selectbox(key=f"user_role_{bob_id}").set_value("Analyst").run()
    assert not at.exception
    db_session.expire_all()
    assert db_session.query(User).filter(User.email == "bob@example.com").one().role == "Analyst"


def test_read_only_user_sees_no_delete_or_add_controls(monkeypatch, db_session):
    db_session.add(DocumentRecord(filename="policy.pdf", description="d", review_date="2999-01-01"))
    db_session.commit()
    at = signed_in_app(monkeypatch, "ada@example.com", page_selection="Knowledge Base")
    assert not at.exception
    assert "🗑️" not in [b.label for b in at.button]
    assert "read-only" in texts(at.info)

    at = signed_in_app(monkeypatch, "ada@example.com", page_selection="Answer Bank")
    assert "➕ Add New" not in [b.label for b in at.button]


# --- output handling ---

def test_document_description_is_html_escaped(monkeypatch, db_session):
    db_session.add(DocumentRecord(filename="policy.pdf", description="<script>alert(1)</script>",
                                  review_date="2999-01-01"))
    db_session.commit()
    at = demo_app(monkeypatch, page_selection="Knowledge Base")
    assert not at.exception
    rendered = texts(at.markdown)
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert "<script>" not in rendered


def test_overdue_document_is_flagged(monkeypatch, db_session):
    db_session.add(DocumentRecord(filename="old.pdf", description="d", review_date="2020-01-01"))
    db_session.commit()
    at = demo_app(monkeypatch, page_selection="Knowledge Base")
    assert "OVERDUE" in texts(at.caption)


# --- save to answer bank ---

class GeneratedAnswerAgent:
    provider = "anthropic"
    vector_db = object()

    def generate_responses(self, questions, product=None, subsidiary=None):
        import pandas as pd
        return pd.DataFrame([{"Question": questions[0], "AI_Response": "MFA is enforced via Okta.",
                              "Status": "🤖 AI Generated", "Evidence": "policy.pdf (Pg. 2)"}])


def ask_question(monkeypatch):
    at = demo_app(monkeypatch, page_selection="Questionnaire Agent", agent=GeneratedAnswerAgent())
    at.chat_input[0].set_value("Do you use MFA?").run()
    assert not at.exception
    return at


def test_save_to_bank_requires_review_confirmation(monkeypatch, db_session):
    from database import AnswerBank

    at = ask_question(monkeypatch)
    next(b for b in at.button if b.label == "💾 Save to Bank").click()
    at.run()
    assert "Confirm you have reviewed" in texts(at.warning)
    assert db_session.query(AnswerBank).count() == 0


def test_save_to_bank_stores_reviewed_answer_with_reviewer(monkeypatch, db_session):
    from database import AnswerBank

    at = ask_question(monkeypatch)
    at.checkbox[0].check()
    next(b for b in at.button if b.label == "💾 Save to Bank").click()
    at.run()
    assert not at.exception
    saved = db_session.query(AnswerBank).one()
    assert (saved.question, saved.answer) == ("Do you use MFA?", "MFA is enforced via Okta.")
    assert saved.verified_by == "john.smith@auditflow.io"
