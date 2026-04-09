import json, urllib.request, os

TREE_PATH = r"C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_full.json"

def get_token():
    auth_path = r"C:\Users\ethan\.openclaw\agents\main\agent\auth-profiles.json"
    with open(auth_path) as f:
        profiles = json.load(f)
    for name, cfg in profiles.items():
        if "minimax" in name.lower():
            return cfg.get("access", "")
    return ""

TOKEN = get_token()
print(f"Token from get_token(): {TOKEN[:30]}...")

# Load tree
with open(TREE_PATH, encoding="utf-8") as f:
    tree = json.load(f)
flat = []
def flatten(nodes):
    for n in nodes:
        flat.append(n)
        if n.get("nodes"): flatten(n["nodes"])
flatten(tree)
print(f"Flat nodes: {len(flat)}")

def score_node(n, query):
    qw = set(query.lower().split())
    txt = (n.get("title","") + " " + n.get("summary","") + " " + n.get("text","")).lower()
    return sum(1 for w in qw if w in txt)

def find_nodes(query, top_k=5):
    scored = [(score_node(n, query), n) for n in flat if score_node(n, query) > 0]
    scored.sort(key=lambda x: -x[0])
    return [n for _, n in scored[:top_k]]

query = "If I'm majoring in computational biology and minoring in computer science, do CSE 1301 and CSE 2407 double count for both the major and minor?"
nodes = find_nodes(query)
print(f"Nodes found: {len(nodes)}")

ctx = "\n\n".join(f"## {n['title']}\n{n.get('text') or n.get('summary','')}" for n in nodes)
print(f"Context length: {len(ctx)} chars")

messages = [
    {"role": "system", "content": "You are a WashU academic advisor. Answer using the context. If you need more info say NEED_MORE_INFO: <topic>."},
    {"role": "user", "content": f"Bulletin context:\n{ctx}\n\nQuestion: {query}"}
]
print(f"Messages: {len(messages)}")

payload = json.dumps({
    "model": "MiniMax-M2.7",
    "max_tokens": 1500,
    "temperature": 0.3,
    "messages": messages
}).encode("utf-8")
print(f"Payload size: {len(payload)} bytes")

req = urllib.request.Request(
    "https://api.minimax.io/v1/chat/completions",
    data=payload,
    headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    method="POST"
)
print(f"Request URL: {req.full_url}")
print(f"Request headers: {dict(req.headers)}")

try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
        print("SUCCESS!")
        print(result["choices"][0]["message"]["content"][:300])
except Exception as e:
    print(f"FAILED: {e}")
    if hasattr(e, 'read'):
        print("Response body:", e.read().decode())