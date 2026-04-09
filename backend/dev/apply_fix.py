with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "rb") as f:
    content = f.read()

# Find the problem area
idx = content.find(b"        \r\n                # Remove chain-of-thought")
old_block_end = content.find(b"    except Exception:", idx)
old_block = content[idx:old_block_end]

# Build the correct replacement block
# The try block content should have 8 spaces indent
# The inner block (answer processing) should have 12 spaces
correct_block = (
    b"        \r\n"  # empty line, 8-space indent (inside try)
    b"        # Remove chain-of-thought / reasoning trace lines from the response\r\n"
    b"        lines = answer.split(\"\\n\")\r\n"
    b"        skip = [\"based on the content\", \"i need to\", \"let me check\", \"the content says\", \"now produce final answer\", \"final answer\", \"thus answer accordingly\"]\r\n"
    b"        clean = [l for l in lines if not any(l.strip().lower().startswith(p) for p in skip)]\r\n"
    b"        answer = \"\\n\".join(clean).strip()\r\n"
    b"            if not answer:\r\n"
    b"                    answer = \"I couldn\\'t find a confident answer.\""
)

print("old in content:", old_block in content)
if old_block in content:
    content = content.replace(old_block, correct_block)
    with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "wb") as f:
        f.write(content)
    print("Fixed!")
else:
    print("ERROR: old block not found")
