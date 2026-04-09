with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "r", encoding="utf-8") as f:
    content = f.read()

idx = content.find("def get_tree_path")
with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\dev\tree_func.txt", "w", encoding="utf-8") as f:
    f.write(content[idx:idx+600])
print("Written")
