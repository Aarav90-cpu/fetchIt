import asyncio
import aiohttp
import os
import logging
import re
import json
from urllib.parse import urlparse, urljoin, urlunparse, parse_qs, urlencode
from bs4 import BeautifulSoup
from typing import Set, List, Tuple, Optional, Dict
from tqdm.asyncio import tqdm

from .cache import Cache
from .extractor import Extractor, FONT_EXTENSIONS, IMAGE_EXTENSIONS
from .markdown_converter import html_to_markdown
from .url_manager import URLManager
from .sitemap_parser import extract_urls_from_sitemap

# Realistic modern browser user agent to prevent 403 blocks from Cloudflare/WAFs
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 FetchIt/0.0.6"
)

# Common sitemap and feed discovery paths
COMMON_DISCOVERY_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/wp-sitemap.xml",
    "/sitemap/sitemap-index.xml",
    "/feed/",
    "/rss.xml",
    "/atom.xml",
    "/feed.xml",
]

# WordPress REST API endpoints for automatic page/post enumeration
WP_REST_ENDPOINTS = [
    "/wp-json/wp/v2/pages?per_page=100&_fields=link",
    "/wp-json/wp/v2/posts?per_page=100&_fields=link",
]

# Default depth limit when crawling without a sitemap
DEFAULT_LINK_FOLLOW_DEPTH = 100


def normalize_url(url: str) -> str:
    """Normalizes a URL by removing fragments, preserving directory trailing slashes, and sorting query params."""
    parsed = urlparse(url)
    raw_path = parsed.path or '/'

    # Check if the last path segment looks like a file with an extension (.html, .php, etc.)
    last_segment = raw_path.split('/')[-1]
    has_file_extension = '.' in last_segment and not last_segment.startswith('.')

    # Keep trailing slash on directory paths so urljoin resolves relative assets inside the directory
    if not has_file_extension and not raw_path.endswith('/'):
        path = raw_path + '/'
    else:
        path = raw_path

    query_params = parse_qs(parsed.query, keep_blank_values=True)
    sorted_query = urlencode(sorted(query_params.items()), doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, path, '', sorted_query, ''))


class RobotsRules:
    """Simple robots.txt parser for Disallow/Allow rules."""

    def __init__(self):
        self.disallow: List[str] = []
        self.allow: List[str] = []
        self.sitemaps: List[str] = []

    @classmethod
    def parse(cls, content: str) -> 'RobotsRules':
        """Parses robots.txt content and extracts rules for all user agents."""
        rules = cls()
        applies = False

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            if line.lower().startswith('sitemap:'):
                rules.sitemaps.append(line.split(':', 1)[1].strip())
                continue

            if line.lower().startswith('user-agent:'):
                agent = line.split(':', 1)[1].strip().lower()
                applies = agent == '*' or 'fetchit' in agent
                continue

            if not applies:
                continue

            if line.lower().startswith('disallow:'):
                path = line.split(':', 1)[1].strip()
                if path:
                    rules.disallow.append(path)
            elif line.lower().startswith('allow:'):
                path = line.split(':', 1)[1].strip()
                if path:
                    rules.allow.append(path)

        return rules

    def is_allowed(self, url: str) -> bool:
        """Checks if a URL path is allowed by the parsed rules."""
        parsed = urlparse(url)
        path = parsed.path or '/'

        for pattern in self.allow:
            if path.startswith(pattern):
                return True
        for pattern in self.disallow:
            if path.startswith(pattern):
                return False
        return True


