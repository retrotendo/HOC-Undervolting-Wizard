from pathlib import Path
p = Path('source/main.cpp')
s = p.read_text()
needle = 'constexpr int VDD2_STEP_UV = 12500;\n'
if needle not in s:
    raise SystemExit('constant insertion point not found')
if 'constexpr int UI_COL = 3;' not in s:
    s = s.replace(needle, needle + 'constexpr int UI_COL = 3; // legacy direct-print compatibility\n', 1)
p.write_text(s)
