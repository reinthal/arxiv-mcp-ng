#!/usr/bin/env python3
"""
Example client demonstrating how to use the arXiv MCP server.

This script shows how to connect to the MCP server and use its tools
to convert arXiv papers to Markdown format.
"""

import asyncio
from fastmcp.client import Client


async def main():
    """Example usage of the arXiv MCP server"""

    # Connect to the server (running as a subprocess)
    async with Client("python server.py") as client:
        print("Connected to arXiv MCP server\n")

        # List available tools
        print("Available tools:")
        tools = await client.list_tools()
        for tool in tools:
            print(f"  - {tool.name}: {tool.description}")
        print()

        # Example 1: Convert a famous paper (Attention Is All You Need)
        print("Example 1: Converting 'Attention Is All You Need' paper")
        print("-" * 60)

        arxiv_url = "https://arxiv.org/abs/1706.03762"
        print(f"Converting: {arxiv_url}")

        result = await client.call_tool(
            "convert_arxiv_to_markdown",
            {"arxiv_url": arxiv_url}
        )

        paper_data = result.data
        print(f"\nTitle: {paper_data.get('title', 'N/A')}")
        print(f"Authors: {', '.join(paper_data.get('authors', []) or ['N/A'])}")
        print(f"Markdown length: {len(paper_data['markdown'])} characters")

        # Save to file
        output_file = "attention_is_all_you_need.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(paper_data['markdown'])
        print(f"Saved to: {output_file}")

        print("\n" + "=" * 60 + "\n")

        # Example 2: Extract arXiv ID from URL
        print("Example 2: Extracting arXiv ID from URL")
        print("-" * 60)

        result = await client.call_tool(
            "extract_arxiv_id",
            {"arxiv_url": arxiv_url}
        )
        arxiv_id = result.data
        print(f"Extracted ID: {arxiv_id}")

        print("\n" + "=" * 60 + "\n")

        # Example 3: Build URLs from ID
        print("Example 3: Building URLs from arXiv ID")
        print("-" * 60)

        result = await client.call_tool(
            "build_arxiv_urls",
            {"arxiv_id": arxiv_id}
        )
        urls = result.data
        print("Generated URLs:")
        for url_type, url in urls.items():
            print(f"  {url_type}: {url}")


if __name__ == "__main__":
    print("arXiv MCP Server - Example Client")
    print("=" * 60)
    print()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        raise
