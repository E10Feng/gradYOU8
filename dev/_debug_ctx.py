import sys
sys.path.insert(0, r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator')
from run_llm_scored_rag import select_nodes, build_context

q = 'If I am majoring in computational biology in arts and sciences and minoring in computer science in the engineering school, do CSE 1301 and CSE 2407 double count for both?'
selected = select_nodes(q, k=8)
ctx = build_context(selected)

print('Context length:', len(ctx))
print()
print('=== FULL CONTEXT ===')
print(ctx)
