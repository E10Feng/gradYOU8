with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'prompt = f"""' in line:
        with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\dev\prompt.txt", "w", encoding="utf-8") as out:
            for j in range(i, min(i+25, len(lines))):
                out.write(f"{j+1}: {lines[j]}\n")
        print("Written")
        break
