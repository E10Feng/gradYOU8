import sys
sys.path.insert(0, r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator')

from run_llm_scored_rag import select_nodes, build_context

q = 'computational biology cs minor double count'
nodes = select_nodes(q, k=8)
ctx = build_context(nodes)
print('Context length:', len(ctx))
print('CSE 1301 in ctx:', 'CSE 1301' in ctx)
print('CSE 2407 in ctx:', 'CSE 2407' in ctx)
print()
# Show what portion of 0252 looks like
idx = ctx.find('0252')
if idx != -1:
    print('0252 section:')
    print(ctx[idx:idx+500])
