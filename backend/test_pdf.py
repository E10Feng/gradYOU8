import sys
sys.path.insert(0, '.')
sys.path.insert(0, 'libs/pageindex_agent')
from utils import get_text_of_pages
t = get_text_of_pages('data/bulletin_full.pdf', 1, 1, tag=False)
print(f"Length: {len(t)}")
print(f"First 300: {t[:300]}")
