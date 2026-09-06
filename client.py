import asyncio
import logging
import os
import random

from click import prompt
import httpx
from pathlib import Path
from mcp import types
from dotenv import load_dotenv
from google import genai

from mcp import ClientSession
from mcp.client.session import ClientRequestContext
from mcp.client.streamable_http import streamable_http_client


# =========================================================
# Configuration
# =========================================================

load_dotenv()

MCP_API_TOKEN = os.getenv("MCP_API_TOKEN")

if not MCP_API_TOKEN:
    raise RuntimeError("MCP_API_TOKEN not found in .env")

SERVER_URL = "http://127.0.0.1:8000/mcp"

gemini_client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"]
)

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
# Roots Callback
# =========================================================

async def list_roots_callback(context):

    # Get the current project directory
    project_path = Path.cwd()

    # Create an MCP Root
    root = types.Root(
        uri=project_path.as_uri(),
        name=project_path.name
    )

    logger.info(
        "Roots requested by server: %s",
        project_path
    )

    # Return the Root to the MCP server
    return types.ListRootsResult(
        roots=[root]
    )


# =========================================================
# Roots Test
# MCP 2026-07-28 Multi-Round-Trip Handling
# =========================================================

async def test_roots(session):
    print("\nTesting MCP Roots...")

    input_responses = None
    request_state = None

    # A modern MCP server can return InputRequiredResult first.
    # We satisfy the embedded Roots request using the same callback
    # registered on ClientSession, then retry the tool call.
    for round_number in range(1, 6):
        try:
            result = await session.call_tool(
                "show_roots",
                arguments={},
                input_responses=input_responses,
                request_state=request_state,
                allow_input_required=True
            )
        except Exception as e:
            print("\nRoots Error:")
            print(type(e).__name__)
            print(e)
            return

        # Terminal tool result: Roots flow completed.
        if not isinstance(result, types.InputRequiredResult):
            print("\nRoots Result:")
            print(result)

            if getattr(result, "content", None):
                print("\nRoots Content:")
                for item in result.content:
                    text = getattr(item, "text", None)
                    if text:
                        print(text)

            return

        print(
            f"Roots round {round_number}: "
            "server requested client input"
        )

        responses = {}

        for key, request in result.input_requests.items():
            params = request.params
            meta = params.meta if params is not None else None

            context = ClientRequestContext(
                session=session,
                request_id=key,
                meta=meta
            )

            response = await session.dispatch_input_request(
                context,
                request
            )

            if isinstance(response, types.ErrorData):
                raise RuntimeError(
                    f"Client could not satisfy input request "
                    f"{key}: {response.message}"
                )

            responses[key] = response

        input_responses = responses
        request_state = result.request_state

    raise RuntimeError(
        "Roots flow exceeded the maximum number of input rounds"
    )



# =========================================================
# MCP Sampling Callback - Real Gemini
# =========================================================

async def sampling_callback(
    context: ClientRequestContext,
    params: types.CreateMessageRequestParams
) -> types.CreateMessageResult:

    print("\n========================================")
    print("SAMPLING REQUEST RECEIVED")
    print("========================================")

    # Show what the MCP server requested
    print("\nMessages:")
    print(params.messages)

    print("\nMax Tokens:")
    print(params.max_tokens)

    print("\nSystem Prompt:")
    print(params.system_prompt)

    print("\nTemperature:")
    print(params.temperature)

    # ---------------------------------------------------------
    # Create the prompt BEFORE using it.
    #
    # IMPORTANT:
    # It is "prompt", not "promt".
    # ---------------------------------------------------------

    prompt = ""

    # ---------------------------------------------------------
    # Extract text from every MCP sampling message
    # ---------------------------------------------------------

    for message in params.messages:

        if isinstance(message.content, types.TextContent):

            prompt += message.content.text + "\n"

    # ---------------------------------------------------------
    # Add the system prompt
    # ---------------------------------------------------------

    if params.system_prompt:

        prompt = (
            params.system_prompt
            + "\n\n"
            + prompt
        )
        # Make the context explicit for Gemini
        prompt = (
             "You are an assistant helping the user learn the "
    "Model Context Protocol (MCP). "
    "Answer specifically in the context of MCP.\n\n"
    + prompt
)

    print("\nPrompt sent to Gemini:")
    print("----------------------------------------")
    print(prompt)
    print("----------------------------------------")

    # ---------------------------------------------------------
    # REAL LLM CALL
    # ---------------------------------------------------------
    #
    # The MCP client now sends the prompt to Gemini.
    # There is NO fake response.
    # ---------------------------------------------------------

    try:
        response = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
            )

    except Exception as e:

        print("\nGemini API Error:")
        print(e)

        return types.ErrorData(
            code=-1,
            message=f"Gemini API error: {str(e)}"
        )

    # ---------------------------------------------------------
    # Get the text generated by Gemini
    # ---------------------------------------------------------

    response_text = response.text

    print("\nGemini generated:")
    print("----------------------------------------")
    print(response_text)
    print("----------------------------------------")

    # ---------------------------------------------------------
    # Convert Gemini's response into an MCP response
    # ---------------------------------------------------------

    return types.CreateMessageResult(
        role="assistant",

        content=types.TextContent(
            type="text",
            text=response_text
        ),

        model="gemini-2.5-flash",

        stop_reason="endTurn"
    )


# =========================================================
# Sampling Test
# =========================================================

async def test_sampling(session):
    """
    Test MCP Sampling.

    The MCP server will request an LLM response.
    The MCP client receives that sampling request,
    calls Gemini through sampling_callback(),
    and returns the generated response.
    """

    print("\nTesting MCP Sampling...")

    try:
        # Call the MCP tool that triggers sampling
        result = await session.call_tool(
            "test_sampling",
            arguments={}
        )

        print("\nSampling Result:")
        print(result)

        print("\nSampling Content:")

        # Read the content returned by the MCP server
        for item in result.content:

            # Extract text from the returned content
            text = getattr(item, "text", None)

            if text:
                print(text)

    except Exception as e:

        print("\nSampling Error:")
        print(type(e).__name__)
        print(e)


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
                message_handler=message_handler,
                sampling_callback=sampling_callback,
                list_roots_callback=list_roots_callback
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
                # Roots
                # -------------------------------------------------

                await test_roots(session)

                # -------------------------------------------------
                # Sampling
                # -------------------------------------------------

                await test_sampling(session)

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