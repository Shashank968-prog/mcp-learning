import asyncio
import os

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


HEALTHCARE_SERVER_URL = "http://127.0.0.1:8000/mcp"


async def main():
    print("Starting healthcare client...", flush=True)

    token = os.getenv("MCP_API_TOKEN")

    if not token:
        raise RuntimeError(
            "MCP_API_TOKEN environment variable is not set."
        )

    headers = {
        "Authorization": f"Bearer {token}"
    }

    async with httpx2.AsyncClient(
        headers=headers
    ) as http_client:

        print("Connecting to healthcare server...", flush=True)

        async with streamable_http_client(
    HEALTHCARE_SERVER_URL,
    http_client=http_client
) as (read_stream, write_stream):

            print("Healthcare transport connected.", flush=True)

            async with ClientSession(
                read_stream,
                write_stream
            ) as session:

                print("Initializing session...", flush=True)

                await session.initialize()

                print("Healthcare session initialized.", flush=True)

                tools = await session.list_tools()

                print("\nAvailable healthcare tools:", flush=True)

                for tool in tools.tools:
                    print("-", tool.name, flush=True)


if __name__ == "__main__":
    asyncio.run(main())