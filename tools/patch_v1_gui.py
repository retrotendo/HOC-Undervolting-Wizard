from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

# 1) Include the renderer and remove the old fixed center column.
s = s.replace('#include "updater.hpp"\n', '#include "updater.hpp"\n#include "gui_console.hpp"\n', 1)
s = s.replace('constexpr int UI_COL = 36;\n', '', 1)

# 2) Animation state.
s = s.replace('bool g_lastVminAtFloor = false;\n', 'bool g_lastVminAtFloor = false;\nbool g_guiPulse = false;\n', 1)

old_ui = '''void uiPrintf(int row, const char* fmt, ...) {
    std::printf("\\x1b[%d;%dH", row, UI_COL);
    va_list args;
    va_start(args, fmt);
    std::vprintf(fmt, args);
    va_end(args);
}
'''

new_ui = r'''int guiProgressStep(Stage s) {
    switch (s) {
        case Stage::HardwareDetection:
        case Stage::Preparation:
            return 1;
        case Stage::LowUvQuick:
        case Stage::LowUvValidateQuick:
        case Stage::LowUvLong:
            return 2;
        case Stage::LowVminQuick:
        case Stage::LowVminLong:
        case Stage::LowVminSweep612:
        case Stage::LowVminSweep714:
        case Stage::LowVminValidate816:
        case Stage::LowVminSweep918:
        case Stage::LowVminValidate1020:
        case Stage::LowVminFinalLong:
        case Stage::LowVminPlateauValidate:
            return 3;
        case Stage::VddqQuick:
        case Stage::VddqLong:
            return 4;
        case Stage::Vdd2Quick:
        case Stage::Vdd2Long:
        case Stage::RamBoostValidate:
        case Stage::Ram1331Validate:
        case Stage::NormalMatrixValidate:
            return 5;
        case Stage::HighUvQuick:
        case Stage::HighUvLong:
        case Stage::BoostCpuRamValidate:
        case Stage::BoostMatrixValidate:
        case Stage::BoostMemValidate:
        case Stage::BoostCpuMemValidate:
            return 6;
        case Stage::NormalMemValidate:
        case Stage::NormalGpuValidate:
        case Stage::RealWorldValidate:
        case Stage::Complete:
            return 7;
    }
    return 1;
}

u32 guiInstructionMask() {
    if (g_configPrompt) return g_configCheck.mask;
    if (g_autoPrepConfirm) return g_autoSetMask;
    if (g_rebootConfirm) return g_configCheck.mask;
    if (g_bootPrompt && g.pendingConfigMask) return g.pendingConfigMask;
    if (g.pendingConfigMask) return g.pendingConfigMask;
    return activeConfigMask();
}

std::string guiVdd2Value(int uv) {
    return formatVdd2(uv);
}

std::string guiDurationForStage(Stage st) {
    stress::Kind kind;
    int seconds = 0;
    if (!testPlan(st, kind, seconds)) return "";
    if (seconds == 60) return "1 minute";
    if (seconds == 1800) return "30 minutes";
    return "1 hour";
}

gui::View buildGuiView() {
    gui::View v{};
    v.version = HOC_WIZARD_VERSION;
    v.activeStep = guiProgressStep(g.stage);
    v.pulse = g_guiPulse;

    const u32 mask = guiInstructionMask();
    if (mask & Config_Prepare) {
        v.instructionTitle = "Set values @ Horizon OC";
        v.instructionLine1 = "Preparation";
        v.instructionLine2 = "Use values shown left";
    } else if (mask != Config_None) {
        const bool ram = (mask & (Config_Vddq | Config_Vdd2)) != 0;
        v.instructionTitle = (mask & (mask - 1U)) ? "Set values @ Horizon OC" : "Set value @ Horizon OC";
        v.instructionLine1 = ram ? "RAM Settings" : "CPU Settings";
        if ((mask & Config_LowUv) != 0)
            v.instructionLine2 = "Low UV  " + std::to_string(targetLowUv());
        else if ((mask & Config_LowVmin) != 0)
            v.instructionLine2 = "Low VMIN  " + std::to_string(targetLowVmin()) + " mV";
        else if ((mask & Config_Vddq) && (mask & Config_Vdd2))
            v.instructionLine2 = "VDDQ + VDD2 pair";
        else if ((mask & Config_Vddq) != 0)
            v.instructionLine2 = "VDDQ  " + std::to_string(targetVddqMv()) + " mV";
        else if ((mask & Config_Vdd2) != 0)
            v.instructionLine2 = "VDD2  " + guiVdd2Value(targetVdd2Uv());
        else if ((mask & Config_HighUv) != 0)
            v.instructionLine2 = "High UV  " + std::to_string(targetHighUv());
    } else if (g.limitNoticePending) {
        v.instructionTitle = "Wizard limit reached";
        v.instructionLine1 = stageName(g.stage);
        v.instructionLine2 = "Confirm to continue";
    } else if (g_bootPrompt) {
        v.instructionTitle = "Boot check";
        v.instructionLine1 = stageName(g.stage);
        v.instructionLine2 = "Confirm boot stability";
    } else if (g_vminScanScreen) {
        v.instructionTitle = "CPU voltage scan";
        v.instructionLine1 = "Review scan result";
        v.instructionLine2 = "Continue when ready";
    } else if (g_configPrompt) {
        v.instructionTitle = "Setting not ready";
        v.instructionLine1 = "Fix WRONG values";
        v.instructionLine2 = "Then check again";
    } else if (g_rebootConfirm) {
        v.instructionTitle = "Reboot required";
        v.instructionLine1 = "Setting verified";
        v.instructionLine2 = "Apply with reboot";
    } else if (g_resultScreen) {
        v.instructionTitle = "Test result";
        v.instructionLine1 = stageName(g.stage);
        v.instructionLine2 = "Review and continue";
    } else if (g.stage == Stage::LowUvLong || g.stage == Stage::LowVminLong) {
        v.instructionTitle = "Scan voltage regions";
        v.instructionLine1 = stageName(g.stage);
        v.instructionLine2 = "A : Start scan";
    } else if (g.stage == Stage::RealWorldValidate) {
        v.instructionTitle = "Real-world validation";
        v.instructionLine1 = "Remove all overrides";
        v.instructionLine2 = "Then run game test";
    } else if (g.stage == Stage::Complete) {
        v.instructionTitle = "Undervolting complete";
        v.instructionLine1 = "Final values saved";
        v.instructionLine2 = "B : Exit";
    } else if (g.stage == Stage::HardwareDetection) {
        v.instructionTitle = "Hardware detection";
        v.instructionLine1 = g.ramDetected ? "RAM detected" : "Detect RAM module";
        v.instructionLine2 = g.ramDetected ? "A : Continue" : "A : Retry";
    } else {
        const std::string d = guiDurationForStage(g.stage);
        if (!d.empty()) {
            v.instructionTitle = "Start stability test";
            v.instructionLine1 = stageName(g.stage);
            v.instructionLine2 = d;
        } else {
            v.instructionTitle = stageName(g.stage);
            v.instructionLine1 = "Follow the guide";
            v.instructionLine2 = "Choose an action";
        }
    }

    HocMonConfig c{};
    bool have = R_SUCCEEDED(hocmonGetConfig251(&c));
    if (!have) have = readHocConfigIni(c);
    v.haveActiveValues = have;

    v.values[0].label = "CPU Low UV";
    v.values[1].label = "CPU Low VMIN";
    v.values[2].label = "VDDQ";
    v.values[3].label = "VDD2";
    v.values[4].label = "CPU High UV";

    if (have) {
        v.values[0].value = std::to_string(c.lowUv);
        v.values[1].value = std::to_string(c.lowVminMv) + " mV";
        v.values[2].value = std::to_string((int)(c.vddqUv / 1000U)) + " mV";
        v.values[3].value = guiVdd2Value((int)c.vdd2Uv);
        v.values[4].value = std::to_string(c.highUv);

        if (mask & Config_Prepare) {
            v.values[0].mismatch = c.lowUv != STOCK_LOW_UV;
            v.values[1].mismatch = c.lowVminMv != STOCK_LOW_VMIN_MV;
            v.values[2].mismatch = (int)(c.vddqUv / 1000U) != g.vddqStartMv;
            v.values[3].mismatch = (int)c.vdd2Uv != STOCK_VDD2_UV;
            v.values[4].mismatch = c.highUv != STOCK_HIGH_UV;
        } else {
            if (mask & Config_LowUv) v.values[0].mismatch = c.lowUv != targetLowUv();
            if (mask & Config_LowVmin) v.values[1].mismatch = c.lowVminMv != targetLowVmin();
            if (mask & Config_Vddq) v.values[2].mismatch = (int)(c.vddqUv / 1000U) != targetVddqMv();
            if (mask & Config_Vdd2) v.values[3].mismatch = (int)c.vdd2Uv != targetVdd2Uv();
            if (mask & Config_HighUv) v.values[4].mismatch = c.highUv != targetHighUv();
        }
    }
    return v;
}

void guiPageClear() {
    gui::draw(buildGuiView());
}

void uiPrintf(int row, const char* fmt, ...) {
    char buffer[1024];
    va_list args;
    va_start(args, fmt);
    std::vsnprintf(buffer, sizeof(buffer), fmt, args);
    va_end(args);
    gui::printLeft(row, buffer);
}
'''

