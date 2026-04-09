"""Remove duplicate broken audit functions from run_llm_scored_rag.py"""

with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\run_llm_scored_rag.py', 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')

# Find the line indices (0-indexed)
# Line 374 (0-idx): end of answer_with_profile
# Line 375 (0-idx): first # ── Degree Audit ── (broken)
# Line 549 (0-idx): end of first broken copy
# Line 551 (0-idx): second # ── Degree Audit ── (clean) — keep from here
# Line 688 (0-idx): end of file

first_audit_marker = None
second_audit_marker = None

for i, line in enumerate(lines):
    if '# ── Degree Audit ──' in line:
        if first_audit_marker is None:
            first_audit_marker = i
        else:
            second_audit_marker = i
            break

print(f"First audit marker: line {first_audit_marker+1}")
print(f"Second audit marker: line {second_audit_marker+1}")

# Find end of second copy (last line of file = len(lines)-1)
# The second copy goes to the end of the file
second_copy_start = second_audit_marker
first_copy_end = first_audit_marker - 1  # line before the first marker

# Keep: lines[:374] + lines[551:]
# But line 374 = "return run_agentic..." (end of answer_with_profile)
# We want to keep lines up to and including line 374, then skip to line 551

# Find where answer_with_profile ends (should be before line 375)
answer_with_end = None
for i in range(first_audit_marker - 1, -1, -1):
    if lines[i].strip().startswith('def '):
        answer_with_end = i - 1
        break

print(f"answer_with_end: line {answer_with_end+1}")

# Keep: lines[:374] + lines[551:]
new_lines = lines[:374] + [''] + lines[551:]

with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\run_llm_scored_rag.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_lines))

print(f"Done. Old: {len(lines)} lines. New: {len(new_lines)} lines.")
