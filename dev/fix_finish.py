import re

path = r"C:\Users\ethan\.openclaw\workspace\vectorless_gemini\pageindex_agent\page_index.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix all finish_reason checks to include "length"
content = content.replace(
    'finish_reason in ("finished", "stop")',
    'finish_reason in ("finished", "stop", "length")'
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Done. Replacements:", content.count('finish_reason in ("finished", "stop", "length")'))
