from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

if '#include <cstdarg>' not in s:
    s = s.replace('#include <algorithm>\n', '#include <algorithm>\n#include <cstdarg>\n', 1)

start = s.index('void title() {')
end = s.index('void renderRealWorld() {')

block = r'''constexpr int UI_COL = 82;

void uiPrintf(int row, const char* fmt, ...) {
    std::printf("\x1b[%d;%dH", row, UI_COL);
    va_list args;
    va_start(args, fmt);
    std::vprintf(fmt, args);
    va_end(args);
}

const char* compactStepName(Stage s) {
    switch (s) {
        case Stage::Preparation: return "Preparation";
        case Stage::LowUvQuick: return "CPU Low UV";
        case Stage::LowUvLong: return "CPU Low UV - Validate";
        case Stage::LowVminQuick: return "CPU Low VMIN";
        case Stage::LowVminLong: return "CPU Low VMIN - Clock Check";
        case Stage::LowVminSweep612: return "CPU Low VMIN - Clock Check";
        case Stage::LowVminSweep714: return "CPU Low VMIN - Clock Check";
        case Stage::LowVminValidate816: return "CPU Low VMIN - Clock Check";
        case Stage::LowVminSweep918: return "CPU Low VMIN - Clock Check";
        case Stage::LowVminValidate1020: return "CPU Low VMIN - Clock Check";
        case Stage::LowVminFinalLong: return "CPU Low VMIN - Validate";
        case Stage::VddqQuick: return "RAM VDDQ";
        case Stage::VddqLong: return "RAM VDDQ - Validate";
        case Stage::Vdd2Quick: return "RAM VDD2";
        case Stage::Vdd2Long: return "RAM VDD2 - Validate";
        case Stage::RamBoostValidate: return "RAM Rails - Boost";
        case Stage::Ram1331Validate: return "RAM Rails - Handheld";
        case Stage::HighUvQuick: return "CPU High UV";
        case Stage::HighUvLong: return "CPU High UV - Validate";
        case Stage::BoostCpuRamValidate: return "Boost CPU + RAM";
        case Stage::NormalMatrixValidate: return "Final Handheld - CPU";
        case Stage::NormalMemValidate: return "Final Handheld - RAM";
        case Stage::NormalGpuValidate: return "Final Handheld - GPU";
        case Stage::BoostMatrixValidate: return "Final Boost - CPU";
        case Stage::BoostMemValidate: return "Final Boost - RAM";
        case Stage::BoostCpuMemValidate: return "Final Boost - CPU + RAM";
        case Stage::RealWorldValidate: return "Real World";
        case Stage::Complete: return "Complete";
    }
    return "Unknown";
}

void title() {
    uiPrintf(1, "\x1b[36mBattery Wizard\x1b[0m");
    uiPrintf(2, "Step : %s", compactStepName(g.stage));
    uiPrintf(3, "----------------------------------------------");
}

void printSafeRecovery(const std::string& restoreText) {
    uiPrintf(5, "\x1b[33mPrevious setting did not boot\x1b[0m");
    uiPrintf(7, "Recovery:");
    uiPrintf(8, "1. Boot Hekate without hoc.kip");
    uiPrintf(9, "2. Open Horizon OC");
    uiPrintf(10, "3. Restore : %s", restoreText.c_str());
    uiPrintf(11, "4. Save KIP + Reboot");
}

const char* compactTestName(stress::Kind kind) {
    switch (kind) {
        case stress::Kind::Cpu: return "Matrix + Hanoi";
        case stress::Kind::Ram: return "RAM memtester";
        case stress::Kind::Combined: return "CPU + RAM";
        case stress::Kind::Gpu: return "GPU compute/memory";
    }
    return "Built-in test";
}

void printOverrides(int row, const OverrideExpectation& e) {
    uiPrintf(row,     "Overrides:");
    uiPrintf(row + 1, "CPU : %s", formatClock(e.cpuHz).c_str());
    uiPrintf(row + 2, "GPU : %s", formatClock(e.gpuHz).c_str());
    uiPrintf(row + 3, "RAM : %s", formatClock(e.ramHz).c_str());
}

void footerTest(int row) {
    uiPrintf(row,     "Keys:");
    uiPrintf(row + 1, "A : Start Test");
    uiPrintf(row + 2, "+ : Known PASS / Skip");
    uiPrintf(row + 3, "X : Known FAIL / Skip");
    if (isQuickStage(g.stage)) uiPrintf(row + 4, "Y : Did Not Boot");
    uiPrintf(row + 5, "B : Exit    - : Reset");
}

void renderPreparation() {
    title();
    uiPrintf(5, "Set in Horizon OC:");
    uiPrintf(6, "Uncapped Clocks : OFF");
    uiPrintf(7, "HP Mode         : OFF");
    uiPrintf(8, "RAM Max         : 1600 MHz");
    uiPrintf(9, "VDD2            : 1175 mV");
    uiPrintf(10, "VDDQ            : 600 mV");
    uiPrintf(11, "CPU Max         : Lowest selectable (1963)");
    uiPrintf(12, "CPU UV Table    : 1683 MHz Tbreak");
    uiPrintf(13, "Low / High UV   : 0 / 0");
    uiPrintf(14, "Low VMIN        : 620 mV");
    uiPrintf(15, "High VMIN       : 750 mV");
    uiPrintf(17, "HOC Toolkit:");
    uiPrintf(18, "CPU Boost       : Lowest selectable / 1785");
    uiPrintf(20, "Then:");
    uiPrintf(21, "Save Toolkit + Save KIP + Reboot CFW");
    uiPrintf(22, "Reopen Wizard after reboot");
    uiPrintf(24, "Keys:");
    uiPrintf(25, "A : Setup done / Start");
    uiPrintf(26, "B : Exit    - : Reset");
}

bool isVminSweepStage(Stage st);

void renderTestStage() {
    title();

    stress::Kind kind;
    int seconds = 0;
    const bool hasTest = testPlan(g.stage, kind, seconds);
    OverrideExpectation expected{};
    const bool hasOverrides = overridePlan(g.stage, expected);

    int row = 5;
    uiPrintf(row++, "Set in HOC:");

    switch (g.stage) {
        case Stage::LowUvQuick:
            uiPrintf(row++, "Low UV : %d", g.lowUvTest);
            uiPrintf(row++, "Action : Save KIP + Reboot");
            break;
        case Stage::LowUvLong:
            if (g.recoveryNeeded) { printSafeRecovery("CPU Low UV = " + std::to_string(g.lowUvGood)); row = 13; }
            else {
                uiPrintf(row++, "Low UV : %d", g.lowUvGood);
                uiPrintf(row++, "Action : Save KIP + Reboot");
            }
            break;
        case Stage::LowVminQuick:
            uiPrintf(row++, "Low UV   : %d", g.lowUvGood);
            uiPrintf(row++, "Low VMIN : %d mV", g.lowVminTest);
            uiPrintf(row++, "Action   : Save KIP + Reboot");
            break;
        case Stage::LowVminLong:
        case Stage::LowVminSweep612:
        case Stage::LowVminSweep714:
        case Stage::LowVminValidate816:
        case Stage::LowVminSweep918:
        case Stage::LowVminValidate1020:
            uiPrintf(row++, "Low VMIN : %d mV", g.lowVminGood);
            uiPrintf(row++, "Action   : Set Overrides below");
            break;
        case Stage::LowVminFinalLong:
            uiPrintf(row++, "Low VMIN : %d mV", g.lowVminGood);
            uiPrintf(row++, "Floor CPU: %s", formatClock(g.vminFloorHz ? g.vminFloorHz : CLOCK_CPU_VMIN_510_HZ).c_str());
            break;
        case Stage::VddqQuick:
            uiPrintf(row++, "VDD2 : %s", formatVdd2(STOCK_VDD2_UV).c_str());
            uiPrintf(row++, "VDDQ : %d mV", g.vddqTest);
            uiPrintf(row++, "Action: Save KIP + Reboot");
            break;
        case Stage::VddqLong:
            if (g.recoveryNeeded) { printSafeRecovery("RAM VDDQ = " + std::to_string(g.vddqGood) + " mV"); row = 13; }
            else {
                uiPrintf(row++, "VDDQ : %d mV", g.vddqGood);
                uiPrintf(row++, "Action: Save KIP + Reboot");
            }
            break;
        case Stage::Vdd2Quick:
            uiPrintf(row++, "VDDQ : %d mV", g.vddqGood);
            uiPrintf(row++, "VDD2 : %s", formatVdd2(g.vdd2TestUv).c_str());
            uiPrintf(row++, "Action: Save KIP + Reboot");
            break;
        case Stage::Vdd2Long:
            if (g.recoveryNeeded) { printSafeRecovery("RAM VDD2 = " + formatVdd2(g.vdd2GoodUv)); row = 13; }
            else {
                uiPrintf(row++, "VDDQ : %d mV", g.vddqGood);
                uiPrintf(row++, "VDD2 : %s", formatVdd2(g.vdd2GoodUv).c_str());
                uiPrintf(row++, "Action: Save KIP + Reboot");
            }
            break;
        case Stage::RamBoostValidate:
            uiPrintf(row++, "VDDQ : %d mV", g.vddqGood);
            uiPrintf(row++, "VDD2 : %s", formatVdd2(g.vdd2GoodUv).c_str());
            if (g.ramPairRetryMode == 1) uiPrintf(row++, "Retry: VDDQ +10 mV");
            if (g.ramPairRetryMode == 2) uiPrintf(row++, "Retry: VDD2 +12.5 mV");
            break;
        case Stage::Ram1331Validate:
            uiPrintf(row++, "VDDQ : %d mV", g.vddqGood);
            uiPrintf(row++, "VDD2 : %s", formatVdd2(g.vdd2GoodUv).c_str());
            break;
        case Stage::HighUvQuick:
            uiPrintf(row++, "High UV : %d", g.highUvTest);
            uiPrintf(row++, "Action  : Save KIP + Reboot");
            break;
        case Stage::HighUvLong:
            if (g.recoveryNeeded) { printSafeRecovery("CPU High UV = " + std::to_string(g.highUvGood)); row = 13; }
            else {
                uiPrintf(row++, "High UV : %d", g.highUvGood);
                uiPrintf(row++, "Action  : Save KIP + Reboot");
            }
            break;
        case Stage::BoostCpuRamValidate:
            uiPrintf(row++, "Low UV  : %d", g.lowUvGood);
            uiPrintf(row++, "High UV : %d", g.highUvGood);
            uiPrintf(row++, "VMIN    : %d mV", g.lowVminGood);
            break;
        case Stage::NormalMatrixValidate:
        case Stage::NormalMemValidate:
        case Stage::NormalGpuValidate:
        case Stage::BoostMatrixValidate:
        case Stage::BoostMemValidate:
        case Stage::BoostCpuMemValidate:
            uiPrintf(row++, "Use final validated values");
            break;
        default:
            break;
    }

    row++;
    if (hasOverrides) {
        printOverrides(row, expected);
        row += 5;
    }

    if (isVminSweepStage(g.stage)) {
        uiPrintf(row++, "Next:");
        uiPrintf(row++, "A : Continue");
        uiPrintf(row++, "    (CPU voltage checked automatically)");
        uiPrintf(row++, "B : Exit");
        return;
    }

    if (hasTest) {
        uiPrintf(row++, "Test:");
        uiPrintf(row++, "%s - %s", seconds == 60 ? "1 min" : "1 hour", compactTestName(kind));
        footerTest(row + 1);
    }
}

'''

