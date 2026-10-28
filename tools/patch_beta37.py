from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

def rep(old, new, label, count=1):
    global s
    if old not in s:
        raise SystemExit(f'{label} not found')
    s = s.replace(old, new, count)


def replace_between(start_marker, end_marker, replacement, label):
    global s
    a = s.find(start_marker)
    if a < 0:
        raise SystemExit(f'{label} start not found')
    b = s.find(end_marker, a)
    if b < 0:
        raise SystemExit(f'{label} end not found')
    s = s[:a] + replacement + s[b:]

# Generic built-in test footer: same wording everywhere.
rep('''void footerTest(int row) {
    uiPrintf(row,     "Keys:");
    uiPrintf(row + 1, "A : Start Test");
    uiPrintf(row + 2, "    If the test crashes, reboot and");
    uiPrintf(row + 3, "    open the Wizard again.");
    uiPrintf(row + 4, "+ : Known PASS / Skip step");
    uiPrintf(row + 5, "X : Known FAIL / Skip");
    uiPrintf(row + 6, "B : Exit");
    printResetHint(row + 6);
}
''', '''void footerTest(int row) {
    uiPrintf(row,     "A : Start automatic stability test");
    uiPrintf(row + 1, "    If the test crashes, reboot and");
    uiPrintf(row + 2, "    open the Wizard again.");
    uiPrintf(row + 3, "+ : Known PASS / Skip step");
    uiPrintf(row + 4, "X : Known FAIL / Skip step");
    uiPrintf(row + 5, "B : Exit");
    printResetHint(row + 5);
}
''', 'footerTest')

# Automatic temporary-override setup for every built-in stability test.
needle = '''bool restoreTemporaryOverrides(const HocMonClocks& before) {
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
'''
insert = '''bool restoreTemporaryOverrides(const HocMonClocks& before) {
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

bool setupAutomaticTestOverrides(Stage st, HocMonClocks& before) {
    g_overrideCheck = OverrideCheckState{};
    if (!overridePlan(st, g_overrideCheck.expected)) return true;

    g_overrideCheck.rc = hocmonGetClocks(&before);
    if (R_FAILED(g_overrideCheck.rc)) {
        g_overrideCheck.readOk = false;
        return false;
    }

    // Set the supporting clocks first and CPU last. The user does not need to
    // manage these Temporary Overrides manually.
    Result rc = hocmonSetOverride(HocMonModule_GPU, g_overrideCheck.expected.gpuHz);
    if (R_SUCCEEDED(rc)) rc = hocmonSetOverride(HocMonModule_MEM, g_overrideCheck.expected.ramHz);
    if (R_SUCCEEDED(rc)) rc = hocmonSetOverride(HocMonModule_CPU, g_overrideCheck.expected.cpuHz);
    if (R_FAILED(rc)) {
        g_overrideCheck.rc = rc;
        restoreTemporaryOverrides(before);
        return false;
    }

    svcSleepThread(400'000'000);
    g_overrideCheck.rc = hocmonGetClocks(&g_overrideCheck.current);
    if (R_FAILED(g_overrideCheck.rc)) {
        g_overrideCheck.readOk = false;
        restoreTemporaryOverrides(before);
        return false;
    }

    g_overrideCheck.readOk = true;
    g_overrideCheck.cpuOk = clockMatches(g_overrideCheck.current.overrideHz[0], g_overrideCheck.expected.cpuHz);
    g_overrideCheck.gpuOk = clockMatches(g_overrideCheck.current.overrideHz[1], g_overrideCheck.expected.gpuHz);
    g_overrideCheck.ramOk = clockMatches(g_overrideCheck.current.overrideHz[2], g_overrideCheck.expected.ramHz);
    if (!(g_overrideCheck.cpuOk && g_overrideCheck.gpuOk && g_overrideCheck.ramOk)) {
        restoreTemporaryOverrides(before);
        return false;
    }
    return true;
}

void renderVminScanScreen() {
'''
rep(needle, insert, 'automatic override helper')

# Error-only override page. Normal test starts never ask the user to set clocks.
new_override_prompt = '''void renderOverridePrompt() {
    consoleClear();
    uiPrintf(1, "\\x1b[31mBattery Wizard - TEST SETUP FAILED\\x1b[0m");
    uiPrintf(2, "Step : %s", compactStepName(g.stage));
    uiPrintf(3, "----------------------------------------");

    uiPrintf(5, "Could not automatically set or verify");
    uiPrintf(6, "the required test clocks.");

    if (!g_overrideCheck.readOk) {
        uiPrintf(8, "Horizon OC clock read failed.");
        if (g_overrideCheck.rc)
            uiPrintf(9, "Result : 0x%08X", g_overrideCheck.rc);
    } else {
        uiPrintf(8, "Required test clocks:");
        uiPrintf(9,  " CPU : %s", formatClock(g_overrideCheck.expected.cpuHz).c_str());
        uiPrintf(10, " GPU : %s", formatClock(g_overrideCheck.expected.gpuHz).c_str());
        uiPrintf(11, " RAM : %s", formatClock(g_overrideCheck.expected.ramHz).c_str());
        uiPrintf(13, "Current Temporary Overrides:");
        uiPrintf(14, " CPU : %s", formatClock(g_overrideCheck.current.overrideHz[0]).c_str());
        uiPrintf(15, " GPU : %s", formatClock(g_overrideCheck.current.overrideHz[1]).c_str());
        uiPrintf(16, " RAM : %s", formatClock(g_overrideCheck.current.overrideHz[2]).c_str());
    }

    uiPrintf(19, "A : Try automatic setup again");
    uiPrintf(20, "B : Back");
    consoleUpdate(nullptr);
}

'''
replace_between('void renderOverridePrompt() {', 'void renderResultScreen() {', new_override_prompt, 'renderOverridePrompt')

