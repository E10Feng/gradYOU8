import sys, json, re, traceback
from pathlib import Path
sys.path.insert(0, str(Path('.') / 'libs' / 'pageindex_agent'))
sys.path.insert(0, str(Path('.')))

# Load tree
DATA_DIR = Path(__file__).parent.parent / "data"
with open(DATA_DIR / 'bulletin_full.tree.json', 'r', encoding='utf-8') as f:
    tree_raw = json.load(f)
tree = {'structure': tree_raw, 'doc_name': 'WashU Bulletin (Full)'} if isinstance(tree_raw, list) else tree_raw

from main import agentic_retrieve, TOOL_DEFINITIONS, AGENT_SYSTEM_PROMPT
from pageindex_agent.utils import ChatGPT_API, _call_minimax_stream

# Test direct call
messages = [
    {'role': 'system', 'content': AGENT_SYSTEM_PROMPT},
    {'role': 'user', 'content': 'what are all the courses that satisfy the area B component of the biology major'},
]

print('Testing direct ChatGPT_API call with tools...')
try:
    response, finish_reason, tool_calls = ChatGPT_API(
        model='MiniMax-M2.7',
        prompt=messages[-1]['content'],
        chat_history=messages[:-1],
        tools=TOOL_DEFINITIONS,
    )
    print('Response type:', type(response))
    print('finish_reason:', finish_reason)
    print('tool_calls is not None:', tool_calls is not None)
    if tool_calls:
        print('tool_calls count:', len(tool_calls))
    resp_preview = str(response)[:200] if response else 'EMPTY'
    print('Response preview:', resp_preview)
except Exception as e:
    traceback.print_exc()
