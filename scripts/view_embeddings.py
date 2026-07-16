#!/usr/bin/env python3
"""
Utility script to view the chunks and their embeddings stored in ChromaDB.
"""

import sys
import argparse
from pathlib import Path

# Ensure project root is on sys.path so 'src' is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.vector_store import get_collection

def main():
    parser = argparse.ArgumentParser(description="View embeddings and chunks in ChromaDB.")
    parser.add_argument("--limit", type=int, default=3, help="Number of chunks to display (default: 3).")
    parser.add_argument("--show-full-embedding", action="store_true", help="Print the full 384-dimensional embedding array.")
    args = parser.parse_args()

    collection = get_collection()
    count = collection.count()
    
    if count == 0:
        print("Vector store is empty. Please run the ingestion pipeline first.")
        return

    print(f"Total chunks in vector store: {count}")
    print(f"Displaying {min(args.limit, count)} chunk(s)...\n")

    # Retrieve from ChromaDB
    results = collection.get(
        limit=args.limit,
        include=["metadatas", "documents", "embeddings"]
    )

    if not results or not results["ids"]:
        print("No data retrieved.")
        return

    for i in range(len(results["ids"])):
        chunk_id = results["ids"][i]
        metadata = results["metadatas"][i] if results["metadatas"] else {}
        document = results["documents"][i] if results["documents"] else ""
        embedding = results["embeddings"][i] if results.get("embeddings") is not None else []

        print("=" * 80)
        print(f"CHUNK ID   : {chunk_id}")
        print(f"SCHEME     : {metadata.get('scheme_name', 'N/A')}")
        print(f"SECTION    : {metadata.get('section_title', 'N/A')}")
        print("-" * 80)
        
        # Display a truncated version of the text
        display_text = document.strip().replace('\n', ' ')
        if len(display_text) > 200:
            display_text = display_text[:200] + "..."
        print(f"TEXT       : {display_text}")
        print("-" * 80)
        
        if embedding is not None and len(embedding) > 0:
            dims = len(embedding)
            print(f"EMBEDDING  : Dimensions = {dims}")
            if args.show_full_embedding:
                print(f"VECTOR     : {embedding}")
            else:
                # Show first 3 and last 1 element to keep it clean
                vector_preview = f"[{embedding[0]:.4f}, {embedding[1]:.4f}, {embedding[2]:.4f}, ..., {embedding[-1]:.4f}]"
                print(f"VECTOR     : {vector_preview}")
        else:
            print("EMBEDDING  : None retrieved.")
        print()

if __name__ == "__main__":
    main()
