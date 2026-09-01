import asyncio
import logging
import os

from dotenv import load_dotenv

from mcp.server.mcpserver import MCPServer, Context
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.auth.middleware.auth_context import get_access_token


# =========================================================
# Environment Variables
# =========================================================

load_dotenv()

MCP_API_TOKEN = os.getenv("MCP_API_TOKEN")

if not MCP_API_TOKEN:
    raise RuntimeError(
        "MCP_API_TOKEN not found in .env"
    )


# =========================================================
# Logging Configuration
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# =========================================================
# Authentication
# =========================================================

class SimpleTokenVerifier:

    async def verify_token(
        self,
        token: str
    ) -> AccessToken | None:

        logger.info(
            "Verifying access token"
        )

        # Check token
        if token != MCP_API_TOKEN:

            logger.warning(
                "Invalid access token"
            )

            return None

        logger.info(
            "Access token is valid"
        )

        # Return information about authenticated client
        return AccessToken(
            token=token,
            client_id="calculator-client",
            scopes=["calculator"]
        )


# =========================================================
# Authentication Configuration
# =========================================================

auth_settings = AuthSettings(
    issuer_url="http://127.0.0.1:8000",
    resource_server_url="http://127.0.0.1:8000"
)


# =========================================================
# Authorization Helper
# =========================================================

def require_scope(
    required_scope: str
):

    # Get the access token of the current request
    access_token = get_access_token()

    # Authentication check
    if access_token is None:

        logger.warning(
            "No authenticated access token"
        )

        raise PermissionError(
            "Authentication required"
        )

    # Authorization check
    if required_scope not in access_token.scopes:

        logger.warning(
            "Authorization failed: "
            "client=%s required_scope=%s available_scopes=%s",
            access_token.client_id,
            required_scope,
            access_token.scopes
        )

        raise PermissionError(
            f"Missing required scope: {required_scope}"
        )

    logger.info(
        "Authorization successful: "
        "client=%s scope=%s",
        access_token.client_id,
        required_scope
    )


# =========================================================
# MCP Server
# =========================================================

mcp = MCPServer(
    "Calculator",
    auth=auth_settings,
    token_verifier=SimpleTokenVerifier()
)


# =========================================================
# Calculator Tools
# =========================================================

@mcp.tool()
def add(
    a: int,
    b: int
) -> int:

    # Authorization
    require_scope("calculator")

    logger.info(
        "add() called with a=%s, b=%s",
        a,
        b
    )

    return a + b


@mcp.tool()
def subtract(
    a: int,
    b: int
) -> int:

    # Authorization
    require_scope("calculator")

    logger.info(
        "subtract() called with a=%s, b=%s",
        a,
        b
    )

    return a - b


@mcp.tool()
def multiply(
    a: int,
    b: int
) -> int:

    # Authorization
    require_scope("calculator")

    logger.info(
        "multiply() called with a=%s, b=%s",
        a,
        b
    )

    return a * b


@mcp.tool()
def divide(
    a: float,
    b: float
) -> float:

    # Authorization
    require_scope("calculator")

    logger.info(
        "divide() called with a=%s, b=%s",
        a,
        b
    )

    if b == 0:

        logger.error(
            "Division by zero"
        )

        raise ValueError(
            "Cannot divide by zero"
        )

    return a / b

# =========================================================
# Percentage Tool
# Input Validation
# =========================================================

@mcp.tool()
def percentage(
    value: float,
    percent: float
) -> float:

    # Authorization
    require_scope("calculator")

    logger.info(
        "percentage() called with value=%s, percent=%s",
        value,
        percent
    )

    # Validate percentage range
    if percent < 0 or percent > 100:

        logger.warning(
            "Invalid percentage: %s",
            percent
        )

        raise ValueError(
            "Percent must be between 0 and 100"
        )

    # Calculate percentage
    result = value * (percent / 100)

    logger.info(
        "Percentage result: %s",
        result
    )

    return result


# =========================================================
# Admin Tool
# =========================================================

@mcp.tool()
def admin_reset() -> str:

    # This tool requires admin permission
    require_scope("admin")

    logger.info(
        "Admin reset executed"
    )

    return "Calculator reset successfully!"


# =========================================================
# Unstable Operation
# Retry Testing
# =========================================================

attempt_count = 0


@mcp.tool()
async def unstable_operation() -> str:

    global attempt_count

    # Authorization
    require_scope("calculator")

    attempt_count += 1

    logger.info(
        "unstable_operation attempt %s",
        attempt_count
    )

    # Fail first two attempts
    if attempt_count < 3:

        logger.warning(
            "Temporary failure"
        )

        raise RuntimeError(
            "Temporary failure"
        )

    logger.info(
        "unstable_operation succeeded"
    )

    return "Operation succeeded!"


# =========================================================
# Long Calculation
# Progress + Cancellation
# =========================================================

@mcp.tool()
async def long_calculation(
    context: Context
) -> str:

    # Authorization
    require_scope("calculator")

    logger.info(
        "long_calculation started"
    )

    try:

        for progress in range(
            0,
            101,
            20
        ):

            await context.report_progress(
                progress=progress,
                total=100
            )

            logger.info(
                "Progress: %s%%",
                progress
            )

            await asyncio.sleep(1)

        logger.info(
            "long_calculation completed"
        )

        return "Calculation completed!"

    except asyncio.CancelledError:

        logger.warning(
            "long_calculation cancelled"
        )

        raise


# =========================================================
# Resource
# =========================================================

@mcp.resource(
    "calculator://instructions"
)
def calculator_instructions() -> str:

    logger.info(
        "calculator instructions requested"
    )

    return """
This calculator supports four operations:

1. Addition
2. Subtraction
3. Multiplication
4. Division
"""
# =========================================================
# Secure Resource Template
# =========================================================

@mcp.resource(
    "calculator://history/{filename}"
)
def calculator_history(
    filename: str
) -> str:

    logger.info(
        "Calculator history requested: %s",
        filename
    )

    return f"Calculator history for: {filename}"

# =========================================================
# Prompt
# =========================================================

@mcp.prompt()
def calculator_help(
    operation: str
) -> str:

    logger.info(
        "calculator_help requested: %s",
        operation
    )

    return f"""
You are a helpful calculator assistant.

The user wants help with: {operation}

Explain how to perform this operation
and give a simple example.
"""


# =========================================================
# Start MCP Server
# =========================================================

if __name__ == "__main__":

    logger.info(
        "Starting authenticated MCP server..."
    )

    mcp.run(
        transport="streamable-http"
    )