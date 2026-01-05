import os
import shutil
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv
from rich.console import Console

# Setup
load_dotenv()
console = Console()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATA_DIR = "./data"
DB_DIR = "./chroma_db"

def build_knowledge_base():
    console.rule("[bold blue]🧠 Knowledge Base Builder[/bold blue]")

    # 1. Check for Documents
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    pdf_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.pdf')]
    if not pdf_files:
        console.print(f"[red]❌ No PDFs found in {DATA_DIR}. Please add your SOC 2 reports or Policies.[/red]")
        return

    # 2. Reset Database (Optional: Clean slate)
    if os.path.exists(DB_DIR):
        shutil.rmtree(DB_DIR)
        console.print("[yellow]⚠️  Cleared existing Vector Database.[/yellow]")

    documents = []
    
    # 3. Ingest Documents
    with console.status(f"[bold green]Reading {len(pdf_files)} PDFs...[/bold green]"):
        for pdf in pdf_files:
            try:
                loader = PyPDFLoader(os.path.join(DATA_DIR, pdf))
                docs = loader.load()
                # Add source metadata just to be safe
                for d in docs:
                    d.metadata["source_file"] = pdf
                documents.extend(docs)
                console.print(f"   ✅ Loaded: {pdf} ({len(docs)} pages)")
            except Exception as e:
                console.print(f"   ❌ Error loading {pdf}: {e}")

    # 4. Chunking (Critical for RAG)
    # We use a 1000-char chunk with overlap to capture context across paragraphs.
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", " ", ""]
    )
    chunks = text_splitter.split_documents(documents)
    console.print(f"   ✂️  Split into {len(chunks)} semantic chunks.")

    # 5. Embed & Store
    with console.status("[bold green]🧠 Embedding into Vector Database...[/bold green]"):
        embedding_model = OpenAIEmbeddings(model="text-embedding-3-small")
        Chroma.from_documents(
            documents=chunks,
            embedding=embedding_model,
            persist_directory=DB_DIR
        )

    console.print(f"\n[bold blue]🎉 Knowledge Base Built![/bold blue] Saved to: {DB_DIR}")

if __name__ == "__main__":
    build_knowledge_base()
