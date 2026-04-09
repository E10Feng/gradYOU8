import sys as _sys
# Remove cached modules
mods = [k for k in _sys.modules.keys() if 'washu' in k or 'run_llm' in k]
for m in mods: del _sys.modules[m]
_sys.path.insert(0, r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator')
import run_llm_scored_rag as rag

from run_llm_scored_rag import select_nodes, build_context

q = 'computational biology cs minor double count'
nodes = select_nodes(q, k=8)
ctx = build_context(nodes)

print('Total context:', len(ctx), 'chars')
# Show [0252] section
idx = ctx.find('[0252]')
next_idx = ctx.find('[', idx+5) if idx != -1 else -1
end_idx = next_idx if next_idx != -1 else len(ctx)
print(f'[0252] section ({end_idx-idx} chars):')
print(ctx[idx:min(end_idx, idx+2000)])
print()
print('CSE 1301 in 0252 section:', 'CSE 1301' in ctx[idx:end_idx])
print('CSE 2407 in 0252 section:', 'CSE 2407' in ctx[idx:end_idx])
