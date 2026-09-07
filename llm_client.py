import os

from google import genai
from dotenv import load_dotenv


# =========================================================
# Load environment variables
# =========================================================

load_dotenv()

# Read Gemini API key from .env
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY was not found in the environment."
    )


# =========================================================
# Create Gemini client
# =========================================================

client = genai.Client(
    api_key=GEMINI_API_KEY
)


# =========================================================
# Function to ask Gemini
# =========================================================

async def ask_gemini(prompt: str) -> str:

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return response.text


# =========================================================
# Test Gemini directly
# =========================================================

async def main():

    response = await ask_gemini(
        "Explain MCP in one simple sentence."
    )

    print("\nGemini Response:")
    print(response)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())