if old_ui not in s:
    raise SystemExit('old uiPrintf block not found')
s = s.replace(old_ui, new_ui, 1)

# 3) Compact title: the global header already carries the app name.
old_title = '''void title() {
    uiPrintf(1, "\\x1b[36mBattery Wizard\\x1b[0m");
    uiPrintf(2, "Step : %s", compactStepName(g.stage));
    uiPrintf(3, "----------------------------------------");
}
'''
new_title = '''void title() {
    uiPrintf(1, "\\x1b[1;96mStep : %s\\x1b[0m", compactStepName(g.stage));
    uiPrintf(2, "------------------------------------------------");
}
'''
if old_title not in s:
    raise SystemExit('title block not found')
s = s.replace(old_title, new_title, 1)

# 4) On search-setting pages the right panel is now the single source of truth
# for the requested HOC value. Keep the beta42 objective/actions on the left.
old_set_block = '''        row++;
        const bool multiple = (configMask & Config_Vddq) && (configMask & Config_Vdd2);
        uiPrintf(row++, multiple ? "Set values:" : "Set value:");
        row++;
        uiPrintf(row++, "@ Horizon OC");
        row++;
        uiPrintf(row++, (configMask & (Config_Vddq | Config_Vdd2)) ? "RAM Settings:" : "CPU Settings:");
        if (configMask & Config_LowUv) uiPrintf(row++, " - Low UV   : %d", targetLowUv());
        if (configMask & Config_LowVmin) uiPrintf(row++, " - Low VMIN : %d mV", targetLowVmin());
        if (configMask & Config_Vddq) uiPrintf(row++, " - VDDQ     : %d mV", targetVddqMv());
        if (configMask & Config_Vdd2) uiPrintf(row++, " - VDD2     : %s", formatVdd2(targetVdd2Uv()).c_str());
        if (configMask & Config_HighUv) uiPrintf(row++, " - High UV  : %d", targetHighUv());
        row += 2;
'''
new_set_block = '''        // The requested value is shown once in the right-side Current Instruction box.
        row += 2;
'''
if old_set_block not in s:
    raise SystemExit('search set-value block not found')