s = s[:start] + block + s[end:]

# Reformat override-block screen into the same right-side table so it stays
# visible while Ultrahand/Horizon OC occupies the left side.
start = s.index('void renderOverridePrompt() {')
end = s.index('void renderResultScreen() {')
block = r'''void renderOverridePrompt() {
    consoleClear();
    uiPrintf(1, "\x1b[31mBattery Wizard - TEST BLOCKED\x1b[0m");
    uiPrintf(2, "Step : %s", compactStepName(g.stage));
    uiPrintf(3, "----------------------------------------------");

    if (!g_overrideCheck.readOk) {
        uiPrintf(5, "Could not read Horizon OC hoc:clk");
        uiPrintf(6, "Result : 0x%08X", g_overrideCheck.rc);
        uiPrintf(8, "Boot CFW with Horizon OC / hoc.kip");
    } else {
        const char* ok = "OK";
        const char* bad = "WRONG";
        uiPrintf(5, "Overrides        Expected       Current        Status");
        uiPrintf(6, "CPU              %-13s %-13s %s",
                 formatClock(g_overrideCheck.expected.cpuHz).c_str(),
                 formatClock(g_overrideCheck.current.overrideHz[0]).c_str(),
                 g_overrideCheck.cpuOk ? ok : bad);
        uiPrintf(7, "GPU              %-13s %-13s %s",
                 formatClock(g_overrideCheck.expected.gpuHz).c_str(),
                 formatClock(g_overrideCheck.current.overrideHz[1]).c_str(),
                 g_overrideCheck.gpuOk ? ok : bad);
        uiPrintf(8, "RAM              %-13s %-13s %s",
                 formatClock(g_overrideCheck.expected.ramHz).c_str(),
                 formatClock(g_overrideCheck.current.overrideHz[2]).c_str(),
                 g_overrideCheck.ramOk ? ok : bad);
        if (g_overrideAction == PendingOverrideAction::VminProbe) {
            uiPrintf(9, "CPU applied      %-13s %-13s %s",
                     formatClock(g_overrideCheck.expected.cpuHz).c_str(),
                     formatClock(g_overrideCheck.current.targetHz[0]).c_str(),
                     g_overrideCheck.cpuAppliedOk ? ok : bad);
        }
        uiPrintf(11, "Correct every WRONG value in Horizon OC");
    }

    uiPrintf(14, "A : Check again / Continue");
    uiPrintf(15, "B : Back");
    consoleUpdate(nullptr);
}

'''
s = s[:start] + block + s[end:]

