import subprocess
import time
import urllib.request
import json
import os

# Kill any existing servers
os.system("netstat -ano | findstr :8000 | findstr LISTEN | for /f \"tokens=5\" %a in ('more') do taskkill /F /PID %a")

# Start fresh server on port 9000
proc = subprocess.Popen(
    [r"C:\Users\ethan\AppData\Local\Programs\Python\Python311\python.exe",
     "-m", "uvicorn", "main:app",
     "--host", "127.0.0.1", "--port", "9000"],
    cwd=r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend",
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

print("Waiting for server to start...")
time.sleep(5)

# Check if server is up
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
result = s.connect_ex(("127.0.0.1", 9000))
s.close()
if result == 0:
    print("Server is up on port 9000")
else:
    print("Server failed to start, checking output:")
    output, _ = proc.communicate(timeout=2)
    print(output)
    exit(1)

# Test the chat endpoint
payload = json.dumps({"question": "what are the core classes for the bio major?"}).encode()
req = urllib.request.Request(
    "http://127.0.0.1:9000/chat",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST"
)

try:
    with urllib.request.urlopen(req, timeout=120) as r:
        result = json.loads(r.read())
        print("\nStatus:", r.status)
        print("\nAnswer:")
        print(result["answer"])
        print("\nSources:")
        for s in result.get("sources", []):
            print(f"  - {s.get('title', 'no title')} [{s.get('school', '?')}]")
except Exception as e:
    print("\nError:", e)

proc.terminate()
