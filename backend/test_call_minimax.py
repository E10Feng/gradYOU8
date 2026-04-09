import os, sys, json
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# Load env
_dotenv_path = ROOT / ".env"
from dotenv import load_dotenv
load_dotenv(str(_dotenv_path), override=True)
if not os.getenv("MINIMAX_API_KEY"):
    _auth_path = Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
    import json as _json
    with open(_auth_path) as _f:
        _profiles = _json.load(_f)
    for _name, _cfg in _profiles.get("profiles", {}).items():
        if "minimax" in _name.lower():
            os.environ["MINIMAX_API_KEY"] = _cfg["access"]
            break

token = os.getenv("MINIMAX_API_KEY", "")
print(f"Token: {token[:15]}...")

# Test MiniMax API with urllib
import urllib.request, urllib.error
messages = [{"role": "user", "content": "Say exactly: TEST OK"}]
payload = json.dumps({"model": "MiniMax-M2.7", "messages": messages, "max_tokens": 20}).encode()
req = urllib.request.Request(
    "https://api.minimax.io/v1/chat/completions",
    data=payload,
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    method="POST"
)
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        result = json.loads(r.read())
        print("URllib result:", result["choices"][0]["message"]["content"][:50])
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code, e.read()[:200])
except Exception as e:
    print("Error:", type(e).__name__, str(e)[:200])

# Test the call_minimax function
def call_minimax(prompt, model="MiniMax-M2.7"):
    payload = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 8000}).encode()
    req = urllib.request.Request(
        "https://api.minimax.io/v1/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            result = json.loads(r.read())
            return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"API_ERROR: {e}"

# Test with a simple prompt
result = call_minimax("What is 2+2?")
print("call_minimax result:", result[:100])
