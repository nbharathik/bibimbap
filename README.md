# BIM-CLI: Connect BIM tools to LLMs

A command-line interface for working with Claude and Model Context Protocol (MCP) servers.

## Quick Start

1. Clone or download the project
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. (Optional) Set up the project:
   ```bash
   python setup.py
   ```
4. Set your API key:
   ```bash
   export ANTHROPIC_API_KEY="your-anthropic-api-key"
   # For Windows PowerShell:
   $env:ANTHROPIC_API_KEY="your-anthropic-api-key"
   ```
5. Run the CLI:
   ```bash
   python bim-cli.py
   ```

## Basic Usage

Start the CLI:
```bash
python bim-cli.py
```

### Main Commands
- `help` - Show all available commands
- `status` - Show current configuration and server status
- `quit` or `exit` - Exit the CLI
- `clear` - Clear the screen
- `config` - Show config file location

### MCP Server Commands
- `mcp on` - Enable and connect to all enabled MCP servers
- `mcp off` - Disconnect all MCP servers
- `mcp status` - Show MCP server status (enabled, running, failed)
- `mcp list` - List all MCP servers with their status
- `mcp enable <server>` - Enable a specific server
- `mcp disable <server>` - Disable a specific server
- `mcp tools` - Show available tools
- `mcp add-server <file>` - Add a new MCP server from a JSON file
- `mcp remove-server <name>` - Remove an MCP server by name
- `mcp add-servers-dir <dir_path>` - Add all MCP servers from JSON files in a directory

## Configuration

All configuration is in `configs/config.json` in the project root. Example:
```json
{
  "version": "1.0.0",
  "claude": {
    "model": "claude-3-5-sonnet-20241022",
    "temperature": 0.1,
    "max_tokens": 4096
  },
  "mcp_servers": {
    "filesystem": {
      "name": "filesystem",
      "enabled": true,
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
      "description": "File system access"
    },
    "math": {
      "name": "math",
      "enabled": true,
      "transport": "stdio",
      "command": "python",
      "args": ["servers/math_server.py"],
      "description": "Math operations"
    }
  },
  "ui": {
    "show_tools": true,
    "show_timing": true,
    "colored_output": true,
    "prompt_prefix": "BIM-CLI"
  }
}
```
Copy `configs/.env.example` to `configs/.env` and fill in your API keys.