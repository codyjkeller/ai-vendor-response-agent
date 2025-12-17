# 🤖 AI Vendor Response Agent

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![LangChain](https://img.shields.io/badge/LangChain-Enabled-orange)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

**An automated RAG (Retrieval-Augmented Generation) agent designed to streamline Third-Party Risk Management (TPRM).** This tool ingests historical security artifacts (SOC 2 reports, policies, previous SIG questionnaires) and uses a Vector Database to autonomously answer incoming security questionnaires with high accuracy.

## 🏗️ Architecture

1.  **Ingestion:** Loads PDFs/TXT files from the `/data` directory.
2.  **Chunking:** Splits text into semantic chunks using `RecursiveCharacterTextSplitter`.
3.  **Embedding:** Converts text to vectors using `OpenAIEmbeddings`.
4.  **Storage:** Persists vectors in a local `ChromaDB`.
5.  **Retrieval:** The Agent queries the DB for relevant context before answering via `GPT-4o`.

## 🚀 Usage

### 1. Setup
```bash
pip install -r requirements.txt
