"""Stage 2 Evaluation — Keyword vs Semantic Retrieval.

This script performs a small local evaluation comparing the baseline
KeywordRetriever with the SemanticRetriever on the two known issues
from the sandbox/mini_shop repository.

Usage:
    python run_evaluation_stage2.py
"""

import sys
from pathlib import Path

SANDBOX_PATH = str(Path(__file__).parent / "sandbox" / "mini_shop")

# Extract the core issue descriptions as queries
EVAL_ISSUES = [
    {
        "id": 1,
        "query": (
            "calculate_discount calculates negative or inflated totals. "
            "When applying a percentage discount (e.g. 10%), calculate_discount(100.0, 10.0) "
            "produces -900.0 instead of 90.00. The discount formula appears to treat the "
            "discount as a direct multiplier rather than a percentage."
        ),
        "target_file": "shop/pricing.py",
        "target_symbol": "calculate_discount",
    },
    {
        "id": 2,
        "query": (
            "remove_item raises unhandled KeyError when item not present. "
            "When attempting to remove an item that is not currently in the shopping cart, "
            "the code raises a raw Python KeyError. The library defines a custom exception "
            "ItemNotFoundError which should be raised instead."
        ),
        "target_file": "shop/cart.py",
        "target_symbol": "remove_item",
    }
]

def find_target_in_results(results, expected_file, expected_symbol):
    """Finds the rank and score of the expected target in the retrieval results."""
    for idx, r in enumerate(results, 1):
        fp = r.get("file_path", "")
        # For keyword, we check preview_lines, for semantic we check symbol_name
        sym = r.get("symbol_name", r.get("preview_lines", ""))

        if expected_file in fp and expected_symbol in sym:
            return idx, r.get("score")

        # Fallback if just the file is found
        if expected_file in fp:
            return idx, r.get("score")

    return None, None

def main():
    print("================================================================")
    print(" STAGE 2 EVALUATION: Keyword vs Semantic Retrieval")
    print("================================================================\n")
    print(f"Target Repository: {SANDBOX_PATH}")
    print("This is a small local evaluation demonstrating the differences")
    print("between lexical token matching and semantic embedding matching.\n")

    print("[*] Initializing Retrievers...")
    from mini_swe_agent.retrieval.keyword_search import KeywordRetriever
    from mini_swe_agent.retrieval.retriever import SemanticRetriever

    kr = KeywordRetriever(SANDBOX_PATH)
    sr = SemanticRetriever(SANDBOX_PATH)

    print("[*] Building Semantic Index (FAISS)...")
    chunks_indexed = sr.index_repository()
    print(f"[*] Semantic Index complete ({chunks_indexed} chunks).\n")

    top_k_eval = 5

    for issue in EVAL_ISSUES:
        print("-" * 64)
        print(f"ISSUE #{issue['id']}")
        print(f"Query: \"{issue['query'][:80]}...\"")
        print(f"Target File:   {issue['target_file']}")
        print(f"Target Symbol: {issue['target_symbol']}")
        print("-" * 64)

        # Keyword Search
        kw_results = kr.retrieve(issue["query"], top_k=top_k_eval)
        kw_rank, kw_score = find_target_in_results(kw_results, issue["target_file"], issue["target_symbol"])
        kw_found = kw_rank is not None

        # Semantic Search
        sem_results = sr.retrieve(issue["query"], top_k=top_k_eval)
        sem_rank, sem_score = find_target_in_results(sem_results, issue["target_file"], issue["target_symbol"])
        sem_found = sem_rank is not None

        # Print detailed comparison
        print(f"{'Metric':<30} | {'KeywordRetriever':<20} | {'SemanticRetriever'}")
        print("-" * 30 + "+" + "-" * 22 + "+" + "-" * 20)

        # Relevant file retrieved?
        kw_file_yes = "Yes" if kw_found else "No"
        sem_file_yes = "Yes" if sem_found else "No"
        print(f"{'Relevant Target Retrieved?':<30} | {kw_file_yes:<20} | {sem_file_yes}")

        # Rank of target
        kw_rank_str = str(kw_rank) if kw_rank else "Not in top 5"
        sem_rank_str = str(sem_rank) if sem_rank else "Not in top 5"
        print(f"{'Rank of Target':<30} | {kw_rank_str:<20} | {sem_rank_str}")

        # Target score
        kw_score_str = str(kw_score) if kw_score else "N/A"
        sem_score_str = f"{sem_score:.3f}" if sem_score else "N/A"
        print(f"{'Retrieval Score':<30} | {kw_score_str:<20} | {sem_score_str}")

        print("\nTop Result Overview:")

        kw_top = kw_results[0] if kw_results else {}
        print(f"  Keyword Top #1:  {kw_top.get('file_path', 'None')} (Score: {kw_top.get('score', 0)})")

        sem_top = sem_results[0] if sem_results else {}
        print(f"  Semantic Top #1: {sem_top.get('file_path', 'None')} -> {sem_top.get('symbol_name', 'None')} (Score: {sem_top.get('score', 0):.3f})")
        print("\n")


if __name__ == "__main__":
    main()
