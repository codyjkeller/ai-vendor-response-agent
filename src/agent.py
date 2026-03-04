import os
import pandas as pd
import argparse
import chromadb
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from sqlalchemy.orm import Session
from thefuzz import fuzz

# Import Database logic
from database import SessionLocal, AnswerBank

# Setup
load_dotenv()
console = Console()

DB_DIR = "./chroma_db"
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").lower()  # "openai", "anthropic", or "" (auto-detect)
LLM_MODEL = os.getenv("LLM_MODEL")  # Optional override

PROMPT_TEMPLATE = """
You are a Security Compliance Officer. Answer the questionnaire based STRICTLY on the context.
If the context is missing, state "Review Required".

Context: {context}
Question: {question}

Answer:
"""

def resolve_provider():
    """Determines which LLM provider to use based on env config."""
    # Explicit override
    if LLM_PROVIDER == "anthropic" and ANTHROPIC_KEY:
        return "anthropic"
    if LLM_PROVIDER == "openai" and OPENAI_KEY:
        return "openai"
    
    # Auto-detect: prefer whichever key is set (Anthropic first if both)
    if ANTHROPIC_KEY:
        return "anthropic"
    if OPENAI_KEY:
        return "openai"
    
    return "local"

def get_llm(provider):
    """Returns the LLM instance for the detected provider."""
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        model = LLM_MODEL or "claude-sonnet-4-20250514"
        console.print(f"[bold green]✅ Anthropic API Key found. Using {model}.[/bold green]")
        return ChatAnthropic(model=model, temperature=0, anthropic_api_key=ANTHROPIC_KEY)
    
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        model = LLM_MODEL or "gpt-4"
        console.print(f"[bold green]✅ OpenAI API Key found. Using {model}.[/bold green]")
        return ChatOpenAI(model_name=model, temperature=0, openai_api_key=OPENAI_KEY)
    
    else:
        console.print("[bold yellow]⚠️  No API Key found. Running in SEARCH-ONLY mode.[/bold yellow]")
        return None

def get_embeddings(provider):
    """Returns embeddings — uses OpenAI if available, otherwise HuggingFace."""
    if provider == "openai" or (provider == "anthropic" and OPENAI_KEY):
        # Anthropic doesn't have its own embeddings, so use OpenAI if available
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(openai_api_key=OPENAI_KEY)
    else:
        return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

class VendorResponseAgent:
    def __init__(self):
        self.provider = resolve_provider()
        self.llm = get_llm(self.provider)
        self.embeddings = get_embeddings(self.provider)

        # --- DATABASE CONNECTION ---
        if os.path.exists(DB_DIR):
            try:
                # FORCE LOCAL CLIENT (Fixes 'tenant' error on Streamlit Cloud)
                self.client = chromadb.PersistentClient(path=DB_DIR)
                
                self.vector_db = Chroma(
                    client=self.client,
                    collection_name="vendor_knowledge", # Must match ingest.py
                    embedding_function=self.embeddings
                )
                console.print("[green]✅ Knowledge Base Loaded.[/green]")
            except Exception as e:
                console.print(f"[red]❌ Error loading DB: {e}[/red]")
                self.vector_db = None
        else:
            console.print("[red]❌ DB not found. Run 'python src/ingest.py'[/red]")
            self.vector_db = None

    def check_answer_bank(self, question, threshold=85):
        """Checks the SQL Master Bank for a similar existing answer."""
        db: Session = SessionLocal()
        try:
            # Get all verified answers
            known_entries = db.query(AnswerBank).all()
            best_match = None
            highest_score = 0

            for entry in known_entries:
                # Fuzzy match score (0-100)
                score = fuzz.ratio(question.lower(), entry.question.lower())
                if score > highest_score:
                    highest_score = score
                    best_match = entry

            if highest_score >= threshold:
                return best_match.answer, f"Answer Bank Match ({highest_score}%)"
            
            return None, None
        finally:
            db.close()

    def generate_responses(self, questions):
        """Generates responses using Bank -> AI -> Search fallback strategy."""
        results = []
        
        # Setup Retrieval Chain (if LLM exists)
        qa_chain = None
        if self.llm and self.vector_db:
            qa_prompt = PromptTemplate(template=PROMPT_TEMPLATE, input_variables=["context", "question"])
            qa_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff",
                retriever=self.vector_db.as_retriever(search_kwargs={"k": 3}),
                return_source_documents=True,
                chain_type_kwargs={"prompt": qa_prompt}
            )

        # Use Rich Progress bar for CLI (Streamlit ignores this mostly)
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
            task = progress.add_task(f"[cyan]Processing {len(questions)} items...", total=len(questions))
            
            for q in questions:
                try:
                    # STEP 1: Check Master Bank (Secure Cache)
                    bank_ans, bank_source = self.check_answer_bank(q)
                    
                    if bank_ans:
                        # Found in Bank -> Use it immediately
                        results.append({
                            "Question": q, 
                            "AI_Response": bank_ans, 
                            "Status": "✅ Verified (Bank)", 
                            "Evidence": bank_source
                        })
                        progress.advance(task)
                        continue

                    # STEP 2: Use AI (RAG)
                    if qa_chain:
                        response = qa_chain.invoke({"query": q})
                        answer = response['result']
                        docs = response['source_documents']
                        
                        status = "⚠️ Review" if "Review Required" in answer else "🤖 AI Generated"
                        evidence = "; ".join([f"{d.metadata.get('source','Doc')}" for d in docs])
                        
                        results.append({
                            "Question": q,
                            "AI_Response": answer,
                            "Status": status,
                            "Evidence": evidence
                        })
                    
                    # STEP 3: Fallback (Search Only / No LLM)
                    elif self.vector_db:
                        docs = self.vector_db.similarity_search(q, k=3)
                        evidence = "; ".join([f"{d.metadata.get('source','Doc')}" for d in docs])
                        results.append({
                            "Question": q, 
                            "AI_Response": "API Key Required for Answer", 
                            "Status": "🔍 Search Result", 
                            "Evidence": evidence
                        })
                    else:
                        results.append({"Question": q, "AI_Response": "No Knowledge Base", "Status": "❌ Failed"})

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
            row = df.iloc[0]
            console.print(f"\n[bold]Answer:[/bold] {row['AI_Response']}")
            console.print(f"[dim]Status: {row['Status']} | Evidence: {row['Evidence']}[/dim]")
    
    elif args.file:
        if os.path.exists(args.file):
            df = pd.read_csv(args.file)
            if "Question" in df.columns:
                results_df = agent.generate_responses(df["Question"].tolist())
                results_df.to_csv("completed_responses.csv", index=False)
                console.print("\n[bold green]✅ Saved to completed_responses.csv[/bold green]")
