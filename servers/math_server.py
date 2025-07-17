#!/usr/bin/env python3
"""
Example Math MCP Server
A simple custom MCP server for mathematical operations
"""

import asyncio
import math
from mcp.server.fastmcp import FastMCP

# Create MCP server
mcp = FastMCP("Math Calculator")

@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers"""
    return a + b

@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract b from a"""
    return a - b

@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers"""
    return a * b

@mcp.tool()
def divide(a: float, b: float) -> float:
    """Divide a by b"""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

@mcp.tool()
def power(base: float, exponent: float) -> float:
    """Calculate base raised to the power of exponent"""
    return math.pow(base, exponent)

@mcp.tool()
def sqrt(n: float) -> float:
    """Calculate square root of n"""
    if n < 0:
        raise ValueError("Cannot calculate square root of negative number")
    return math.sqrt(n)

@mcp.tool()
def factorial(n: int) -> int:
    """Calculate factorial of n"""
    if n < 0:
        raise ValueError("Cannot calculate factorial of negative number")
    return math.factorial(n)

@mcp.tool()
def sin(angle: float) -> float:
    """Calculate sine of angle (in radians)"""
    return math.sin(angle)

@mcp.tool()
def cos(angle: float) -> float:
    """Calculate cosine of angle (in radians)"""
    return math.cos(angle)

@mcp.tool()
def calculate_expression(expression: str) -> str:
    """Safely calculate a mathematical expression"""
    try:
        # Basic safety check - only allow mathematical operations
        allowed_chars = "0123456789+-*/.() "
        allowed_functions = ["sin", "cos", "tan", "sqrt", "log", "exp", "abs"]
        
        # Simple validation
        if not all(c in allowed_chars or any(func in expression for func in allowed_functions) for c in expression):
            return "Error: Invalid characters in expression"
        
        # Use eval with limited scope for safety
        import math
        safe_dict = {"__builtins__": {}, "math": math}
        result = eval(expression, safe_dict)
        
        return f"{expression} = {result}"
        
    except Exception as e:
        return f"Error calculating expression: {str(e)}"

if __name__ == "__main__":
    print("🧮 Starting Math MCP Server...")
    mcp.run(transport="stdio")