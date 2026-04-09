import httpx, json

key = 'AIzaSyAafF0zCnSftTJ-FTG0q9iZODl_mnrrMmo'
url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent'
params = {'key': key}

# Try without markdown wrapper, just plain JSON
large_toc = []
for i in range(300):
    large_toc.append({
        'structure': f'{i//10}.{i%10}',
        'title': f'Section number {i} with a moderately long title for testing output limits'
    })

toc_json = json.dumps(large_toc)
prompt = (
    'Transform this TOC into JSON. Return ONLY valid JSON, no markdown or explanation.\n'
    'Format: {"table_of_contents": [{"structure": "x.x", "title": "..."}]}\n\n'
    'TOC:\n' + toc_json
)

payload = {
    'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
    'generationConfig': {'temperature': 0, 'maxOutputTokens': 65536}
}
r = httpx.post(url, params=params, json=payload, timeout=60)
resp = r.json()
print('Status:', r.status_code)
print('Finish reason:', resp['candidates'][0].get('finish_reason', 'unknown'))
text = resp['candidates'][0]['content']['parts'][0]['text']
print('Response length (chars):', len(text))
print('Last 300 chars:', repr(text[-300:]))
print('Is valid JSON at end?', text.rstrip().endswith(']'))

# Count how many items made it
try:
    # Find last complete item
    parsed = json.loads(text.rstrip() + '"]}') if not text.rstrip().endswith(']') else json.loads(text)
    print('Items in response:', len(parsed.get('table_of_contents', [])))
except:
    # Count manually by finding structures
    import re
    matches = re.findall(r'"structure":\s*"(\d+\.\d+)"', text)
    print('Structure entries found:', len(matches))
    if matches:
        print('Last structure:', matches[-1])
