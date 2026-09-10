import chromadb

from rag.loader import load_documents, split_into_chunks
from rag.embeddings import create_embedding


client = chromadb.PersistentClient(
    path="rag/chroma_db"
)


collection = client.get_or_create_collection(
    name="healthcare_knowledge"
)


def build_vector_store():
    documents = load_documents()

    print(f"Loaded {len(documents)} source documents.")

    all_chunks = []
    all_embeddings = []
    all_metadatas = []
    all_ids = []

    chunk_id = 0

    for document in documents:

        source = document["source"]
        content = document["content"]

        chunks = split_into_chunks(content)

        print(
            f"{source}: created {len(chunks)} chunks"
        )

        for chunk in chunks:

            embedding = create_embedding(chunk)

            all_chunks.append(chunk)

            all_embeddings.append(
                embedding
            )

            all_metadatas.append({
                "source": source
            })

            all_ids.append(
                f"chunk_{chunk_id}"
            )

            chunk_id += 1

    collection.add(
        ids=all_ids,
        documents=all_chunks,
        embeddings=all_embeddings,
        metadatas=all_metadatas
    )

    print()
    print(
        f"Stored {len(all_chunks)} chunks from "
        f"{len(documents)} sources."
    )


if __name__ == "__main__":
    build_vector_store()