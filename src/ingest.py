import os
import shutil
from langchain_community.document_loaders import DirectoryLoader, TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv
from rich.console import Console

# Setup
load_dotenv()
console = Console()

DATA_PATH = "./data"
DB_PATH = "./chroma_db"

def create_vector_db():
    console.rule("[bold blue]🔄 Knowledge Base Builder[/bold blue]")

    # 1. Clear old DB to prevent duplicates
    if os.path.exists(DB_PATH):
        console.print(f"[yellow]⚠️  Cleaning up old database at {DB_PATH}...[/yellow]")
        shutil.rmtree(DB_PATH)

    # 2. Load Documents
    console.print(f"📂 Scanning {DATA_PATH} for security artifacts...")
    
    docs = []
    # Load PDFs
    try:
        pdf_loader = DirectoryLoader(DATA_PATH, glob="**/*.pdf", loader_cls=PyPDFLoader)
        docs.extend(pdf_loader.load())
    except Exception as e:
        console.print(f"[dim]   No PDFs found ({e})[/dim]")

    # Load Text Files
    try:
        txt_loader = DirectoryLoader(DATA_PATH, glob="**/*.txt", loader_cls=TextLoader)
        docs.extend(txt_loader.load())
    except Exception as e:
        console.print(f"[dim]   No TXT files found ({e})[/dim]")

    if not docs:
        console.print("[bold red]❌ No documents found! Put your policies in the 'data/' folder.[/bold red]")
        return

    console.print(f"✅ Loaded [bold green]{len(docs)}[/bold green] documents.")

    # 3. Split Text (Chunking)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_documents(docs)
    console.print(f"🧩 Split into [bold cyan]{len(chunks)}[/bold cyan] semantic chunks.")

    # 4. Save to Vector DB
    console.print("💾 Embedding and saving to ChromaDB...")
    embedding_function = OpenAIEmbeddings()
    
    # Create and persist database
    Chroma.from_documents(
        documents=chunks, 
        embedding=embedding_function, 
        persist_directory=DB_PATH
    )
    
    console.print("[bold green]🚀 Success! Knowledge Base is ready for the Agent.[/bold green]")

if __name__ == "__main__":
    create_vector_db()
