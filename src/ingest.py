import os
from langchain_community.document_loaders import DirectoryLoader, TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv

load_dotenv()

DATA_PATH = "./data"
DB_PATH = "./db"

def create_vector_db():
    print(f"🔄 Loading documents from {DATA_PATH}...")
    # Load both PDFs and Text files if they exist
    pdf_loader = DirectoryLoader(DATA_PATH, glob="./*.pdf", loader_cls=PyPDFLoader)
    txt_loader = DirectoryLoader(DATA_PATH, glob="./*.txt", loader_cls=TextLoader)

    docs = []
    try:
        docs.extend(pdf_loader.load())
    except Exception:
        pass # No PDFs found

    try:
        docs.extend(txt_loader.load())
    except Exception:
        pass # No TXT files found

    if not docs:
        print("❌ No documents found! Please add files to the 'data/' folder.")
        return

    print(f"✅ Loaded {len(docs)} documents.")

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_documents(docs)

    print(f"🧩 Split into {len(chunks)} chunks.")

    print("💾 Saving to local ChromaDB...")
    embedding_function = OpenAIEmbeddings()
    Chroma.from_documents(chunks, embedding_function, persist_directory=DB_PATH)
    print("🚀 Success! Knowledge base created.")

if __name__ == "__main__":
    create_vector_db()
