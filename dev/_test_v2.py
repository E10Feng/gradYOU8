import sys, json
sys.path.insert(0, r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator')

# Monkey-patch run_query to capture the answer
import run_llm_scored_rag as rag

orig_run_query = rag.run_query

def capture_query(question):
    selected = rag.select_nodes(question, k=8)
    if not selected:
        return None, "No relevant sections found.", []
    
    print(f"--- {len(selected)} nodes selected: ---")
    for n in selected:
        print(f"  [{n.get('node_id','?')}] {n.get('title','')[:65]}")
    
    ctx = rag.build_context(selected)
    print(f"\nContext size: {len(ctx)} chars")
    
    messages = [
        {"role": "system", "content": rag.SYSTEM_PROMPT},
        {"role": "user", "content": f"Bulletin sections:\n{ctx}\n\nQuestion: {question}"}
    ]
    answer = rag.minimax(messages, max_tokens=2000)
    print(f"\n--- Answer (first 800 chars) ---\n{answer[:800]}")
    
    # Save
    out = {"query": question, "answer": answer, "nodes": [n.get("node_id") for n in selected]}
    with open(rag.OUT_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved to {rag.OUT_PATH}")
    return answer, None, selected

rag.run_query = capture_query

q = 'If I am majoring in computational biology in arts and sciences and minoring in computer science in the engineering school, do CSE 1301 and CSE 2407 double count for both?'
print('='*60)
print('QUESTION:', q)
print('='*60)
capture_query(q)
