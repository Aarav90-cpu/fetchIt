# Output Modes & Formatting

FetchIt supports three primary output formats depending on whether you are compiling documentation for an e-reader or LLM context, organizing a local wiki, or backing up an entire browsable website.

---

## 1. Single File Markdown Mode (Default)

When neither `--tree` nor `--html` is passed, FetchIt compiles all visited pages into a single consolidated `.md` file.

### Usage
```bash
fetchit https://developer.android.com/compose -o compose.md
```

### Generated Structure
1. **Automated Table of Contents**:
   FetchIt sorts all visited pages by URL and generates an numbered Table of Contents at the top of the file with Markdown anchor links:
   ```markdown
   # Table of Contents

   1. [Compose Basics](#compose-basics)
   2. [Layouts in Compose](#layouts-in-compose)
   3. [State and Jetpack Compose](#state-and-jetpack-compose)

   ---
   ```
2. **Page Metadata Headers**:
   Each page section is separated by a horizontal divider and a standardized header block containing the title and source URL:
   ```markdown
   --------------------------------------------------------------------------------
   # Layouts in Compose

   URL:
   https://developer.android.com/compose/layouts

   --------------------------------------------------------------------------------
   ```
3. **Local Image Storage**:
   Downloaded images are placed in an `images/` directory adjacent to the output Markdown file, with sanitized filenames preventing collisions.

---

## 2. Directory Tree Markdown Mode (`--tree`)

Directory tree mode mirrors the URL path structure on disk, creating a folder hierarchy of individual Markdown files.

### Usage
```bash
fetchit https://developer.android.com/compose -o compose_docs --tree
```

### Generated Structure
```
compose_docs/
 ├── index.md                  # Root page (https://developer.android.com/compose/)
 ├── images/                   # Shared image assets directory
 │    ├── 104231_hero.png
 │    └── 849201_diagram.png
 └── layouts/
      ├── index.md             # Subdirectory index (https://developer.android.com/compose/layouts/)
      └── row-column.md        # Child page (https://developer.android.com/compose/layouts/row-column)
```

### Relative Link Rewriting
Because files in a tree output exist at varying directory depths, FetchIt automatically adjusts image links in nested Markdown files. For example, a file inside `layouts/row-column.md` has its image links rewritten from:
```markdown
![Diagram](images/diagram.png)
```
to:
```markdown
![Diagram](../images/diagram.png)
```
This ensures images render correctly regardless of which markdown viewer or editor is opened.

---

## 3. Offline Localized HTML Mode (`--html`)

HTML mode creates a complete, offline-browsable replica of the website with original styling, fonts, scripts, and internal page navigation.

### Usage
```bash
fetchit https://example.com/docs -o site_backup --html
```

### What HTML Mode Preserves & Localizes

1. **Document Structure**: Retains `<head>`, `<meta>`, stylesheets, and scripts instead of stripping them for Markdown conversion.
2. **Stylesheets & Web Fonts**:
   - Downloads all `<link rel="stylesheet">` files into an `assets/` directory.
   - Inspects CSS files for `url(...)` declarations, downloading referenced web fonts (`.woff2`, `.ttf`) and background images (`.png`, `.svg`) and rewriting their paths within the CSS.
3. **Client-side Scripts & SPA Data**:
   - Downloads referenced JavaScript files into `assets/`.
   - Saves dynamic JSON files (`annotations.json`, `data.json`) discovered by the SPA scanner into `assets/` so client-side JavaScript applications continue to load data offline.
4. **Internal Hyperlink Rewriting**:
   - Inspects all `<a href="...">` links.
   - If a link targets another page downloaded during the crawl, the `href` attribute is rewritten to a relative path pointing to the local HTML file (e.g., `href="../../guide/setup.html#section"`).
   - Links targeting external domains or pages outside the crawl scope remain absolute web URLs.

---

## Output Mode Comparison

| Feature | Single File (`.md`) | Tree (`--tree`) | HTML (`--html`) |
| --- | --- | --- | --- |
| File Format | Markdown | Markdown | HTML |
| Organization | Single `.md` file | Nested directory tree | Nested directory tree |
| Assets Localized | Images | Images | Images, CSS, JS, Fonts, JSON |
| Offline Browsable | In Markdown readers | In Markdown readers | In any standard web browser |
| Best For | LLM context, search, printing | Documentation wikis, Git repos | Complete offline archives |

