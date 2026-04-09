import httpx, json

key = 'AIzaSyAafF0zCnSftTJ-FTG0q9iZODl_mnrrMmo'
url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent'
params = {'key': key}

# Build a large TOC list
large_toc = []
for i in range(300):
    large_toc.append({
        'structure': f'{i//10}.{i%10}',
        'title': f'Section number {i} with a moderately long title for testing'
    })

toc_json = json.dumps(large_toc)
prompt = (
    'Transform this TOC into JSON with format: '
    '{"table_of_contents": [{"structure": "x.x", "title": "..."}]} '
    'Return ONLY the JSON, no explanation.\n\nTOC:\n'
    + toc_json
)

payload = {
    'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
    'generationConfig': {'temperature': 0, 'maxOutputTokens': 8192}
}
r = httpx.post(url, params=params, json=payload, timeout=30)
resp = r.json()
text = resp['candidates'][0]['content']['parts'][0]['text']
print('Response length:', len(text))
print('Last 300 chars:', repr(text[-300:]))
print()
print('Ends with valid JSON array?', text.rstrip().endswith(']'))
print('Has truncation marker?', '...' in text)
