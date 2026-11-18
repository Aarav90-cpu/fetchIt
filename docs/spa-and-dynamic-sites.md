# Single Page Applications & Dynamic Sites

Modern documentation platforms, portfolio viewers, and interactive web applications often operate as Single Page Applications (SPAs). This guide explains how FetchIt handles dynamic client-side applications.

## The Challenge with SPAs

Traditional web crawlers fetch raw HTML using HTTP GET requests. However, on an SPA:

1. The initial HTML returned by the web server is almost empty, often containing only a mount container like `<div id="app"></div>` or `<div id="root"></div>`.
2. The browser executes JavaScript files (e.g. `app.js` or `main.js`) which call `fetch()` to load structured JSON data files (such as `annotations.json`, `projects.json`, or API endpoints).
3. The client-side framework (React, Vue, Angular, Svelte) renders the DOM dynamically in the browser based on the fetched JSON.

If a crawler only reads the initial HTML response, it extracts almost nothing, frequently leaving behind messages like "Nothing here yet" or empty documents.

---

## Strategy 1: Pure Python Dynamic Data Scanner (Default)

FetchIt features a built-in pure Python analyzer that extracts content from SPAs without requiring headless browser binaries or Node.js.

### How the Pure Python Scanner Works

1. **Script Discovery**:
   - The crawler collects all `<script>` tags on the page.
   - For external scripts on the same domain (e.g., `<script src="app.js">`), FetchIt fetches the JavaScript files in parallel.

2. **Endpoint Detection**:
   `Extractor.extract_data_endpoints()` scans all discovered JavaScript using pattern matching:
   - `fetch("...")` and `axios.get("...")` calls.
   - References to `.json` files in string literals (e.g., `'annotations.json'`, `'data.json'`).
   - Standard API endpoints matching `/api/...` or `/wp-json/...`.

3. **Data Fetching & Extraction**:
   - Discovered data URLs are fetched concurrently.
   - If the endpoint returns valid JSON, FetchIt parses the data structure.
   - In `--html` mode, the JSON files are saved locally (e.g., in `assets/annotations.json`) so the client-side app can load data offline.

4. **Media Discovery from JSON**:
   `Extractor.extract_media_from_json()` recursively scans the JSON hierarchy for keys like `image`, `img`, `thumbnail`, `cover`, `poster`, or strings ending in image extensions (`.png`, `.jpg`, `.webp`). These assets are automatically scheduled for concurrent downloading.

5. **JSON-to-Markdown Fallback**:
   If the HTML DOM contains little or no text (less than 150 characters or matching empty placeholders), `Extractor.json_to_markdown()` converts the structured JSON object into formatted Markdown:
   - Dictionary keys (`title`, `name`, `id`) become ATX headings (`## Title`).
   - Nested lists and key-value properties become clean bulleted lists (`- **Description**: ...`).

---

## Strategy 2: Headless Browser Rendering (`--render`)

For websites with complex client-side state, Canvas components, WebGL, or proprietary frameworks where pure data scanning is insufficient, FetchIt provides a headless browser execution flag:

```bash
fetchit https://example.com/app -o app.md --render
```

### How `--render` Works

1. **Chromium Launch**: FetchIt launches a headless instance of Chromium via Playwright.
2. **Navigation & Wait Strategy**:
   - Navigates to the target URL with `wait_until="domcontentloaded"` and a 10-second timeout.
   - Waits an additional 1.5 seconds for deferred AJAX requests and DOM mounts to settle.
   - Avoids `networkidle` strategies that hang on websites with open analytics beacons or WebSocket connections.
3. **DOM Snapshot**: Extracts the fully rendered DOM (`page.content()`) after JavaScript execution.
4. **Graceful Fallback**: If Playwright or Chromium is not installed in the environment, FetchIt logs a warning and automatically falls back to standard HTTP fetching.

---

## Choosing Between Strategies

| Feature | Pure Python Mode (Default) | Headless Browser Mode (`--render`) |
| --- | --- | --- |
| External Dependencies | None (Pure Python) | Requires `playwright` (`pip install playwright`) |
| Execution Speed | Fast (network I/O bound) | Moderate (browser startup & DOM execution) |
| Resource Usage | Low memory footprint | Higher memory footprint for Chromium processes |
| Best For | Standard SPAs with JSON data APIs | JavaScript-heavy pages requiring full DOM evaluation |
