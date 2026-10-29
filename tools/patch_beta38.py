from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()
old = '''        uiPrintf(row++, "+ : Known stable / Skip to next value");
        uiPrintf(row++, "B : Exit");
        printResetHint(row - 1);
'''
new = '''        uiPrintf(row++, "+ : Known stable / Skip to next value");
        uiPrintf(row++, "X : Known unstable / Use last good value");
        uiPrintf(row++, "B : Exit");
        printResetHint(row - 1);
'''
if s.count(old) != 1:
    raise SystemExit(f'expected exactly one search-page action block, found {s.count(old)}')
s = s.replace(old, new, 1)
p.write_text(s)

m = Path('Makefile')
ms = m.read_text()
oldv = 'APP_VERSION := 0.4.0-beta.37'
newv = 'APP_VERSION := 0.4.0-beta.38'
if oldv not in ms:
    raise SystemExit('beta37 version line not found')
m.write_text(ms.replace(oldv, newv, 1))
