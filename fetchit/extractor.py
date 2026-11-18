import os
import re
from typing import Optional, List, Tuple
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# File extensions for assets that should be downloaded and localized
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.bmp', '.avif')
FONT_EXTENSIONS = ('.woff', '.woff2', '.ttf', '.eot', '.otf')
CSS_EXTENSIONS = ('.css',)
JS_EXTENSIONS = ('.js', '.mjs')


class Extractor:
    """Extracts main content, images, stylesheets, scripts, and fonts from HTML pages."""

    def __init__(self, base_url: str, output_dir: str = "."):
        """Initialize with base URL and output directory for assets."""
        self.base_url = base_url
        self.output_dir = output_dir
        self.images_dir = os.path.join(output_dir, "images")
        self.assets_dir = os.path.join(output_dir, "assets")
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(self.assets_dir, exist_ok=True)

    def extract_main_content(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """Heuristically extracts the main article content, removing boilerplate without mutating source soup."""
        target = (
            soup.find("article") or
            soup.find("main") or
            soup.find(id=re.compile(r"content|main", re.I)) or
            soup.find(class_=re.compile(r"content|main|article", re.I)) or
            soup.find("body") or
            soup
        )

        if not target:
            return None

        # Create an isolated clone so decomposing tags does not mutate the source soup
        main_content = BeautifulSoup(str(target), "lxml")

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

    def _safe_filename(self, url: str, default_name: str) -> str:
        """Generates a collision-resistant safe filename from a URL."""
        parsed = urlparse(url)
        raw_name = os.path.basename(parsed.path) or default_name
        # Remove query parameters and illegal filesystem characters
        cleaned = re.sub(r'[^\w.\-]', '_', raw_name)
        if not cleaned or cleaned.startswith('.'):
            cleaned = default_name
        # Prepend a stable hash to prevent naming collisions
        url_hash = abs(hash(url)) % 1000000
        return f"{url_hash}_{cleaned}"

    def _get_effective_base(self, soup: BeautifulSoup, page_url: str) -> str:
        """Determines the effective base URL respecting <base href> tags."""
        base_tag = soup.find("base", href=True)
        if base_tag and base_tag.get("href"):
            return urljoin(page_url, base_tag["href"].strip())
        return page_url

    def process_assets(self, soup: BeautifulSoup, page_url: str,
                       skip_images: bool = False,
                       fetch_css_js: bool = False) -> List[Tuple[str, str]]:
        """
        Rewrites image, CSS, JS, font, and icon references to local paths.
        Returns a list of (absolute_url, local_disk_filepath) to download.
        """
        assets_to_download: List[Tuple[str, str]] = []
        base = self._get_effective_base(soup, page_url)

        # 1. Process <img> tags (including lazy loading and responsive srcset)
        for img in soup.find_all("img"):
            # Detect lazy loading attributes used by modern websites
            src = (
                img.get("data-src") or
                img.get("data-original") or
                img.get("data-lazy-src") or
                img.get("data-fallback-src") or
                img.get("src")
            )
            if not src or src.startswith("data:"):
                # Check if srcset exists when src is missing or a data URI
                srcset = img.get("srcset") or img.get("data-srcset")
                if srcset:
                    first_src = srcset.split(",")[0].strip().split()[0]
                    src = first_src
                else:
                    continue

            abs_url = urljoin(base, src)

            if skip_images:
                img["src"] = abs_url
                continue

            safe_name = self._safe_filename(abs_url, "image.png")
            local_rel = os.path.join("images", safe_name)
            local_disk = os.path.join(self.images_dir, safe_name)

            img["src"] = local_rel
            if img.get("data-src"):
                img["data-src"] = local_rel
            if img.get("srcset"):
                del img["srcset"]
            if img.get("data-srcset"):
                del img["data-srcset"]

            assets_to_download.append((abs_url, local_disk))

        # 2. Process <picture> and <source> tags for responsive images
        for source in soup.find_all("source"):
            srcset = source.get("srcset") or source.get("data-srcset")
            if srcset and not skip_images:
                new_srcset_parts = []
                for entry in srcset.split(","):
                    parts = entry.strip().split()
                    if parts:
                        candidate_url = urljoin(base, parts[0])
                        if not candidate_url.startswith("data:"):
                            safe_name = self._safe_filename(candidate_url, "image.png")
                            local_rel = os.path.join("images", safe_name)
                            local_disk = os.path.join(self.images_dir, safe_name)
                            assets_to_download.append((candidate_url, local_disk))
                            desc = f" {parts[1]}" if len(parts) > 1 else ""
                            new_srcset_parts.append(f"{local_rel}{desc}")
                if new_srcset_parts:
                    source["srcset"] = ", ".join(new_srcset_parts)

        # 3. Process SVG <image> tags
        for svg_img in soup.find_all("image"):
            href = svg_img.get("href") or svg_img.get("xlink:href")
            if href and not href.startswith("data:") and not skip_images:
                abs_url = urljoin(base, href)
                safe_name = self._safe_filename(abs_url, "image.svg")
                local_rel = os.path.join("images", safe_name)
                local_disk = os.path.join(self.images_dir, safe_name)
                if svg_img.get("href"):
                    svg_img["href"] = local_rel
                if svg_img.get("xlink:href"):
                    svg_img["xlink:href"] = local_rel
                assets_to_download.append((abs_url, local_disk))

        if fetch_css_js:
            # 4. Process <link> stylesheets, favicons, and preloaded styles/fonts
            for link in soup.find_all("link"):
                rel_list = link.get("rel", [])
                if isinstance(rel_list, str):
                    rel_list = [rel_list]
                rel_lower = [r.lower() for r in rel_list]

                href = link.get("href")
                if not href or href.startswith("data:"):
                    continue

                abs_url = urljoin(base, href)
                is_css = "stylesheet" in rel_lower or any(abs_url.lower().endswith(ext) for ext in CSS_EXTENSIONS)
                is_icon = any(r in rel_lower for r in ("icon", "shortcut icon", "apple-touch-icon"))
                is_font = any(abs_url.lower().endswith(ext) for ext in FONT_EXTENSIONS)

                if is_css or is_icon or is_font:
                    if is_css:
                        safe_name = self._safe_filename(abs_url, "style.css")
                    elif is_icon:
                        safe_name = self._safe_filename(abs_url, "favicon.ico")
                    else:
                        safe_name = self._safe_filename(abs_url, "font.woff2")

                    local_rel = os.path.join("assets", safe_name)
                    local_disk = os.path.join(self.assets_dir, safe_name)
                    link["href"] = local_rel
                    assets_to_download.append((abs_url, local_disk))

            # 5. Process <script> tags
            for script in soup.find_all("script"):
                src = script.get("src")
                if not src or src.startswith("data:"):
                    continue
                abs_url = urljoin(base, src)
                safe_name = self._safe_filename(abs_url, "script.js")
                local_rel = os.path.join("assets", safe_name)
                local_disk = os.path.join(self.assets_dir, safe_name)
                script["src"] = local_rel
                assets_to_download.append((abs_url, local_disk))

            # 6. Extract url(...) references from inline <style> tags
            for style in soup.find_all("style"):
                if style.string:
                    style.string = self._process_css_urls(style.string, base, assets_to_download)

        return assets_to_download

    def _process_css_urls(self, css_content: str, base_url: str,
                          assets_to_download: List[Tuple[str, str]]) -> str:
        """Extracts and localizes url(...) references (fonts, background images) in CSS content."""
        def replace_match(match):
            raw_url = match.group(1).strip('\'"')
            if raw_url.startswith("data:") or not raw_url:
                return match.group(0)

            abs_url = urljoin(base_url, raw_url)
            parsed = urlparse(abs_url)
            path_lower = parsed.path.lower()

            if any(path_lower.endswith(ext) for ext in FONT_EXTENSIONS):
                default_name = "font.woff2"
            elif any(path_lower.endswith(ext) for ext in IMAGE_EXTENSIONS):
                default_name = "bg.png"
            else:
                default_name = "asset.bin"

            safe_name = self._safe_filename(abs_url, default_name)
            local_rel = os.path.join("assets", safe_name)
            local_disk = os.path.join(self.assets_dir, safe_name)
            assets_to_download.append((abs_url, local_disk))
            return f"url('{local_rel}')"

        return re.sub(r'url\s*\(\s*([^\)]+?)\s*\)', replace_match, css_content)

    def extract_deep_links(self, soup: BeautifulSoup, page_url: str) -> List[str]:
        """
        Discovers internal links from interactive elements, data attributes,
        directory listings, and inline script routes.
        """
        discovered: List[str] = []
        base = self._get_effective_base(soup, page_url)

        # 1. Standard anchor tags
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            # Ignore JavaScript and mailto links
            if href.startswith(("javascript:", "mailto:", "tel:", "#")):
                continue
            discovered.append(urljoin(base, href))

        # 2. Interactive and data attributes (SPA buttons, cards, menus)
        for tag in soup.find_all(True):
            for attr in ("data-href", "data-url", "data-link", "data-target"):
                val = tag.get(attr)
                if val and isinstance(val, str) and not val.startswith(("javascript:", "#")):
                    discovered.append(urljoin(base, val.strip()))

        # 3. IFrames
        for iframe in soup.find_all("iframe", src=True):
            src = iframe["src"].strip()
            if not src.startswith("data:"):
                discovered.append(urljoin(base, src))

        # 4. Web server directory listings ("Index of /")
        title_text = soup.title.string if soup.title and soup.title.string else ""
        if "index of" in title_text.lower():
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                # Ignore parent directory and sorting query parameters
                if href in ("../", "./", "/") or href.startswith("?"):
                    continue
                discovered.append(urljoin(base, href))

        # 5. Extract JSON and script routes (Next.js __NEXT_DATA__, JSON-LD)
        for script in soup.find_all("script"):
            script_type = script.get("type", "").lower()
            script_text = script.string or ""
            if "json" in script_type or "NEXT_DATA" in (script.get("id") or ""):
                # Find URLs embedded in JSON
                for match in re.findall(r'"(https?://[^"\\]+|/[a-zA-Z0-9_\-./]+)"', script_text):
                    discovered.append(urljoin(base, match))
            elif script_text and len(script_text) < 50000:
                # Scan inline JS for explicit route paths (e.g. '/wip/...')
                for match in re.findall(r'["\'](/[\w\-]+(?:/[\w\-]+)*)[\'"]', script_text):
                    discovered.append(urljoin(base, match))

        return discovered

    def extract_data_endpoints(self, script_text: str, base_url: str) -> List[str]:
        """
        Scans JavaScript content for dynamic data endpoints (fetch calls, JSON files, API URLs).
        """
        endpoints = []
        # Pattern 1: fetch("path.json") or axios.get("path.json") or similar
        for match in re.findall(r'(?:fetch|axios(?:\.get|\.post)?)\s*\(\s*[\'"`]([^\'"`]+)[\'"`]', script_text):
            endpoints.append(urljoin(base_url, match.strip()))

        # Pattern 2: Explicit mentions of .json files in strings (e.g. 'annotations.json', 'data.json')
        for match in re.findall(r'[\'"`]([a-zA-Z0-9_\-./]+\.json(?:[?#][^\'"`]*)?)[\'"`]', script_text):
            endpoints.append(urljoin(base_url, match.strip()))

        # Pattern 3: Common API route patterns like "/api/..." or "/wp-json/..."
        for match in re.findall(r'[\'"`](/api/[\w\-./?=&%]+|/wp-json/[\w\-./?=&%]+)[\'"`]', script_text):
            endpoints.append(urljoin(base_url, match.strip()))

        return list(dict.fromkeys(endpoints))

    def extract_media_from_json(self, data: any, base_url: str) -> List[Tuple[str, str]]:
        """
        Recursively extracts media URLs (images, videos) from JSON data structures.
        Returns a list of (absolute_url, local_disk_filepath).
        """
        assets: List[Tuple[str, str]] = []

        def recurse(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, str):
                        clean_v = v.strip()
                        lower_v = clean_v.lower()
                        is_img = any(lower_v.endswith(ext) for ext in IMAGE_EXTENSIONS)
                        is_key = k.lower() in ("image", "img", "src", "thumbnail", "thumb", "cover", "poster", "media")
                        if (is_img or is_key) and (clean_v.startswith("http") or clean_v.startswith("/")):
                            abs_url = urljoin(base_url, clean_v)
                            safe_name = self._safe_filename(abs_url, "image.png")
                            local_disk = os.path.join(self.images_dir, safe_name)
                            assets.append((abs_url, local_disk))
                    else:
                        recurse(v)
            elif isinstance(obj, list):
                for item in obj:
                    recurse(item)

        recurse(data)
        return assets

    def json_to_markdown(self, data: any, title: str, page_url: str) -> str:
        """
        Converts structured JSON data into clean Markdown when an SPA page has an empty DOM.
        """
        lines = [
            "-" * 80,
            f"# {title}",
            "",
            f"URL:\n{page_url}",
            "",
            "-" * 80,
            ""
        ]

        def render_value(val, depth=2):
            if isinstance(val, dict):
                item_title = val.get("title") or val.get("name") or val.get("id")
                if item_title and str(item_title).strip():
                    heading_prefix = "#" * min(depth, 5)
                    lines.append(f"\n{heading_prefix} {str(item_title).strip()}\n")

                for k, v in val.items():
                    if k.lower() in ("title", "name", "id") and item_title:
                        continue
                    if isinstance(v, (dict, list)):
                        lines.append(f"\n**{k.replace('_', ' ').capitalize()}**:")
                        render_value(v, depth + 1)
                    else:
                        lines.append(f"- **{k.replace('_', ' ').capitalize()}**: {v}")
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, (dict, list)):
                        render_value(item, depth)
                    else:
                        lines.append(f"- {item}")
            else:
                lines.append(str(val))

        render_value(data)
        return "\n".join(lines) + "\n\n"
