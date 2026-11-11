import os
import sys
import tempfile

# These must be set before any module under src/ is imported:
# database.py builds its engine at import time from DATABASE_URL, and
# chromadb emits telemetry unless disabled.
_TMP_DIR = tempfile.mkdtemp(prefix="vendor_agent_tests_")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DIR}/test.db"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
for _key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LLM_PROVIDER", "LLM_MODEL",
             "AUDITFLOW_DEMO_MODE", "AUDITFLOW_ADMIN_EMAILS"):
    os.environ.pop(_key, None)

SRC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import pytest  # noqa: E402

import database  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    """Gives every test an empty schema."""
    database.Base.metadata.drop_all(bind=database.engine)
    database.Base.metadata.create_all(bind=database.engine)
    yield


@pytest.fixture
def db_session():
    session = database.SessionLocal()
    try:
        yield session
    finally:
        session.close()
