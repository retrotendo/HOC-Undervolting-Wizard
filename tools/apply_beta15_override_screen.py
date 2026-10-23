from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()
old = r'''void renderOverridePrompt() {
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
new = r'''void renderOverridePrompt() {
    consoleClear();
    uiPrintf(1, "\x1b[31mBattery Wizard - TEST BLOCKED\x1b[0m");
    uiPrintf(2, "Step : %s", compactStepName(g.stage));
    uiPrintf(3, "----------------------------------------");

    if (!g_overrideCheck.readOk) {
        uiPrintf(5, "Could not read Horizon OC hoc:clk");
        uiPrintf(6, "Result : 0x%08X", g_overrideCheck.rc);
        uiPrintf(8, "Boot CFW with Horizon OC / hoc.kip");
        uiPrintf(11, "A : Check again");
        uiPrintf(12, "B : Back");
    } else {
        const char* ok = "\x1b[32mOK\x1b[0m";
        const char* bad = "\x1b[31mWRONG\x1b[0m";
        uiPrintf(5, "Set these overrides in Horizon OC:");

        uiPrintf(7, "CPU");
        uiPrintf(8, "  Required : %s", formatClock(g_overrideCheck.expected.cpuHz).c_str());
        uiPrintf(9, "  Current  : %s", formatClock(g_overrideCheck.current.overrideHz[0]).c_str());
        uiPrintf(10, "  Status   : %s", g_overrideCheck.cpuOk ? ok : bad);

        uiPrintf(12, "GPU");
        uiPrintf(13, "  Required : %s", formatClock(g_overrideCheck.expected.gpuHz).c_str());
        uiPrintf(14, "  Current  : %s", formatClock(g_overrideCheck.current.overrideHz[1]).c_str());
        uiPrintf(15, "  Status   : %s", g_overrideCheck.gpuOk ? ok : bad);

        uiPrintf(17, "RAM");
        uiPrintf(18, "  Required : %s", formatClock(g_overrideCheck.expected.ramHz).c_str());
        uiPrintf(19, "  Current  : %s", formatClock(g_overrideCheck.current.overrideHz[2]).c_str());
        uiPrintf(20, "  Status   : %s", g_overrideCheck.ramOk ? ok : bad);

        int row = 22;
        if (g_overrideAction == PendingOverrideAction::VminProbe) {
            uiPrintf(row++, "CPU applied clock");
            uiPrintf(row++, "  Required : %s", formatClock(g_overrideCheck.expected.cpuHz).c_str());
            uiPrintf(row++, "  Current  : %s", formatClock(g_overrideCheck.current.targetHz[0]).c_str());
            uiPrintf(row++, "  Status   : %s", g_overrideCheck.cpuAppliedOk ? ok : bad);
            row++;
        }

        uiPrintf(row++, "Fix all \x1b[31mWRONG\x1b[0m values, then check again.");
        row++;
        uiPrintf(row++, "A : Check again");
        uiPrintf(row++, "B : Back");
    }
    consoleUpdate(nullptr);
}
'''
if old not in s:
    raise SystemExit('renderOverridePrompt block not found')
s = s.replace(old, new, 1)
p.write_text(s)

p = Path('Makefile')
s = p.read_text().replace('APP_VERSION := 0.4.0-beta.14', 'APP_VERSION := 0.4.0-beta.15')
p.write_text(s)

Path('UPDATE.txt').write_text('''version=0.4.0-beta.15\nnro_url=https://github.com/retrotendo/HOC-Undervolting-Wizard/releases/download/v0.4.0-beta.15/HOC-Undervolting-Wizard.nro\nsha_url=https://github.com/retrotendo/HOC-Undervolting-Wizard/releases/download/v0.4.0-beta.15/HOC-Undervolting-Wizard.nro.sha256\n''')

p = Path('README.md')
s = p.read_text()
marker = '# New in v0.4.0-beta.14\n'
section = '''# New in v0.4.0-beta.15\n\n- Redesign the TEST BLOCKED override screen for readability.\n- Show each CPU/GPU/RAM override vertically with **Required**, live **Current**, and color-coded **OK / WRONG** status.\n- `Current` uses the actual Horizon OC override value; unset overrides show `NOT SET`.\n- VMIN floor checks additionally show the applied CPU clock as its own Required/Current/Status block.\n- No override detection, tuning, reboot, stress-test, VMIN or updater logic changes.\n\n---\n\n'''
if marker not in s:
    raise SystemExit('README beta14 marker not found')
s = s.replace(marker, section + marker, 1)
p.write_text(s)

p = Path('CHANGELOG.md')
s = p.read_text()
p.write_text('''## v0.4.0-beta.15\n- Redesign TEST BLOCKED override screen into vertical Required / Current / Status blocks.\n- Show actual Horizon OC override values for CPU/GPU/RAM.\n- Color WRONG red and OK green.\n- Keep applied CPU clock visible during VMIN floor checks.\n- No tuning or test logic changes.\n\n''' + s)
