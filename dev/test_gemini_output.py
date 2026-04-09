import httpx, json

key = 'AIzaSyAafF0zCnSftTJ-FTG0q9iZODl_mnrrMmo'
url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent'
params = {'key': key}

# Build a large TOC matching WaShU-style entries
large_toc = []
for i in range(300):
    large_toc.append({
        'structure': f'{i//10}.{i%10}',
        'title': f'Section number {i} with a moderately long title for testing output limits'
    })

toc_json = json.dumps(large_toc)
prompt = (
    'Transform this TOC into JSON. Return ONLY the JSON array.\n'
    'Format: {"table_of_contents": [{"structure": "x.x", "title": "..."}]}\n\n'
    'TOC:\n' + toc_json
)

# Test with explicit maxOutputTokens=65536
payload = {
    'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
    'generationConfig': {'temperature': 0, 'maxOutputTokens': 65536}
}
r = httpx.post(url, params=params, json=payload, timeout=60)
resp = r.json()
text = resp['candidates'][0]['content']['parts'][0]['text']
finish = resp['candidates'][0].get('finish_reason', 'unknown')
print('Response length:', len(text))
print('Finish reason:', finish)
print('Last 200 chars:', repr(text[-200:]))
print('Ends with valid JSON?', text.rstrip().endswith(']'))
