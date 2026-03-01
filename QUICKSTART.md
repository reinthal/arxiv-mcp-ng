# Quick Start Guide

Get started with the arXiv MCP server in just a few minutes!

## Prerequisites

1. **Install uv** (Python package manager):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Install latexml** (required for converting LaTeX to Markdown):

   **macOS:**
   ```bash
   brew install latexml
   ```

   **Ubuntu/Debian:**
   ```bash
   sudo apt update && sudo apt install latexml
   ```

## Setup

### Using uv (2 commands!)

```bash
# 1. Install dependencies (uv handles Python version, venv, everything)
uv sync

# 2. Run the example
uv run python example_client.py
```

That's it! uv automatically:
- Downloads and installs Python 3.11
- Creates a virtual environment
- Installs all dependencies (including dev dependencies)

## Testing the Server

### 1. Run the Example Client

```bash
uv run python example_client.py
# or use the shortcut
make example
```

This will convert the "Attention Is All You Need" paper and save it to `attention_is_all_you_need.md`.

### 2. Run Unit Tests

```bash
uv run pytest -v
# or
make test
```

### 3. Demo Rate Limiting

```bash
uv run python demo_rate_limit.py
```

This demonstrates the 3 requests/second rate limit in action.

### 4. Start the Server Manually

**Development mode (with auto-reload and inspector):**
```bash
uv run fastmcp dev inspector server.py
```

This opens the MCP Inspector in your browser for interactive testing.

**Production mode:**
```bash
uv run python server.py
# or
make run
```

The server will start and wait for MCP client connections.

## Using with Claude Desktop

1. **Find your Claude Desktop config file:**
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Linux: `~/.config/claude/claude_desktop_config.json`

2. **Edit the config file** (create it if it doesn't exist):

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

3. **Restart Claude Desktop**

4. **Test it** by asking Claude:
   - "Convert the paper at https://arxiv.org/abs/1706.03762 to markdown"
   - "What's the arXiv ID from this URL: https://arxiv.org/pdf/2103.14899.pdf"

## Example Usage

Once the server is configured with Claude Desktop, you can:

```
Convert the "Attention Is All You Need" paper to markdown:
https://arxiv.org/abs/1706.03762
```

Claude will use the `convert_arxiv_to_markdown` tool and return the paper in Markdown format with metadata.

## Troubleshooting

### "arxiv2md package not installed"

Make sure you've installed the dependencies:
```bash
uv sync
```

### "latexml: command not found"

Install latexml for your system (see Prerequisites above).

### Server doesn't appear in Claude Desktop

1. Check that the path in `claude_desktop_config.json` is absolute and correct
2. Restart Claude Desktop after making changes
3. Check Claude Desktop logs for errors

### Conversion takes a long time

Large papers can take several minutes to convert. The server is working - just be patient!

## Quick Command Reference

All available commands (using uv):

```bash
# Setup
uv sync              # Install/update dependencies

# Running
uv run python server.py                    # Start the MCP server
uv run fastmcp dev inspector server.py     # Dev mode with inspector
make run                                   # Same as production mode

# Testing
uv run pytest -v     # Run tests
make test            # Same as above

# Examples
uv run python example_client.py      # Run example client
uv run python demo_rate_limit.py     # Demo rate limiting
make example         # Run example client
make demo            # Demo rate limiting

# Code quality
make lint            # Lint code with ruff
make format          # Format code with ruff
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Explore the `example_client.py` to see all available tools
- Check out the `server.py` source to understand how it works
- Contribute improvements via pull requests!

## Support

If you encounter issues:
1. Check the [Limitations](README.md#limitations) section in the README
2. Ensure latexml is properly installed
3. Verify the arXiv paper has LaTeX source available (not all do)
