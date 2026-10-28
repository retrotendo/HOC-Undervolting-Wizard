from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

def replace_once(old, new, label):
    global s
    if old not in s:
        raise SystemExit(f'{label} block not found')
    s = s.replace(old, new, 1)

replace_once('''void title() {\n    uiPrintf(1, "\\x1b[36mBattery Wizard\\x1b[0m");\n    std::printf("\\x1b[1;70H- : Reset");\n    uiPrintf(2, "Step : %s", compactStepName(g.stage));\n    uiPrintf(3, "----------------------------------------");\n}\n''', '''void title() {\n    uiPrintf(1, "\\x1b[36mBattery Wizard\\x1b[0m");\n    uiPrintf(2, "Step : %s", compactStepName(g.stage));\n    uiPrintf(3, "----------------------------------------");\n}\n\nvoid printResetHint(int lastOptionRow) {\n    // Keep three empty lines between the final action and Reset.\n    uiPrintf(lastOptionRow + 4, "- : Reset");\n}\n''', 'title/reset helper')

replace_once('''void footerTest(int row) {\n    uiPrintf(row,     "Keys:");\n    uiPrintf(row + 1, "A : Start Test");\n    uiPrintf(row + 2, "+ : Known PASS / Skip");\n    uiPrintf(row + 3, "X : Known FAIL / Skip");\n    uiPrintf(row + 4, "B : Exit");\n}\n''', '''void footerTest(int row) {\n    uiPrintf(row,     "Keys:");\n    uiPrintf(row + 1, "A : Start Test");\n    uiPrintf(row + 2, "+ : Known PASS / Skip");\n    uiPrintf(row + 3, "X : Known FAIL / Skip");\n    uiPrintf(row + 4, "B : Exit");\n    printResetHint(row + 4);\n}\n''', 'footerTest')

replace_once('''        uiPrintf(16, "A : Continue to Preparation");\n        uiPrintf(17, "B : Exit");\n        return;\n''', '''        uiPrintf(16, "A : Continue to Preparation");\n        uiPrintf(17, "B : Exit");\n        printResetHint(17);\n        return;\n''', 'hardware detected reset')
replace_once('''    uiPrintf(18, "A : Retry detection");\n    uiPrintf(19, "B : Exit");\n}\n''', '''    uiPrintf(18, "A : Retry detection");\n    uiPrintf(19, "B : Exit");\n    printResetHint(19);\n}\n''', 'hardware failure reset')

replace_once('''    uiPrintf(29, "A : Check settings");\n    uiPrintf(30, "X : Use my current settings as baseline");\n    uiPrintf(31, "Y : Set values automatically + reboot");\n    uiPrintf(32, "B : Exit");\n}\n''', '''    uiPrintf(29, "A : Check settings");\n    uiPrintf(30, "X : Use my current settings as baseline");\n    uiPrintf(31, "Y : Set values automatically + reboot");\n    uiPrintf(32, "B : Exit");\n    printResetHint(32);\n}\n''', 'preparation reset')

replace_once('''        uiPrintf(row++, "+ : Skip to next value");\n        uiPrintf(row++, "B : Exit");\n        return;\n''', '''        uiPrintf(row++, "+ : Known stable / Skip to next value");\n        uiPrintf(row++, "B : Exit");\n        printResetHint(row - 1);\n        return;\n''', 'setting actions')

replace_once('''        uiPrintf(row++, "A : Scan voltage regions automatically");\n        uiPrintf(row++, "B : Exit");\n        return;\n''', '''        uiPrintf(row++, "A : Scan voltage regions automatically");\n        uiPrintf(row++, "B : Exit");\n        printResetHint(row - 1);\n        return;\n''', 'voltage scan intro reset')

replace_once('''        uiPrintf(row++, "A : Start automatic validation");\n        uiPrintf(row++, "B : Exit");\n        return;\n''', '''        uiPrintf(row++, "A : Start automatic validation");\n        uiPrintf(row++, "B : Exit");\n        printResetHint(row - 1);\n        return;\n''', 'region validation reset')

replace_once('''    uiPrintf(16, "A : PASS");\n    uiPrintf(17, "X : FAIL");\n    uiPrintf(18, "B : Exit");\n}\n''', '''    uiPrintf(16, "A : PASS");\n    uiPrintf(17, "X : FAIL");\n    uiPrintf(18, "B : Exit");\n    printResetHint(18);\n}\n''', 'real world reset')

replace_once('''    uiPrintf(17, "B : Exit");\n}\n\nvoid renderInterruptedPrompt()''', '''    uiPrintf(17, "B : Exit");\n    printResetHint(17);\n}\n\nvoid renderInterruptedPrompt()''', 'complete reset')

p.write_text(s)

m = Path('Makefile')
ms = m.read_text()
if 'APP_VERSION := 0.4.0-beta.33' not in ms:
    raise SystemExit('Makefile beta33 version not found')
ms = ms.replace('APP_VERSION := 0.4.0-beta.33', 'APP_VERSION := 0.4.0-beta.34', 1)
m.write_text(ms)

print('beta34 reset layout patch applied')
# trigger