s = s.replace(old_set_block, new_set_block, 1)

# 5) Paint the GUI shell wherever the old wizard cleared the console. Applet-mode
# startup remains intentionally plain because the full-memory GUI is unavailable.
marker = 'void guiPageClear() {'
pos = s.find(marker)
if pos < 0:
    raise SystemExit('guiPageClear marker missing')
head, tail = s[:pos], s[pos:]
tail = tail.replace('consoleClear();', 'guiPageClear();')
s = head + tail
# Undo recursion introduced by the mechanical replacement inside guiPageClear.
s = s.replace('void guiPageClear() {\n    gui::draw(buildGuiView());\n}', 'void guiPageClear() {\n    gui::draw(buildGuiView());\n}', 1)
# Applet-mode direct text must keep a plain clear because it writes at 1;1.
s = s.replace('            guiPageClear();\n            std::printf("\\x1b[1;1H\\x1b[31mHOC Undervolting Wizard - CANNOT START',
              '            consoleClear();\n            std::printf("\\x1b[1;1H\\x1b[31mHOC Undervolting Wizard - CANNOT START', 1)
# Risk page is also kept plain for this first GUI beta; updater/risk happen before
# the main fullscreen wizard shell starts.
s = s.replace('        guiPageClear();\n        std::printf("\\x1b[1;1H\\x1b[31mHOC Undervolting Wizard - WARNING',
              '        consoleClear();\n        std::printf("\\x1b[1;1H\\x1b[31mHOC Undervolting Wizard - WARNING', 1)

