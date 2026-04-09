"""Replace audit_to_text in run_llm_scored_rag.py"""

with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\run_llm_scored_rag.py', 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')

# Find def audit_to_text
start_idx = None
for i, line in enumerate(lines):
    if line.startswith('def audit_to_text'):
        start_idx = i
        break

if start_idx is None:
    print("Could not find def audit_to_text")
    import sys; sys.exit(1)

print(f"Found def audit_to_text at line {start_idx+1}")

# Find end: next top-level def or class
end_idx = len(lines) - 1
for i in range(start_idx + 1, len(lines)):
    stripped = lines[i].strip()
    if stripped.startswith('def ') or stripped.startswith('class '):
        end_idx = i
        break

print(f"Replacing lines {start_idx+1} to {end_idx}")

# Read new function and split into lines
with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\_fix_audit_final.py', 'r', encoding='utf-8') as f:
    new_func_raw = f.read()

# Split the new function into lines (strip leading/trailing whitespace)
new_func_lines = new_func_raw.strip().split('\n')

# Rebuild with proper indentation
indented = []
for i, line in enumerate(new_func_lines):
    if i == 0:
        indented.append(line)  # first line: def audit_to_text(result):
    else:
        indented.append(line)  # already has correct indentation in the file

# Combine
new_lines = lines[:start_idx] + indented + lines[end_idx:]

with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\run_llm_scored_rag.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_lines))

print(f"Done. Old: {len(lines)} lines. New: {len(new_lines)} lines.")
