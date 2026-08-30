import asyncio
import random

from mcp import ClientSession, types
from mcp.client.streamable_http import streamable_http_client


# -------------------------
# Notification Handler
# -------------------------

async def message_handler(message):

    print("\n--- Notification received ---")
    print(message)


# -------------------------
# Retry + Exponential Backoff + Jitter
# -------------------------

async def call_with_retry(
    session,
    tool_name,
    arguments,
    max_attempts=4
):

    for attempt in range(1, max_attempts + 1):

        print(f"\nClient: attempt {attempt}")

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
        # Failure
        # -------------------------

        print("Client: operation failed")

        # Don't wait after final attempt
        if attempt < max_attempts:

            # Exponential backoff
            backoff = 2 ** (attempt - 1)

            # Random jitter
            jitter = random.uniform(0, 1)

            # Final waiting time
            wait_time = backoff + jitter

            print(
                f"Client: retrying in "
                f"{wait_time:.2f} seconds..."
            )

            await asyncio.sleep(wait_time)

    # All attempts failed
    return result


# -------------------------
# Main Client
# -------------------------

async def main():

    async with streamable_http_client(
        "http://127.0.0.1:8000/mcp"
    ) as streams:

        read_stream, write_stream, *_ = streams

        async with ClientSession(
            read_stream,
            write_stream,
            message_handler=message_handler
        ) as session:

            # -------------------------
            # Initialize MCP Session
            # -------------------------

            await session.initialize()

            print("Connected to MCP server")


            # -------------------------
            # Resource Error
            # -------------------------

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

                print("\nResource result:")
                print(result)

            except Exception as e:

                print("\nProtocol/Request Error:")
                print(type(e).__name__)
                print(e)


            # -------------------------
            # List Tools
            # -------------------------

            tools = await session.list_tools()

            print("\nAvailable Tools:")

            for tool in tools.tools:

                print("-", tool.name)


            # -------------------------
            # Retry + Backoff + Jitter
            # -------------------------

            print("\nTesting retry with jitter...")

            result = await call_with_retry(
                session,
                "unstable_operation",
                {},
                max_attempts=4
            )

            print("\nFinal Retry Result:")

            if result.is_error:

                print("Operation failed after all attempts")
                print(result.content)

            else:

                print("Operation succeeded")
                print(result.content)


            # -------------------------
            # Tool Error
            # -------------------------

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


            # -------------------------
            # Timeout
            # -------------------------

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


# -------------------------
# Run Client
# -------------------------

if __name__ == "__main__":

    asyncio.run(main())