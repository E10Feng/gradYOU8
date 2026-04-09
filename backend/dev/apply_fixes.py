import re

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "r", encoding="utf-8", errors="replace") as f:
    content = f.read()

# Fix 1: Add parse_json parameter to call_minimax signature
old_sig = 'def call_minimax(prompt: str, model: str = "MiniMax-M2.7") -> str:\n    """Call MiniMax chat API and return the response text."""'
new_sig = 'def call_minimax(prompt: str, model: str = "MiniMax-M2.7", *, parse_json: bool = False) -> str:\n    """Call MiniMax chat API and return the response text.\n\n    Args:\n        parse_json: if True, extracts and returns JSON from the response.\n                    MiniMax wraps JSON inside <thinking>...</thinking> blocks.\n    """'

if old_sig in content:
    content = content.replace(old_sig, new_sig)
    print("Fix 1 done: parse_json parameter added")
else:
    print("WARNING: could not find old_sig")

# Fix 2: Add conditional JSON extraction in call_minimax (after stripping)
# Find the stripping line and add the conditional
old_strip = '            raw = raw.replace("<think>", "").replace("</think>", "")\n\n            # Try to find JSON object/array anywhere in the stripped text\n            import re'
new_strip = '            raw = raw.replace("<think>", "").replace("</think>", "")\n\n            if not parse_json:\n                return raw.strip()\n\n            import re'

if old_strip in content:
    content = content.replace(old_strip, new_strip)
    print("Fix 2 done: JSON extraction now conditional")
else:
    print("WARNING: could not find old_strip")
    # Show what's actually there
    idx = content.find('raw = raw.replace("<think>"')
    if idx >= 0:
        print("Found at:", idx)
        print(repr(content[idx:idx+300]))

# Fix 3: In tree_retrieve, use parse_json=True for title selection call
old_call = '        raw = call_minimax(model=model, prompt=select_prompt)\n        parsed = json.loads(raw) if raw.startswith("{") else {}\n    except Exception:\n        parsed = {}'
new_call = '        raw = call_minimax(model=model, prompt=select_prompt, parse_json=True)\n        try:\n            parsed = json.loads(raw)\n        except Exception:\n            parsed = {}\n    except Exception:\n        parsed = {}'

if old_call in content:
    content = content.replace(old_call, new_call)
    print("Fix 3 done: tree_retrieve uses parse_json=True")
else:
    print("WARNING: could not find old_call in tree_retrieve")
    idx = content.find('call_minimax(model=model, prompt=select_prompt)')
    if idx >= 0:
        print(repr(content[idx:idx+200]))

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "w", encoding="utf-8", errors="replace", newline="\r\n") as f:
    f.write(content)

print("Done writing")
