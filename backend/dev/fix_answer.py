import re

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix 1: Update answer_prompt to explicitly tell LLM to skip reasoning
old_prompt_end = 'If the answer is not in the content, say I could not find this information."'
new_prompt_end = 'If the answer is not in the content, say I could not find this information.\\n\\nIMPORTANT: Write ONLY the final answer. Do NOT include any reasoning, chain-of-thought, or intermediate steps. Do NOT write phrases like Based on the content, I need to, Let me check, The content says, or any other meta-commentary. Start your response with the answer directly.'

if old_prompt_end in content:
    content = content.replace(old_prompt_end, new_prompt_end)
    print("1. answer_prompt updated")
else:
    print("WARNING: old_prompt_end not found")

# Fix 2: Post-process answer to strip reasoning lines
old_post = '        answer = (answer or "").strip()\n        # Strip MiniMax reasoning tags\n        answer = answer.replace("&#</section></think>", "").replace("&#</section><think>", "")\n        answer = answer.strip()'

if old_post in content:
    content = content.replace(old_post, new_post)
    print("2. post-processing updated")
else:
    print("WARNING: old_post not found")
    # Show what's there
    idx = content.find('answer = (answer or ')
    if idx >= 0:
        print(repr(content[idx:idx+300]))

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "w", encoding="utf-8", newline="\r\n") as f:
    f.write(content)
print("Done")
