import sys
sys.path.insert(0, r"C:\Users\ethan\.openclaw\workspace\vectorless_gemini")

import os
os.environ["GOOGLE_API_KEY"] = "AIzaSyAafF0zCnSftTJ-FTG0q9iZODl_mnrrMmo"

import fitz, re
from pageindex_agent.pageindex_config import pageindex_config
from pageindex_agent.utils import ConfigLoader, _reset_client
from pageindex_agent.page_index import find_toc_pages

_reset_client()
pageindex_config.PAGEINDEX_MODEL = "gemini-2.5-flash"
opt = ConfigLoader().load({"model": pageindex_config.PAGEINDEX_MODEL})

doc = fitz.open(r"C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_full.pdf")
page_list = [(doc[i].get_text(), doc.get_page_pixmap(i).width) for i in range(len(doc))]

toc_pages, toc_content = find_toc_pages(0, page_list, opt)
print(f"TOC content length: {len(toc_content)}")
print(f"First 2000 chars:\n{toc_content[:2000]}")
print("\n---DETECTING TOP-LEVEL SECTION PATTERNS---")

# Try different split patterns
patterns = [
    r"\n(?=\d+\.\s)",
    r"\n(?=[IVX]+\.\s)",
    r"\n(?=[A-Z]\.\s)",
    r"\n\n(?=\d+\.)",
]
for pat in patterns:
    parts = re.split(pat, toc_content)
    non_empty = [p.strip() for p in parts if p.strip()]
    print(f"\nPattern: {pat}")
    print(f"  Chunks: {len(non_empty)}")
    if non_empty:
        print(f"  First chunk ({len(non_empty[0])} chars): {repr(non_empty[0][:200])}")
        if len(non_empty) > 1:
            print(f"  Second chunk ({len(non_empty[1])} chars): {repr(non_empty[1][:200])}")
