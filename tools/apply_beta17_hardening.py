from pathlib import Path
import re

p = Path('source/main.cpp')
s = p.read_text()

def replace_once(old, new):
    global s
    if old not in s:
        raise SystemExit('pattern not found:\n' + old[:220])
    s = s.replace(old, new, 1)

# 1) Migrate old manual VMIN states into beta16's automatic scan safely.
old = '''    if (g.lowVminGood < LOW_VMIN_MIN_MV) g.lowVminGood = LOW_VMIN_MIN_MV;\n    if (g.lowVminTest < LOW_VMIN_MIN_MV) g.lowVminTest = LOW_VMIN_MIN_MV;\n    if (!g.ramDetected && g.stage == Stage::Preparation) g.stage = Stage::HardwareDetection;\n    return true;'''
new = '''    if (g.lowVminGood < LOW_VMIN_MIN_MV) g.lowVminGood = LOW_VMIN_MIN_MV;\n    if (g.lowVminTest < LOW_VMIN_MIN_MV) g.lowVminTest = LOW_VMIN_MIN_MV;\n    if (!g.ramDetected && g.stage == Stage::Preparation) g.stage = Stage::HardwareDetection;\n\n    // States written by beta.15 used a manual 510->1020 MHz sweep. If an old\n    // state is resumed in the middle/end of that flow, restart at beta.16+'s\n    // automatic scan instead of entering plateau validation with empty data.\n    const bool legacyVminState =\n        g.stage == Stage::LowVminSweep612 || g.stage == Stage::LowVminSweep714 ||\n        g.stage == Stage::LowVminValidate816 || g.stage == Stage::LowVminSweep918 ||\n        g.stage == Stage::LowVminValidate1020 ||\n        (g.stage == Stage::LowVminFinalLong && g.vminValidateCount == 0);\n    if (legacyVminState) {\n        g.stage = Stage::LowVminLong;\n        g.stageReadyAfterBoot = true;\n        g.pendingConfigMask = Config_None;\n        g.vminObsMask = 0;\n        g.vminValidateCount = 0;\n        g.vminValidateIndex = 0;\n        g.lastProbeHz = 0;\n        g.lastProbeMv = 0;\n        for (int i = 0; i < 6; ++i) {\n            g.vminObsMv[i] = 0;\n            g.vminValidateHz[i] = 0;\n            g.vminValidateMv[i] = 0;\n        }\n    }\n    return true;'''
replace_once(old, new)

# 2) Hardware detection on upgrades must not overwrite RAM tuning that already started.
old = '''bool detectRamHardware() {\n    g_hardware = HocMonHardware{};\n    g_hardwareReadRc = hocmonGetHardware(&g_hardware);\n    if (R_FAILED(g_hardwareReadRc)) return false;\n    const RamProfile p = ramProfileForId(g_hardware.dramId);\n    // Icosa = Erista/V1, outside this Mariko Battery guide.\n    if (!p.known || g_hardware.consoleType == 0) return false;\n    g.dramId = g_hardware.dramId;\n    g.consoleType = (int)g_hardware.consoleType;\n    g.vddqStartMv = p.vddqStartMv;\n    g.ramDetected = true;\n    g.vddqGood = g.vddqStartMv;\n    g.vddqTest = g.vddqStartMv - VDDQ_STEP_MV;\n    saveState();\n    return true;\n}'''
new = '''bool ramTuningAlreadyStarted(Stage st) {\n    switch (st) {\n        case Stage::VddqQuick:\n        case Stage::VddqLong:\n        case Stage::Vdd2Quick:\n        case Stage::Vdd2Long:\n        case Stage::RamBoostValidate:\n        case Stage::Ram1331Validate:\n        case Stage::HighUvQuick:\n        case Stage::HighUvLong:\n        case Stage::BoostCpuRamValidate:\n        case Stage::NormalMatrixValidate:\n        case Stage::NormalMemValidate:\n        case Stage::NormalGpuValidate:\n        case Stage::BoostMatrixValidate:\n        case Stage::BoostMemValidate:\n        case Stage::BoostCpuMemValidate:\n        case Stage::RealWorldValidate:\n        case Stage::Complete:\n            return true;\n        default:\n            return false;\n    }\n}\n\nbool detectRamHardware() {\n    g_hardware = HocMonHardware{};\n    g_hardwareReadRc = hocmonGetHardware(&g_hardware);\n    if (R_FAILED(g_hardwareReadRc)) return false;\n    const RamProfile p = ramProfileForId(g_hardware.dramId);\n    // Icosa = Erista/V1, outside this Mariko Battery guide.\n    if (!p.known || g_hardware.consoleType == 0) return false;\n    const bool keepExistingRamTune = ramTuningAlreadyStarted(g.stage);\n    g.dramId = g_hardware.dramId;\n    g.consoleType = (int)g_hardware.consoleType;\n    g.vddqStartMv = p.vddqStartMv;\n    g.ramDetected = true;\n    if (!keepExistingRamTune) {\n        g.vddqGood = g.vddqStartMv;\n        g.vddqTest = g.vddqStartMv - VDDQ_STEP_MV;\n    }\n    saveState();\n    return true;\n}'''
replace_once(old, new)

