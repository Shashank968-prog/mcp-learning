import chromadb

from embeddings import create_embeddings


# =========================================================
# Connect to existing ChromaDB
# =========================================================

client = chromadb.PersistentClient(
    path="rag/chroma_db"
)


# =========================================================
# Get existing collection
# =========================================================

collection = client.get_collection(
    name="healthcare_knowledge"
)


# =========================================================
# Retriever function
# =========================================================

def retrieve(
    query: str,
    top_k: int = 3
):

    # Create embedding for the user question
    query_embedding = create_embeddings(
        [query]
    )[0]

    # Search ChromaDB
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )

    # Return the retrieved documents
    return results["documents"][0]


# =========================================================
# Test retriever
# =========================================================

if __name__ == "__main__":

    query = "What is diabetes?"

    results = retrieve(
        query,
        top_k=3
    )

    print("\n========== Retrieved Chunks ==========")

    for i, chunk in enumerate(results):

        print(f"\n----- Chunk {i + 1} -----")
        print(chunk)