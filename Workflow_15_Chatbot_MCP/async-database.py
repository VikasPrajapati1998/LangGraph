from typing import List, Dict, Optional, Any
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

class AsyncChatDatabase:
    """Manages chat history in PostgreSQL using async connection pool"""
    
    def __init__(self, pool: AsyncConnectionPool):
        self.pool = pool

    @classmethod
    async def create(cls, db_uri: str, min_size: int = 2, max_size: int = 10) -> 'AsyncChatDatabase':
        """Factory method to create instance with new pool"""
        pool = AsyncConnectionPool(
            conninfo=db_uri,
            min_size=min_size,
            max_size=max_size,
            kwargs={"autocommit": True, "row_factory": dict_row},
            timeout=45,
            max_waiting=20,
        )
        # Wait until pool is ready
        await pool.open()
        instance = cls(pool)
        await instance.setup_database()
        return instance

    async def close(self):
        """Close the connection pool when application shuts down"""
        await self.pool.close()

    async def setup_database(self):
        """Create necessary tables if they don't exist"""
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                # chat_threads
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS chat_threads (
                        thread_id VARCHAR(255) PRIMARY KEY,
                        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                        title TEXT
                    )
                """)

                # chat_messages
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id BIGSERIAL PRIMARY KEY,
                        thread_id VARCHAR(255) REFERENCES chat_threads(thread_id) ON DELETE CASCADE,
                        role VARCHAR(50) NOT NULL,
                        content TEXT NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                        message_order INTEGER NOT NULL
                    )
                """)

                # Index for fast message retrieval
                await cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_thread_messages 
                    ON chat_messages(thread_id, message_order)
                """)

                # conversation_summaries
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_summaries (
                        id SERIAL PRIMARY KEY,
                        thread_id VARCHAR(255) REFERENCES chat_threads(thread_id) ON DELETE CASCADE,
                        summary TEXT NOT NULL,
                        messages_covered INTEGER NOT NULL,
                        last_message_order INTEGER NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(thread_id)
                    )
                """)

    # ────────────────────────────────────────────────
    #  Thread operations
    # ────────────────────────────────────────────────

    async def create_thread(self, thread_id: str, title: Optional[str] = None) -> bool:
        try:
            async with self.pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO chat_threads (thread_id, title, created_at, updated_at)
                        VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT (thread_id) DO NOTHING
                        """,
                        (thread_id, title)
                    )
            return True
        except Exception as e:
            print(f"Error creating thread {thread_id}: {e}")
            return False

    async def get_all_threads(self) -> List[Dict[str, Any]]:
        try:
            async with self.pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        SELECT thread_id, title, created_at, updated_at
                        FROM chat_threads
                        ORDER BY updated_at DESC
                    """)
                    return await cur.fetchall()
        except Exception as e:
            print(f"Error fetching threads: {e}")
            return []

    async def delete_thread(self, thread_id: str) -> bool:
        try:
            async with self.pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "DELETE FROM chat_threads WHERE thread_id = %s",
                        (thread_id,)
                    )
            return True
        except Exception as e:
            print(f"Error deleting thread {thread_id}: {e}")
            return False

    async def get_thread_title(self, thread_id: str) -> Optional[str]:
        try:
            async with self.pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT title FROM chat_threads WHERE thread_id = %s",
                        (thread_id,)
                    )
                    row = await cur.fetchone()
                    return row["title"] if row else None
        except Exception as e:
            print(f"Error fetching title for {thread_id}: {e}")
            return None

    # ────────────────────────────────────────────────
    #  Messages
    # ────────────────────────────────────────────────

    async def add_message(self, thread_id: str, role: str, content: str) -> bool:
        try:
            async with self.pool.connection() as conn:
                async with conn.cursor() as cur:
                    # Get next order
                    await cur.execute("""
                        SELECT COALESCE(MAX(message_order), -1) + 1 as next_order
                        FROM chat_messages
                        WHERE thread_id = %s
                    """, (thread_id,))
                    row = await cur.fetchone()
                    next_order = row["next_order"]

                    # Insert message
                    await cur.execute("""
                        INSERT INTO chat_messages 
                            (thread_id, role, content, message_order)
                        VALUES (%s, %s, %s, %s)
                    """, (thread_id, role, content, next_order))

                    # Update thread timestamp
                    await cur.execute("""
                        UPDATE chat_threads
                        SET updated_at = CURRENT_TIMESTAMP
                        WHERE thread_id = %s
                    """, (thread_id,))

                    # Auto-title from first user message
                    if role.lower() in ("user", "human") and next_order == 0:
                        title = (content[:48] + "...") if len(content) > 50 else content
                        await cur.execute("""
                            UPDATE chat_threads
                            SET title = %s
                            WHERE thread_id = %s AND title IS NULL
                        """, (title, thread_id))

            return True
        except Exception as e:
            print(f"Error adding message to {thread_id}: {e}")
            return False

    async def get_thread_messages(self, thread_id: str) -> List[Dict[str, Any]]:
        try:
            async with self.pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        SELECT role, content, created_at, message_order
                        FROM chat_messages
                        WHERE thread_id = %s
                        ORDER BY message_order ASC
                    """, (thread_id,))
                    return await cur.fetchall()
        except Exception as e:
            print(f"Error fetching messages for {thread_id}: {e}")
            return []

    # ────────────────────────────────────────────────
    #  Summary operations
    # ────────────────────────────────────────────────

    async def save_summary(self, thread_id: str, summary: str, messages_covered: int, last_message_order: int) -> bool:
        try:
            async with self.pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        INSERT INTO conversation_summaries 
                            (thread_id, summary, messages_covered, last_message_order, created_at)
                        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (thread_id) DO UPDATE SET
                            summary = EXCLUDED.summary,
                            messages_covered = EXCLUDED.messages_covered,
                            last_message_order = EXCLUDED.last_message_order,
                            created_at = EXCLUDED.created_at
                    """, (thread_id, summary, messages_covered, last_message_order))
            return True
        except Exception as e:
            print(f"Error saving summary for {thread_id}: {e}")
            return False

    async def get_summary(self, thread_id: str) -> Optional[Dict[str, Any]]:
        try:
            async with self.pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        SELECT summary, messages_covered, last_message_order, created_at
                        FROM conversation_summaries
                        WHERE thread_id = %s
                    """, (thread_id,))
                    return await cur.fetchone()
        except Exception as e:
            print(f"Error fetching summary for {thread_id}: {e}")
            return None

    async def delete_summary(self, thread_id: str) -> bool:
        try:
            async with self.pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "DELETE FROM conversation_summaries WHERE thread_id = %s",
                        (thread_id,)
                    )
            return True
        except Exception as e:
            print(f"Error deleting summary for {thread_id}: {e}")
            return False