# Run detection for old states too; only new users are shown the dedicated screen.
old = '''    // First beta16 start: identify Mariko DRAM before Preparation.\n    if (g.stage == Stage::HardwareDetection && !g.ramDetected)\n        detectRamHardware();'''
new = '''    // Identify Mariko DRAM on every upgraded state that does not have it yet.\n    // New users remain on the dedicated Hardware Detection page; progressed\n    // users are enriched silently without losing already-tuned RAM values.\n    if (!g.ramDetected)\n        detectRamHardware();'''
replace_once(old, new)

# 3) Known PASS must never advance past a persistent setting that is not actually set.
old = '''        } else if (k & HidNpadButton_Plus) {\n            if (isVminSweepStage(g.stage)) {\n                runAutomaticVminScan();\n            } else {\n                stress::Kind skipKind;\n                int skipSeconds = 0;\n                if (testPlan(g.stage, skipKind, skipSeconds) || activeConfigMask() != Config_None) {\n                    g_manualPass = true;\n                    handlePass();\n                    g_manualPass = false;\n                }\n            }\n            redraw = true;'''
new = '''        } else if (k & HidNpadButton_Plus) {\n            if (isVminSweepStage(g.stage)) {\n                runAutomaticVminScan();\n            } else {\n                const u32 cfgMask = activeConfigMask();\n                stress::Kind skipKind;\n                int skipSeconds = 0;\n                if (cfgMask != Config_None) {\n                    // KNOWN PASS skips the reboot/stress validation, not the\n                    // requirement to actually have the requested HOC value set.\n                    if (verifyPersistentSettings(cfgMask)) {\n                        g_manualPass = true;\n                        handlePass();\n                        g_manualPass = false;\n                    } else {\n                        g_configPrompt = true;\n                    }\n                } else if (testPlan(g.stage, skipKind, skipSeconds)) {\n                    g_manualPass = true;\n                    handlePass();\n                    g_manualPass = false;\n                }\n            }\n            redraw = true;'''
replace_once(old, new)

# 4) Preparation mismatch page: show every wrong field compactly instead of hiding most of them.
start = s.find('void renderConfigPrompt() {')
end = s.find('\nvoid renderRebootConfirm() {', start)
if start < 0 or end < 0:
    raise SystemExit('renderConfigPrompt block not found')
