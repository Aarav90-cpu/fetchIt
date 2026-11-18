# Architecture & Module Breakdown

FetchIt is composed of decoupled Python modules responsible for command-line parsing, crawling orchestration, content extraction, Markdown conversion, URL deduplication, and persistence.

## Architecture Overview

```
                        +-------------------+
                        |   fetchit.cli     |
                        +---------+---------+
                                  |
                                  v
                        +-------------------+
                        |  fetchit.crawler  |
                        +----+---------+----+
                             |         |
              +--------------+         +--------------+
              |                                       |
              v                                       v
    +-------------------+                   +-------------------+
    | fetchit.extractor |                   |   fetchit.cache   |
    +---------+---------+                   +-------------------+
              |
              +-----------------------+
              |                       |
              v                       v
    +-------------------+   +-------------------+
    |fetchit.markdown_  |   |fetchit.url_manager|
    |   converter       |   +-------------------+
    +-------------------+   |fetchit.sitemap_   |
                            |     parser        |
                            +-------------------+
```

---

## 1. `fetchit.cli` (`fetchit/cli.py`)

The entrypoint module for the command-line interface.

### Key Components

- **`TqdmLoggingHandler`**: A custom logging handler inheriting from `logging.Handler`. Standard Python logging outputs to `sys.stderr`, which collides with `tqdm` progress bars and causes terminal cursor flicker or distorted lines. `TqdmLoggingHandler` routes all log records through `tqdm.tqdm.write()`, ensuring clean output without interrupting progress bar redraws.
- **`setup_logging(verbose: bool)`**: Configures root logger handlers and log levels (`DEBUG` when `--verbose` is specified, otherwise `INFO`).
- **`main()`**: Defines the command-line interface using `argparse.ArgumentParser`. Validates arguments, checks for incompatible options (e.g., `--tree` and `--html`), instantiates the `Crawler`, and handles graceful shutdowns via `KeyboardInterrupt` to save completed pages before exiting.

---

## 2. `fetchit.crawler` (`fetchit/crawler.py`)

The asynchronous crawling engine responsible for orchestrating network requests, discovery, and worker coroutines.

### Key Components

- **`normalize_url(url: str) -> str`**: Standardizes URLs to prevent duplicate visits. Strips URL fragments (`#section`), preserves trailing slashes on directory paths (e.g., `/docs/`) so `urllib.parse.urljoin` resolves relative paths accurately, and sorts query parameters deterministically.
- **`RobotsRules`**: Lightweight parser for `robots.txt`. Extracts `Sitemap:`, `Allow:`, and `Disallow:` directives applicable to wildcard `*` or `FetchIt` user agents, allowing the crawler to respect webmaster policies.
- **`Crawler`**: Central orchestrator initialized with target URL, concurrency, retry limits, depth limits, and output modes.
  - **`_discover_initial_urls(session)`**: Probes standard discovery endpoints concurrently using `asyncio.gather` and fast timeouts (4 seconds total, 2 seconds connection timeout). Checks root and subdirectory paths for `/sitemap.xml`, `/sitemap_index.xml`, `/wp-sitemap.xml`, `/feed/`, `/rss.xml`, `/atom.xml`, and WordPress REST API endpoints (`/wp-json/wp/v2/pages`, `/wp-json/wp/v2/posts`).
  - **`_get_url_ancestors(url: str) -> List[str]`**: Generates ancestor directory paths for directory structure discovery while keeping scope confined to the provided subpath.
  - **`fetch(session, url, warn_on_error)`**: Performs asynchronous HTTP GET requests using `aiohttp` with exponential backoff retries (`2 ** attempt`) and modern browser User-Agent headers.
  - **`fetch_rendered(url)`**: Uses Playwright headless Chromium to execute client-side JavaScript. Uses `domcontentloaded` with a 10-second timeout to avoid indefinite hangs from long-polling or background analytics.
  - **`download_asset(session, asset_url, local_path)`**: Downloads binary assets (images, fonts, stylesheets, scripts). When a CSS file is downloaded, it automatically parses `url(...)` declarations to discover and enqueue nested fonts and background images.
  - **`process_page(session, url, html)`**: Core processing method executed by workers. Performs deep link extraction, DOM content cleaning, concurrent asset downloading via `asyncio.Semaphore(10)`, script scanning for SPA data endpoints, JSON structured data parsing, and Markdown conversion.
  - **`worker(name, session, queue, pbar)`**: Consumer task that reads `(url, depth)` tuples from `asyncio.Queue`. Enforces depth limits, checks cache, invokes `process_page`, enqueues discovered links, and guarantees progress bar updates via `finally: pbar.update(1)`.
  - **`_generate_output()`**: Assembles a single concatenated Markdown file sorted by URL with an auto-generated Table of Contents and anchor links.
  - **`_generate_tree_output()`**: Creates a mirrored folder structure of Markdown files (`index.md` or `<name>.md`) with recalculated relative image links.
  - **`_generate_html_tree_output()`**: Creates an offline-browsable HTML website with localized stylesheets, fonts, scripts, and rewritten relative hyperlinks between pages.

---

