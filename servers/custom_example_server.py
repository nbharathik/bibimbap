#!/usr/bin/env python3
"""
Example: Creating Your Own Custom MCP Server
This shows how to create a custom MCP server for your specific needs
"""

import asyncio
import json
import sqlite3
from datetime import datetime
from mcp.server.fastmcp import FastMCP

# Create MCP server
mcp = FastMCP("Custom Business Server")

# Initialize a simple database for demo
def init_database():
    """Initialize example database"""
    conn = sqlite3.connect("business.db")
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT,
            created_at TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            product TEXT,
            amount REAL,
            created_at TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers (id)
        )
    """)
    
    conn.commit()
    conn.close()

# Initialize database on startup
init_database()

@mcp.tool()
def add_customer(name: str, email: str) -> str:
    """Add a new customer to the database"""
    try:
        conn = sqlite3.connect("business.db")
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO customers (name, email, created_at) VALUES (?, ?, ?)",
            (name, email, datetime.now())
        )
        
        customer_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return f"Customer added successfully with ID: {customer_id}"
        
    except Exception as e:
        return f"Error adding customer: {str(e)}"

@mcp.tool()
def get_customer_info(customer_id: int) -> str:
    """Get information about a customer"""
    try:
        conn = sqlite3.connect("business.db")
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT name, email, created_at FROM customers WHERE id = ?",
            (customer_id,)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return f"Customer ID {customer_id}: {result[0]} ({result[1]}) - Created: {result[2]}"
        else:
            return f"Customer with ID {customer_id} not found"
            
    except Exception as e:
        return f"Error getting customer info: {str(e)}"

@mcp.tool()
def add_order(customer_id: int, product: str, amount: float) -> str:
    """Add a new order for a customer"""
    try:
        conn = sqlite3.connect("business.db")
        cursor = conn.cursor()
        
        # Check if customer exists
        cursor.execute("SELECT id FROM customers WHERE id = ?", (customer_id,))
        if not cursor.fetchone():
            return f"Customer with ID {customer_id} not found"
        
        cursor.execute(
            "INSERT INTO orders (customer_id, product, amount, created_at) VALUES (?, ?, ?, ?)",
            (customer_id, product, amount, datetime.now())
        )
        
        order_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return f"Order added successfully with ID: {order_id}"
        
    except Exception as e:
        return f"Error adding order: {str(e)}"

@mcp.tool()
def get_customer_orders(customer_id: int) -> str:
    """Get all orders for a customer"""
    try:
        conn = sqlite3.connect("business.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT o.id, o.product, o.amount, o.created_at
            FROM orders o
            WHERE o.customer_id = ?
            ORDER BY o.created_at DESC
        """, (customer_id,))
        
        orders = cursor.fetchall()
        conn.close()
        
        if orders:
            result = [f"Orders for customer {customer_id}:"]
            for order in orders:
                result.append(f"  Order {order[0]}: {order[1]} - ${order[2]:.2f} ({order[3]})")
            return "\n".join(result)
        else:
            return f"No orders found for customer {customer_id}"
            
    except Exception as e:
        return f"Error getting orders: {str(e)}"

@mcp.tool()
def get_sales_summary() -> str:
    """Get a summary of all sales"""
    try:
        conn = sqlite3.connect("business.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) as total_orders, SUM(amount) as total_revenue
            FROM orders
        """)
        
        result = cursor.fetchone()
        
        cursor.execute("""
            SELECT COUNT(*) as total_customers FROM customers
        """)
        
        customer_count = cursor.fetchone()[0]
        conn.close()
        
        return f"Sales Summary:\n  Total Customers: {customer_count}\n  Total Orders: {result[0]}\n  Total Revenue: ${result[1]:.2f}"
        
    except Exception as e:
        return f"Error getting sales summary: {str(e)}"

if __name__ == "__main__":
    print("🏢 Starting Custom Business MCP Server...")
    mcp.run(transport="stdio")
