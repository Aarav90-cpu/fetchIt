import asyncio
import aiohttp
import os
import logging
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from typing import Set, List, Tuple
from tqdm.asyncio import tqdm

# Import C++ extension
try:
    import fetchit_core
except ImportError:
    logging.warning("fetchit_core not found. Falling back to Python sets.")
    fetchit_core = None

from .cache import Cache
from .extractor import Extractor
from .markdown_converter import html_to_markdown

class Crawler:
    """Asynchronous web crawler that fetches, extracts, and converts pages to Markdown."""

    def __init__(self, base_url: str, output_file: str, max_concurrency: int = 10, retries: int = 3, skip_images: bool = False, tree_output: bool = False):
        self.base_url = base_url
        self.output_file = output_file
        self.max_concurrency = max_concurrency
        self.retries = retries
        self.skip_images = skip_images
        self.tree_output = tree_output
        
        self.parsed_base = urlparse(base_url)
        self.cache = Cache()
        self.extractor = Extractor(base_url)
        
        # We'll collect all markdown pages in memory/file to concatenate later
        self.pages_data = [] 

    async def fetch(self, session: aiohttp.ClientSession, url: str) -> Tuple[str, str]:
        """Fetches a URL with retries and exponential backoff."""
        for attempt in range(self.retries):
            try:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        content = await response.text()
                        return url, content
                    elif response.status in (401, 403, 404):
                        logging.warning(f"Failed to fetch {url}, status: {response.status}")
                        return url, ""
                    else:
                        logging.warning(f"Failed to fetch {url}, status: {response.status}")
                        response.raise_for_status()
            except Exception as e:
                logging.debug(f"Attempt {attempt+1} failed for {url}: {e}")
                if attempt < self.retries - 1:
                    await asyncio.sleep(min(2 ** attempt, 10))  # Exponential backoff capped at 10s
        return url, ""

    async def download_image(self, session: aiohttp.ClientSession, img_url: str, local_path: str):
        """Downloads an image and saves it to the local filesystem."""
        if os.path.exists(local_path):
            return # Already downloaded
            
        for attempt in range(self.retries):
            try:
                async with session.get(img_url, timeout=10) as response:
                    if response.status == 200:
                        content = await response.read()
                        with open(local_path, 'wb') as f:
                            f.write(content)
                        return
                    elif response.status in (401, 403, 404):
                        return
                    else:
                        response.raise_for_status()
            except Exception:
                if attempt < self.retries - 1:
                    await asyncio.sleep(min(2 ** attempt, 10))

    async def process_page(self, session: aiohttp.ClientSession, url: str, html: str) -> List[str]:
        """Extracts content, converts to markdown, and finds new links."""
        soup = BeautifulSoup(html, "lxml")
        
        # 1. Extract links to crawl
        new_links = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            full_url = urljoin(url, href)
            # Remove fragment
            full_url = full_url.split('#')[0]
            
            # Check if it belongs to base_url
            if full_url.startswith(self.base_url):
                new_links.append(full_url)
                
        # 2. Extract main content
        main_content = self.extractor.extract_main_content(soup)
        if not main_content:
            return new_links

        # 3. Process images
        image_tasks = self.extractor.process_images(main_content, url, self.skip_images)
        for img_url, local_path in image_tasks:
            await self.download_image(session, img_url, local_path)

        # 4. Convert to markdown
        title = soup.title.string if soup.title else "Untitled Page"
        title = title.strip()
        markdown_content = html_to_markdown(main_content, title, url)
        
        self.pages_data.append((title, url, markdown_content))
        self.cache.save_page(url, html)
        
        return new_links

    async def worker(self, name: str, session: aiohttp.ClientSession, queue: asyncio.Queue, pbar):
        """Worker task that consumes URLs from the queue."""
        while True:
            url = await queue.get()
            try:
                cached_html = self.cache.get_page(url)
                if cached_html:
                    new_links = await self.process_page(session, url, cached_html)
                else:
                    _, html = await self.fetch(session, url)
                    if html:
                        new_links = await self.process_page(session, url, html)
                    else:
                        new_links = []
                        
                for link in new_links:
                    is_new = fetchit_core.add_and_check_url(link) if fetchit_core else self._add_url_python(link)
                    if is_new:
                        queue.put_nowait(link)
                        pbar.total += 1
                        pbar.refresh()
                
                pbar.update(1)
            except Exception as e:
                logging.error(f"Worker {name} failed on {url}: {e}")
            finally:
                queue.task_done()

    def _add_url_python(self, url: str) -> bool:
        """Fallback deduplication if C++ extension fails."""
        if not hasattr(self, '_visited_urls'):
            self._visited_urls = set()
        if url in self._visited_urls:
            return False
        self._visited_urls.add(url)
        return True

    async def _fetch_sitemap(self, session: aiohttp.ClientSession) -> List[str]:
        """Attempts to find and parse sitemaps from robots.txt or common locations."""
        urls = []
        robots_url = urljoin(self.base_url, "/robots.txt")
        _, content = await self.fetch(session, robots_url)
        
        sitemap_urls = []
        if content:
            for line in content.splitlines():
                if line.lower().startswith("sitemap:"):
                    sitemap_urls.append(line.split(":", 1)[1].strip())
                    
        if not sitemap_urls:
            sitemap_urls.append(urljoin(self.base_url, "/sitemap.xml"))
            
        for sitemap_url in sitemap_urls:
            _, xml_content = await self.fetch(session, sitemap_url)
            if xml_content:
                if fetchit_core:
                    urls.extend(fetchit_core.extract_urls_from_sitemap(xml_content))
                else:
                    # Basic Python fallback
                    urls.extend([line.split('<loc>')[1].split('</loc>')[0] for line in xml_content.splitlines() if '<loc>' in line])
                    
        return [u for u in urls if u.startswith(self.base_url)]

    async def crawl(self):
        """Main crawl orchestration method."""
        queue = asyncio.Queue()
        
        # Start session
        async with aiohttp.ClientSession() as session:
            # First try sitemap
            sitemap_urls = await self._fetch_sitemap(session)
            
            urls_to_start = sitemap_urls if sitemap_urls else [self.base_url]
            
            for url in urls_to_start:
                is_new = fetchit_core.add_and_check_url(url) if fetchit_core else self._add_url_python(url)
                if is_new:
                    queue.put_nowait(url)

            with tqdm(total=queue.qsize(), desc="Crawling Pages", unit="page") as pbar:
                # Create workers
                workers = []
                for i in range(self.max_concurrency):
                    worker = asyncio.create_task(self.worker(f"worker-{i}", session, queue, pbar))
                    workers.append(worker)

                # Wait until queue is fully processed
                await queue.join()

                # Cancel workers
                for w in workers:
                    w.cancel()

        if self.tree_output:
            self._generate_tree_output()
        else:
            self._generate_output()

    def _generate_output(self):
        """Generates the final concatenated markdown file with TOC."""
        logging.info("Generating final markdown file...")
        with open(self.output_file, 'w', encoding='utf-8') as f:
            f.write("# Table of Contents\n\n")
            
            # Sort by URL for consistent TOC
            self.pages_data.sort(key=lambda x: x[1])
            
            for idx, (title, url, _) in enumerate(self.pages_data, 1):
                import re
                anchor = re.sub(r'[^\w-]', '', title.lower().replace(' ', '-'))
                f.write(f"{idx}. [{title}](#{anchor})\n")
                
            f.write("\n---\n\n")
            
            for title, url, md_content in self.pages_data:
                f.write(md_content)
                f.write("\n")
                
        logging.info(f"Successfully wrote documentation to {self.output_file}")

    def _generate_tree_output(self):
        """Generates a directory tree of markdown files representing the site structure."""
        # Determine the root directory name
        output_dir = self.output_file
        if output_dir == "output.md":
            output_dir = self.parsed_base.netloc
        elif output_dir.endswith('.md'):
            output_dir = output_dir[:-3]
            
        logging.info(f"Generating markdown file tree in '{output_dir}/' ...")
        
        for title, url, md_content in self.pages_data:
            parsed = urlparse(url)
            path = parsed.path.strip('/')
            
            if not path:
                # Root of the domain
                filepath = os.path.join(output_dir, "index.md")
            else:
                if url.endswith('/'):
                    filepath = os.path.join(output_dir, path, "index.md")
                else:
                    filepath = os.path.join(output_dir, path + ".md")
                    
            # Ensure the directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(md_content)
                
        logging.info(f"Successfully wrote file tree to {output_dir}/")
