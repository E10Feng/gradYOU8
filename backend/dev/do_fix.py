with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "rb") as f:
    content = f.read()

idx = content.find(b"answer = answer.strip()")
old = content[idx - 68 : idx + 116]

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\dev\old_block.bin", "wb") as f:
    f.write(old)

print("Written old block, len:", len(old))

# Now build and try replacement
new = (
    content[idx - 68 : idx - 1]
    + b"\r\n"
    + b'                # Remove chain-of-thought / reasoning trace lines from the response\r\n'
    + b'                lines = answer.split("\\n")\r\n'
    + b'                skip = ["based on the content", "i need to", "let me check", "the content says", "now produce final answer", "final answer", "thus answer accordingly"]\r\n'
    + b'                clean = [l for l in lines if not any(l.strip().lower().startswith(p) for p in skip)]\r\n'
    + b'                answer = "\\n".join(clean).strip()'
    + content[idx + 15 : idx + 116]
)

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\dev\new_block.bin", "wb") as f:
    f.write(new)

print("Written new block, len:", len(new))
print("old in content:", old in content)

if old in content:
    content = content.replace(old, new)
    with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "wb") as f:
        f.write(content)
    print("Fixed!")
else:
    print("NOT FOUND - manual fix needed")