p.write_text(s)

# Version bump.
p = Path('Makefile')
s = p.read_text().replace('APP_VERSION := 0.4.0-beta.8', 'APP_VERSION := 0.4.0-beta.9')
p.write_text(s)

# README / changelog UI note.
p = Path('README.md')
s = p.read_text()
marker = '# New in v0.4.0-beta.8\n'
entry = '''# New in v0.4.0-beta.9\n\n## Ultrahand-friendly right-side layout\n\n- Reworked Wizard stage screens into a compact table-style layout.\n- All values that must be entered in Horizon OC and all Temporary Override targets are displayed on the right side of the screen so they remain readable while Ultrahand/Horizon OC is open on the left.\n- The tuning workflow, reboot points, test logic, dynamic Low VMIN detection, recovery behavior and KNOWN PASS/FAIL shortcuts are unchanged from beta.8.\n- `Save KIP + Reboot` is shown only on stages where the persistent HOC value has actually changed.\n- Dynamic Low VMIN voltage probing remains internal; the UI simply tells the user which Overrides to set and when to continue.\n\n---\n\n'''
if '# New in v0.4.0-beta.9' not in s and marker in s:
    s = s.replace(marker, entry + marker, 1)
p.write_text(s)

p = Path('CHANGELOG.md')
s = p.read_text()
marker = '# Changelog\n\n'
entry = '''## v0.4.0-beta.9\n\n- Redesign tuning-stage UI into a compact right-side table layout for use alongside the Ultrahand/Horizon OC overlay.\n- Keep Set in HOC values, Temporary Overrides, test type/duration and controls visible on the right half of the screen.\n- Preserve beta.8 tuning/test/reboot/skip logic unchanged.\n- Hide dynamic VMIN probe implementation details from the normal workflow while retaining the same automatic voltage measurement.\n- Show Save KIP + Reboot only when a persistent HOC setting was changed.\n\n'''
if '## v0.4.0-beta.9' not in s:
    s = s.replace(marker, marker + entry, 1)
p.write_text(s)
