with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "rb") as f:
    content = f.read()

# Find the problem area - look for the badly indented block
# We want to find:
# b'        \n'  (empty line with 8 spaces)
# followed by the new block with 16-space indentation
# and then '        if not answer:' (8 spaces) - which should be '            if not answer:' (12 spaces)

# Find: b'        \r\n                # Remove chain-of-thought'
idx = content.find(b"        \r\n                # Remove chain-of-thought")
print("Found at:", idx)
if idx >= 0:
    # The correct block should be:
    correct_block = (
        b"        \r\n"  # empty line with 8 spaces (part of try block)
        b"        # Remove chain-of-thought / reasoning trace lines from the response\r\n"
        b"        lines = answer.split(\"\\n\")\r\n"
        b"        skip = [\"based on the content\", \"i need to\", \"let me check\", \"the content says\", \"now produce final answer\", \"final answer\", \"thus answer accordingly\"]\r\n"
        b"        clean = [l for l in lines if not any(l.strip().lower().startswith(p) for p in skip)]\r\n"
        b"        answer = \"\\n\".join(clean).strip()\r\n"
        b"            if not answer:\r\n"  # 12 spaces - inside try block
        b"                    answer = \"I couldn\\'t find a confident answer.\""
    )
    old_block_end = content.find(b"    except Exception:", idx)
    old_block = content[idx:old_block_end]
    print("Old block:", repr(old_block[:200]))
    print("Correct block:", repr(correct_block[:200]))
    print("old in content:", old_block in content)
