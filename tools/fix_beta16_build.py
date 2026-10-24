from pathlib import Path
p=Path('source/main.cpp')
s=p.read_text()
old='''    std::sort(samples, samples + count);\n    latest.cpuVoltageUv = samples[count / 2];'''
new='''    // Median of exactly three samples without std::sort's large-range template path.\n    if (samples[0] > samples[1]) std::swap(samples[0], samples[1]);\n    if (samples[1] > samples[2]) std::swap(samples[1], samples[2]);\n    if (samples[0] > samples[1]) std::swap(samples[0], samples[1]);\n    latest.cpuVoltageUv = samples[1];'''
if old not in s: raise SystemExit('median marker not found')
s=s.replace(old,new,1)
# Remove helpers no longer used after guided reboot refactor.
for block in [
'''bool isQuickStage(Stage s) {\n    return s == Stage::LowUvQuick || s == Stage::LowVminQuick ||\n           s == Stage::VddqQuick || s == Stage::Vdd2Quick ||\n           s == Stage::HighUvQuick;\n}\n\n''',
'''void printSafeRecovery(const char* menu, const std::string& restoreText) {\n    uiPrintf(5, "@ Horizon OC");\n    uiPrintf(7, "\\x1b[33mPrevious setting did not boot\\x1b[0m");\n    uiPrintf(9, "Recovery:");\n    uiPrintf(10, " - Boot Hekate without hoc.kip");\n    uiPrintf(11, " - Open Horizon OC");\n    uiPrintf(12, "%s:", menu);\n    uiPrintf(13, " - Restore : %s", restoreText.c_str());\n    uiPrintf(14, " - Reboot CFW");\n}\n\n''',
'''void enterLowUvLong(bool recovery) { g.stage = Stage::LowUvLong; g.recoveryNeeded = recovery; saveState(); }\nvoid enterLowVminLong(bool recovery) { restartVminSweep(recovery); }\nvoid enterVddqLong(bool recovery) { g.stage = Stage::VddqLong; g.recoveryNeeded = recovery; saveState(); }\nvoid enterVdd2Long(bool recovery) { g.stage = Stage::Vdd2Long; g.recoveryNeeded = recovery; saveState(); }\nvoid enterHighUvLong(bool recovery) { g.stage = Stage::HighUvLong; g.recoveryNeeded = recovery; saveState(); }\n\n''']:
    s=s.replace(block,'')
p.write_text(s)
