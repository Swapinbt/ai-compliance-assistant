import os
import json
import glob
from datetime import datetime
import PyPDF2
import docx
import requests
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st
from openai import OpenAI

# ------------------ AUTH ------------------
st.set_page_config(page_title="AI Compliance Assistant", layout="wide")
PASSWORD = os.getenv("APP_PASSWORD", "admin123")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    with st.form("login_form"):
        st.title("🔐 Login to AI Compliance Assistant")
        password = st.text_input("Enter password:", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            if password == PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Incorrect password")
    st.stop()

# ------------------ OPENAI SETUP ------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# ------------------ KNOWLEDGE BASE ------------------
compliance_knowledge = """
1. CBB Rulebook Volume 5 (Specialized Licensees):
   - FC Module: Financial Crime
   - HC Module: High-Level Controls
   - RR Module: Regulatory Reporting

2. Company-Specific Policies:
   - KYC Onboarding Guidelines
   - AML Transaction Monitoring Rules
   - Regulatory Reporting Schedule
"""

# ------------------ LOAD DOCUMENTS ------------------
def load_documents_from_folder(folder_path: str) -> str:
    docs = []
    for file_path in glob.glob(os.path.join(folder_path, '*')):
        if file_path.endswith(".pdf"):
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = " ".join([page.extract_text() or "" for page in reader.pages])
                docs.append(text)
        elif file_path.endswith(".docx"):
            doc = docx.Document(file_path)
            text = " ".join([para.text for para in doc.paragraphs])
            docs.append(text)
    return "\n".join(docs)

# ------------------ SCRAPE WEBSITE ------------------
def get_regulations_from_website(url: str) -> str:
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        text = ' '.join([p.get_text() for p in soup.find_all(['p', 'li'])])
        return text.strip()
    except Exception as e:
        return f"Error fetching website: {e}"

# ------------------ LOG QUERIES ------------------
def log_query(question: str, answer: str, logfile: str = "query_log.json"):
    record = {
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "answer": answer
    }
    if os.path.exists(logfile):
        with open(logfile, 'r+') as f:
            logs = json.load(f)
            logs.append(record)
            f.seek(0)
            json.dump(logs, f, indent=2)
    else:
        with open(logfile, 'w') as f:
            json.dump([record], f, indent=2)

# ------------------ ASK AI ------------------
def query_compliance_agent(prompt: str, extra_docs_folder: str = None, website_url: str = None) -> str:
    folder_content = load_documents_from_folder(extra_docs_folder) if extra_docs_folder else ""
    web_content = get_regulations_from_website(website_url) if website_url else ""

    system_prompt = f"""
You are a senior compliance assistant AI trained on the Central Bank of Bahrain (CBB) Rulebook, internal fintech policies, and regulatory practices. 
Provide responses with direct references (Volume, Module, Clause) and actionable guidance.

Knowledge Base:
{compliance_knowledge}

Document Extracts:
{folder_content[:2000]}...

Website Content:
{web_content[:2000]}...
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]

    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        temperature=0.2
    )

    answer = response.choices[0].message.content
    log_query(prompt, answer)
    return answer

# ------------------ UI ------------------
tabs = st.tabs(["💬 Ask Compliance AI", "📊 Audit Dashboard"])

with tabs[0]:
    st.title("💬 AI Compliance Assistant")
    with st.sidebar:
        st.header("📂 Document & Source Settings")
        doc_folder = st.text_input("Folder path to PDF/Word files", value="./regulations")
        website_url = st.text_input("(Optional) Regulatory Website URL", value="")

    user_query = st.text_area("🔍 Ask a compliance question:", height=100)
    submit = st.button("Submit Query")

    if submit and user_query.strip():
        with st.spinner("Thinking..."):
            try:
                response = query_compliance_agent(user_query.strip(), extra_docs_folder=doc_folder, website_url=website_url.strip())
                st.markdown("---")
                st.subheader("✅ Response")
                st.write(response)
            except Exception as e:
                st.error(f"⚠️ Error: {e}")

with tabs[1]:
    st.title("📊 Audit Dashboard – Query Logs")
    try:
        df = pd.read_json("query_log.json")
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        st.dataframe(df.sort_values(by="timestamp", ascending=False), use_container_width=True)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Logs", data=csv, file_name="query_log.csv")
    except Exception as e:
        st.warning("No logs found yet or error reading file.")
