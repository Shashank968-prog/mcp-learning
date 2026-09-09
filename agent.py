
# =========================================================
# MCP AI AGENT
#
# Architecture:
#
#                    USER
#                      |
#                      v
#                MAIN AGENT
#                Gemini LLM
#                      |
#          +-----------+-----------+
#          |           |           |
#          v           v           v
#     Calculator   Healthcare   Explanation
#       Agent        Agent        Agent
#          |           |
#          |           v
#          |      search_healthcare
#          |           |
#          +-----------+
#                      |
#                      v
#                  MCP SERVER
#                      |
#                      v
#                 MCP TOOLS
#
# Healthcare flow:
#
# User Question
#      |
#      v
# Main Agent
#      |
#      v
# Healthcare Agent
#      |
#      v
# search_healthcare MCP Tool
#      |
#      v
# RAG Retriever
#      |
#      v
# ChromaDB
#      |
#      v
# Relevant Chunks
#      |
#      v
# Healthcare Agent
#      |
#      v
# Final Answer
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

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
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
# Convert MCP Tools to Gemini Format
# =========================================================

def convert_mcp_tools(mcp_tools):

    tools = []

    for tool in mcp_tools:

        tools.append(
            {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.input_schema,
            }
        )

    return tools


# =========================================================
# Parse Gemini JSON Response
# =========================================================

def parse_json_response(response_text):

    response_text = response_text.strip()

    # Remove ```json
    if response_text.startswith("```json"):

        response_text = response_text[7:]

    # Remove ``` if Gemini did not specify json
    elif response_text.startswith("```"):

        response_text = response_text[3:]

    # Remove closing ```
    if response_text.endswith("```"):

        response_text = response_text[:-3]

    response_text = response_text.strip()

    return json.loads(response_text)


# =========================================================
# MAIN ROUTER AGENT
# =========================================================

async def route_agent(question):
    """
    Main agent decides which specialized agent
    should handle the user's request.
    """

    prompt = f"""
You are the main routing agent.

Your job is to decide which specialized agent
should handle the user's request.

Available specialized agents:

1. calculator_agent
   - Handles mathematical calculations.
   - Uses MCP calculator tools such as:
     add, subtract, multiply, divide, percentage.

2. healthcare_agent
   - Handles healthcare-related questions.
   - Uses the MCP search_healthcare tool.
   - The search_healthcare tool searches a healthcare
     RAG knowledge base.

3. explanation_agent
   - Explains MCP, RAG, AI, programming, and
     other technical concepts.
   - Does not need calculator tools.

User question:

{question}

Return ONLY valid JSON.

For calculator questions:

{{
    "handoff": "calculator_agent",
    "task": "the task for the calculator agent"
}}

For healthcare questions:

{{
    "handoff": "healthcare_agent",
    "task": "the healthcare question"
}}

For explanation or technical questions:

{{
    "handoff": "explanation_agent",
    "task": "the explanation task"
}}

Important:

- Return only JSON.
- Do not use Markdown.
- Choose healthcare_agent for questions about
  diseases, symptoms, prevention, diabetes,
  healthcare, medical knowledge, etc.
"""

    response = await asyncio.to_thread(
        gemini.models.generate_content,
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return response.text


# =========================================================
# EXPLANATION AGENT
# =========================================================

async def explanation_agent(task):
    """
    Specialized agent for explaining concepts.
    """

    prompt = f"""
You are an explanation agent.

Explain the following topic clearly and simply.

Task:

{task}

Give a useful explanation suitable for someone
learning AI, RAG, MCP, or programming.
"""

    response = await asyncio.to_thread(
        gemini.models.generate_content,
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return response.text


# =========================================================
# MCP TOOL AGENT LOOP
# =========================================================

async def run_agent_loop(
    session,
    question,
    mcp_tools,
    agent_type="general",
    max_iterations=5
):
    """
    Run a specialized agent.

    The agent:

        Question
            |
            v
         Gemini
            |
            v
       MCP Tool
            |
            v
       MCP Server
            |
            v
        Tool Result
            |
            v
         Gemini
            |
            v
       Final Answer
    """

    # Convert MCP tools to Gemini-readable definitions

    tool_definitions = convert_mcp_tools(
        mcp_tools
    )

    # Start conversation

    conversation = question

    # =====================================================
    # Agent Loop
    # =====================================================

    for iteration in range(max_iterations):

        print(
            f"\n========== {agent_type.upper()} AGENT "
            f"ITERATION {iteration + 1} =========="
        )

        # -------------------------------------------------
        # Build prompt
        # -------------------------------------------------

        prompt = f"""
You are a {agent_type} AI agent.

You are connected to an MCP server.

Available MCP tools:

{json.dumps(tool_definitions, indent=2)}

User request:

{conversation}

Your job is to solve the user's request.

IMPORTANT RULES:

1. If an MCP tool is required, use the appropriate
   MCP tool.

2. For healthcare questions, use the
   search_healthcare MCP tool to retrieve
   information from the healthcare RAG knowledge base.

3. Do not invent healthcare information.

4. For calculator questions, use the calculator
   MCP tools instead of calculating yourself.

5. After receiving an MCP tool result, determine
   whether the user's request is complete.

6. If the task is complete, return:

{{
    "final_answer": "your final answer"
}}

7. If another MCP tool is required, return:

{{
    "tool": "tool_name",
    "arguments": {{
        "argument": "value"
    }}
}}

8. Return ONLY valid JSON.

9. Do not return Markdown.

Current conversation:

{conversation}
"""

        # -------------------------------------------------
        # Ask Gemini
        # -------------------------------------------------

        response = await asyncio.to_thread(
            gemini.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
        )

        print("\nGemini Decision:")
        print(response.text)

        # -------------------------------------------------
        # Parse Gemini decision
        # -------------------------------------------------

        decision = parse_json_response(
            response.text
        )

        # =================================================
        # FINAL ANSWER
        # =================================================

        if "final_answer" in decision:

            final_answer = decision[
                "final_answer"
            ]

            print("\nFinal Answer:")
            print(final_answer)

            return final_answer

        # =================================================
        # MCP TOOL
        # =================================================

        if "tool" not in decision:

            raise RuntimeError(
                "Gemini response did not contain "
                "'tool' or 'final_answer'."
            )

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
        # Verify selected tool exists
        # -------------------------------------------------

        available_tool_names = [
            tool.name
            for tool in mcp_tools
        ]

        if tool_name not in available_tool_names:

            raise RuntimeError(
                f"Gemini selected unknown MCP tool: "
                f"{tool_name}"
            )

        # =================================================
        # Call MCP Tool
        # =================================================

        print("\nCalling MCP Server...")

        tool_result = await session.call_tool(
            tool_name,
            arguments=arguments,
        )

        print("\nMCP Tool Result:")
        print(tool_result)

        # =================================================
        # Extract MCP Text Result
        # =================================================

        result_text = ""

        for item in tool_result.content:

            text = getattr(
                item,
                "text",
                None
            )

            if text:

                result_text += (
                    text + "\n"
                )

        result_text = result_text.strip()

        print("\nMCP Result Text:")
        print(result_text)

        # =================================================
        # Give MCP Result Back to Gemini
        # =================================================

        conversation += f"""

MCP tool used:

{tool_name}

Arguments:

{arguments}

MCP tool result:

{result_text}

The MCP tool has completed.

Now decide what to do next.

If the user's task is complete,
return a final_answer.

Otherwise,
select another MCP tool.
"""

    # =====================================================
    # Maximum Iterations
    # =====================================================

    return (
        "Agent stopped because maximum "
        "iterations were reached."
    )


# =========================================================
# AGENT HANDOFF
# =========================================================

async def run_handoff(
    session,
    question,
    mcp_tools
):
    """
    Main agent routes the question to
    the appropriate specialized agent.
    """

    print(
        "\n========== MAIN AGENT =========="
    )

    # =====================================================
    # Ask Main Router
    # =====================================================

    router_response = await route_agent(
        question
    )

    print("\nMain Agent Decision:")
    print(router_response)

    # =====================================================
    # Parse Router Decision
    # =====================================================

    decision = parse_json_response(
        router_response
    )

    handoff = decision["handoff"]

    task = decision["task"]

    print("\nHandoff Target:")
    print(handoff)

    print("\nHandoff Task:")
    print(task)

    # =====================================================
    # Calculator Agent
    # =====================================================

    if handoff == "calculator_agent":

        print(
            "\nHanding off to Calculator Agent..."
        )

        return await run_agent_loop(
            session=session,
            question=task,
            mcp_tools=mcp_tools,
            agent_type="calculator",
        )

    # =====================================================
    # Healthcare Agent
    # =====================================================

    elif handoff == "healthcare_agent":

        print(
            "\nHanding off to Healthcare Agent..."
        )

        return await run_agent_loop(
            session=session,
            question=task,
            mcp_tools=mcp_tools,
            agent_type="healthcare",
        )

    # =====================================================
    # Explanation Agent
    # =====================================================

    elif handoff == "explanation_agent":

        print(
            "\nHanding off to Explanation Agent..."
        )

        result = await explanation_agent(
            task
        )

        print(
            "\nExplanation Agent Result:"
        )

        print(result)

        return result

    # =====================================================
    # Unknown Agent
    # =====================================================

    else:

        raise ValueError(
            f"Unknown handoff target: {handoff}"
        )


# =========================================================
# MAIN
# =========================================================

async def main():

    """
    Complete MCP Agent flow.

    User
      |
      v
    Main Agent
      |
      +-------------------+
      |         |         |
      v         v         v
    Calc    Healthcare  Explanation
    Agent      Agent       Agent
      |         |
      |         v
      |    search_healthcare
      |         |
      |         v
      |       RAG
      |         |
      +---------+
                |
                v
           MCP Server
    """

    # =====================================================
    # MCP Authentication
    # =====================================================

    headers = {
        "Authorization": (
            f"Bearer {MCP_API_TOKEN}"
        )
    }

    # =====================================================
    # Authenticated HTTP Client
    # =====================================================

    async with httpx.AsyncClient(
        headers=headers
    ) as http_client:

        print(
            "\nConnecting to MCP server..."
        )

        # =================================================
        # Connect to MCP Server
        # =================================================

        async with streamable_http_client(
            SERVER_URL,
            http_client=http_client,
        ) as streams:

            read_stream = streams[0]
            write_stream = streams[1]

            # =================================================
            # Create MCP Session
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
                # 2. Get MCP Tools
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
                # 3. Get MCP Resources
                # =============================================

                resources = (
                    await session.list_resources()
                )

                print(
                    "\nAvailable MCP Resources:"
                )

                for resource in resources.resources:

                    print(
                        "-",
                        resource.uri
                    )

                # =============================================
                # 4. Read Healthcare Resource
                # =============================================

                healthcare_resource = (
                    await session.read_resource(
                        "healthcare://knowledge"
                    )
                )

                print(
                    "\n========== Healthcare Resource =========="
                )

                for content in (
                    healthcare_resource.contents
                ):

                    text = getattr(
                        content,
                        "text",
                        None
                    )

                    if text:

                        print(
                            text[:1000]
                        )

                # =============================================
                # 5. User Question
                # =============================================

                question = (
                    "What are the common symptoms "
                    "of diabetes?"
                )

                print(
                    "\nUser:"
                )

                print(question)

                # =============================================
                # 6. Main Agent + Handoff
                # =============================================

                final_answer = await run_handoff(
                    session=session,
                    question=question,
                    mcp_tools=result.tools,
                )

                # =============================================
                # 7. Final Output
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

                print(final_answer)


# =========================================================
# Run Agent
# =========================================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )
