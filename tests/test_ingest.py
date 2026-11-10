import os

import pandas as pd
import pytest
from langchain_community.embeddings import DeterministicFakeEmbedding

import ingest


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    path = tmp_path / "data"
    path.mkdir()
    monkeypatch.setattr(ingest, "DATA_DIR", str(path))
    monkeypatch.setattr(ingest, "DB_DIR", str(tmp_path / "chroma_db"))
    return path


def by_source(documents):
    return {d.metadata["source"]: d for d in documents}


def test_load_documents_creates_missing_data_dir(tmp_path, monkeypatch):
    missing = tmp_path / "does_not_exist"
    monkeypatch.setattr(ingest, "DATA_DIR", str(missing))
    assert ingest.load_documents() == []
    assert missing.is_dir()


def test_load_documents_reads_text_file(data_dir):
    (data_dir / "policy.txt").write_text("MFA is enforced.", encoding="utf-8")
    docs = by_source(ingest.load_documents())
    assert docs["policy.txt"].page_content == "MFA is enforced."
    assert docs["policy.txt"].metadata["type"] == "text"


def test_load_documents_skips_urls_txt(data_dir):
    (data_dir / "urls.txt").write_text("https://example.com\n", encoding="utf-8")
    assert ingest.load_documents() == []


def test_load_documents_skips_empty_text_file(data_dir):
    (data_dir / "empty.txt").write_text("", encoding="utf-8")
    assert ingest.load_documents() == []


def test_load_documents_reads_csv_as_spreadsheet(data_dir):
    pd.DataFrame({"Question": ["Do you use MFA?"], "Answer": ["Yes."]}).to_csv(
        data_dir / "past.csv", index=False
    )
    doc = by_source(ingest.load_documents())["past.csv"]
    assert doc.metadata["type"] == "spreadsheet"
    assert "Do you use MFA?" in doc.page_content
    assert "Yes." in doc.page_content


def test_load_documents_reads_xlsx(data_dir):
    pd.DataFrame({"Question": ["RTO?"], "Answer": ["4 hours."]}).to_excel(
        data_dir / "past.xlsx", index=False
    )
    doc = by_source(ingest.load_documents())["past.xlsx"]
    assert "4 hours." in doc.page_content


def test_load_documents_ignores_unsupported_extensions(data_dir):
    (data_dir / "notes.md").write_text("ignored", encoding="utf-8")
    assert ingest.load_documents() == []


def test_load_documents_survives_corrupt_xlsx(data_dir, capsys):
    # data/past_assessments.xlsx in the repository is a Python script with an
    # .xlsx extension; ingestion must report it and carry on.
    (data_dir / "broken.xlsx").write_text("import pandas as pd\n", encoding="utf-8")
    (data_dir / "good.txt").write_text("kept", encoding="utf-8")
    docs = by_source(ingest.load_documents())
    assert list(docs) == ["good.txt"]
    assert "Excel Error broken.xlsx" in capsys.readouterr().out


# Known defect: extension matching is case-sensitive, so POLICY.TXT / REPORT.PDF
# are silently skipped. strict=True flags the XPASS once it is fixed.
@pytest.mark.xfail(strict=True, reason="extension match is case-sensitive")
def test_load_documents_accepts_uppercase_extension(data_dir):
    (data_dir / "POLICY.TXT").write_text("MFA is enforced.", encoding="utf-8")
    assert "POLICY.TXT" in by_source(ingest.load_documents())


def test_create_vector_db_without_documents_leaves_no_index(data_dir, capsys):
    ingest.create_vector_db()
    assert not os.path.exists(ingest.DB_DIR)
    assert "No documents found" in capsys.readouterr().out


def test_create_vector_db_builds_index(data_dir, monkeypatch):
    monkeypatch.setattr(ingest, "get_embeddings", lambda: DeterministicFakeEmbedding(size=16))
    (data_dir / "policy.txt").write_text("MFA is enforced for all employees.", encoding="utf-8")

    ingest.create_vector_db()
    assert os.path.isdir(ingest.DB_DIR)


# Known defect: create_vector_db() deletes the index directory with shutil.rmtree
# while chromadb still holds an open client for that path in the same process.
# The second rebuild fails with "attempt to write a readonly database". The
# Streamlit app does exactly this on its second document upload or delete.
@pytest.mark.xfail(strict=True, reason="rmtree under an open chromadb client; rebuild raises InternalError")
def test_create_vector_db_can_rebuild_in_same_process(data_dir, monkeypatch):
    monkeypatch.setattr(ingest, "get_embeddings", lambda: DeterministicFakeEmbedding(size=16))
    (data_dir / "policy.txt").write_text("MFA is enforced for all employees.", encoding="utf-8")

    ingest.create_vector_db()
    marker = os.path.join(ingest.DB_DIR, "stale.marker")
    with open(marker, "w") as handle:
        handle.write("x")

    ingest.create_vector_db()
    assert os.path.isdir(ingest.DB_DIR)
    assert not os.path.exists(marker)
