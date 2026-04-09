with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "rb") as f:
    content = f.read().decode("utf-8", errors="replace")

# The current call_minimax block (already fixed to strip thinking tags)
# We need to replace it with one that returns raw (no JSON extraction)
old_block = (
    b'    try:\r\n'
    b'        with urllib.request.urlopen(req, timeout=120) as r:\r\n'
    b'            result = json.loads(r.read())\r\n'
    b'            raw = result["choices"][0]["message"]["content"]\r\n'
    b'            # MiniMax embeds thinking in <thinking>...</thinking> blocks.\r\n'
    b'            # Strip them to get the clean response text.\r\n'
    b'            raw = raw.replace("'
    b'\xef\x81\x91'  #的开始
)

# Simpler approach: just replace the specific lines we need to change
# Current return: raw.strip()
# We want: raw (no stripping - handle at call site)

# Let's just find the "return raw.strip()" in call_minimax and add JSON extraction after it
import re

# Find and fix the select_prompt JSON parsing in tree_retrieve instead
# The key fix is in tree_retrieve where we parse the LLM response

# Let me find the tree_retrieve function and fix the JSON parsing
idx = content.find("parsed = json.loads(raw) if raw.startswith")
if idx < 0:
    print("Could not find the JSON parsing section")
else:
    print("Found at:", idx)
    # Show the current code
    print(repr(content[idx - 100:idx + 300]))