# 6) Convert the two remaining direct-print wizard pages so they do not overwrite
# the GUI header/sidebar.
start = s.index('void renderInterruptedPrompt() {')
end = s.index('void renderOverridePrompt() {', start)
new_interrupted = r'''void renderInterruptedPrompt() {
    guiPageClear();
    uiPrintf(1, "\x1b[1;33mInterrupted Test\x1b[0m");
    uiPrintf(2, "------------------------------------------------");
    uiPrintf(4, "The previous built-in test was marked RUNNING");
    uiPrintf(5, "but never finished.");
    uiPrintf(7, "Stage: %s", stageName(static_cast<Stage>(g.testStage)));
    uiPrintf(8, "Test : %s", stress::kindName(static_cast<stress::Kind>(g.testKind)));
    uiPrintf(9, "Time : %s", g.testDurationSec == 60 ? "1 minute" : (g.testDurationSec == 1800 ? "30 minutes" : "1 hour"));
    uiPrintf(11, "Did the console freeze, crash or reboot?");
    uiPrintf(14, "A : YES - count as FAIL");
    uiPrintf(15, "X : NO - interrupted manually; run again");
    uiPrintf(16, "B : Exit and decide later");
    consoleUpdate(nullptr);
}

'''
s = s[:start] + new_interrupted + s[end:]

start = s.index('void renderResultScreen() {')
end = s.index('void render() {', start)
new_result = r'''void renderResultScreen() {
    guiPageClear();
    uiPrintf(1, "\x1b[1;96mBuilt-in %s\x1b[0m", stress::kindName(g_lastKind));
    uiPrintf(2, "------------------------------------------------");
    if (g_lastResult.outcome == stress::Outcome::Pass)
        uiPrintf(4, "\x1b[32mPASS\x1b[0m");
    else if (g_lastResult.outcome == stress::Outcome::Fail)
        uiPrintf(4, "\x1b[31mFAIL\x1b[0m");
    else if (g_lastResult.outcome == stress::Outcome::Cancelled)
        uiPrintf(4, "\x1b[33mCANCELLED\x1b[0m");
    else
        uiPrintf(4, "\x1b[31mTEST ENGINE ERROR\x1b[0m");
    uiPrintf(6, "Elapsed    : %llu ms", (unsigned long long)g_lastResult.elapsedMs);
    uiPrintf(7, "Iterations : %llu", (unsigned long long)g_lastResult.iterations);
    uiPrintf(8, "Errors     : %llu", (unsigned long long)g_lastResult.errors);
    uiPrintf(9, "Mismatches : %llu", (unsigned long long)g_lastResult.mismatches);
    if (!g_lastResult.detail.empty()) uiPrintf(11, "%s", g_lastResult.detail.c_str());
    if (!g_resultAction.empty()) uiPrintf(13, "%s", g_resultAction.c_str());
    uiPrintf(17, "A : Continue");
    consoleUpdate(nullptr);
}

'''
s = s[:start] + new_result + s[end:]

# 7) Reset confirmation uses the same action panels.
old_reset = '''    if (g_resetConfirm) {
        std::printf("\\x1b[1;1H\\x1b[31mReset ALL wizard progress?\\x1b[0m\\n\\n");
        std::printf("[A] Yes, reset   [B] Cancel\\n");
        consoleUpdate(nullptr);
        return;
    }
'''
new_reset = '''    if (g_resetConfirm) {
        uiPrintf(1, "\\x1b[1;31mReset ALL wizard progress?\\x1b[0m");
        uiPrintf(4, "A : Yes, reset");
        uiPrintf(5, "B : Cancel");
        consoleUpdate(nullptr);
        return;
    }
'''
if old_reset not in s:
    raise SystemExit('reset prompt block not found')
s = s.replace(old_reset, new_reset, 1)

# 8) Subtle active-step pulse (~1.2 s). It only redraws the UI; tuning state is untouched.
old_loop = '''    bool redraw = true;
    while (appletMainLoop()) {
        padUpdate(&pad);
        const u64 k = padGetButtonsDown(&pad);

        if (redraw) {
'''
new_loop = '''    bool redraw = true;
    int guiPulseTicks = 0;
    while (appletMainLoop()) {
        padUpdate(&pad);
        const u64 k = padGetButtonsDown(&pad);
        if (++guiPulseTicks >= 60) {
            guiPulseTicks = 0;
            g_guiPulse = !g_guiPulse;
            redraw = true;
        }

        if (redraw) {
'''
if old_loop not in s:
    raise SystemExit('main redraw loop block not found')
s = s.replace(old_loop, new_loop, 1)

p.write_text(s)

m = Path('Makefile')
ms = m.read_text()
old_version = 'APP_VERSION := 0.4.0-beta.42'
if old_version not in ms:
    raise SystemExit('Makefile beta42 version not found')
ms = ms.replace(old_version, 'APP_VERSION := 1.0.0-beta', 1)
m.write_text(ms)

print('v1 GUI patch applied')
