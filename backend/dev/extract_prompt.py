with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "rb") as f:
    content = f.read()

# Opening f""" is at 7733, so prompt starts at 7737
# Closing """ is at 8441
prompt_bytes = content[7737:8441]
prompt_text = prompt_bytes.decode("utf-8", errors="replace")

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\dev\prompt_text.txt", "w", encoding="utf-8", errors="replace") as f:
    f.write(prompt_text)

print("Prompt text:")
print(prompt_text)
print()
print("Total prompt chars:", len(prompt_text))
