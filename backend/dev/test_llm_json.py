import sys
import os
import urllib.request
import json

backend = r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend"
os.chdir(backend)
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

from services.tree_router import _get_api_key
token = _get_api_key()

# Test the LLM response for a simple prompt
payload = json.dumps({
    "model": "MiniMax-M2.7",
    "messages": [{"role": "user", "content": "Return JSON with your favorite color: {\"color\": \"red\"}. Just return JSON, no thinking."}],
    "max_tokens": 200
}).encode()

req = urllib.request.Request(
    "https://api.minimax.io/v1/chat/completions",
    data=payload,
    headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    method="POST"
)

with urllib.request.urlopen(req, timeout=30) as r:
    result = json.loads(r.read())
    content = result["choices"][0]["message"]["content"]
    print("Raw response:")
    print(repr(content[:500]))
    print()
    print("Is JSON?:", content.strip().startswith("{"))
