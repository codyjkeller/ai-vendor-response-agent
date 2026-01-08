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
from langchain_openai import OpenAIEmbeddings
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
                try:
                    df = pd.read_excel(os.path.join(root, file))
                    text_data = df.to_string(index=False)
                    from langchain.docstore.document import Document
                    docs.append(Document(page_content=text_data, metadata={"source": file}))
                    console.print(f"[green]   Loaded Excel: {file}[/green]")
                except Exception as e:
                    console.print(f"[red]   Failed Excel: {file} ({e})[/red]")
    return docs

def get_embeddings():
    """Returns OpenAI if key exists, else HuggingFace (Local)."""
    if os.getenv("OPENAI_API_KEY"):
        console.print("[bold green]🧠 Using OpenAI Embeddings (Cloud)[/bold green]")
        return OpenAIEmbeddings()
    else:
        console.print("[bold yellow]🧠 Using HuggingFace Embeddings (Local/Free)[/bold yellow]")
        return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def create_vector_db():
    console.rule("[bold blue]🔄 Knowledge Base Builder[/bold blue]")

    # 1. Clean Slate
    if os.path.exists(DB_PATH):
        shutil.rmtree(DB_PATH)

    docs = []
    
    # 2. Load all file types
    try: docs.extend(DirectoryLoader(DATA_PATH, glob="**/*.pdf", loader_cls=PyPDFLoader).load())
    except: pass
    try: docs.extend(DirectoryLoader(DATA_PATH, glob="**/*.txt", loader_cls=TextLoader).load())
    except: pass
    try: docs.extend(DirectoryLoader(DATA_PATH, glob="**/*.docx", loader_cls=Docx2txtLoader).load())
    except: pass
    
    docs.extend(load_excel())
    docs.extend(load_urls())

    if not docs:
        console.print("[bold red]❌ No documents found in /data![/bold red]")
        return

    console.print(f"✅ Total Artifacts: [bold green]{len(docs)}[/bold green]")

    # 3. Chunk & Embed
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_documents(docs)
    
    console.print("💾 Saving to Vector Database...")
    embedding_function = get_embeddings()
    
    Chroma.from_documents(chunks, embedding_function, persist_directory=DB_PATH)
    
    console.print("[bold green]🚀 Knowledge Base Updated Successfully![/bold green]")

if __name__ == "__main__":
    create_vector_db()
