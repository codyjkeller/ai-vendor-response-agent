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
INPUT_FILE = "questionnaire_input.csv"  # The file you get from a vendor
OUTPUT_FILE = "vendor_response_complete.csv"

# The prompt engineering that prevents hallucinations
RAG_PROMPT = """
You are a Senior Security Engineer answering a vendor security questionnaire.
Use ONLY the provided context to answer the question. 

Rules:
1. If the answer is in the context, cite the specific document name.
2. If the context does NOT contain the answer, say "Review Required - Not found in Knowledge Base".
3. Keep answers professional, concise, and audit-ready.

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
        self.llm = ChatOpenAI(model_name="gpt-4-turbo", temperature=0)
        self.retriever = self.vector_db.as_retriever(search_kwargs={"k": 4})

    def format_docs(self, docs):
        """Helper to format retrieved docs for the prompt"""
        return "\n\n".join(f"[Source: {d.metadata.get('source_file', 'Unknown')}, Page: {d.metadata.get('page', '0')}]\n{d.page_content}" for d in docs)

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
            return response.content, source_str
        except Exception as e:
            return f"Error: {e}", "N/A"

    def process_file(self):
        if not os.path.exists(INPUT_FILE):
            self.console.print(f"[red]❌ Input file '{INPUT_FILE}' not found.[/red]")
            self.console.print("   -> Create a CSV with a column named 'Question'.")
            return

        self.console.rule("[bold blue]📝 Vendor Questionnaire Agent[/bold blue]")
        
        # Load CSV
        df = pd.read_csv(INPUT_FILE)
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
                
                # Simple confidence logic
                if "Review Required" in ans:
                    status_list.append("🔴 Low Confidence")
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
