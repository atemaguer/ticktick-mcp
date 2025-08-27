#!/usr/bin/env python3
"""
Test script for MCP remote connection using mcp-remote package.
This connects to the FastMCP server with OAuth proxy via mcp-remote.
"""

from fastmcp.client.transports import StdioTransport
from fastmcp.client import Client
import asyncio
import sys

# Use the root SSE endpoint for FastMCP's built-in server
SERVER_URL = "https://ticktick-mcp.fly.dev/sse"

def create_client(server_url):
    """Create MCP client with mcp-remote transport"""
    transport = StdioTransport(
        command="npx",
        args=["mcp-remote", server_url]
    )
    return Client(transport)

async def test_mcp_connection():
    """Test the MCP connection and OAuth flow"""
    try:
        print(f"🔗 Connecting to MCP server: {SERVER_URL}")
        client = create_client(SERVER_URL)
        async with client:
            # Test basic connectivity
            print("📡 Testing ping...")
            pong = await client.ping()
            print(f"✅ Ping successful: {pong}")
            
            # List available tools
            print("🔧 Listing available tools...")
            tools_response = await client.list_tools()
            tools = tools_response.tools if hasattr(tools_response, 'tools') else tools_response
            print(f"✅ Found {len(tools)} tools:")
            for tool in tools:
                tool_name = tool.name if hasattr(tool, 'name') else tool.get('name', 'Unknown')
                tool_desc = tool.description if hasattr(tool, 'description') else tool.get('description', 'No description')
                print(f"  - {tool_name}: {tool_desc}")
            
            # Test a simple tool call
            print("🧪 Testing get_projects tool...")
            result = await client.call_tool("get_all_tasks", {})
            print(f"✅ get_projects result: {result}")
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("💡 Make sure:")
        print("  1. Your server is running (python server.py)")
        print("  2. OAuth credentials are set in .env file")
        print("  3. TickTick OAuth app is configured correctly")
        print("  4. Redirect URI is set to http://localhost:8000/auth/callback")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_mcp_connection())
