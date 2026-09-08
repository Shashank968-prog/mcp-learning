from retriever import retrieve
from embeddings import ask_gemini


# =========================================================
# RAG Pipeline
# =========================================================

async def answer_question(question: str):

    # -----------------------------------------------------
    # Step 1: Retrieve relevant chunks
    # -----------------------------------------------------

    retrieved_chunks = retrieve(
        question,
        top_k=3
    )

    # -----------------------------------------------------
    # Step 2: Combine retrieved chunks into context
    # -----------------------------------------------------

    context = "\n\n".join(
        retrieved_chunks
    )

    # -----------------------------------------------------
    # Step 3: Create RAG prompt
    # -----------------------------------------------------

    prompt = f"""
You are a healthcare knowledge assistant.

Answer the user's question using ONLY the
information provided in the context below.

If the answer cannot be found in the context,
say:

"I don't have enough information in the
knowledge base to answer that."

Do not make up information.

================ CONTEXT ================

{context}

================ QUESTION ================

{question}

================ ANSWER ================
"""

    # -----------------------------------------------------
    # Step 4: Send context + question to Gemini
    # -----------------------------------------------------

    answer = await ask_gemini(
        prompt
    )

    return answer


# =========================================================
# Test RAG Pipeline
# =========================================================

async def main():

    question = "What is diabetes?"

    answer = await answer_question(
        question
    )

    print("\n========== RAG Answer ==========")
    print(answer)


# =========================================================
# Run
# =========================================================

if __name__ == "__main__":

    import asyncio

    asyncio.run(main())

