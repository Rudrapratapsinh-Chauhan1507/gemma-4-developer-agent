"""Stage 2 Demo — Repository-Aware Semantic Code Retrieval.

Demonstrates the full Stage 2 retrieval pipeline on the sandbox repository
using a single issue query.

Usage:
    python run_demo_stage2.py
"""

import sys
from pathlib import Path

SANDBOX_PATH = str(Path(__file__).parent / "sandbox" / "mini_shop")

# The specific issue requested for the demo
ISSUE = "discount percentage calculation is incorrect"
EXPECTED_FILE = "shop/pricing.py"
EXPECTED_SYMBOL = "calculate_discount"

SEPARATOR = "=" * 64
THIN = "-" * 64

def print_section(title: str) -> None:
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)

def print_sub(title: str) -> None:
    print(f"\n{THIN}")
    print(f"  {title}")
    print(THIN)

def main() -> None:
    print_section("STAGE 2 DEMO — Semantic Code Retrieval")
    print(f"Sandbox: {SANDBOX_PATH}")
    print(f"Issue:   \"{ISSUE}\"\n")

    # 1. Repository Discovery
    from mini_swe_agent.retrieval.discovery import FileDiscovery
    d = FileDiscovery(SANDBOX_PATH)
    files = d.discover_files()
    print(f"[*] Repository Discovery: Found {len(files)} valid file(s).")

    # 2. Chunking / Semantic Indexing
    print("[*] Building FAISS Index (Loading Embedder...)")
    from mini_swe_agent.retrieval.retriever import SemanticRetriever
    retriever = SemanticRetriever(SANDBOX_PATH)
    chunk_count = retriever.index_repository()
    print(f"[*] Semantic Retriever: Indexed {chunk_count} code chunk(s).\n")

    # 3. Keyword Retrieval
    from mini_swe_agent.retrieval.keyword_search import KeywordRetriever
    kr = KeywordRetriever(SANDBOX_PATH)
    kw_results = kr.retrieve(ISSUE, top_k=5)

    print_sub("Keyword Retrieval Results")
    if not kw_results:
        print("  (no results)")
    else:
        print(f"  {'Rank':<5} {'Score':<7} {'File':<30} {'Matched Keywords'}")
        print(f"  {'-'*4:<5} {'-'*5:<7} {'-'*28:<30} {'-'*20}")
        for i, r in enumerate(kw_results, 1):
            kw = ", ".join(r.get("matched_keywords", []))[:35]
            fp = r["file_path"][:28]
            print(f"  {i:<5} {r['score']:<7} {fp:<30} {kw}")

    # 4. Semantic Retrieval (Semantic similarity scores, File paths and symbols)
    sem_results = retriever.retrieve(ISSUE, top_k=5)

    print_sub("Semantic Retrieval Results")
    if not sem_results:
        print("  (no results)")
    else:
        print(f"  {'Rank':<5} {'Score':<7} {'File':<25} {'Symbol':<25} {'Type'}")
        print(f"  {'-'*4:<5} {'-'*5:<7} {'-'*23:<25} {'-'*23:<25} {'-'*8}")
        for i, r in enumerate(sem_results, 1):
            fp = r["file_path"][:23]
            sym = r["symbol_name"][:23]
            stype = r["symbol_type"]
            score = r["score"]
            print(f"  {i:<5} {score:<7.3f} {fp:<25} {sym:<25} {stype}")

    # 5. Final ContextBuilder output
    from mini_swe_agent.retrieval.context_builder import ContextBuilder
    print_sub("ContextBuilder Output (First 3 Chunks)")
    cb = ContextBuilder(max_chunks=3, max_chars_per_chunk=800, max_total_chars=3000)
    context_block = cb.build_context(sem_results)

    if not context_block:
        print("  (no context generated)")
    else:
        print(f"  [Context block length: {len(context_block)} chars]\n")
        # Indent for neatness
        for line in context_block.split("\n"):
            print(f"    {line}")

    print_section("DEMO COMPLETE")


if __name__ == "__main__":
    main()
