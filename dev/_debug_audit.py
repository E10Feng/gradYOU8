import sys, json, re
sys.path.insert(0, r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator')
from run_llm_scored_rag import (
    load_student_profile, audit, id_to_node, build_context,
    build_profile_context, minimax, AUDIT_PROMPT, _get_audit_anchors
)

profile = load_student_profile()

# Step 1: What anchors are selected?
anchors = _get_audit_anchors(profile)
print('Anchors:', anchors)

# Step 2: What nodes?
nodes = [id_to_node[aid] for aid in anchors if aid in id_to_node]
for n in nodes:
    print(f"  [{n.get('node_id')}] {n.get('title')[:60]}")

# Step 3: Build context sizes
ctx = build_context(nodes)
student_ctx = build_profile_context(profile)
print(f"\nBulletin context: {len(ctx)} chars")
print(f"Student context: {len(student_ctx)} chars")
print(f"AUDIT_PROMPT: {len(AUDIT_PROMPT)} chars")

# Step 4: Try the minimax call directly with fewer nodes
messages = [
    {"role": "system", "content": AUDIT_PROMPT},
    {"role": "user", "content": f"Student profile:\n{student_ctx}\n\nBulletin requirement sections:\n{ctx[:3000]}\n\nProduce the structured degree audit JSON."}
]
print(f"\nTotal prompt: {sum(len(m['content']) for m in messages)} chars")
print("\nCalling minimax...")
response = minimax(messages, max_tokens=3000)
print(f"Response length: {len(response)}")
print(f"Response preview: {response[:300]}")
