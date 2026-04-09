import json
with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\student_profile.json') as f:
    p = json.load(f)

print('All semesters:', [s['term'] for s in p['semesters']])
print()
print('CSE/SDS courses taken:')
for sem in p['semesters']:
    for c in sem['courses']:
        if 'CSE' in c['code'] or 'SDS' in c['code'] or 'MATH' in c['code']:
            print(f'  {sem["term"]}: {c["code"]} - {c["title"]} ({c["grade"]})')
print()
print('Cumulative:', p.get('cumulative', {}))
