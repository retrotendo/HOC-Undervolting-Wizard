from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()


def rep(old, new, count=1):
    global s
    if s.count(old) < count:
        raise SystemExit(f'marker missing: {old[:120]!r}')
    s = s.replace(old, new, count)


def replace_function(signature, replacement):
    global s
    start = s.find(signature)
    if start < 0:
        raise SystemExit(f'function not found: {signature}')
    brace = s.find('{', start)
    if brace < 0:
        raise SystemExit(f'opening brace missing: {signature}')
    depth = 0
    i = brace
    in_str = False
    esc = False
    line_comment = False
    block_comment = False
    while i < len(s):
        c = s[i]
        n = s[i+1] if i + 1 < len(s) else ''
        if line_comment:
            if c == '\n': line_comment = False
        elif block_comment:
            if c == '*' and n == '/':
                block_comment = False
                i += 1
        elif in_str:
            if esc: esc = False
            elif c == '\\': esc = True
            elif c == '"': in_str = False
        else:
            if c == '/' and n == '/':
                line_comment = True
                i += 1
            elif c == '/' and n == '*':
                block_comment = True
                i += 1
            elif c == '"': in_str = True
            elif c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    s = s[:start] + replacement.rstrip() + '\n' + s[end:]
                    return
        i += 1
    raise SystemExit(f'unclosed function: {signature}')


# Runtime-only automatic scan result screen.
rep('''Result g_hardwareReadRc = 0;\nHocMonHardware g_hardware{};\n''', '''Result g_hardwareReadRc = 0;\nHocMonHardware g_hardware{};\n\nbool g_vminScanScreen = false;\nbool g_vminScanSuccess = false;\nbool g_vminScanRestoreOk = true;\nResult g_vminScanErrorRc = 0;\nstd::string g_vminScanErrorText;\n''')

# Give the voltage sampler awareness of the full automatic sweep.
replace_function('bool sampleVminVoltage(Stage s)', r'''bool sampleVminVoltage(Stage s, int sweepIndex = -1, int sweepTotal = 0) {
    if (!checkAllOverrides(s)) return false;

    u32 samples[3] = {};
    int count = 0;
    HocMonClocks latest = g_overrideCheck.current;

    for (int i = 0; i < 3; ++i) {
        consoleClear();
        std::printf("\x1b[1;%dH\x1b[36mBattery Wizard\x1b[0m", UI_COL);
        std::printf("\x1b[2;%dHStep : CPU Low VMIN - AUTO SCAN", UI_COL);
        std::printf("\x1b[3;%dH----------------------------------------", UI_COL);
        if (sweepIndex >= 0 && sweepTotal > 0)
            std::printf("\x1b[5;%dHFrequency : %d / %d", UI_COL, sweepIndex + 1, sweepTotal);
        std::printf("\x1b[7;%dHCPU       : %s", UI_COL, formatClock(g_overrideCheck.expected.cpuHz).c_str());
        std::printf("\x1b[8;%dHGPU / RAM : 384 / 1331.2 MHz", UI_COL);
        std::printf("\x1b[10;%dHReading CPU voltage...", UI_COL);
        char bar[13] = "............";
        for (int j = 0; j < i * 4; ++j) bar[j] = '#';
        std::printf("\x1b[12;%dH[%s] %d/3", UI_COL, bar, i);
        consoleUpdate(nullptr);
        svcSleepThread(900'000'000);

        HocMonClocks cur{};
        Result rc = hocmonGetClocks(&cur);
        if (R_SUCCEEDED(rc) &&
            clockMatches(cur.overrideHz[0], g_overrideCheck.expected.cpuHz) &&
            clockMatches(cur.overrideHz[1], g_overrideCheck.expected.gpuHz) &&
            clockMatches(cur.overrideHz[2], g_overrideCheck.expected.ramHz) &&
            clockMatches(cur.targetHz[0], g_overrideCheck.expected.cpuHz) &&
            cur.cpuVoltageUv != 0) {
            samples[count++] = cur.cpuVoltageUv;
            latest = cur;
        }

        consoleClear();
        std::printf("\x1b[1;%dH\x1b[36mBattery Wizard\x1b[0m", UI_COL);
        std::printf("\x1b[2;%dHStep : CPU Low VMIN - AUTO SCAN", UI_COL);
        std::printf("\x1b[3;%dH----------------------------------------", UI_COL);
        if (sweepIndex >= 0 && sweepTotal > 0)
            std::printf("\x1b[5;%dHFrequency : %d / %d", UI_COL, sweepIndex + 1, sweepTotal);
        std::printf("\x1b[7;%dHCPU       : %s", UI_COL, formatClock(g_overrideCheck.expected.cpuHz).c_str());
        std::printf("\x1b[8;%dHGPU / RAM : 384 / 1331.2 MHz", UI_COL);
        std::printf("\x1b[10;%dHReading CPU voltage...", UI_COL);
        char done[13] = "............";
        for (int j = 0; j < (i + 1) * 4; ++j) done[j] = '#';
        std::printf("\x1b[12;%dH[%s] %d/3", UI_COL, done, i + 1);
        consoleUpdate(nullptr);
    }

    if (count < 3) {
        g_overrideCheck.current = latest;
        g_overrideCheck.readOk = true;
        g_overrideCheck.cpuOk = clockMatches(latest.overrideHz[0], g_overrideCheck.expected.cpuHz);
        g_overrideCheck.gpuOk = clockMatches(latest.overrideHz[1], g_overrideCheck.expected.gpuHz);
        g_overrideCheck.ramOk = clockMatches(latest.overrideHz[2], g_overrideCheck.expected.ramHz);
        g_overrideCheck.cpuAppliedOk = clockMatches(latest.targetHz[0], g_overrideCheck.expected.cpuHz);
        g_overrideCheck.voltageSamplesOk = false;
        return false;
    }

    if (samples[0] > samples[1]) std::swap(samples[0], samples[1]);
    if (samples[1] > samples[2]) std::swap(samples[1], samples[2]);
    if (samples[0] > samples[1]) std::swap(samples[0], samples[1]);
    latest.cpuVoltageUv = samples[1];
    g_overrideCheck.current = latest;
    g_overrideCheck.readOk = true;
    g_overrideCheck.cpuOk = g_overrideCheck.gpuOk = g_overrideCheck.ramOk = true;
    g_overrideCheck.cpuAppliedOk = true;
    g_overrideCheck.voltageSamplesOk = true;
    return true;
}''')

