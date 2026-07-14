# FetchIt

FetchIt downloads web documentation and converts it to a single Markdown file.

## Features

- Downloads multiple pages at the same time.
- Removes headers, footers, sidebars, and menus.
- Converts HTML to standard Markdown.
- Saves images locally and updates links.
- Detects programming languages automatically.
- Saves progress to resume later.
- Uses C++ for fast parsing.

## Installation

### Prerequisites

- Python 3.8 or newer
- C++ compiler (like GCC or Clang)
- `make` utility

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
- The C++ extension compiles automatically on the first run.

### Options

| Option | Description | Default |
| --- | --- | --- |
| `URL` | Starting website address | Required |
| `-o`, `--output` | Output file name | `output.md` |
| `-c`, `--concurrency` | Maximum pages to download at once | `10` |
| `-r`, `--retries` | Number of retries for failed downloads | `3` |
| `--no-images` | Skip downloading images and use remote URLs | Disabled |
| `--tree` | Save output as a directory tree of markdown files | Disabled |
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

## Architecture

- **C++ Extension**: Parses sitemaps and checks URLs quickly.
- **Python Crawler**: Manages network requests and retries.
- **Python Extractor**: Cleans HTML and converts it to Markdown.
