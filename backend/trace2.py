import json, urllib.request, os, re

tree_path = r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_arts_sciences.tree.json'
with open(tree_path, encoding='utf-8', errors='replace') as f:
    tree = json.load(f)

structure = tree.get('structure', [])

def summarize_tree(nodes, depth=0):
    lines = []
    for node in nodes:
        indent = '  ' * depth
        title = node.get('title', '')
        start = node.get('start_index', '?')
        end = node.get('end_index', '?')
        summary = node.get('summary', '')[:80]
        lines.append('{}- [{}] {} | {}'.format(indent, start, end, summary))
        if node.get('nodes'):
            lines.extend(summarize_tree(node['nodes'], depth+1))
    return lines

overview = '\n'.join(summarize_tree(structure))
print('Overview length:', len(overview))
print('First 400 chars:')
print(overview[:400])

query = 'how many credits is the biology major'
prompt = 'You are a WashU degree requirement assistant.\nA student asks: "' + query + '"\n\nHere is the table of contents:\n\n' + overview + '\n\nReturn ONLY JSON with relevant_sections and answer.'

# Call MiniMax
token = os.getenv('MINIMAX_API_KEY', '')
messages = [{'role': 'user', 'content': prompt}]
payload = json.dumps({'model': 'MiniMax-M2.7', 'messages': messages, 'max_tokens': 8000}).encode()
req = urllib.request.Request(
    'https://api.minimax.io/v1/chat/completions',
    data=payload,
    headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
    method='POST'
)
try:
    with urllib.request.urlopen(req, timeout=120) as r:
        result = json.loads(r.read())
        raw = result['choices'][0]['message']['content']
        print('\nMiniMax response (first 500 chars):')
        print(raw[:500])
except Exception as e:
    print('API error:', e)
