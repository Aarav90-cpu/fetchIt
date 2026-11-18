# Crawling & URL Discovery Guide

This guide explains how FetchIt discovers, filters, prioritizes, and traverses web pages during a crawl.

## 1. Discovery Phase

Before launching worker tasks, FetchIt attempts to discover the complete site structure upfront.

### Speculative Probing
FetchIt runs concurrent probes using `asyncio.gather` with a 4-second timeout and 2-second connection timeout across common discovery endpoints:

- **XML Sitemaps**:
  - `/sitemap.xml`
  - `/sitemap_index.xml`
  - `/wp-sitemap.xml`
  - `/sitemap/sitemap-index.xml`
- **RSS & Atom Feeds**:
  - `/feed/`
  - `/rss.xml`
  - `/atom.xml`
  - `/feed.xml`
- **WordPress REST API**:
  - `/wp-json/wp/v2/pages?per_page=100&_fields=link`
  - `/wp-json/wp/v2/posts?per_page=100&_fields=link`

If the starting URL targets a specific subpath (e.g., `https://example.com/docs/`), FetchIt automatically tests these endpoints both at the domain root (`/sitemap.xml`) and within the subdirectory (`/docs/sitemap.xml`).

### Sitemaps vs Link Following
- **Sitemap Found**: All `<loc>` URLs from the sitemap (and any nested sub-sitemaps) are extracted and added to the crawl queue at depth `0`. In sitemap mode, the crawl covers all enumerated pages without depth limitations.
- **No Sitemap Found**: If all discovery probes return 404 or empty responses, FetchIt logs an informational message and switches to link-following mode. In this mode, the crawler explores the starting URL and recursively follows discovered internal links up to the default depth limit of `100` (or the value set by `--depth`).

---

## 2. URL Normalization

URL normalization prevents redundant downloads caused by slight variations in URL structure.

```python
normalize_url(url: str) -> str
```

The normalization pipeline applies three transformations:

1. **Fragment Removal**: URL fragments (`#section-name`) are stripped because they point to client-side anchors on the same document.
2. **Directory Trailing Slash Preservation**:
   - If a URL path does not contain a file extension (e.g., `/docs/guide`), FetchIt ensures it ends with a trailing slash (`/docs/guide/`).
   - If a URL path points to a file with an extension (e.g., `/docs/intro.html` or `/app.js`), FetchIt preserves the extension without appending a slash.
   - Preserving directory trailing slashes ensures that relative asset resolution (such as `urljoin('/docs/', 'image.png')`) resolves correctly to `/docs/image.png` rather than dropping the subfolder and requesting `/image.png`.
3. **Deterministic Query Parameter Sorting**:
   - Query parameters are parsed, decoded, sorted alphabetically by key, and re-encoded. This ensures that `?b=2&a=1` and `?a=1&b=2` resolve to the exact same URL cache key.

---

## 3. Subdirectory Crawl Scoping

When a user specifies a URL targeting a subfolder (such as `https://example.com/wip/?project=example`), FetchIt:

1. Prioritizes the target URL first in the queue.
2. Confines parent directory discovery (`_get_url_ancestors`) to ancestors within the subpath (e.g., `https://example.com/wip/`).
3. Prevents the domain root (`https://example.com/`) from being enqueued as a depth-0 target, which protects against accidental crawl runaway across the entire root domain.

---

## 4. Depth Tracking & Queue Management

The crawl queue contains tuples of `(url, depth)`:

1. The initial target URL and sitemap links are enqueued at `depth = 0`.
2. As workers extract links from pages at `depth = d`, newly discovered links are enqueued at `depth = d + 1`.
3. When a worker dequeues a URL:
   - If `max_depth` is configured and `depth > max_depth`, the worker skips fetching and immediately marks the task as completed.
   - The progress bar is updated inside a `finally:` block, guaranteeing that `pbar.update(1)` executes for every dequeued item regardless of whether it succeeded, failed, or was skipped.

---

## 5. `robots.txt` Compliance

FetchIt automatically fetches and parses `https://<domain>/robots.txt` before beginning a crawl:

- Directives targeting `User-agent: *` or `User-agent: FetchIt` are recorded.
- Disallow and Allow rules are checked using prefix matching against the URL path:
  - If a path matches an `Allow:` rule, crawling is permitted.
  - If a path matches a `Disallow:` rule and no higher-priority allow rule, the URL is skipped.
- Explicit `Sitemap:` declarations in `robots.txt` are automatically added to the candidate sitemap list.
