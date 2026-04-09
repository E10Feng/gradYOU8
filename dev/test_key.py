import httpx
import json

API_KEY = "sk-cp-eONyc1lsRF8VqUMKE41edOMcpXnFqd_vFFtJVZ_ZlrDOWofcj3eWqkiSU7nrNZwuyqDLzc8UyP3Lljh3DwzKFIyOaDqo3ok22P_V3kr-MpydccZcXl60bpQ"
BASE_URL = "https://api.minimax.io/v1"

print("Testing Minimax API...")
print(f"URL: {BASE_URL}/chat/completions")

try:
    response = httpx.post(
        f"{BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "MiniMax-M2.7",
            "messages": [{"role": "user", "content": "Reply with OK"}],
            "stream": False,
        },
        timeout=30.0,
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
