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


def main():
    """Entry point for the MCP server"""
    mcp.run()


if __name__ == "__main__":
    main()
