import streamlit as st
import pandas as pd
import os
import sys

# --- Path Setup (Crucial for Cloud Imports) ---
# This tells Python to look in the current directory for agent.py and ingest.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent import VendorResponseAgent
from ingest import create_vector_db

# --- Page Config ---
st.set_page_config(
    page_title="Vendor AI Agent",
    page_icon="🛡️",
    layout="centered"
)

# --- Cloud Self-Healing: Build DB if missing ---
# Streamlit Cloud wipes the disk on restart, so we must rebuild the brain if it's gone.
if not os.path.exists("./chroma_db"):
    if os.path.exists("./data"):
        with st.spinner("🤖 First run detected. Building Knowledge Base..."):
            try:
                # Re-run the ingest script to build the vector DB
                create_vector_db()
                st.success("✅ Knowledge Base Built!")
            except Exception as e:
                st.error(f"Failed to build database: {e}")
    else:
        st.error("❌ Data folder not found! Please make sure you committed the 'data' folder to GitHub.")

# --- Session State (Memory) ---
if "messages" not in st.session_state:
    st.session_state.messages = []

if "agent" not in st.session_state:
    # Initialize the agent once and cache it
    st.session_state.agent = VendorResponseAgent()

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Settings")
    
    # Model Status
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        st.success("🟢 AI Model: GPT-4 (Online)")
    else:
        st.warning("🟡 AI Model: Search Only (Offline)")

    st.divider()
    
    # Knowledge Base Status
    if os.path.exists("./chroma_db"):
        st.info(f"📚 Knowledge Base: Active")
    else:
        st.error("🔴 Knowledge Base: Missing")

    st.divider()
    if st.button("🧹 Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

# --- Main Interface ---
st.title("🛡️ Security Questionnaire Agent")
st.caption("Ask questions about your SOC 2, Security Policies, or previous SIG questionnaires.")

# 1. Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "evidence" in message and message["evidence"]:
            with st.expander("🔍 View Source Evidence"):
                st.markdown(message["evidence"])

# 2. Chat Input
if prompt := st.chat_input("Ex: Do we use Multi-Factor Authentication?"):
    # Add User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate Response
    with st.chat_message("assistant"):
        with st.spinner("Analyzing security artifacts..."):
            try:
                # Use the agent to get a response (returns a DataFrame)
                df = st.session_state.agent.generate_responses([prompt])
                
                # Extract the first row
                if not df.empty:
                    answer = df.iloc[0]['AI_Response']
                    evidence = df.iloc[0]['Evidence']
                    
                    # Display Answer
                    st.markdown(answer)
                    
                    # Display Evidence
                    if evidence and evidence != "No Source":
                        with st.expander("🔍 View Source Evidence"):
                            st.markdown(evidence)

                    # Save to History
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": answer,
                        "evidence": evidence
                    })
                else:
                    st.error("No response generated.")
                
            except Exception as e:
                st.error(f"An error occurred: {e}")
