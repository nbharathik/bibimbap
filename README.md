# BIM-CLI: Connect BIM tools to LLMs

A flexible, extensible command-line interface for working with Claude and Model Context Protocol (MCP) servers.

## Features

- Easy to Use: Start with `python bim-cli.py`
- Flexible Configuration: All MCP servers are managed in a single JSON config file
- Hot-Pluggable MCP Integration: Add or remove MCP servers at runtime, or load all from a directory
- Interactive Shell: Tab-completion for commands and server names using prompt_toolkit
- Clear Error Messages: See full command and environment if a server fails to start
- Server Status: Check if each MCP server is enabled, running, or failed
- Multiple Agent Types: Tool Calling and React agents
- Colorful, Human-Friendly CLI Output

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

### Agent Commands
- `agent react` - Use React agent
- `agent tool` - Use Tool Calling agent
- `agent status` - Show current agent type

### Example Session
```
BIM-CLI> mcp on
Setting up MCP servers...
MCP servers connected successfully!
Total tools available: 8

BIM-CLI> mcp list
MCP Servers:
  filesystem: Enabled | Status: running - File system access
  math: Enabled | Status: running - Math operations
  web_search: Disabled | Status: unknown - Web search

BIM-CLI> mcp add-server servers/my_custom_server.json
Added server 'my_custom_server' from servers/my_custom_server.json

BIM-CLI> mcp add-servers-dir mcp_servers/
Added server 'foo' from mcp_servers/foo.json
Added server 'bar' from mcp_servers/bar.json
Total servers added from directory: 2

BIM-CLI> mcp status
MCP Status:
   Enabled: True
   Active Servers: 3
   Available Tools: 8

BIM-CLI> What is the capital of France?
Response:
The capital of France is Paris.
```

## Configuration

All configuration is in `bim-config.json` in the project root. Example:
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
    // ... more servers ...
  },
  "ui": {
    "show_tools": true,
    "show_timing": true,
    "colored_output": true,
    "prompt_prefix": "BIM-CLI"
  }
}
```

- To add a new server, use `mcp add-server <file>` or add it manually to the config.
- To remove, use `mcp remove-server <name>`.
- To bulk add, use `mcp add-servers-dir <dir_path>`.

## Advanced Features

- **Environment Variables:**
  Set `env_vars` in your server config to pass environment variables to the server process.
- **Custom Headers:**
  For HTTP servers, set `headers` in the config.
- **Error Reporting:**
  If a server fails to start, the CLI will show the full command, arguments, and environment used.
- **Tab Completion:**
  The CLI uses prompt_toolkit for interactive tab-completion of commands and server names.
- **Server Status:**
  See if each server is enabled, running, or failed with `mcp list` or `status`.

## Project Structure

```
bim-cli/
├── bim-cli.py              # Main CLI application
├── setup.py                # Setup script
├── requirements.txt        # Python dependencies
├── bim-config.json         # Configuration file (auto-generated)
├── servers/                # Example MCP servers
│   ├── math_server.py      # Math operations
│   └── web_search_server.py # Web search
├── mcp_servers/            # (Optional) Directory for plug-and-play server configs
└── configs/                # Example configurations
```

## Troubleshooting

- If a server fails to start, check the printed command, arguments, and environment.
- Make sure all dependencies are installed:
  ```bash
  pip install -r requirements.txt
  ```
- For Node.js MCP servers:
  ```bash
  npm install -g @modelcontextprotocol/server-filesystem
  ```
- If you see API key errors:
  ```bash
  export ANTHROPIC_API_KEY="your-key-here"
  ```

## License

MIT License - use, share, and modify as you like.

---

For more about MCP servers, visit: https://modelcontextprotocol.io/