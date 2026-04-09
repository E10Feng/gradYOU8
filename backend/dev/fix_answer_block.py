with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "rb") as f:
    content = f.read()

idx = content.find(b"answer = call_minimax")
ret = content.find(b"    return answer, sources", idx)
old_block = content[idx:ret]
print("Old block length:", len(old_block))
print("Old block:", repr(old_block[:200]))

# Build correct replacement - all inside try block (8-space indent inside get_answer)
new_block = (
    b'        answer = call_minimax(model=model, prompt=answer_prompt)\r\n'
    b'        answer = (answer or "").strip()\r\n'
    b'        answer = answer.replace("\n</think>", "").replace("\n<think>", "")\r\n'
    b'        # Remove chain-of-thought / reasoning trace lines from the response\r\n'
    b'        lines = answer.split("\\n")\r\n'
    b'        skip = ["based on the content", "i need to", "let me check", "the content says", "now produce final answer", "final answer", "thus answer accordingly"]\r\n'
    b'        clean = [l for l in lines if not any(l.strip().lower().startswith(p) for p in skip)]\r\n'
    b'        answer = "\\n".join(clean).strip()\r\n'
    b'        if not answer:\r\n'
    b'            answer = "I couldn\'t find a confident answer."\r\n'
    b'    except Exception:\r\n'
    b'        answer = "I couldn\'t find a confident answer."\r\n'
)

print("New block length:", len(new_block))
print("new in content:", new_block in content)

if old_block in content:
    content = content.replace(old_block, new_block)
    with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "wb") as f:
        f.write(content)
    print("Fixed!")
else:
    print("ERROR: old block not found - trying shorter version")
    # Try without the answer = call_minimax line
    idx2 = content.find(b'        answer = call_minimax')
    ret2 = content.find(b"    return answer, sources", idx2)
    old2 = content[idx2:ret2]
    print("old2 in content:", old2 in content)
