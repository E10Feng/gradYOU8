import re

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "rb") as f:
    content = f.read()

idx = content.find(b"answer = answer.strip()")
print("idx:", idx)

old = (
    b'                answer = answer.replace("\n</think>", "").replace("\n<think>", "")\n'
    b'                answer = answer.strip()\n'
    b'                if not answer:\n'
    b'                    answer = "I couldn'
    b'\xe2\x80\x99t find a confident answer."'
)

print("old in content:", old in content)
print("old:", repr(old[:100]))

# Try without the r prefix (escaped newline)
old2 = (
    b'                answer = answer.replace("'
    b'\xef\x81\x91'
    b'", "").replace("'
    b'\xef\x81\x91'
    b'", "")'
)
print("old2 in content:", old2 in content)
