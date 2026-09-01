import asyncio
import random
import logging
import os

import httpx
from dotenv import load_dotenv

from mcp import ClientSession, types
from mcp.client.streamable_http import streamable_http_client


# =========================================================
# Environment Variables
# =========================================================

load_dotenv()

MCP_API_TOKEN = os.getenv("MCP_API_TOKEN")

if not MCP_API_TOKEN:
    raise RuntimeError("MCP_API_TOKEN not found in .env")


# =========================================================
# Logging
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# =========================================================
# MCP Notification Handler
# =========================================================

async def message_handler(message):

    logger.info(
        "MCP notification received: %s",
        message
    )


# =========================================================
# Retry + Exponential Backoff + Jitter
# =========================================================

async def call_with_retry(
    session,
    tool_name,
    arguments,
    max_attempts=4
):

    for attempt in range(1, max_attempts + 1):

        print(f"\nClient: attempt {attempt}")

        try:

            result = await session.call_tool(
                tool_name,
                arguments=arguments
            )

            # -------------------------
            # Success
            # -------------------------

            if not result.is_error:

                print("Client: operation succeeded")

                return result

            # -------------------------
            # Tool Error
            # -------------------------

            print("Client: operation failed")

        except Exception:

            logger.exception(
                "Exception while calling %s",
                tool_name
            )

        # -------------------------
        # Retry
        # -------------------------

        if attempt < max_attempts:

            # Exponential backoff
            backoff = 2 ** (attempt - 1)

            # Jitter
            jitter = random.uniform(0, 1)

            wait_time = backoff + jitter

            print(
                f"Client: retrying in "
                f"{wait_time:.2f} seconds..."
            )

            await asyncio.sleep(wait_time)

    print(
        f"Client: failed after "
        f"{max_attempts} attempts"
    )

    return result


# =========================================================
# Main
# =========================================================

async def main():

    # -----------------------------------------------------
    # Create HTTP client with Bearer token
    # -----------------------------------------------------

    headers = {
        "Authorization": f"Bearer {MCP_API_TOKEN}"
    }

    async with httpx.AsyncClient(
        headers=headers
    ) as http_client:

        logger.info(
            "Connecting to authenticated MCP server..."
        )

        # -------------------------------------------------
        # Connect to MCP Server
        # -------------------------------------------------

        async with streamable_http_client(
            "http://127.0.0.1:8000/mcp",
            http_client=http_client
        ) as streams:

            read_stream, write_stream, *_ = streams

            # ---------------------------------------------
            # MCP Session
            # ---------------------------------------------

            async with ClientSession(
                read_stream,
                write_stream,
                message_handler=message_handler
            ) as session:

                # =========================================
                # Initialize
                # =========================================

                await session.initialize()

                print(
                    "\nConnected to authenticated MCP server"
                )


                # =========================================
                # Resource Error
                # =========================================

                print(
                    "\nTesting invalid resource request..."
                )

                request = types.ReadResourceRequest(
                    method="resources/read",
                    params=types.ReadResourceRequestParams(
                        uri="calculator://does-not-exist"
                    )
                )

                try:

                    result = await session.send_request(
                        request,
                        types.ReadResourceResult
                    )

                    print("\nResource result:")
                    print(result)

                except Exception as e:

                    print(
                        "\nProtocol/Request Error:"
                    )

                    print(
                        type(e).__name__
                    )

                    print(e)


                # =========================================
                # List Tools
                # =========================================

                tools = await session.list_tools()

                print(
                    "\nAvailable Tools:"
                )

                for tool in tools.tools:

                    print(
                        "-",
                        tool.name
                    )


                # =========================================
                # Retry + Backoff + Jitter
                # =========================================

                print(
                    "\nTesting retry with jitter..."
                )

                result = await call_with_retry(
                    session,
                    "unstable_operation",
                    {},
                    max_attempts=4
                )

                print(
                    "\nFinal Retry Result:"
                )

                if result.is_error:

                    print(
                        "Operation failed after all attempts"
                    )

                    print(
                        result.content
                    )

                else:

                    print(
                        "Operation succeeded"
                    )

                    print(
                        result.content
                    )


                # =========================================
                # Tool Error
                # =========================================

                print(
                    "\nCalling divide with invalid input..."
                )

                result = await session.call_tool(
                    "divide",
                    arguments={
                        "a": 10,
                        "b": 0
                    }
                )

                print(
                    "\nTool Result:"
                )

                print(result)

                print(
                    "\nIs Error:"
                )

                print(
                    result.is_error
                )

                print(
                    "\nStructured Content:"
                )

                print(
                    result.structured_content
                )

                print(
                    "\nContent:"
                )

                print(
                    result.content
                )


                # =========================================
                # Timeout
                # =========================================

                print(
                    "\nStarting long calculation "
                    "with 3-second timeout..."
                )

                try:

                    result = await asyncio.wait_for(
                        session.call_tool(
                            "long_calculation",
                            arguments={}
                        ),
                        timeout=3
                    )

                    print(
                        "\nFinal Result:"
                    )

                    print(result)

                except asyncio.TimeoutError:

                    print(
                        "\nClient: calculation timed out"
                    )


# =========================================================
# Run Client
# =========================================================

if __name__ == "__main__":

    asyncio.run(main())