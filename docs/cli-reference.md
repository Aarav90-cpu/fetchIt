# CLI Reference

FetchIt provides a command-line interface with options to control concurrency, output format, crawling depth, asset handling, and rendering behavior.

## Synopsis

```bash
fetchit <URL> [OPTIONS]
```

If run without arguments, FetchIt displays the standard help menu and exits.

---

## Positional Arguments

### `URL`
- **Type**: String
- **Description**: The starting web address to crawl. Can be a domain root (e.g., `https://example.com`) or a deep subdirectory (e.g., `https://example.com/docs/intro`).
- **Required**: Yes

---

## Options & Flags

### `-o`, `--output <PATH>`
- **Type**: String
- **Default**: `output.md`
- **Description**: Specifies the destination filename or directory.
  - In single-file Markdown mode (default): Name of the generated `.md` file.
  - In tree Markdown mode (`--tree`): Name of the directory to hold the generated file tree.
  - In HTML mode (`--html`): Name of the directory to hold the offline website files.

### `-c`, `--concurrency <INT>`
- **Type**: Integer
- **Default**: `10`
- **Description**: The maximum number of concurrent HTTP worker tasks downloading pages and assets simultaneously. Increasing this value speeds up crawls on high-bandwidth networks, while decreasing it helps avoid rate limits or HTTP 429 responses from protected servers.

### `-r`, `--retries <INT>`
- **Type**: Integer
- **Default**: `3`
- **Description**: The number of attempts to make for failed requests before giving up. Failed requests employ exponential backoff with jitter (`min(2 ** attempt, 4)` seconds).

### `-d`, `--depth <INT>`
- **Type**: Integer
- **Default**: Unlimited when a sitemap is found; `100` when crawling via link-following without a sitemap.
- **Description**: The maximum crawl depth from the starting URL. A depth of `0` processes only the initial starting URL. A depth of `1` crawls the starting URL and links directly discovered on it. Subsequent levels increment the depth by 1.

### `--no-images`
- **Type**: Flag (boolean)
- **Default**: Disabled
- **Description**: Disables downloading image files to local storage. When this flag is enabled, image references in the generated Markdown retain their absolute remote web URLs (e.g., `![alt](https://example.com/img.png)`), keeping output file sizes minimal while remaining viewable online.

### `--tree`
- **Type**: Flag (boolean)
- **Default**: Disabled
- **Description**: Saves output as a mirrored directory hierarchy of individual Markdown files instead of concatenating all pages into a single file. Directories contain `index.md` files or subpage Markdown documents reflecting the original URL structure.

### `--html`
- **Type**: Flag (boolean)
- **Default**: Disabled
- **Description**: Downloads the raw HTML documents rather than converting them to Markdown. Automatically preserves `<head>`, styles, scripts, fonts, and images, and rewrites hyperlinks so the site can be browsed completely offline in any web browser.
- **Interaction**: If `--tree` is specified alongside `--html`, `--tree` is ignored because HTML mode implicitly organizes files into a directory hierarchy.

### `--render`
- **Type**: Flag (boolean)
- **Default**: Disabled
- **Description**: Launches a headless Chromium browser using Playwright to evaluate client-side JavaScript before content extraction. Use this option when crawling Single Page Applications (SPAs) or dynamic websites where the initial HTML is a skeleton container.

### `--verbose`
- **Type**: Flag (boolean)
- **Default**: Disabled
- **Description**: Enables verbose `DEBUG` logging. Displays detailed probe records, asset discovery notices, CSS parsing notes, and worker connection states.

### `-v`, `--version`
- **Type**: Flag
- **Description**: Prints the installed FetchIt version (e.g., `fetchit 0.0.6`) and exits.

---

## Flag Interaction Table

| Desired Result | Recommended Command |
| --- | --- |
| Single Markdown file with table of contents | `fetchit https://example.com -o docs.md` |
| Directory tree of Markdown files | `fetchit https://example.com -o docs --tree` |
| Deep crawl without sitemap | `fetchit https://example.com -o docs --depth 20` |
| Full offline browsable website | `fetchit https://example.com -o offline_site --html` |
| Single Page Application with dynamic JS | `fetchit https://example.com/spa -o spa.md --render` |
| Fast crawl skipping local image downloads | `fetchit https://example.com -o fast.md --no-images` |
