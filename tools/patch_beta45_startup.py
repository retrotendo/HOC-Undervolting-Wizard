from pathlib import Path

# Fix beta44 startup recursion before GUI init.
p = Path('source/main.cpp')
s = p.read_text()
old = '''void uiPresent() {
    if (gui::isInitialized()) gui::present();
    else uiPresent();
}
'''
new = '''void uiPresent() {
    if (gui::isInitialized()) gui::present();
    else consoleUpdate(nullptr);
}
'''
if old not in s:
    raise SystemExit('uiPresent recursion anchor not found')
s = s.replace(old, new, 1)
p.write_text(s)

# Bump application version.
p = Path('Makefile')
s = p.read_text()
old = 'APP_VERSION := 0.4.0-beta.44\n'
new = 'APP_VERSION := 0.4.0-beta.45\n'
if old not in s:
    raise SystemExit('beta44 version anchor not found')
s = s.replace(old, new, 1)
p.write_text(s)
