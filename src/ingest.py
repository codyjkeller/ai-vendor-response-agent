import os
import pandas as pd
import chromadb
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import DataFrameLoader, PyPDFLoader, Docx2txtLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from dotenv import load_dotenv

load_dotenv()

DATA_PATH = "./data"
DB_PATH = "./chroma_db"

def create_vector_db():
    if not os.path.exists(DATA_PATH):
        os.makedirs(DATA_PATH)
        return

    all_docs = []
    
    for filename in os.listdir(DATA_PATH):
        file_path = os.path.join(DATA_PATH, filename)
        try:
            if filename.lower().endswith(".pdf"):
                loader = PyPDFLoader(file_path)
                all_docs.extend(loader.load())
            elif filename.lower().endswith(".xlsx"):
                df = pd.read_excel(file_path).astype(str)
                loader = DataFrameLoader(df, page_content_column=df.columns[0])
                all_docs.extend(loader.load())
            elif filename.lower().endswith(".docx"):
                loader = Docx2txtLoader(file_path)
                all_docs.extend(loader.load())
        except Exception as e:
            print(f"Error loading {filename}: {e}")

    if not all_docs:
        return

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    splits = text_splitter.split_documents(all_docs)

    # FORCE LOCAL CLIENT (Fixes Tenant Error)
    client = chromadb.PersistentClient(path=DB_PATH)
    try: client.reset() 
    except: pass
    
    Chroma.from_documents(
        documents=splits,
        embedding=OpenAIEmbeddings(),
        client=client, 
        collection_name="vendor_knowledge"
    )
    print("✅ Knowledge Base Built Successfully!")

if __name__ == "__main__":
    create_vector_db()
