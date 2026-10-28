from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

def rep(old, new, label):
    global s
    if old not in s:
        raise SystemExit(f'{label} not found')
    s = s.replace(old, new, 1)

# Every generic test-start page keeps crash guidance visually attached to A.
rep('''void footerTest(int row) {\n    uiPrintf(row,     "Keys:");\n    uiPrintf(row + 1, "A : Start Test");\n    uiPrintf(row + 2, "+ : Known PASS / Skip step");\n    uiPrintf(row + 3, "X : Known FAIL / Skip");\n    uiPrintf(row + 4, "B : Exit");\n    printResetHint(row + 4);\n}\n''', '''void footerTest(int row) {\n    uiPrintf(row,     "Keys:");\n    uiPrintf(row + 1, "A : Start Test");\n    uiPrintf(row + 2, "    If the test crashes, reboot and");\n    uiPrintf(row + 3, "    open the Wizard again.");\n    uiPrintf(row + 4, "+ : Known PASS / Skip step");\n    uiPrintf(row + 5, "X : Known FAIL / Skip");\n    uiPrintf(row + 6, "B : Exit");\n    printResetHint(row + 6);\n}\n''', 'generic test footer')

# On tuning search pages, Known stable / Skip to next value must only advance
# the candidate. It must not open the config-check page or reboot. A remains
# the explicit check/apply action for the newly displayed candidate.
rep('''                if (cfgMask != Config_None) {\n                    // KNOWN PASS skips the reboot/stress validation, not the\n                    // requirement to actually have the requested HOC value set.\n                    if (verifyPersistentSettings(cfgMask)) {\n                        g_manualPass = true;\n                        handlePass();\n                        g_manualPass = false;\n                    } else {\n                        g_configPrompt = true;\n                    }\n                } else if (testPlan(g.stage, skipKind, skipSeconds)) {\n                    g_manualPass = true;\n                    handlePass();\n                    g_manualPass = false;\n                }\n''', '''                const bool searchSetting = g.stage == Stage::LowUvQuick ||\n                                           g.stage == Stage::LowVminQuick ||\n                                           g.stage == Stage::VddqQuick ||\n                                           g.stage == Stage::Vdd2Quick ||\n                                           g.stage == Stage::HighUvQuick;\n                if (cfgMask != Config_None && searchSetting) {\n                    g_manualPass = true;\n                    handlePass();\n                    g_manualPass = false;\n                } else if (cfgMask != Config_None) {\n                    if (verifyPersistentSettings(cfgMask)) {\n                        g_manualPass = true;\n                        handlePass();\n                        g_manualPass = false;\n                    } else {\n                        g_configPrompt = true;\n                    }\n                } else if (testPlan(g.stage, skipKind, skipSeconds)) {\n                    g_manualPass = true;\n                    handlePass();\n                    g_manualPass = false;\n                }\n''', 'known stable candidate advance')

p.write_text(s)
print('beta36 follow-up patch applied')
