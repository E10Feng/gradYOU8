content = open(r"C:\Users\ethan\.openclaw\workspace\vectorless_gemini\pageindex_agent\page_index.py", encoding="utf-8").read()
lines = content.split("\n")
for i, l in enumerate(lines[269:320], 270):
    print(f"{i}: {l[:150]}")
