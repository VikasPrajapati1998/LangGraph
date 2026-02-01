import uuid
import asyncio
import nest_asyncio
import streamlit as st
import atexit
import warnings
import os
import shutil
from backend import build_graph, DB_URI, llm
from database import ChatDatabase
from history import ChatHistoryManager, ConversationSummarizer, create_summary_callback
from langchain_core.messages import ToolMessage
from book_tool import setup as setup_vector_data


# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

# Suppress harmless warnings about pending tasks
warnings.filterwarnings('ignore', message='coroutine.*was never awaited')
warnings.filterwarnings('ignore', category=ResourceWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sys
if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ==================== CLEANUP HANDLERS ====================
# Simplified cleanup to avoid recursion issues

def cleanup_on_exit():
    """Simple cleanup that avoids recursion issues"""
    try:
        # Don't try to cancel tasks or close loops - let Python handle it
        # Just close database connections if possible
        if 'db' in globals() and hasattr(globals()['db'], 'pool'):
            try:
                # Try to close database pool synchronously
                pool = globals()['db'].pool
                if hasattr(pool, 'close') and callable(pool.close):
                    pool.close()
            except:
                pass
    except:
        pass

# Register cleanup handler
atexit.register(cleanup_on_exit)

# ==================== END CLEANUP HANDLERS ====================

# -------------------- ENSURE DIRECTORIES EXIST --------------------
# Create necessary directories
os.makedirs("data", exist_ok=True)
setup_vector_data()  # Create vector_data directory

# -------------------- DATABASE SETUP --------------------
db = ChatDatabase(DB_URI)

# -------------------- EVENT LOOP SETUP --------------------
# Create a fresh SelectorEventLoop every time so psycopg never sees a ProactorEventLoop
if "event_loop" not in st.session_state or st.session_state.event_loop.is_closed():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    st.session_state.event_loop = loop

# -------------------- CHATBOT INITIALIZATION --------------------
# Initialize chatbot asynchronously using the same event loop
if "chatbot" not in st.session_state:
    st.session_state.chatbot = st.session_state.event_loop.run_until_complete(build_graph())

# -------------------- SUMMARIZER SETUP --------------------
summarizer = ConversationSummarizer(model=llm, db=db)

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

# Initialize uploaded PDFs tracking with metadata
if "uploaded_pdfs" not in st.session_state:
    st.session_state.uploaded_pdfs = []

# Track processed PDF files to avoid re-processing
if "processed_pdf_names" not in st.session_state:
    st.session_state.processed_pdf_names = set()

# Initialize PDF upload status
if "pdf_upload_status" not in st.session_state:
    st.session_state.pdf_upload_status = None

# -------------------- HELPER FUNCTIONS --------------------
def save_uploaded_file(uploaded_file):
    """
    Save the uploaded PDF file to the data directory
    
    Args:
        uploaded_file: Streamlit UploadedFile object
        
    Returns:
        str: Path to the saved file
    """
    try:
        # Create a unique filename to avoid conflicts
        file_path = os.path.join("data", uploaded_file.name)
        
        # Save the file
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        return file_path
    except Exception as e:
        st.error(f"Error saving file: {str(e)}")
        return None


def process_uploaded_pdf(uploaded_file):
    """
    Process the uploaded PDF and IMMEDIATELY create vector store
    
    Args:
        uploaded_file: Streamlit UploadedFile object
        
    Returns:
        dict: Status and file path information
    """
    try:
        # Save the file first
        file_path = save_uploaded_file(uploaded_file)
        
        if not file_path:
            return {
                "success": False,
                "message": "❌ Failed to save file"
            }
        
        # Import the helper function from book_tool
        from book_tool import create_vector_store_for_pdf
        
        # IMMEDIATELY create vector store (don't wait for first query)
        print(f"\n🔄 Processing {uploaded_file.name}...")
        vector_result = create_vector_store_for_pdf(file_path)
        
        if vector_result["success"]:
            # Extract PDF name (without extension) for easy reference
            pdf_name = os.path.basename(file_path).replace('.pdf', '').replace('.PDF', '')
            
            # Store PDF info in session state
            pdf_info = {
                "name": uploaded_file.name,
                "pdf_name": pdf_name,
                "path": file_path,
                "vector_store": vector_result["vector_store_name"],
                "size": uploaded_file.size,
                "ready": True
            }
            
            # Add to uploaded PDFs list if not already there
            if not any(pdf["name"] == uploaded_file.name for pdf in st.session_state.uploaded_pdfs):
                st.session_state.uploaded_pdfs.append(pdf_info)
            
            return {
                "success": True,
                "file_path": file_path,
                "file_name": uploaded_file.name,
                "pdf_name": pdf_name,
                "vector_store": vector_result["vector_store_name"],
                "message": f"✅ {uploaded_file.name} is ready for querying!"
            }
        else:
            return {
                "success": False,
                "message": f"❌ Vector store creation failed: {vector_result.get('error', 'Unknown error')}"
            }
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error processing PDF: {error_details}")
        return {
            "success": False,
            "message": f"❌ Error processing file: {str(e)}"
        }


def get_available_pdfs():
    """Get list of all available PDF files from session state"""
    return st.session_state.uploaded_pdfs


def delete_pdf(file_path):
    """Delete a PDF file and its vector store"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            
            # Also remove the vector store for this PDF
            file_name = os.path.basename(file_path).replace('.pdf', '').replace('.PDF', '').replace(' ', '_')
            # Clean the name (replace special chars with underscore)
            clean_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in file_name)
            vector_db_dir = os.path.join("vector_data", clean_name)
            
            if os.path.exists(vector_db_dir):
                shutil.rmtree(vector_db_dir)
            
            return True
        return False
    except Exception as e:
        st.error(f"Error deleting file: {str(e)}")
        return False


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

# -------------------- PDF UPLOAD SECTION --------------------
st.sidebar.header("📄 Document Management")

# File uploader with automatic processing
uploaded_file = st.sidebar.file_uploader(
    "Upload PDF Document",
    type=['pdf'],
    help="Upload a PDF - it will be processed automatically!",
    key="pdf_uploader"
)

# AUTOMATIC PROCESSING when file is uploaded
if uploaded_file is not None:
    # Check if this PDF has already been processed
    if uploaded_file.name not in st.session_state.processed_pdf_names:
        with st.spinner(f"🔄 Processing {uploaded_file.name}..."):
            result = process_uploaded_pdf(uploaded_file)
            st.session_state.pdf_upload_status = result
            
            if result["success"]:
                # Mark as processed
                st.session_state.processed_pdf_names.add(uploaded_file.name)
                st.sidebar.success(result["message"])
                st.balloons()  # Celebrate!
                # Rerun to update UI
                st.rerun()
            else:
                st.sidebar.error(result["message"])
    else:
        st.sidebar.info(f"✅ {uploaded_file.name} already processed")

# Show upload status if available
if st.session_state.pdf_upload_status and st.session_state.pdf_upload_status["success"]:
    with st.sidebar.expander("📊 Last Upload Details", expanded=False):
        st.write(f"**File:** {st.session_state.pdf_upload_status['file_name']}")
        st.write(f"**PDF Name:** `{st.session_state.pdf_upload_status.get('pdf_name', 'N/A')}`")
        st.write(f"**Vector Store:** `{st.session_state.pdf_upload_status.get('vector_store', 'N/A')}`")
        if st.button("Clear Upload Status"):
            st.session_state.pdf_upload_status = None
            st.rerun()

# Show available PDFs with enhanced information
available_pdfs = get_available_pdfs()
if available_pdfs:
    st.sidebar.subheader(f"📚 Available Documents ({len(available_pdfs)})")
    
    for pdf in available_pdfs:
        with st.sidebar.expander(f"📄 {pdf['name']}", expanded=False):
            st.write(f"**Query name:** `{pdf['pdf_name']}`")
            st.write(f"**Size:** {pdf['size'] / (1024*1024):.2f} MB")
            st.write(f"**Vector Store:** `{pdf['vector_store']}`")
            st.write(f"**Status:** {'✅ Ready' if pdf['ready'] else '⏳ Processing'}")
            
            # Delete button for this PDF
            if st.button("🗑️ Delete", key=f"delete_pdf_{pdf['name']}", use_container_width=True):
                if delete_pdf(pdf['path']):
                    # Remove from session state
                    st.session_state.uploaded_pdfs = [
                        p for p in st.session_state.uploaded_pdfs if p['name'] != pdf['name']
                    ]
                    st.session_state.processed_pdf_names.discard(pdf['name'])
                    st.success(f"Deleted {pdf['name']}")
                    st.rerun()
else:
    st.sidebar.info("📭 No documents uploaded yet")

st.sidebar.divider()

# -------------------- MEMORY STRATEGY SECTION --------------------
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

# -------------------- CHAT MANAGEMENT SECTION --------------------
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

# Show helpful info about PDF querying
if available_pdfs:
    with st.expander("💡 How to ask questions about your documents", expanded=False):
        st.markdown("""
        **To query your uploaded PDF documents, simply mention the PDF name in your question!**
        
        ### 📝 Query Examples:
        """)
        
        # Show examples with actual uploaded PDF names
        for i, pdf in enumerate(available_pdfs[:3], 1):
            pdf_name = pdf['pdf_name']
            st.markdown(f"""
            **{i}. For "{pdf['name']}":**
            - "From **{pdf_name}**, explain [topic]"
            - "What does **{pdf_name}** say about [subject]?"
            - "Ask **{pdf_name}** to summarize [section]"
            """)
        
        st.markdown("""
        ---
        ### 📚 Your Available PDFs:
        """)
        
        for pdf in available_pdfs:
            st.markdown(f"- 📄 **{pdf['name']}** → Use name: `{pdf['pdf_name']}`")
        
        st.markdown("""
        ---
        ### 🎯 How It Works:
        1. **Mention the PDF name** in your question
        2. **AI automatically detects** which PDF to query
        3. **Gets relevant information** from that specific document
        4. **Returns answer** based on the document content
        
        ### ⚡ Pro Tips:
        - You don't need to include `.pdf` extension
        - Case doesn't matter: "mybook" = "MyBook" = "myBook"
        - The AI will extract the PDF name automatically
        - You can query multiple PDFs in one conversation
        """)

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
            # Create status container
            status_container = st.status("🤔 Processing...", expanded=True)
            
            with status_container:
                st.write("📝 Preparing context...")
                
                # ========== KEY CHANGE: Use managed history ==========
                # For summarization strategy, get existing summary
                existing_summary = None
                if history_manager.strategy == "summarization":
                    st.write("📊 Checking conversation summary...")
                    # Check if we need to update summary
                    summarizer.update_summary_if_needed(
                        st.session_state.thread_id,
                        st.session_state.chat_history
                    )
                    # Get the summary for context
                    existing_summary = summarizer.get_summary_for_context(st.session_state.thread_id)
                    if existing_summary:
                        st.write("✅ Using existing summary for context")
                
                # Get MANAGED history (not full history) to send to model
                messages_to_send = history_manager.get_managed_history(
                    st.session_state.chat_history,
                    include_system=True,
                    existing_summary=existing_summary
                )
                
                st.write(f"💭 Sending {len(messages_to_send)} messages to model...")
                
                # Define async streaming function
                async def stream_response():
                    full_response = ""
                    tool_calls_made = []
                    tool_outputs = []
                    
                    async for chunk, metadata in st.session_state.chatbot.astream(
                        {"messages": messages_to_send},
                        config={
                            "configurable": {"thread_id": st.session_state.thread_id},
                            "metadata": {"thread_id": st.session_state.thread_id},
                            "run_name": f"Chat_{st.session_state.thread_id}"
                        },
                        stream_mode="messages"
                    ):
                        # Check if this is a tool call
                        if hasattr(chunk, 'tool_calls') and chunk.tool_calls:
                            for tool_call in chunk.tool_calls:
                                tool_name = tool_call.get('name', 'unknown')
                                tool_args = tool_call.get('args', {})
                                
                                # Update status for tool call
                                st.write(f"🔧 **Tool Called:** `{tool_name}`")
                                
                                # Show PDF file being queried if it's book_tool
                                if tool_name == "book_tool":
                                    pdf_name = tool_args.get('pdf_name', 'N/A')
                                    query = tool_args.get('query', 'N/A')
                                    st.write(f"📄 **PDF Name:** {pdf_name}")
                                    st.write(f"🔍 **Query:** {query}")
                                else:
                                    st.json(tool_args)
                                
                                tool_calls_made.append({
                                    'name': tool_name,
                                    'args': tool_args
                                })
                        
                        # Check if this is a ToolMessage (tool result)
                        if isinstance(chunk, ToolMessage):
                            st.write(f"✅ **Tool Result Received**")
                            tool_output = str(chunk.content)
                            tool_outputs.append(tool_output)
                            
                            # For book_tool, show a preview of the retrieved context
                            with st.expander("View retrieved information"):
                                if len(tool_output) > 500:
                                    st.text(tool_output[:500] + "...")
                                else:
                                    st.text(tool_output)
                            continue  # Skip adding tool content to response
                        
                        # Only collect content from AIMessage chunks (not ToolMessage)
                        if hasattr(chunk, 'content') and chunk.content:
                            # Skip if it's a tool-type message
                            if hasattr(chunk, 'type') and chunk.type == 'tool':
                                continue
                            
                            # Only add actual AI response content
                            if not isinstance(chunk, ToolMessage):
                                full_response += chunk.content
                    
                    return full_response, tool_calls_made, tool_outputs
                
                # Run the async streaming using the same event loop
                full_response, tool_calls_made, tool_outputs = st.session_state.event_loop.run_until_complete(stream_response())
                
                # Update status to complete
                if tool_calls_made:
                    st.write(f"✨ **Used {len(tool_calls_made)} tool(s)** to generate response")
                st.write("✅ Response generated!")
            
            # Update status to complete
            status_container.update(label="✅ Complete!", state="complete", expanded=False)
            
            # Display final response outside status container
            st.markdown(full_response)
        
        # Add assistant response to current chat
        assistant_msg = {"role": "assistant", "content": full_response}
        st.session_state.chat_history.append(assistant_msg)
        
        # Save to database
        db.add_message(st.session_state.thread_id, "assistant", full_response)
        
    except Exception as e:
        import traceback
        error_msg = f"Error during generation: {str(e)}\n\n{traceback.format_exc()}"
        st.error(error_msg)
        error_response = {"role": "assistant", "content": f"Error: {str(e)}"}
        st.session_state.chat_history.append(error_response)
        # Save error to database
        db.add_message(st.session_state.thread_id, "assistant", f"Error: {str(e)}")
