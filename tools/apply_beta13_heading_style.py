from pathlib import Path
import re

# One-shot patch for beta.13 UI hierarchy.
p = Path('source/main.cpp')
s = p.read_text()

s = s.replace(
'''void printSafeRecovery(const char* menu, const std::string& restoreText) {
    uiPrintf(5, "\\x1b[33mPrevious setting did not boot\\x1b[0m");
    uiPrintf(7, "Recovery:");
    uiPrintf(8, "1. Boot Hekate without hoc.kip");
    uiPrintf(9, "2. Open Horizon OC");
    uiPrintf(10, "%s:", menu);
    uiPrintf(11, "Restore : %s", restoreText.c_str());
    uiPrintf(12, "3. Reboot CFW");
}
''',
'''void printSafeRecovery(const char* menu, const std::string& restoreText) {
    uiPrintf(5, "@ Horizon OC");
    uiPrintf(7, "\\x1b[33mPrevious setting did not boot\\x1b[0m");
    uiPrintf(9, "Recovery:");
    uiPrintf(10, " - Boot Hekate without hoc.kip");
    uiPrintf(11, " - Open Horizon OC");
    uiPrintf(12, "%s:", menu);
    uiPrintf(13, " - Restore : %s", restoreText.c_str());
    uiPrintf(14, " - Reboot CFW");
}
''')

s = s.replace(
'''void printOverrides(int row, const OverrideExpectation& e) {
    uiPrintf(row,     "Overrides:");
    uiPrintf(row + 1, "CPU : %s", formatClock(e.cpuHz).c_str());
    uiPrintf(row + 2, "GPU : %s", formatClock(e.gpuHz).c_str());
    uiPrintf(row + 3, "RAM : %s", formatClock(e.ramHz).c_str());
}
''',
'''void printOverrides(int row, const OverrideExpectation& e) {
    uiPrintf(row,     "Temporary Overrides:");
    uiPrintf(row + 1, " - CPU : %s", formatClock(e.cpuHz).c_str());
    uiPrintf(row + 2, " - GPU : %s", formatClock(e.gpuHz).c_str());
    uiPrintf(row + 3, " - RAM : %s", formatClock(e.ramHz).c_str());
}
''')

prep_pattern = re.compile(r'void renderPreparation\(\) \{.*?\n\}\n\nbool isVminSweepStage', re.S)
prep_new = '''void renderPreparation() {
    title();
    uiPrintf(5, "@ Horizon OC");

    uiPrintf(7, "General:");
    uiPrintf(8, " - Uncapped Clocks : OFF");

    uiPrintf(10, "RAM Settings:");
    uiPrintf(11, " - HP Mode         : OFF");
    uiPrintf(12, " - RAM Max         : 1600 MHz");
    uiPrintf(13, " - VDD2            : 1175 mV");
    uiPrintf(14, " - VDDQ            : 600 mV");

    uiPrintf(16, "CPU Settings:");
    uiPrintf(17, " - CPU Max         : Lowest selectable (1963)");
    uiPrintf(18, " - Low VMIN        : 620 mV");
    uiPrintf(19, " - High VMIN       : 750 mV");

    uiPrintf(21, "CPU UV:");
    uiPrintf(22, " - UV Table        : 1683 MHz Tbreak");
    uiPrintf(23, " - Low UV          : 0");
    uiPrintf(24, " - High UV         : 0");

    uiPrintf(26, "@ HOC Toolkit");
    uiPrintf(28, " - CPU Boost       : Lowest selectable / 1785");

    uiPrintf(30, "Then:");
    uiPrintf(31, " - Reboot CFW and reopen Wizard");
    uiPrintf(33, "Keys:");
    uiPrintf(34, "A : Setup done / Start");
    uiPrintf(35, "B : Exit    - : Reset");
}

bool isVminSweepStage'''
s, n = prep_pattern.subn(prep_new, s, count=1)
if n != 1:
    raise SystemExit('renderPreparation block not found')

needle = '''    int row = 5;\n\n    switch (g.stage) {'''
replacement = '''    int row = 5;\n    const bool recoveryPage = g.recoveryNeeded &&\n        (g.stage == Stage::LowUvLong || g.stage == Stage::VddqLong ||\n         g.stage == Stage::Vdd2Long || g.stage == Stage::HighUvLong);\n    if (!recoveryPage) {\n        uiPrintf(row++, "@ Horizon OC");\n        row++;\n    }\n\n    switch (g.stage) {'''
if needle not in s:
    raise SystemExit('renderTestStage insertion point not found')
s = s.replace(needle, replacement, 1)

