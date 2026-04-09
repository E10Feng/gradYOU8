"""
test_pageindex.py — Test PageIndex with the WashU Biology Bulletin PDF
Run: python test_pageindex.py
"""
import sys
import os
import json
from pathlib import Path

# ── Setup ────────────────────────────────────────────────────────────────────
PDF_PATH = Path(__file__).parent.parent / "data" / "bulletin.pdf"
WORKSPACE = Path(__file__).parent.parent / "workspace"

# ── API key ──────────────────────────────────────────────────────────────────
# Set via environment MINIMAX_API_KEY
api_key = os.getenv("MINIMAX_API_KEY", "sk-cp-eONyc1lsRF8VqUMKE41edOMcpXnFqd_vFFtJVZ_ZlrDOWofcj3eWqkiSU7nrNZwuyqDLzc8UyP3Lljh3DwzKFIyOaDqo3ok22P_V3kr-MpydccZcXl60bpQ")

TEST_QUERIES = [
    "What are the required courses for the Biology major?",
    "What are the gateway courses for the Biology major?",
    "Can BIOL 296 count toward the natural science distribution requirement?",
    "What are the different Biology major specializations?",
    "What is the grade requirement for Biology major courses?",
]


def main():
    import sys
    sys.path.insert(0, str(Path(__file__).parent / "libs" / "pageindex_agent" / "pageindex_agent"))

    from pageindex_agent.page_index import page_index_main
    from pageindex_agent.pageindex_config import pageindex_config
    from pageindex_agent.utils import ConfigLoader, ChatGPT_API

    # ── Config ──────────────────────────────────────────────────────────────
    os.environ["MINIMAX_API_KEY"] = api_key
    os.environ["MINIMAX_GROUP_ID"] = ""
    os.environ["MINIMAX_MODEL"] = "MiniMax-M2.7"

    # Override config
    pageindex_config.PAGEINDEX_MODEL = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7")

    # ── Check PDF ──────────────────────────────────────────────────────────
    if not PDF_PATH.exists():
        print(f"ERROR: PDF not found at {PDF_PATH}")
        print("Save the WashU bulletin PDF to: data/bulletin.pdf")
        sys.exit(1)

    print(f"Using PDF: {PDF_PATH}")
    print(f"PDF size: {PDF_PATH.stat().st_size / 1024:.1f} KB")

    # ── Quick API test ─────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("Testing Minimax API connection...")
    print("=" * 70)

    test_prompt = "You are a helpful assistant. Reply with just the word 'OK' if you can read this."
    try:
        response = ChatGPT_API(pageindex_config.PAGEINDEX_MODEL, test_prompt)
        print(f"API response: {response[:50]}")
    except Exception as e:
        print(f"API ERROR: {e}")
        print("Check your MINIMAX_API_KEY and try again.")
        sys.exit(1)

    # ── Index ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("Indexing PDF with PageIndex...")
    print("=" * 70)

    config_loader = ConfigLoader()
    opt = config_loader.load({
        "model": pageindex_config.PAGEINDEX_MODEL,
        "if_add_node_id": "yes",
        "if_add_node_summary": "yes",
        "if_add_doc_description": "yes",
        "if_add_node_text": "yes",
    })

    print(f"Using model: {opt.model}")
    print("This may take several minutes for a large PDF...")

    import time
    t0 = time.time()
    result = page_index_main(str(PDF_PATH), opt)
    elapsed = time.time() - t0

    tree_path = WORKSPACE / "bulletin.tree.json"
    tree_path.parent.mkdir(parents=True, exist_ok=True)
    with open(tree_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\nIndexing complete in {elapsed:.1f}s")
    print(f"Tree saved to: {tree_path}")
    print(f"Top-level sections: {len(result.get('structure', []))}")

    # ── Test queries ────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("Running test queries...")
    print("=" * 70)

    for i, question in enumerate(TEST_QUERIES, 1):
        print(f"\nQ{i}: {question}")
        print("-" * 50)
        # Simple RAG: get structure, find relevant section, get page content
        from pageindex_agent.utils import structure_to_list, get_text_of_pdf_pages
        import re

        nodes = structure_to_list(result.get("structure", []))
        # Find nodes related to the question via keyword match
        question_words = set(question.lower().split())
        scored = []
        for node in nodes:
            title_words = set(node.get("title", "").lower().split())
            # Simple overlap score
            overlap = len(question_words & title_words)
            scored.append((overlap, node))

        scored.sort(reverse=True)
        top_nodes = scored[:3]

        print(f"  Top matching sections:")
        for score, node in top_nodes:
            start = node.get("start_index", "?")
            end = node.get("end_index", "?")
            title = node.get("title", "?")
            print(f"    [{start}-{end}] {title} (score: {score})")

            # Get page content for top match
            if score > 0 and start != "?":
                try:
                    text = get_text_of_pdf_pages(
                        str(PDF_PATH), int(start), int(end), tag=False
                    )
                    # Print first 300 chars
                    clean = re.sub(r"\s+", " ", text).strip()
                    print(f"    Preview: {clean[:300]}...")
                except Exception as e:
                    print(f"    (couldn't fetch text: {e})")

    print("\n" + "=" * 70)
    print("Test complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
