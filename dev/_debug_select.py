import sys
sys.path.insert(0, r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator')
from run_llm_scored_rag import select_nodes, get_anchor_ids

q = 'If I am majoring in computational biology in arts and sciences and minoring in computer science in the engineering school, do CSE 1301 and CSE 2407 double count for both?'
anchors = get_anchor_ids(q)
print('Top anchors:', anchors[:10])
print()
result = select_nodes(q, k=8)
print('SELECT_NODES result:')
for n in result:
    nid = n.get('node_id', '?')
    print(f'  [{nid}] {n.get("title","")[:65]}')
print()
print('0649 in result:', any(n.get('node_id') == '0649' for n in result))
print('0252 in result:', any(n.get('node_id') == '0252' for n in result))
