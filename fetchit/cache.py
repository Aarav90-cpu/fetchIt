import sqlite3
import os
from typing import Optional, Dict, Any

class Cache:
    """
    Manages a local SQLite cache for storing downloaded pages and fetch status.
    This prevents re-downloading the same page across interrupted sessions.
    """
    
    def __init__(self, db_path: str = "fetchit_cache.db"):
        """
        Initialize the SQLite cache.
        
        Args:
            db_path (str): Path to the SQLite database file.
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self._init_db()

    def _init_db(self):
        """
        Create tables if they don't exist.
        The 'pages' table stores the URL, raw HTML content, and HTTP status.
        """
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
        """
        Retrieve page content from cache if it was successfully downloaded.
        
        Args:
            url (str): The URL of the page.
            
        Returns:
            Optional[str]: The raw HTML content if cached and successful, else None.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT content FROM pages WHERE url = ? AND status = 200", (url,))
        result = cursor.fetchone()
        return result[0] if result else None

    def save_page(self, url: str, content: str, status: int = 200):
        """
        Save a downloaded page to the cache.
        
        Args:
            url (str): The URL of the page.
            content (str): The raw HTML content.
            status (int): The HTTP status code (defaults to 200).
        """
        cursor = self.conn.cursor()
        cursor.execute("REPLACE INTO pages (url, content, status) VALUES (?, ?, ?)", (url, content, status))
        self.conn.commit()

    def is_visited(self, url: str) -> bool:
        """
        Check if a URL has already been processed and cached.
        
        Args:
            url (str): The URL to check.
            
        Returns:
            bool: True if the URL is in the cache, False otherwise.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM pages WHERE url = ?", (url,))
        return cursor.fetchone() is not None

    def close(self):
        """Close the database connection safely."""
        self.conn.close()