# Automatic scan helpers are placed immediately before the UI rendering section.
marker = 'void renderHardwareDetection() {'
idx = s.find(marker)
if idx < 0:
    raise SystemExit('renderHardwareDetection marker missing')
helpers = r'''
bool restoreTemporaryOverrides(const HocMonClocks& before) {
    bool ok = true;
    // Restore GPU/RAM first, CPU last so a previous high CPU override is not
    // reintroduced while the scan's RAM/GPU clocks are still active.
    const u32 modules[3] = {HocMonModule_GPU, HocMonModule_MEM, HocMonModule_CPU};
    for (u32 module : modules) {
        Result rc = hocmonSetOverride(module, before.overrideHz[module]);
        if (R_FAILED(rc)) ok = false;
    }
    svcSleepThread(300'000'000);
    return ok;
}

void renderVminScanScreen() {
    consoleClear();
    uiPrintf(1, "\x1b[36mBattery Wizard - AUTO VMIN SCAN\x1b[0m");
    uiPrintf(3, "----------------------------------------");

    if (!g_vminScanSuccess) {
        uiPrintf(5, "\x1b[31mAutomatic scan stopped\x1b[0m");
        if (!g_vminScanErrorText.empty()) uiPrintf(7, "%s", g_vminScanErrorText.c_str());
        if (g_vminScanErrorRc) uiPrintf(8, "Result : 0x%08X", g_vminScanErrorRc);
        uiPrintf(10, "Previous overrides : %s", g_vminScanRestoreOk ? "\x1b[32mRESTORED\x1b[0m" : "\x1b[31mCHECK HOC\x1b[0m");
        uiPrintf(13, "A : Retry full scan");
        uiPrintf(14, "B : Back");
        consoleUpdate(nullptr);
        return;
    }

    uiPrintf(5, "\x1b[32mAutomatic scan complete\x1b[0m");
    uiPrintf(7, "Low VMIN : %d mV", g.lowVminGood);
    uiPrintf(8, "Regions  : %d", g.vminValidateCount);
    int row = 10;
    for (int i = 0; i < g.vminValidateCount && i < 6; ++i)
        uiPrintf(row++, " %d. %s @ ~%d mV", i + 1, formatClock(g.vminValidateHz[i]).c_str(), g.vminValidateMv[i]);
    row++;
    if (g.vminFloorHz)
        uiPrintf(row++, "VMIN floor ends at %s", formatClock(g.vminFloorHz).c_str());
    uiPrintf(row++, "Previous overrides : %s", g_vminScanRestoreOk ? "\x1b[32mRESTORED\x1b[0m" : "\x1b[31mCHECK HOC\x1b[0m");
    row += 2;
    uiPrintf(row++, "A : Continue to validation");
    uiPrintf(row++, "B : Exit");
    consoleUpdate(nullptr);
}

'''
s = s[:idx] + helpers + s[idx:]

