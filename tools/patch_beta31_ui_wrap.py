from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

old = '''        uiPrintf(row++, "It looks like the console did not boot");
        uiPrintf(row++, "Requested value likely did not boot.");
'''
new = '''        uiPrintf(row++, "It looks like this value did not boot.");
'''
if old not in s:
    raise SystemExit('Expected recovery wording not found')

s = s.replace(old, new, 1)
p.write_text(s)

visible_lines = [
    'It looks like this value did not boot.',
    'Recovery restored last working value.',
    'Last good value: Low VMIN 000 mV',
    'A : Confirm last good value',
    'X : This is not correct',
]
for line in visible_lines:
    if len(line) > 39:
        raise SystemExit(f'beta31 line too wide ({len(line)}): {line}')

print('beta31 recovery wording refined')
