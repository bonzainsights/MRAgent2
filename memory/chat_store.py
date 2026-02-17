"""
MRAgent — Chat Store
Lightweight SQLite storage for conversation history.

Created: 2026-02-15
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

from config.settings import CHAT_DB_PATH
from utils.logger import get_logger
from utils.helpers import generate_id, estimate_tokens

logger = get_logger("memory.chat_store")


class ChatStore:
    """
    SQLite-based chat history storage.
    Lightweight: one file, no server, <1MB for thousands of messages.
    """

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or CHAT_DB_PATH
        self._init_db()
        logger.info(f"Chat store initialized: {self.db_path}")

    @contextmanager
    def _conn(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent access
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        """Create tables if they don't exist."""
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS chats (
                    id TEXT PRIMARY KEY,
                    title TEXT DEFAULT 'New Chat',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    summary TEXT DEFAULT '',
                    token_count INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT REFERENCES chats(id),
                    role TEXT NOT NULL,
                    content TEXT DEFAULT '',
                    tool_calls TEXT DEFAULT '',
                    tool_call_id TEXT DEFAULT '',
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    token_estimate INTEGER DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_messages_chat_id
                ON messages(chat_id);
            """)

    # ──────────────────────────────────────────────
    # Chat operations
    # ──────────────────────────────────────────────

    def create_chat(self, chat_id: str = None, title: str = "New Chat") -> str:
        """Create a new chat and return its ID."""
        chat_id = chat_id or generate_id("chat_")
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO chats (id, title) VALUES (?, ?)",
                (chat_id, title)
            )
        logger.info(f"Created chat: {chat_id} — '{title}'")
        return chat_id

    def get_chat(self, chat_id: str) -> dict | None:
        """Get a chat by ID."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM chats WHERE id = ?", (chat_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_chats(self, limit: int = 20) -> list[dict]:
        """List recent chats."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM chats ORDER BY updated_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def update_chat_title(self, chat_id: str, title: str):
        """Update chat title."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE chats SET title = ?, updated_at = ? WHERE id = ?",
                (title, datetime.now().isoformat(), chat_id)
            )

    def update_chat_summary(self, chat_id: str, summary: str):
        """Update chat summary (for context retrieval)."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE chats SET summary = ?, updated_at = ? WHERE id = ?",
                (summary, datetime.now().isoformat(), chat_id)
            )

    def delete_chat(self, chat_id: str):
        """Delete a chat and all its messages."""
        with self._conn() as conn:
            conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
            conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
        logger.info(f"Deleted chat: {chat_id}")

    # ──────────────────────────────────────────────
    # Message operations
    # ──────────────────────────────────────────────

    def save_message(self, chat_id: str, role: str, content: str,
                     tool_calls: list = None, tool_call_id: str = ""):
        """Save a message to a chat."""
        # Auto-create chat if it doesn't exist
        if not self.get_chat(chat_id):
            self.create_chat(chat_id)

        tc_json = json.dumps(tool_calls) if tool_calls else ""
        tokens = estimate_tokens(content)

        with self._conn() as conn:
            conn.execute(
                "INSERT INTO messages (chat_id, role, content, tool_calls, tool_call_id, token_estimate) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (chat_id, role, content, tc_json, tool_call_id, tokens)
            )
            # Update chat timestamp and token count
            conn.execute(
                "UPDATE chats SET updated_at = ?, token_count = token_count + ? WHERE id = ?",
                (datetime.now().isoformat(), tokens, chat_id)
            )

    def get_messages(self, chat_id: str, limit: int = 100) -> list[dict]:
        """Get messages for a chat (most recent first if limit applied)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE chat_id = ? ORDER BY id ASC LIMIT ?",
                (chat_id, limit)
            ).fetchall()

        messages = []
        for row in rows:
            msg = {
                "role": row["role"],
                "content": row["content"],
            }
            if row["tool_calls"]:
                try:
                    msg["tool_calls"] = json.loads(row["tool_calls"])
                except json.JSONDecodeError:
                    pass
            if row["tool_call_id"]:
                msg["tool_call_id"] = row["tool_call_id"]
            messages.append(msg)
        return messages

    def get_message_count(self, chat_id: str) -> int:
        """Get total message count for a chat."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM messages WHERE chat_id = ?",
                (chat_id,)
            ).fetchone()
        return row["cnt"] if row else 0

    # ──────────────────────────────────────────────
    # Search & retrieval
    # ──────────────────────────────────────────────

    def search_chats(self, query: str, limit: int = 5) -> list[dict]:
        """Search across all chats by content (simple LIKE search)."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT c.* FROM chats c
                JOIN messages m ON c.id = m.chat_id
                WHERE m.content LIKE ? OR c.title LIKE ? OR c.summary LIKE ?
                ORDER BY c.updated_at DESC LIMIT ?
                """,
                (f"%{query}%", f"%{query}%", f"%{query}%", limit)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        """Return storage statistics."""
        with self._conn() as conn:
            chat_count = conn.execute("SELECT COUNT(*) FROM chats").fetchone()[0]
            msg_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
        return {
            "chats": chat_count,
            "messages": msg_count,
            "db_size_kb": db_size / 1024,
        }
