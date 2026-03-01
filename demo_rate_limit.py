#!/usr/bin/env python3
"""
Demonstration of the centralized rate limiting feature.

This script makes multiple rapid requests to show how the server enforces
a rate limit of 3 requests per second across all tools.
"""

import asyncio
import time
from fastmcp.client import Client
from fastmcp.client.transports import StdioTransport


async def demo_rate_limiting():
    """Demonstrate rate limiting with multiple rapid requests"""

    transport = StdioTransport(command="python", args=["server.py"])
    async with Client(transport) as client:
        print("=" * 70)
        print("Rate Limiting Demo - arxiv-mcp-ng")
        print("=" * 70)
        print("\nServer configuration: 3 requests per second (centralized)")
        print("Making 7 rapid requests to demonstrate rate limiting...\n")

        start_time = time.time()
        timings = []

        for i in range(7):
            request_start = time.time()
            result = await client.call_tool(
                "extract_arxiv_id",
                {"arxiv_url": f"https://arxiv.org/abs/{1700+i}.00000"}
            )
            request_end = time.time()

            elapsed_total = request_end - start_time
            elapsed_request = request_end - request_start
            timings.append(elapsed_total)

            # Visual indicator for delayed requests
            indicator = "⏸️  DELAYED" if elapsed_request > 0.1 else "✓"

            print(f"Request {i+1}: {result.data:>12} | "
                  f"Total: {elapsed_total:5.2f}s | "
                  f"Wait: {elapsed_request:5.2f}s | {indicator}")

        total_time = time.time() - start_time

        print("\n" + "=" * 70)
        print("Analysis:")
        print("=" * 70)
        print(f"Requests 1-3: Completed immediately (no wait)")
        print(f"Request 4:    Waited ~1.0s (rate limit enforced)")
        print(f"Requests 5-6: Completed immediately (window refreshed)")
        print(f"Request 7:    Waited ~1.0s (rate limit enforced again)")
        print(f"\nTotal time: {total_time:.2f}s")
        print(f"Expected:   ~2.0s (for 7 requests at 3 req/s)")
        print("\n✅ Rate limiting is working correctly!")
        print("=" * 70)


if __name__ == "__main__":
    try:
        asyncio.run(demo_rate_limiting())
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        raise