replacement = r'''const char* cpuTableLabel(int table) {
    switch (table) {
        case 1: return "Default";
        case 2: return "1581 Tbreak";
        case 3: return "1683 Tbreak";
        case 4: return "Extreme UV";
        default: return "Unknown";
    }
}

void printCompactWrong(int& row, const char* label, const std::string& required, const std::string& current) {
    uiPrintf(row++, "%s", label);
    uiPrintf(row++, " Req:%s  Cur:%s  \x1b[31mWRONG\x1b[0m", required.c_str(), current.c_str());
}

void renderConfigPrompt() {
    consoleClear();
    uiPrintf(1, "\x1b[31mBattery Wizard - SETTING NOT READY\x1b[0m");
    uiPrintf(2, "Step : %s", compactStepName(g.stage));
    uiPrintf(3, "----------------------------------------");
    if (!g_configCheck.readOk) {
        uiPrintf(5, "Could not read Horizon OC settings");
        uiPrintf(6, "Result : 0x%08X", g_configCheck.rc);
        uiPrintf(9, "A : Check again");
        uiPrintf(10, "B : Back");
        consoleUpdate(nullptr);
        return;
    }

    const u32 m = g_configCheck.mask;
    int row = 5;
    if (m & Config_Prepare) {
        uiPrintf(row++, "Fix these Preparation values:");
        row++;
        if (g_configCheck.current.uncappedClocks)
            printCompactWrong(row, "General - Uncapped Clocks", "OFF", "ON");
        if (g_configCheck.current.hpMode)
            printCompactWrong(row, "RAM - HP Mode", "OFF", "ON");
        if (g_configCheck.current.ramMaxKHz != 1600000U)
            printCompactWrong(row, "RAM - Max", "1600MHz", std::to_string(g_configCheck.current.ramMaxKHz / 1000U) + "MHz");
        if (g_configCheck.current.vdd2Uv != (u32)STOCK_VDD2_UV)
            printCompactWrong(row, "RAM - VDD2", formatVdd2(STOCK_VDD2_UV), formatVdd2((int)g_configCheck.current.vdd2Uv));
        if (g_configCheck.current.vddqUv != (u32)g.vddqStartMv * 1000U)
            printCompactWrong(row, "RAM - VDDQ", formatMv(g.vddqStartMv), formatMv((int)(g_configCheck.current.vddqUv / 1000U)));
        if (g_configCheck.current.cpuMaxKHz != 1963500U)
            printCompactWrong(row, "CPU - Max", "1963MHz", std::to_string(g_configCheck.current.cpuMaxKHz / 1000U) + "MHz");
        if (g_configCheck.current.lowVminMv != STOCK_LOW_VMIN_MV)
            printCompactWrong(row, "CPU - Low VMIN", formatMv(STOCK_LOW_VMIN_MV), formatMv(g_configCheck.current.lowVminMv));
        if (g_configCheck.current.highVminMv != STOCK_HIGH_VMIN_MV)
            printCompactWrong(row, "CPU - High VMIN", formatMv(STOCK_HIGH_VMIN_MV), formatMv(g_configCheck.current.highVminMv));
        if (g_configCheck.current.tableConf != 3)
            printCompactWrong(row, "CPU - UV Table", "1683 Tbreak", cpuTableLabel(g_configCheck.current.tableConf));
        if (g_configCheck.current.lowUv != STOCK_LOW_UV)
            printCompactWrong(row, "CPU - Low UV", "0", std::to_string(g_configCheck.current.lowUv));
        if (g_configCheck.current.highUv != STOCK_HIGH_UV)
            printCompactWrong(row, "CPU - High UV", "0", std::to_string(g_configCheck.current.highUv));
        if (g_configCheck.current.cpuBoostKHz != 1785000U)
            printCompactWrong(row, "HOC Toolkit - CPU Boost", "1785MHz", std::to_string(g_configCheck.current.cpuBoostKHz / 1000U) + "MHz");
    } else if (m & Config_LowUv) {
        printSingleConfigCheck(row, "CPU Low UV", std::to_string(targetLowUv()), std::to_string(g_configCheck.current.lowUv), g_configCheck.current.lowUv == targetLowUv());
        row += 5;
    } else if (m & Config_LowVmin) {
        printSingleConfigCheck(row, "CPU Low VMIN", formatMv(targetLowVmin()), formatMv(g_configCheck.current.lowVminMv), g_configCheck.current.lowVminMv == targetLowVmin());
        row += 5;
    } else if ((m & Config_Vddq) && (m & Config_Vdd2)) {
        printSingleConfigCheck(row, "RAM VDDQ", formatMv(targetVddqMv()), formatMv((int)(g_configCheck.current.vddqUv / 1000U)), g_configCheck.current.vddqUv == (u32)targetVddqMv() * 1000U);
        row += 5;
        printSingleConfigCheck(row, "RAM VDD2", formatVdd2(targetVdd2Uv()), formatVdd2((int)g_configCheck.current.vdd2Uv), g_configCheck.current.vdd2Uv == (u32)targetVdd2Uv());
        row += 5;
    } else if (m & Config_Vddq) {
        printSingleConfigCheck(row, "RAM VDDQ", formatMv(targetVddqMv()), formatMv((int)(g_configCheck.current.vddqUv / 1000U)), g_configCheck.current.vddqUv == (u32)targetVddqMv() * 1000U);
        row += 5;
    } else if (m & Config_Vdd2) {
        printSingleConfigCheck(row, "RAM VDD2", formatVdd2(targetVdd2Uv()), formatVdd2((int)g_configCheck.current.vdd2Uv), g_configCheck.current.vdd2Uv == (u32)targetVdd2Uv());
        row += 5;
    } else if (m & Config_HighUv) {
        printSingleConfigCheck(row, "CPU High UV", std::to_string(targetHighUv()), std::to_string(g_configCheck.current.highUv), g_configCheck.current.highUv == targetHighUv());
        row += 5;
    }
    uiPrintf(row + 1, "Fix \x1b[31mWRONG\x1b[0m values in Horizon OC.");
    uiPrintf(row + 3, "A : Check again");
    uiPrintf(row + 4, "B : Back");
    consoleUpdate(nullptr);
}
'''
s = s[:start] + replacement + s[end:]

