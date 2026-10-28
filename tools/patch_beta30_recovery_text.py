from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()
old = '''    } else if (state == BootInference::SaferActive) {
        uiPrintf(row++, "\\x1b[33mA safer previous value is active.\\x1b[0m");
        uiPrintf(row++, "The attempted value did not remain active.");
        uiPrintf(row++, "That makes the active previous value the candidate.");
        row += 2;
        uiPrintf(row++, "A : Continue with this candidate");
    } else {
'''
new = '''    } else if (state == BootInference::SaferActive) {
        uiPrintf(row++, "\\x1b[33mRequested value is NOT active.\\x1b[0m");
        uiPrintf(row++, "It looks like the console did not boot");
        uiPrintf(row++, "successfully with the requested value and");
        uiPrintf(row++, "was recovered to the previous working value.");
        row++;
        if (g.stage == Stage::LowUvQuick)
            uiPrintf(row++, "\\x1b[32mLast good value: Low UV %d\\x1b[0m", active);
        else if (g.stage == Stage::LowVminQuick)
            uiPrintf(row++, "\\x1b[32mLast good value: Low VMIN %d mV\\x1b[0m", active);
        row++;
        uiPrintf(row++, "Confirm only if this matches your recovery.");
        uiPrintf(row++, "A : Confirm last good value");
        uiPrintf(row++, "X : This is not correct");
    } else {
'''
if old not in s:
    raise SystemExit('target block not found')
p.write_text(s.replace(old, new, 1))
print('recovery text patched')
