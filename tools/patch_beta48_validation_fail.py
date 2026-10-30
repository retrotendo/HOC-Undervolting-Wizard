from pathlib import Path


def rep(text, old, new, label):
    if old not in text:
        raise SystemExit(f'missing pattern: {label}')
    return text.replace(old, new, 1)

p = Path('source/main.cpp')
s = p.read_text()

s = rep(s,
'''void footerTest(int row) {\n    uiPrintf(row,     "A : Start automatic stability test");\n    uiPrintf(row + 1, "    If the test crashes, reboot and");\n    uiPrintf(row + 2, "    open the Wizard again.");\n    uiPrintf(row + 3, "+ : Known PASS / Skip step");\n    uiPrintf(row + 4, "X : Known FAIL / Skip step");\n    uiPrintf(row + 5, "B : Exit");\n    printResetHint(row + 5);\n}\n''',
'''void footerTest(int row) {\n    uiPrintf(row,     "A : Start automatic stability test");\n    uiPrintf(row + 1, "    If the test crashes, reboot and");\n    uiPrintf(row + 2, "    open the Wizard again.");\n    uiPrintf(row + 3, "+ : Known PASS / Skip step");\n    uiPrintf(row + 4, "B : Exit");\n    printResetHint(row + 4);\n}\n''', 'validation footer')

s = rep(s,
'''        } else if (k & HidNpadButton_X) {\n            if (!isVminSweepStage(g.stage) && g.stage != Stage::Preparation && g.stage != Stage::Complete) {\n                handleFail(false);\n                redraw = true;\n            }\n        } else if (k & HidNpadButton_A) {\n''',
'''        } else if (k & HidNpadButton_X) {\n            // X is only a manual "known unstable" shortcut while searching a\n            // new candidate. Long/final validations record FAIL automatically;\n            // crashes/reboots are handled by the interrupted-test popup on restart.\n            const u32 cfgMask = activeConfigMask();\n            const bool searchSetting = g.stage == Stage::LowUvQuick ||\n                                       g.stage == Stage::LowVminQuick ||\n                                       g.stage == Stage::VddqQuick ||\n                                       g.stage == Stage::Vdd2Quick ||\n                                       g.stage == Stage::HighUvQuick;\n            if (cfgMask != Config_None && searchSetting) {\n                handleFail(false);\n                redraw = true;\n            }\n        } else if (k & HidNpadButton_A) {\n''', 'x handling')

p.write_text(s)