s = s.replace('printSafeRecovery("CPU UV", "Low UV = " + std::to_string(g.lowUvGood)); row = 14;',
              'printSafeRecovery("CPU UV", "Low UV = " + std::to_string(g.lowUvGood)); row = 16;')
s = s.replace('printSafeRecovery("RAM Settings", "VDDQ = " + std::to_string(g.vddqGood) + " mV"); row = 14;',
              'printSafeRecovery("RAM Settings", "VDDQ = " + std::to_string(g.vddqGood) + " mV"); row = 16;')
s = s.replace('printSafeRecovery("RAM Settings", "VDD2 = " + formatVdd2(g.vdd2GoodUv)); row = 14;',
              'printSafeRecovery("RAM Settings", "VDD2 = " + formatVdd2(g.vdd2GoodUv)); row = 16;')
s = s.replace('printSafeRecovery("CPU UV", "High UV = " + std::to_string(g.highUvGood)); row = 14;',
              'printSafeRecovery("CPU UV", "High UV = " + std::to_string(g.highUvGood)); row = 16;')

labels = [
    'Low UV : %d', 'Low UV   : %d', 'Low VMIN : %d mV', 'Floor CPU: %s',
    'VDD2 : %s', 'VDDQ : %d mV', 'High UV : %d', 'Low UV  : %d',
    'High UV : %d', 'Low VMIN: %d mV'
]
for label in labels:
    s = s.replace('"' + label + '"', '" - ' + label + '"')

s = s.replace(
'''void renderRealWorld() {
    title();
    uiPrintf(5, "Temporary Overrides:");
    uiPrintf(6, "Remove all Overrides");
''',
'''void renderRealWorld() {
    title();
    uiPrintf(5, "@ Horizon OC");
    uiPrintf(7, "Temporary Overrides:");
    uiPrintf(8, " - Remove all Overrides");
''')
s = s.replace('    uiPrintf(8, "Test:");\n    uiPrintf(9, "1 hour Tears of the Kingdom");\n    uiPrintf(10, "Fast travel / battles / loading");\n    uiPrintf(11, "Home + Sleep/Wake");\n    uiPrintf(13, "Keys:");\n    uiPrintf(14, "A : PASS");\n    uiPrintf(15, "X : FAIL");\n    uiPrintf(16, "B : Exit");',
              '    uiPrintf(10, "Test:");\n    uiPrintf(11, "1 hour Tears of the Kingdom");\n    uiPrintf(12, "Fast travel / battles / loading");\n    uiPrintf(13, "Home + Sleep/Wake");\n    uiPrintf(15, "Keys:");\n    uiPrintf(16, "A : PASS");\n    uiPrintf(17, "X : FAIL");\n    uiPrintf(18, "B : Exit");')

p.write_text(s)

p = Path('Makefile')
s = p.read_text().replace('APP_VERSION := 0.4.0-beta.12', 'APP_VERSION := 0.4.0-beta.13')
p.write_text(s)

p = Path('UPDATE.txt')
p.write_text('''version=0.4.0-beta.13\nnro_url=https://github.com/retrotendo/HOC-Undervolting-Wizard/releases/download/v0.4.0-beta.13/HOC-Undervolting-Wizard.nro\nsha_url=https://github.com/retrotendo/HOC-Undervolting-Wizard/releases/download/v0.4.0-beta.13/HOC-Undervolting-Wizard.nro.sha256\n''')

p = Path('README.md')
s = p.read_text()
marker = '# New in v0.4.0-beta.12\n'
section = '''# New in v0.4.0-beta.13\n\n- Keep the beta.12 right-side layout, but make the application hierarchy explicit.\n- Horizon OC values are shown under one **@ Horizon OC** heading, with the actual submenu below it (General, RAM Settings, CPU Settings, CPU UV, Temporary Overrides).\n- HOC Toolkit values are separated under **@ HOC Toolkit**.\n- Child settings use a compact `- setting : value` table style for quick reading while Ultrahand is open.\n- Tuning, reboot, test, VMIN and updater logic are unchanged.\n\n---\n\n'''
if marker not in s:
    raise SystemExit('README beta12 marker not found')
s = s.replace(marker, section + marker, 1)
p.write_text(s)

p = Path('CHANGELOG.md')
s = p.read_text()
entry = '''## v0.4.0-beta.13\n- Add top-level `@ Horizon OC` / `@ HOC Toolkit` headings.\n- Keep Horizon OC submenu names as second-level headings.\n- Use compact child-row formatting for settings and Temporary Overrides.\n- No tuning/test logic changes.\n\n'''
p.write_text(entry + s)
