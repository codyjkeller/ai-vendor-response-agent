"""Runtime configuration shared by the app, the agent, and ingestion."""
import os

from dotenv import load_dotenv

load_dotenv()

_TRUTHY = ("1", "true", "yes", "on")


def _flag(name):
    return os.getenv(name, "").strip().lower() in _TRUTHY


# Demo mode turns on the simulated sign-in, the sample dashboard figures, the
# sample Gap Analysis / Projects pages, and indexing of sample_data/.
# It is off unless explicitly enabled. Never enable it for real use.
DEMO_MODE = _flag("AUDITFLOW_DEMO_MODE")

# Comma-separated e-mail addresses that are granted the Administrator role when
# they first sign in through the identity provider.
ADMIN_EMAILS = {
    e.strip().lower() for e in os.getenv("AUDITFLOW_ADMIN_EMAILS", "").split(",") if e.strip()
}

DATA_DIR = "data"
SAMPLE_DATA_DIR = "sample_data"

# File types the Knowledge Base accepts and ingestion can read.
ALLOWED_UPLOAD_EXTENSIONS = ("pdf", "docx", "xlsx", "csv", "txt")

ROLES = ["Administrator", "Manager", "Analyst", "Read Only"]
DEFAULT_ROLE = "Read Only"
ADMIN_ROLES = {"Administrator"}
WRITE_ROLES = {"Administrator", "Manager", "Analyst"}
