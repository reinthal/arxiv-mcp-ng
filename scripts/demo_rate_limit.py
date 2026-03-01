#!/usr/bin/env python3
"""
Demonstration of the rate limiting feature in the arXiv MCP server.

This script makes rapid consecutive requests to show how the server
automatically throttles requests to 3 per second.
"""

import asyncio
import time
from fastmcp.client import Client


async def main():
    """Demonstrate rate limiting with rapid requests"""

    print("arXiv MCP Server - Rate Limiting Demo")
    print("=" * 60)
    print()
    print("This demo will make 7 rapid requests to the server.")
    print("You should see:")
    print("  - First 3 requests complete immediately")
    print("  - Requests 4-6 delayed by ~1 second")
    print("  - Request 7 delayed by ~2 seconds")
    print()
    print("-" * 60)
    print()

    async with Client("python server.py") as client:
        test_urls = [
            "https://arxiv.org/abs/1706.03762",
            "https://arxiv.org/abs/2103.14899",
            "https://arxiv.org/abs/1234.56789",
            "https://arxiv.org/abs/2203.12345",
            "https://arxiv.org/abs/1912.54321",
            "https://arxiv.org/abs/2105.98765",
            "https://arxiv.org/abs/1803.24680",
        ]

        start_time = time.time()

        # Make requests sequentially to clearly show the rate limiting
        for i, url in enumerate(test_urls, 1):
            request_start = time.time()

            try:
                # Use extract_arxiv_id as it's fast and doesn't require actual conversion
                result = await client.call_tool("extract_arxiv_id", {"arxiv_url": url})

                elapsed = time.time() - request_start
                total_elapsed = time.time() - start_time

                print(
                    f"Request {i:2d}: {result.data:13s} | "
                    f"Request time: {elapsed:5.2f}s | "
                    f"Total elapsed: {total_elapsed:5.2f}s"
                )

            except Exception as e:
                print(f"Request {i:2d}: Error - {e}")

    print()
    print("-" * 60)
    print()
    print("Demo complete!")
    print()
    print("Notice how:")
    print("  • Requests 1-3 completed in ~0.00s (immediate)")
    print("  • Requests 4-6 waited ~1 second (rate limit kicked in)")
    print("  • Request 7 waited ~2 seconds (still throttled)")
    print()
    print("This ensures the server never exceeds 3 requests/second,")
    print("protecting both the server and the arXiv infrastructure.")


async def demo_parallel_requests():
    """Demonstrate rate limiting with parallel requests"""

    print("\n" + "=" * 60)
    print("Parallel Requests Demo")
    print("=" * 60)
    print()
    print("Making 5 parallel requests simultaneously...")
    print()

    async with Client("python server.py") as client:
        test_urls = [
            "https://arxiv.org/abs/1706.03762",
            "https://arxiv.org/abs/2103.14899",
            "https://arxiv.org/abs/1234.56789",
            "https://arxiv.org/abs/2203.12345",
            "https://arxiv.org/abs/1912.54321",
        ]

        async def make_request(url: str, request_num: int):
            """Make a single request and track timing"""
            start = time.time()
            result = await client.call_tool("extract_arxiv_id", {"arxiv_url": url})
            elapsed = time.time() - start
            return request_num, result.data, elapsed

        # Launch all requests in parallel
        start_time = time.time()
        results = await asyncio.gather(
            *[make_request(url, i + 1) for i, url in enumerate(test_urls)]
        )
        total_time = time.time() - start_time

        # Sort by request number and display
        for req_num, arxiv_id, elapsed in sorted(results):
            print(f"Request {req_num}: {arxiv_id:13s} | Completed at: {elapsed:5.2f}s")

        print()
        print(f"Total time: {total_time:.2f}s")
        print()
        print("Notice that even though all requests were launched together,")
        print("the rate limiter queued them to maintain 3 requests/second.")


if __name__ == "__main__":
    print()
    try:
        asyncio.run(main())
        asyncio.run(demo_parallel_requests())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        raise
    print()
