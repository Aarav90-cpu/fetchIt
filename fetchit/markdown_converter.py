import re
from bs4 import BeautifulSoup
from markdownify import MarkdownConverter

class FetchItConverter(MarkdownConverter):
    """Custom markdown converter for FetchIt to ensure clean formatting."""

    def __init__(self, **options):
        super().__init__(**options)
        self.options['heading_style'] = 'ATX'
        self.options['code_language'] = ''
        self.options['escape_asterisks'] = False
        self.options['escape_underscores'] = False

    def convert_pre(self, el, text, convert_as_inline=False, **kwargs):
        """Handle fenced code blocks and attempt basic language detection."""
        if not text:
            return ""

        # Try to detect language from class
        code_tag = el.find('code')
        lang = ""
        if code_tag and code_tag.get('class'):
            classes = code_tag.get('class')
            for cls in classes:
                if cls.startswith('language-') or cls.startswith('lang-'):
                    lang = cls.split('-')[-1]
                    break
        
        # Simple heuristics if language is not explicitly defined
        if not lang:
            content = text.lower()
            if "import " in content and "def " in content:
                lang = "python"
            elif "fun " in content and "val " in content:
                lang = "kotlin"
            elif "public class " in content:
                lang = "java"
            elif "<?xml" in content or "</" in content:
                lang = "xml"
            elif "apply plugin:" in content or "dependencies {" in content:
                lang = "gradle"
            elif "#!/bin/bash" in content or "$" in content:
                lang = "bash"

        return f"\n```{lang}\n{text.strip()}\n```\n"



def html_to_markdown(soup: BeautifulSoup, page_title: str, url: str) -> str:
    """Converts a BeautifulSoup object to formatted Markdown."""
    converter = FetchItConverter(
        strip=['script', 'style', 'nav', 'header', 'footer'],
        bullets='-',
        strong_em_symbol='**'
    )
    content_md = converter.convert_soup(soup).strip()
    
    # Ensure correct nesting and spacing
    content_md = re.sub(r'\n{3,}', '\n\n', content_md)
    
    # Format the final page output
    header = "-" * 80 + "\n"
    header += f"# {page_title}\n\n"
    header += f"URL:\n{url}\n\n"
    header += "-" * 80 + "\n\n"
    
    return header + content_md + "\n\n"
