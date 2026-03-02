"""
MRAgent — Web Tools
Provides search and fetching capabilities inspired by Bonza/nanobot.

Created: 2026-03-02
"""

import time
import requests
from urllib.parse import urlparse
import re

from bs4 import BeautifulSoup
from tools.base import Tool
from utils.logger import get_logger
from utils.helpers import truncate
from utils.sanitizer import sanitize_external_data

logger = get_logger("tools.web")

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_2) AppleWebKit/537.36"
MAX_CONTENT_LENGTH = 15000

class WebSearchTool(Tool):
    """Search the web (Wrapper around configured providers)."""

    name = "web_search"
    description = (
        "Search the internet for information. Returns titles, URLs, and "
        "snippets of the results. "
        "IMPORTANT: You MUST subsequently use web_fetch to read the actual URL content to ensure factual accuracy."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
            "count": {
                "type": "integer",
                "description": "Number of results (1-10, default: 5)",
            },
        },
        "required": ["query"],
    }

    def execute(self, query: str, count: int = 5) -> str:
        try:
            from providers import get_search
            # get_search() will return the active search provider
            raw_results = get_search().search_formatted(query, count)
            return sanitize_external_data(raw_results, source_label="web search")
        except Exception as e:
            logger.error(f"Search Web Tool error: {e}")
            return f"❌ Search error: {e}"


class WebFetchTool(Tool):
    """Fetch URL and extract readable content."""

    name = "web_fetch"
    description = (
        "Fetch a URL and extract its readable content as Markdown. "
        "Use this for reading articles, documentation, or news completely."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to fetch",
            },
        },
        "required": ["url"],
    }

    def _html_to_markdown(self, soup: BeautifulSoup) -> str:
        """Convert basic HTML structure to clean Markdown."""
        # Convert links
        for a in soup.find_all('a', href=True):
            if a.text.strip():
                a.replace_with(f"[{a.text.strip()}]({a['href']})")
        
        # Convert headings
        for i in range(1, 7):
            for h in soup.find_all(f'h{i}'):
                if h.text.strip():
                    h.replace_with(f"\n\n{'#' * i} {h.text.strip()}\n\n")
                    
        # Convert lists
        for li in soup.find_all('li'):
            if li.text.strip():
                li.replace_with(f"\n- {li.text.strip()}")
                
        # Clean up tags we want to format with linebreaks
        for tag in soup.find_all(['p', 'div', 'section', 'article', 'br', 'hr']):
            tag.insert_after("\n\n")
            
        return soup.get_text()

    def execute(self, url: str) -> str:
        parsed = urlparse(url)
        if not parsed.scheme:
            url = "https://" + url
            parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return f"❌ Invalid URL scheme: {parsed.scheme}"

        logger.info(f"WebFetchTool fetching: {url}")
        start_time = time.time()

        try:
            resp = requests.get(
                url, 
                headers={"User-Agent": USER_AGENT},
                timeout=20.0,
                allow_redirects=True
            )
            resp.raise_for_status()
        except requests.exceptions.SSLError:
            logger.warning(f"SSL verification failed for {url}. Retrying without verification.")
            resp = requests.get(
                url, 
                headers={"User-Agent": USER_AGENT},
                timeout=20.0,
                allow_redirects=True,
                verify=False
            )
            resp.raise_for_status()
        except Exception as e:
            return f"❌ HTTP fetch error: {e}"

        duration_ms = (time.time() - start_time) * 1000

        try:
            soup = BeautifulSoup(resp.text, "html.parser")

            # Remove noise
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "meta"]):
                tag.decompose()

            title = soup.title.string.strip() if soup.title and soup.title.string else parsed.netloc

            # We focus on main article contents if possible
            main_content = soup.find('main') or soup.find('article') or soup.find('div', role='main') or soup.body
            if not main_content:
                main_content = soup

            text = self._html_to_markdown(main_content)

            # Normalize whitespace
            text = re.sub(r'[ \t]+', ' ', text)
            text = re.sub(r'\n{3,}', '\n\n', text).strip()
            
            content = truncate(text, MAX_CONTENT_LENGTH)
            
            logger.info(f"Fetched {url}: {len(content)} chars ({duration_ms:.0f}ms)")
            safe_content = sanitize_external_data(content, source_label=f"web_fetch: {parsed.netloc}")

            return f"🌐 {title}\nURL: {resp.url}\n\n{safe_content}"
            
        except Exception as e:
            return f"❌ Parsing error: {e}"
