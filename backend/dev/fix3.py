with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "r", encoding="utf-8") as f:
    content = f.read()

old = (
    '            answer = answer.replace("&#</section></think>", "&#</section></think>", "").replace("&#</section></minimax:tool_call>
            answer = answer.strip()\n'
    '            if not answer:\n'
    '                answer = "I couldn\'t find a confident answer."'
)

new = (
    '            answer = answer.replace("</think>", "").replace("<think>", "")\n'
    '            # Remove chain-of-thought / reasoning trace lines from the visible response\n'
    '            lines = answer.split("\\n")\n'
    '            skip_prefixes = [\n'
    '                "based on the content",\n'
    '                "i need to",\n'
    '                "let me check",\n'
    '                "the content says",\n'
    '                "now produce final answer",\n'
    '                "final answer",\n'
    '                "thus answer accordingly",\n'
    '            ]\n'
    '            clean_lines = [\n'
    '                l for l in lines\n'
    '                if not any(l.strip().lower().startswith(p) for p in skip_prefixes)\n'
    '            ]\n'
    '            answer = "\\n".join(clean_lines).strip()\n'
    '            if not answer:\n'
    '                answer = "I couldn\'t find a confident answer."'
)

if old in content:
    content = content.replace(old, new)
    print("Fixed")
else:
    print("Not found")
    # Find what's actually there
    idx = content.find('answer = answer.replace')
    if idx >= 0:
        print("Found at:", repr(content[idx-5:idx+300]))

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "w", encoding="utf-8", newline="\r\n") as f:
    f.write(content)
