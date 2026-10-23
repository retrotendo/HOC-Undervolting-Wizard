from pathlib import Path

# App preparation screen + result metadata
p = Path('source/main.cpp')
s = p.read_text()
repls = {
    'VDD2             : 1175 mV or known-stable lower value': 'VDD2             : 1175 mV',
    'VDDQ             : 600 mV or known-stable lower value': 'VDDQ             : 600 mV',
    'CPU UV Table     : 1683 MHz Tbreak or known-working table': 'CPU UV Table     : 1683 MHz Tbreak',
    'Low UV / High UV : 0 / 0, or known-stable values': 'Low UV / High UV : 0 / 0',
    'Low VMIN         : 620 mV or known-stable value': 'Low VMIN         : 620 mV',
    'CPU UV Table: user-selected (recommended: 1683 MHz Tbreak)': 'CPU UV Table: 1683 MHz Tbreak',
}
for old, new in repls.items():
    if old not in s:
        raise SystemExit(f'main.cpp marker not found: {old}')
    s = s.replace(old, new, 1)
p.write_text(s)

# README: setup is now deliberately fixed to the guide baseline.
p = Path('README.md')
s = p.read_text()
repls = {
    'For RAM testing, Homebrew Menu **title takeover / full application mode** is strongly recommended.':
        'The Wizard requires Homebrew Menu **title takeover / Full Application Mode**. Applet Mode is blocked at startup.',
    'Prepare the Battery profile before tuning. Conservative defaults may be replaced by values already proven stable on your own console.':
        'Prepare the Battery profile before tuning using the exact guide starting values below. If you already know stable values, use the Wizard\'s KNOWN PASS / SKIP controls during the corresponding tuning stages instead of changing the starting baseline.',
    '- **VDD2: 1175 mV**, or a known-stable lower value': '- **VDD2: 1175 mV**',
    '- **VDDQ: 600 mV**, or a known-stable lower value': '- **VDDQ: 600 mV**',
    '- **CPU UV Table: 1683 MHz Tbreak**, or another known-working table': '- **CPU UV Table: 1683 MHz Tbreak**',
    '- **Low UV: 0**, or a known-stable value': '- **Low UV: 0**',
    '- **High UV: 0**, or a known-stable value': '- **High UV: 0**',
    '- **Low VMIN: 620 mV**, or a known-stable value': '- **Low VMIN: 620 mV**',
}
for old, new in repls.items():
    if old not in s:
        raise SystemExit(f'README marker not found: {old}')
    s = s.replace(old, new, 1)

marker = '# New in v0.4.0-beta.6\n'
block = '''# New in v0.4.0-beta.7\n\n- Preparation now shows only the exact Battery-guide starting values.\n- Removed all \"or known-stable/known-working value\" alternatives from the setup screen and setup documentation.\n- Previously validated personal values are handled only through **KNOWN PASS / SKIP** during the relevant tuning stages.\n- Clarified that Full Application Mode is required, matching the beta.6 startup blocker.\n\n---\n\n# New in v0.4.0-beta.6\n'''
if marker not in s:
    raise SystemExit('README beta6 marker not found')
s = s.replace(marker, block, 1)
p.write_text(s)

# Version
p = Path('Makefile')
s = p.read_text()
old = 'APP_VERSION := 0.4.0-beta.6'
if old not in s:
    raise SystemExit('Makefile beta6 version not found')
p.write_text(s.replace(old, 'APP_VERSION := 0.4.0-beta.7', 1))

# Changelog
p = Path('CHANGELOG.md')
s = p.read_text()
entry = '''## v0.4.0-beta.7\n\n- Use only the exact Battery-guide baseline values on the Preparation screen.\n- Remove alternative \"known-stable\" and \"known-working\" setup values.\n- Keep previously validated user values supported through KNOWN PASS / SKIP at the relevant test stages.\n- Clarify Full Application Mode as required rather than recommended.\n\n'''
if '## v0.4.0-beta.7' not in s:
    first = s.find('## ')
    s = s[:first] + entry + s[first:] if first >= 0 else s + '\n' + entry
p.write_text(s)

Path('RELEASE_NOTES_v0.4.0-beta.7.md').write_text('''# HOC Undervolting Wizard v0.4.0-beta.7\n\nThis beta makes the Preparation screen match the Battery guide exactly.\n\n## Fixed starting baseline\n\nThe setup screen no longer suggests replacing guide defaults with previously known personal values. It now always asks for the defined guide baseline:\n\n- HP Mode: OFF\n- RAM Max Clock: 1600 MHz\n- VDD2: 1175 mV\n- VDDQ: 600 mV\n- CPU Max Clock: lowest selectable (currently 1963 MHz on current Mariko HOC builds)\n- CPU UV Table: 1683 MHz Tbreak\n- Low UV / High UV: 0 / 0\n- Low VMIN: 620 mV\n- High VMIN: 750 mV\n- CPU Boost Clock: lowest selectable, stock workflow target 1785 MHz\n\nUsers who already know stable values should keep using **KNOWN PASS / SKIP** during the corresponding tuning stages. This preserves one consistent starting state for every new run while still allowing experienced users to fast-forward.\n\nFull Application Mode remains mandatory; Applet Mode is blocked at startup.\n\nThis remains a pre-release until validated on real Mariko / Switch OLED hardware.\n''')
