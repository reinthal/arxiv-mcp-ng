#!/usr/bin/env python3
"""
FastMCP server for arxiv-mcp-ng - Convert arXiv papers to Markdown format.

This server exposes tools to convert arXiv papers from LaTeX source to Markdown
using the arxiv2md.org API with centralized rate limiting (3 requests/second).
"""

from fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import Tuple, Optional
import logging
import asyncio
import time
from collections import deque
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastMCP server
mcp = FastMCP("arxiv-mcp-ng")


# ============================================================================
# Centralized Rate Limiter
# ============================================================================

class RateLimiter:
    """
    Centralized rate limiter using a sliding window approach.
    Ensures no more than max_requests requests occur within the time_window.
    """

    def __init__(self, max_requests: int = 3, time_window: float = 1.0):
        """
        Initialize the rate limiter.

        Args:
            max_requests: Maximum number of requests allowed in the time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.request_times = deque()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """
        Acquire permission to make a request.
        Blocks if rate limit would be exceeded.
        """
        async with self._lock:
            now = time.time()

            # Remove timestamps outside the current window
            while self.request_times and self.request_times[0] <= now - self.time_window:
                self.request_times.popleft()

            # If we're at the limit, wait until the oldest request expires
            if len(self.request_times) >= self.max_requests:
                sleep_time = self.request_times[0] + self.time_window - now
                if sleep_time > 0:
                    logger.info(
                        f"Rate limit reached ({self.max_requests} requests/{self.time_window}s). "
                        f"Waiting {sleep_time:.2f} seconds..."
                    )
                    await asyncio.sleep(sleep_time)

                # Clean up again after sleeping
                now = time.time()
                while self.request_times and self.request_times[0] <= now - self.time_window:
                    self.request_times.popleft()

            # Record this request
            self.request_times.append(now)
            logger.debug(f"Request permitted. Current window: {len(self.request_times)}/{self.max_requests}")


# Global rate limiter instance - shared across all tool invocations
_rate_limiter = RateLimiter(max_requests=3, time_window=1.0)


def rate_limited(func):
    """
    Decorator to apply centralized rate limiting to both sync and async functions.
    """
    if asyncio.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            await _rate_limiter.acquire()
            return await func(*args, **kwargs)
        return async_wrapper
    else:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we need to run the acquire in an event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, just await
                # This shouldn't happen with FastMCP but handle it gracefully
                raise RuntimeError("Cannot use sync rate-limited function in async context")
            else:
                loop.run_until_complete(_rate_limiter.acquire())
            return func(*args, **kwargs)
        return sync_wrapper


class ArxivConversionResult(BaseModel):
    """Result of arxiv paper conversion"""
    markdown: str = Field(description="The converted markdown content")
    title: Optional[str] = Field(None, description="Paper title from metadata")
    authors: Optional[list[str]] = Field(None, description="Paper authors from metadata")
    abstract: Optional[str] = Field(None, description="Paper abstract from metadata")
    url: str = Field(description="Original arXiv URL")


@mcp.tool()
@rate_limited
async def convert_arxiv_to_markdown(
    arxiv_url: str,
    remove_refs: bool = True,
    remove_toc: bool = False,
    remove_inline_citations: bool = True,
    section_filter_mode: str = "exclude",
    sections: list[str] = []
) -> ArxivConversionResult:
    """
    Convert an arXiv paper to Markdown format using the arxiv2md.org API.

    This tool takes an arXiv URL and converts the paper to Markdown format via the
    arxiv2md.org API service.

    Rate Limited: This tool is subject to a server-wide rate limit of 3 requests/second.

    Args:
        arxiv_url: The arXiv URL (e.g., https://arxiv.org/abs/1706.03762)
        remove_refs: Remove references section (default: True)
        remove_toc: Remove table of contents (default: False)
        remove_inline_citations: Remove inline citations (default: True)
        section_filter_mode: How to filter sections - "exclude" or "include" (default: "exclude")
        sections: List of section names to filter (default: [])

    Returns:
        ArxivConversionResult containing the markdown content and metadata

    Note:
        - Papers without LaTeX source cannot be converted
        - Large papers may take significant time to process
        - This uses the arxiv2md.org API service

    Example:
        convert_arxiv_to_markdown("https://arxiv.org/abs/1706.03762")
    """
    import httpx

    try:
        logger.info(f"Converting arXiv paper: {arxiv_url}")

        # Prepare API request
        api_url = "https://arxiv2md.org/api/ingest"
        payload = {
            "input_text": arxiv_url,
            "remove_refs": remove_refs,
            "remove_toc": remove_toc,
            "remove_inline_citations": remove_inline_citations,
            "section_filter_mode": section_filter_mode,
            "sections": sections
        }

        # Make async API request with timeout
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(api_url, json=payload)
            response.raise_for_status()
            result = response.json()

        logger.info(f"Successfully converted paper from {arxiv_url}")

        # Extract data from API response
        markdown = result.get("content", "")
        title = result.get("title")

        # Parse authors from summary if available
        summary = result.get("summary", "")
        authors = None
        if summary and "Authors:" in summary:
            # Extract authors line from summary
            for line in summary.split("\n"):
                if line.startswith("Authors:"):
                    authors_str = line.replace("Authors:", "").strip()
                    # Split by comma and clean up
                    authors = [a.strip() for a in authors_str.split(",")]
                    break

        # Abstract is not provided by this API
        abstract = None

        return ArxivConversionResult(
            markdown=markdown,
            title=title,
            authors=authors,
            abstract=abstract,
            url=arxiv_url
        )

    except httpx.HTTPStatusError as e:
        logger.error(f"API request failed with status {e.response.status_code}: {e}")
        raise RuntimeError(
            f"Failed to convert arXiv paper. API returned status {e.response.status_code}. "
            f"The paper may not have LaTeX source available or the API may be unavailable."
        ) from e
    except httpx.TimeoutException as e:
        logger.error(f"API request timed out: {e}")
        raise RuntimeError(
            "Conversion timed out. Large papers may take a while to process. "
            "Please try again or use a smaller paper."
        ) from e
    except Exception as e:
        logger.error(f"Error converting arXiv paper: {e}")
        raise RuntimeError(f"Failed to convert arXiv paper: {str(e)}") from e


@mcp.tool()
@rate_limited
async def extract_arxiv_id(arxiv_url: str) -> str:
    """
    Extract the arXiv ID from a given arXiv URL.

    This utility tool extracts the paper ID from various arXiv URL formats.

    Rate Limited: This tool is subject to a server-wide rate limit of 3 requests/second.

    Args:
        arxiv_url: An arXiv URL in any format

    Returns:
        The extracted arXiv ID (e.g., "1706.03762")

    Example:
        extract_arxiv_id("https://arxiv.org/abs/1706.03762") -> "1706.03762"
    """
    import re

    # Pattern to match arXiv IDs in various URL formats
    patterns = [
        r'arxiv\.org/abs/(\d+\.\d+)',
        r'arxiv\.org/pdf/(\d+\.\d+)',
        r'arxiv\.org/e-print/(\d+\.\d+)',
        r'(\d{4}\.\d{4,5})',  # Just the ID itself
    ]

    for pattern in patterns:
        match = re.search(pattern, arxiv_url)
        if match:
            return match.group(1)

    raise ValueError(f"Could not extract arXiv ID from URL: {arxiv_url}")


@mcp.tool()
@rate_limited
async def build_arxiv_urls(arxiv_id: str) -> dict[str, str]:
    """
    Build various arXiv URLs from a paper ID.

    Given an arXiv paper ID, this tool generates all common URL formats for the paper.

    Rate Limited: This tool is subject to a server-wide rate limit of 3 requests/second.

    Args:
        arxiv_id: The arXiv paper ID (e.g., "1706.03762")

    Returns:
        Dictionary containing different URL formats (abs, pdf, source)

    Example:
        build_arxiv_urls("1706.03762") -> {
            "abstract": "https://arxiv.org/abs/1706.03762",
            "pdf": "https://arxiv.org/pdf/1706.03762",
            "source": "https://arxiv.org/e-print/1706.03762"
        }
    """
    return {
        "abstract": f"https://arxiv.org/abs/{arxiv_id}",
        "pdf": f"https://arxiv.org/pdf/{arxiv_id}",
        "source": f"https://arxiv.org/e-print/{arxiv_id}",
    }


# ============================================================================
# arXiv Search Tools
# ============================================================================

_ARXIV_API_BASE = "http://export.arxiv.org/api/query"
_ARXIV_ATOM_NS = "http://www.w3.org/2005/Atom"
_TITLE_STOPWORDS = frozenset({
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or",
    "is", "are", "was", "were", "be", "been", "with", "from", "by", "as",
    "that", "this", "it", "its", "via", "using", "based", "towards", "toward",
})


def _parse_arxiv_entries(xml_text: str) -> list[dict]:
    """
    Parse arXiv Atom XML response into a list of paper metadata dicts.

    Args:
        xml_text: Raw Atom XML string from the arXiv API

    Returns:
        List of dicts with keys: id, title, authors, abstract, url, published, categories
    """
    import xml.etree.ElementTree as ET
    import re as _re

    ns = _ARXIV_ATOM_NS
    root = ET.fromstring(xml_text)
    papers = []

    for entry in root.findall(f"{{{ns}}}entry"):
        raw_id = entry.findtext(f"{{{ns}}}id", "")
        # Extract ID from full URL and strip version suffix (e.g. "2301.12345v2" -> "2301.12345")
        arxiv_id = _re.sub(r"v\d+$", "", raw_id.split("/abs/")[-1]) if "/abs/" in raw_id else raw_id

        title_elem = entry.find(f"{{{ns}}}title")
        title = " ".join((title_elem.text or "").split()) if title_elem is not None else ""

        summary_elem = entry.find(f"{{{ns}}}summary")
        abstract = " ".join((summary_elem.text or "").split()) if summary_elem is not None else ""

        published_elem = entry.find(f"{{{ns}}}published")
        published = (published_elem.text or "").strip() if published_elem is not None else ""

        authors = [
            " ".join((author.findtext(f"{{{ns}}}name", "") or "").split())
            for author in entry.findall(f"{{{ns}}}author")
        ]

        categories = [
            cat.get("term", "")
            for cat in entry.findall(f"{{{ns}}}category")
            if cat.get("term")
        ]

        papers.append({
            "id": arxiv_id,
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "url": f"https://arxiv.org/abs/{arxiv_id}",
            "published": published,
            "categories": categories,
        })

    return papers


@mcp.tool()
@rate_limited
async def search_arxiv(
    query: str,
    max_results: int = 10,
    category: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> list[dict]:
    """
    Search for arXiv papers by keyword, category, and date range.

    This tool queries the arXiv API to find papers matching the given search
    criteria. Results are returned in order of relevance.

    Rate Limited: This tool is subject to a server-wide rate limit of 3 requests/second.

    Args:
        query: Keyword search query (e.g., "attention mechanisms transformers")
        max_results: Maximum number of results to return (default: 10)
        category: arXiv category filter (e.g., "cs.AI", "physics.hep-th")
        date_from: Start date filter in YYYY-MM-DD format (e.g., "2023-01-01")
        date_to: End date filter in YYYY-MM-DD format (e.g., "2023-12-31")

    Returns:
        List of dicts with keys: id, title, authors, abstract, url, published, categories

    Example:
        search_arxiv("attention mechanisms", max_results=5, category="cs.AI")
    """
    import httpx

    try:
        logger.info(
            f"Searching arXiv: query={query!r}, category={category}, "
            f"date_from={date_from}, date_to={date_to}"
        )

        # Build search query string
        search_query = f"all:{query}"
        if category:
            search_query += f" AND cat:{category}"
        if date_from or date_to:
            from_str = date_from.replace("-", "") + "000000" if date_from else "00000000000000"
            to_str = date_to.replace("-", "") + "235959" if date_to else "99991231235959"
            search_query += f" AND submittedDate:[{from_str} TO {to_str}]"

        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": max_results,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(_ARXIV_API_BASE, params=params)
            response.raise_for_status()

        papers = _parse_arxiv_entries(response.text)
        logger.info(f"Found {len(papers)} papers for query {query!r}")
        return papers

    except httpx.HTTPStatusError as e:
        logger.error(f"arXiv API request failed with status {e.response.status_code}: {e}")
        raise RuntimeError(
            f"Failed to search arXiv. API returned status {e.response.status_code}."
        ) from e
    except httpx.TimeoutException as e:
        logger.error(f"arXiv API request timed out: {e}")
        raise RuntimeError("arXiv API request timed out. Please try again.") from e
    except Exception as e:
        logger.error(f"Error searching arXiv: {e}")
        raise RuntimeError(f"Failed to search arXiv: {str(e)}") from e


@mcp.tool()
@rate_limited
async def get_author_papers(
    author_name: str,
    max_results: int = 10,
) -> list[dict]:
    """
    Retrieve papers by a specific author from arXiv.

    This tool queries the arXiv API for papers authored by the given name.
    Results are returned in order of relevance/recency.

    Rate Limited: This tool is subject to a server-wide rate limit of 3 requests/second.

    Args:
        author_name: Full or partial author name (e.g., "Yoshua Bengio")
        max_results: Maximum number of results to return (default: 10)

    Returns:
        List of dicts with keys: id, title, authors, abstract, url, published, categories

    Example:
        get_author_papers("Yann LeCun", max_results=5)
    """
    import httpx

    try:
        logger.info(f"Fetching arXiv papers for author: {author_name!r}")

        params = {
            "search_query": f"au:{author_name}",
            "start": 0,
            "max_results": max_results,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(_ARXIV_API_BASE, params=params)
            response.raise_for_status()

        papers = _parse_arxiv_entries(response.text)
        logger.info(f"Found {len(papers)} papers for author {author_name!r}")
        return papers

    except httpx.HTTPStatusError as e:
        logger.error(f"arXiv API request failed with status {e.response.status_code}: {e}")
        raise RuntimeError(
            f"Failed to retrieve author papers. API returned status {e.response.status_code}."
        ) from e
    except httpx.TimeoutException as e:
        logger.error(f"arXiv API request timed out: {e}")
        raise RuntimeError("arXiv API request timed out. Please try again.") from e
    except Exception as e:
        logger.error(f"Error fetching author papers: {e}")
        raise RuntimeError(f"Failed to retrieve author papers: {str(e)}") from e


@mcp.tool()
@rate_limited
async def get_related_papers(
    arxiv_url: str,
    max_results: int = 10,
) -> list[dict]:
    """
    Find papers related to a given arXiv paper.

    This tool extracts the paper ID from the given URL, fetches its metadata
    (title and categories), then searches for related papers using title keywords
    and the paper's primary category.

    Rate Limited: This tool is subject to a server-wide rate limit of 3 requests/second.

    Args:
        arxiv_url: An arXiv URL (e.g., "https://arxiv.org/abs/1706.03762")
        max_results: Maximum number of related papers to return (default: 10)

    Returns:
        List of dicts with keys: id, title, authors, abstract, url, published, categories

    Example:
        get_related_papers("https://arxiv.org/abs/1706.03762", max_results=5)
    """
    import httpx
    import re as _re

    try:
        # Extract arXiv ID from URL using same patterns as extract_arxiv_id
        patterns = [
            r'arxiv\.org/abs/(\d+\.\d+)',
            r'arxiv\.org/pdf/(\d+\.\d+)',
            r'arxiv\.org/e-print/(\d+\.\d+)',
            r'(\d{4}\.\d{4,5})',
        ]
        arxiv_id = None
        for pattern in patterns:
            match = _re.search(pattern, arxiv_url)
            if match:
                arxiv_id = match.group(1)
                break

        if not arxiv_id:
            raise ValueError(f"Could not extract arXiv ID from URL: {arxiv_url}")

        logger.info(f"Fetching metadata for paper {arxiv_id} to find related papers")

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Fetch metadata for the source paper
            meta_response = await client.get(
                _ARXIV_API_BASE,
                params={"id_list": arxiv_id, "max_results": 1},
            )
            meta_response.raise_for_status()

        source_papers = _parse_arxiv_entries(meta_response.text)
        if not source_papers:
            raise RuntimeError(f"Could not retrieve metadata for arXiv paper {arxiv_id}")

        source = source_papers[0]
        title = source["title"]
        categories = source["categories"]

        # Extract meaningful keywords from title (skip stopwords and short words)
        keywords = [
            w for w in _re.sub(r"[^a-zA-Z0-9 ]", " ", title).lower().split()
            if len(w) > 3 and w not in _TITLE_STOPWORDS
        ][:5]

        if not keywords:
            raise RuntimeError(f"Could not extract keywords from title: {title!r}")

        # Build related search query from title keywords + primary category
        search_query = " AND ".join(f"ti:{kw}" for kw in keywords)
        if categories:
            search_query += f" AND cat:{categories[0]}"

        logger.info(f"Searching for related papers with query={search_query!r}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            search_response = await client.get(
                _ARXIV_API_BASE,
                params={"search_query": search_query, "start": 0, "max_results": max_results + 1},
            )
            search_response.raise_for_status()

        # Exclude the source paper from results
        related = [p for p in _parse_arxiv_entries(search_response.text) if p["id"] != arxiv_id]
        logger.info(f"Found {len(related)} related papers for {arxiv_id}")
        return related[:max_results]

    except httpx.HTTPStatusError as e:
        logger.error(f"arXiv API request failed with status {e.response.status_code}: {e}")
        raise RuntimeError(
            f"Failed to find related papers. API returned status {e.response.status_code}."
        ) from e
    except httpx.TimeoutException as e:
        logger.error(f"arXiv API request timed out: {e}")
        raise RuntimeError("arXiv API request timed out. Please try again.") from e
    except (ValueError, RuntimeError):
        raise
    except Exception as e:
        logger.error(f"Error finding related papers: {e}")
        raise RuntimeError(f"Failed to find related papers: {str(e)}") from e


def main():
    """Entry point for the MCP server"""
    mcp.run()


if __name__ == "__main__":
    main()
