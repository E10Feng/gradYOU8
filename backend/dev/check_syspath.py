with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()
idx = content.find("sys.path.insert")
with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\dev\syspath_check.txt", "w", encoding="utf-8") as f:
    f.write(content[idx:idx+300])
print("Written")