# Validation pages: consistent objective/current-value layout and no visible
# Temporary Override instructions.
needle = '''bool isVminSweepStage(Stage st);\n\nvoid renderTestStage() {'''.replace('\\n', '\n')
helper = '''bool isVminSweepStage(Stage st);

void renderValidationObjective(int& row) {
    HocMonConfig current{};
    bool haveCurrent = R_SUCCEEDED(hocmonGetConfig251(&current));
    if (!haveCurrent) haveCurrent = readHocConfigIni(current);

    uiPrintf(row++, "Objective:");
    switch (g.stage) {
        case Stage::VddqQuick:
        case Stage::VddqLong: {
            const int value = g.stage == Stage::VddqQuick ? g.vddqTest : g.vddqGood;
            uiPrintf(row++, "VDDQ %d mV will be tested now.", value);
            uiPrintf(row++, "Current VDDQ : %s", haveCurrent ? formatMv((int)(current.vddqUv / 1000U)).c_str() : "unavailable");
            break;
        }
        case Stage::Vdd2Quick:
        case Stage::Vdd2Long: {
            const int value = g.stage == Stage::Vdd2Quick ? g.vdd2TestUv : g.vdd2GoodUv;
            uiPrintf(row++, "VDD2 %s will be tested now.", formatVdd2(value).c_str());
            uiPrintf(row++, "Current VDD2 : %s", haveCurrent ? formatVdd2((int)current.vdd2Uv).c_str() : "unavailable");
            break;
        }
        case Stage::HighUvQuick:
        case Stage::HighUvLong: {
            const int value = g.stage == Stage::HighUvQuick ? g.highUvTest : g.highUvGood;
            uiPrintf(row++, "High UV %d will be tested now.", value);
            if (haveCurrent) uiPrintf(row++, "Current High UV : %d", current.highUv);
            else uiPrintf(row++, "Current High UV : unavailable");
            break;
        }
        case Stage::RamBoostValidate:
            uiPrintf(row++, "Tuned RAM voltages will be tested now.");
            uiPrintf(row++, "Boost operating state validation.");
            if (haveCurrent) {
                uiPrintf(row++, "Current VDDQ : %s", formatMv((int)(current.vddqUv / 1000U)).c_str());
                uiPrintf(row++, "Current VDD2 : %s", formatVdd2((int)current.vdd2Uv).c_str());
            }
            break;
        case Stage::Ram1331Validate:
            uiPrintf(row++, "Tuned RAM voltages will be tested now.");
            uiPrintf(row++, "Handheld operating state validation.");
            if (haveCurrent) {
                uiPrintf(row++, "Current VDDQ : %s", formatMv((int)(current.vddqUv / 1000U)).c_str());
                uiPrintf(row++, "Current VDD2 : %s", formatVdd2((int)current.vdd2Uv).c_str());
            }
            break;
        case Stage::BoostCpuRamValidate:
            uiPrintf(row++, "CPU + RAM Boost stability will be tested now.");
            break;
        case Stage::NormalMatrixValidate:
            uiPrintf(row++, "Final handheld CPU stability will be tested now.");
            break;
        case Stage::NormalMemValidate:
            uiPrintf(row++, "Final handheld RAM stability will be tested now.");
            break;
        case Stage::NormalGpuValidate:
            uiPrintf(row++, "Final handheld GPU stability will be tested now.");
            break;
        case Stage::BoostMatrixValidate:
            uiPrintf(row++, "Final Boost CPU stability will be tested now.");
            break;
        case Stage::BoostMemValidate:
            uiPrintf(row++, "Final Boost RAM stability will be tested now.");
            break;
        case Stage::BoostCpuMemValidate:
            uiPrintf(row++, "Final Boost CPU + RAM stability will be tested now.");
            break;
        case Stage::LowVminFinalLong:
            uiPrintf(row++, "Low VMIN stability will be tested now.");
            uiPrintf(row++, "Current Low VMIN : %s", haveCurrent ? formatMv(current.lowVminMv).c_str() : "unavailable");
            break;
        default:
            uiPrintf(row++, "This stability step will be tested now.");
            break;
    }
    row++;
}

void renderTestStage() {'''
rep(needle, helper, 'validation objective helper')