# The user-facing sweep stage becomes one automatic scan start page.
old = '''    if (hasOverrides) {\n        uiPrintf(row++, "@ Horizon OC");\n        row++;\n        printOverrides(row, expected);\n        row += 5;\n    }\n\n    if (isVminSweepStage(g.stage)) {\n        uiPrintf(row++, "Voltage scan:");\n        uiPrintf(row++, "A : Read voltage");\n        uiPrintf(row++, "    (3 samples / progress shown)");\n        if (g.lastProbeHz) uiPrintf(row++, "Last: %s @ ~%d mV", formatClock(g.lastProbeHz).c_str(), g.lastProbeMv);\n        uiPrintf(row++, "B : Exit");\n        return;\n    }'''
new = '''    if (isVminSweepStage(g.stage)) {\n        uiPrintf(row++, "Automatic CPU voltage scan");\n        row++;\n        uiPrintf(row++, "Low VMIN : %d mV", g.lowVminGood);\n        uiPrintf(row++, "CPU       : 510 -> 612 -> 714 ->");\n        uiPrintf(row++, "            816 -> 918 -> 1020 MHz");\n        uiPrintf(row++, "GPU       : 384 MHz (automatic)");\n        uiPrintf(row++, "RAM       : 1331.2 MHz (automatic)");\n        row++;\n        uiPrintf(row++, "The Wizard will set Temporary Overrides,");\n        uiPrintf(row++, "measure 3 samples at every CPU clock,");\n        uiPrintf(row++, "then restore your previous Overrides.");\n        row += 2;\n        uiPrintf(row++, "A : START SCAN");\n        uiPrintf(row++, "B : Exit");\n        return;\n    }\n\n    if (hasOverrides) {\n        uiPrintf(row++, "@ Horizon OC");\n        row++;\n        printOverrides(row, expected);\n        row += 5;\n    }'''
if old not in s:
    raise SystemExit('render sweep block missing')
s = s.replace(old, new, 1)

# Make the dedicated scan screen part of normal render priority.
rep('''    if (g_bootPrompt) { renderBootPrompt(); return; }\n    if (g_interruptedPrompt) { renderInterruptedPrompt(); return; }''', '''    if (g_bootPrompt) { renderBootPrompt(); return; }\n    if (g_vminScanScreen) { renderVminScanScreen(); return; }\n    if (g_interruptedPrompt) { renderInterruptedPrompt(); return; }''')

