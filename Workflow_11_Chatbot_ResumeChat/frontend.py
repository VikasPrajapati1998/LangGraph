import streamlit as st
from backend import chatbot
from langchain_core.messages import HumanMessage
import uuid

# -------------------- PAGE CONFIG --------------------

st.set_page_config(
    page_title="Universal Chatbot",
    layout="centered"
)

# -------------------- SESSION STATE --------------------

# Active chat id
if "chat_id" not in st.session_state:
    st.session_state.chat_id = str(uuid.uuid4())

# Store ALL chats: chat_id -> message list
if "chat_histories" not in st.session_state:
    st.session_state.chat_histories = {
        st.session_state.chat_id: []
    }

# Ensure current chat exists
if st.session_state.chat_id not in st.session_state.chat_histories:
    st.session_state.chat_histories[st.session_state.chat_id] = []

# -------------------- SIDEBAR --------------------

st.sidebar.title("Chat Controls")

# New chat button
if st.sidebar.button("➕ New Chat"):
    new_chat_id = str(uuid.uuid4())
    st.session_state.chat_id = new_chat_id
    st.session_state.chat_histories[new_chat_id] = []
    st.rerun()

st.sidebar.divider()
st.sidebar.header("My Conversations")

# Chat selector (NO LangChain sync here)
for thread_id in st.session_state.chat_histories.keys():
    if st.sidebar.button(thread_id[:8], key=f"chat_{thread_id}"):
        st.session_state.chat_id = thread_id
        st.rerun()

st.sidebar.divider()
st.sidebar.caption(f"Active Chat ID:\n{st.session_state.chat_id}")

# -------------------- MAIN CHAT UI --------------------

st.title("Arya Chatbot")

current_history = st.session_state.chat_histories[st.session_state.chat_id]

# Display chat history
for msg in current_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# -------------------- USER INPUT --------------------

if prompt := st.chat_input("Type your message..."):

    # Store & display user message
    current_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                placeholder = st.empty()
                full_response = ""

                # SEND ONLY THE NEW MESSAGE
                for chunk, metadata in chatbot.stream(
                    {"messages": [HumanMessage(content=prompt)]},
                    config={
                        "configurable": {
                            "thread_id": st.session_state.chat_id
                        }
                    },
                    stream_mode="messages"
                ):
                    if chunk.content:
                        full_response += chunk.content
                        placeholder.markdown(full_response + "▋")

                placeholder.markdown(full_response)

        # Store assistant response
        current_history.append({
            "role": "assistant",
            "content": full_response
        })

    except Exception as e:
        error_msg = f"Error during generation: {str(e)}"
        st.error(error_msg)
        current_history.append({
            "role": "assistant",
            "content": error_msg
        })

