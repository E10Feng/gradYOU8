with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "rb") as f:
    content = f.read()

lines = content.split(b"\r\n")
for i in range(375, 385):
    print(f"{i}: spaces={len(lines[i]) - len(lines[i].lstrip())} repr={repr(lines[i])}")
