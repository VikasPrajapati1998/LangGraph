import streamlit as st
from backend import chatbot
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import uuid
import os

# Optional file loaders
from pypdf import PdfReader
from docx import Document

st.set_page_config(page_title="Universal Chatbot", layout="centered")

# -------------------- SESSION STATE --------------------

if "chat_id" not in st.session_state:
    st.session_state.chat_id = str(uuid.uuid4())

if "history" not in st.session_state:
    st.session_state.history = []

if "file_context" not in st.session_state:
    st.session_state.file_context = ""

if "file_injected" not in st.session_state:
    st.session_state.file_injected = False

# -------------------- FILE HANDLER --------------------

def extract_file_content(uploaded_file):
    filename = uploaded_file.name
    ext = os.path.splitext(filename)[1].lower()

    try:
        if ext in [".txt", ".py", ".js", ".html", ".css", ".c", ".cpp", ".java", ".json", ".md"]:
            return uploaded_file.read().decode("utf-8")

        if ext == ".pdf":
            reader = PdfReader(uploaded_file)
            return "\n".join(page.extract_text() or "" for page in reader.pages)

        if ext == ".docx":
            doc = Document(uploaded_file)
            return "\n".join(p.text for p in doc.paragraphs)

        return f"""Uploaded file: {filename}
                File type: {ext}
                Size: {uploaded_file.size} bytes
                (binary or unsupported format)"""

    except Exception as e:
        return f"Error reading file {filename}: {str(e)}"

# -------------------- SIDEBAR --------------------

st.sidebar.title("Chat Controls")

if st.sidebar.button("➕ New Chat"):
    st.session_state.chat_id = str(uuid.uuid4())
    st.session_state.history = []
    st.session_state.file_context = ""
    st.session_state.file_injected = False
    st.rerun()

uploaded_file = st.sidebar.file_uploader("Upload any file", type=None)

if uploaded_file is not None:
    content = extract_file_content(uploaded_file)
    if content != st.session_state.file_context:
        st.session_state.file_context = content
        st.session_state.file_injected = False
        st.sidebar.success(f"✅ {uploaded_file.name} loaded")
        
        with st.sidebar.expander("📄 File Preview"):
            st.text_area("Content", content[:800] + ("..." if len(content) > 800 else ""), height=180, disabled=True)

# -------------------- MAIN CHAT UI --------------------

st.title("💬 Universal File-Aware Chatbot")

# Show history
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User input
if prompt := st.chat_input("Type your message..."):
    
    # Save & display user message
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Prepare messages for model
    messages = []

    # Inject file context only once (at beginning of conversation)
    if st.session_state.file_context and not st.session_state.file_injected:
        messages.append(
            SystemMessage(
                content=f"""The user has uploaded a file. Use its content when relevant to answer questions.

                            FILE CONTENT:
                            {st.session_state.file_context}"""
            )
        )
        st.session_state.file_injected = True

    # Add previous history
    for msg in st.session_state.history[:-1]:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))

    # Add current user message
    messages.append(HumanMessage(content=prompt))

    # Get streaming response
    try:
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                message_placeholder = st.empty()
                full_response = ""

                # ──── REAL STREAMING ────
                for chunk, metadata in chatbot.stream(
                    {"messages": messages},
                    config={"configurable": {"thread_id": st.session_state.chat_id}},
                    stream_mode="messages"
                ):
                    if chunk.content:
                        full_response += chunk.content
                        message_placeholder.markdown(full_response + "▋")

                # Final clean output (no cursor)
                message_placeholder.markdown(full_response)

                # Save complete response
                st.session_state.history.append({
                    "role": "assistant",
                    "content": full_response
                })

    except Exception as e:
        error_msg = f"Error during generation: {str(e)}"
        st.error(error_msg)
        st.session_state.history.append({"role": "assistant", "content": error_msg})


