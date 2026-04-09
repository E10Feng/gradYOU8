import os, sys
sys.path.insert(0, '.')
sys.path.insert(0, 'libs/pageindex_agent')
sys.path.insert(0, 'libs/pageindex_agent/pageindex_agent')
from dotenv import load_dotenv
load_dotenv('.env', override=True)
print("MINIMAX_API_KEY:", os.getenv('MINIMAX_API_KEY', 'NOT SET')[:10])
print("CWD:", os.getcwd())
from utils import ChatGPT_API
try:
    result = ChatGPT_API(model='MiniMax-M2.7', prompt='Say exactly: HELLO')
    print("API RESULT:", result[:100])
except Exception as e:
    print("API ERROR:", str(e)[:200])
