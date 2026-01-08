import os
import pandas as pd
import argparse
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain.chains import RetrievalQA
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# Setup
load_dotenv()
console = Console()

DB_DIR = "./chroma_db"
EXPORT_FILE = "vendor_response_export.csv"

class VendorResponseAgent:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings()
        self.llm = ChatOpenAI(model_name="gpt-4", temperature=0)
        self.vector_db = None
        
        # Load existing DB
        if os.path.exists(DB_DIR):
            self.vector_db = Chroma(persist_directory=DB_DIR, embedding_function=self.embeddings)
            console.print(f"[dim]✅ Loaded Knowledge Base from {DB_DIR}[/dim]")
        else:
            console.print("[bold red]❌ Database not found! Run 'python src/ingest.py' first.[/bold red]")

    def generate_responses(self, questions):
        """
        Takes a list of questions, retrieves answers + sources, 
        and returns a structured DataFrame.
        """
        if not self.vector_db:
            return None

        # Create the Retrieval Chain
        qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.vector_db.as_retriever(search_kwargs={"k": 3}),
            return_source_documents=True
        )

        results = []
        console.rule("[bold blue]🤖 Generating Responses[/bold blue]")
        
        for i, q in enumerate(questions, 1):
            console.print(f"[bold cyan]Q{i}:[/bold cyan] {q}")
            
            # Invoke the chain
            response = qa_chain.invoke({"query": q})
            
            answer_text = response['result']
            source_docs = response['source_documents']
            
            # Citation Logic
            if source_docs:
                sources = [f"{doc.metadata.get('source', 'Unknown')} (Pg {doc.metadata.get('page', 0)})" for doc in source_docs]
                formatted_sources = "; ".join(list(set(sources)))
                console.print(f"[green]   -> Answered with {len(source_docs)} citations.[/green]")
            else:
                formatted_sources = "No Source Found"
                console.print("[red]   -> No sources found.[/red]")

            # Confidence Logic
            status = "Review Required" if "don't know" in answer_text.lower() or not source_docs else "Auto-Filled"

            results.append({
                "Question": q,
                "AI Response": answer_text,
                "Confidence Status": status,
                "Source Documents": formatted_sources
            })

        return pd.DataFrame(results)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Vendor Response Agent")
    parser.add_argument("--interactive", action="store_true", help="Ask a single question in CLI mode")
    args = parser.parse_args()

    agent = VendorResponseAgent()

    if args.interactive:
        # Chat Mode
        console.print("[yellow]💬 Interactive Mode (Type 'exit' to quit)[/yellow]")
        while True:
            q = input("\nQuestion: ")
            if q.lower() in ["exit", "quit"]: break
            df = agent.generate_responses([q])
            console.print(f"\n[bold]Answer:[/bold] {df.iloc[0]['AI Response']}")
            console.print(f"[dim]Source: {df.iloc[0]['Source Documents']}[/dim]")
    else:
        # Batch Mode (The "Product" Demo)
        standard_questionnaire = [
            "Do you encrypt data at rest and in transit?",
            "Do you have a formal Incident Response Plan?",
            "How often are third-party penetration tests performed?",
            "What is your password complexity policy?",
            "Do you utilize multi-factor authentication (MFA) for production access?"
        ]
        
        df_results = agent.generate_responses(standard_questionnaire)
        
        if df_results is not None:
            # Save to CSV
            df_results.to_csv(EXPORT_FILE, index=False)
            
            # Print Pretty Table
            table = Table(title="Generated Security Responses")
            table.add_column("Question", style="cyan")
            table.add_column("Status", style="bold")
            table.add_column("Source", style="dim")
            
            for _, row in df_results.iterrows():
                status_color = "green" if row['Confidence Status'] == "Auto-Filled" else "red"
                table.add_row(
                    row['Question'][:50] + "...", 
                    f"[{status_color}]{row['Confidence Status']}[/{status_color}]",
                    row['Source Documents'][:30] + "..."
                )
            
            console.print(table)
            console.print(f"\n[bold green]💾 Exported full report to: {EXPORT_FILE}[/bold green]")
