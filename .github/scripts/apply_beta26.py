from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

# Preparation NOT READY: remove top baseline/debug controls and start content normally.
old = '''    if (g.stage == Stage::Preparation) {\n        uiPrintf(4, "X : Use current tuning as baseline");\n        uiPrintf(5, "\\x1b[33mY : RAW CONFIG DEBUG\\x1b[0m");\n    }\n    if (!g_configCheck.readOk) {\n        const int r = (g.stage == Stage::Preparation) ? 7 : 5;'''
new = '''    if (!g_configCheck.readOk) {\n        const int r = 5;'''
if old not in s:
    raise SystemExit('config prompt header anchor not found')
s = s.replace(old, new, 1)

old = '''    const u32 m = g_configCheck.mask;\n    int row = (g.stage == Stage::Preparation) ? 7 : 5;'''
new = '''    const u32 m = g_configCheck.mask;\n    int row = 5;'''
if old not in s:
    raise SystemExit('config prompt row anchor not found')
s = s.replace(old, new, 1)

# Put Use Current with the normal action options at the bottom.
old = '''    uiPrintf(row + 1, "Fix \\x1b[31mWRONG\\x1b[0m values in Horizon OC.");\n    uiPrintf(row + 3, "A : Check again");\n    uiPrintf(row + 4, "B : Back");\n    consoleUpdate(nullptr);'''
new = '''    uiPrintf(row + 1, "Fix \\x1b[31mWRONG\\x1b[0m values in Horizon OC.");\n    uiPrintf(row + 3, "A : Check again");\n    if (g.stage == Stage::Preparation) {\n        uiPrintf(row + 4, "X : Use current settings as baseline");\n        uiPrintf(row + 5, "B : Back");\n    } else {\n        uiPrintf(row + 4, "B : Back");\n    }\n    consoleUpdate(nullptr);'''
if old not in s:
    raise SystemExit('config prompt footer anchor not found')
s = s.replace(old, new, 1)

# Reboot page: show recovery instructions before offering restart.
old = '''    else if (m & Config_HighUv)\n        uiPrintf(6, "\\x1b[32mHigh UV %d is set.\\x1b[0m", targetHighUv());\n    uiPrintf(9, "A : Restart console");\n    uiPrintf(10, "B : Back");\n    consoleUpdate(nullptr);'''
new = '''    else if (m & Config_HighUv)\n        uiPrintf(6, "\\x1b[32mHigh UV %d is set.\\x1b[0m", targetHighUv());\n\n    uiPrintf(9, "\\x1b[33mIf the console does NOT boot:\\x1b[0m");\n    uiPrintf(10, "1. In Hekate start CFW No OC.");\n    if (m & Config_LowUv)\n        uiPrintf(11, "2. Lower Low UV by one step.");\n    else\n        uiPrintf(11, "2. Restore the previous safe value.");\n    uiPrintf(12, "3. Restart normal CFW.");\n    uiPrintf(13, "4. Open the Wizard again.");\n\n    uiPrintf(16, "A : Restart console");\n    uiPrintf(17, "B : Back");\n    consoleUpdate(nullptr);'''
if old not in s:
    raise SystemExit('reboot confirm anchor not found')
s = s.replace(old, new, 1)

# Preparation page: no Known PASS / Skip here.
old = '''    uiPrintf(29, "A : Check settings");\n    uiPrintf(30, "X : Use current settings as baseline");\n    uiPrintf(31, "+ : Known PASS / Skip");\n    uiPrintf(32, "B : Exit    - : Reset");'''
new = '''    uiPrintf(29, "A : Check settings");\n    uiPrintf(30, "X : Use current settings as baseline");\n    uiPrintf(31, "B : Exit    - : Reset");'''
if old not in s:
    raise SystemExit('preparation footer anchor not found')
s = s.replace(old, new, 1)

# Remove the hidden RAW CONFIG DEBUG hotkey from the NOT READY page.
old = '''            if ((k & HidNpadButton_X) && g.stage == Stage::Preparation) {\n                if (captureCurrentSettingsBaseline()) {\n                    g_configPrompt = false;\n                    g_rebootConfirm = true;\n                }\n                redraw = true;\n            } else if ((k & HidNpadButton_Y) && g.stage == Stage::Preparation) {\n                openConfigDebug();\n                redraw = true;\n            } else if (k & HidNpadButton_A) {'''
new = '''            if ((k & HidNpadButton_X) && g.stage == Stage::Preparation) {\n                if (captureCurrentSettingsBaseline()) {\n                    g_configPrompt = false;\n                    g_rebootConfirm = true;\n                }\n                redraw = true;\n            } else if (k & HidNpadButton_A) {'''
if old not in s:
    raise SystemExit('config prompt input anchor not found')
s = s.replace(old, new, 1)

# Preparation must not accept the hidden + skip input either.
old = '''        } else if (k & HidNpadButton_Plus) {\n            if (isVminSweepStage(g.stage)) {'''
new = '''        } else if ((k & HidNpadButton_Plus) && g.stage != Stage::Preparation) {\n            if (isVminSweepStage(g.stage)) {'''
if old not in s:
    raise SystemExit('plus input anchor not found')
s = s.replace(old, new, 1)

p.write_text(s)

# Version bump for test release.
make = Path('Makefile')
ms = make.read_text()
ms = ms.replace('APP_VERSION := 0.4.0-beta.25', 'APP_VERSION := 0.4.0-beta.26', 1)
make.write_text(ms)

upd = Path('UPDATE.txt')
us = upd.read_text()
us = us.replace('0.4.0-beta.25', '0.4.0-beta.26')
upd.write_text(us)
