import asyncio
import logging
import os
import time
import uuid
from collections import defaultdict

from dotenv import load_dotenv

from mcp.server.mcpserver import MCPServer, Context
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.server import ServerMiddleware


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
# Request Logging Middleware
# =========================================================

class RequestLoggingMiddleware:
    async def __call__(self, ctx, call_next):
        logger.info(
            "MCP request started: method=%s request_id=%s",
            ctx.method,
            ctx.request_id
        )
        #start the timer

        start_time=time.perf_counter()

        try:
            result=await call_next(ctx)
            duration=time.perf_counter()-start_time
            logger.info(
                "MCP request completed: method=%s request_id=%s",
                ctx.method,
                ctx.request_id
            )
            return result
        except Exception:
            # Calculate duration even when the request fails
            duration = time.perf_counter() - start_time
            logger.exception(
                "MCP request failed: method=%s request_id=%s",
                ctx.method,
                ctx.request_id
            )
            raise

#==========================================================
#RateLimitMiddleWare
#==========================================================

class RateLimitMiddleware:
    def __init__(self, max_requests=100, window_seconds=60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

        # Store request timestamps for each client
        self.requests = defaultdict(list)

    async def __call__(self, ctx, call_next):
        # Get the client identifier
        client_id = "unknown"

        # Check if authentication information is available
        access_token = get_access_token()

        if access_token is not None:
            client_id = access_token.client_id

        current_time = time.monotonic()

        # Get previous requests from this client
        request_times = self.requests[client_id]

        # Remove requests outside the current time window
        request_times[:] = [
            timestamp
            for timestamp in request_times
            if current_time - timestamp < self.window_seconds
        ]

        # Check whether the client has reached the limit
        if len(request_times) >= self.max_requests:
            logger.warning(
                "Rate limit exceeded: client=%s requests=%s",
                client_id,
                len(request_times)
            )

            raise PermissionError(
                "Rate limit exceeded. Try again later."
            )

        # Record this request
        request_times.append(current_time)

        logger.info(
            "Rate limit check passed: client=%s requests=%s/%s",
            client_id,
            len(request_times),
            self.max_requests
        )

        # Continue processing the request
        return await call_next(ctx)


#==========================================================
#RequestTracingMiddleware
#==========================================================

class RequestTracingMiddleware:
    async def __call__(self, ctx, call_next):
        # Generate a unique ID for this request
        trace_id = str(uuid.uuid4())

        logger.info(
            "[%s] Request started: method=%s request_id=%s",
            trace_id,
            ctx.method,
            ctx.request_id
        )

        try:
            # Continue processing the request
            result = await call_next(ctx)

            logger.info(
                "[%s] Request completed: method=%s request_id=%s",
                trace_id,
                ctx.method,
                ctx.request_id
            )
            return result
        except Exception:
            logger.exception(
                "[%s] Request failed: method=%s request_id=%s",
                trace_id,
                ctx.method,
                ctx.request_id
            )
            raise

# =========================================================
# Metrics
# =========================================================

class MetricsMiddleware:
    def __init__(self):
        self.total_requests=0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_duration = 0.0
    
    async def __call__(self, ctx, call_next):
        self.total_requests += 1

        start_time = time.perf_counter()

        try:
            result = await call_next(ctx)

            self.successful_requests += 1

            return result

        except Exception:
            self.failed_requests += 1
            raise

        finally:
            duration = time.perf_counter() - start_time
            self.total_duration += duration

            average_duration = (
                self.total_duration / self.total_requests
            )
            logger.info(
                "Metrics: total=%s successful=%s failed=%s "
                "total_duration=%.2fs average_duration=%.2fs",
                self.total_requests,
                self.successful_requests,
                self.failed_requests,
                self.total_duration,
                average_duration
            )

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
    token_verifier=SimpleTokenVerifier(),
    middleware=[
        RequestLoggingMiddleware(),
        RateLimitMiddleware(
            max_requests=100,
            window_seconds=60
        ),
        RequestTracingMiddleware(),
        MetricsMiddleware()
    ]
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