from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

old = '''void renderRealWorld() {
    title();
    if (!g_realWorldHelpPage) {
        uiPrintf(5, "Recommendation: Tears of the Kingdom");
        uiPrintf(7, "Play for at least 1 hour.");
        uiPrintf(9, "Use:");
        uiPrintf(10, "• Normal gameplay");
        uiPrintf(11, "• Fast travel / battles");
        uiPrintf(12, "• Loading screens");
        uiPrintf(13, "• Sleep / Wake");
        uiPrintf(15, "Watch for crash, freeze or reboot.");
        uiPrintf(19, "A : If instability occurs");
        uiPrintf(20, "+ : Stable / Continue to results");
        uiPrintf(21, "B : Exit");
        printResetHint(21);
        return;
    }

    uiPrintf(5, "Change only ONE setting at a time.");
    uiPrintf(6, "Change one step, then play again.");
    uiPrintf(8, "Recommended order:");
    uiPrintf(10, "1. Low VMIN - raise one step");
    uiPrintf(11, "2. VDDQ - raise one step");
    uiPrintf(12, "3. VDD2 - raise one step");
    uiPrintf(13, "4. CPU High UV - one step less aggressive");
    uiPrintf(14, "5. CPU Low UV - one step less aggressive");
    uiPrintf(16, "Still unstable? Restore the previous value.");
    uiPrintf(17, "Then try the next setting.");
    uiPrintf(20, "A : Continue to results");
    uiPrintf(21, "B : Back");
    printResetHint(21);
}
'''

new = '''void renderRealWorld() {
    title();
    if (!g_realWorldHelpPage) {
        uiPrintf(5, "Recommendation");
        uiPrintf(7, "Tears of the Kingdom");
        uiPrintf(9, "Play for at least 1 hour");
        uiPrintf(11, "Normal gameplay");
        uiPrintf(12, "Fast travel / battles");
        uiPrintf(13, "Loading screens");
        uiPrintf(14, "Sleep / Wake");
        uiPrintf(16, "Watch for crash, freeze or reboot");
        uiPrintf(19, "A : Instability occurred");
        uiPrintf(20, "+ : Stable / Continue");
        uiPrintf(21, "B : Exit");
        printResetHint(21);
        return;
    }

    uiPrintf(5, "Change only ONE setting at a time");
    uiPrintf(6, "Change one step, then play again");
    uiPrintf(8, "Recommended order");
    uiPrintf(10, "1. Low VMIN");
    uiPrintf(11, "2. VDDQ");
    uiPrintf(12, "3. VDD2");
    uiPrintf(13, "4. CPU High UV");
    uiPrintf(14, "5. CPU Low UV");
    uiPrintf(16, "VMIN / VDDQ / VDD2  raise one step");
    uiPrintf(17, "High UV / Low UV  one step less aggressive");
    uiPrintf(18, "Still unstable? Restore the previous value");
    uiPrintf(19, "Then try the next setting");
    uiPrintf(21, "A : Continue to results");
    uiPrintf(22, "B : Back");
    printResetHint(22);
}
'''

if old not in s:
    raise SystemExit('renderRealWorld block not found')
s = s.replace(old, new, 1)
p.write_text(s)

make = Path('Makefile')
m = make.read_text()
if 'APP_VERSION := 0.4.0-beta.54' not in m:
    raise SystemExit('beta54 version not found')
make.write_text(m.replace('APP_VERSION := 0.4.0-beta.54', 'APP_VERSION := 0.4.0-beta.55', 1))

readme = Path('README.md')
r = readme.read_text().replace('v0.4.0-beta.54', 'v0.4.0-beta.55')
readme.write_text(r)

print('beta55 readability patch applied')
