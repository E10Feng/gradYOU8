import re

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "r", encoding="utf-8") as f:
    content = f.read()

# Find and replace the answer_prompt ending
old_ending = '"If the answer is not in the content, say I couldn\'t find this information."\n    )'
new_ending = '"If the answer is not in the content, say I couldn\'t find this information.\\n\\nIMPORTANT: Write ONLY the final answer. Do NOT include any reasoning, chain-of-thought, or intermediate steps. Do NOT write phrases like \'Based on the content\', \'I need to\', \'Let me check\', \'The content says\', or any other meta-commentary. Start your response with the answer directly."\n    )'

if old_ending in content:
    content = content.replace(old_ending, new_ending)
    print("1. answer_prompt fixed")
else:
    print("WARNING: old_ending not found")
    # Show what's there
    idx = content.find("couldn't find this information")
    if idx >= 0:
        print(repr(content[idx:idx+100]))

# Also add answer post-processing cleanup
old_answer_block = '        answer = (answer or "").strip()\n        answer = answer.replace("</think>", "").replace("<think>", "")\n        answer = answer.strip()\n        if not answer:\n            answer = "I couldn\'t find a confident answer."'
new_answer_block = '        answer = (answer or "").strip()\n        answer = answer.replace("</think>", "").replace("<think>", "")\n        # Remove reasoning trace lines\n        lines = answer.split("\\n")\n        skip_prefixes = [\n            "based on the content",\n            "i need to",\n            "let me check",\n            "the content says",\n            "now produce final answer",\n            "final answer",\n            "thus answer accordingly",\n        ]\n        clean_lines = [l for l in lines if not any(l.strip().lower().startswith(p) for p in skip_prefixes)]\n        answer = "\\n".join(clean_lines).strip()\n        if not answer:\n            answer = "I couldn\'t find a confident answer."'

if old_answer_block in content:
    content = content.replace(old_answer_block, new_answer_block)
    print("2. answer post-processing fixed")
else:
    print("WARNING: old_answer_block not found")
    idx = content.find('answer = answer.replace("</think>"')
    if idx >= 0:
        print(repr(content[idx-50:idx+200]))

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "w", encoding="utf-8", newline="\r\n") as f:
    f.write(content)
print("Done")
