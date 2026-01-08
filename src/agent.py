import os
import pandas as pd
import argparse
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# Setup
load_dotenv()
console = Console()

DB_DIR = "./chroma_db"
API_KEY = os.getenv("OPENAI_API_KEY")

class VendorResponseAgent:
    def __init__(self):
        # 1. Load Embeddings (Local if no key, OpenAI if key exists)
        if not API_KEY:
            console.print("[bold yellow]⚠️  No API Key found. Running in SEARCH-ONLY mode (HuggingFace).[/bold yellow]")
            self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            self.llm = None
        else:
            console.print("[bold green]✅ API Key found. Running in FULL AI mode.[/bold green]")
            self.embeddings = OpenAIEmbeddings()
            self.llm = ChatOpenAI(model_name="gpt-4", temperature=0)

        if os.path.exists(DB_DIR):
            self.vector_db = Chroma(persist_directory=DB_DIR, embedding_function=self.embeddings)
        else:
            console.print("[red]❌ DB not found. Run 'python src/ingest.py'[/red]")
            self.vector_db = None

    def search_knowledge_base(self, question):
        """Retrieves documents without generating an answer (Free Mode)."""
        if not self.vector_db: return "DB Error"
        
        console.print(f"\n[cyan]🔍 Searching for:[/cyan] {question}")
        docs = self.vector_db.similarity_search(question, k=3)
        
        if not docs:
            return "No relevant documents found."
            
        # Format the "found" text
        results = []
        for i, doc in enumerate(docs):
            source = doc.metadata.get('source', 'Unknown')
            content = doc.page_content.replace('\n', ' ')[:200] + "..."
            results.append(f"[bold]Source:[/bold] {source}\n[dim]{content}[/dim]")
        
        return "\n\n".join(results)

    def generate_response(self, question):
        """Full AI Answer (Paid Mode)."""
        if not self.llm:
            return self.search_knowledge_base(question)
            
        qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.vector_db.as_retriever(search_kwargs={"k": 3}),
            return_source_documents=True
        )
        response = qa_chain.invoke({"query": question})
        return response['result']

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interactive", action="store_true")
    args = parser.parse_args()

    agent = VendorResponseAgent()

    if args.interactive:
        console.rule("[bold]💬 Vendor Agent (Type 'exit' to quit)[/bold]")
        while True:
            q = input("\nQuestion: ")
            if q.lower() in ["exit", "quit"]: break
            
            if API_KEY:
                print(agent.generate_response(q))
            else:
                # Search Only Output
                result = agent.search_knowledge_base(q)
                console.print(result)
