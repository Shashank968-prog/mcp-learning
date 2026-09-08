from pathlib import Path


# =========================================================
# Document path
# =========================================================

DOCUMENT_PATH = Path(__file__).parent / "documents" / "healthcare.txt"


# =========================================================
# Load document
# =========================================================

def load_document():

    with open(DOCUMENT_PATH, "r", encoding="utf-8") as file:
        text = file.read()

    return text


# =========================================================
# Split document into chunks
# =========================================================

def split_into_chunks(text, chunk_size=500):

    chunks = []

    for start in range(0, len(text), chunk_size):

        chunk = text[start:start + chunk_size]

        chunks.append(chunk)

    return chunks


# =========================================================
# Test
# =========================================================

if __name__ == "__main__":

    document = load_document()

    print("Document loaded.")
    print("Characters:", len(document))

    chunks = split_into_chunks(document)

    print("Number of chunks:", len(chunks))

    for i, chunk in enumerate(chunks):

        print(f"\n========== Chunk {i + 1} ==========")
        print(chunk)