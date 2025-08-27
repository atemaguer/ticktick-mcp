import asyncio
from fastmcp import Client, FastMCP

client = Client("https://ticktick-mcp.fastmcp.app/mcp")

async def main():
    async with client:
        # Ensure client can connect
        await client.ping()

        # List available operations
        tools = await client.list_tools()
        resources = await client.list_resources()
        prompts = await client.list_prompts()

        # Ex. execute a tool call
        result = await client.call_tool("get_all_tasks", {})
        print(result)

asyncio.run(main())