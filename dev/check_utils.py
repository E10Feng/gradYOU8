content = open(r"C:\Users\ethan\.openclaw\workspace\vectorless_gemini\pageindex_agent\utils.py", encoding="utf-8").read()
lines = content.split("\n")
for i, l in enumerate(lines):
    if any(kw in l.lower() for kw in ["stream", "generatecontent", "generate_content"]):
        print(f"{i+1}: {l[:150]}")
