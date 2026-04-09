with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "r", encoding="utf-8") as f:
    content = f.read()

idx = content.find("    answer_prompt = (")
end = content.find("\n# ── Routes", idx)
with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\dev\answer_prompt.txt", "w", encoding="utf-8") as f:
    f.write(content[idx:end + 50])
print("Written")
