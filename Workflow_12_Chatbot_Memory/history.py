from typing import List, Dict, Optional, Callable
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_ollama import ChatOllama

class ChatHistoryManager:
    """
    Intelligent chat history management with multiple strategies
    """
    
    def __init__(
        self,
        strategy: str = "token_based",  # Options: "message_count", "token_based", "sliding_window", "hybrid", "summarization"
        max_messages: int = 20,
        max_tokens: int = 3000,
        system_prompt: str = None,
        summarize_threshold: int = 30,  # Summarize when messages exceed this
        recent_messages_count: int = 10,  # Keep this many recent messages with summary
        summarizer_callback: Optional[Callable] = None  # Function to generate summaries
    ):
        self.strategy = strategy
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt
        self.summarize_threshold = summarize_threshold
        self.recent_messages_count = recent_messages_count
        self.summarizer_callback = summarizer_callback
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate tokens (rough approximation)
        More accurate: use tiktoken library for OpenAI models
        """
        return len(text.split(" "))
    
    def get_managed_history(
        self,
        full_history: List[Dict[str, str]],
        include_system: bool = True,
        existing_summary: Optional[str] = None
    ) -> List[BaseMessage]:
        """
        Get managed chat history based on selected strategy
        
        Args:
            full_history: Complete chat history from database
            include_system: Whether to include system prompt
            existing_summary: Pre-generated summary for summarization strategy
        
        Returns:
            Managed list of messages to send to model
        """
        
        if self.strategy == "message_count":
            return self._message_count_strategy(full_history, include_system)
        
        elif self.strategy == "token_based":
            return self._token_based_strategy(full_history, include_system)
        
        elif self.strategy == "sliding_window":
            return self._sliding_window_strategy(full_history, include_system)
        
        elif self.strategy == "hybrid":
            return self._hybrid_strategy(full_history, include_system)
        
        elif self.strategy == "summarization":
            return self._summarization_strategy(full_history, include_system, existing_summary)
        
        else:
            # Default: return all
            return self._convert_to_messages(full_history, include_system)
    
    def _message_count_strategy(
        self,
        full_history: List[Dict[str, str]],
        include_system: bool
    ) -> List[BaseMessage]:
        """
        Strategy 1: Keep last N messages
        Simple and predictable
        """
        # Take last N messages
        recent_messages = full_history[-self.max_messages:] if len(full_history) > self.max_messages else full_history
        return self._convert_to_messages(recent_messages, include_system)
    
    def _token_based_strategy(
        self,
        full_history: List[Dict[str, str]],
        include_system: bool
    ) -> List[BaseMessage]:
        """
        Strategy 2: Keep messages within token limit
        More accurate for context management
        """
        selected_messages = []
        current_tokens = 0
        
        # Add system prompt tokens if needed
        if include_system and self.system_prompt:
            current_tokens += self.estimate_tokens(self.system_prompt)
        
        # Work backwards from most recent
        for msg in reversed(full_history):
            msg_tokens = self.estimate_tokens(msg['content'])
            
            if current_tokens + msg_tokens <= self.max_tokens:
                selected_messages.insert(0, msg)
                current_tokens += msg_tokens
            else:
                break
        
        return self._convert_to_messages(selected_messages, include_system)
    
    def _sliding_window_strategy(
        self,
        full_history: List[Dict[str, str]],
        include_system: bool
    ) -> List[BaseMessage]:
        """
        Strategy 3: Keep last N conversation exchanges (user + assistant pairs)
        Ensures complete exchanges
        """
        exchanges_to_keep = self.max_messages // 2  # Each exchange = 2 messages
        
        # Find complete exchanges from the end
        selected_messages = []
        exchange_count = 0
        
        for i in range(len(full_history) - 1, -1, -1):
            selected_messages.insert(0, full_history[i])
            
            # Count exchanges (when we see a user message)
            if full_history[i]['role'] == 'user':
                exchange_count += 1
                if exchange_count >= exchanges_to_keep:
                    break
        
        return self._convert_to_messages(selected_messages, include_system)
    
    def _hybrid_strategy(
        self,
        full_history: List[Dict[str, str]],
        include_system: bool
    ) -> List[BaseMessage]:
        """
        Strategy 4: RECOMMENDED - Hybrid approach
        
        Keeps:
        1. First user message (for context about what conversation is about)
        2. Last N messages within token limit
        3. Ensures complete exchanges
        """
        if not full_history:
            return self._convert_to_messages([], include_system)
        
        # 1. Always keep first user message for context
        first_user_msg = None
        for msg in full_history:
            if msg['role'] == 'user':
                first_user_msg = msg
                break
        
        # 2. Get recent messages within token limit
        selected_messages = []
        current_tokens = 0
        
        if include_system and self.system_prompt:
            current_tokens += self.estimate_tokens(self.system_prompt)
        
        if first_user_msg:
            current_tokens += self.estimate_tokens(first_user_msg['content'])
        
        # Work backwards from most recent
        recent_portion = []
        for msg in reversed(full_history[1:]):  # Skip first message
            msg_tokens = self.estimate_tokens(msg['content'])
            
            if current_tokens + msg_tokens <= self.max_tokens:
                recent_portion.insert(0, msg)
                current_tokens += msg_tokens
            else:
                break
        
        # 3. Combine: first message + ... + recent messages
        if first_user_msg and first_user_msg not in recent_portion:
            selected_messages = [first_user_msg]
            if recent_portion:
                # Add separator indicator
                selected_messages.append({
                    'role': 'assistant',
                    'content': '[Previous conversation context...]'
                })
                selected_messages.extend(recent_portion)
        else:
            selected_messages = recent_portion
        
        return self._convert_to_messages(selected_messages, include_system)
    
    def _summarization_strategy(
        self,
        full_history: List[Dict[str, str]],
        include_system: bool,
        existing_summary: Optional[str] = None
    ) -> List[BaseMessage]:
        """
        Strategy 5: Summarization
        
        For long conversations:
        1. Summarize old messages (if > threshold)
        2. Keep last N recent messages in full
        3. Combine: [Summary] + [Recent Messages]
        
        Args:
            full_history: Complete chat history
            include_system: Whether to include system prompt
            existing_summary: Previously generated summary (optional)
        """
        total_messages = len(full_history)
        
        # If conversation is short, just use recent messages
        if total_messages <= self.summarize_threshold:
            return self._message_count_strategy(full_history, include_system)
        
        # Split into: messages to summarize + recent messages
        split_point = total_messages - self.recent_messages_count
        messages_to_summarize = full_history[:split_point]
        recent_messages = full_history[split_point:]
        
        # Generate or use existing summary
        summary_text = existing_summary
        if not summary_text and self.summarizer_callback:
            summary_text = self.summarizer_callback(messages_to_summarize)
        elif not summary_text:
            # Fallback: create a simple summary without AI
            summary_text = self._create_simple_summary(messages_to_summarize)
        
        # Build final message list
        messages = []
        
        # Add system prompt
        if include_system and self.system_prompt:
            messages.append(SystemMessage(content=self.system_prompt))
        
        # Add summary as a system message
        if summary_text:
            messages.append(SystemMessage(
                content=f"Previous conversation summary:\n{summary_text}\n\n---\nRecent conversation continues below:"
            ))
        
        # Add recent messages
        for msg in recent_messages:
            if msg['role'] == 'user':
                messages.append(HumanMessage(content=msg['content']))
            elif msg['role'] == 'assistant':
                messages.append(AIMessage(content=msg['content']))
        
        return messages
    
    def _create_simple_summary(self, messages: List[Dict[str, str]]) -> str:
        """
        Create a simple summary without AI (fallback)
        Just lists key information about the conversation
        """
        user_messages = [m for m in messages if m['role'] == 'user']
        assistant_messages = [m for m in messages if m['role'] == 'assistant']
        
        # Get first and some key user questions
        topics = []
        if user_messages:
            topics.append(f"Initial topic: {user_messages[0]['content'][:100]}")
        
        summary = f"""This conversation started with {len(messages)} messages.
