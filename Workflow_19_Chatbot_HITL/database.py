import psycopg
from psycopg.rows import dict_row
from typing import List, Dict, Optional
from datetime import datetime

class ChatDatabase:
    """Manages chat history in PostgreSQL database"""
    
    def __init__(self, db_uri: str):
        self.db_uri = db_uri
        self.setup_database()
    
    def get_connection(self):
        """Create a new database connection"""
        return psycopg.connect(self.db_uri, autocommit=True, row_factory=dict_row)
    
    def setup_database(self):
        """Create necessary tables if they don't exist"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Create chat_threads table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS chat_threads (
                        thread_id VARCHAR(255) PRIMARY KEY,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        title TEXT
                    )
                """)
                
                # Create chat_messages table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id SERIAL PRIMARY KEY,
                        thread_id VARCHAR(255) REFERENCES chat_threads(thread_id) ON DELETE CASCADE,
                        role VARCHAR(50) NOT NULL,
                        content TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        message_order INTEGER NOT NULL
                    )
                """)
                
                # Create index for faster queries
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_thread_messages 
                    ON chat_messages(thread_id, message_order)
                """)
                
                # Create conversation_summaries table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_summaries (
                        id SERIAL PRIMARY KEY,
                        thread_id VARCHAR(255) REFERENCES chat_threads(thread_id) ON DELETE CASCADE,
                        summary TEXT NOT NULL,
                        messages_covered INTEGER NOT NULL,
                        last_message_order INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(thread_id)
                    )
                """)
    
    def create_thread(self, thread_id: str, title: Optional[str] = None) -> bool:
        """Create a new chat thread"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO chat_threads (thread_id, title, created_at, updated_at)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (thread_id) DO NOTHING
                        """,
                        (thread_id, title, datetime.now(), datetime.now())
                    )
            return True
        except Exception as e:
            return False
    
    def get_all_threads(self) -> List[Dict]:
        """Get all chat threads ordered by most recent first"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT thread_id, title, created_at, updated_at
                        FROM chat_threads
                        ORDER BY updated_at DESC
                    """)
                    return cur.fetchall()
        except Exception as e:
            return []
    
    def get_thread_messages(self, thread_id: str) -> List[Dict]:
        """Get all messages for a specific thread"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT role, content, created_at, message_order
                        FROM chat_messages
                        WHERE thread_id = %s
                        ORDER BY message_order ASC
                    """, (thread_id,))
                    return cur.fetchall()
        except Exception as e:
            return []
    
    def add_message(self, thread_id: str, role: str, content: str) -> bool:
        """Add a message to a thread"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Get the next message order
                    cur.execute("""
                        SELECT COALESCE(MAX(message_order), -1) + 1 as next_order
                        FROM chat_messages
                        WHERE thread_id = %s
                    """, (thread_id,))
                    next_order = cur.fetchone()['next_order']
                    
                    # Insert the message
                    cur.execute("""
                        INSERT INTO chat_messages (thread_id, role, content, message_order)
                        VALUES (%s, %s, %s, %s)
                    """, (thread_id, role, content, next_order))
                    
                    # Update thread's updated_at timestamp
                    cur.execute("""
                        UPDATE chat_threads
                        SET updated_at = %s
                        WHERE thread_id = %s
                    """, (datetime.now(), thread_id))
                    
                    # Update title if this is the first user message
                    if role == "user" and next_order == 0:
                        title = content[:50] + "..." if len(content) > 50 else content
                        cur.execute("""
                            UPDATE chat_threads
                            SET title = %s
                            WHERE thread_id = %s AND title IS NULL
                        """, (title, thread_id))
            return True
        except Exception as e:
            return False
    
    def delete_thread(self, thread_id: str) -> bool:
        """Delete a thread and all its messages"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM chat_threads WHERE thread_id = %s", (thread_id,))
            return True
        except Exception as e:
            return False
    
    def get_thread_title(self, thread_id: str) -> Optional[str]:
        """Get the title of a thread"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT title FROM chat_threads WHERE thread_id = %s", (thread_id,))
                    result = cur.fetchone()
                    return result['title'] if result else None
        except Exception as e:
            return None
    
    # ==================== SUMMARY METHODS ====================
    
    def save_summary(self, thread_id: str, summary: str, messages_covered: int, last_message_order: int) -> bool:
        """Save or update conversation summary"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO conversation_summaries 
                            (thread_id, summary, messages_covered, last_message_order, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (thread_id) 
                        DO UPDATE SET 
                            summary = EXCLUDED.summary,
                            messages_covered = EXCLUDED.messages_covered,
                            last_message_order = EXCLUDED.last_message_order,
                            created_at = EXCLUDED.created_at
                    """, (thread_id, summary, messages_covered, last_message_order, datetime.now()))
            return True
        except Exception as e:
            return False
    
    def get_summary(self, thread_id: str) -> Optional[Dict]:
        """Get conversation summary for a thread"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT summary, messages_covered, last_message_order, created_at
                        FROM conversation_summaries
                        WHERE thread_id = %s
                    """, (thread_id,))
                    result = cur.fetchone()
                    return result if result else None
        except Exception as e:
            return None
    
    def delete_summary(self, thread_id: str) -> bool:
        """Delete conversation summary"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM conversation_summaries WHERE thread_id = %s", (thread_id,))
            return True
        except Exception as e:
            return False
