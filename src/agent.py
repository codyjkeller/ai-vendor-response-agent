import os
import pandas as pd
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.chat_models import ChatOpenAI
from langchain.chains import RetrievalQA

# Configuration
DATA_DIR = "./data"
DB_DIR = "./chroma_db"
EXPORT_FILE = "vendor_response_export.csv"

class VendorResponseAgent:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings()
        self.llm = ChatOpenAI(model_name="gpt-4o", temperature=0)
        self.vector_db = None
        
        # Initialize DB if it exists
        if os.path.exists(DB_DIR):
            self.vector_db = Chroma(persist_directory=DB_DIR, embedding_function=self.embeddings)
            print(f"✅ Loaded existing knowledge base from {DB_DIR}")

    def ingest_documents(self):
        """Loads PDFs from /data, chunks them, and builds the Vector DB."""
        print(f"📂 Loading documents from {DATA_DIR}...")
        loader = DirectoryLoader(DATA_DIR, glob="*.pdf", loader_cls=PyPDFLoader)
        docs = loader.load()
        
        if not docs:
            print("❌ No documents found in /data.")
            return

        # Split text for better retrieval context
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = splitter.split_documents(docs)
        
        print(f"🧩 Split into {len(chunks)} chunks. Building Vector DB...")
        self.vector_db = Chroma.from_documents(
            documents=chunks, 
            embedding=self.embeddings, 
            persist_directory=DB_DIR
        )
        self.vector_db.persist()
        print("✅ Knowledge base built and saved.")

    def generate_responses(self, questions):
        """
        Takes a list of questions, retrieves answers + sources, 
        and returns a structured DataFrame.
        """
        if not self.vector_db:
            print("⚠️ DB not initialized. Please run ingestion first.")
            return None

        # Create the Retrieval Chain with Source Return enabled
        qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.vector_db.as_retriever(search_kwargs={"k": 3}),
            return_source_documents=True
        )

        results = []
        
        print(f"🤖 Processing {len(questions)} questions...")
        
        for q in questions:
            print(f"   > Asking: {q}")
            response = qa_chain({"query": q})
            
            answer_text = response['result']
            source_docs = response['source_documents']
            
            # Logic for Source Citation
            if source_docs:
                sources = [f"{doc.metadata.get('source', 'Unknown')} (Pg. {doc.metadata.get('page', 0)})" for doc in source_docs]
                formatted_sources = "; ".join(list(set(sources))) # Remove duplicates
            else:
                formatted_sources = "No Source Found"

            # Logic for Low Confidence Flag
            # If the LLM says "I don't know" or source is missing, flag it.
            status = "Review Required" if "don't know" in answer_text.lower() or not source_docs else "Auto-Filled"

            results.append({
                "Question": q,
                "AI Response": answer_text,
                "Confidence Status": status,
                "Source Documents": formatted_sources
            })

        return pd.DataFrame(results)

# --- Main Execution Flow ---
if __name__ == "__main__":
    agent = VendorResponseAgent()
    
    # 1. OPTIONAL: Uncomment to re-ingest documents
    # agent.ingest_documents()

    # 2. Define your incoming Questionnaire (This could be loaded from a CSV too)
    incoming_questionnaire = [
        "Do you encrypt data at rest and in transit?",
        "Do you have a formal Incident Response Plan?",
        "Are third-party penetration tests performed annually?",
        "What is your password complexity policy?"
    ]

    # 3. Run the Agent
    df_results = agent.generate_responses(incoming_questionnaire)

    # 4. Export to CSV for Human Review
    if df_results is not None:
        df_results.to_csv(EXPORT_FILE, index=False)
        print(f"\n🚀 Success! Draft responses exported to: {EXPORT_FILE}")
        print(df_results[['Question', 'AI Response', 'Source Documents']])
