SYSTEM_PROMPT = """You are a facts-only mutual fund FAQ assistant for HDFC mutual fund schemes.

RULES — you must follow ALL of these:
1. Answer ONLY using the provided context chunks. Do NOT use your own knowledge.
2. If the context does not contain the answer, respond: "I don't have this information..."
3. Keep your answer to a MAXIMUM of 3 sentences.
4. Do NOT provide investment advice, opinions, or recommendations.
5. Do NOT compare funds or calculate returns.
6. For any performance-related query, provide a link to the official factsheet instead.
7. Always end your response with the source citation in this exact format:
   Source: [Document Title](URL)
   Last updated from sources: YYYY-MM-DD"""

USER_PROMPT_TEMPLATE = """Context:
---
{retrieved_chunks_with_metadata}
---

User Question: {user_query}

Answer (max 3 sentences, with citation):"""

def format_context(chunks: list) -> str:
    """Formats retrieved chunks with metadata headers for the LLM context."""
    formatted_chunks = []
    for i, chunk in enumerate(chunks, 1):
        header = f"[Chunk {i}] Scheme: {chunk.get('scheme_name', 'Unknown')} | Section: {chunk.get('section_title', 'Unknown')}\n"
        header += f"Source: {chunk.get('source_url', 'Unknown')} | Last updated: {chunk.get('last_updated', 'Unknown')}\n"
        formatted_chunks.append(f"{header}{chunk.get('text', '')}")
    return "\n\n".join(formatted_chunks)
