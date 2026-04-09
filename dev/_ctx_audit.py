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

print('Total context:', len(ctx), 'chars')
print()

# Show where each node starts and its first 50 chars
for nid in ['0252', '0649', '0657']:
    idx = ctx.find(f'[{nid}]')
    if idx != -1:
        print(f'[{nid}] starts at {idx}, next 300 chars:')
        print(ctx[idx:idx+300])
        print()
        # Find CSE 1301 near this node
        cse_idx = ctx.find('CSE 1301', idx)
        if cse_idx != -1 and cse_idx < idx + 9000:
            print(f'  -> CSE 1301 found at position {cse_idx} (within this node)')
            print(ctx[max(idx, cse_idx-50):cse_idx+100])
        else:
            print(f'  -> CSE 1301 NOT found within this node section')
    else:
        print(f'[{nid}] NOT FOUND in context')
    print()
