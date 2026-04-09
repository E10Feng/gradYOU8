import sys, importlib
mods = [k for k in sys.modules if 'washu' in k or 'run_llm' in k]
for m in mods: del sys.modules[m]
sys.path.insert(0, r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator')
import run_llm_scored_rag as rag
importlib.reload(rag)

from run_llm_scored_rag import select_nodes, build_context

q = 'computational biology cs minor double count'
nodes = select_nodes(q, k=8)
ctx = build_context(nodes)

# Find boundaries by scanning for [NID] markers
import re
section_bounds = []
for m in re.finditer(r'\[(\d+)\]', ctx):
    section_bounds.append((m.start(), m.group(1)))

def find_in_section(pos):
    """Which node does position pos belong to?"""
    for i in range(len(section_bounds)-1):
        start, nid = section_bounds[i]
        end = section_bounds[i+1][0]
        if start <= pos < end:
            return nid, start, end
    # Last section
    if section_bounds:
        start, nid = section_bounds[-1]
        return nid, start, len(ctx)
    return None, 0, 0

# Find all CSE occurrences
for m in re.finditer(r'CSE \d+', ctx):
    nid, s, e = find_in_section(m.start())
    print(f'CSE at {m.start()}: [{nid}] section ({e-s} chars), snippet: ...{ctx[max(0,m.start()-30):m.start()+50]}...')

print()
print('Section boundaries:')
for start, nid in section_bounds:
    print(f'  [{nid}]: starts at {start}')
