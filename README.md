# FetchIt

FetchIt is a tool to download web documentation and convert it into a single clean Markdown file.

## Features

- **Concurrent Crawling**: Downloads many pages at the same time.
- **Smart Extraction**: Removes headers, footers, sidebars, and menus.
- **Markdown Conversion**: Converts HTML into standard Markdown formats.
- **Image Downloading**: Saves images locally and updates links.
- **Auto Language Detection**: Detects code languages like Python, Java, and Bash.
- **Cache and Resume**: Saves progress using SQLite so it can resume after stopping.
- **Fast Parsing**: Uses a C++ module in the background for fast XML parsing and URL checking.

## Installation

Follow these steps to set up the project on your machine.

### Prerequisites

- Python 3.8 or newer
- C++ compiler (like GCC or Clang)
- `make` utility

### Setup Instructions

1. Clone the repository or navigate to the folder.
2. Create and activate a Python virtual environment.
3. Install the dependencies.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

- `python3 -m venv .venv` creates an isolated Python space.
- `source .venv/bin/activate` activates the isolated Python space.
- `pip install -e .` installs FetchIt and all required packages from `setup.py`.

## Usage

Run the tool using the command line interface (CLI).

```bash
fetchit <URL> -o <OUTPUT_FILE> -c <CONCURRENCY> -r <RETRIES>
```

- `fetchit` is the main command to start the crawler.
- The C++ extension will automatically compile in the background when you run this command.

### Available Commands and Options

| Command/Option | Description | Default Value |
| --- | --- | --- |
| `URL` | The starting website address to crawl | (Required) |
| `-o`, `--output` | The name of the final Markdown file | `output.md` |
| `-c`, `--concurrency` | Maximum number of pages to download at once | `10` |
| `-r`, `--retries` | Number of times to retry a failed download | `3` |
| `-v`, `--verbose` | Print detailed logs for debugging | Disabled |

### Example

```bash
fetchit https://developer.android.com/compose -o compose.md -c 20
```

- This command will start crawling the given Android Compose URL.
- It will download up to 20 pages at the same time.
- It will save the final result in a file named `compose.md`.
- All images will be saved in a folder named `images/` in your current directory.

## Architecture

The project is split into three main parts.

- **C++ Extension**: Handles fast sitemap parsing and checking for duplicate URLs.
- **Python Crawler**: Manages network requests, retries, and caching.
- **Python Extractor**: Analyzes the HTML, cleans it, and converts it to Markdown.
