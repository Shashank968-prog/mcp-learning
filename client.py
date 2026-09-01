import asyncio
import logging
import os
import random

import httpx
from dotenv import load_dotenv

from mcp import ClientSession, types
from mcp.client.streamable_http import streamable_http_client


# =========================================================
# Configuration
# =========================================================

load_dotenv()

MCP_API_TOKEN = os.getenv("MCP_API_TOKEN")

if not MCP_API_TOKEN:
    raise RuntimeError("MCP_API_TOKEN not found in .env")

SERVER_URL = "http://127.0.0.1:8000/mcp"


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
    last_result = None

    for attempt in range(1, max_attempts + 1):

        print(f"\nClient: attempt {attempt}")

        try:
            result = await session.call_tool(
                tool_name,
                arguments=arguments
            )

            last_result = result

            if not result.is_error:
                print("Client: operation succeeded")
                return result

            print("Client: operation failed")

        except Exception:
            logger.exception(
                "Exception while calling %s",
                tool_name
            )

        if attempt < max_attempts:

            backoff = 2 ** (attempt - 1)
            jitter = random.uniform(0, 1)
            wait_time = backoff + jitter

            print(
                f"Client: retrying in "
                f"{wait_time:.2f} seconds..."
            )

            await asyncio.sleep(wait_time)

    print(
        f"\nClient: failed after "
        f"{max_attempts} attempts"
    )

    return last_result


# =========================================================
# Resource Error Test
# =========================================================

async def test_invalid_resource(session):

    print("\nTesting invalid resource request...")

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

        print("\nResource Result:")
        print(result)

    except Exception as e:

        print("\nProtocol/Request Error:")
        print(type(e).__name__)
        print(e)


# =========================================================
# Resource Security Test
# =========================================================

async def test_resource_security(session):

    print("\nTesting resource security...")

    # -----------------------------------------------------
    # Valid resource
    # -----------------------------------------------------

    print("\n1. Testing valid resource...")

    try:

        result = await session.read_resource(
            "calculator://history/report.txt"
        )

        print("Valid Resource Result:")
        print(result)

    except Exception as e:

        print("Valid Resource Error:")
        print(type(e).__name__)
        print(e)

    # -----------------------------------------------------
    # Path traversal
    # -----------------------------------------------------

    print("\n2. Testing path traversal...")

    try:

        result = await session.read_resource(
            "calculator://history/../../secret.txt"
        )

        print("Path Traversal Result:")
        print(result)

    except Exception as e:

        print("Path Traversal Blocked:")
        print(type(e).__name__)
        print(e)


# =========================================================
# Authorization Test
# =========================================================

async def test_authorization(session):

    print("\nTesting authorization...")

    try:

        result = await session.call_tool(
            "admin_reset",
            arguments={}
        )

        print("\nAdmin Tool Result:")
        print(result)

        print("\nIs Error:")
        print(result.is_error)

        print("\nContent:")
        print(result.content)

    except Exception as e:

        print("\nAuthorization Error:")
        print(type(e).__name__)
        print(e)


# =========================================================
# Input Validation Test
# =========================================================

async def test_input_validation(session):

    print("\nTesting input validation...")

    try:

        result = await session.call_tool(
            "percentage",
            arguments={
                "value": 200,
                "percent": 150
            }
        )

        print("\nPercentage Tool Result:")
        print(result)

        print("\nIs Error:")
        print(result.is_error)

        print("\nContent:")
        print(result.content)

    except Exception as e:

        print("\nValidation Error:")
        print(type(e).__name__)
        print(e)


# =========================================================
# Tool Error Test
# =========================================================

async def test_tool_error(session):

    print("\nCalling divide with invalid input...")

    result = await session.call_tool(
        "divide",
        arguments={
            "a": 10,
            "b": 0
        }
    )

    print("\nTool Result:")
    print(result)

    print("\nIs Error:")
    print(result.is_error)

    print("\nStructured Content:")
    print(result.structured_content)

    print("\nContent:")
    print(result.content)


# =========================================================
# Timeout Test
# =========================================================

async def test_timeout(session):

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

        print("\nFinal Result:")
        print(result)

    except asyncio.TimeoutError:

        print(
            "\nClient: calculation timed out"
        )


# =========================================================
# Main
# =========================================================

async def main():

    headers = {
        "Authorization": f"Bearer {MCP_API_TOKEN}"
    }

    async with httpx.AsyncClient(
        headers=headers
    ) as http_client:

        logger.info(
            "Connecting to authenticated MCP server..."
        )

        async with streamable_http_client(
            SERVER_URL,
            http_client=http_client
        ) as streams:

            read_stream, write_stream, *_ = streams

            async with ClientSession(
                read_stream,
                write_stream,
                message_handler=message_handler
            ) as session:

                # -------------------------------------------------
                # Initialize
                # -------------------------------------------------

                await session.initialize()

                print(
                    "\nConnected to authenticated MCP server"
                )

                # -------------------------------------------------
                # Resource Error
                # -------------------------------------------------

                await test_invalid_resource(session)

                # -------------------------------------------------
                # Resource Security
                # -------------------------------------------------

                await test_resource_security(session)

                # -------------------------------------------------
                # List Tools
                # -------------------------------------------------

                tools = await session.list_tools()

                print("\nAvailable Tools:")

                for tool in tools.tools:
                    print("-", tool.name)

                # -------------------------------------------------
                # Retry + Jitter
                # -------------------------------------------------

                print(
                    "\nTesting retry with jitter..."
                )

                result = await call_with_retry(
                    session,
                    "unstable_operation",
                    {},
                    max_attempts=4
                )

                print("\nFinal Retry Result:")

                if result and result.is_error:

                    print(
                        "Operation failed "
                        "after all attempts"
                    )

                    print(result.content)

                elif result:

                    print("Operation succeeded")
                    print(result.content)

                # -------------------------------------------------
                # Tool Error
                # -------------------------------------------------

                await test_tool_error(session)

                # -------------------------------------------------
                # Authorization
                # -------------------------------------------------

                await test_authorization(session)

                # -------------------------------------------------
                # Input Validation
                # -------------------------------------------------

                await test_input_validation(session)

                # -------------------------------------------------
                # Timeout
                # -------------------------------------------------

                await test_timeout(session)


# =========================================================
# Run Client
# =========================================================

if __name__ == "__main__":
    asyncio.run(main())