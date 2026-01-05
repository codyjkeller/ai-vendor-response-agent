import os
import pandas as pd
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from dotenv import load_dotenv
from rich.console import Console

# Setup
load_dotenv()
console = Console()
DB_DIR = "./chroma_db"
INPUT_FILE = "questionnaire_input.csv"
OUTPUT_FILE = "vendor_response_complete.csv"

# 🛡️ THE GUARDRAILS PROMPT
# This is the "Brain" of the agent. We strictly limit it to context and length.
RAG_PROMPT = """
You are a strict Compliance Officer answering a security questionnaire. 
Your goal is to provide a binary answer (Yes/No) followed by a short justification based ONLY on the context.

 STRICT RULES:
1. Answer in 1-2 sentences MAX. Be extremely concise.
2. Start with "Yes," "No," or "Partially" if applicable.
3. If the answer is NOT explicitly in the context below, output EXACTLY: "Review Required - Not found in Knowledge Base".
4. Do NOT make up information. Do NOT use outside knowledge.
5. If the context mentions a specific policy name (e.g., "Access Control Policy"), cite it.

Context:
{context}

Question:
{question}

Answer:
"""

class VendorResponder:
    def __init__(self):
        self.console = Console()
        
        # Load the existing Database
        if not os.path.exists(DB_DIR):
            self.console.print("[red]❌ Knowledge Base not found. Run 'src/builder.py' first![/red]")
            raise FileNotFoundError

        self.vector_db = Chroma(
            persist_directory=DB_DIR,
            embedding_function=OpenAIEmbeddings(model="text-embedding-3-small")
        )
        
        # Temperature=0 is CRITICAL for reducing hallucinations
        self.llm = ChatOpenAI(model_name="gpt-4-turbo", temperature=0)
        
        # k=4 means "Find the 4 most relevant paragraphs"
        self.retriever = self.vector_db.as_retriever(search_kwargs={"k": 4})

    def format_docs(self, docs):
        """Helper to format retrieved docs for the prompt"""
        return "\n\n".join(f"[Source: {d.metadata.get('source_file', 'Unknown')}]\n{d.page_content}" for d in docs)

    def generate_answer(self, question):
        """Retrieves context and generates an answer"""
        # 1. Retrieve
        docs = self.retriever.invoke(question)
        context_text = self.format_docs(docs)
        
        # 2. Extract Sources (for the Excel export)
        sources = list(set([d.metadata.get('source_file', 'Unknown') for d in docs]))
        source_str = ", ".join(sources)

        # 3. Generate
        prompt = ChatPromptTemplate.from_template(RAG_PROMPT)
        chain = (
            {"context": lambda x: context_text, "question": RunnablePassthrough()}
            | prompt
            | self.llm
        )
        
        try:
            response = chain.invoke(question)
            content = response.content.strip()
            return content, source_str
        except Exception as e:
            return f"Error: {e}", "N/A"

    def process_file(self):
        if not os.path.exists(INPUT_FILE):
            self.console.print(f"[red]❌ Input file '{INPUT_FILE}' not found.[/red]")
            self.console.print("   -> Create a CSV with a column named 'Question'.")
            return

        self.console.rule("[bold blue]📝 Vendor Questionnaire Agent[/bold blue]")
        
        # Load CSV
        try:
            df = pd.read_csv(INPUT_FILE)
        except Exception as e:
            self.console.print(f"[red]❌ Error reading CSV: {e}[/red]")
            return

        if 'Question' not in df.columns:
            self.console.print("[red]❌ CSV must have a column named 'Question'[/red]")
            return

        self.console.print(f"📋 Loaded {len(df)} questions from {INPUT_FILE}\n")

        # Iterate and Answer
        answers = []
        sources_list = []
        status_list = []

        with self.console.status("[bold green]🤖 Agent is writing answers...[/bold green]"):
            for q in df['Question']:
                ans, src = self.generate_answer(q)
                answers.append(ans)
                sources_list.append(src)
                
                # Confidence Logic: If the Agent says "Review Required", mark it RED
                if "Review Required" in ans:
                    status_list.append("🔴 Manual Review")
                else:
                    status_list.append("🟢 Auto-Filled")

        # Save Results
        df['AI_Response'] = answers
        df['Sources'] = sources_list
        df['Status'] = status_list
        
        df.to_csv(OUTPUT_FILE, index=False)
        self.console.print(f"\n[bold green]✅ Job Complete![/bold green] Results saved to: [underline]{OUTPUT_FILE}[/underline]")

if __name__ == "__main__":
    agent = VendorResponder()
    agent.process_file()
