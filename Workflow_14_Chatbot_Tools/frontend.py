import streamlit as st
from backend import chatbot, DB_URI, model
from database import ChatDatabase
from history import ChatHistoryManager, ConversationSummarizer, create_summary_callback
from langchain_core.messages import HumanMessage, AIMessage
import uuid

# -------------------- DATABASE SETUP --------------------
db = ChatDatabase(DB_URI)

# -------------------- SUMMARIZER SETUP --------------------
summarizer = ConversationSummarizer(model=model, db=db)

# -------------------- HISTORY MANAGER SETUP --------------------
# Choose your strategy here!
history_manager = ChatHistoryManager(
    strategy="hybrid",  # Options: "message_count", "token_based", "sliding_window", "hybrid", "summarization"
    max_messages=20,    # For message_count and sliding_window
    max_tokens=3000,    # For token_based and hybrid
    system_prompt="You are Arya, a helpful and friendly AI assistant.",
    summarize_threshold=30,  # For summarization strategy
    recent_messages_count=10,  # For summarization strategy
    summarizer_callback=create_summary_callback(summarizer)  # AI summarizer
)

# -------------------- PAGE CONFIG --------------------
st.set_page_config(
    page_title="Arya Chatbot",
    layout="centered"
)

# -------------------- SESSION STATE INITIALIZATION --------------------
# Initialize thread_id
if "thread_id" not in st.session_state:
    # Try to get the most recent thread from database
    all_threads = db.get_all_threads()
    if all_threads:
        st.session_state.thread_id = all_threads[0]['thread_id']
    else:
        # Create a new thread if none exist
        new_thread_id = str(uuid.uuid4())
        db.create_thread(new_thread_id)
        st.session_state.thread_id = new_thread_id

# Initialize chat_history from database
if "chat_history" not in st.session_state:
    messages = db.get_thread_messages(st.session_state.thread_id)
    st.session_state.chat_history = [
        {"role": msg['role'], "content": msg['content']} 
        for msg in messages
    ]

# -------------------- HELPER FUNCTIONS --------------------
def create_new_chat():
    """Create a new chat and switch to it"""
    new_thread_id = str(uuid.uuid4())
    db.create_thread(new_thread_id)
    st.session_state.thread_id = new_thread_id
    st.session_state.chat_history = []

def switch_to_chat(thread_id):
    """Switch to an existing chat"""
    st.session_state.thread_id = thread_id
    messages = db.get_thread_messages(thread_id)
    st.session_state.chat_history = [
        {"role": msg['role'], "content": msg['content']} 
        for msg in messages
    ]

def delete_chat(thread_id):
    """Delete a chat thread"""
    db.delete_thread(thread_id)
    # If we deleted the active chat, create a new one
    if thread_id == st.session_state.thread_id:
        create_new_chat()

# -------------------- SIDEBAR --------------------
st.sidebar.title("⚙️ Chat Controls")

# Strategy selector
st.sidebar.subheader("Memory Strategy")
strategy_options = {
    "Hybrid (Recommended)": "hybrid",
    "Summarization (Long Chats)": "summarization",
    "Token-Based": "token_based",
    "Message Count": "message_count",
    "Sliding Window": "sliding_window"
}
selected_strategy = st.sidebar.selectbox(
    "Select strategy:",
    options=list(strategy_options.keys()),
    index=0
)
history_manager.strategy = strategy_options[selected_strategy]

# Strategy parameters
if history_manager.strategy in ["message_count", "sliding_window"]:
    history_manager.max_messages = st.sidebar.slider(
        "Max messages:", 
        min_value=5, 
        max_value=50, 
        value=20, 
        step=2
    )
elif history_manager.strategy in ["token_based", "hybrid"]:
    history_manager.max_tokens = st.sidebar.slider(
        "Max tokens:", 
        min_value=1000, 
        max_value=8000, 
        value=3000, 
        step=500
    )
elif history_manager.strategy == "summarization":
    history_manager.summarize_threshold = st.sidebar.slider(
        "Summarize after (messages):", 
        min_value=20, 
        max_value=100, 
        value=30, 
        step=5
    )
    history_manager.recent_messages_count = st.sidebar.slider(
        "Keep recent (messages):", 
        min_value=5, 
        max_value=20, 
        value=10, 
        step=1
    )

