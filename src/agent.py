import os
import pandas as pd
import argparse
import time
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

# Setup
load_dotenv()
console = Console()

DB_DIR = "./chroma_db"
DEFAULT_EXPORT = "vendor_response_export.csv"

# --- SYSTEM PROMPT (The "Persona") ---
# This ensures the AI sounds like a pragmatic Security Engineer, not a robot.
PROMPT_TEMPLATE = """
You are a Senior Security Assurance Engineer at a tech company. 
Your job is to answer vendor security questionnaires accurately based STRICTLY on the provided context.

Context from our internal policy/audit reports:
{context}

Question: 
{question}

Guidelines:
1. Answer directly and professionally.
2. If the context does not contain the answer, say "Review Required - Not found in policy."
3. Do not make up facts.
4. Keep answers concise (2-3 sentences max) unless the question asks for a list.

Answer:
"""

class VendorResponseAgent:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings()
        # Using GPT-4 for high-quality reasoning
        self.llm = ChatOpenAI(model_name="gpt-4", temperature=0)
        self.vector_db = None
        
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

        # Custom Prompt Setup
        qa_prompt = PromptTemplate(
            template=PROMPT_TEMPLATE, 
            input_variables=["context", "question"]
        )

        qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.vector_db.as_retriever(search_kwargs={"k": 4}),
            return_source_documents=True,
            chain_type_kwargs={"prompt": qa_prompt}
        )

        results = []
        
        # Fancy Progress Bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True
        ) as progress:
            task = progress.add_task(f"[cyan]Processing {len(questions)} items...", total=len(questions))
            
            for q in questions:
                # progress.update(task, description=f"Thinking: {q[:30]}...")
                
                try:
                    response = qa_chain.invoke({"query": q})
                    answer_text = response['result']
                    source_docs = response['source_documents']
                    
                    # Citation Formatting
                    if source_docs:
                        sources = [f"{doc.metadata.get('source', 'Unknown')} (Pg {doc.metadata.get('page', 1)})" for doc in source_docs]
                        formatted_sources = "; ".join(list(set(sources)))
                    else:
                        formatted_sources = "No Source Found"

                    # Confidence Grading
                    if "Review Required" in answer_text or not source_docs:
                        status = "⚠️ Review"
                    else:
                        status = "✅ Auto-Filled"

                    results.append({
                        "Question": q,
                        "AI Response": answer_text,
                        "Status": status,
                        "Evidence": formatted_sources
                    })
                    
                except Exception as e:
                    results.append({
                        "Question": q,
                        "AI Response": f"Error: {str(e)}",
                        "Status": "❌ Failed",
                        "Evidence": ""
                    })
                
                progress.advance(task)

        return pd.DataFrame(results)

def main():
    parser = argparse.ArgumentParser(description="AI Vendor Response Agent")
    parser.add_argument("--interactive", action="store_true", help="Chat mode")
    parser.add_argument("--file", help="Path to CSV containing a 'Question' column")
    args = parser.parse_args()

    agent = VendorResponseAgent()

    # MODE 1: Bulk File Processing (The "Real" Use Case)
    if args.file:
        if not os.path.exists(args.file):
            console.print(f"[red]File not found: {args.file}[/red]")
            return
            
        console.rule(f"[bold blue]📄 Bulk Processing: {args.file}[/bold blue]")
        try:
            input_df = pd.read_csv(args.file)
            if "Question" not in input_df.columns:
                console.print("[red]CSV must have a column named 'Question'[/red]")
                return
            
            questions = input_df["Question"].tolist()
            df_results = agent.generate_responses(questions)
            
            output_filename = f"completed_{os.path.basename(args.file)}"
            df_results.to_csv(output_filename, index=False)
            
            console.print(f"\n[bold green]✅ Done! Saved responses to: {output_filename}[/bold green]")
            
        except Exception as e:
            console.print(f"[red]Error processing file: {e}[/red]")

    # MODE 2: Interactive Chat
    elif args.interactive:
        console.rule("[bold yellow]💬 Interactive Mode[/bold yellow]")
        while True:
            q = input("\n[USER] Question: ")
            if q.lower() in ["exit", "quit"]: break
            
            df = agent.generate_responses([q])
            row = df.iloc[0]
            
            console.print(f"\n[AI] Answer: [cyan]{row['AI Response']}[/cyan]")
            console.print(f"[dim]Evidence: {row['Evidence']}[/dim]")

    # MODE 3: Default Demo
    else:
        standard_qs = [
            "Do you encrypt data at rest?",
            "How often do you perform penetration testing?",
            "Do you background check employees?",
            "What is your SLA for critical incidents?"
        ]
        console.rule("[bold green]🚀 Running Standard Demo[/bold green]")
        df = agent.generate_responses(standard_qs)
        
        table = Table(title="Demo Results")
        table.add_column("Question")
        table.add_column("Answer")
        table.add_column("Status")
        
        for _, row in df.iterrows():
            table.add_row(row['Question'], row['AI Response'], row['Status'])
        
        console.print(table)

if __name__ == "__main__":
    main()