# Replace the single-point probe with the full automatic sweep.
replace_function('void runVminProbe()', r'''void runAutomaticVminScan() {
    static const Stage stages[6] = {
        Stage::LowVminLong,
        Stage::LowVminSweep612,
        Stage::LowVminSweep714,
        Stage::LowVminValidate816,
        Stage::LowVminSweep918,
        Stage::LowVminValidate1020,
    };
    static const u32 cpuHz[6] = {
        CLOCK_CPU_VMIN_510_HZ,
        CLOCK_CPU_LOW_HZ,
        CLOCK_CPU_VMIN_714_HZ,
        CLOCK_CPU_VMIN_MID_HZ,
        CLOCK_CPU_VMIN_918_HZ,
        CLOCK_CPU_NORMAL_HZ,
    };

    g_vminScanScreen = false;
    g_vminScanSuccess = false;
    g_vminScanRestoreOk = true;
    g_vminScanErrorRc = 0;
    g_vminScanErrorText.clear();

    HocMonClocks before{};
    Result rc = hocmonGetClocks(&before);
    if (R_FAILED(rc)) {
        g_vminScanErrorRc = rc;
        g_vminScanErrorText = "Could not read current HOC overrides.";
        g_vminScanScreen = true;
        return;
    }

    clearVminSweepData();
    g.stage = Stage::LowVminLong;
    saveState();

    // Move CPU to the safe low scan clock before changing the other modules.
    rc = hocmonSetOverride(HocMonModule_CPU, cpuHz[0]);
    if (R_SUCCEEDED(rc)) rc = hocmonSetOverride(HocMonModule_GPU, CLOCK_GPU_NORMAL_HZ);
    if (R_SUCCEEDED(rc)) rc = hocmonSetOverride(HocMonModule_MEM, CLOCK_RAM_NORMAL_HZ);
    if (R_FAILED(rc)) {
        g_vminScanErrorRc = rc;
        g_vminScanErrorText = "HOC refused an automatic Temporary Override.";
        g_vminScanRestoreOk = restoreTemporaryOverrides(before);
        g_vminScanScreen = true;
        return;
    }

    for (int i = 0; i < 6; ++i) {
        consoleClear();
        uiPrintf(1, "\x1b[36mBattery Wizard - AUTO VMIN SCAN\x1b[0m");
        uiPrintf(3, "----------------------------------------");
        uiPrintf(5, "Frequency : %d / 6", i + 1);
        uiPrintf(7, "Setting CPU override : %s", formatClock(cpuHz[i]).c_str());
        uiPrintf(8, "GPU / RAM            : 384 / 1331.2 MHz");
        uiPrintf(10, "Please do not open Horizon OC during scan.");
        consoleUpdate(nullptr);

        if (i > 0) {
            rc = hocmonSetOverride(HocMonModule_CPU, cpuHz[i]);
            if (R_FAILED(rc)) {
                g_vminScanErrorRc = rc;
                g_vminScanErrorText = "Could not switch the CPU Temporary Override.";
                break;
            }
        }

        // Let HOC/governor settle before taking the first context sample.
        svcSleepThread(700'000'000);

        bool measured = sampleVminVoltage(stages[i], i, 6);
        if (!measured) {
            // One automatic retry covers a late governor/context update.
            svcSleepThread(500'000'000);
            measured = sampleVminVoltage(stages[i], i, 6);
        }
        if (!measured) {
            g_vminScanErrorRc = g_overrideCheck.readOk ? 0 : g_overrideCheck.rc;
            if (!g_overrideCheck.cpuOk || !g_overrideCheck.gpuOk || !g_overrideCheck.ramOk)
                g_vminScanErrorText = "Requested Temporary Override was not applied.";
            else if (!g_overrideCheck.cpuAppliedOk)
                g_vminScanErrorText = "CPU clock did not settle on the requested value.";
            else
                g_vminScanErrorText = "Could not obtain 3 valid CPU-voltage samples.";
            break;
        }

        recordVminObservation(stages[i]);

        consoleClear();
        uiPrintf(1, "\x1b[36mBattery Wizard - AUTO VMIN SCAN\x1b[0m");
        uiPrintf(3, "----------------------------------------");
        uiPrintf(5, "Frequency : %d / 6", i + 1);
        uiPrintf(7, "\x1b[32mMeasured\x1b[0m : %s @ ~%d mV", formatClock(cpuHz[i]).c_str(), g.lastProbeMv);
        consoleUpdate(nullptr);
        svcSleepThread(350'000'000);
    }

    g_vminScanRestoreOk = restoreTemporaryOverrides(before);

    if (!g_vminScanErrorText.empty() || g_vminScanErrorRc) {
        g.stage = Stage::LowVminLong;
        saveState();
        g_vminScanScreen = true;
        return;
    }

    buildVminPlateaus();
    if (g.vminValidateCount <= 0) {
        g_vminScanErrorText = "No valid CPU voltage regions were detected.";
        g.stage = Stage::LowVminLong;
        saveState();
        g_vminScanScreen = true;
        return;
    }

    g.stage = Stage::LowVminPlateauValidate;
    g.stageReadyAfterBoot = true;
    saveState();
    g_vminScanSuccess = true;
    g_vminScanScreen = true;
}''')

# Dedicated scan-screen key handling goes before the interrupted-test page.
needle = '''        if (g_interruptedPrompt) {\n'''
block = '''        if (g_vminScanScreen) {\n            if (k & HidNpadButton_A) {\n                if (g_vminScanSuccess) {\n                    g_vminScanScreen = false;\n                    redraw = true;\n                } else {\n                    g_vminScanScreen = false;\n                    runAutomaticVminScan();\n                    redraw = true;\n                }\n            } else if (k & HidNpadButton_B) {\n                if (g_vminScanSuccess) {\n                    saveState();\n                    break;\n                }\n                g_vminScanScreen = false;\n                redraw = true;\n            }\n            svcSleepThread(20'000'000);\n            continue;\n        }\n\n'''
if needle not in s:
    raise SystemExit('interrupted prompt marker missing')
s = s.replace(needle, block + needle, 1)

# No manual override retry path is needed for the automatic VMIN scan anymore.
rep('''                if (g_overrideAction == PendingOverrideAction::VminProbe) runVminProbe();\n                else runCurrentTest();''', '''                if (g_overrideAction == PendingOverrideAction::VminProbe) runAutomaticVminScan();\n                else runCurrentTest();''')
rep('''            if (isVminSweepStage(g.stage)) {\n                runVminProbe();\n            } else {''', '''            if (isVminSweepStage(g.stage)) {\n                runAutomaticVminScan();\n            } else {''')
rep('''            } else if (isVminSweepStage(g.stage)) {\n                runVminProbe();\n            } else {''', '''            } else if (isVminSweepStage(g.stage)) {\n                runAutomaticVminScan();\n            } else {''')

p.write_text(s)
print('automatic VMIN override scan applied')
