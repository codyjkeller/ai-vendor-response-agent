import os
import pdfplumber
import docx2txt
import pandas as pd
import chromadb
from datetime import date
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain.docstore.document import Document
from dotenv import load_dotenv

load_dotenv()

from config import DEMO_MODE, SAMPLE_DATA_DIR  # noqa: E402

DATA_DIR = "data"
DB_DIR = "chroma_db"
COLLECTION_NAME = "vendor_knowledge"  # Must match agent.py
SAMPLE_LABEL = "SAMPLE - "

def get_embeddings():
    """Returns the best available embedding model."""
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        from langchain_openai import OpenAIEmbeddings
        print("🔑 Using OpenAI embeddings.")
        return OpenAIEmbeddings()
    else:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        print("🆓 No OpenAI key found. Using local HuggingFace embeddings (all-MiniLM-L6-v2).")
        return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def get_expired_filenames():
    """Returns filenames whose review date (set in the Knowledge Base) has passed.

    Files that were never registered through the app have no review date and
    are always indexed.
    """
    expired = set()
    try:
        from database import SessionLocal, init_db, Document as DocumentRecord
        init_db()
        db = SessionLocal()
        try:
            for record in db.query(DocumentRecord).all():
                try:
                    if date.fromisoformat(str(record.review_date)) < date.today():
                        expired.add(record.filename)
                except ValueError:
                    continue
        finally:
            db.close()
    except Exception as e:
        print(f"⚠️ Could not read review dates: {e}")
    return expired

def load_documents():
    """Loads PDFs, Word Docs, and Excel files as knowledge."""
    documents = []
    
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    print(f"📂 Scanning {DATA_DIR}...")

    expired = get_expired_filenames()
    entries = []
    for name in sorted(os.listdir(DATA_DIR)):
        if name in expired:
            print(f"   - Skipping (review date passed): {name}")
            continue
        entries.append((name, os.path.join(DATA_DIR, name)))

    # Sample documents are indexed in demo mode only, and are labelled so they
    # cannot be mistaken for real evidence.
    if DEMO_MODE and os.path.isdir(SAMPLE_DATA_DIR):
        print(f"📂 Demo mode: also scanning {SAMPLE_DATA_DIR}...")
        for name in sorted(os.listdir(SAMPLE_DATA_DIR)):
            entries.append((SAMPLE_LABEL + name, os.path.join(SAMPLE_DATA_DIR, name)))

    for filename, file_path in entries:
        # Extension matching is case-insensitive (REPORT.PDF, Policy.TXT).
        lower_name = filename.lower()
        
        # 1. PDF Handling
        if lower_name.endswith(".pdf"):
            try:
                print(f"   - Processing PDF: {filename}")
                with pdfplumber.open(file_path) as pdf:
                    for i, page in enumerate(pdf.pages):
                        text = page.extract_text()
                        if text:
                            # Heuristic: Remove page numbers/footers < 10 chars
                            clean_text = "\n".join([line for line in text.split('\n') if len(line) > 10])
                            documents.append(Document(
                                page_content=clean_text,
                                metadata={"source": filename, "page": i + 1, "type": "pdf"}
                            ))
            except Exception as e:
                print(f"❌ PDF Error {filename}: {e}")

        # 2. Word Doc Handling
        elif lower_name.endswith(".docx"):
            try:
                print(f"   - Processing Word Doc: {filename}")
                text = docx2txt.process(file_path)
                if text:
                    documents.append(Document(
                        page_content=text,
                        metadata={"source": filename, "page": 1, "type": "docx"}
                    ))
            except Exception as e:
                print(f"❌ Docx Error {filename}: {e}")

        # 3. Excel/CSV Handling (Previous Questionnaires)
        elif lower_name.endswith(".xlsx") or lower_name.endswith(".csv"):
            try:
                print(f"   - Processing Spreadsheet: {filename}")
                if lower_name.endswith(".xlsx"):
                    df = pd.read_excel(file_path)
                else:
                    df = pd.read_csv(file_path)
                
                # Convert rows to text blobs for searching
                # Assumes columns like 'Question' and 'Answer' exist, or just concatenates all text
                text_blob = df.to_string(index=False)
                documents.append(Document(
                    page_content=text_blob,
                    metadata={"source": filename, "page": 1, "type": "spreadsheet"}
                ))
            except Exception as e:
                print(f"❌ Excel Error {filename}: {e}")

        # 4. Plain Text Handling
        elif lower_name.endswith(".txt") and os.path.basename(file_path).lower() != "urls.txt":
            try:
                print(f"   - Processing Text: {filename}")
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read()
                if text:
                    documents.append(Document(
                        page_content=text,
                        metadata={"source": filename, "page": 1, "type": "text"}
                    ))
            except Exception as e:
                print(f"❌ Text Error {filename}: {e}")

    return documents

def create_vector_db():
    """Rebuilds the vector database."""
    raw_docs = load_documents()

    # Drop the old collection through the client instead of deleting the
    # directory: removing files under an open chromadb client leaves it
    # pointing at a read-only database for the rest of the process.
    client = None
    if os.path.exists(DB_DIR) or raw_docs:
        client = chromadb.PersistentClient(path=DB_DIR)
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass  # Collection did not exist yet

    if not raw_docs:
        print("⚠️ No documents found to index.")
        return

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ".", "!", "?", " "]
    )
    
    chunks = text_splitter.split_documents(raw_docs)
    
    embeddings = get_embeddings()
    
    print(f"🧠 Embedding {len(chunks)} knowledge chunks...")
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        client=client,
        collection_name=COLLECTION_NAME
    )
    print(f"✅ Knowledge Base Rebuilt!")

if __name__ == "__main__":
    create_vector_db()
