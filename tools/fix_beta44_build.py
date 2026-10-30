from pathlib import Path
p = Path('source/main.cpp')
s = p.read_text()
needle = 'bool g_guiPulse = false;\n'
if needle not in s:
    raise SystemExit('g_guiPulse anchor not found')
if 'void uiPresent();' not in s[:s.find('bool sampleVminVoltage')]:
    s = s.replace(needle, needle + '\nvoid uiPresent();\n', 1)
p.write_text(s)
