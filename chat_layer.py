"""
WashU Navigator — Minimax RAG Chat Layer
Uses the PageIndex tree JSON as a structured index for question-answering.

Usage:
    python chat_layer.py "What courses does the Biology major require?"
"""

import json
import os
import sys
import re
from pathlib import Path

# ── CONFIG ──────────────────────────────────────────────────────────────────
TREE_JSON = r"C:\Users\ethan\.openclaw\media\inbound\document-structure-pi-cmnjh3eow03yj01qp0hv0s1f0---7806c9ed-271a-496e-81db-5d4619b8ee35.json"
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY") or os.getenv("MINIMAX_BASE_URL")
# ────────────────────────────────────────────────────────────────────────────

# Load tree
with open(TREE_JSON, encoding="utf-8") as f:
    raw = json.load(f)

tree = raw if isinstance(raw, list) else raw.get("structure", [])

# ── TREE WALKER ─────────────────────────────────────────────────────────────
def flatten_nodes(nodes, depth=0):
    """Yield all nodes in depth-first order."""
    for node in nodes:
        yield node, depth
        if node.get("nodes"):
            yield from flatten_nodes(node["nodes"], depth + 1)

def extract_text(node):
    """Get the best available text from a node."""
    return node.get("text") or node.get("summary", "")

def score_node(node, query):
    """Simple keyword overlap score between query and node."""
    q_words = set(query.lower().split())
    fields = " ".join([
        node.get("title", ""),
        node.get("summary", ""),
        node.get("text", "")
    ]).lower()
    return sum(1 for w in q_words if w in fields)

def find_relevant_nodes(query, top_k=5):
    """Return the top_k nodes most relevant to the query."""
    scored = []
    for node, depth in flatten_nodes(tree):
        text = extract_text(node)
        if not text:
            continue
        score = score_node(node, query)
        if score > 0:
            scored.append((score, depth, node))
    scored.sort(key=lambda x: (-x[0], x[1]))  # highest score first, then shallowest
    return scored[:top_k]

def build_context(nodes_with_depth):
    """Build a context string from retrieved nodes, with nesting headers."""
    ctx = []
    for node, depth in nodes_with_depth:
        indent = "  " * depth
        title = node.get("title", "Unknown")
        text = extract_text(node)
        ctx.append(f"{indent}## {title}\n{indent}{text}")
    return "\n\n".join(ctx)

# ── MINIMAX CALL ─────────────────────────────────────────────────────────────
MINIMAX_API_URL = "https://api.minimax.chat/v1/text/chatcompletion_v2"
MINIMAX_GROUP_ID = os.getenv("MINIMAX_GROUP_ID")
MINIMAX_API_KEY  = os.getenv("MINIMAX_API_KEY") or os.getenv("MINIMAX_KEY")

def ask_minimax(question, context):
    """Call Minimax Chat API with question + context."""
    import urllib.request
    import urllib.error

    if not MINIMAX_API_KEY:
        return "ERROR: MINIMAX_API_KEY not set in environment."

    url = f"{MINIMAX_API_URL}?GroupId={MINIMAX_GROUP_ID}" if MINIMAX_GROUP_ID else MINIMAX_API_URL

    payload = {
        "model": "MiniMax-Text-01",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a helpful academic advisor assistant for Washington University in St. Louis. "
                    "Use the provided context from the WashU Arts & Sciences bulletin to answer questions. "
                    "Be specific and cite course codes, requirements, and page references when available. "
                    "If the answer isn't in the context, say you don't have that information."
                )
            },
            {
                "role": "user",
                "content": f"Context from the WashU bulletin:\n\n{context}\n\n---\nQuestion: {question}"
            }
        ],
        "temperature": 0.3,
        "max_tokens": 1024
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {MINIMAX_API_KEY}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            choices = result.get("choices", [{}])
            return choices[0].get("message", {}).get("content", "No response")
    except urllib.error.HTTPError as e:
        return f"HTTPError {e.code}: {e.read().decode()}"
    except Exception as e:
        return f"Error: {e}"

# ── INTERACTIVE CHAT ─────────────────────────────────────────────────────────
def chat(query):
    print(f"\n🔍  Query: {query}")
    nodes = find_relevant_nodes(query)
    if not nodes:
        print("No relevant nodes found.")
        return
    ctx = build_context(nodes)
    print(f"📚  Retrieved {len(nodes)} relevant section(s)\n")
    answer = ask_minimax(query, ctx)
    print(f"💬  Answer:\n{answer}")
    return answer

if __name__ == "__main__":
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        chat(question)
    else:
        print("WashU Navigator — Chat Layer")
        print("Ask a question about the WashU Arts & Sciences bulletin.\n")
        while True:
            try:
                q = input("\nYou: ")
                if q.strip().lower() in ("exit", "quit", "q"):
                    break
                chat(q)
            except EOFError:
                break
