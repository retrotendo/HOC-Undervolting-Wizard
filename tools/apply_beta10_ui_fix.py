from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

s = s.replace('constexpr int UI_COL = 82;', 'constexpr int UI_COL = 36;', 1)
s = s.replace('uiPrintf(3, "----------------------------------------------");', 'uiPrintf(3, "----------------------------------------");')

start = s.index('void renderOverridePrompt() {')
end = s.index('void renderResultScreen() {')
block = r'''void renderOverridePrompt() {
    consoleClear();
    uiPrintf(1, "\x1b[31mBattery Wizard - TEST BLOCKED\x1b[0m");
    uiPrintf(2, "Step : %s", compactStepName(g.stage));
    uiPrintf(3, "----------------------------------------");

    if (!g_overrideCheck.readOk) {
        uiPrintf(5, "Could not read Horizon OC hoc:clk");
        uiPrintf(6, "Result : 0x%08X", g_overrideCheck.rc);
        uiPrintf(8, "Boot CFW with Horizon OC / hoc.kip");
    } else {
        const char* ok = "OK";
        const char* bad = "WRONG";
        uiPrintf(5, "Overrides - Expected / Current");
        uiPrintf(7, "CPU : %s / %s  %s",
                 formatClock(g_overrideCheck.expected.cpuHz).c_str(),
                 formatClock(g_overrideCheck.current.overrideHz[0]).c_str(),
                 g_overrideCheck.cpuOk ? ok : bad);
        uiPrintf(8, "GPU : %s / %s  %s",
                 formatClock(g_overrideCheck.expected.gpuHz).c_str(),
                 formatClock(g_overrideCheck.current.overrideHz[1]).c_str(),
                 g_overrideCheck.gpuOk ? ok : bad);
        uiPrintf(9, "RAM : %s / %s  %s",
                 formatClock(g_overrideCheck.expected.ramHz).c_str(),
                 formatClock(g_overrideCheck.current.overrideHz[2]).c_str(),
                 g_overrideCheck.ramOk ? ok : bad);
        if (g_overrideAction == PendingOverrideAction::VminProbe) {
            uiPrintf(10, "Applied CPU : %s  %s",
                     formatClock(g_overrideCheck.current.targetHz[0]).c_str(),
                     g_overrideCheck.cpuAppliedOk ? ok : bad);
        }
        uiPrintf(12, "Correct every WRONG value in Horizon OC");
    }

    uiPrintf(15, "A : Check again / Continue");
    uiPrintf(16, "B : Back");
    consoleUpdate(nullptr);
}

'''
s = s[:start] + block + s[end:]
p.write_text(s)

p = Path('Makefile')
s = p.read_text().replace('APP_VERSION := 0.4.0-beta.9', 'APP_VERSION := 0.4.0-beta.10')
p.write_text(s)

p = Path('CHANGELOG.md')
s = p.read_text()
marker = '# Changelog\n\n'
entry = '''## v0.4.0-beta.10\n\n- Fix the beta.9 right-side UI start column after real-hardware validation.\n- Move the compact Wizard panel from console column 82 to column 36 so it sits immediately to the right of Ultrahand.\n- Shorten the divider and override-error table to prevent wrapping at the right edge.\n- No tuning, test, updater, VMIN, reboot or recovery logic changes.\n\n'''
if '## v0.4.0-beta.10' not in s:
    s = s.replace(marker, marker + entry, 1)
p.write_text(s)

p = Path('README.md')
s = p.read_text()
marker = '# New in v0.4.0-beta.9\n'
entry = '''# New in v0.4.0-beta.10\n\n- Correct the Ultrahand-friendly panel position based on real Switch OLED testing.\n- The right-side panel now starts at console column 36 instead of 82.\n- Shorter fixed-width lines avoid wrapping at the screen edge.\n- beta.9/beta.8 tuning behavior remains unchanged.\n\n---\n\n'''
if 'v0.4.0-beta.10' not in s:
    s = s.replace(marker, entry + marker, 1)
p.write_text(s)
