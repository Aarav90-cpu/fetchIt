import sqlite3
import os
from typing import Optional, Dict, Any

class Cache:
    """Manages SQLite cache for storing downloaded pages and fetch status."""
    
    def __init__(self, db_path: str = "fetchit_cache.db"):
        """Initialize the SQLite cache."""
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist."""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                url TEXT PRIMARY KEY,
                content TEXT,
                status INTEGER
            )
        """)
        self.conn.commit()

    def get_page(self, url: str) -> Optional[str]:
        """Retrieve page content from cache if it was successfully downloaded."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT content FROM pages WHERE url = ? AND status = 200", (url,))
        result = cursor.fetchone()
        return result[0] if result else None

    def save_page(self, url: str, content: str, status: int = 200):
        """Save a downloaded page to the cache."""
        cursor = self.conn.cursor()
        cursor.execute("REPLACE INTO pages (url, content, status) VALUES (?, ?, ?)", (url, content, status))
        self.conn.commit()

    def is_visited(self, url: str) -> bool:
        """Check if a URL has already been processed."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM pages WHERE url = ?", (url,))
        return cursor.fetchone() is not None

    def close(self):
        """Close the database connection."""
        self.conn.close()
