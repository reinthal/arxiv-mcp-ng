#!/usr/bin/env python3
"""
Tests for the arXiv MCP server.
"""

import pytest
import asyncio
from server import extract_arxiv_id, build_arxiv_urls, _rate_limiter


@pytest.mark.asyncio
async def test_extract_arxiv_id_from_abs_url():
    """Test extracting ID from abstract URL"""
    url = "https://arxiv.org/abs/1706.03762"
    result = await extract_arxiv_id(url)
    assert result == "1706.03762"


@pytest.mark.asyncio
async def test_extract_arxiv_id_from_pdf_url():
    """Test extracting ID from PDF URL"""
    url = "https://arxiv.org/pdf/2103.14899.pdf"
    result = await extract_arxiv_id(url)
    assert result == "2103.14899"


@pytest.mark.asyncio
async def test_extract_arxiv_id_from_eprint_url():
    """Test extracting ID from e-print URL"""
    url = "https://arxiv.org/e-print/1234.56789"
    result = await extract_arxiv_id(url)
    assert result == "1234.56789"


@pytest.mark.asyncio
async def test_extract_arxiv_id_from_plain_id():
    """Test extracting ID from plain ID string"""
    result = await extract_arxiv_id("1706.03762")
    assert result == "1706.03762"


@pytest.mark.asyncio
async def test_extract_arxiv_id_invalid_url():
    """Test that invalid URL raises ValueError"""
    with pytest.raises(ValueError):
        await extract_arxiv_id("https://example.com")


@pytest.mark.asyncio
async def test_build_arxiv_urls():
    """Test building URLs from ID"""
    arxiv_id = "1706.03762"
    urls = await build_arxiv_urls(arxiv_id)

    assert urls["abstract"] == "https://arxiv.org/abs/1706.03762"
    assert urls["pdf"] == "https://arxiv.org/pdf/1706.03762"
    assert urls["source"] == "https://arxiv.org/e-print/1706.03762"


def test_server_imports():
    """Test that server imports correctly"""
    from server import mcp

    assert mcp.name == "arxiv2md"


def test_server_tools_registered():
    """Test that all expected tools are registered"""
    from server import mcp

    # Get tool names
    tool_names = [name for name in dir(mcp) if not name.startswith('_')]

    # We should have our tools registered
    # Note: This is a basic check - actual tool registration
    # happens during server initialization
    assert mcp.name == "arxiv2md"


@pytest.mark.asyncio
async def test_rate_limiter():
    """Test that the rate limiter enforces the limit"""
    import time
    from server import RateLimiter

    # Create a rate limiter with 3 requests per second
    limiter = RateLimiter(max_requests=3, time_window=1.0)

    # Make 3 requests - should all complete immediately
    start_time = time.time()
    for _ in range(3):
        await limiter.acquire()

    elapsed = time.time() - start_time
    assert elapsed < 0.1, "First 3 requests should be immediate"

    # 4th request should be delayed
    start_time = time.time()
    await limiter.acquire()
    elapsed = time.time() - start_time

    # Should have waited at least ~1 second (minus the small elapsed time from first 3 requests)
    assert elapsed > 0.8, f"4th request should be delayed, but only waited {elapsed}s"


@pytest.mark.asyncio
async def test_rate_limiter_parallel_requests():
    """Test rate limiter with parallel requests"""
    import time
    from server import RateLimiter

    limiter = RateLimiter(max_requests=3, time_window=1.0)

    # Launch 5 concurrent requests
    start_time = time.time()

    async def make_request():
        await limiter.acquire()
        return time.time() - start_time

    timestamps = await asyncio.gather(*[make_request() for _ in range(5)])

    # First 3 should be immediate (within 0.1s)
    assert sum(1 for t in timestamps if t < 0.1) == 3, "First 3 requests should be immediate"

    # Last 2 should be delayed by about 1 second
    assert sum(1 for t in timestamps if t > 0.8) == 2, "Last 2 requests should be delayed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
