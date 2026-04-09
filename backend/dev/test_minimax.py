import sys
sys.path.insert(0, r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\libs\pageindex_agent")
from pageindex_agent.utils import ChatGPT_API, extract_json

prompt = 'Return JSON: {"answer": "hello world"}'
r = ChatGPT_API(model="MiniMax-M2.7", prompt=prompt)
print("Response:", r[:500] if r else "None")
if r:
    p = extract_json(r)
    print("Parsed:", p)
