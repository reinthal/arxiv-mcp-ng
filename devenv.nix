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
      doCheck = false; # Skip tests that are failing
    }))
  ];

  languages.python = {
    enable = true;
    version = "3.11";
    uv.enable = true;
  };

  scripts.menu.exec = ''
    echo ""
    echo "╭──────────────────────────────────────────────────────────────╮"
    echo "│                                                              │"
    echo "│              📚 arXiv MCP Server - Commands                  │"
    echo "│                                                              │"
    echo "╰──────────────────────────────────────────────────────────────╯"
    echo ""
    echo "🔧 Setup:"
    echo "  install       Install dependencies with uv sync"
    echo ""
    echo "🚀 Running:"
    echo "  run           Start MCP server (production mode)"
    echo "  dev           Start MCP server (dev mode with inspector)"
    echo ""
    echo "🧪 Testing:"
    echo "  test          Run tests with pytest"
    echo "  example       Run example client (converts a paper)"
    echo "  demo          Demonstrate rate limiting in action"
    echo ""
    echo "📋 Other:"
    echo "  menu          Show this menu"
    echo ""
    echo "💡 Tip: Run 'install' first if you haven't set up dependencies yet"
    echo ""
  '';

  scripts.install.exec = ''
    uv sync
  '';

  scripts.run.exec = ''
    uv run python server.py
  '';

  scripts.dev.exec = ''
    uv run fastmcp dev inspector server.py
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
    echo ""
    echo "╭──────────────────────────────────────────────────────────────╮"
    echo "│                                                              │"
    echo "│       🚀 arXiv MCP Server Development Environment            │"
    echo "│                                                              │"
    echo "╰──────────────────────────────────────────────────────────────╯"
    echo ""
    echo "Tools installed:"
    echo "  Python:  $(python --version | cut -d' ' -f2)"
    echo "  uv:      $(uv --version | cut -d' ' -f2)"
    echo "  LaTeXML: $(latexml --VERSION 2>&1 | head -1)"
    echo ""
    echo "📋 Type 'menu' to see all available commands"
    echo ""
  '';

  enterTest = ''
    echo "Running tests"
    git --version | grep --color=auto "${pkgs.git.version}"
  '';
}
