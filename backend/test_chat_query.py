import urllib.request, json, sys
sys.stdout.reconfigure(encoding='utf-8')
body = json.dumps({'question': 'what courses are required for the genomics and computation track of the biology major'}).encode()
req = urllib.request.Request('http://localhost:8001/chat', data=body, headers={'Content-Type': 'application/json'}, method='POST')
try:
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read())
        print('Sources:')
        for i, s in enumerate(resp.get('sources', [])):
            print(f'  [{i}] {s.get("title","")[:70]}')
        print()
        print('Answer[:400]:', resp.get('answer','')[:400])
except Exception as e:
    print('Error:', e)
