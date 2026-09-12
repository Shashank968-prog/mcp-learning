
import asyncio

from mcp.server.mcpserver import MCPServer


mcp = MCPServer(
    name="Calculator Server"
)


@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b


@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract the second number from the first."""
    return a - b


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b


@mcp.tool()
def divide(a: float, b: float) -> float:
    """Divide the first number by the second."""
    if b == 0:
        raise ValueError("Cannot divide by zero.")

    return a / b


async def main():
    await mcp.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())