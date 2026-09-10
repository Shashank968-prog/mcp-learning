from pathlib import Path


DOCUMENTS_DIR = Path("rag/documents")


def load_documents():
    """
    Load all .txt documents from rag/documents.
    Returns a list of dictionaries containing:
    - source
    - content
    """
    documents = []

    for file_path in DOCUMENTS_DIR.glob("*.txt"):
        content = file_path.read_text(encoding="utf-8")

        documents.append({
            "source": file_path.name,
            "content": content
        })

    return documents


def split_into_chunks(text: str, chunk_size: int = 500, overlap: int = 100):
    """
    Split text into overlapping chunks.
    """
    chunks = []

    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        chunks.append(chunk)

        start += chunk_size - overlap

    return chunks