import argparse
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from dotenv import load_dotenv

load_dotenv()
DB_PATH = "./db"

PROMPT_TEMPLATE = """
You are a Security Compliance Officer. 
Answer the following vendor questionnaire question based strictly on the provided context.
If the context does not contain the answer, state "Requires manual review."

Context:
{context}

---

Question: {question}
Answer (Professional & Concise):
"""

def query_agent(question_text):
    embedding_function = OpenAIEmbeddings()
    db = Chroma(persist_directory=DB_PATH, embedding_function=embedding_function)

    results = db.similarity_search_with_score(question_text, k=3)
    context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])

    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(context=context_text, question=question_text)

    model = ChatOpenAI(model="gpt-4o-mini")
    response = model.invoke(prompt)

    print(f"\n❓ Q: {question_text}")
    print(f"✅ A: {response.content}\n")
    return response.content

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("question", type=str, help="The security question to answer.")
    args = parser.parse_args()

    query_agent(args.question)
