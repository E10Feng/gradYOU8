with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "rb") as f:
    content = f.read()

# Check the current function signature and find the function body
idx = content.find(b"call_minimax(prompt")
# Find the function end - next top-level 'def '
search_from = idx + 1
next_def = content.find(b"\ndef ", search_from)
# Find end of this def (before next def)
print("Function signature:", repr(content[idx:idx + 100]))
print()
print("Found next def at:", next_def)
print()
print("Function end area:")
print(repr(content[next_def - 200:next_def + 10]))
