import sys, os

libs_path = r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\libs\pageindex_agent"
if libs_path not in sys.path:
    sys.path.insert(0, libs_path)

from pageindex_agent.utils import ChatGPT_API

query = "what are the math requirements for the computational biology major?"
prompt = f'Return JSON: {{"answer": "test", "relevant_sections": []}}'
print("Calling ChatGPT_API...")
try:
    r = ChatGPT_API(model="MiniMax-M2.7", prompt=prompt)
    print("Response type:", type(r))
    print("Response[:200]:", r[:200] if r else "None/empty")
except Exception as e:
    print("EXCEPTION:", type(e).__name__, str(e))
