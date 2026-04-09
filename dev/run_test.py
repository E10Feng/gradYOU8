import os, sys, time
sys.stdout.reconfigure(line_buffering=True)
os.environ["MINIMAX_API_KEY"] = "sk-cp-eONyc1lsRF8VqUMKE41edOMcpXnFqd_vFFtJVZ_ZlrDOWofcj3eWqkiSU7nrNZwuyqDLzc8UyP3Lljh3DwzKFIyOaDqo3ok22P_V3kr-MpydccZcXl60bpQ"
os.environ["MINIMAX_MODEL"] = "MiniMax-M2.7"
os.environ["MINIMAX_GROUP_ID"] = ""

sys.path.insert(0, r"C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\backend\libs\pageindex_agent")

import json
from pathlib import Path
import PyPDF2

pdf_path = r"C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin.pdf"
WORKSPACE = Path(r"C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\workspace")
WORKSPACE.mkdir(exist_ok=True)

from pageindex_agent.pageindex_config import pageindex_config
from pageindex_agent.utils import ConfigLoader
from pageindex_agent.page_index import page_index_main

pageindex_config.PAGEINDEX_MODEL = "MiniMax-M2.7"
opt = ConfigLoader().load({
    "model": pageindex_config.PAGEINDEX_MODEL,
    "if_add_node_id": "yes",
    "if_add_node_summary": "no",
    "if_add_node_text": "yes",
    "if_add_doc_description": "no",
    "toc_check_page_num": 5,
})

print(f"PDF: {pdf_path}", flush=True)
print(f"toc_check_page_num: {opt.toc_check_page_num}", flush=True)
print("Starting indexing (will take several minutes)...", flush=True)

t0 = time.time()
try:
    result = page_index_main(str(pdf_path), opt)
    elapsed = time.time() - t0
    print(f"\n=== DONE in {elapsed:.1f}s ===", flush=True)
    sections = result.get("structure", [])
    print(f"Top-level sections: {len(sections)}", flush=True)
    
    tree_path = WORKSPACE / "bulletin.tree.json"
    with open(tree_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"Saved: {tree_path}", flush=True)
except Exception as e:
    print(f"ERROR: {e}", flush=True)
    import traceback
    traceback.print_exc()
