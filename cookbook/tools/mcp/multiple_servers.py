"""
This example demonstrates how to use multiple MCP servers in a single agent.

Prerequisites:
- Set the environment variable "ACCUWEATHER_API_KEY" for the weather MCP tools.
- You can get the API key from the AccuWeather website: https://developer.accuweather.com/
"""

import asyncio
from os import getenv

from agno.agent import Agent
from agno.tools.mcp import MultiMCPTools


async def run_agent(message: str) -> None:
    # Initialize the MCP tools
    mcp_tools = MultiMCPTools(
        [
            "npx -y @openbnb/mcp-server-airbnb --ignore-robots-txt",
            "npx -y @modelcontextprotocol/server-brave-search",
        ],
        env={
            "BRAVE_API_KEY": getenv("BRAVE_API_KEY"),
        },
        timeout_seconds=30,
    )

    # Connect to the MCP servers
    await mcp_tools.connect()

    # Use the MCP tools with an Agent
    agent = Agent(
        tools=[mcp_tools],
        markdown=True,
    )
    await agent.aprint_response(message)

    # Close the MCP connection
    await mcp_tools.close()


# Example usage
if __name__ == "__main__":
    asyncio.run(run_agent("What listings are available in Barcelona tonight?"))
    asyncio.run(run_agent("What's the fastest way to get to Barcelona from London?"))
