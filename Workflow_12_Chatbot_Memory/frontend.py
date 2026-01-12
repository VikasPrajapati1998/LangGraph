import streamlit as st
from backend import chatbot
from langchain_core.messages import HumanMessage
import uuid

# -------------------- PAGE CONFIG --------------------
st.set_page_config(
    page_title="Universal Chatbot",
    layout="centered"
)

# -------------------- SESSION STATE INITIALIZATION --------------------
# 1. ALL_CHAT_HISTORY: Acts as database - stores ALL conversations
# Structure: {thread_id: [{"role": "user"/"assistant", "content": "..."}]}
if "all_chat_history" not in st.session_state:
    st.session_state.all_chat_history = {}

# 2. Active thread ID
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.all_chat_history[st.session_state.thread_id] = []

# 3. CHAT_HISTORY: Current/selected chat history (reference to active chat)
if "chat_history" not in st.session_state:
    st.session_state.chat_history = st.session_state.all_chat_history[st.session_state.thread_id]

# -------------------- HELPER FUNCTIONS --------------------
def create_new_chat():
    """Create a new chat and switch to it"""
    new_thread_id = str(uuid.uuid4())
    st.session_state.all_chat_history[new_thread_id] = []
    st.session_state.thread_id = new_thread_id
    st.session_state.chat_history = st.session_state.all_chat_history[new_thread_id]

def switch_to_chat(thread_id):
    """Switch to an existing chat"""
    st.session_state.thread_id = thread_id
    st.session_state.chat_history = st.session_state.all_chat_history[thread_id]

# -------------------- SIDEBAR --------------------
st.sidebar.title("Chat Controls")

# New chat button
if st.sidebar.button("New Chat"):
    create_new_chat()
    st.rerun()

st.sidebar.divider()
st.sidebar.header("My Conversations")

# Display all chats
for thread_id in st.session_state.all_chat_history.keys():
    # Create preview text
    chat_messages = st.session_state.all_chat_history[thread_id]
    if chat_messages:
        first_msg = chat_messages[0]["content"]
        preview = first_msg[:25] + "..." if len(first_msg) > 25 else first_msg
    else:
        preview = f"Chat {thread_id[:8]}"
    
    # Highlight active chat
    is_active = (thread_id == st.session_state.thread_id)
    button_label = f"{'🔵 ' if is_active else ''}{preview}"
    
    if st.sidebar.button(button_label, key=f"chat_{thread_id}", disabled=is_active):
        switch_to_chat(thread_id)
        st.rerun()

st.sidebar.divider()
st.sidebar.caption(f"Active Thread:\n{st.session_state.thread_id[:16]}...")

# -------------------- MAIN CHAT UI --------------------
st.title("Arya Chatbot")

# Display current chat history
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# -------------------- USER INPUT --------------------
if prompt := st.chat_input("Type your message..."):
    # Add user message to current chat
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    try:
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                placeholder = st.empty()
                full_response = ""
                
                # Build complete message history for chatbot
                messages_to_send = []
                for msg in st.session_state.chat_history:
                    if msg["role"] == "user":
                        messages_to_send.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "assistant":
                        from langchain_core.messages import AIMessage
                        messages_to_send.append(AIMessage(content=msg["content"]))
                
                # Stream response from chatbot with full history
                for chunk, metadata in chatbot.stream(
                    {"messages": messages_to_send},
                    config={
                        "configurable": {
                            "thread_id": st.session_state.thread_id
                        }
                    },
                    stream_mode="messages"
                ):
                    if chunk.content:
                        full_response += chunk.content
                        placeholder.markdown(full_response + "▋")
                
                placeholder.markdown(full_response)
        
        # Add assistant response to current chat
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": full_response
        })
        
        # Update the database (all_chat_history is automatically updated 
        # because chat_history is a reference to it)
        
    except Exception as e:
        error_msg = f"Error during generation: {str(e)}"
        st.error(error_msg)
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": error_msg
        })
