import sys
sys.path.insert(0, r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator')
from run_llm_scored_rag import run_query

q = 'If I am majoring in computational biology in arts and sciences and minoring in computer science in the engineering school, do CSE 1301 and CSE 2407 double count for both?'
print('='*60)
print('QUESTION:', q)
print('='*60)
run_query(q)
