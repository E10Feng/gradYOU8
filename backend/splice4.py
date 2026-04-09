# Read the new function
with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\backend\new_tree_retrieve.txt', 'r') as f:
    new_func = f.read()

# Read main.py
with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\backend\main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find tree_retrieve start: the def line
import re
m = re.search(r'^def tree_retrieve\(', content, re.MULTILINE)
if not m:
    print("ERROR: tree_retrieve def not found")
    exit(1)
func_start = m.start()

# Find the next top-level section after tree_retrieve
rest = content[func_start:]
m2 = re.search(r'^# .+-{10,}', rest[10:], re.MULTILINE)
if m2:
    func_end = func_start + 10 + m2.start()
else:
    func_end = len(content)

print(f"Replacing chars {func_start}-{func_end} ({func_end-func_start} chars)")

new_content = content[:func_start] + new_func + "\n" + content[func_end:]
with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\backend\main.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f"Done! New content length: {len(new_content)}")
