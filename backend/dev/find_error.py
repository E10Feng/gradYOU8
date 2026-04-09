import re

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

for m in re.finditer(r'"Error"', content):
    print(m.start(), repr(content[max(0, m.start() - 100) : m.start() + 50]))
    print("---")
