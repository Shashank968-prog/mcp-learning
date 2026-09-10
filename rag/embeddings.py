import os

from dotenv import load_dotenv
from google import genai

from rag.loader import load_documents, split_into_chunks


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
# Create embeddings for multiple chunks
# =========================================================

def create_embeddings(chunks):

    embeddings = []

    for i, chunk in enumerate(chunks):

        print(
            f"Creating embedding {i + 1}/{len(chunks)}"
        )

        vector = create_embedding(chunk)

        embeddings.append(vector)

    return embeddings


# =========================================================
# Ask Gemini
# =========================================================

async def ask_gemini(prompt: str):

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return response.text


# =========================================================
# Test embedding pipeline
# =========================================================

if __name__ == "__main__":

    documents = load_documents()

    print(
        f"Documents loaded: {len(documents)}"
    )

    for document in documents:

        source = document["source"]
        content = document["content"]

        print("\n================================")
        print(f"Source: {source}")
        print(
            f"Characters: {len(content)}"
        )

        chunks = split_into_chunks(content)

        print(
            f"Number of chunks: {len(chunks)}"
        )

        embeddings = create_embeddings(
            chunks
        )

        print(
            f"Embeddings created: {len(embeddings)}"
        )

        print(
            f"Embedding dimensions: "
            f"{len(embeddings[0])}"
        )