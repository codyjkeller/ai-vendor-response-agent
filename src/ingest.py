import os
import pandas as pd
import chromadb
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import DataFrameLoader, PyPDFLoader, TextLoader, Docx2txtLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from dotenv import load_dotenv

load_dotenv()

DATA_PATH = "./data"
DB_PATH = "./chroma_db"

def create_vector_db():
    """
    Ingests all PDF, Excel, and Docx files from the 'data' folder 
    and saves them to a local ChromaDB.
    """
    if not os.path.exists(DATA_PATH):
        os.makedirs(DATA_PATH)
        print(f"Created {DATA_PATH} directory")
        return

    all_docs = []

    # 1. Loop through files in /data
    for filename in os.listdir(DATA_PATH):
        file_path = os.path.join(DATA_PATH, filename)
        
        try:
            # PDF Handler
            if filename.lower().endswith(".pdf"):
                print(f"📄 Processing PDF: {filename}")
                loader = PyPDFLoader(file_path)
                all_docs.extend(loader.load())
                
            # Excel Handler
            elif filename.lower().endswith(".xlsx"):
                print(f"📊 Processing Excel: {filename}")
                df = pd.read_excel(file_path)
                # Convert all columns to text for searching
                df = df.astype(str)
                loader = DataFrameLoader(df, page_content_column=df.columns[0])
                all_docs.extend(loader.load())
                
            # Word Handler
            elif filename.lower().endswith(".docx"):
                print(f"📝 Processing Word: {filename}")
                loader = Docx2txtLoader(file_path)
                all_docs.extend(loader.load())
                
        except Exception as e:
            print(f"⚠️ Error loading {filename}: {e}")

    if not all_docs:
        print("No documents found to ingest.")
        return

    # 2. Split text into chunks (better for AI memory)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    splits = text_splitter.split_documents(all_docs)

    # 3. Create the Database (Force Local Mode)
    print(f"💾 Saving {len(splits)} chunks to {DB_PATH}...")
    
    # Initialize a persistent client explicitly to avoid "tenant" errors
    client = chromadb.PersistentClient(path=DB_PATH)
    
    # Reset/Delete old data to avoid duplicates on re-run
    try:
        client.reset() 
    except:
        pass # If reset isn't enabled/allowed, just proceed
    
    # Create the vector store using the explicit client
    Chroma.from_documents(
        documents=splits,
        embedding=OpenAIEmbeddings(),
        client=client, 
        collection_name="vendor_knowledge"
    )
    
    print("✅ Knowledge Base Built Successfully!")

if __name__ == "__main__":
    create_vector_db()
