from fastmcp.client.transports import StdioTransport
from fastmcp.client import Client
import asyncio

transport = StdioTransport(
    command="npx",
    args=["-p", "mcp-remote", "https://ticktick-mcp.fly.dev/sse"]
)

client = Client(transport)

async def get_all_tasks():
    async with client:
        await client.ping()
    
    async with client:  # Reuses the same subprocess
        await client.call_tool("get_all_tasks", {})

asyncio.run(get_all_tasks())