class Crawler:
    """Asynchronous web crawler that fetches, extracts, and converts pages to Markdown or raw HTML."""

    def __init__(self, base_url: str, output_file: str, max_concurrency: int = 10,
                 retries: int = 3, skip_images: bool = False, tree_output: bool = False,
                 html_mode: bool = False, max_depth: Optional[int] = None,
                 render_js: bool = False):
        self.base_url = base_url
        self.output_file = output_file
        self.max_concurrency = max_concurrency
        self.retries = retries
        self.skip_images = skip_images
        self.tree_output = tree_output
        self.html_mode = html_mode
        self.max_depth = max_depth
        self.render_js = render_js

        self.parsed_base = urlparse(base_url)
        self.base_domain = self.parsed_base.netloc
        self.base_scheme = self.parsed_base.scheme or "https"

        # Determine target output directory
        if self.html_mode or self.tree_output:
            if self.output_file == "output.md":
                self.output_dir = self.base_domain
            elif self.output_file.endswith(('.md', '.html')):
                self.output_dir = self.output_file[:self.output_file.rfind('.')]
            else:
                self.output_dir = self.output_file
        else:
            self.output_dir = "."

        self.cache = Cache()
        self.extractor = Extractor(base_url, output_dir=self.output_dir)
        self.url_manager = URLManager()
        self.robots_rules = RobotsRules()

        # Collect (title, url, content)
        self.pages_data: List[Tuple[str, str, str]] = []

    def _is_same_domain(self, url: str) -> bool:
        """Checks if a URL belongs to the target domain or its subdomains."""
        parsed = urlparse(url)
        return parsed.netloc == self.base_domain

    def _is_valid_page_url(self, url: str) -> bool:
        """Filters out non-page binary assets (images, fonts, archives, videos)."""
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https', ''):
            return False
        skip_extensions = (
            '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.bmp', '.avif',
            '.pdf', '.zip', '.tar', '.gz', '.7z', '.rar', '.exe', '.bin',
            '.mp4', '.mp3', '.wav', '.webm', '.ogg', '.m4a',
            '.woff', '.woff2', '.ttf', '.eot', '.otf',
            '.css', '.js', '.mjs',
        )
        path_lower = parsed.path.lower()
        if any(path_lower.endswith(ext) for ext in skip_extensions):
            return False
        return True

    def _get_url_ancestors(self, url: str) -> List[str]:
        """
        Discovers parent directory paths for directory structure understanding.
        Keeps scope to the target path hierarchy without escaping to root when in a subdirectory.
        """
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        if not path:
            return [f"{parsed.scheme}://{parsed.netloc}/"]

        segments = [s for s in path.split('/') if s]
        ancestors = []
        cur = ""
        for seg in segments:
            if '.' in seg and not seg.startswith('.'):
                cur += f"/{seg}"
                ancestors.append(f"{parsed.scheme}://{parsed.netloc}{cur}")
            else:
                cur += f"/{seg}"
                ancestors.append(f"{parsed.scheme}://{parsed.netloc}{cur}/")

        return list(dict.fromkeys(ancestors))

    async def _probe_url(self, session: aiohttp.ClientSession, url: str) -> Tuple[str, str]:
        """Fast single-attempt probe for speculative discovery endpoints."""
        timeout = aiohttp.ClientTimeout(total=4, connect=2, sock_read=3)
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            async with session.get(url, timeout=timeout, headers=headers) as response:
                if response.status == 200:
                    content = await response.text(errors='replace')
                    return url, content
        except Exception:
            pass
        return url, ""

    async def fetch_rendered(self, url: str) -> Tuple[str, str]:
        """Renders the page using Playwright headless browser to execute dynamic client-side JS."""
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=10000)
                    await page.wait_for_timeout(1500)
                except Exception as nav_err:
                    logging.debug(f"Headless navigation note for {url}: {nav_err}")
                content = await page.content()
                await browser.close()
                return url, content
        except Exception as e:
            logging.warning(f"Headless rendering unavailable ({e}), falling back to standard fetch")
            async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as temp_session:
                return await self.fetch(temp_session, url)

    async def fetch(self, session: aiohttp.ClientSession, url: str, warn_on_error: bool = True) -> Tuple[str, str]:
        """Fetches a URL with retries, exponential backoff, and modern request headers."""
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        timeout = aiohttp.ClientTimeout(total=15, connect=5, sock_read=10)
        for attempt in range(self.retries):
            try:
                async with session.get(url, timeout=timeout, headers=headers) as response:
                    if response.status == 200:
                        content = await response.text(errors='replace')
                        return url, content
                    elif response.status in (401, 403, 404):
                        if warn_on_error:
                            logging.warning(f"Failed to fetch {url}, status: {response.status}")
                        else:
                            logging.debug(f"Speculative probe skipped: {url}, status: {response.status}")
                        return url, ""
                    else:
                        if warn_on_error:
                            logging.warning(f"Failed to fetch {url}, status: {response.status}")
                        response.raise_for_status()
            except Exception as e:
                logging.debug(f"Attempt {attempt+1} failed for {url}: {e}")
                if attempt < self.retries - 1:
                    await asyncio.sleep(min(2 ** attempt, 4))
        return url, ""

    async def download_asset(self, session: aiohttp.ClientSession, asset_url: str, local_path: str):
        """Downloads an asset and inspects CSS files for nested font/image url() references."""
        if os.path.exists(local_path):
            return

        timeout = aiohttp.ClientTimeout(total=15, connect=5, sock_read=10)
        for attempt in range(self.retries):
            try:
                async with session.get(asset_url, timeout=timeout) as response:
                    if response.status == 200:
                        content = await response.read()
                        os.makedirs(os.path.dirname(local_path), exist_ok=True)

                        # If this is a stylesheet, inspect for fonts and background images
                        if local_path.endswith('.css'):
                            try:
                                css_text = content.decode('utf-8', errors='ignore')
                                nested_assets: List[Tuple[str, str]] = []
                                rewritten_css = self.extractor._process_css_urls(
                                    css_text, asset_url, nested_assets
                                )
                                # Rewrite local asset path to be relative to the assets folder
                                rewritten_css = rewritten_css.replace("url('assets/", "url('")
                                content = rewritten_css.encode('utf-8')

                                # Download nested fonts / images discovered in the CSS
                                for nested_url, nested_disk in nested_assets:
                                    asyncio.create_task(self.download_asset(session, nested_url, nested_disk))
                            except Exception as css_err:
                                logging.debug(f"CSS parsing note for {asset_url}: {css_err}")

                        with open(local_path, 'wb') as f:
                            f.write(content)
                        return
                    elif response.status in (401, 403, 404):
                        return
                    else:
                        response.raise_for_status()
            except Exception:
                if attempt < self.retries - 1:
                    await asyncio.sleep(min(2 ** attempt, 4))
                async with session.get(asset_url, timeout=timeout) as response:
                    if response.status == 200:
                        content = await response.read()
                        os.makedirs(os.path.dirname(local_path), exist_ok=True)

                        # If this is a stylesheet, inspect for fonts and background images
                        if local_path.endswith('.css'):
                            try:
                                css_text = content.decode('utf-8', errors='ignore')
                                nested_assets: List[Tuple[str, str]] = []
                                rewritten_css = self.extractor._process_css_urls(
                                    css_text, asset_url, nested_assets
                                )
                                # Rewrite local asset path to be relative to the assets folder
                                rewritten_css = rewritten_css.replace("url('assets/", "url('")
                                content = rewritten_css.encode('utf-8')

                                # Download nested fonts / images discovered in the CSS
                                for nested_url, nested_disk in nested_assets:
                                    asyncio.create_task(self.download_asset(session, nested_url, nested_disk))
                            except Exception as css_err:
                                logging.debug(f"CSS parsing note for {asset_url}: {css_err}")

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
        """Extracts deep links, downloads assets with full styling fidelity, and saves page data."""
        soup = BeautifulSoup(html, "lxml")

        # 1. Deep link discovery: anchors, data-attributes, iframes, directory indexes, script routes
        raw_links = self.extractor.extract_deep_links(soup, url)
        new_links = []
        for raw in raw_links:
            norm = normalize_url(raw)
            if self._is_same_domain(norm) and self._is_valid_page_url(norm):
                if self.robots_rules.is_allowed(norm):
                    new_links.append(norm)

        # 2. Extract content (in HTML mode, preserve the entire document including <head> and styling)
        if not self.html_mode:
            main_content = self.extractor.extract_main_content(soup)
            if not main_content:
                main_content = soup
        else:
            main_content = soup

        # 3. Process images, stylesheets, fonts, and scripts concurrently
        asset_tasks = self.extractor.process_assets(
            main_content, url, self.skip_images, fetch_css_js=self.html_mode
        )
        sem = asyncio.Semaphore(10)

        async def _bounded_download(asset_u: str, local_p: str):
            async with sem:
                await self.download_asset(session, asset_u, local_p)

        if asset_tasks:
            await asyncio.gather(*[_bounded_download(u, p) for u, p in asset_tasks], return_exceptions=True)

        # 4. Pure Python SPA Data Scanner
        # Extract JavaScript from inline scripts and fetch external same-domain scripts concurrently
        script_snippets = []
        external_script_urls = []
        for script in soup.find_all("script"):
            if script.string:
                script_snippets.append(script.string)
            src = script.get("src")
            if src and not src.startswith("data:"):
                script_url = urljoin(url, src)
                if self._is_same_domain(script_url):
                    external_script_urls.append(script_url)

        if external_script_urls:
            script_results = await asyncio.gather(
                *[self.fetch(session, s_url, warn_on_error=False) for s_url in external_script_urls],
                return_exceptions=True
            )
            for res in script_results:
                if isinstance(res, tuple) and res[1]:
                    script_snippets.append(res[1])

        all_js = "\n".join(script_snippets)
        discovered_data_endpoints = self.extractor.extract_data_endpoints(all_js, url)

        data_fetch_targets = [ep for ep in discovered_data_endpoints if self._is_same_domain(ep)]
        extracted_json_objects = []

        if data_fetch_targets:
            data_results = await asyncio.gather(
                *[self.fetch(session, d_url, warn_on_error=False) for d_url in data_fetch_targets],
                return_exceptions=True
            )
            media_download_tasks = []
            for d_url, res in zip(data_fetch_targets, data_results):
                if isinstance(res, tuple) and res[1]:
                    json_text = res[1]
                    if json_text.strip().startswith(('{', '[')):
                        try:
                            parsed_json = json.loads(json_text)
                            extracted_json_objects.append(parsed_json)

                            # Save the JSON file so client-side apps can load data offline in --html mode
                            parsed_data_url = urlparse(d_url)
                            data_filename = os.path.basename(parsed_data_url.path) or "data.json"
                            rel_data_path = parsed_data_url.path.strip('/')

                            dest_paths = [
                                os.path.join(self.output_dir, rel_data_path),
                                os.path.join(self.output_dir, data_filename),
                                os.path.join(self.extractor.assets_dir, data_filename)
                            ]
                            for dp in dest_paths:
                                os.makedirs(os.path.dirname(dp), exist_ok=True)
                                with open(dp, 'w', encoding='utf-8') as jf:
                                    jf.write(json_text)

                            # Extract and download media URLs from the JSON
                            json_media = self.extractor.extract_media_from_json(parsed_json, d_url)
                            for media_url, media_local in json_media:
                                media_download_tasks.append((media_url, media_local))
                        except Exception as json_err:
                            logging.debug(f"JSON parsing note for {d_url}: {json_err}")

            if media_download_tasks:
                await asyncio.gather(
                    *[_bounded_download(m_url, m_path) for m_url, m_path in media_download_tasks],
                    return_exceptions=True
                )

        # 5. Convert to markdown or keep HTML
        title = soup.title.string if soup.title and soup.title.string else "Untitled Page"
        title = title.strip() if title else ""

        if self.html_mode:
            content_to_save = str(main_content)
        else:
            extracted_text = main_content.get_text(strip=True) if main_content else ""
            # If the page is an empty SPA shell (like "Nothing here yet") and JSON data was discovered:
            if (len(extracted_text) < 150 or "nothing here yet" in extracted_text.lower()) and extracted_json_objects:
                logging.info(f"Dynamic SPA detected on {url}. Generating Markdown from structured JSON data.")
                content_to_save = ""
                for j_data in extracted_json_objects:
                    content_to_save += self.extractor.json_to_markdown(j_data, title, url)
            else:
                content_to_save = html_to_markdown(main_content, title, url)

        self.pages_data.append((title, url, content_to_save))
        self.cache.save_page(url, html)

        return new_links

    async def worker(self, name: str, session: aiohttp.ClientSession, queue: asyncio.Queue, pbar):
        """Worker task consuming (url, depth) tuples."""
        while True:
            url, depth = await queue.get()
            try:
                if self.max_depth is not None and depth > self.max_depth:
                    continue

                cached_html = self.cache.get_page(url)
                if cached_html:
                    new_links = await self.process_page(session, url, cached_html)
                else:
                    if self.render_js:
                        _, html = await self.fetch_rendered(url)
                    else:
                        _, html = await self.fetch(session, url)

                    if html:
                        new_links = await self.process_page(session, url, html)
                    else:
                        new_links = []

                for link in new_links:
                    if self.url_manager.add_and_check(link):
                        queue.put_nowait((link, depth + 1))
                        pbar.total += 1
                        pbar.refresh()
            except Exception as e:
                logging.error(f"Worker {name} failed on {url}: {e}")
            finally:
                pbar.update(1)
                queue.task_done()

    async def _fetch_robots(self, session: aiohttp.ClientSession):
        """Fetches and parses robots.txt."""
        robots_url = f"{self.base_scheme}://{self.base_domain}/robots.txt"
        _, content = await self.fetch(session, robots_url, warn_on_error=False)
        if content:
            self.robots_rules = RobotsRules.parse(content)
            logging.debug(f"Parsed robots.txt: {len(self.robots_rules.disallow)} disallow rules, "
                          f"{len(self.robots_rules.sitemaps)} sitemaps")

    async def _discover_initial_urls(self, session: aiohttp.ClientSession) -> List[str]:
        """
        Discovers URLs across sitemaps, feeds, and WordPress REST endpoints.
        Probes both the domain root and the target subdirectory concurrently.
        """
        urls: List[str] = []

        # 1. Candidate discovery paths at root and subdirectory
        candidates = list(self.robots_rules.sitemaps)
        subpath = self.parsed_base.path.rstrip('/')

        for path in COMMON_DISCOVERY_PATHS:
            root_cand = f"{self.base_scheme}://{self.base_domain}{path}"
            if root_cand not in candidates:
                candidates.append(root_cand)

            if subpath:
                sub_cand = f"{self.base_scheme}://{self.base_domain}{subpath}{path}"
                if sub_cand not in candidates:
                    candidates.append(sub_cand)

        # Also probe common SPA data files in the subdirectory
        if subpath:
            for data_file in ("/annotations.json", "/data.json", "/projects.json"):
                data_cand = f"{self.base_scheme}://{self.base_domain}{subpath}{data_file}"
                if data_cand not in candidates:
                    candidates.append(data_cand)

        # Probe all candidate endpoints concurrently
        probe_results = await asyncio.gather(
            *[self._probe_url(session, c) for c in candidates],
            return_exceptions=True
        )

        nested_sitemaps = []
        for res in probe_results:
            if isinstance(res, tuple) and res[1]:
                cand_url, content = res

                # XML sitemap
                if "<loc>" in content:
                    extracted = extract_urls_from_sitemap(content)
                    nested = [u for u in extracted if u.endswith('.xml')]
                    pages = [u for u in extracted if not u.endswith('.xml')]
                    urls.extend(pages)
                    nested_sitemaps.extend(nested[:10])

                # RSS / Atom feed
                elif "<link>" in content:
                    try:
                        feed_soup = BeautifulSoup(content, "xml")
                        for item in feed_soup.find_all(["item", "entry"]):
                            link_elem = item.find("link")
                            if link_elem:
                                link_val = link_elem.get("href") or link_elem.string or ""
                                if link_val.strip():
                                    urls.append(link_val.strip())
                    except Exception:
                        pass

        # Probe nested sitemaps concurrently if found
        if nested_sitemaps:
            nested_results = await asyncio.gather(
                *[self._probe_url(session, n) for n in nested_sitemaps],
                return_exceptions=True
            )
            for n_res in nested_results:
                if isinstance(n_res, tuple) and n_res[1]:
                    urls.extend(extract_urls_from_sitemap(n_res[1]))

        # 2. WordPress REST API probing concurrently
        wp_candidates = [f"{self.base_scheme}://{self.base_domain}{ep}" for ep in WP_REST_ENDPOINTS]
        wp_results = await asyncio.gather(
            *[self._probe_url(session, wp) for wp in wp_candidates],
            return_exceptions=True
        )
        for wp_res in wp_results:
            if isinstance(wp_res, tuple) and wp_res[1]:
                wp_json = wp_res[1]
                if wp_json.strip().startswith('['):
                    try:
                        items = json.loads(wp_json)
                        for item in items:
                            if isinstance(item, dict) and "link" in item:
                                urls.append(item["link"])
                    except Exception:
                        pass

        # Filter to target domain
        return [normalize_url(u) for u in urls if self._is_same_domain(u)]

    async def crawl(self):
        """Main crawl orchestration method."""
        queue = asyncio.Queue()

        headers = {"User-Agent": USER_AGENT}
        async with aiohttp.ClientSession(headers=headers) as session:
            # 1. Fetch robots.txt
            await self._fetch_robots(session)

            # 2. Discover URLs via sitemaps, feeds, and REST endpoints
            discovered_urls = await self._discover_initial_urls(session)

            # 3. Add path hierarchy ancestry for comprehensive discovery
            ancestor_urls = self._get_url_ancestors(self.base_url)

            # HTML-First: Prioritize starting URL first, then discovered URLs, then ancestors
            start_norm = normalize_url(self.base_url)
            ordered_start = [start_norm]

            if discovered_urls:
                logging.info(f"Discovered {len(discovered_urls)} URLs via site metadata.")
                for u in discovered_urls:
                    norm_u = normalize_url(u)
                    if norm_u not in ordered_start:
                        ordered_start.append(norm_u)
            else:
                logging.info("No sitemap found. Exploring starting URL and following links.")
                if self.max_depth is None:
                    self.max_depth = DEFAULT_LINK_FOLLOW_DEPTH
                    logging.info(f"Using default depth limit of {self.max_depth}. Use --depth to change.")

            for a in ancestor_urls:
                norm_a = normalize_url(a)
                if norm_a not in ordered_start:
                    ordered_start.append(norm_a)

            for url in ordered_start:
                if self.url_manager.add_and_check(url):
                    queue.put_nowait((url, 0))

            with tqdm(total=queue.qsize(), desc="Crawling Pages", unit="page") as pbar:
                workers = []
                for i in range(self.max_concurrency):
                    worker = asyncio.create_task(self.worker(f"worker-{i}", session, queue, pbar))
                    workers.append(worker)

                await queue.join()

                for w in workers:
                    w.cancel()

        if self.html_mode:
            self._generate_html_tree_output()
        elif self.tree_output:
            self._generate_tree_output()
        else:
            self._generate_output()

    def _generate_output(self):
        """Generates single concatenated markdown file with TOC."""
        logging.info("Generating final markdown file...")
        with open(self.output_file, 'w', encoding='utf-8') as f:
            f.write("# Table of Contents\n\n")

            self.pages_data.sort(key=lambda x: x[1])

            for idx, (title, url, _) in enumerate(self.pages_data, 1):
                anchor = re.sub(r'[^\w-]', '', title.lower().replace(' ', '-'))
                f.write(f"{idx}. [{title}](#{anchor})\n")

            f.write("\n---\n\n")

            for title, url, md_content in self.pages_data:
                f.write(md_content)
                f.write("\n")

        logging.info(f"Successfully wrote documentation to {self.output_file}")

    def _generate_tree_output(self):
        """Generates directory tree of markdown files with correct relative image paths."""
        output_dir = self.output_dir
        logging.info(f"Generating markdown file tree in '{output_dir}/' ...")

        for title, url, md_content in self.pages_data:
            parsed = urlparse(url)
            path = parsed.path.strip('/')

            if not path:
                filepath = os.path.join(output_dir, "index.md")
                rel_prefix = ""
            else:
                if url.endswith('/'):
                    filepath = os.path.join(output_dir, path, "index.md")
                    my_dir = path
                else:
                    filepath = os.path.join(output_dir, path + ".md")
                    my_dir = os.path.dirname(path)

                rel_prefix = os.path.relpath(".", my_dir) if my_dir else ""
                if rel_prefix and not rel_prefix.endswith('/'):
                    rel_prefix += '/'

            # Rewrite images relative to the markdown file's depth
            if rel_prefix:
                md_content = md_content.replace("](images/", f"]({rel_prefix}images/")

            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(md_content)

        logging.info(f"Successfully wrote file tree to {output_dir}/")

    def _generate_html_tree_output(self):
        """Generates directory tree of HTML files with fully localized assets and links."""
        output_dir = self.output_dir
        logging.info(f"Generating HTML file tree in '{output_dir}/' ...")

        # Map URLs to relative local file paths
        url_to_filepath: Dict[str, str] = {}
        for title, url, _ in self.pages_data:
            parsed = urlparse(url)
            path = parsed.path.strip('/')

            if not path:
                filepath = "index.html"
            else:
                if url.endswith('/'):
                    filepath = os.path.join(path, "index.html")
                else:
                    filepath = path + ".html"
            url_to_filepath[url] = filepath

        for title, url, html_content in self.pages_data:
            my_filepath = url_to_filepath[url]
            full_filepath = os.path.join(output_dir, my_filepath)
            my_dir = os.path.dirname(my_filepath)

            # Compute relative path prefix to the root output folder
            rel_prefix = os.path.relpath(".", my_dir) if my_dir else ""
            if rel_prefix and not rel_prefix.endswith('/'):
                rel_prefix += '/'

            soup = BeautifulSoup(html_content, "lxml")

            # 1. Rewrite internal links between pages
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                full_url = urljoin(url, href)
                full_url_no_frag = full_url.split('#')[0]
                frag = '#' + full_url.split('#')[1] if '#' in full_url else ''

                norm_no_frag = normalize_url(full_url_no_frag)
                if norm_no_frag in url_to_filepath:
                    target_filepath = url_to_filepath[norm_no_frag]
                    rel_path = os.path.relpath(target_filepath, my_dir) if my_dir else target_filepath
                    a_tag["href"] = rel_path + frag

            # 2. Adjust asset references (images, stylesheets, scripts, fonts) relative to this file's depth
            if rel_prefix:
                for img in soup.find_all("img", src=True):
                    if img["src"].startswith("images/"):
                        img["src"] = rel_prefix + img["src"]
                for link in soup.find_all("link", href=True):
                    if link["href"].startswith("assets/"):
                        link["href"] = rel_prefix + link["href"]
                for script in soup.find_all("script", src=True):
                    if script["src"].startswith("assets/"):
                        script["src"] = rel_prefix + script["src"]
                for source in soup.find_all("source", srcset=True):
                    parts = []
                    for entry in source["srcset"].split(","):
                        p = entry.strip().split()
                        if p and p[0].startswith("images/"):
                            p[0] = rel_prefix + p[0]
                        parts.append(" ".join(p))
                    source["srcset"] = ", ".join(parts)

            os.makedirs(os.path.dirname(full_filepath), exist_ok=True)
            with open(full_filepath, 'w', encoding='utf-8') as f:
                f.write(str(soup))

        logging.info(f"Successfully wrote HTML file tree to {output_dir}/")
