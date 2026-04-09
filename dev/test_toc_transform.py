import os, sys, httpx, json

key = 'AIzaSyAafF0zCnSftTJ-FTG0q9iZODl_mnrrMmo'
url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent'
params = {'key': key}

toc_content = '''1. University Information
   1.1 Vision
   1.2 Mission
2. Academic Programs
   2.1 Undergraduate'''

init_prompt = """You are given a table of contents, You job is to transform the whole table of content into a JSON format included table_of_contents.
structure is the numeric system which represents the index of the hierarchy section in the table of contents.
The response should be in the following JSON format:
{
table_of_contents: [
    {
        "structure": <structure index, "x.x.x"> (string),
        "title": <title of the section>
    },
    ...
],
}
You should transform the full table of contents in one go.
Directly return the final JSON structure, do not output anything else."""

prompt = init_prompt + "\n Given table of contents\n:" + toc_content

payload = {
    'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
    'generationConfig': {'temperature': 0}
}
r = httpx.post(url, params=params, json=payload, timeout=30)
print('Status:', r.status_code)
resp = r.json()
text = resp['candidates'][0]['content']['parts'][0]['text']
print('Response:', text[:1000])
print('Starts with ```json:', text.strip().startswith('```json'))
