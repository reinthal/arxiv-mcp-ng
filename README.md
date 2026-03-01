# arXiv MCP Server

A [FastMCP](https://github.com/jlowin/fastmcp) server that provides tools for converting arXiv academic papers to Markdown format using the [arxiv2md.org](https://arxiv2md.org) API.

**Key Features:**
- Convert arXiv papers from LaTeX to Markdown
- Extract arXiv IDs from URLs
- Generate arXiv URLs from paper IDs
- **Centralized rate limiting** (3 requests/second across all tools)

## Tools

This MCP server exposes the following tools (all subject to rate limiting):

### 1. `convert_arxiv_to_markdown`
Convert an arXiv paper to Markdown format by downloading and processing its LaTeX source.

**Parameters:**
- `arxiv_url` (string): The arXiv URL (e.g., `https://arxiv.org/abs/1706.03762`)

**Returns:**
- `markdown` (string): The converted markdown content
- `title` (string, optional): Paper title from metadata
- `authors` (list, optional): Paper authors from metadata
- `abstract` (string, optional): Paper abstract from metadata
- `url` (string): Original arXiv URL

### 2. `extract_arxiv_id`
Extract the arXiv paper ID from a URL.

**Parameters:**
- `arxiv_url` (string): An arXiv URL in any format

**Returns:**
- The extracted arXiv ID (e.g., `"1706.03762"`)

### 3. `build_arxiv_urls`
Generate various arXiv URLs from a paper ID.

**Parameters:**
- `arxiv_id` (string): The arXiv paper ID

**Returns:**
- Dictionary with `abstract`, `pdf`, and `source` URLs

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for fast, reliable Python package management.

**Install uv (if not already installed):**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Install project dependencies:**
```bash
uv sync
```

That's it! uv will automatically:
- Install the correct Python version (3.11)
- Create a virtual environment
- Install all dependencies including dev dependencies

## Usage

### Running the Server

**Development mode (with auto-reload and inspector):**
```bash
uv run fastmcp dev inspector server.py
```

This starts the server with:
- Auto-reload when you save changes
- MCP Inspector in your browser for interactive testing
- Better debugging output

**Production mode:**
```bash
uv run python server.py
```

**With make:**
```bash
make run
```

### Using with Claude Desktop

Add this server to your Claude Desktop configuration:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux: `~/.config/claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "arxiv": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/arxiv-mcp-ng",
        "arxiv-mcp-ng"
      ]
    }
  }
}
```

Replace `/absolute/path/to/arxiv-mcp-ng` with the actual path to this directory.

After updating the configuration, restart Claude Desktop for the changes to take effect.

### Using with MCP Client

A complete example client is provided in `example_client.py`. Run it to see the server in action:

```bash
python example_client.py
```

This will:
1. Connect to the MCP server
2. List all available tools
3. Convert the "Attention Is All You Need" paper to Markdown
4. Extract the arXiv ID from a URL
5. Build URLs from an arXiv ID

You can also use the FastMCP client programmatically:

```python
from fastmcp.client import Client
import asyncio

async def main():
    async with Client("python server.py") as client:
        # Convert a paper
        result = await client.call_tool(
            "convert_arxiv_to_markdown",
            {"arxiv_url": "https://arxiv.org/abs/1706.03762"}
        )

        paper_data = result.data
        with open("paper.md", "w") as f:
            f.write(paper_data['markdown'])

asyncio.run(main())
```

## Rate Limiting

This server implements **centralized rate limiting** to prevent overwhelming the arXiv servers and ensure fair usage:

- **Limit:** 3 requests per second across all tools
- **Scope:** Server-wide (applies to all tool invocations combined)
- **Implementation:** Uses a sliding window algorithm with async/await
- **Behavior:** When the limit is exceeded, requests are automatically queued and delayed

The rate limiting is transparent to clients - your requests will simply wait if necessary. You'll see log messages indicating when rate limiting is active:

```
Rate limit reached (3 requests/1.0s). Waiting 0.45 seconds...
```

All three tools (`convert_arxiv_to_markdown`, `extract_arxiv_id`, `build_arxiv_urls`) share the same rate limit pool, ensuring the server never exceeds 3 requests per second regardless of which tools are called.

## Limitations

Based on the arxiv2md.org API:

- Papers without LaTeX source cannot be converted (some older papers only have PDFs)
- Large papers may require significant processing time (up to 2 minutes)
- Requires internet connection to access the API

## Requirements

- Python >= 3.11
- fastmcp >= 3.0.0
- httpx >= 0.27.0
- pydantic >= 2.0.0

## License

MIT