# Hide internal recovery bookkeeping from validation pages.
rep('''    int row = 5;
    if (g.recoveryNeeded) {
        uiPrintf(row++, "\\x1b[33mPrevious safe value restored.\\x1b[0m");
        g.recoveryNeeded = false;
        row++;
    }
''', '''    int row = 5;
    if (g.recoveryNeeded) g.recoveryNeeded = false;
''', 'hide recovery bookkeeping')

# Generic test pages no longer expose Temporary Overrides.
rep('''    stress::Kind kind;
    int seconds = 0;
    const bool hasTest = testPlan(g.stage, kind, seconds);
    OverrideExpectation expected{};
    const bool hasOverrides = overridePlan(g.stage, expected);

    if (hasOverrides) {
        uiPrintf(row++, "@ Horizon OC");
        row++;
        printOverrides(row, expected);
        row += 5;
    }
    if (hasTest) {
        uiPrintf(row++, "Test:");
        uiPrintf(row++, "%s - %s", seconds == 60 ? "1 min" : "1 hour", compactTestName(kind));
        footerTest(row + 1);
    }
''', '''    stress::Kind kind;
    int seconds = 0;
    const bool hasTest = testPlan(g.stage, kind, seconds);
    if (hasTest) {
        renderValidationObjective(row);
        uiPrintf(row++, "Test:");
        uiPrintf(row++, "%s - %s", seconds == 60 ? "1 min" : "1 hour", compactTestName(kind));
        footerTest(row + 1);
    }
''', 'generic validation layout')

# Real-world manual validation also offers the same known-pass skip action.
rep('''    uiPrintf(15, "Keys:");
    uiPrintf(16, "A : PASS");
    uiPrintf(17, "X : FAIL");
    uiPrintf(18, "B : Exit");
    printResetHint(18);
''', '''    uiPrintf(15, "Keys:");
    uiPrintf(16, "A : PASS");
    uiPrintf(17, "+ : Known PASS / Skip step");
    uiPrintf(18, "X : FAIL");
    uiPrintf(19, "B : Exit");
    printResetHint(19);
''', 'real world known pass')

# Built-in tests automatically set, verify, and then restore their test clocks.
new_run = '''void runCurrentTest() {
    stress::Kind kind;
    int seconds = 0;
    if (!testPlan(g.stage, kind, seconds)) return;

    OverrideExpectation expected{};
    const bool hasOverrides = overridePlan(g.stage, expected);
    HocMonClocks before{};
    g_overrideAction = PendingOverrideAction::StartTest;
    if (hasOverrides && !setupAutomaticTestOverrides(g.stage, before)) {
        g_overridePrompt = true;
        return;
    }
    g_overridePrompt = false;

    const Stage testedStage = g.stage;
    g_lastVminAtFloor = false;
    if (isVminSweepStage(testedStage))
        recordVminObservation(testedStage);
    g.testRunning = true;
    g.testKind = static_cast<int>(kind);
    g.testDurationSec = seconds;
    g.testStage = static_cast<int>(testedStage);
    saveState();

    g_lastKind = kind;
    g_lastResult = stress::run(kind, seconds);

    g.testRunning = false;
    g.testKind = 0;
    g.testDurationSec = 0;
    g.testStage = 0;
    saveState();

    const bool restored = !hasOverrides || restoreTemporaryOverrides(before);

    g_resultAction.clear();
    if (g_lastResult.outcome == stress::Outcome::Pass) {
        handlePass();
        g_resultAction = "PASS recorded automatically. The wizard advanced to the next step.";
        if (isVminSweepStage(testedStage)) {
            const u32 uv = g_overrideCheck.current.cpuVoltageUv;
            g_resultAction += " CPU rail was about " + std::to_string((uv + 500U) / 1000U) + " mV.";
        }
    } else if (g_lastResult.outcome == stress::Outcome::Fail) {
        handleFail(false);
        g_resultAction = "FAIL recorded automatically. Follow the safer value shown on the next step.";
    } else if (g_lastResult.outcome == stress::Outcome::Cancelled) {
        g_resultAction = "No tuning result was recorded. You can run the same test again.";
    } else {
        g_resultAction = "The tuning value was NOT marked failed. Fix the test-engine problem and retry.";
    }
    if (!restored)
        g_resultAction += " WARNING: the previous test clocks could not be fully restored.";
    g_resultScreen = true;
}

'''
replace_between('void runCurrentTest() {', '} // namespace', new_run, 'runCurrentTest')

# Known PASS / Skip step must also work on the manual real-world step.
rep('''        } else if ((k & HidNpadButton_Plus) && g.stage != Stage::Preparation) {
            if (g.stage == Stage::LowUvValidateQuick) {
''', '''        } else if ((k & HidNpadButton_Plus) && g.stage != Stage::Preparation) {
            if (g.stage == Stage::RealWorldValidate) {
                g_manualPass = true;
                handlePass();
                g_manualPass = false;
            } else if (g.stage == Stage::LowUvValidateQuick) {
''', 'real world plus handling')

p.write_text(s)
print('beta37 consistency patch applied')
