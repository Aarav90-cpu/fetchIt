# FetchIt Documentation

FetchIt is a command-line tool and asynchronous web crawler designed to download online documentation, articles, and websites and convert them into clean, structured Markdown or localized offline HTML.

## Why FetchIt is Needed

1. **Fragmented Online Documentation**: Modern software libraries, frameworks, and web platforms spread documentation across hundreds of linked web pages. Reading or searching across these sites offline or loading them into Large Language Models (LLMs) requires a consolidated, clean format.
2. **Boilerplate Noise**: Web pages contain navigation bars, cookie banners, tracking scripts, headers, sidebars, and footers. FetchIt automatically detects and extracts the core content while stripping away boilerplate elements.
3. **Missing or Broken Sitemaps**: Many websites and documentation hubs do not provide a `sitemap.xml`. FetchIt automatically falls back to recursive link following with configurable depth limits.
4. **Single Page Applications (SPAs)**: Many modern sites serve an empty HTML skeleton and populate the page dynamically using JavaScript and JSON APIs. FetchIt includes both a pure Python dynamic data scanner (inspecting client scripts and JSON files) and an optional headless browser renderer (`--render`).
5. **Asset & Styling Preservation**: FetchIt can download images, stylesheets, scripts, and fonts locally, updating relative links so documentation displays correctly offline.

## Core Capabilities

- **High Concurrency**: Uses Python's `asyncio` and `aiohttp` to download multiple pages and assets simultaneously.
- **Pure Python**: Architecture-independent implementation with zero compilation dependencies.
- **Robust URL Management**: Thread-safe URL deduplication and normalization preventing infinite crawling loops.
- **Persistent SQLite Cache**: Caches visited pages in `fetchit_cache.db` to resume interrupted crawl sessions without duplicate requests.
- **Multiple Output Formats**: Supports single-file Markdown with an automated Table of Contents, directory-tree Markdown (`--tree`), or full offline HTML (`--html`).

## Documentation Structure

- [Architecture Guide](architecture.md): Detailed internal structure of all modules, classes, and algorithms.
- [CLI Reference](cli-reference.md): Complete list of command-line options, argument types, defaults, and interactions.
- [Crawling Guide](crawling-guide.md): How URL discovery, link following, depth limits, and robots.txt parsing work.
- [Single Page Applications & Dynamic Sites](spa-and-dynamic-sites.md): Handling JavaScript-heavy websites via pure Python data scraping and Playwright headless rendering.
- [Output Modes](output-modes.md): Comparison and usage of Single File Markdown, Directory Tree Markdown, and Offline HTML modes.
- [Installation Guide](installation.md): Installation options via PyPI, AUR, Makefile, and source development.