The user asked {len(user_messages)} questions and received {len(assistant_messages)} responses.
{topics[0] if topics else 'The conversation covered various topics.'}"""
        
        return summary
    
    def _convert_to_messages(
        self,
        history: List[Dict[str, str]],
        include_system: bool
    ) -> List[BaseMessage]:
        """Convert dict history to LangChain message objects"""
        messages = []
        
        # Add system prompt if provided
        if include_system and self.system_prompt:
            messages.append(SystemMessage(content=self.system_prompt))
        
        # Convert history
        for msg in history:
            if msg['role'] == 'user':
                messages.append(HumanMessage(content=msg['content']))
            elif msg['role'] == 'assistant':
                messages.append(AIMessage(content=msg['content']))
        
        return messages
    
    def get_history_stats(self, full_history: List[Dict[str, str]]) -> Dict:
        """Get statistics about the chat history"""
        total_messages = len(full_history)
        total_tokens = sum(self.estimate_tokens(msg['content']) for msg in full_history)
        
        managed_history = self.get_managed_history(full_history, include_system=False)
        managed_tokens = sum(self.estimate_tokens(msg.content) for msg in managed_history)
        
        return {
            'total_messages': total_messages,
            'total_tokens': total_tokens,
            'managed_messages': len(managed_history),
            'managed_tokens': managed_tokens,
            'reduction_percentage': round((1 - managed_tokens / max(total_tokens, 1)) * 100, 2),
            'needs_summary': total_messages > self.summarize_threshold if self.strategy == "summarization" else False
        }


# ==================== CONVERSATION SUMMARIZER ====================

class ConversationSummarizer:
    """
    Handles AI-powered conversation summarization
    """
    
    def __init__(self, model: ChatOllama, db):
        """
        Initialize the summarizer
        
        Args:
            model: The ChatOllama model instance
            db: Database instance for storing summaries
        """
        self.model = model
        self.db = db
    
    def generate_summary(self, messages: List[Dict[str, str]]) -> str:
        """
        Generate an AI summary of conversation messages
        
        Args:
            messages: List of message dicts with 'role' and 'content'
        
        Returns:
            Summary text
        """
        # Build conversation text
        conversation_text = ""
        for msg in messages:
            role = "User" if msg['role'] == 'user' else "Assistant"
            conversation_text += f"{role}: {msg['content'][:500]}\n\n"  # Limit each message
        
        # Create summarization prompt
        prompt = f"""Please provide a concise summary of the following conversation between a user and an AI assistant.

