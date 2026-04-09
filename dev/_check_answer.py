import json, sys
sys.path.insert(0, r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator')

# Check what's in the saved answer
with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\rag_answer.json') as f:
    content = f.read()

print('File size:', len(content))
print()

# Try to find the answer portion
try:
    d = json.loads(content)
    ans = d.get('answer', '')
    print('Answer length:', len(ans))
    print()
    # Print just the last 1000 chars (end of answer)
    print('=== END OF ANSWER ===')
    print(ans[-1000:])
except Exception as e:
    print('Error:', e)
    print('Content snippet:', content[:500])
