import asyncio
import os

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


SERVER_URL = "http://127.0.0.1:8000/mcp"


async def main():
    print("Client A: Starting...", flush=True)

    token = os.getenv("MCP_API_TOKEN")

    if not token:
        raise RuntimeError(
            "MCP_API_TOKEN environment variable is not set."
        )

    async with httpx2.AsyncClient(
        headers={
            "Authorization": f"Bearer {token}"
        }
    ) as http_client:

        async with streamable_http_client(
            SERVER_URL,
            http_client=http_client
        ) as (read_stream, write_stream):

            async with ClientSession(
                read_stream,
                write_stream
            ) as session:

                await session.initialize()

                print("Client A: Connected successfully.", flush=True)

                result = await session.call_tool(
                    "search_healthcare",
                    arguments={
                        "question": "What are the symptoms of diabetes?",
                        "top_k": 2
                    }
                )

                print("\nClient A: Healthcare result", flush=True)

                for content in result.content:
                    if hasattr(content, "text"):
                        print(content.text, flush=True)


if __name__ == "__main__":
    asyncio.run(main())