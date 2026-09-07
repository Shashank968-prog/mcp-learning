# =========================================================
# Imports
# =========================================================

import asyncio
import json
import os

import httpx

from dotenv import load_dotenv
from google import genai

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


# =========================================================
# Load Environment Variables
# =========================================================

# Load values from .env
load_dotenv()

# Gemini API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# MCP authentication token
MCP_API_TOKEN = os.getenv("MCP_API_TOKEN")


# Make sure Gemini API key exists
if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY was not found in .env"
    )


# Make sure MCP authentication token exists
if not MCP_API_TOKEN:
    raise RuntimeError(
        "MCP_API_TOKEN was not found in .env"
    )


# =========================================================
# MCP Server URL
# =========================================================

SERVER_URL = "http://127.0.0.1:8000/mcp"


# =========================================================
# Create Gemini Client
# =========================================================

gemini = genai.Client(
    api_key=GEMINI_API_KEY
)


# =========================================================
# Convert MCP Tools for Gemini
# =========================================================

def convert_mcp_tools(mcp_tools):
    """
    Convert MCP tool information into simple dictionaries
    that Gemini can understand inside the prompt.

    Each MCP tool contains:

        name
        description
        inputSchema

    Example:

        add
        Add two numbers
        {
            "a": integer,
            "b": integer
        }
    """

    tools = []

    for tool in mcp_tools:

        tools.append({
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema,
        })

    return tools


# =========================================================
# Ask Gemini Which MCP Tool To Use
# =========================================================

async def ask_agent(
    question,
    mcp_tools
):
    """
    Gemini acts as the decision maker.

    Gemini receives:

        1. User question
        2. Available MCP tools
        3. Tool argument schemas

    Gemini then decides:

        Which tool?
        What arguments?

    Gemini does NOT execute the MCP tool.
    """

    # Convert MCP tool objects into dictionaries
    tool_definitions = convert_mcp_tools(
        mcp_tools
    )


    # -----------------------------------------------------
    # Build prompt for Gemini
    # -----------------------------------------------------

    prompt = f"""
You are a calculator AI agent.

Your job is to choose the correct MCP calculator tool.

Available MCP tools:

{json.dumps(tool_definitions, indent=2)}

User question:

{question}

Choose the correct MCP tool and arguments.

Return ONLY valid JSON.

Use exactly this structure:

{{
    "tool": "tool_name",
    "arguments": {{
        "argument_name": value
    }}
}}

Do not calculate the answer yourself.

The MCP calculator tool must perform the calculation.
"""


    # -----------------------------------------------------
    # Call Gemini
    # -----------------------------------------------------
    #
    # Gemini SDK generate_content() is synchronous.
    #
    # asyncio.to_thread() runs it without blocking
    # the MCP async event loop.
    # -----------------------------------------------------

    response = await asyncio.to_thread(
        gemini.models.generate_content,
        model="gemini-2.5-flash",
        contents=prompt,
    )


    # Gemini returns text
    return response.text


# =========================================================
# Clean Gemini JSON Response
# =========================================================

def parse_agent_decision(
    response_text
):
    """
    Convert Gemini's JSON response into a Python dictionary.

    Sometimes an LLM may return:

        ```json
        {...}
        ```

    instead of plain JSON.

    This function removes those markdown markers first.
    """

    response_text = response_text.strip()


    # Remove ```json
    if response_text.startswith("```json"):

        response_text = response_text[7:]


    # Remove ```
    elif response_text.startswith("```"):

        response_text = response_text[3:]


    # Remove ending ```
    if response_text.endswith("```"):

        response_text = response_text[:-3]


    response_text = response_text.strip()


    # Convert JSON text into Python dictionary
    return json.loads(
        response_text
    )


# =========================================================
# Main Agent
# =========================================================

async def main():
    """
    Complete flow:

        User
          ↓
        Gemini
          ↓
        Chooses MCP tool
          ↓
        MCP Client
          ↓
        MCP Server
          ↓
        Calculator tool
          ↓
        Tool result
    """


    # -----------------------------------------------------
    # Authentication
    # -----------------------------------------------------
    #
    # Your Calculator MCP server requires:
    #
    # Authorization: Bearer <token>
    #
    # So agent.py must send the same token that
    # your normal client.py sends.
    # -----------------------------------------------------

    headers = {
        "Authorization":
            f"Bearer {MCP_API_TOKEN}"
    }


    # -----------------------------------------------------
    # Create authenticated HTTP client
    # -----------------------------------------------------

    async with httpx.AsyncClient(
        headers=headers
    ) as http_client:


        print(
            "\nConnecting to MCP server..."
        )


        # -------------------------------------------------
        # Connect using Streamable HTTP
        # -------------------------------------------------

        async with streamable_http_client(
            SERVER_URL,
            http_client=http_client
        ) as streams:


            # Get MCP read/write streams
            read_stream, write_stream, *_ = streams


            # -------------------------------------------------
            # Create MCP Client Session
            # -------------------------------------------------

            async with ClientSession(
                read_stream,
                write_stream,
            ) as session:


                # =============================================
                # 1. Initialize MCP
                # =============================================

                await session.initialize()

                print(
                    "\nConnected to MCP server."
                )


                # =============================================
                # 2. Get available MCP tools
                # =============================================

                result = await session.list_tools()


                print(
                    "\nAvailable MCP Tools:"
                )


                for tool in result.tools:

                    print(
                        "-",
                        tool.name
                    )


                # =============================================
                # 3. User Question
                # =============================================

                question = (
                    "What is 25 + 35?"
                )


                print(
                    "\nUser:"
                )

                print(
                    question
                )


                # =============================================
                # 4. Gemini decides which tool to use
                # =============================================

                agent_response = await ask_agent(
                    question,
                    result.tools,
                )


                print(
                    "\nGemini Agent Decision:"
                )

                print(
                    agent_response
                )


                # =============================================
                # 5. Convert Gemini JSON → Python dictionary
                # =============================================

                decision = parse_agent_decision(
                    agent_response
                )


                # Extract selected tool
                tool_name = decision[
                    "tool"
                ]


                # Extract tool arguments
                arguments = decision[
                    "arguments"
                ]


                print(
                    "\nSelected MCP Tool:"
                )

                print(
                    tool_name
                )


                print(
                    "\nArguments:"
                )

                print(
                    arguments
                )


                # =============================================
                # 6. Execute the MCP Tool
                # =============================================
                #
                # Gemini decided WHAT should happen.
                #
                # The MCP client now actually calls
                # the MCP server tool.
                # =============================================

                tool_result = await session.call_tool(
                    tool_name,
                    arguments=arguments,
                )


                # =============================================
                # 7. Display MCP Tool Result
                # =============================================

                print(
                    "\nMCP Tool Result:"
                )

                print(
                    tool_result
                )


                print(
                    "\nTool Result Content:"
                )


                for item in tool_result.content:

                    text = getattr(
                        item,
                        "text",
                        None
                    )

                    if text:

                        print(
                            text
                        )


# =========================================================
# Run Agent
# =========================================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )