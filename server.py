import asyncio

from mcp.server.mcpserver import MCPServer, Context


# -------------------------
# Create MCP Server
# -------------------------

mcp = MCPServer("Calculator")


# -------------------------
# Calculator Tools
# -------------------------

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@mcp.tool()
def subtract(a: int, b: int) -> int:
    """Subtract two numbers."""
    return a - b


@mcp.tool()
def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b


@mcp.tool()
def divide(a: float, b: float) -> float:
    """Divide two numbers."""

    if b == 0:
        raise ValueError("Cannot divide by zero")

    return a / b


# -------------------------
# Unstable Operation
# Used for Retry Testing
# -------------------------

attempt_count = 0


@mcp.tool()
async def unstable_operation() -> str:
    """Simulates a temporary failure."""

    global attempt_count

    attempt_count += 1

    print(f"Server: attempt {attempt_count}")

    # Fail first two attempts
    if attempt_count < 3:
        raise RuntimeError("Temporary failure")

    # Succeed on third attempt
    return "Operation succeeded!"


# -------------------------
# Long Calculation
# Progress + Cancellation
# -------------------------

@mcp.tool()
async def long_calculation(context: Context) -> str:
    """Demonstrate MCP progress notifications and cancellation."""

    try:

        for progress in range(0, 101, 20):

            await context.report_progress(
                progress=progress,
                total=100
            )

            print(f"Progress: {progress}%")

            await asyncio.sleep(1)

        return "Calculation completed!"

    except asyncio.CancelledError:

        print("Server: calculation was cancelled")

        # Pass cancellation to MCP
        raise


# -------------------------
# Resource
# -------------------------

@mcp.resource("calculator://instructions")
def calculator_instructions() -> str:
    """Instructions for using the calculator."""

    return """
This calculator supports four operations:

1. Addition
2. Subtraction
3. Multiplication
4. Division
"""


# -------------------------
# Prompt
# -------------------------

@mcp.prompt()
def calculator_help(operation: str) -> str:
    """Provide instructions for using a calculator operation."""

    return f"""
You are a helpful calculator assistant.

The user wants help with: {operation}

Explain how to perform this operation and give a simple example.
"""


# -------------------------
# Start MCP Server
# -------------------------

if __name__ == "__main__":

    mcp.run(
        transport="streamable-http"
    )