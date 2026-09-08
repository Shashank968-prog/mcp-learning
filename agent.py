# =========================================================
# MCP AI Agent
# Gemini decides which MCP tool to use
# =========================================================


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

load_dotenv()

# Gemini API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# MCP authentication token
MCP_API_TOKEN = os.getenv("MCP_API_TOKEN")


# =========================================================
# Validate Environment Variables
# =========================================================

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY was not found in .env"
    )

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
    Convert MCP Tool objects into dictionaries
    that Gemini can understand.

    Each MCP tool contains:

    - name
    - description
    - input_schema

    input_schema describes the arguments
    required by the tool.
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
# Ask Gemini What To Do
# =========================================================

async def ask_agent(question, mcp_tools):
    """
    Ask Gemini to decide what the agent should do next.

    Gemini can return:

    1. An MCP tool to execute.

    OR

    2. A final answer.

    Gemini only makes the decision.

    Gemini does NOT execute the MCP tool.
    """

    # Convert MCP tools into a Gemini-readable format
    tool_definitions = convert_mcp_tools(
        mcp_tools
    )

    # -----------------------------------------------------
    # Build prompt for Gemini
    # -----------------------------------------------------

    prompt = f"""
You are a calculator AI agent.

Your job is to solve the user's request by using
the available MCP calculator tools.

Available MCP tools:

{json.dumps(tool_definitions, indent=2)}

User request:

{question}

You must decide what to do next.

If you need to use an MCP tool,
return ONLY valid JSON in this format:

{{
    "tool": "tool_name",
    "arguments": {{
        "argument_name": value
    }}
}}

If the task is already complete,
return ONLY valid JSON in this format:

{{
    "final_answer": "your answer"
}}

Important rules:

- Do not calculate the answer yourself when an MCP
  calculator tool is required.
- Use the MCP calculator tool.
- Return ONLY valid JSON.
- Do not use Markdown.
"""

    # -----------------------------------------------------
    # Call Gemini
    # -----------------------------------------------------

    # generate_content() is synchronous.
    # Running it in a separate thread prevents it
    # from blocking the asynchronous MCP event loop.

    response = await asyncio.to_thread(
        gemini.models.generate_content,
        model="gemini-2.5-flash",
        contents=prompt,
    )

    # Gemini returns its decision as text
    return response.text


# =========================================================
# Clean Gemini JSON Response
# =========================================================

def parse_agent_decision(response_text):
    """
    Convert Gemini's JSON response into a Python dictionary.

    Gemini may sometimes return JSON inside Markdown
    code fences.

    Example:

    ```json
    {
        "tool": "add",
        "arguments": {
            "a": 25,
            "b": 35
        }
    }
    ```

    This function removes those code fences.
    """

    response_text = response_text.strip()

    # Remove ```json
    if response_text.startswith("```json"):
        response_text = response_text[7:]

    # Remove ```
    elif response_text.startswith("```"):
        response_text = response_text[3:]

    # Remove closing ```
    if response_text.endswith("```"):
        response_text = response_text[:-3]

    response_text = response_text.strip()

    # Convert JSON text into Python dictionary
    return json.loads(response_text)


# =========================================================
# Agent Loop
# =========================================================

async def run_agent_loop(
    session,
    question,
    mcp_tools,
    max_iterations=5
):
    """
    Run the AI agent repeatedly.

    Flow:

        User question
              ↓
           Gemini
              ↓
        Select MCP tool
              ↓
         MCP Server
              ↓
          Tool Result
              ↓
           Gemini
              ↓
        Select next action
              ↓
         Final Answer

    max_iterations prevents the agent from
    running forever.
    """

    # Start conversation with user's question
    conversation = question

    # -----------------------------------------------------
    # Agent Loop
    # -----------------------------------------------------

    for iteration in range(max_iterations):

        print(
            f"\n========== Agent Iteration "
            f"{iteration + 1} =========="
        )

        # -------------------------------------------------
        # Ask Gemini what to do next
        # -------------------------------------------------

        agent_response = await ask_agent(
            conversation,
            mcp_tools
        )

        print("\nGemini Decision:")
        print(agent_response)

        # -------------------------------------------------
        # Convert Gemini JSON into Python dictionary
        # -------------------------------------------------

        decision = parse_agent_decision(
            agent_response
        )

        # -------------------------------------------------
        # Check whether Gemini has finished
        # -------------------------------------------------

        if decision.get("final_answer"):

            print("\nFinal Answer:")
            print(
                decision["final_answer"]
            )

            return decision["final_answer"]

        # -------------------------------------------------
        # Make sure Gemini selected a tool
        # -------------------------------------------------

        if "tool" not in decision:

            raise RuntimeError(
                "Gemini response did not contain "
                "'tool' or 'final_answer'."
            )

        # -------------------------------------------------
        # Get selected MCP tool
        # -------------------------------------------------

        tool_name = decision["tool"]

        arguments = decision.get(
            "arguments",
            {}
        )

        print("\nSelected MCP Tool:")
        print(tool_name)

        print("\nArguments:")
        print(arguments)

        # -------------------------------------------------
        # Execute MCP Tool
        # -------------------------------------------------

        tool_result = await session.call_tool(
            tool_name,
            arguments=arguments,
        )

        print("\nMCP Tool Result:")
        print(tool_result)

        # -------------------------------------------------
        # Extract readable text from MCP result
        # -------------------------------------------------

        result_text = ""

        for item in tool_result.content:

            text = getattr(
                item,
                "text",
                None
            )

            if text:
                result_text += text + "\n"

        result_text = result_text.strip()

        print("\nMCP Result Text:")
        print(result_text)

        # -------------------------------------------------
        # Give MCP result back to Gemini
        # -------------------------------------------------

        conversation += f"""

MCP tool used:
{tool_name}

Arguments:
{arguments}

MCP tool result:
{result_text}

The MCP tool has completed its operation.

Now decide what to do next.

If the user's task is complete,
return a final_answer.

Otherwise, choose another MCP tool.
"""

    # -----------------------------------------------------
    # Maximum Iterations Reached
    # -----------------------------------------------------

    return (
        "Agent stopped because maximum iterations "
        "were reached."
    )


# =========================================================
# Main Agent Router
# =========================================================

# =========================================================
# Main Agent Router
# =========================================================

async def route_agent(question):
    """
    The main agent decides which specialized agent
    should handle the user's request.
    """

    prompt = f"""
You are the main routing agent.

Decide which specialized agent should handle
the user's request.

Available agents:

1. calculator_agent
   - Handles mathematical calculations
   - Uses MCP calculator tools

2. explanation_agent
   - Explains MCP and AI concepts
   - Does not use calculator tools

User question:

{question}

Return ONLY JSON.

For calculator questions:

{{
    "handoff": "calculator_agent",
    "task": "the task to give to the calculator agent"
}}

For explanation questions:

{{
    "handoff": "explanation_agent",
    "task": "the task to give to the explanation agent"
}}
"""

    response = gemini.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return response.text

# =========================================================
# Explanation Agent
# =========================================================

async def explanation_agent(task):
    """
    Specialized agent for explaining concepts.
    """

    prompt = f"""
You are an explanation agent.

Your job is to explain MCP and AI concepts
clearly and simply.

Task:

{task}

Give a clear explanation suitable for someone
learning MCP.
"""

    response = gemini.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return response.text


# =========================================================
# Agent Handoff
# =========================================================

async def run_handoff(session,question, mcp_tools):
    """
    Main agent decides which specialized agent
    should handle the user's request.
    """

    print("\n========== Main Agent ==========")

    # Ask the main agent which specialized
    # agent should handle the request.
    router_response = await route_agent(question)

    print("\nMain Agent Decision:")
    print(router_response)

    

    # Get the selected agent.
    clean_response = router_response.strip()

    if clean_response.startswith("```json"):
        clean_response = clean_response[7:]

    if clean_response.endswith("```"):
        clean_response = clean_response[:-3]

    clean_response = clean_response.strip()

    decision = json.loads(clean_response)

    handoff = decision["handoff"]

    print("\nHandoff Target:")
    print(handoff)
    # Get the task that should be given
    # to the selected agent.
    task = decision["task"]

    print("\nHandoff Target:")
    print(handoff)

    print("\nHandoff Task:")
    print(task)

    # -----------------------------------------------------
    # Handoff to Calculator Agent
    # -----------------------------------------------------

    if handoff == "calculator_agent":

        print("\nHanding off to Calculator Agent...")

        return await run_agent_loop(
            session=session,
            question=task,
            mcp_tools=mcp_tools,
        )

    # -----------------------------------------------------
    # Handoff to Explanation Agent
    # -----------------------------------------------------

    elif handoff == "explanation_agent":

        print("\nHanding off to Explanation Agent...")

        result = await explanation_agent(task)

        print("\nExplanation Agent Result:")
        print(result)

        return result

    # -----------------------------------------------------
    # Unknown agent
    # -----------------------------------------------------

    else:

        raise ValueError(
            f"Unknown handoff target: {handoff}"
        )
    


# =========================================================
# Main Agent
# =========================================================


async def main():
    """
    Complete Agent + MCP flow:

        User
          ↓
        Gemini
          ↓
      Agent Decision
          ↓
       MCP Client
          ↓
       MCP Server
          ↓
      Calculator Tool
          ↓
       Tool Result
          ↓
        Gemini
          ↓
      Final Answer
    """

    # =====================================================
    # MCP Authentication
    # =====================================================

    # Your MCP server requires:

    # Authorization: Bearer <token>

    headers = {
        "Authorization": f"Bearer {MCP_API_TOKEN}"
    }

    # =====================================================
    # Create Authenticated HTTP Client
    # =====================================================

    async with httpx.AsyncClient(
        headers=headers
    ) as http_client:

        print(
            "\nConnecting to MCP server..."
        )

        # =================================================
        # Connect using Streamable HTTP
        # =================================================

        async with streamable_http_client(
            SERVER_URL,
            http_client=http_client
        ) as streams:

            # Some MCP versions return additional
            # transport information.
            read_stream = streams[0]
            write_stream = streams[1]

            # =================================================
            # Create MCP Client Session
            # =================================================

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
                # 2. Get Available MCP Tools
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

                question="What is 25 + 35?"

                print("\nUser:")
                print(question)

                #start agent

                await run_handoff(
                    session,
                    question,
                    result.tools,
                )

                # =============================================
                # 4. Run Agent Loop
                # =============================================

                final_answer = await run_agent_loop(
                    session,
                    question,
                    result.tools,
                    max_iterations=5
                )

                # =============================================
                # 5. Display Final Answer
                # =============================================

                print(
                    "\n========================================"
                )

                print(
                    "Agent Finished"
                )

                print(
                    "========================================"
                )

                print(
                    "\nFinal Answer:"
                )

                print(
                    final_answer
                )


# =========================================================
# Run Agent
# =========================================================

if __name__ == "__main__":
    asyncio.run(main())