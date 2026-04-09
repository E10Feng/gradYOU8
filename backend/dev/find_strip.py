with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "rb") as f:
    content = f.read().decode("utf-8", errors="replace")

idx = content.find("strip thinking tags")
if idx >= 0:
    with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\dev\found_strip.txt", "w", encoding="utf-8") as f:
        f.write(content[idx - 100:idx + 400])
    print("Written")
else:
    print("Not found")
