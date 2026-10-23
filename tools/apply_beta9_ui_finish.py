from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

start = s.index('void renderRealWorld() {')
end = s.index('void renderInterruptedPrompt() {')
block = r'''void renderRealWorld() {
    title();
    uiPrintf(5, "Set in HOC:");
    uiPrintf(6, "Remove all Temporary Overrides");
    uiPrintf(8, "Test:");
    uiPrintf(9, "1 hour Tears of the Kingdom");
    uiPrintf(10, "Fast travel / battles / loading");
    uiPrintf(11, "Home + Sleep/Wake");
    uiPrintf(13, "Keys:");
    uiPrintf(14, "A : PASS");
    uiPrintf(15, "X : FAIL");
    uiPrintf(16, "B : Exit");
}

void renderComplete() {
    title();
    uiPrintf(5, "\x1b[32mUNDERVOLTING COMPLETE\x1b[0m");
    uiPrintf(7, "Final values:");
    uiPrintf(8, "CPU Low UV   : %d", g.lowUvGood);
    uiPrintf(9, "CPU Low VMIN : %d mV", g.lowVminGood);
    uiPrintf(10, "RAM VDDQ     : %d mV", g.vddqGood);
    uiPrintf(11, "RAM VDD2     : %s", formatVdd2(g.vdd2GoodUv).c_str());
    uiPrintf(12, "CPU High UV  : %d", g.highUvGood);
    uiPrintf(14, "Saved to:");
    uiPrintf(15, "/switch/HOC-Undervolting-Wizard/results.txt");
    uiPrintf(17, "B : Exit    - : Reset");
}

'''
s = s[:start] + block + s[end:]
p.write_text(s)
