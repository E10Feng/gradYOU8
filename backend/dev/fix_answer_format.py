with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "r", encoding="utf-8") as f:
    content = f.read()

old_prompt = (
    '    answer_prompt = (\n'
    '        "You are a WashU degree requirement assistant. A student asks: " + query + "\\n\\n"\n'
    '        "Here is relevant content from the WashU Undergraduate Bulletin:\\n\\n"\n'
    '        + context + "\\n\\n"\n'
    '        "Based ONLY on the content above, answer the student\'s question. "\n'
    '        "Be specific with course numbers and unit counts. "\n'
    '        "If the answer is not in the content, say I couldn\'t find this information."\n'
    '    )'
)

new_prompt = (
    '    answer_prompt = (\n'
    '        "You are a WashU degree requirement assistant. A student asks: " + query + "\\n\\n"\n'
    '        "Here is relevant content from the WashU Undergraduate Bulletin:\\n\\n"\n'
    '        + context + "\\n\\n"\n'
    '        "Based ONLY on the content above, answer the student\'s question. "\n'
    '        "Be specific with course numbers and unit counts. "\n'
    '        "If the answer is not in the content, say I couldn\'t find this information.\\n\\n"\n'
    '        "IMPORTANT: Write ONLY the final answer. Do NOT include any reasoning, chain-of-thought, "\n'
    '        "or intermediate steps. Do NOT write phrases like \\'Based on the content\\', \\'I need to\\', "\n'
    '        "\\'Let me check\\', \\'The content says\\', or any other meta-commentary. "\n'
    '        "Start your response with the answer directly."\n'
    '    )'
)

if old_prompt in content:
    content = content.replace(old_prompt, new_prompt)
    print("Prompt updated")
else:
    print("WARNING: old_prompt not found")
    # Show what we have around answer_prompt
    idx = content.find("answer_prompt = (")
    print(repr(content[idx:idx+400]))

# Also fix the answer post-processing
old_answer = (
    '        answer = (answer or "").strip()\n'
    '        # Strip MiniMax reasoning tags\n'
    '        answer = answer.replace("</think>", "").replace("<think>", "")\n'
    '        answer = answer.strip()'
)

new_answer = (
    '        answer = (answer or "").strip()\n'
    '        # Strip any thinking block residue\n'
    '        answer = answer.replace("</think>", "").replace("<think>", "")\n'
    '        # Remove reasoning trace lines from the response\n'
    '        lines = answer.split("\\n")\n'
    '        skip_phrase = [\n'
    '            "based on the content",\n'
    '            "i need to",\n'
    '            "let me check",\n'
    '            "the content says",\n'
    '            "now produce final answer",\n'
    '            "final answer",\n'
    '            "thus answer accordingly",\n'
    '        ]\n'
    '        clean_lines = []\n'
    '        for line in lines:\n'
    '            stripped = line.strip().lower()\n'
    '            if any(stripped.startswith(p) for p in skip_phrase):\n'
    '                continue\n'
    '            # Skip lines that are just the question echoed back\n'
    '            if query.lower() in stripped and len(stripped) < len(query) + 20:\n'
    '                continue\n'
    '            clean_lines.append(line)\n'
    '        answer = "\\n".join(clean_lines).strip()'
)

if old_answer in content:
    content = content.replace(old_answer, new_answer)
    print("Answer post-processing updated")
else:
    print("WARNING: old_answer not found")
    idx = content.find('answer = (answer or "").strip()')
    print(repr(content[idx-30:idx+200]))

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "w", encoding="utf-8", newline="\r\n") as f:
    f.write(content)
print("Done")
