import os
import streamlit as st
import pdfplumber
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.docstore.document import Document

DATA_DIR = "data"
DB_DIR = "chroma_db"

def load_documents():
    """Loads PDFs with layout preservation and page tracking."""
    documents = []
    
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        return []

    for filename in os.listdir(DATA_DIR):
        file_path = os.path.join(DATA_DIR, filename)
        
        if filename.endswith(".pdf"):
            try:
                with pdfplumber.open(file_path) as pdf:
                    for i, page in enumerate(pdf.pages):
                        text = page.extract_text()
                        if text:
                            # Add metadata for accurate citations
                            documents.append(Document(
                                page_content=text,
                                metadata={"source": filename, "page": i + 1}
                            ))
            except Exception as e:
                print(f"Error reading {filename}: {e}")
                
        elif filename.endswith(".txt"):
            with open(file_path, "r") as f:
                documents.append(Document(
                    page_content=f.read(),
                    metadata={"source": filename, "page": 1}
                ))

    return documents

def create_vector_db():
    """Rebuilds the vector database with smart chunking."""
    if os.path.exists(DB_DIR):
        import shutil
        shutil.rmtree(DB_DIR)

    raw_docs = load_documents()
    if not raw_docs:
        return

    # Slower but more accurate splitter for policies
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
    )
    
    chunks = text_splitter.split_documents(raw_docs)
    
    # Create DB
    Chroma.from_documents(
        documents=chunks,
        embedding=OpenAIEmbeddings(),
        persist_directory=DB_DIR
    )
    print(f"✅ Indexed {len(chunks)} chunks.")