# Show stats
if st.session_state.chat_history:
    stats = history_manager.get_history_stats(st.session_state.chat_history)
    st.sidebar.metric("Total Messages", stats['total_messages'])
    st.sidebar.metric("Sent to Model", stats['managed_messages'])
    st.sidebar.metric("Token Reduction", f"{stats['reduction_percentage']}%")
    
    # Show summary status for summarization strategy
    if history_manager.strategy == "summarization":
        existing_summary = db.get_summary(st.session_state.thread_id)
        if existing_summary:
            st.sidebar.success(f"✅ Summary: {existing_summary['messages_covered']} msgs")
            with st.sidebar.expander("View Summary"):
                st.write(existing_summary['summary'])
        elif stats.get('needs_summary'):
            st.sidebar.warning("⚠️ Summary needed")
            if st.sidebar.button("Generate Summary Now"):
                with st.spinner("Generating summary..."):
                    summarizer.update_summary_if_needed(
                        st.session_state.thread_id,
                        st.session_state.chat_history,
                        force=True
                    )
                st.rerun()

st.sidebar.divider()

# New chat button
if st.sidebar.button("🆕 New Chat", use_container_width=True):
    create_new_chat()
    st.rerun()

st.sidebar.divider()
st.sidebar.header("💬 My Conversations")

# Get all threads from database
all_threads = db.get_all_threads()

if not all_threads:
    st.sidebar.info("No conversations yet. Start a new chat!")
else:
    # Display all chats
    for thread in all_threads:
        thread_id = thread['thread_id']
        title = thread['title']
        
        # Create preview text
        if title:
            preview = title[:30] + "..." if len(title) > 30 else title
        else:
            preview = f"Chat {thread_id[:8]}"
        
        # Highlight active chat
        is_active = (thread_id == st.session_state.thread_id)
        
        # Create a container for each chat with switch and delete buttons
        col1, col2 = st.sidebar.columns([4, 1])
        
        with col1:
            button_label = f"{'🔵 ' if is_active else '💬 '}{preview}"
            if st.button(button_label, key=f"chat_{thread_id}", disabled=is_active, use_container_width=True):
                switch_to_chat(thread_id)
                st.rerun()
        
        with col2:
            if st.button("🗑️", key=f"delete_{thread_id}", disabled=is_active, help="Delete chat"):
                delete_chat(thread_id)
                st.rerun()

st.sidebar.divider()
st.sidebar.caption(f"Active Thread:\n{st.session_state.thread_id[:16]}...")

# -------------------- MAIN CHAT UI --------------------
st.title("🤖 Arya Chatbot")

# Display current chat history (FULL HISTORY for UI)
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# -------------------- USER INPUT --------------------
if prompt := st.chat_input("Type your message..."):
    # Add user message to current chat
    user_msg = {"role": "user", "content": prompt}
    st.session_state.chat_history.append(user_msg)
    
    # Save to database
    db.add_message(st.session_state.thread_id, "user", prompt)
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    try:
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                placeholder = st.empty()
                full_response = ""
                
                # ========== KEY CHANGE: Use managed history ==========
                # For summarization strategy, get existing summary
                existing_summary = None
                if history_manager.strategy == "summarization":
                    # Check if we need to update summary
                    summarizer.update_summary_if_needed(
                        st.session_state.thread_id,
                        st.session_state.chat_history
                    )
                    # Get the summary for context
                    existing_summary = summarizer.get_summary_for_context(st.session_state.thread_id)
                
                # Get MANAGED history (not full history) to send to model
                messages_to_send = history_manager.get_managed_history(
                    st.session_state.chat_history,
                    include_system=True,
                    existing_summary=existing_summary
                )
                
                # Stream response from chatbot with MANAGED history
                for chunk, metadata in chatbot.stream(
                    {"messages": messages_to_send},
                    config={
                        "configurable": {"thread_id": st.session_state.thread_id},
                        "metadata": {"thread_id": st.session_state.thread_id},
                        "run_name": f"Chat_{st.session_state.thread_id}"
                    },
                    stream_mode="messages"
                ):
                    if chunk.content:
                        full_response += chunk.content
                        placeholder.markdown(full_response + "▋")
                
                placeholder.markdown(full_response)
        
        # Add assistant response to current chat
        assistant_msg = {"role": "assistant", "content": full_response}
        st.session_state.chat_history.append(assistant_msg)
        
        # Save to database
        db.add_message(st.session_state.thread_id, "assistant", full_response)
        
    except Exception as e:
        error_msg = f"Error during generation: {str(e)}"
        st.error(error_msg)
        error_response = {"role": "assistant", "content": error_msg}
        st.session_state.chat_history.append(error_response)
        # Save error to database
        db.add_message(st.session_state.thread_id, "assistant", error_msg)
