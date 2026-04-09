"""
WashU Navigator — Agentic RAG Pipeline
Multi-pass: retrieves, asks, and if incomplete, searches for the missing piece.
"""

import json, os, urllib.request, sys

TREE_PATH = r"C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_full.json"
OUT_PATH  = r"C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\rag_answer.json"
MAX_ITERS = 3

# ── MiniMax API ────────────────────────────────────────────────────────────
def get_token():
    auth_path = r"C:\Users\ethan\.openclaw\agents\main\agent\auth-profiles.json"
    with open(auth_path) as f:
        profiles = json.load(f)
    for name, cfg in profiles["profiles"].items():
        if "minimax" in name.lower():
            return cfg.get("access", "")
    return ""

TOKEN = get_token()

def minimax_chat(messages, max_tokens=1500):
    """Call MiniMax Chat Completions API (OpenAI-compatible)."""
    payload = json.dumps({
        "model": "MiniMax-M2.7",
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "messages": messages
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.minimax.io/v1/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
        return result["choices"][0]["message"]["content"]

# ── Load tree ──────────────────────────────────────────────────────────────
with open(TREE_PATH, encoding="utf-8") as f:
    tree = json.load(f)

flat = []
def flatten(nodes):
    for n in nodes:
        flat.append(n)
        if n.get("nodes"): flatten(n["nodes"])
flatten(tree)

def extract_text(n): return n.get("text") or n.get("summary", "")

def score_node(n, query):
    qw = set(query.lower().split())
    txt = (n.get("title","") + " " + n.get("summary","") + " " + n.get("text","")).lower()
    return sum(1 for w in qw if w in txt)

def find_nodes(query, top_k=5, exclude_ids=None):
    exclude_ids = exclude_ids or set()
    scored = [(score_node(n, query), n) for n in flat
              if score_node(n, query) > 0 and n.get("node_id","") not in exclude_ids]
    scored.sort(key=lambda x: -x[0])
    return [n for _, n in scored[:top_k]]

SYSTEM_PROMPT = (
    "You are a WashU academic advisor. Answer questions using ONLY the bulletin context provided.\n"
    "CRITICAL: Before answering, explicitly identify:\n"
    "  1. The specific MAJOR and SPECIALIZATION (if any) — and which SCHOOL it belongs to (e.g., Arts & Sciences, Engineering).\n"
    "  2. The specific MINOR (if any) — and which SCHOOL it belongs to.\n"
    "  3. Whether the question involves a COMBINATION across schools (e.g., Bio major in Arts & Sciences + CS minor in Engineering — this is allowed and common at WashU).\n"
    "If you have enough information to answer fully, give a complete, specific answer with course codes and unit counts.\n"
    "If the context is MISSING information needed to fully answer, say exactly:\n"
    "  NEED_MORE_INFO: <specific topic that is missing from the context>\n"
    "Do NOT make up information not in the provided context."
)

def build_context(nodes):
    return "\n\n".join(f"## {n['title']}\n{extract_text(n)}" for n in nodes)

def run_query(query):
    seed_nodes = find_nodes(query)
    if not seed_nodes:
        return None, "No relevant sections found in the bulletin."
    ctx = build_context(seed_nodes)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Bulletin context:\n{ctx}\n\nQuestion: {query}"}
    ]
    print(f"\n--- Pass 1: {len(seed_nodes)} nodes retrieved ---")
    for n in seed_nodes: print(f"  [{n.get('node_id','?')}] {n['title'][:65]}")
    answer = minimax_chat(messages)
    print(f"\n--- Answer ---\n{answer[:500]}")
    need_more = None
    if "NEED_MORE_INFO:" in answer:
        need_more = answer.split("NEED_MORE_INFO:")[1].split("\n")[0].strip()
        print(f"\n--- Need more: {need_more} ---")
    return answer, need_more, seed_nodes

def run_agentic(query):
    print(f"\n{'='*60}\nAGENTIC RAG — {query}\n{'='*60}")
    answer, need_more, seeds = run_query(query)
    if not answer: return answer
    iteration = 2
    while need_more and iteration <= MAX_ITERS:
        more_nodes = find_nodes(need_more, top_k=4)
        if not more_nodes:
            print(f"\n--- Could not find: {need_more} ---")
            break
        print(f"\n--- Pass {iteration}: {len(more_nodes)} nodes for '{need_more}' ---")
        for n in more_nodes: print(f"  [{n.get('node_id','?')}] {n['title'][:65]}")
        ctx = build_context(more_nodes)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Bulletin context:\n{ctx}\n\nQuestion: {query}"}
        ]
        answer = minimax_chat(messages)
        print(f"\n--- Answer ---\n{answer[:500]}")
        if "NEED_MORE_INFO:" in answer:
            need_more = answer.split("NEED_MORE_INFO:")[1].split("\n")[0].strip()
        else:
            need_more = None
        iteration += 1
    print(f"\n{'='*60}\nFINAL:\n{answer}")
    return answer

if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "What are the requirements for the Biology major?"
    result = run_agentic(query)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"query": query, "answer": result}, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to {OUT_PATH}")