## 3. `fetchit.extractor` (`fetchit/extractor.py`)

Responsible for DOM parsing, content isolation, asset rewriting, and SPA data extraction.

### Key Components

- **`Extractor`**: Initialized with base URL and output directory paths for `images/` and `assets/`.
- **`extract_main_content(soup: BeautifulSoup) -> Optional[BeautifulSoup]`**: Heuristically extracts the core article content by searching for `<article>`, `<main>`, elements with `id` or `class` containing `content` or `main`, or `<body>`. To avoid corrupting the original document, it creates an isolated clone (`BeautifulSoup(str(target), "lxml")`) before stripping boilerplate tags (`nav`, `header`, `footer`, `aside`, `style`, `noscript`, `iframe`, `form`) and sidebar/cookie classes.
- **`_safe_filename(url: str, default_name: str) -> str`**: Generates filesystem-safe, collision-resistant filenames by combining a hash of the URL with a sanitized basename.
- **`_get_effective_base(soup: BeautifulSoup, page_url: str) -> str`**: Detects and resolves HTML `<base href="...">` tags so relative links and asset paths resolve against the declared base rather than the raw URL.
- **`process_assets(soup, page_url, skip_images, fetch_css_js)`**: Locates all media elements (`<img>` with lazy-loading attributes, `<picture>`, `<source>` responsive `srcset`, SVG `<image>`, `<link rel="stylesheet">`, `<script src="...">`, `<link rel="icon">`, and inline `<style>` tags), rewrites their references to local relative paths, and returns a download list.
- **`_process_css_urls(css_content, base_url, assets_to_download)`**: Parses CSS `url(...)` declarations using regular expressions, detects font (`.woff2`, `.ttf`, etc.) and image extensions, rewrites paths to local assets, and queues files for download.
- **`extract_deep_links(soup, page_url) -> List[str]`**: Discovers links from standard `<a>` tags, HTML5 interactive attributes (`data-href`, `data-url`, `data-target`), `<iframe>` sources, Apache/Nginx web server directory indexes (`Index of /`), and embedded JSON route manifests (e.g. Next.js `__NEXT_DATA__`).
- **`extract_data_endpoints(script_text, base_url) -> List[str]`**: Scans JavaScript source code using regex patterns to find data endpoints: `fetch()` and `axios` calls, explicit `.json` file references, and `/api/` or `/wp-json/` endpoints.
- **`extract_media_from_json(data, base_url) -> List[Tuple[str, str]]`**: Recursively traverses arbitrary JSON dictionaries and lists to extract image and media URLs.
- **`json_to_markdown(data, title, page_url) -> str`**: Converts structured JSON data into hierarchical Markdown headings, bullet lists, and key-value entries when an SPA renders an empty HTML container.

---

## 4. `fetchit.markdown_converter` (`fetchit/markdown_converter.py`)

Handles transformation of cleaned HTML DOM trees into standard Markdown.

### Key Components

- **`FetchItConverter`**: Subclass of `markdownify.MarkdownConverter`.
  - Configures ATX heading style (`# Heading`).
  - Disables aggressive backslash-escaping of asterisks and underscores to maintain readable prose and code identifiers.
  - Implements **`convert_pre(el, text)`**: Fences `<pre><code>` blocks with triple backticks (```` ``` ````). Detects language syntax from CSS classes (`language-python`, `lang-js`) or applies heuristic detection for Python, Kotlin, Java, Gradle, XML, and Bash.
- **`html_to_markdown(soup, page_title, url) -> str`**: Top-level function that runs the converter, compresses excessive whitespace to double newlines, and prepends a metadata banner with page title, divider lines, and source URL.

---

## 5. `fetchit.url_manager` (`fetchit/url_manager.py`)

Thread-safe URL tracking and deduplication.

### Key Components

- **`URLManager`**: Wraps a Python `set` with a `threading.Lock`. Provides `add_and_check(url: str) -> bool`, which atomically checks if a URL has already been seen. Returns `True` if newly added, or `False` if duplicate, preventing race conditions across concurrent workers.

---

## 6. `fetchit.sitemap_parser` (`fetchit/sitemap_parser.py`)

Pure Python XML sitemap extractor.

### Key Components

- **`extract_urls_from_sitemap(xml_content: str) -> List[str]`**: Uses regex `<loc>\s*(.*?)\s*</loc>` extraction to parse page and nested sitemap URLs from standard XML sitemaps and sitemap index files without heavy XML schema parsing dependencies.

---

## 7. `fetchit.cache` (`fetchit/cache.py`)

Persistent local SQLite storage for crawl state.

### Key Components

- **`Cache`**: Manages an SQLite database (`fetchit_cache.db`).
  - Table schema: `pages (url TEXT PRIMARY KEY, content TEXT, status INTEGER)`.
  - **`get_page(url)`**: Returns cached HTML content for previously visited URLs that returned HTTP 200.
  - **`save_page(url, content, status)`**: Uses `REPLACE INTO` to persist page content and HTTP status.
  - **`is_visited(url)`**: Quick boolean existence check.
  - Allows interrupted crawls to resume immediately without re-fetching existing network resources.

