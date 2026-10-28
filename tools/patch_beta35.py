from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

def rep(old, new, label):
    global s
    if old not in s:
        raise SystemExit(f'{label} not found')
    s = s.replace(old, new, 1)

rep('''    row++;\n    uiPrintf(row++, "Previous overrides : %s", g_vminScanRestoreOk ? "\\x1b[32mRESTORED\\x1b[0m" : "\\x1b[31mCHECK HOC\\x1b[0m");\n    row += 2;\n    uiPrintf(row++, "A : Start automatic 1-minute tests");\n    uiPrintf(row++, "B : Exit");\n''', '''    row += 2;\n    uiPrintf(row++, "A : Start automatic stability test");\n    row++;\n    uiPrintf(row++, "If the test crashes, reboot and");\n    uiPrintf(row++, "open the Wizard again.");\n    uiPrintf(row++, "B : Exit");\n''', 'scan success UI')

rep('''        uiPrintf(row++, "Wizard sets each override.");\n        uiPrintf(row++, "Each CPU frequency runs for 1 minute.");\n        row += 2;\n        uiPrintf(row++, "A : Start automatic validation");\n        uiPrintf(row++, "B : Exit");\n''', '''        uiPrintf(row++, "Wizard sets each override.");\n        uiPrintf(row++, "Each CPU frequency runs for 1 minute.");\n        row += 2;\n        uiPrintf(row++, "A : Start automatic stability test");\n        row++;\n        uiPrintf(row++, "If the test crashes, reboot and");\n        uiPrintf(row++, "open the Wizard again.");\n        uiPrintf(row++, "B : Exit");\n''', 'region validation UI')

rep('''                if (g_vminScanSuccess) {\n                    g_vminScanScreen = false;\n                    redraw = true;\n                } else {\n''', '''                if (g_vminScanSuccess) {\n                    g_vminScanScreen = false;\n                    runAutomaticRegionValidation(g_scanForLowUv);\n                    redraw = true;\n                } else {\n''', 'direct stability start')

p.write_text(s)
print('beta35 patch applied')
