with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\dev\call_func.txt", "rb") as f:
    data = f.read()

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\dev\call_func_hex.txt", "w", encoding="utf-8", errors="replace") as f:
    f.write("Length: " + str(len(data)) + "\n")
    f.write(repr(data[:600]))
