# 🤖 AI Vendor Response Agent

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![LangChain](https://img.shields.io/badge/LangChain-Enabled-orange)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

**An automated RAG (Retrieval-Augmented Generation) agent designed to streamline Third-Party Risk Management (TPRM).**

This tool ingests your company's "Source of Truth" security artifacts (SOC 2 reports, Policy PDFs, previous SIG questionnaires) and uses a local Vector Database to autonomously answer incoming security questionnaires. Unlike generic chatbots, this agent provides **Source Citations** (e.g., "See Page 4 of Access Policy") and **Confidence Scoring** to ensure audit-readiness.

## ✨ Key Features

* **📄 Audit-Ready Citations:** Every answer includes a reference to the specific source document and page number used to generate the response.
* **📊 Excel-Compatible Export:** Automatically generates a `.csv` file with answers, allowing for easy copy-pasting into vendor portals or Excel questionnaires.
* **⚠️ Confidence Flagging:** Automatically flags low-confidence answers or missing data as "Review Required" so you don't accidentally mislead an assessor.
* **🔒 Local Vector Store:** Uses `ChromaDB` locally—your sensitive embeddings are not stored in a third-party cloud vector provider.

## 🏗️ Architecture

1.  **Ingestion:** Loads PDFs from the `/data` directory.
2.  **Chunking:** Splits text into semantic chunks using `RecursiveCharacterTextSplitter`.
3.  **Embedding:** Converts text to vectors using `OpenAIEmbeddings`.
4.  **Storage:** Persists vectors in a local `ChromaDB`.
5.  **Retrieval:** The Agent queries the DB for relevant context + source metadata.
6.  **Generation:** `GPT-4o` synthesizes the answer.
7.  **Export:** Results are saved to `vendor_response_export.csv`.

## 🚀 Usage

### 1. Setup

Clone the repository and install dependencies:

```bash
git clone [https://github.com/codyjkeller/ai-vendor-response-agent.git](https://github.com/codyjkeller/ai-vendor-response-agent.git)
cd ai-vendor-response-agent
pip install -r requirements.txt

2. Configure Environment
Create a .env file in the root directory to store your OpenAI API key:
OPENAI_API_KEY=sk-your-key-here

3. Add Your Data
Place your security documents (PDFs only) into the data/ folder.

Recommended: SOC 2 Type II Report, Information Security Policy, Access Control Policy, Business Continuity Plan.
python src/agent.py

📂 Output
The tool generates a file named vendor_response_export.csv containing:
Question,AI Response,Confidence Status,Source Documents
Do you use MFA?,"Yes, we enforce MFA for all employees...",Auto-Filled,Access_Policy.pdf (Pg. 4)
Do you have ISO 27001?,I could not find mention of ISO 27001...,Review Required,No Source Found

🛡️ Data Privacy Note
Do not commit the data/ folder or .env file to GitHub. A .gitignore is included to prevent this.

While the Vector DB is local, the text chunks are sent to OpenAI for embedding and generation. Ensure this aligns with your company's AI usage policy.

📜 License
MIT
