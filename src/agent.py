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
from rich.progress import Progress, SpinnerColumn, TextColumn

# Setup
load_dotenv()
console = Console()

DB_DIR = "./chroma_db"
API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = os.getenv("LLM_MODEL", "gpt-4")

PROMPT_TEMPLATE = """
You are a Security Compliance Officer. Answer the questionnaire based STRICTLY on the context.
If the context is missing, state "Review Required".

Context: {context}
Question: {question}

Answer:
"""

class VendorResponseAgent:
    def __init__(self):
        if not API_KEY:
            console.print("[bold yellow]⚠️  No API Key found. Running in SEARCH-ONLY mode.[/bold yellow]")
            self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            self.llm = None
        else:
            console.print(f"[bold green]✅ API Key found. Using {MODEL_NAME}.[/bold green]")
            self.embeddings = OpenAIEmbeddings()
            self.llm = ChatOpenAI(model_name=MODEL_NAME, temperature=0)

        if os.path.exists(DB_DIR):
            self.vector_db = Chroma(persist_directory=DB_DIR, embedding_function=self.embeddings)
        else:
            console.print("[red]❌ DB not found. Run 'python src/ingest.py'[/red]")
            self.vector_db = None

    def generate_responses(self, questions):
        """Generates AI responses (if key exists) or Search results (if no key)."""
        if not self.vector_db: return None
        
        results = []
        
        # Setup Retrieval Chain (if LLM exists)
        qa_chain = None
        if self.llm:
            qa_prompt = PromptTemplate(template=PROMPT_TEMPLATE, input_variables=["context", "question"])
            qa_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff",
                retriever=self.vector_db.as_retriever(search_kwargs={"k": 3}),
                return_source_documents=True,
                chain_type_kwargs={"prompt": qa_prompt}
            )

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
            task = progress.add_task(f"[cyan]Processing {len(questions)} items...", total=len(questions))
            
            for q in questions:
                try:
                    if self.llm:
                        # Full AI Mode
                        response = qa_chain.invoke({"query": q})
                        answer = response['result']
                        docs = response['source_documents']
                        status = "⚠️ Review" if "Review Required" in answer else "✅ Auto-Filled"
                    else:
                        # Search Only Mode
                        docs = self.vector_db.similarity_search(q, k=3)
                        answer = "API Key Required for AI Answer. See Evidence."
                        status = "🔍 Search Result"

                    # Evidence Logic
                    evidence = "; ".join([f"{d.metadata.get('source','Doc')}" for d in docs]) if docs else "No Source"

                    results.append({
                        "Question": q,
                        "AI_Response": answer,
                        "Status": status,
                        "Evidence": evidence
                    })
                except Exception as e:
                    results.append({"Question": q, "AI_Response": f"Error: {e}", "Status": "❌ Failed"})
                
                progress.advance(task)

        return pd.DataFrame(results)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--file", help="CSV with 'Question' column")
    args = parser.parse_args()

    agent = VendorResponseAgent()

    if args.interactive:
        console.rule("[bold]💬 Vendor Agent (Type 'exit' to quit)[/bold]")
        while True:
            q = input("\nQuestion: ")
            if q.lower() in ["exit", "quit"]: break
            df = agent.generate_responses([q])
            console.print(f"\n[bold]Answer:[/bold] {df.iloc[0]['AI_Response']}")
            console.print(f"[dim]Evidence: {df.iloc[0]['Evidence']}[/dim]")
    
    elif args.file:
        if os.path.exists(args.file):
            df = pd.read_csv(args.file)
            if "Question" in df.columns:
                results_df = agent.generate_responses(df["Question"].tolist())
                results_df.to_csv("completed_responses.csv", index=False)
                console.print("\n[bold green]✅ Saved to completed_responses.csv[/bold green]")
