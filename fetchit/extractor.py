import os
import re
from typing import Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

class Extractor:
    """Extracts main content and images from HTML pages."""

    def __init__(self, base_url: str, output_dir: str = "."):
        """Initialize with base URL to resolve relative links."""
        self.base_url = base_url
        self.images_dir = os.path.join(output_dir, "images")
        self.assets_dir = os.path.join(output_dir, "assets")
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(self.assets_dir, exist_ok=True)

    def extract_main_content(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """Heuristically extracts the main article content, removing boilerplate."""

        # Try to find the most likely container for the main content
        main_content = (
            soup.find("article") or
            soup.find("main") or
            soup.find(id=re.compile(r"content|main", re.I)) or
            soup.find(class_=re.compile(r"content|main|article", re.I)) or
            soup.find("body") or
            soup
        )

        if not main_content:
            return None

        # Remove boilerplate elements
        tags_to_remove = [
            "nav", "header", "footer", "aside", "script", "style", "noscript",
            "button", "iframe", "form"
        ]
        classes_to_remove = re.compile(r"breadcrumb|sidebar|ad|cookie|feedback|widget|menu|toc", re.I)

        for tag in main_content.find_all(tags_to_remove):
            tag.decompose()

        for tag in main_content.find_all(class_=classes_to_remove):
            tag.decompose()
            
        for tag in main_content.find_all(id=classes_to_remove):
            tag.decompose()

        return main_content

    def process_assets(self, soup: BeautifulSoup, page_url: str, skip_images: bool = False, fetch_css_js: bool = False) -> list[tuple[str, str]]:
        """Rewrites image/css/js src/href to local paths and returns a list of absolute URLs to download."""
        assets_to_download = []
        for img in soup.find_all("img"):
            src = img.get("src")
            if not src:
                continue

            # Resolve absolute URL
            abs_url = urljoin(page_url, src)
            
            if skip_images:
                img["src"] = abs_url
                continue
            
            # Create a safe local filename based on the URL path
            parsed_url = urlparse(abs_url)
            filename = os.path.basename(parsed_url.path)
            if not filename:
                filename = "image.png"
                
            # Fallback for name collisions
            safe_filename = f"{hash(abs_url) % 100000}_{filename}"
            
            # Rewrite src to local path (relative to the markdown file)
            local_path = os.path.join("images", safe_filename)
            img["src"] = local_path
            
            # Save for downloading
            assets_to_download.append((abs_url, os.path.join(self.images_dir, safe_filename)))

        if fetch_css_js:
            # CSS
            for link in soup.find_all("link", rel="stylesheet"):
                href = link.get("href")
                if not href:
                    continue
                abs_url = urljoin(page_url, href)
                parsed_url = urlparse(abs_url)
                filename = os.path.basename(parsed_url.path) or "style.css"
                safe_filename = f"{hash(abs_url) % 100000}_{filename}"
                local_path = os.path.join("assets", safe_filename)
                link["href"] = local_path
                assets_to_download.append((abs_url, os.path.join(self.assets_dir, safe_filename)))
                
            # JS
            for script in soup.find_all("script"):
                src = script.get("src")
                if not src:
                    continue
                abs_url = urljoin(page_url, src)
                parsed_url = urlparse(abs_url)
                filename = os.path.basename(parsed_url.path) or "script.js"
                safe_filename = f"{hash(abs_url) % 100000}_{filename}"
                local_path = os.path.join("assets", safe_filename)
                script["src"] = local_path
                assets_to_download.append((abs_url, os.path.join(self.assets_dir, safe_filename)))

        return assets_to_download
