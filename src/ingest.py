import os
import shutil
import pandas as pd
from langchain_community.document_loaders import (
    DirectoryLoader, 
    TextLoader, 
    PyPDFLoader, 
    Docx2txtLoader, 
    WebBaseLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
# SWAP: Using Local HuggingFace Embeddings instead of OpenAI
from langchain_community.embeddings import HuggingFaceEmbeddings 
from langchain_chroma import Chroma
from dotenv import load_dotenv
from rich.console import Console

# Setup
load_dotenv()
console = Console()

DATA_PATH = "./data"
DB_PATH = "./chroma_db"

def load_urls():
    """Reads URLs from data/urls.txt if it exists."""
    url_path = os.path.join(DATA_PATH, "urls.txt")
    if os.path.exists(url_path):
        with open(url_path, "r") as f:
            urls = [line.strip() for line in f if line.strip()]
        if urls:
            console.print(f"[blue]🌐 Scraping {len(urls)} websites...[/blue]")
            try:
                loader = WebBaseLoader(urls)
                return loader.load()
            except Exception as e:
                console.print(f"[red]   Warning: Could not scrape URLs ({e})[/red]")
                return []
    return []

def load_excel():
    """Reads all Excel files in /data and converts rows to text documents."""
    docs = []
    if not os.path.exists(DATA_PATH): return []
    
    for root, _, files in os.walk(DATA_PATH):
        for file in files:
            if file.endswith(".xlsx"):
                file_path = os.path.join(root, file)
                try:
                    df = pd.read_excel(file_path)
                    text_data = df.to_string(index=False)
                    from langchain.docstore.document import Document
                    docs.append(Document(page_content=text_data, metadata={"source": file}))
                    console.print(f"[green]   Loaded Excel: {file}[/green]")
                except Exception as e:
                    console.print(f"[red]   Failed Excel: {file} ({e})[/red]")
    return docs

def create_vector_db():
    console.rule("[bold blue]🔄 Omni-Ingest Knowledge Builder (Local Mode)[/bold blue]")

    # 1. Clean Slate
    if os.path.exists(DB_PATH):
        shutil.rmtree(DB_PATH)

    docs = []

    # 2. PDF & Text
    try:
        docs.extend(DirectoryLoader(DATA_PATH, glob="**/*.pdf", loader_cls=PyPDFLoader).load())
        docs.extend(DirectoryLoader(DATA_PATH, glob="**/*.txt", loader_cls=TextLoader).load())
    except Exception: pass

    # 3. Word Docs
    try:
        docs.extend(DirectoryLoader(DATA_PATH, glob="**/*.docx", loader_cls=Docx2txtLoader).load())
    except Exception: pass

    # 4. Excel & Web
    docs.extend(load_excel())
    docs.extend(load_urls())

    if not docs:
        console.print("[bold red]❌ No documents found in /data! Creating dummy data...[/bold red]")
        # Create dummy data so the script doesn't fail for the demo
        from langchain.docstore.document import Document
        docs.append(Document(page_content="The RTO is 4 hours. Data is encrypted with AES-256.", metadata={"source": "dummy_policy.txt"}))

    console.print(f"✅ Total Artifacts: [bold green]{len(docs)}[/bold green]")

    # 5. Chunk & Embed
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_documents(docs)
    
    console.print("💾 Embedding with [bold yellow]HuggingFace (Local)[/bold yellow]...")
    
    # FREE MODE: Uses your local CPU instead of OpenAI API
    embedding_function = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    Chroma.from_documents(chunks, embedding_function, persist_directory=DB_PATH)
    
    console.print("[bold green]🚀 Knowledge Base Built Successfully! (No API Key Required)[/bold green]")

if __name__ == "__main__":
    create_vector_db()