Focus on:
1. Main topics and questions discussed
2. Key information or solutions provided
3. Important context for continuing the conversation

Keep the summary brief (under 150 words) but informative.

Conversation:
{conversation_text}

Provide a clear, factual summary:"""
        
        try:
            # Generate summary
            response = self.model.invoke([
                SystemMessage(content="You are a helpful assistant that creates concise conversation summaries."),
                HumanMessage(content=prompt)
            ])
            
            summary = response.content.strip()
            return summary
        
        except Exception as e:
            print(f"Error generating summary: {e}")
            # Fallback to simple summary
            return self._create_fallback_summary(messages)
    
    def _create_fallback_summary(self, messages: List[Dict[str, str]]) -> str:
        """Create a simple fallback summary without AI"""
        user_messages = [m for m in messages if m['role'] == 'user']
        
        if not user_messages:
            return "Previous conversation covered various topics."
        
        first_topic = user_messages[0]['content'][:100]
        return f"Conversation started with: {first_topic}... ({len(messages)} messages exchanged)"
    
    def should_update_summary(self, thread_id: str, current_message_count: int) -> bool:
        """
        Check if summary needs to be updated
        
        Args:
            thread_id: Thread ID
            current_message_count: Current number of messages in thread
        
        Returns:
            True if summary should be updated
        """
        existing_summary = self.db.get_summary(thread_id)
        
        # No summary exists and we have enough messages
        if not existing_summary and current_message_count >= 30:
            return True
        
        # Summary exists but is outdated (more than 20 new messages)
        if existing_summary:
            messages_since_summary = current_message_count - existing_summary['messages_covered']
            if messages_since_summary >= 20:
                return True
        
        return False
    
    def update_summary_if_needed(
        self,
        thread_id: str,
        all_messages: List[Dict[str, str]],
        force: bool = False
    ) -> Optional[str]:
        """
        Update summary if needed
        
        Args:
            thread_id: Thread ID
            all_messages: All messages in the conversation
            force: Force update even if not needed
        
        Returns:
            Summary text if updated, None otherwise
        """
        current_count = len(all_messages)
        
        # Check if update is needed
        if not force and not self.should_update_summary(thread_id, current_count):
            # Return existing summary if available
            existing = self.db.get_summary(thread_id)
            return existing['summary'] if existing else None
        
        # Determine how many messages to summarize
        # Keep last 10 messages out of summary
        recent_messages_count = 10
        
        if current_count <= recent_messages_count:
            return None  # Too few messages to summarize
        
        # Messages to include in summary
        messages_to_summarize = all_messages[:-recent_messages_count]
        
        # Generate new summary
        summary = self.generate_summary(messages_to_summarize)
        
        # Save to database
        last_message_order = len(messages_to_summarize) - 1
        self.db.save_summary(
            thread_id=thread_id,
            summary=summary,
            messages_covered=len(messages_to_summarize),
            last_message_order=last_message_order
        )
        
        return summary
    
    def get_summary_for_context(self, thread_id: str) -> Optional[str]:
        """
        Get existing summary for a thread
        
        Args:
            thread_id: Thread ID
        
        Returns:
            Summary text or None
        """
        summary_data = self.db.get_summary(thread_id)
        return summary_data['summary'] if summary_data else None


# ==================== UTILITY FUNCTIONS ====================

def create_summary_callback(summarizer: ConversationSummarizer):
    """
    Create a callback function for ChatHistoryManager
    
    Args:
        summarizer: ConversationSummarizer instance
    
    Returns:
        Callback function that generates summaries
    """
    def callback(messages: List[Dict[str, str]]) -> str:
        return summarizer.generate_summary(messages)
    
    return callback
