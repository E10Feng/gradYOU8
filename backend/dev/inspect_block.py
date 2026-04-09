with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "rb") as f:
    content = f.read()

idx = content.find(b"answer = answer.strip()")
old = content[idx - 68 : idx + 116]
print("Looking for:", repr(old))

# Find where the if-not-answer block starts
if_idx = content.find(b"if not answer:", idx - 100)
print("if not answer at:", if_idx)
print("if block:", repr(content[if_idx : if_idx + 100]))

# Build the exact old block
old_exact = (
    b'                answer = answer.replace("\n</think>", "").replace("\n<think>", "")'
    b'\r\n'
    b'                answer = answer.strip()'
    b'\r\n'
    b'                if not answer:'
    b'\r\n'
    b'                    answer = "I couldn'
    b'\xe2\x80\x99t find a confident answer."'
)

print("Exact old:", repr(old_exact))
print("Found:", old_exact in content)
