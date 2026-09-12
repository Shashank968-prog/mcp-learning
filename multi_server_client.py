import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client


HEALTHCARE_SERVER_URL = "http://127.0.0.1:8000/mcp"


async def connect_to_healthcare_server():
    print("Connecting to healthcare server...", flush=True)

    token = os.getenv("MCP_API_TOKEN")

    if not token:
        raise RuntimeError(
            "MCP_API_TOKEN environment variable is not set."
        )

    headers = {
        "Authorization": f"Bearer {token}"
    }

    async with streamable_http_client(
        HEALTHCARE_SERVER_URL,
        headers=headers
    ) as (read_stream, write_stream, _):

        print("Healthcare transport connected.", flush=True)

        async with ClientSession(
            read_stream,
            write_stream
        ) as session:

            print("Initializing healthcare session...", flush=True)
            await session.initialize()
            print("Healthcare session initialized.", flush=True)

            tools = await session.list_tools()

            print("\n=== Healthcare MCP Server Tools ===", flush=True)

            for tool in tools.tools:
                print(f"- {tool.name}", flush=True)

            result = await session.call_tool(
                "search_healthcare",
                arguments={
                    "question": "What are the symptoms of diabetes?",
                    "top_k": 2
                }
            )

            print("\n=== Healthcare Tool Result ===", flush=True)

            for content in result.content:
                if hasattr(content, "text"):
                    print(content.text, flush=True)


async def connect_to_calculator_server():
    print("\nConnecting to calculator server...", flush=True)

    server_parameters = StdioServerParameters(
        command=sys.executable,
        args=["calculator_server.py"],
        env=os.environ.copy()
    )

    async with stdio_client(server_parameters) as (
        read_stream,
        write_stream
    ):

        print("Calculator transport connected.", flush=True)

        async with ClientSession(
            read_stream,
            write_stream
        ) as session:

            print("Initializing calculator session...", flush=True)
            await session.initialize()
            print("Calculator session initialized.", flush=True)

            tools = await session.list_tools()

            print("\n=== Calculator MCP Server Tools ===", flush=True)

            for tool in tools.tools:
                print(f"- {tool.name}", flush=True)

            result = await session.call_tool(
                "multiply",
                arguments={
                    "a": 12,
                    "b": 5
                }
            )

            print("\n=== Calculator Tool Result ===", flush=True)

            for content in result.content:
                if hasattr(content, "text"):
                    print(content.text, flush=True)


async def main():
    print("Starting multi-server client...", flush=True)

    await asyncio.gather(
        connect_to_healthcare_server(),
        connect_to_calculator_server()
    )

    print("\nMulti-server client finished.", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:
        print(
            f"\nERROR: {type(error).__name__}: {error}",
            file=sys.stderr,
            flush=True
        )