from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

def replace_once(old, new, label):
    global s
    if old not in s:
        raise SystemExit(f'{label} block not found')
    s = s.replace(old, new, 1)

replace_once('''    if (m & (Config_Prepare | Config_LowUv | Config_LowVmin))\n        uiPrintf(row + 4, "Y : Set required value(s) automatically");\n''', '''    if (m & Config_Prepare)\n        uiPrintf(row + 4, "Y : Set required values automatically");\n    else if (m & (Config_LowUv | Config_LowVmin))\n        uiPrintf(row + 4, "Y : Set required value automatically");\n''', 'config prompt singular/plural')

replace_once('''    uiPrintf(16, "A : Confirm - set value(s)");\n''', '''    if (g_autoSetMask & Config_Prepare)\n        uiPrintf(16, "A : Confirm - set values");\n    else\n        uiPrintf(16, "A : Confirm - set value");\n''', 'auto confirm singular/plural')

p.write_text(s)
print('beta34 singular/plural copy patch applied')
