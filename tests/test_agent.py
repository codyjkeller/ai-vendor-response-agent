import pytest
from langchain_core.documents import Document

import agent
from database import AnswerBank


@pytest.fixture
def no_keys(monkeypatch):
    monkeypatch.setattr(agent, "OPENAI_KEY", None)
    monkeypatch.setattr(agent, "ANTHROPIC_KEY", None)
    monkeypatch.setattr(agent, "LLM_PROVIDER", "")


@pytest.fixture
def agent_instance(no_keys, monkeypatch):
    """A VendorResponseAgent with no LLM, no embeddings model, and no vector DB."""
    monkeypatch.setattr(agent, "get_embeddings", lambda provider: None)
    monkeypatch.setattr(agent, "DB_DIR", "/nonexistent/chroma_db")
    return agent.VendorResponseAgent()


def add_bank_entry(db_session, question, answer):
    db_session.add(AnswerBank(question=question, answer=answer, product="P", subsidiary="S",
                              verified_by="tester", date_added="2026-01-01"))
    db_session.commit()


# --- resolve_provider ---

def test_resolve_provider_local_without_keys(no_keys):
    assert agent.resolve_provider() == "local"


def test_resolve_provider_openai_only(no_keys, monkeypatch):
    monkeypatch.setattr(agent, "OPENAI_KEY", "sk-test")
    assert agent.resolve_provider() == "openai"


def test_resolve_provider_anthropic_only(no_keys, monkeypatch):
    monkeypatch.setattr(agent, "ANTHROPIC_KEY", "sk-ant-test")
    assert agent.resolve_provider() == "anthropic"


def test_resolve_provider_prefers_anthropic_when_both_keys_set(no_keys, monkeypatch):
    monkeypatch.setattr(agent, "OPENAI_KEY", "sk-test")
    monkeypatch.setattr(agent, "ANTHROPIC_KEY", "sk-ant-test")
    assert agent.resolve_provider() == "anthropic"


def test_resolve_provider_explicit_openai_overrides_auto_detect(no_keys, monkeypatch):
    monkeypatch.setattr(agent, "OPENAI_KEY", "sk-test")
    monkeypatch.setattr(agent, "ANTHROPIC_KEY", "sk-ant-test")
    monkeypatch.setattr(agent, "LLM_PROVIDER", "openai")
    assert agent.resolve_provider() == "openai"


def test_resolve_provider_explicit_choice_without_key_falls_back(no_keys, monkeypatch):
    monkeypatch.setattr(agent, "OPENAI_KEY", "sk-test")
    monkeypatch.setattr(agent, "LLM_PROVIDER", "anthropic")
    assert agent.resolve_provider() == "openai"


# --- check_answer_bank ---

def test_answer_bank_exact_match(agent_instance, db_session):
    add_bank_entry(db_session, "Do you use MFA?", "Yes, via Okta.")
    answer, source = agent_instance.check_answer_bank("Do you use MFA?")
    assert answer == "Yes, via Okta."
    assert "100%" in source


def test_answer_bank_is_case_insensitive(agent_instance, db_session):
    add_bank_entry(db_session, "Do you use MFA?", "Yes, via Okta.")
    answer, _ = agent_instance.check_answer_bank("DO YOU USE MFA?")
    assert answer == "Yes, via Okta."


def test_answer_bank_unrelated_question_returns_none(agent_instance, db_session):
    add_bank_entry(db_session, "Do you use MFA?", "Yes, via Okta.")
    assert agent_instance.check_answer_bank("What is your RTO?") == (None, None)


def test_answer_bank_empty_returns_none(agent_instance):
    assert agent_instance.check_answer_bank("Anything?") == (None, None)


def test_answer_bank_returns_best_of_several(agent_instance, db_session):
    add_bank_entry(db_session, "Do you encrypt data at rest?", "At rest answer.")
    add_bank_entry(db_session, "Do you use MFA for all employees?", "MFA answer.")
    answer, _ = agent_instance.check_answer_bank("Do you use MFA for all employees?")
    assert answer == "MFA answer."


# Known defect, recorded as expected failures. check_answer_bank scores string
# similarity only, so questions that differ in a meaning-bearing word clear the
# 85 threshold and return the wrong answer labelled "Verified (Bank)".
# strict=True: when the matching is fixed these start passing and pytest
# reports XPASS(strict) as a failure, which is the cue to remove the marker.
@pytest.mark.xfail(strict=True, reason="at rest vs in transit scores 85, at the threshold")
def test_answer_bank_does_not_conflate_at_rest_and_in_transit(agent_instance, db_session):
    add_bank_entry(db_session, "Do you encrypt data at rest?", "At rest answer.")
    assert agent_instance.check_answer_bank("Do you encrypt data in transit?") == (None, None)


