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
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

try:
    import anthropic
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langchain_mcp_adapters.tools import load_mcp_tools
    import colorama
    from colorama import Fore, Style, Back
    colorama.init()
except ImportError as e:
    print(f"Missing dependencies: {e}")
    print("Install with: pip install anthropic langchain-mcp-adapters colorama")
    sys.exit(1)

# Load environment variables from .env file in configs/
env_path = Path(__file__).parent / 'configs' / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

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
    cwd: Optional[str] = None 
    description: Optional[str] = None

class BIMConfig:
    """Configuration manager for BIM-CLI"""
    
    def __init__(self, config_file: str = None):
        # Default to configs/config.json for all config
        if config_file is None:
            config_file = str(Path(__file__).parent / 'configs' / 'config.json')
        self.config_file = Path(config_file)
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        if not self.config_file.exists():
            print(f"Config file {self.config_file} not found. Please copy config.example.json to config.json and edit as needed.")
            sys.exit(1)
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            sys.exit(1)
    
    def create_default_config(self) -> Dict[str, Any]:
        """No longer used. configs/servers.json is required."""
        print("Please create configs/servers.json from servers.example.json.")
        sys.exit(1)
    
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
        self.client = None
        self.mcp_client = None
        self.tools = []
        self.initialize_anthropic()
    
    def initialize_anthropic(self):
        """Initialize Anthropic client"""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print(f"{Fore.RED}ANTHROPIC_API_KEY environment variable not set{Style.RESET_ALL}")
            sys.exit(1)
        
        self.client = anthropic.Anthropic(api_key=api_key)
        claude_config = self.config.config["claude"]
        self.model = claude_config["model"]
        self.temperature = claude_config["temperature"]
        self.max_tokens = claude_config["max_tokens"]
        
        print(f"{Fore.GREEN}Anthropic initialized: {self.model}{Style.RESET_ALL}")
    
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
                if server.cwd:
                    server_config["cwd"] = server.cwd  # Add cwd if present
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
                    if 'cwd' in cfg:
                        print(f"    CWD: {cfg['cwd']}")
                if 'url' in cfg:
                    print(f"    URL: {cfg['url']}")
                if 'headers' in cfg:
                    print(f"    Headers: {cfg['headers']}")
            print(f"  Error: {e}")
            return False
    
    def show_available_tools(self):
        """Display available tools as bullet points"""
        if not self.tools:
            return
        
        console = Console()
        console.print(f"\n[cyan]Available Tools ({len(self.tools)}):[/cyan]")
        
        for tool in self.tools:
            console.print(f"  • [yellow]{tool.name}[/yellow]")
        console.print()
    
    def convert_mcp_tools_to_anthropic(self, mcp_tools):
        """Convert MCP tools to Anthropic tool format"""
        anthropic_tools = []
        for tool in mcp_tools:
            anthropic_tool = {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.args_schema
            }
            anthropic_tools.append(anthropic_tool)
        return anthropic_tools
    
    async def run_direct_claude(self, query: str) -> str:
        """Run query with direct Claude (no MCP), with streaming support"""
        from rich.live import Live
        from rich.text import Text
        start_time = datetime.now()
        console = Console()
        response = ""
        try:
            console.print("[cyan]Processing...[/cyan]")
            # Streaming response from Claude
            with Live(Text(""), console=console, refresh_per_second=8) as live:
                stream = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    messages=[{"role": "user", "content": query}],
                    stream=True
                )
                for event in stream:
                    if hasattr(event, "delta") and hasattr(event.delta, "text"):
                        response += event.delta.text
                        live.update(Text(response))
            if self.config.config["ui"]["show_timing"]:
                elapsed = (datetime.now() - start_time).total_seconds()
                console.print(f"[magenta]Response time: {elapsed:.2f}s[/magenta]")
            return response
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            return f"Error: {e}"
    
    async def run_with_mcp(self, query: str) -> str:
        """Run query with MCP tools using native Anthropic tool calling, with streaming support and immediate tool result display"""
        from rich.live import Live
        from rich.text import Text
        from rich.panel import Panel
        from rich.markdown import Markdown
        start_time = datetime.now()
        console = Console()
        full_response = ""  
        try:
            anthropic_tools = self.convert_mcp_tools_to_anthropic(self.tools)
            messages = [{"role": "user", "content": query}]
            
            while True:
                # Streaming response from Claude with tools
                streamed_response = ""
                tool_calls = []
                
                with Live(Text(""), console=console, refresh_per_second=8) as live:
                    with self.client.messages.stream(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        temperature=self.temperature,
                        tools=anthropic_tools,
                        messages=messages
                    ) as stream:
                        for text in stream.text_stream:
                            streamed_response += text
                            live.update(Text(streamed_response))
                
                final_message = stream.get_final_message()

                # Extract any tool calls
                for content_block in final_message.content:
                    if content_block.type == "tool_use":
                        tool_calls.append(content_block)

                # Add this cycle's streamed content to the full response
                if streamed_response:
                    if full_response:
                        full_response += "\n\n" + streamed_response
                    else:
                        full_response = streamed_response
                
                # Add assistant's response to messages
                messages.append({"role": "assistant", "content": final_message.content})
                
                if not tool_calls:
                    break
                
                # Execute tool calls and show results immediately
                tool_results = []
                for tool_call in tool_calls:
                    try:
                        mcp_tool = next(tool for tool in self.tools if tool.name == tool_call.name)
                        result = await mcp_tool.ainvoke(tool_call.input)
                        tool_result_content = str(result)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_call.id,
                            "content": tool_result_content
                        })
                        console.print()
                        console.print(Panel(Markdown(tool_result_content), title=f"[bold green]Tool: {tool_call.name}[/bold green]", border_style="green", padding=(1, 2)))
                    except Exception as e:
                        error_msg = f"Error: {str(e)}"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_call.id,
                            "content": error_msg,
                            "is_error": True
                        })
                        console.print(Panel(error_msg, title=f"[bold red]Tool Error: {tool_call.name}[/bold red]", border_style="red", padding=(1, 2)))
                
                # Add tool results to continue the conversation
                messages.append({
                    "role": "user",
                    "content": tool_results
                })
            
            if self.config.config["ui"]["show_timing"]:
                elapsed = (datetime.now() - start_time).total_seconds()
                console.print(f"[magenta]Response time: {elapsed:.2f}s[/magenta]")
            
            return full_response
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
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
        # Only show completions for special prefixes
        self.special_commands = [
            '/help', '/quit', '/exit', '/clear', '/status', '/config',
            '/mcp',
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
            if success:
                console = Console()
            
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
    
    async def process_query(self, query: str):
        """Process user query"""
        from rich.console import Console
        from rich.markdown import Markdown
        from rich.panel import Panel
        console = Console()
        if self.mcp_enabled:
            with console.status("[cyan]Processing with MCP...[/cyan]"):
                response = await self.core.run_with_mcp(query)
        else:
            response = await self.core.run_direct_claude(query)
        if response:
            console.print(
                Panel(
                    Markdown(response),
                    title="[bold cyan]Response[/bold cyan]",
                    border_style="bright_blue",
                    padding=(1, 2),
                )
            )
    
    async def run(self):
        """Main CLI loop"""
        self.print_banner()
        
        while True:
            try:
                prompt_prefix = self.config.config["ui"]["prompt_prefix"]
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
                    print(f"\nConfiguration file: {self.config.config_file}")
                elif user_input.lower().startswith("/mcp "):
                    await self.handle_mcp_command(user_input[1:])  
                else:
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
        print("Setting up BIM-CLI...")
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
        import nest_asyncio
        nest_asyncio.apply()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())