# Installation Guide

FetchIt is distributed as a pure Python package compatible with Linux, macOS, and Windows.

---

## Prerequisites

- **Python**: Version 3.10 or newer (tested with Python 3.10, 3.11, 3.12, 3.13, and 3.14).
- **Core Dependencies**: Installed automatically by package managers:
  - `aiohttp`: Asynchronous HTTP client/server for asyncio
  - `beautifulsoup4`: HTML/XML document parsing and traversal
  - `lxml`: High-performance XML/HTML parser backend
  - `markdownify`: HTML to Markdown conversion
  - `tqdm`: Terminal progress bar integration

---

## 1. PyPI Installation (Recommended)

Install the latest release directly from the Python Package Index (PyPI):

```bash
pip install fetchit-md
```

To upgrade an existing installation:

```bash
pip install --upgrade fetchit-md
```

After installation, the `fetchit` executable will be available on your system `PATH`.

---

## 2. Arch Linux (AUR)

For Arch Linux and derivative distributions (Manjaro, EndeavourOS), FetchIt is available on the Arch User Repository (AUR):

Using `yay`:
```bash
yay -S fetchit-aur
```

Using `paru`:
```bash
paru -S fetchit-aur
```

---

## 3. System-Wide Installation via Makefile

FetchIt includes a `Makefile` for installing system-wide directly from source:

```bash
# Clone the repository
git clone https://github.com/Aarav90-cpu/fetchIt.git
cd fetchIt

# Install system-wide
sudo make install
```

To remove the installation later:
```bash
sudo make uninstall
```

---

## 4. Local Virtual Environment Development

For contributing or running from source without affecting system packages:

```bash
# 1. Clone the repository
git clone https://github.com/Aarav90-cpu/fetchIt.git
cd fetchIt

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install in editable mode
pip install -e .
```

Verify your installation:
```bash
fetchit --version
```

---

## Optional: Headless Browser Rendering (`--render`)

If you plan to use `--render` to crawl complex Single Page Applications that require browser DOM execution:

```bash
pip install playwright
playwright install chromium
```

