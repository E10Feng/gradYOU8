import os, httpx, json, time

api_key = os.environ.get("MINIMAX_API_KEY", "")
print(f"API key present: {bool(api_key)}")

client = httpx.Client(
    base_url='https://api.minimax.io/v1',
    headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
    timeout=httpx.Timeout(30.0, connect=10.0)
)

start = time.time()
try:
    r = client.post('/chat/completions', json={
        'model': 'MiniMax-M2.7',
        'messages': [{'role': 'user', 'content': 'Say hello in one sentence'}],
        'stream': True
    }, timeout=30)
    elapsed = time.time() - start
    print(f'Status: {r.status_code}, Time: {elapsed:.1f}s')
    print(f'Response preview: {r.text[:300]}')
except Exception as e:
    print(f'Error: {e}, Time: {time.time()-start:.1f}s')
