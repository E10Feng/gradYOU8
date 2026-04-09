with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "rb") as f:
    content = f.read().decode("utf-8", errors="replace")

# Fix double CRLF
content = content.replace("\r\r\n", "\r\n")

# Fix for-loop
old_loop = '    for title, text in matched:\r\n        if title not in seen and len(text) > 200:'
new_loop = '    for node in matched:\r\n        title = node.get("title", "")\r\n        text = node.get("text", "")\r\n        if title not in seen and len(text) > 200:'

if old_loop in content:
    content = content.replace(old_loop, new_loop)
    print("Fix 1 done")
else:
    print("WARNING: could not find old for-loop")
    idx = content.find("for title, text in matched")
    if idx >= 0:
        print(repr(content[idx - 20:idx + 100]))

# Fix kw_key
content = content.replace("kw_key.lower().split()", "query_keywords")
print("Fix 2 done")

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "w", encoding="utf-8", newline="\r\n") as f:
    f.write(content)

print("Written OK")

# Verify
with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "rb") as f:
    verify = f.read().decode("utf-8", errors="replace")
print("Double CRLF count:", verify.count("\r\r\n"))
idx = verify.find("for node in matched")
print("for node in matched found at:", idx)
