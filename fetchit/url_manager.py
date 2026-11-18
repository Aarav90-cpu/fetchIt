"""Thread-safe URL deduplication, replacing the C++ url_manager."""
import threading


class URLManager:
    """Tracks visited URLs using a set protected by a lock."""

    def __init__(self):
        self._visited = set()
        self._lock = threading.Lock()

    def add_and_check(self, url: str) -> bool:
        """Atomically checks if a URL is new. Returns True if it was added, False if already seen."""
        with self._lock:
            if url in self._visited:
                return False
            self._visited.add(url)
            return True

    def __len__(self):
        with self._lock:
            return len(self._visited)

    def __contains__(self, url: str):
        with self._lock:
            return url in self._visited
