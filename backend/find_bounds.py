with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\backend\main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find tree_retrieve boundaries
func_line = None
for i, line in enumerate(lines):
    if line.startswith('def tree_retrieve('):
        func_line = i
        break

if func_line is None:
    print("ERROR: tree_retrieve not found")
    exit(1)

print(f"def tree_retrieve at line {func_line+1}")

# Find docstring end (next line that is just '    """')
doc_end = None
for i in range(func_line+1, min(func_line+10, len(lines))):
    if lines[i].strip() == '"""':
        doc_end = i
        break

print(f"Docstring ends at line {doc_end+1}: {repr(lines[doc_end][:40])}")

# Find return answer, sources
return_line = None
for i in range(doc_end+1, len(lines)):
    if '    return answer, sources' in lines[i]:
        return_line = i
        break

print(f"return at line {return_line+1}: {repr(lines[return_line][:60])}")

# Find # Routes section (has box drawing chars)
routes_line = None
for i in range(return_line+1, min(return_line+10, len(lines))):
    if '#' in lines[i] and 'Routes' in lines[i]:
        routes_line = i
        break

print(f"Routes section at line {routes_line+1}: {repr(lines[routes_line][:60])}")

# Print context around return
print("\nAround return:")
for i in range(return_line-2, return_line+3):
    print(f"  {i+1}: {repr(lines[i][:80])}")

print("\nAround routes:")
for i in range(routes_line-2, routes_line+3):
    print(f"  {i+1}: {repr(lines[i][:80])}")
