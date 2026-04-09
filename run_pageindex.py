"""
Index a WashU bulletin PDF using PageIndex API.
Saves the hierarchical tree JSON for use in RAG/Q&A pipeline.

Usage:
    python run_pageindex.py

Requires:
    pip install pageindex
    PAGEINDEX_API_KEY environment variable, or set it below
"""

import os
import sys
import time
import json
import logging
from pathlib import Path

# ── CONFIG ──────────────────────────────────────────────────────────────────
PDF_PATH  = r"C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_full.pdf"
OUT_PATH  = r"C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_tree.json"
API_KEY   = os.getenv("PAGEINDEX_API_KEY", "").strip()
POLL_SEC  = 10
MAX_WAIT  = 600  # 10 min max
# ────────────────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger("pageindex")

if not API_KEY:
    print("ERROR: Set PAGEINDEX_API_KEY env var or edit API_KEY in this script.")
    sys.exit(1)

try:
    from pageindex import PageIndexClient
except ImportError:
    print("Installing pageindex...")
    os.system(f"{sys.executable} -m pip install -U pageindex")
    from pageindex import PageIndexClient

pi = PageIndexClient(api_key=API_KEY)

# ── SUBMIT ──────────────────────────────────────────────────────────────────
pdf_file = Path(PDF_PATH)
if not pdf_file.exists():
    print(f"ERROR: PDF not found: {PDF_PATH}")
    sys.exit(1)

print(f"Uploading {pdf_file.name} ...")
result = pi.submit_document(str(pdf_file))
doc_id = result.get("doc_id")
print(f"  doc_id = {doc_id}")

# ── POLL ────────────────────────────────────────────────────────────────────
elapsed = 0
while elapsed < MAX_WAIT:
    status = pi.get_document(doc_id)
    s = status.get("status", "unknown")
    print(f"[{elapsed}s] status = {s}")
    if s == "completed":
        break
    if s in ("failed", "error"):
        print(f"FATAL: processing {s}")
        sys.exit(1)
    time.sleep(POLL_SEC)
    elapsed += POLL_SEC
else:
    print(f"TIMEOUT after {MAX_WAIT}s")
    sys.exit(1)

# ── FETCH TREE ──────────────────────────────────────────────────────────────
print("Fetching tree structure...")
tree_result = pi.get_tree(doc_id)
tree = tree_result.get("result", [])

# ── SAVE ────────────────────────────────────────────────────────────────────
out = {"doc_id": doc_id, "structure": tree}
with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)

print(f"\nDone! Saved {len(tree)} top-level nodes → {OUT_PATH}")

# Quick summary
def count_nodes(nodes):
    total = len(nodes)
    for n in nodes:
        if n.get("nodes"):
            total += count_nodes(n["nodes"])
    return total

total = count_nodes(tree)
print(f"Total nodes in tree: {total}")
