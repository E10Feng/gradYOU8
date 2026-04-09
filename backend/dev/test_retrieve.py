import sys, os
sys.path.insert(0, r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend")
os.chdir(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend")
from main import tree_retrieve, load_tree

tree = load_tree()
query = "what are the math requirements for the computational biology major?"
print("Calling tree_retrieve...")
answer, sources = tree_retrieve(query, tree, model="MiniMax-M2.7")
print("Answer:", answer[:1000] if answer else "None")
print("Sources:", sources[:2] if sources else "[]")
