import os
os.chdir(r"C:\Users\ethan\.openclaw\workspace\vectorless_gemini")
os.environ["MINIMAX_API_KEY"] = "sk-cp-eONyc1lsRF8VqUMKE41edOMcpXnFqd_vFFtJVZ_ZlrDOWofcj3eWqkiSU7nrNZwuyqDLzc8UyP3Lljh3DwzKFIyOaDqo3ok22P_V3kr-MpydccZcXl60bpQ"
os.environ["MINIMAX_MODEL"] = "MiniMax-M2.7"
os.environ["MINIMAX_GROUP_ID"] = ""

import sys
sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, ".")

import json
from pathlib import Path
import time

pdf_path = r"C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin.pdf"
WORKSPACE = Path(r"C:\Users\ethan\.openclaw\workspace\vectorless_gemini\workspace")
WORKSPACE.mkdir(exist_ok=True)

from pageindex_agent.page_index import page_index_main
from pageindex_agent.pageindex_config import pageindex_config
from pageindex_agent.utils import ConfigLoader

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
print("Starting page_index_main...", flush=True)

t0 = time.time()
result = page_index_main(pdf_path, opt)
elapsed = time.time() - t0

print(f"\n=== DONE in {elapsed:.1f}s ===", flush=True)
print(f"Sections: {len(result.get('structure', []))}", flush=True)

tree_path = WORKSPACE / "bulletin.tree.json"
with open(tree_path, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
print(f"Saved: {tree_path}", flush=True)
