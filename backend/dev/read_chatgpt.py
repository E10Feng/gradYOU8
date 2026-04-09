with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\libs\pageindex_agent\pageindex_agent\utils.py", "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

idx = content.find("def ChatGPT_API")
with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\dev\chatgpt_api.txt", "w", encoding="utf-8") as f:
    f.write(content[idx:idx+3000])
print("Written")
