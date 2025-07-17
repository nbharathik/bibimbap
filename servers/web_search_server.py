#!/usr/bin/env python3
"""
Example Web Search MCP Server
A simple web search MCP server using requests
"""

import os
import requests
from mcp.server.fastmcp import FastMCP

# Create MCP server
mcp = FastMCP("Web Search")

@mcp.tool()
def search_web(query: str, num_results: int = 5) -> str:
    """Search the web for information"""
    api_key = os.getenv("SEARCH_API_KEY")
    
    if not api_key:
        return "Error: SEARCH_API_KEY environment variable not set"
    
    try:
        # This is a placeholder - replace with actual search API
        # For example, you could use DuckDuckGo, Google Custom Search, etc.
        
        # Mock search results for demo
        results = [
            {"title": f"Search result {i} for '{query}'", 
             "url": f"https://example.com/result{i}",
             "snippet": f"This is a mock search result {i} for the query '{query}'"}
            for i in range(1, num_results + 1)
        ]
        
        # Format results
        formatted_results = []
        for i, result in enumerate(results, 1):
            formatted_results.append(f"{i}. {result['title']}")
            formatted_results.append(f"   URL: {result['url']}")
            formatted_results.append(f"   {result['snippet']}")
            formatted_results.append("")
        
        return "\n".join(formatted_results)
        
    except Exception as e:
        return f"Error searching web: {str(e)}"

@mcp.tool()
def get_webpage_content(url: str) -> str:
    """Get the content of a webpage"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Simple text extraction (in real implementation, use BeautifulSoup)
        content = response.text[:1000]  # Limit to first 1000 characters
        return f"Content from {url}:\n{content}"
        
    except Exception as e:
        return f"Error fetching webpage: {str(e)}"

if __name__ == "__main__":
    print("🔍 Starting Web Search MCP Server...")
    mcp.run(transport="stdio")
