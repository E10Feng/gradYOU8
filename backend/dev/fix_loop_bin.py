with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "rb") as f:
    content = f.read()

# Normalize: replace \r\r\n with \r\n
normalized = content.replace(b'\r\r\n', b'\r\n')

# Now fix the loop
old_bytes = (
    b'    for title, text in matched:\r\n'
    b'        if title not in seen and len(text) > 200:'
)
new_bytes = (
    b'    for node in matched:\r\n'
    b'        title = node.get("title", "")\r\n'
    b'        text = node.get("text", "")\r\n'
    b'        if title not in seen and len(text) > 200:'
)

if old_bytes in normalized:
    normalized = normalized.replace(old_bytes, new_bytes)
    print("Fix 1 done: for-loop updated")
else:
    print("WARNING: could not find old for-loop")
    idx = normalized.find(b'for title, text in matched')
    if idx >= 0:
        print(repr(normalized[idx - 20:idx + 100]))

# Fix kw_key
normalized = normalized.replace(b'kw_key.lower().split()', b'query_keywords')
print("Fix 2 done: kw_key replaced")

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "wb") as f:
    f.write(normalized)

print("Written OK")

# Verify
with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "rb") as f:
    verify = f.read()
print("CRCRLF count:", verify.count(b'\r\r\n'))
print("Normal CRLF:", verify.count(b'\r\n') - verify.count(b'\r\r\n'))
idx = verify.find(b'for node in matched')
print("for node in matched at:", idx)
