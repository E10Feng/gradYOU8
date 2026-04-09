with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "rb") as f:
    content = f.read()
lines = content.split(b"\r\n")
with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\dev\lines.txt", "w", encoding="utf-8") as f:
    for i in range(348, 385):
        f.write(f"{i}: {repr(lines[i])}\n")
print("Written")
