import os, sys, time
sys.stdout.reconfigure(line_buffering=True)
os.environ["GOOGLE_API_KEY"] = "AIzaSyAafF0zCnSftTJ-FTG0q9iZODl_mnrrMmo"

sys.path.insert(0, r"C:\Users\ethan\.openclaw\workspace\vectorless_gemini")

import json
from pathlib import Path

pdf_path = r"C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_full.pdf"
WORKSPACE = Path(r"C:\Users\ethan\.openclaw\workspace\vectorless_gemini\workspace")
WORKSPACE.mkdir(exist_ok=True)

from pageindex_agent.pageindex_config import pageindex_config
from pageindex_agent.utils import ConfigLoader, _reset_client
from pageindex_agent.page_index import page_index_main

_reset_client()
pageindex_config.PAGEINDEX_MODEL = "gemini-2.5-flash"
opt = ConfigLoader().load({
    "model": pageindex_config.PAGEINDEX_MODEL,
    "if_add_node_id": "yes",
    "if_add_node_summary": "yes",
    "if_add_doc_description": "yes",
    "if_add_node_text": "yes",
})

print(f"PDF: {pdf_path}", flush=True)
print(f"Model: {pageindex_config.PAGEINDEX_MODEL}", flush=True)
print("Starting indexing...", flush=True)

t0 = time.time()
result = page_index_main(str(pdf_path), opt)
elapsed = time.time() - t0

print(f"\n=== DONE in {elapsed:.1f}s ===", flush=True)
sections = result.get("structure", [])
print(f"Top-level sections: {len(sections)}", flush=True)

tree_path = WORKSPACE / "bulletin_full.tree.json"
with open(tree_path, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
print(f"Saved: {tree_path}", flush=True)