p.write_text(s)

mk = Path('Makefile').read_text()
mk = re.sub(r'APP_VERSION := .*', 'APP_VERSION := 0.4.0-beta.17', mk)
Path('Makefile').write_text(mk)

Path('UPDATE.txt').write_text(
    'version=0.4.0-beta.17\n'
    'nro_url=https://github.com/retrotendo/HOC-Undervolting-Wizard/releases/download/v0.4.0-beta.17/HOC-Undervolting-Wizard.nro\n'
    'sha_url=https://github.com/retrotendo/HOC-Undervolting-Wizard/releases/download/v0.4.0-beta.17/HOC-Undervolting-Wizard.nro.sha256\n'
)

Path('RELEASE_NOTES_v0.4.0-beta.17.md').write_text('''# HOC Undervolting Wizard v0.4.0-beta.17\n\nThis beta hardens the new hardware-aware/reboot/automatic VMIN workflow introduced in beta.16.\n\n## Fixes\n\n- Old beta.15 manual VMIN sweep states migrate back into the automatic 510->1020 MHz scan instead of entering plateau validation with empty observations.\n- RAM is detected for upgraded in-progress states too. If RAM tuning already started, detection records the module/baseline without overwriting the user's tuned VDDQ values.\n- `KNOWN PASS / SKIP` can no longer silently advance a persistent-setting step while Horizon OC still contains the wrong value. The value is verified first; if it is wrong, the Required/Current screen is shown. A correct known value may still skip reboot/stress validation.\n- Preparation mismatch reporting now lists every incorrect Horizon OC/HOC Toolkit value compactly with Required, Current and red WRONG status.\n\n## Retained beta.16 workflow\n\n- automatic RAM detection and 600/640 mV VDDQ baseline\n- green setting confirmation before user-confirmed system reboot\n- boot-normal confirmation after restart\n- fully automatic Temporary Override CPU voltage scan at 510/612/714/816/918/1020 MHz\n- visible scan/sample progress\n- automatic restoration of previous Temporary Overrides\n- voltage-region grouping and 1-hour validation at the highest clock of every region\n\nThis remains a pre-release pending real-hardware validation.\n''')

print('beta17 hardening applied')
