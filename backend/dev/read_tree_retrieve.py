with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "r", encoding="utf-8") as f:
    content = f.read()

idx = content.find("def tree_retrieve")
with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\dev\tree_retrieve.txt", "w", encoding="utf-8") as f:
    f.write(content[idx:idx+4000])
print("Written")
