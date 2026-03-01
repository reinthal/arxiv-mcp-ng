#!/usr/bin/env python3
"""
FastMCP server for arxiv2md - Convert arXiv papers to Markdown format.

This server exposes tools to convert arXiv papers from LaTeX source to Markdown
using the arxiv2md package with centralized rate limiting (3 requests/second).
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
mcp = FastMCP("arxiv2md", dependencies=["arxiv2md", "tenacity"])


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
async def convert_arxiv_to_markdown(arxiv_url: str) -> ArxivConversionResult:
    """
    Convert an arXiv paper to Markdown format.

    This tool takes an arXiv URL (abstract page, PDF page, or source URL) and converts
    the paper's LaTeX source to Markdown format. The conversion uses latexml to process
    the LaTeX source.

    Rate Limited: This tool is subject to a server-wide rate limit of 3 requests/second.

    Args:
        arxiv_url: The arXiv URL (e.g., https://arxiv.org/abs/1706.03762)

    Returns:
        ArxivConversionResult containing the markdown content and metadata

    Note:
        - Papers without LaTeX source cannot be converted
        - Figures and tables are ignored in the conversion
        - Large papers may take significant time to process

    Example:
        convert_arxiv_to_markdown("https://arxiv.org/abs/1706.03762")
    """
    try:
        from arxiv2md import arxiv2md

        logger.info(f"Converting arXiv paper: {arxiv_url}")

        # Call arxiv2md to convert the paper
        # Run the blocking operation in a thread pool
        loop = asyncio.get_event_loop()
        markdown, metadata = await loop.run_in_executor(None, arxiv2md, arxiv_url)

        logger.info(f"Successfully converted paper from {arxiv_url}")

        # Extract metadata fields if available
        title = metadata.get("title") if metadata else None
        authors = metadata.get("authors") if metadata else None
        abstract = metadata.get("abstract") if metadata else None

        return ArxivConversionResult(
            markdown=markdown,
            title=title,
            authors=authors,
            abstract=abstract,
            url=arxiv_url
        )

    except ImportError as e:
        logger.error("arxiv2md package not installed")
        raise RuntimeError(
            "arxiv2md package is required. Install with: pip install arxiv2md\n"
            "Also ensure latexml is installed on your system:\n"
            "  macOS: brew install latexml\n"
            "  Ubuntu: sudo apt install latexml"
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
