import streamlit as st
from backend import run_chat
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import uuid
import os

# Optional loaders
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
    """Extract text content from various file types."""
    filename = uploaded_file.name
    ext = os.path.splitext(filename)[1].lower()

    try:
        # TEXT FILES
        if ext in [".txt", ".py", ".js", ".html", ".css", ".c", ".cpp", ".java", ".json", ".md"]:
            return uploaded_file.read().decode("utf-8")

        # PDF FILE
        if ext == ".pdf":
            reader = PdfReader(uploaded_file)
            return "\n".join(page.extract_text() or "" for page in reader.pages)

        # DOCX FILE
        if ext == ".docx":
            doc = Document(uploaded_file)
            return "\n".join(p.text for p in doc.paragraphs)

        # UNKNOWN / BINARY FILE
        return f"""Uploaded file: {filename}
        File type: {ext}
        Size: {uploaded_file.size} bytes
        This is a binary or unsupported format."""

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

uploaded_file = st.sidebar.file_uploader(
    "Upload any file",
    type=None
)

if uploaded_file:
    content = extract_file_content(uploaded_file)
    if content != st.session_state.file_context:
        st.session_state.file_context = content
        st.session_state.file_injected = False
        st.sidebar.success(f"✅ {uploaded_file.name} loaded")
        
        # Show preview of file content
        with st.sidebar.expander("📄 View File Content"):
            st.text_area(
                "Extracted Content",
                value=content[:500] + ("..." if len(content) > 500 else ""),
                height=200,
                disabled=True
            )

# -------------------- CHAT UI --------------------

st.title("💬 Universal File Chatbot")

# Display chat history
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Handle user input
user_input = st.chat_input("Type your message...")

if user_input:
    # Add user message to history
    st.session_state.history.append({"role": "user", "content": user_input})
    
    with st.chat_message("user"):
        st.write(user_input)

    # Prepare messages for the model
    messages = []

    # Inject file context ONLY ONCE at the beginning
    if st.session_state.file_context and not st.session_state.file_injected:
        messages.append(
            SystemMessage(
                content=f"""The user has uploaded a file. Use its content to answer their questions.

                FILE CONTENT:
                {st.session_state.file_context}"""
            )
        )
        st.session_state.file_injected = True

    # Add conversation history (excluding the current message we just added)
    for msg in st.session_state.history[:-1]:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))

    # Add the current user message
    messages.append(HumanMessage(content=user_input))

    # Get AI response with error handling
    try:
        with st.spinner("Thinking..."):
            result = run_chat(messages, st.session_state.chat_id)
            ai_reply = result["messages"][-1].content

        # Add AI response to history
        st.session_state.history.append({"role": "assistant", "content": ai_reply})
        
        with st.chat_message("assistant"):
            st.write(ai_reply)
            
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        st.session_state.history.append({"role": "assistant", "content": error_msg})
        
        with st.chat_message("assistant"):
            st.error(error_msg)
