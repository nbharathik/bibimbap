#!/usr/bin/env python3
"""
BIM-CLI: Build, Integrate, MCP - Command Line Interface
A flexible CLI for working with Claude and MCP servers

Usage: python bim-cli.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
import argparse
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.completion import Completer, Completion

# Required imports
try:
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    from langchain.agents import create_tool_calling_agent, AgentExecutor
    from langchain.prompts import ChatPromptTemplate
    from langgraph.prebuilt import create_react_agent
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langchain_mcp_adapters.tools import load_mcp_tools
    import colorama
    from colorama import Fore, Style, Back
    colorama.init()
except ImportError as e:
    print(f"Missing dependencies: {e}")
    print("Install with: pip install langchain-anthropic langchain langgraph langchain-mcp-adapters colorama")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

@dataclass
class MCPServerConfig:
    """Configuration for MCP server"""
    name: str
    enabled: bool = True
    transport: str = "stdio"  # stdio, streamable_http
    command: Optional[str] = None
    args: Optional[List[str]] = None
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    env_vars: Optional[Dict[str, str]] = None
    description: Optional[str] = None

class BIMConfig:
    """Configuration manager for BIM-CLI"""
    
    def __init__(self, config_file: str = "bim-config.json"):
        self.config_file = Path(config_file)
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        if not self.config_file.exists():
            return self.create_default_config()
        
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return self.create_default_config()
    
    def create_default_config(self) -> Dict[str, Any]:
        """Create default configuration"""
        default_config = {
            "version": "1.0.0",
            "claude": {
                "model": "claude-3-5-sonnet-20241022",
                "temperature": 0.1,
                "max_tokens": 4096
            },
            "mcp_servers": {
                "filesystem": {
                    "name": "filesystem",
                    "enabled": True,
                    "transport": "stdio",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
                    "description": "File system access for current directory"
                },
                "math": {
                    "name": "math",
                    "enabled": False,
                    "transport": "stdio",
                    "command": "python",
                    "args": ["servers/math_server.py"],
                    "description": "Mathematical calculations"
                },
                "sqlite": {
                    "name": "sqlite",
                    "enabled": False,
                    "transport": "stdio",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-sqlite", "--db-path", "database.db"],
                    "description": "SQLite database access"
                },
                "web_search": {
                    "name": "web_search",
                    "enabled": False,
                    "transport": "stdio",
                    "command": "python",
                    "args": ["servers/web_search_server.py"],
                    "env_vars": {"SEARCH_API_KEY": "your-search-api-key"},
                    "description": "Web search capabilities"
                },
                "custom_http": {
                    "name": "custom_http",
                    "enabled": False,
                    "transport": "streamable_http",
                    "url": "http://localhost:8000/mcp/",
                    "headers": {"Authorization": "Bearer your-token"},
                    "description": "Custom HTTP MCP server"
                }
            },
            "ui": {
                "show_tools": True,
                "show_timing": True,
                "colored_output": True,
                "prompt_prefix": "BIM-CLI"
            }
        }
        
        self.save_config(default_config)
        return default_config
    
    def save_config(self, config: Dict[str, Any] = None):
        """Save configuration to file"""
        if config is None:
            config = self.config
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get_enabled_servers(self) -> List[MCPServerConfig]:
        """Get list of enabled MCP servers"""
        servers = []
        for server_name, server_config in self.config["mcp_servers"].items():
            if server_config.get("enabled", False):
                servers.append(MCPServerConfig(**server_config))
        return servers
    
    def enable_server(self, server_name: str):
        """Enable an MCP server"""
        if server_name in self.config["mcp_servers"]:
            self.config["mcp_servers"][server_name]["enabled"] = True
            self.save_config()
            return True
        return False
    
    def disable_server(self, server_name: str):
        """Disable an MCP server"""
        if server_name in self.config["mcp_servers"]:
            self.config["mcp_servers"][server_name]["enabled"] = False
            self.save_config()
            return True
        return False
    
    def add_server(self, server_config: MCPServerConfig):
        """Add a new MCP server configuration"""
        self.config["mcp_servers"][server_config.name] = asdict(server_config)
        self.save_config()
    
    def add_server_from_file(self, file_path: str):
        """Add a new MCP server from a JSON file"""
        try:
            with open(file_path, 'r') as f:
                server_config = json.load(f)
            if 'name' not in server_config:
                print("Server config must have a 'name' field.")
                return False
            self.config["mcp_servers"][server_config['name']] = server_config
            self.save_config()
            print(f"Added server '{server_config['name']}' from {file_path}")
            return True
        except Exception as e:
            print(f"Error adding server from file: {e}")
            return False

    def remove_server(self, server_name: str):
        """Remove an MCP server by name"""
        if server_name in self.config["mcp_servers"]:
            del self.config["mcp_servers"][server_name]
            self.save_config()
            print(f"Removed server '{server_name}'")
            return True
        print(f"Server '{server_name}' not found.")
        return False

    def add_servers_from_directory(self, dir_path: str):
        """Add all MCP servers from JSON files in a directory"""
        dir_path = Path(dir_path)
        if not dir_path.is_dir():
            print(f"Directory '{dir_path}' not found.")
            return False
        added = 0
        for file in dir_path.glob('*.json'):
            try:
                with open(file, 'r') as f:
                    server_config = json.load(f)
                if 'name' not in server_config:
                    print(f"File {file} missing 'name' field, skipping.")
                    continue
                self.config["mcp_servers"][server_config['name']] = server_config
                added += 1
                print(f"Added server '{server_config['name']}' from {file}")
            except Exception as e:
                print(f"Error adding server from {file}: {e}")
        self.save_config()
        print(f"Total servers added from directory: {added}")
        return added > 0

class BIMCore:
    """Core BIM-CLI functionality"""
    
    def __init__(self, config: BIMConfig):
        self.config = config
        self.claude = None
        self.mcp_client = None
        self.tools = []
        self.agent = None
        self.initialize_claude()
    
    def initialize_claude(self):
        """Initialize Claude model"""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print(f"{Fore.RED}ANTHROPIC_API_KEY environment variable not set{Style.RESET_ALL}")
            sys.exit(1)
        
        claude_config = self.config.config["claude"]
        self.claude = ChatAnthropic(
            anthropic_api_key=api_key,
            model_name=claude_config["model"],
            temperature=claude_config["temperature"],
            max_tokens=claude_config["max_tokens"]
        )
        
        print(f"{Fore.GREEN}Claude initialized: {claude_config['model']}{Style.RESET_ALL}")
    
    async def setup_mcp_servers(self) -> bool:
        """Setup enabled MCP servers"""
        enabled_servers = self.config.get_enabled_servers()
        if not enabled_servers:
            print("No MCP servers enabled.")
            return False
        print("Setting up MCP servers...")
        client_config = {}
        for server in enabled_servers:
            print(f"  Configuring {server.name}...")
            server_config = {}
            if server.transport == "stdio":
                server_config = {
                    "command": server.command,
                    "args": server.args or [],
                    "transport": "stdio"
                }
                if server.env_vars:
                    server_config["env_vars"] = server.env_vars
            elif server.transport == "streamable_http":
                server_config = {
                    "url": server.url,
                    "transport": "streamable_http"
                }
                if server.headers:
                    server_config["headers"] = server.headers
            client_config[server.name] = server_config
        try:
            self.mcp_client = MultiServerMCPClient(client_config)
            self.tools = await self.mcp_client.get_tools()
            print("MCP servers connected successfully!")
            print(f"Total tools available: {len(self.tools)}")
            if self.config.config["ui"]["show_tools"]:
                self.show_available_tools()
            return True
        except Exception as e:
            print("Failed to setup MCP servers:")
            for name, cfg in client_config.items():
                print(f"  Server: {name}")
                if 'command' in cfg:
                    print(f"    Command: {cfg['command']} {' '.join(cfg.get('args', []))}")
                    if 'env_vars' in cfg:
                        print(f"    Env: {cfg['env_vars']}")
                if 'url' in cfg:
                    print(f"    URL: {cfg['url']}")
                if 'headers' in cfg:
                    print(f"    Headers: {cfg['headers']}")
            print(f"  Error: {e}")
            return False
    
    def show_available_tools(self):
        """Display available tools"""
        if not self.tools:
            return
        
        print(f"\n{Fore.CYAN}Available Tools:{Style.RESET_ALL}")
        for i, tool in enumerate(self.tools, 1):
            print(f"   {i}. {Fore.YELLOW}{tool.name}{Style.RESET_ALL}: {tool.description}")
    
    async def run_direct_claude(self, query: str) -> str:
        """Run query with direct Claude (no MCP)"""
        start_time = datetime.now()
        
        try:
            response = await self.claude.ainvoke([HumanMessage(content=query)])
            
            if self.config.config["ui"]["show_timing"]:
                elapsed = (datetime.now() - start_time).total_seconds()
                print(f"{Fore.MAGENTA} Response time: {elapsed:.2f}s{Style.RESET_ALL}")
            
            return response.content
            
        except Exception as e:
            return f"Error: {e}"
    
    async def run_with_mcp(self, query: str, use_react: bool = False) -> str:
        """Run query with MCP tools"""
        if not self.tools:
            return await self.run_direct_claude(query)
        
        start_time = datetime.now()
        
        try:
            if use_react:
                # Use React agent
                agent = create_react_agent(
                    self.claude,
                    self.tools,
                    system_message="You are a helpful assistant with access to various tools through MCP servers. Use them when appropriate to provide accurate and helpful responses."
                )
                
                result = await agent.ainvoke({"messages": [HumanMessage(content=query)]})
                response = result["messages"][-1].content
                
            else:
                # Use tool calling agent
                prompt = ChatPromptTemplate.from_messages([
                    ("system", "You are a helpful assistant with access to various tools through MCP servers. Use them when appropriate to provide accurate and helpful responses."),
                    ("placeholder", "{chat_history}"),
                    ("human", "{input}"),
                    ("placeholder", "{agent_scratchpad}"),
                ])
                
                agent = create_tool_calling_agent(self.claude, self.tools, prompt)
                agent_executor = AgentExecutor(
                    agent=agent,
                    tools=self.tools,
                    verbose=False,
                    handle_parsing_errors=True
                )
                
                result = await agent_executor.ainvoke({"input": query})
                response = result["output"]
            
            if self.config.config["ui"]["show_timing"]:
                elapsed = (datetime.now() - start_time).total_seconds()
                print(f"{Fore.MAGENTA} Response time: {elapsed:.2f}s{Style.RESET_ALL}")
            
            return response
            
        except Exception as e:
            return f"Error: {e}"

class SpecialCharCompleter(Completer):
    """
    Trigger completions if '/', '#' or '@' appear anywhere in the input.
    """
    def __init__(self, commands):
        self.commands = commands

    def get_completions(self, document, complete_event):
        text = document.text
        # Find the last occurrence of any special char
        last_pos = -1
        trigger = None
        for ch in ('/', '#', '@'):
            pos = text.rfind(ch)
            if pos > last_pos:
                last_pos = pos
                trigger = ch
        if last_pos != -1:
            fragment = text[last_pos:]
            for cmd in self.commands:
                if cmd.startswith(fragment):
                    yield Completion(cmd, start_position=-len(fragment))
        # No completions otherwise

class BIMCLI:
    """Main CLI interface"""
    
    def __init__(self):
        self.config = BIMConfig()
        self.core = BIMCore(self.config)
        self.mcp_enabled = False
        self.use_react = False
        # Only show completions for special prefixes
        self.special_commands = [
            '/help', '/quit', '/exit', '/clear', '/status', '/config',
            '/mcp', '/agent',
            '#search', '#info', '#tools', '@user', '@admin'
        ]
        self.session = PromptSession()
        self.command_completer = SpecialCharCompleter(self.special_commands)
    
    def print_banner(self):
        """Print CLI banner"""
        banner = (
            "\n"
            "╔═══════════════════════════════════════════════════════════════╗\n"
            "║                     BIM-CLI v1.0.0                            ║\n"
            "║                                                               ║\n"
            "║  Type '/help' for commands, '/quit' to exit                   ║\n"
            "╚═══════════════════════════════════════════════════════════════╝\n"
        )
        print(banner)
    
    def print_help(self):
        """Print help information"""
        help_text = (
            "\n"
            "BIM-CLI Commands:\n"
            "\n"
            "General Commands:\n"
            "  /help                    - Show this help message\n"
            "  /quit, /exit             - Exit the CLI\n"
            "  /clear                   - Clear the screen\n"
            "  /status                  - Show current status\n"
            "  /config                  - Show configuration\n"
            "\n"
            "MCP Commands:\n"
            "  /mcp on                  - Enable MCP servers\n"
            "  /mcp off                 - Disable MCP servers\n"
            "  /mcp status              - Show MCP server status\n"
            "  /mcp list                - List all available MCP servers\n"
            "  /mcp enable <server>     - Enable specific MCP server\n"
            "  /mcp disable <server>    - Disable specific MCP server\n"
            "  /mcp tools               - Show available tools\n"
            "  /mcp add-server <file>   - Add a new MCP server from a file\n"
            "  /mcp remove-server <name> - Remove an MCP server\n"
            "  /mcp add-servers-dir <dir_path> - Add MCP servers from all JSON files in a directory\n"
            "\n"
            "Agent Commands:\n"
            "  /agent react             - Use React agent (when MCP enabled)\n"
            "  /agent tool              - Use tool calling agent (when MCP enabled)\n"
            "  /agent status            - Show current agent type\n"
            "\n"
            "Usage Examples:\n"
            "  What is the capital of France?\n"
            "  /mcp on\n"
            "  List files in current directory\n"
            "  /mcp enable math\n"
            "  Calculate 15 * 23 + 45\n"
        )
        print(help_text)
    
    def show_status(self):
        """Show current status"""
        print("\nCurrent Status:")
        print(f"  Claude Model: {self.config.config['claude']['model']}")
        print(f"  MCP Enabled: {self.mcp_enabled}")
        print(f"  Tools Available: {len(self.core.tools)}")
        print(f"  Agent Type: {'React' if self.use_react else 'Tool Calling'}")
        # Show MCP server process status if possible
        if self.core.mcp_client and hasattr(self.core.mcp_client, 'get_server_status'):
            status = self.core.mcp_client.get_server_status()
            for name, stat in status.items():
                print(f"  Server {name}: {stat}")
        else:
            print("  (Server process status not available)")
    
    def list_servers(self):
        """List all MCP servers with status (enabled, running, failed)"""
        print("\nMCP Servers:")
        for name, config in self.config.config["mcp_servers"].items():
            status = "Enabled" if config["enabled"] else "Disabled"
            running = "Unknown"
            if self.core.mcp_client and hasattr(self.core.mcp_client, 'get_server_status'):
                stat = self.core.mcp_client.get_server_status()
                if name in stat:
                    running = stat[name]
            print(f"  {name}: {status} | Status: {running} - {config.get('description', 'No description')}")
    
    async def handle_mcp_command(self, command: str):
        """Handle MCP-related commands"""
        parts = command.split()
        
        if len(parts) < 2:
            print(f"{Fore.RED}Invalid MCP command. Type 'help' for usage.{Style.RESET_ALL}")
            return
        
        action = parts[1].lower()
        
        if action == "on":
            success = await self.core.setup_mcp_servers()
            self.mcp_enabled = success
            
        elif action == "off":
            self.mcp_enabled = False
            self.core.mcp_client = None
            self.core.tools = []
            print(f"{Fore.YELLOW}MCP servers disabled{Style.RESET_ALL}")
            
        elif action == "status":
            enabled_servers = self.config.get_enabled_servers()
            print(f"\n{Fore.CYAN}📡 MCP Status:{Style.RESET_ALL}")
            print(f"   Enabled: {Fore.GREEN if self.mcp_enabled else Fore.RED}{self.mcp_enabled}{Style.RESET_ALL}")
            print(f"   Active Servers: {Fore.YELLOW}{len(enabled_servers)}{Style.RESET_ALL}")
            print(f"   Available Tools: {Fore.YELLOW}{len(self.core.tools)}{Style.RESET_ALL}")
            
        elif action == "list":
            self.list_servers()
            
        elif action == "enable" and len(parts) >= 3:
            server_name = parts[2]
            success = self.config.enable_server(server_name)
            if success:
                print(f"{Fore.GREEN}Enabled server: {server_name}{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}Server not found: {server_name}{Style.RESET_ALL}")
                
        elif action == "disable" and len(parts) >= 3:
            server_name = parts[2]
            success = self.config.disable_server(server_name)
            if success:
                print(f"{Fore.YELLOW}Disabled server: {server_name}{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}Server not found: {server_name}{Style.RESET_ALL}")
                
        elif action == "add-server" and len(parts) >= 3:
            file_path = parts[2]
            self.config.add_server_from_file(file_path)
        elif action == "remove-server" and len(parts) >= 3:
            server_name = parts[2]
            self.config.remove_server(server_name)
        elif action == "tools":
            self.core.show_available_tools()
        elif action == "add-servers-dir" and len(parts) >= 3:
            dir_path = parts[2]
            self.config.add_servers_from_directory(dir_path)
        else:
            print(f"{Fore.RED}Unknown MCP command: {action}{Style.RESET_ALL}")
    
    def handle_agent_command(self, command: str):
        """Handle agent-related commands"""
        parts = command.split()
        
        if len(parts) < 2:
            print(f"{Fore.RED}Invalid agent command. Type 'help' for usage.{Style.RESET_ALL}")
            return
        
        action = parts[1].lower()
        
        if action == "react":
            self.use_react = True
            print(f"{Fore.GREEN}Switched to React agent{Style.RESET_ALL}")
            
        elif action == "tool":
            self.use_react = False
            print(f"{Fore.GREEN}Switched to Tool Calling agent{Style.RESET_ALL}")
            
        elif action == "status":
            agent_type = "React" if self.use_react else "Tool Calling"
            print(f"{Fore.CYAN}Current Agent: {Fore.YELLOW}{agent_type}{Style.RESET_ALL}")
            
        else:
            print(f"{Fore.RED}Unknown agent command: {action}{Style.RESET_ALL}")
    
    async def process_query(self, query: str):
        """Process user query"""
        print("Processing...")
        
        if self.mcp_enabled:
            response = await self.core.run_with_mcp(query, self.use_react)
        else:
            response = await self.core.run_direct_claude(query)
        
        print("\nResponse:")
        print(response)
    
    async def run(self):
        """Main CLI loop"""
        self.print_banner()
        
        while True:
            try:
                prompt_prefix = self.config.config["ui"]["prompt_prefix"]
                # Use prompt_toolkit's HTML for color, avoid raw ANSI
                prompt_html = HTML(f'<ansicyan><b>{prompt_prefix}&gt;</b></ansicyan> ')
                user_input = await asyncio.to_thread(
                    self.session.prompt,
                    prompt_html,
                    completer=self.command_completer
                )
                user_input = user_input.strip()
                if not user_input:
                    continue

                # Special commands with prefix
                if user_input.lower() in ["/quit", "/exit"]:
                    print("Finishing session!")
                    break
                elif user_input.lower() == "/help":
                    self.print_help()
                elif user_input.lower() == "/clear":
                    os.system('cls' if os.name == 'nt' else 'clear')
                elif user_input.lower() == "/status":
                    self.show_status()
                elif user_input.lower() == "/config":
                    print(f"\n⚙️  Configuration file: {self.config.config_file}")
                elif user_input.lower().startswith("/mcp "):
                    await self.handle_mcp_command(user_input[1:])  # Remove leading '/'
                elif user_input.lower().startswith("/agent "):
                    self.handle_agent_command(user_input[1:])  # Remove leading '/'
                # You can add more special symbol commands here
                else:
                    # Regular query
                    await self.process_query(user_input)
            except KeyboardInterrupt:
                print("\nFinishing session!")
                break
            except Exception as e:
                print(f"Error: {e}")

async def main():
    parser = argparse.ArgumentParser(description="BIM-CLI: Build, Integrate, MCP")
    parser.add_argument("--config", "-c", default="bim-config.json", help="Configuration file path")
    parser.add_argument("--setup", action="store_true", help="Setup initial configuration")
    args = parser.parse_args()

    if args.setup:
        print("🔧 Setting up BIM-CLI...")
        config = BIMConfig(args.config)
        print(f"Configuration created: {config.config_file}")
        print("Edit the configuration file to customize your MCP servers.")
        return

    cli = BIMCLI()
    await cli.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        # If already in an event loop (e.g. Jupyter), use alternative
        import nest_asyncio
        nest_asyncio.apply()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())