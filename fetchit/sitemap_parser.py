"""Pure Python sitemap parser, replacing the C++ sitemap_parser."""
import re
from typing import List


def extract_urls_from_sitemap(xml_content: str) -> List[str]:
    """Extracts all URLs from <loc> tags in a sitemap XML string."""
    return re.findall(r'<loc>\s*(.*?)\s*</loc>', xml_content)
