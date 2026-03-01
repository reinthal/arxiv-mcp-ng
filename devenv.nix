{
  pkgs,
  lib,
  config,
  inputs,
  ...
}: {
  packages = [
    pkgs.git
    (pkgs.perl5Packages.LaTeXML.overrideAttrs (oldAttrs: {
      doCheck = false;  # Skip tests that are failing
    }))
  ];

  languages.python = {
    enable = true;
    version = "3.11";
    uv.enable = true;
  };

  scripts.install.exec = ''
    uv sync
  '';

  scripts.run-server.exec = ''
    uv run python server.py
  '';

  scripts.run.exec = ''
    uv run arxiv-mcp
  '';

  scripts.test.exec = ''
    uv run pytest -v
  '';

  scripts.demo.exec = ''
    uv run python demo_rate_limit.py
  '';

  scripts.example.exec = ''
    uv run python example_client.py
  '';

  enterShell = ''
    echo "arXiv MCP Server Development Environment"
    echo "========================================"
    echo ""
    echo "First time setup:"
    echo "  install       - Install dependencies with uv"
    echo ""
    echo "Available commands:"
    echo "  run           - Start the MCP server (via entry point)"
    echo "  run-server    - Start the MCP server (via python)"
    echo "  test          - Run tests with pytest"
    echo "  demo          - Run rate limiting demo"
    echo "  example       - Run example client"
    echo ""
    echo "Tools:"
    python --version
    uv --version
    latexml --version | head -n 1
    echo ""
    echo "Run 'install' to set up dependencies if not done yet"
  '';

  enterTest = ''
    echo "Running tests"
    git --version | grep --color=auto "${pkgs.git.version}"
  '';
}
