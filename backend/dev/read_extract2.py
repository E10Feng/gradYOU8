with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\libs\pageindex_agent\pageindex_agent\utils.py", "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

idx = content.find("def extract_json")
with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\dev\extract_json.txt", "w", encoding="utf-8") as f:
    f.write(content[idx:idx+2000])
print("Written")
