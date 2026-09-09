import os

from dotenv import load_dotenv
from google import genai

from rag.loader import load_document, split_into_chunks
# =========================================================
# Load environment variables
# =========================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY was not found."
    )


# =========================================================
# Create Gemini client
# =========================================================

client = genai.Client(
    api_key=GEMINI_API_KEY
)


# =========================================================
# Generate embedding for one chunk
# =========================================================

def create_embedding(text):

    response = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
    )

    return response.embeddings[0].values


# =========================================================
# Create embeddings for all chunks
# =========================================================

def create_embeddings(chunks):

    embeddings = []

    for i, chunk in enumerate(chunks):

        print(f"Creating embedding {i + 1}/{len(chunks)}")

        vector = create_embedding(chunk)

        embeddings.append(vector)

    return embeddings


# =========================================================
# Test embedding pipeline
# =========================================================

if __name__ == "__main__":

    # Load healthcare document
    document = load_document()

    print("Document loaded.")
    print("Characters:", len(document))

    # Split document into chunks
    chunks = split_into_chunks(document)

    print("Number of chunks:", len(chunks))

    # Create embeddings
    embeddings = create_embeddings(chunks)

    print("\nEmbedding generation completed.")

    # Show information about first embedding
    print("\nFirst chunk:")
    print(chunks[0])

    print("\nFirst embedding:")
    print(embeddings[0])

    print("\nEmbedding dimensions:")
    print(len(embeddings[0]))

    # =========================================================
# Ask Gemini
# =========================================================

async def ask_gemini(prompt: str):

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return response.text