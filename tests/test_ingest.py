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


def search_index(query):
    import chromadb
    from langchain_chroma import Chroma

    store = Chroma(
        client=chromadb.PersistentClient(path=ingest.DB_DIR),
        collection_name=ingest.COLLECTION_NAME,
        embedding_function=DeterministicFakeEmbedding(size=16),
    )
    return [d.metadata["source"] for d in store.similarity_search(query, k=10)]


def test_create_vector_db_can_rebuild_in_same_process(data_dir, monkeypatch):
    # Regression: the rebuild used to delete the directory under an open
    # chromadb client and fail with "attempt to write a readonly database".
    monkeypatch.setattr(ingest, "get_embeddings", lambda: DeterministicFakeEmbedding(size=16))
    (data_dir / "old.txt").write_text("Old policy text.", encoding="utf-8")
    ingest.create_vector_db()
    assert search_index("policy") == ["old.txt"]

    (data_dir / "old.txt").unlink()
    (data_dir / "new.txt").write_text("New policy text.", encoding="utf-8")
    ingest.create_vector_db()
    assert search_index("policy") == ["new.txt"]

    # Removing the last document empties the index instead of leaving stale chunks.
    (data_dir / "new.txt").unlink()
    ingest.create_vector_db()
    assert search_index("policy") == []


def test_sample_data_is_not_indexed_outside_demo_mode(data_dir, tmp_path, monkeypatch):
    samples = tmp_path / "sample_data"
    samples.mkdir()
    (samples / "sample_policy.txt").write_text("Sample.", encoding="utf-8")
    monkeypatch.setattr(ingest, "SAMPLE_DATA_DIR", str(samples))
    monkeypatch.setattr(ingest, "DEMO_MODE", False)
    assert ingest.load_documents() == []


def test_sample_data_is_indexed_and_labelled_in_demo_mode(data_dir, tmp_path, monkeypatch):
    samples = tmp_path / "sample_data"
    samples.mkdir()
    (samples / "sample_policy.txt").write_text("Sample.", encoding="utf-8")
    (samples / "urls.txt").write_text("https://example.com", encoding="utf-8")
    monkeypatch.setattr(ingest, "SAMPLE_DATA_DIR", str(samples))
    monkeypatch.setattr(ingest, "DEMO_MODE", True)
    assert list(by_source(ingest.load_documents())) == ["SAMPLE - sample_policy.txt"]


def test_documents_past_review_date_are_not_indexed(data_dir, db_session):
    from database import Document as DocumentRecord

    (data_dir / "stale.txt").write_text("Stale.", encoding="utf-8")
    (data_dir / "current.txt").write_text("Current.", encoding="utf-8")
    (data_dir / "unregistered.txt").write_text("Dropped in by hand.", encoding="utf-8")
    db_session.add(DocumentRecord(filename="stale.txt", review_date="2020-01-01"))
    db_session.add(DocumentRecord(filename="current.txt", review_date="2999-01-01"))
    db_session.commit()

    assert sorted(by_source(ingest.load_documents())) == ["current.txt", "unregistered.txt"]
