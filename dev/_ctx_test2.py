import importlib, sys
# Remove cached modules
mods_to_remove = [k for k in sys.modules if 'washu' in k or 'run_llm' in k]
for m in mods_to_remove:
    del sys.modules[m]

sys.path.insert(0, r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator')
import run_llm_scored_rag as rag
importlib.reload(rag)

from run_llm_scored_rag import select_nodes, build_context

q = 'computational biology cs minor double count'
nodes = select_nodes(q, k=8)
ctx = build_context(nodes)
print('Context length:', len(ctx))
print('CSE 1301 in ctx:', 'CSE 1301' in ctx)
print('CSE 2407 in ctx:', 'CSE 2407' in ctx)
print()
idx = ctx.find('0252')
if idx != -1:
    print('0252 section (first 700 chars):')
    print(ctx[idx:idx+700])
