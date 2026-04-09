import re

with open(r'C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\libs\pageindex_agent\pageindex_agent\utils.py', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Find _get_client
idx = content.find('def _get_client')
end_idx = content.find('\n\n', idx + 10)
segment = content[idx:end_idx]
with open(r'C:\Users\ethan\.openclaw\workspace\gradYOU8\dev\stream_code.txt', 'w', encoding='utf-8', errors='replace') as f:
    f.write(segment)
print("get_client:", len(segment), "chars")

# Find _reset_client
idx = content.find('def _reset_client')
end_idx = content.find('\n\n', idx + 10)
segment = content[idx:end_idx]
with open(r'C:\Users\ethan\.openclaw\workspace\gradYOU8\dev\stream_code.txt', 'w', encoding='utf-8', errors='replace') as f:
    f.write(segment)
print("reset_client:", len(segment), "chars")
