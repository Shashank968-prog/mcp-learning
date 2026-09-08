
import chromadb

from embeddings import create_embeddings


# =========================================================
# Create ChromaDB client
# =========================================================

client = chromadb.PersistentClient(
    path="rag/chroma_db"
)


# =========================================================
# Create or load collection
# =========================================================

collection = client.get_or_create_collection(
    name="healthcare_knowledge"
)


# =========================================================
# Load healthcare document
# =========================================================

with open(
    "rag/documents/healthcare.txt",
    "r",
    encoding="utf-8"
) as file:

    document = file.read()


# =========================================================
# Split document into chunks
# =========================================================

chunk_size = 500

chunks = [
    document[i:i + chunk_size]
    for i in range(
        0,
        len(document),
        chunk_size
    )
]


# =========================================================
# Generate embeddings
# =========================================================

embeddings = create_embeddings(chunks)


# =========================================================
# Store chunks + embeddings
# =========================================================

collection.add(
    ids=[
        f"chunk_{i}"
        for i in range(len(chunks))
    ],

    documents=chunks,

    embeddings=embeddings
)


print("Embeddings stored in ChromaDB.")

print(
    "Number of stored documents:",
    collection.count()
)


# =========================================================
# Test vector search
# =========================================================

query = "What is diabetes?"


query_embedding = create_embeddings(
    [query]
)[0]


results = collection.query(
    query_embeddings=[query_embedding],
    n_results=3
)


# =========================================================
# Display search results
# =========================================================

print("\n========== Vector Search Results ==========")

for i, document in enumerate(
    results["documents"][0]
):

    print(f"\nResult {i + 1}:")
    print(document)

