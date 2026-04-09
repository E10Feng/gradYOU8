import re

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "rb") as f:
    content = f.read()

# 1. Replace the call_minimax function
old_call = (
    b'def call_minimax(prompt: str, model: str = "MiniMax-M2.7") -> str:\r\n'
    b'    """Call MiniMax chat API and return the response text."""\r\n'
    b'    import urllib.request\r\n'
    b'    import os\r\n'
    b'    token = os.getenv("MINIMAX_API_KEY", "")\r\n'
    b'    if not token:\r\n'
    b'        _auth_path = Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"\r\n'
    b'        try:\r\n'
    b'            with open(_auth_path) as _f:\r\n'
    b'                _profiles = json.load(_f)\r\n'
    b'            for _name, _cfg in _profiles.get("profiles", {}).items():\r\n'
    b'                if "minimax" in _name.lower():\r\n'
    b'                    token = _cfg["access"]\r\n'
    b'                    break\r\n'
    b'        except Exception:\r\n'
    b'            pass\r\n'
    b'    payload = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 8000}).encode()\r\n'
    b'    req = urllib.request.Request(\r\n'
    b'        "https://api.minimax.io/v1/chat/completions",\r\n'
    b'        data=payload,\r\n'
    b'        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},\r\n'
    b'        method="POST"\r\n'
    b'    )\r\n'
    b'    try:\r\n'
    b'        with urllib.request.urlopen(req, timeout=120) as r:\r\n'
    b'            result = json.loads(r.read())\r\n'
    b'            raw = result["choices"][0]["message"]["content"]\r\n'
    b'            # MiniMax embeds the actual response inside <thinking> blocks.\r\n'
    b'            # Strip them to get the clean response text.\r\n'
    b'            raw = raw.replace("'
    b'\x81'
    b'", "").replace("'
    b'\x81'
    b'", "")\r\n'
    b'            return raw.strip()\r\n'
    b'    except Exception as e:\r\n'
    b'        return f"API_ERROR: {e}"'
)

new_call = (
    b'def call_minimax(prompt: str, model: str = "MiniMax-M2.7", *, parse_json: bool = False) -> str:\r\n'
    b'    """\r\n'
    b'    Call MiniMax chat API and return the response text.\r\n'
    b'    parse_json: if True, extracts and parses a JSON object from the response.\r\n'
    b'                  MiniMax wraps JSON inside <thinking>...</thinking> blocks,\r\n'
    b'                  so we strip those and extract JSON from the remaining text.\r\n'
    b'    """\r\n'
    b'    import re\r\n'
    b'    import urllib.request\r\n'
    b'    import os\r\n'
    b'    token = os.getenv("MINIMAX_API_KEY", "")\r\n'
    b'    if not token:\r\n'
    b'        _auth_path = Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"\r\n'
    b'        try:\r\n'
    b'            with open(_auth_path) as _f:\r\n'
    b'                _profiles = json.load(_f)\r\n'
    b'            for _name, _cfg in _profiles.get("profiles", {}).items():\r\n'
    b'                if "minimax" in _name.lower():\r\n'
    b'                    token = _cfg["access"]\r\n'
    b'                    break\r\n'
    b'        except Exception:\r\n'
    b'            pass\r\n'
    b'    payload = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 8000}).encode()\r\n'
    b'    req = urllib.request.Request(\r\n'
    b'        "https://api.minimax.io/v1/chat/completions",\r\n'
    b'        data=payload,\r\n'
    b'        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},\r\n'
    b'        method="POST"\r\n'
    b'    )\r\n'
    b'    try:\r\n'
    b'        with urllib.request.urlopen(req, timeout=120) as r:\r\n'
    b'            result = json.loads(r.read())\r\n'
    b'            raw = result["choices"][0]["message"]["content"]\r\n'
    b'            stripped = raw.replace("'
    b'\x81'
    b'", "").replace("'
    b'\x81'
    b'", "")\r\n'
    b'            if not parse_json:\r\n'
    b'                return stripped.strip()\r\n'
    b'            # Extract JSON from stripped text (appears after </think>)\r\n'
    b'            for match in re.finditer(r\'\\{[^{}]*(?:\\{[^{}]*\\}[^{}]*)*\\}\', stripped, re.DOTALL):\r\n'
    b'                try:\r\n'
    b'                    parsed = json.loads(match.group(0))\r\n'
    b'                    return json.dumps(parsed)\r\n'
    b'                except Exception:\r\n'
    b'                    pass\r\n'
    b'            for match in re.finditer(r\'\\[[^\\[\\]]+\\]\', stripped):\r\n'
    b'                try:\r\n'
    b'                    parsed = json.loads(match.group(0))\r\n'
    b'                    if isinstance(parsed, list):\r\n'
    b'                        return json.dumps(parsed)\r\n'
    b'                except Exception:\r\n'
    b'                    pass\r\n'
    b'            return stripped.strip()\r\n'
    b'    except Exception as e:\r\n'
    b'        return f"API_ERROR: {e}"'
)

if old_call in content:
    content = content.replace(old_call, new_call)
    print("1. call_minimax updated")
else:
    print("WARNING: could not find old call_minimax")
    # Show what's there instead
    idx = content.find(b"def call_minimax")
    if idx >= 0:
        print("Found at:", idx)
        print(repr(content[idx:idx+400]))

# 2. In tree_retrieve, update the call_minimax call for title selection to use parse_json=True
# and update the parsing code
old_parse = b'    try:\r\n        raw = call_minimax(model=model, prompt=select_prompt)\r\n        parsed = json.loads(raw) if raw.startswith("{") else {}\r\n    except Exception:\r\n        parsed = {}\r\n\r\n    selected = parsed.get("titles", []) if isinstance(parsed, dict) else []'
new_parse = b'    try:\r\n        raw = call_minimax(model=model, prompt=select_prompt, parse_json=True)\r\n        parsed = json.loads(raw)\r\n    except Exception:\r\n        parsed = {}\r\n\r\n    selected = parsed.get("titles", []) if isinstance(parsed, dict) else []'

if old_parse in content:
    content = content.replace(old_parse, new_parse)
    print("2. tree_retrieve JSON parsing updated")
else:
    print("WARNING: could not find old parse block")
    idx = content.find(b"call_minimax(model=model, prompt=select_prompt)")
    if idx >= 0:
        print(repr(content[idx:idx+200]))

# 3. Fix answer_prompt stripping - currently removes the prompt text from the response
# The issue is that call_minimax returns the raw thinking+JSON, not the actual answer
# After the parse_json fix, the answer_prompt response still echoes the prompt
# We need to strip the echoed prompt from the response
# Actually - wait. The answer_prompt call also has thinking tags and the answer is after </think>
# With parse_json=False (default), we get the stripped thinking+JSON text
# But the answer generation JSON isn't returned as JSON - it's free text after </think>
# So for the answer, we should NOT use parse_json - we just get the stripped text
# The stripped text for answer_prompt starts with the thinking text
# Let me check what the answer looks like...

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "wb") as f:
    f.write(content.encode("utf-8", errors="replace"))

print("Done writing")