@pytest.mark.xfail(strict=True, reason="negated question scores 93")
def test_answer_bank_does_not_conflate_negation(agent_instance, db_session):
    add_bank_entry(db_session, "Is data encrypted at rest?", "Yes.")
    assert agent_instance.check_answer_bank("Is data not encrypted at rest?") == (None, None)


@pytest.mark.xfail(strict=True, reason="Type I vs Type II scores 99")
def test_answer_bank_does_not_conflate_soc2_types(agent_instance, db_session):
    add_bank_entry(db_session, "Do you have a SOC 2 Type II report?", "Yes.")
    assert agent_instance.check_answer_bank("Do you have a SOC 2 Type I report?") == (None, None)


# --- generate_responses ---

class FakeVectorDB:
    def __init__(self, docs):
        self.docs = docs

    def as_retriever(self, **kwargs):
        return object()

    def similarity_search(self, query, k=3):
        return self.docs[:k]


class FakeChain:
    def __init__(self, result, docs):
        self.result = result
        self.docs = docs

    def invoke(self, payload):
        return {"result": self.result, "source_documents": self.docs}


def install_fake_chain(monkeypatch, result, docs):
    class FakeRetrievalQA:
        @staticmethod
        def from_chain_type(**kwargs):
            return FakeChain(result, docs)

    monkeypatch.setattr(agent, "RetrievalQA", FakeRetrievalQA)


def test_generate_responses_without_knowledge_base(agent_instance):
    df = agent_instance.generate_responses(["Do you use MFA?"])
    row = df.iloc[0]
    assert row["Status"] == "❌ Failed"
    assert row["AI_Response"] == "No Knowledge Base"


def test_generate_responses_prefers_answer_bank(agent_instance, db_session):
    add_bank_entry(db_session, "Do you use MFA?", "Yes, via Okta.")
    row = agent_instance.generate_responses(["Do you use MFA?"]).iloc[0]
    assert row["Status"] == "✅ Verified (Bank)"
    assert row["AI_Response"] == "Yes, via Okta."


def test_generate_responses_search_only_when_no_llm(agent_instance):
    docs = [Document(page_content="x", metadata={"source": "policy.txt"})]
    agent_instance.vector_db = FakeVectorDB(docs)
    row = agent_instance.generate_responses(["Do you use MFA?"]).iloc[0]
    assert row["Status"] == "🔍 Search Result"
    assert row["Evidence"] == "policy.txt"


def test_generate_responses_flags_review_required(agent_instance, monkeypatch):
    docs = [Document(page_content="x", metadata={"source": "policy.txt"})]
    agent_instance.llm = object()
    agent_instance.vector_db = FakeVectorDB(docs)
    install_fake_chain(monkeypatch, "Review Required", docs)
    row = agent_instance.generate_responses(["Do you have ISO 27001?"]).iloc[0]
    assert row["Status"] == "⚠️ Review"


def test_generate_responses_marks_generated_answer_with_sources(agent_instance, monkeypatch):
    docs = [
        Document(page_content="x", metadata={"source": "a.pdf"}),
        Document(page_content="y", metadata={"source": "b.pdf"}),
    ]
    agent_instance.llm = object()
    agent_instance.vector_db = FakeVectorDB(docs)
    install_fake_chain(monkeypatch, "MFA is enforced via Okta.", docs)
    row = agent_instance.generate_responses(["Do you use MFA?"]).iloc[0]
    assert row["Status"] == "🤖 AI Generated"
    assert row["Evidence"] == "a.pdf; b.pdf"


def test_generate_responses_reports_chain_errors_per_row(agent_instance, monkeypatch):
    class BoomChain:
        def invoke(self, payload):
            raise RuntimeError("provider down")

    class BoomRetrievalQA:
        @staticmethod
        def from_chain_type(**kwargs):
            return BoomChain()

    agent_instance.llm = object()
    agent_instance.vector_db = FakeVectorDB([])
    monkeypatch.setattr(agent, "RetrievalQA", BoomRetrievalQA)
    df = agent_instance.generate_responses(["Q1?", "Q2?"])
    assert list(df["Status"]) == ["❌ Failed", "❌ Failed"]
    assert "provider down" in df.iloc[0]["AI_Response"]
