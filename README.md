# FetchIt

FetchIt downloads web documentation and converts it to Markdown. It works with or without a sitemap -- if no sitemap is found, it discovers pages by following links automatically.

## Features

- Downloads multiple pages at the same time.
- Discovers pages automatically even without a sitemap.
- Respects `robots.txt` rules.
- Removes headers, footers, sidebars, and menus.
- Converts HTML to standard Markdown.
- Saves images locally and updates links.
- Fetches raw HTML with CSS/JS assets (`--html` mode).
- Detects programming languages automatically.
- Saves progress to resume later.
- Controls crawl depth with `--depth`.

## Installation

### Prerequisites

- Python 3.10 or newer

### PyPI (Recommended)

Install the latest version directly from PyPI:

```bash
pip install fetchit-md
```

### Arch Linux

Install using `yay` from the AUR:

```bash
yay -S fetchit-aur
```

### System-Wide Installation (Other Systems)

Use `make` to install system-wide.

```bash
sudo make install
```

To remove the program later:

```bash
sudo make uninstall
```

### Local Virtual Environment

Use a virtual environment to avoid system conflicts.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

Run the tool from the command line.

```bash
fetchit <URL> -o <OUTPUT_FILE> -c <CONCURRENCY> -r <RETRIES>
```

- Run `fetchit` without arguments to see the help menu.

### Options

| Option | Description | Default |
| --- | --- | --- |
| `URL` | Starting website address | Required |
| `-o`, `--output` | Output file name | `output.md` |
| `-c`, `--concurrency` | Maximum pages to download at once | `10` |
| `-r`, `--retries` | Number of retries for failed downloads | `3` |
| `-d`, `--depth` | Maximum crawl depth from the starting URL | Unlimited (sitemap) / 100 (no sitemap) |
| `--no-images` | Skip downloading images and use remote URLs | Disabled |
| `--tree` | Save output as a directory tree of markdown files | Disabled |
| `--html` | Fetch raw HTML with CSS/JS instead of Markdown (skips cleaning, saves as directory tree) | Disabled |
| `--render` | Render JavaScript with a headless browser before extracting content | Disabled |
| `--verbose` | Print detailed debug logs | Disabled |
| `-v`, `--version` | Print the current version | Disabled |

> **Note on `--no-images`**: This flag skips downloading image files to your local disk, but the images are still embedded in the Markdown using their original absolute web URLs (e.g., `![image](https://reddit.com/...)`). This means the images will still load and display when you view the Markdown online or in an editor, as long as you have an active internet connection!

### Example

```bash
fetchit https://developer.android.com/compose -o compose.md -c 20
```

- Crawls the Android Compose documentation.
- Downloads 20 pages at a time.
- Saves output to a single file `compose.md`.
- Saves images in the `images/` directory.

### Directory Tree Example

You can save the documentation as a file tree instead of a single markdown file:

```bash
fetchit https://developer.android.com/compose -o docs --tree
```

This will create a `docs/` folder containing the file structure:
```
docs/
 |- compose/
 |   |- index.md
 |   |- setup.md
 |   |- ui/
 |       |- button.md
```

### Crawling Without a Sitemap

Some sites do not have a `sitemap.xml`. FetchIt handles this automatically by following links found on each page:

```bash
fetchit https://example.com -o example --tree --depth 3
```

- Starts from the given URL and follows links up to 3 levels deep.
- If no `--depth` is specified and no sitemap is found, the default depth is 100.

### Single Page Applications (SPAs) & Dynamic Websites

FetchIt includes built-in dynamic data discovery for JavaScript-heavy sites and Single Page Applications:
- Automatically detects `.json` data files (like `annotations.json` or `data.json`) and API calls in client-side scripts.
- In `--html` mode, downloads these data files locally so client-side applications continue to function offline.
- In Markdown mode, if an SPA returns an empty HTML container, FetchIt extracts the structured data from the discovered JSON files and generates formatted Markdown.
- Use `--render` to execute JavaScript via a headless browser for sites requiring dynamic client-side DOM rendering:

```bash
fetchit https://example.com/app -o app.md --render
```

## Documentation

Comprehensive guides and architectural breakdowns are available in the [docs/](docs/index.md) directory:

- [Architecture & Module Breakdown](docs/architecture.md): Deep-dive into internal classes, methods, and algorithms.
- [CLI Reference](docs/cli-reference.md): Detailed option flags, defaults, and option interactions.
- [Crawling & URL Discovery Guide](docs/crawling-guide.md): Probing, URL normalization, depth limits, and robots.txt.
- [Single Page Applications & Dynamic Sites](docs/spa-and-dynamic-sites.md): Pure Python data scraping and Playwright headless rendering.
- [Output Modes & Formatting](docs/output-modes.md): Single-file Markdown, Directory Tree Markdown, and Offline HTML.
- [Installation Guide](docs/installation.md): Installation options for PyPI, AUR, Makefile, and development environments.

## Architecture

- **Python Crawler**: Manages concurrent network requests, retries, and depth tracking.
- **Python Extractor**: Cleans HTML and converts it to Markdown.
- **URL Manager**: Deduplicates visited URLs.
- **Sitemap Parser**: Extracts URLs from sitemap XML files.
- **Robots Parser**: Respects `robots.txt` Disallow/Allow rules.
