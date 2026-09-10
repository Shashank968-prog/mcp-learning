import chromadb

from rag.embeddings import create_embedding


client = chromadb.PersistentClient(
    path="rag/chroma_db"
)


collection = client.get_collection(
    name="healthcare_knowledge"
)


def retrieve(
    query: str,
    top_k: int = 3
):
    query_embedding = create_embedding(
        query
    )

    results = collection.query(
        query_embeddings=[
            query_embedding
        ],
        n_results=top_k
    )

    documents = results.get(
        "documents",
        [[]]
    )[0]

    metadatas = results.get(
        "metadatas",
        [[]]
    )[0]

    retrieved_results = []

    for document, metadata in zip(
        documents,
        metadatas
    ):

        retrieved_results.append({
            "content": document,
            "source": metadata.get(
                "source",
                "unknown"
            )
        })

    return retrieved_results