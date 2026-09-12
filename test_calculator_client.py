import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    print("Starting calculator test...", flush=True)

    parameters = StdioServerParameters(
        command=sys.executable,
        args=["calculator_server.py"],
        env=os.environ.copy(),
    )

    print("Starting calculator process...", flush=True)

    async with stdio_client(parameters) as (read_stream, write_stream):
        print("Calculator process started.", flush=True)

        async with ClientSession(read_stream, write_stream) as session:
            print("Initializing session...", flush=True)

            await session.initialize()

            print("Session initialized.", flush=True)

            tools = await session.list_tools()

            print("Available tools:", flush=True)

            for tool in tools.tools:
                print("-", tool.name, flush=True)

            result = await session.call_tool(
                "multiply",
                arguments={"a": 12, "b": 5},
            )

            print("Result:", result, flush=True)


if __name__ == "__main__":
    asyncio.run(main())