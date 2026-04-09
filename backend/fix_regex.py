with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\backend\main.py', 'r', encoding='utf-8') as f:
    c = f.read()

# The corrupted line is truncated. Find and replace it.
old = "            for match in re.finditer(r'(?i)^#{1,6}\s+([^"
new = "            for match in re.finditer(r'(?im)^#{1,6}\s+([^"

if old in c:
    c = c.replace(old, new)
    print("Fixed!")
else:
    print("Not found. Trying to find manually...")
    idx = c.find("re.finditer")
    print("re.finditer found at:", idx)
    print(repr(c[idx-30:idx+120]))

with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\backend\main.py', 'w', encoding='utf-8') as f:
    f.write(c)
