import os
import pdfplumber
import docx2txt
import pandas as pd
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain.docstore.document import Document
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = "data"
DB_DIR = "chroma_db"

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

def load_documents():
    """Loads PDFs, Word Docs, and Excel files as knowledge."""
    documents = []
    
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        return []

    print(f"📂 Scanning {DATA_DIR}...")

    for filename in os.listdir(DATA_DIR):
        file_path = os.path.join(DATA_DIR, filename)
        
        # 1. PDF Handling
        if filename.endswith(".pdf"):
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
        elif filename.endswith(".docx"):
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
        elif filename.endswith(".xlsx") or filename.endswith(".csv"):
            try:
                print(f"   - Processing Spreadsheet: {filename}")
                if filename.endswith(".xlsx"):
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
        elif filename.endswith(".txt") and filename != "urls.txt":
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
    if os.path.exists(DB_DIR):
        import shutil
        shutil.rmtree(DB_DIR)

    raw_docs = load_documents()
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
        persist_directory=DB_DIR,
        collection_name="vendor_knowledge"
    )
    print(f"✅ Knowledge Base Rebuilt!")

if __name__ == "__main__":
    create_vector_db()
