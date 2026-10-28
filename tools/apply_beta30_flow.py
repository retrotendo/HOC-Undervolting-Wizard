from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def find_func_span(text: str, signature: str):
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f"signature not found: {signature}")
    brace = text.find('{', start + len(signature))
    if brace < 0:
        raise RuntimeError(f"opening brace not found: {signature}")
    depth = 0
    i = brace
    state = 'code'
    while i < len(text):
        c = text[i]
        n = text[i + 1] if i + 1 < len(text) else ''
        if state == 'code':
            if c == '"': state = 'str'
            elif c == "'": state = 'char'
            elif c == '/' and n == '/': state = 'line'; i += 1
            elif c == '/' and n == '*': state = 'block'; i += 1
            elif c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return start, i + 1
        elif state == 'str':
            if c == '\\': i += 1
            elif c == '"': state = 'code'
        elif state == 'char':
            if c == '\\': i += 1
            elif c == "'": state = 'code'
        elif state == 'line':
            if c == '\n': state = 'code'
        elif state == 'block':
            if c == '*' and n == '/': state = 'code'; i += 1
        i += 1
    raise RuntimeError(f"unterminated function: {signature}")


def replace_func(text: str, signature: str, replacement: str):
    a, b = find_func_span(text, signature)
    return text[:a] + replacement.rstrip() + text[b:]


def replace_once(text: str, old: str, new: str):
    if old not in text:
        raise RuntimeError('replace target not found:\n' + old[:240])
    if text.count(old) != 1:
        raise RuntimeError(f'replace target count={text.count(old)} expected 1')
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Horizon OC IPC: add a narrow 2.5.1 writer for Low UV / Low VMIN.
# ---------------------------------------------------------------------------
h = ROOT / 'source/hoc_monitor.h'
text = h.read_text()
needle = 'Result hocmonApplyPreparation251(const HocMonConfig* desired);\n\n'
insert = '''Result hocmonApplyPreparation251(const HocMonConfig* desired);\n\n/*\n * Horizon OC 2.5.1 only: update CPU Low UV and/or Low VMIN through the\n * same SetConfigValues + SetKipData path used by Horizon OC itself.\n * fieldsMask bit0 = Low UV, bit1 = Low VMIN.\n */\nResult hocmonApplyCpuLow251(int lowUv, int lowVminMv, u32 fieldsMask);\n\n'''
text = replace_once(text, needle, insert)
h.write_text(text)

c = ROOT / 'source/hoc_monitor.c'
text = c.read_text()
insert_before = 'Result hocmonGetConfigDebug(HocMonConfigDebug* out)\n'
if insert_before not in text:
    raise RuntimeError('hocmonGetConfigDebug insertion point missing')
helper = r'''Result hocmonApplyCpuLow251(int lowUv, int lowVminMv, u32 fieldsMask)
{
    if ((fieldsMask & 3U) == 0)
        return 1;

    Service srv = {0};
    u32 api = 0;
    Result rc = hocmonOpen(&srv, &api);
    if (R_FAILED(rc))
        return rc;
    if (api < HOCCLK_API_VERSION_REQUIRED) {
        serviceClose(&srv);
        return 2;
    }

    HocMonRawConfig cfg;
    memset(&cfg, 0, sizeof(cfg));
    rc = serviceDispatch(&srv, HOCCLK_IPC_CMD_GET_CONFIG_VALUES,
        .buffer_attrs = { SfBufferAttr_HipcAutoSelect | SfBufferAttr_Out },
        .buffers = {{ &cfg, sizeof(cfg) }},
    );
    if (R_FAILED(rc)) {
        serviceClose(&srv);
        return rc;
    }

    if ((u32)cfg.values[CFG251_KIP_VERSION] != 251U) {
        serviceClose(&srv);
        return 4;
    }

    if (fieldsMask & 1U)
        cfg.values[CFG251_CPU_LOW_UV] = (u64)lowUv;
    if (fieldsMask & 2U)
        cfg.values[CFG251_CPU_LOW_VMIN_MV] = (u64)lowVminMv;

    rc = serviceDispatch(&srv, HOCCLK_IPC_CMD_SET_CONFIG_VALUES,
        .buffer_attrs = { SfBufferAttr_HipcAutoSelect | SfBufferAttr_In },
        .buffers = {{ &cfg, sizeof(cfg) }},
    );
    if (R_SUCCEEDED(rc)) {
        const u32 dummy = 0;
        rc = serviceDispatchIn(&srv, HOCCLK_IPC_CMD_SET_KIP_DATA, dummy);
    }

    serviceClose(&srv);
    return rc;
}

'''
text = text.replace(insert_before, helper + insert_before, 1)
c.write_text(text)

# ---------------------------------------------------------------------------
# Main wizard flow.
# ---------------------------------------------------------------------------
p = ROOT / 'source/main.cpp'
text = p.read_text()
text = replace_once(text, 'constexpr int LOW_VMIN_STEP_MV = 5;', 'constexpr int LOW_VMIN_STEP_MV = 10;')
text = replace_once(text,
    'bool g_autoPrepConfirm = false;\nstd::string g_autoPrepError;\nbool g_bootPrompt = false;',
    'bool g_autoPrepConfirm = false;\nu32 g_autoSetMask = Config_Prepare;\nstd::string g_autoPrepError;\nbool g_bootPrompt = false;\nbool g_scanForLowUv = false;')

# Names now reflect boot-limit discovery followed by automatic region validation.
for old, new in [
    ('case Stage::LowUvQuick: return "CPU Low UV - 1 Min Search";', 'case Stage::LowUvQuick: return "CPU Low UV - Boot Search";'),
    ('case Stage::LowUvValidateQuick: return "CPU Low UV - Legacy Quick Validation";', 'case Stage::LowUvValidateQuick: return "CPU Low UV - Region Validation";'),
    ('case Stage::LowUvLong: return "CPU Low UV - 1 Hour Validation";', 'case Stage::LowUvLong: return "CPU Low UV - Voltage Scan";'),
    ('case Stage::LowVminQuick: return "CPU Low VMIN - Quick Search @ 510";', 'case Stage::LowVminQuick: return "CPU Low VMIN - Boot Search";'),
    ('case Stage::LowVminPlateauValidate: return "CPU Low VMIN - Plateau Validation";', 'case Stage::LowVminPlateauValidate: return "CPU Low VMIN - Region Validation";'),
    ('case Stage::LowUvQuick: return "CPU Low UV - 1 Min Search";', 'case Stage::LowUvQuick: return "CPU Low UV - Boot Search";'),
    ('case Stage::LowUvValidateQuick: return "CPU Low UV - Legacy Quick Test";', 'case Stage::LowUvValidateQuick: return "CPU Low UV - Region Test";'),
    ('case Stage::LowUvLong: return "CPU Low UV - Validate";', 'case Stage::LowUvLong: return "CPU Low UV - Voltage Scan";'),
]:
    if old in text:
        text = text.replace(old, new, 1)

text = replace_func(text, 'bool testPlan(Stage s, stress::Kind& kind, int& seconds)', r'''bool testPlan(Stage s, stress::Kind& kind, int& seconds) {
    switch (s) {
        case Stage::HighUvQuick:
            kind = stress::Kind::Cpu; seconds = 60; return true;
        case Stage::LowVminFinalLong:
        case Stage::HighUvLong:
        case Stage::NormalMatrixValidate:
        case Stage::BoostMatrixValidate:
            kind = stress::Kind::Cpu; seconds = 3600; return true;
        case Stage::VddqQuick:
        case Stage::Vdd2Quick:
            kind = stress::Kind::Ram; seconds = 60; return true;
        case Stage::VddqLong:
        case Stage::Vdd2Long:
        case Stage::RamBoostValidate:
        case Stage::Ram1331Validate:
        case Stage::NormalMemValidate:
        case Stage::BoostMemValidate:
            kind = stress::Kind::Ram; seconds = 3600; return true;
        case Stage::BoostCpuRamValidate:
        case Stage::BoostCpuMemValidate:
            kind = stress::Kind::Combined; seconds = 3600; return true;
        case Stage::NormalGpuValidate:
            kind = stress::Kind::Gpu; seconds = 3600; return true;
        default:
            return false;
    }
}''')

text = replace_func(text, 'u32 defaultConfigMaskForStage(Stage st)', r'''u32 defaultConfigMaskForStage(Stage st) {
    switch (st) {
        case Stage::Preparation: return Config_Prepare;
        case Stage::LowUvQuick:
        case Stage::LowUvLong: return Config_LowUv;
        case Stage::LowVminQuick:
        case Stage::LowVminLong: return Config_LowVmin;
        case Stage::VddqQuick:
        case Stage::VddqLong: return Config_Vddq;
        case Stage::Vdd2Quick:
        case Stage::Vdd2Long: return Config_Vdd2;
        case Stage::HighUvQuick:
        case Stage::HighUvLong: return Config_HighUv;
        default: return Config_None;
    }
}''')

# Preparation auto-write must stop at the reboot confirmation page instead of rebooting immediately.
old = '''    resetPreparationBaselineState();\n    g.pendingConfigMask = Config_Prepare;\n    g.rebootPending = true;\n    saveState();\n    return true;'''
new = '''    resetPreparationBaselineState();\n    g.pendingConfigMask = Config_Prepare;\n    g.rebootPending = false;\n    saveState();\n    return true;'''
text = replace_once(text, old, new)

# Generic CPU auto writer used by the Preparation check and Low UV / Low VMIN pages.
marker = 'bool preparationFixedSettingsMatch(const HocMonConfig& c) {'
if marker not in text:
    raise RuntimeError('preparationFixedSettingsMatch marker missing')
auto_helper = r'''bool applyAutomaticCurrentSetting(u32 mask) {
    g_autoPrepError.clear();
    if (mask & Config_Prepare)
        return applyAutomaticPreparation();

    u32 hocMask = 0;
    if (mask & Config_LowUv) hocMask |= 1U;
    if (mask & Config_LowVmin) hocMask |= 2U;
    if (!hocMask) {
        g_autoPrepError = "Automatic setting is not available for this step yet.";
        return false;
    }

    const Result rc = hocmonApplyCpuLow251(targetLowUv(), targetLowVmin(), hocMask);
    if (R_FAILED(rc)) {
        if (rc == 4)
            g_autoPrepError = "Automatic setting currently supports Horizon OC 2.5.1 only.";
        else {
            char msg[96];
            std::snprintf(msg, sizeof(msg), "Horizon OC Save KIP failed: 0x%08X", rc);
            g_autoPrepError = msg;
        }
        return false;
    }

    svcSleepThread(150'000'000);
    if (!verifyPersistentSettings(mask)) {
        g_autoPrepError = "Readback did not match the requested value.";
        return false;
    }
    g.pendingConfigMask = mask;
    saveState();
    return true;
}

'''
text = text.replace(marker, auto_helper + marker, 1)

# Boot inference uses the actually active persisted value after reopening the Wizard.
marker = 'void renderBootPrompt() {'
if marker not in text:
    raise RuntimeError('renderBootPrompt marker missing')
boot_helpers = r'''enum class BootInference { Unknown, RequestedActive, SaferActive };

BootInference inferBootState(int* activeValue = nullptr) {
    HocMonConfig c{};
    if (!readHocConfigIni(c)) return BootInference::Unknown;

    if (g.stage == Stage::Preparation)
        return configMatchesCurrent(Config_Prepare, c) ? BootInference::RequestedActive : BootInference::Unknown;

    if (g.stage == Stage::LowUvQuick) {
        if (activeValue) *activeValue = c.lowUv;
        if (c.lowUv == g.lowUvTest) return BootInference::RequestedActive;
        if (c.lowUv < g.lowUvTest && c.lowUv <= g.lowUvGood) return BootInference::SaferActive;
        return BootInference::Unknown;
    }
    if (g.stage == Stage::LowVminQuick) {
        if (activeValue) *activeValue = c.lowVminMv;
        if (c.lowVminMv == g.lowVminTest) return BootInference::RequestedActive;
        if (c.lowVminMv > g.lowVminTest && c.lowVminMv >= g.lowVminGood) return BootInference::SaferActive;
        return BootInference::Unknown;
    }

    const u32 mask = g.pendingConfigMask ? g.pendingConfigMask : defaultConfigMaskForStage(g.stage);
    return mask != Config_None && configMatchesCurrent(mask, c)
        ? BootInference::RequestedActive : BootInference::Unknown;
}

'''
text = text.replace(marker, boot_helpers + marker, 1)

text = replace_func(text, 'void renderBootPrompt()', r'''void renderBootPrompt() {
    consoleClear();
    uiPrintf(1, "\x1b[36mBattery Wizard - BOOT CHECK\x1b[0m");
    uiPrintf(3, "----------------------------------------");

    int active = 0;
    const BootInference state = inferBootState(&active);
    int row = 5;
    if (g.stage == Stage::LowUvQuick) {
        uiPrintf(row++, "Requested Low UV : %d", g.lowUvTest);
        uiPrintf(row++, "Active Low UV    : %d", active);
    } else if (g.stage == Stage::LowVminQuick) {
        uiPrintf(row++, "Requested VMIN   : %d mV", g.lowVminTest);
        uiPrintf(row++, "Active VMIN      : %d mV", active);
    }
    row++;

    if (state == BootInference::RequestedActive) {
        uiPrintf(row++, "\x1b[32mRequested value is active.\x1b[0m");
        uiPrintf(row++, "The console appears to have booted with it.");
        row++;
        uiPrintf(row++, "Only continue if normal CFW booted AND:");
        uiPrintf(row++, " - no system freeze");
        uiPrintf(row++, " - no crash");
        uiPrintf(row++, " - no spontaneous reboot/system failure");
        row += 2;
        uiPrintf(row++, "A : Stable boot - continue");
        uiPrintf(row++, "X : Not stable / crashed / froze");
    } else if (state == BootInference::SaferActive) {
        uiPrintf(row++, "\x1b[33mA safer previous value is active.\x1b[0m");
        uiPrintf(row++, "The attempted value did not remain active.");
        uiPrintf(row++, "That makes the active previous value the candidate.");
        row += 2;
        uiPrintf(row++, "A : Continue with this candidate");
    } else {
        uiPrintf(row++, "\x1b[31mCould not confirm the expected active value.\x1b[0m");
        uiPrintf(row++, "Check Horizon OC / recovery state first.");
        row += 2;
        uiPrintf(row++, "A : Check again");
        uiPrintf(row++, "X : Treat as unstable and recover");
    }
    uiPrintf(row + 1, "B : Exit and decide later");
    consoleUpdate(nullptr);
}''')

# Add automatic option on wrong-value screens.
old = '''    uiPrintf(row + 1, "Fix \\x1b[31mWRONG\\x1b[0m values in Horizon OC.");\n    uiPrintf(row + 3, "A : Check again");\n    if (g.stage == Stage::Preparation) {\n        uiPrintf(row + 4, "X : Use current settings as baseline");\n        uiPrintf(row + 5, "B : Back");\n    } else {\n        uiPrintf(row + 4, "B : Back");\n    }'''
new = '''    uiPrintf(row + 1, "Fix \\x1b[31mWRONG\\x1b[0m values in Horizon OC.");\n    uiPrintf(row + 3, "A : Check again");\n    if (m & (Config_Prepare | Config_LowUv | Config_LowVmin))\n        uiPrintf(row + 4, "Y : Set required value(s) automatically");\n    if (g.stage == Stage::Preparation) {\n        uiPrintf(row + 5, "X : Use current settings as baseline");\n        uiPrintf(row + 6, "B : Back");\n    } else {\n        uiPrintf(row + 5, "B : Back");\n    }'''
text = replace_once(text, old, new)

text = replace_func(text, 'void renderAutoPrepConfirm()', r'''void renderAutoPrepConfirm() {
    consoleClear();
    uiPrintf(1, "\x1b[36mBattery Wizard\x1b[0m");
    uiPrintf(2, "Step : Automatic Setting");
    uiPrintf(3, "----------------------------------------");
    if (g_autoSetMask & Config_Prepare)
        uiPrintf(5, "Set all required Preparation values automatically?");
    else if (g_autoSetMask & Config_LowUv)
        uiPrintf(5, "Set CPU Low UV %d automatically?", targetLowUv());
    else if (g_autoSetMask & Config_LowVmin)
        uiPrintf(5, "Set CPU Low VMIN %d mV automatically?", targetLowVmin());
    uiPrintf(7, "Uses Horizon OC SetConfigValues + Save KIP.");
    uiPrintf(8, "Unrelated Horizon OC values stay unchanged.");
    uiPrintf(10, "Horizon OC 2.5.1 is required.");
    uiPrintf(12, "The value is read back before reboot is offered.");
    if (!g_autoPrepError.empty())
        uiPrintf(15, "\x1b[31m%s\x1b[0m", g_autoPrepError.c_str());
    uiPrintf(20, "A : Confirm - set value(s)");
    uiPrintf(21, "B : Cancel");
    consoleUpdate(nullptr);
}''')

text = replace_func(text, 'void renderRebootConfirm()', r'''void renderRebootConfirm() {
    consoleClear();
    uiPrintf(1, "\x1b[36mBattery Wizard\x1b[0m");
    uiPrintf(2, "Step : %s", compactStepName(g.stage));
    uiPrintf(3, "----------------------------------------");
    const u32 m = g_configCheck.mask;
    if (m & Config_Prepare)
        uiPrintf(5, "\x1b[32mPreparation values are saved and verified.\x1b[0m");
    else if (m & Config_LowUv)
        uiPrintf(5, "\x1b[32mLow UV %d is saved and verified.\x1b[0m", targetLowUv());
    else if (m & Config_LowVmin)
        uiPrintf(5, "\x1b[32mLow VMIN %d mV is saved and verified.\x1b[0m", targetLowVmin());
    else
        uiPrintf(5, "\x1b[32mRequested setting is saved and verified.\x1b[0m");

    uiPrintf(7, "A reboot is required to apply the KIP value.");
    uiPrintf(8, "After normal CFW boots, open this Wizard again.");
    uiPrintf(10, "\x1b[33mIf normal CFW does not boot, freezes or crashes:\x1b[0m");
    uiPrintf(11, "1. Boot Hekate.");
    uiPrintf(12, "2. Start CFW No OC / without hoc.kip.");
    uiPrintf(13, "3. Restore the previous safe value.");
    uiPrintf(14, "4. Reboot normal CFW.");
    uiPrintf(15, "5. Open this Wizard again.");
    uiPrintf(18, "A : Reboot now");
    uiPrintf(19, "B : Back");
    consoleUpdate(nullptr);
}''')

# Render the two CPU searches as boot-limit discovery, then scan/test voltage regions.
text = replace_func(text, 'void renderTestStage()', r'''void renderTestStage() {
    title();

    const u32 configMask = activeConfigMask();
    if (configMask != Config_None) {
        uiPrintf(5, "@ Horizon OC");
        uiPrintf(7, (configMask & (Config_Vddq | Config_Vdd2)) ? "RAM Settings:" : "CPU Settings:");
        int setRow = 8;
        if (configMask & Config_LowUv) uiPrintf(setRow++, " - Low UV   : %d", targetLowUv());
        if (configMask & Config_LowVmin) uiPrintf(setRow++, " - Low VMIN : %d mV", targetLowVmin());
        if (configMask & Config_Vddq) uiPrintf(setRow++, " - VDDQ     : %d mV", targetVddqMv());
        if (configMask & Config_Vdd2) uiPrintf(setRow++, " - VDD2     : %s", formatVdd2(targetVdd2Uv()).c_str());
        if (configMask & Config_HighUv) uiPrintf(setRow++, " - High UV  : %d", targetHighUv());
        setRow += 2;
        if (g.stage == Stage::LowUvQuick)
            uiPrintf(setRow++, "Find the highest Low UV that can boot normally.");
        else if (g.stage == Stage::LowVminQuick)
            uiPrintf(setRow++, "Lower Low VMIN in 10 mV steps until boot fails.");
        uiPrintf(setRow++, "A : Check setting");
        if (configMask & (Config_LowUv | Config_LowVmin))
            uiPrintf(setRow++, "Y : Set value automatically");
        uiPrintf(setRow++, "+ : Known PASS / Skip");
        uiPrintf(setRow++, "B : Exit    - : Reset");
        return;
    }

    int row = 5;
    if (g.recoveryNeeded) {
        uiPrintf(row++, "\x1b[33mPrevious safe value restored.\x1b[0m");
        g.recoveryNeeded = false;
        row++;
    }

    if (g.stage == Stage::LowUvLong || g.stage == Stage::LowVminLong) {
        const bool lowUv = g.stage == Stage::LowUvLong;
        uiPrintf(row++, "\x1b[32mBoot-limit candidate found.\x1b[0m");
        uiPrintf(row++, lowUv ? "CPU Low UV   : %d" : "CPU Low VMIN : %d mV",
                 lowUv ? g.lowUvGood : g.lowVminGood);
        row++;
        uiPrintf(row++, "Next the Wizard maps the CPU voltage curve at:");
        uiPrintf(row++, "510 / 612 / 714 / 816 / 918 / 1020 MHz");
        uiPrintf(row++, "and keeps only the highest frequency of each");
        uiPrintf(row++, "different voltage region for stability testing.");
        row += 2;
        uiPrintf(row++, "A : Scan voltage regions automatically");
        uiPrintf(row++, "B : Exit");
        return;
    }

    if (g.stage == Stage::LowUvValidateQuick || g.stage == Stage::LowVminPlateauValidate) {
        const bool lowUv = g.stage == Stage::LowUvValidateQuick;
        uiPrintf(row++, lowUv ? "CPU Low UV candidate : %d" : "CPU Low VMIN candidate : %d mV",
                 lowUv ? g.lowUvGood : g.lowVminGood);
        uiPrintf(row++, "Voltage regions to test : %d", g.vminValidateCount);
        row++;
        for (int i = 0; i < g.vminValidateCount && i < 6; ++i)
            uiPrintf(row++, " %d. %s @ ~%d mV", i + 1,
                     formatClock(g.vminValidateHz[i]).c_str(), g.vminValidateMv[i]);
        row++;
        uiPrintf(row++, "The Wizard will set every override automatically");
        uiPrintf(row++, "and run each listed CPU frequency for 1 minute.");
        row += 2;
        uiPrintf(row++, "A : Start automatic validation");
        uiPrintf(row++, "B : Exit");
        return;
    }

    stress::Kind kind;
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
}''')

text = replace_func(text, 'void renderVminScanScreen()', r'''void renderVminScanScreen() {
    consoleClear();
    uiPrintf(1, "\x1b[36mBattery Wizard - CPU VOLTAGE SCAN\x1b[0m");
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
    uiPrintf(7, g_scanForLowUv ? "Low UV : %d" : "Low VMIN : %d mV",
             g_scanForLowUv ? g.lowUvGood : g.lowVminGood);
    uiPrintf(8, "Different voltage regions : %d", g.vminValidateCount);
    int row = 10;
    for (int i = 0; i < g.vminValidateCount && i < 6; ++i)
        uiPrintf(row++, " %d. %s @ ~%d mV", i + 1, formatClock(g.vminValidateHz[i]).c_str(), g.vminValidateMv[i]);
    row++;
    uiPrintf(row++, "Previous overrides : %s", g_vminScanRestoreOk ? "\x1b[32mRESTORED\x1b[0m" : "\x1b[31mCHECK HOC\x1b[0m");
    row += 2;
    uiPrintf(row++, "A : Continue to automatic 1-minute tests");
    uiPrintf(row++, "B : Exit");
    consoleUpdate(nullptr);
}''')

# Generic six-frequency voltage scan and automatic region tests.
marker = 'void runAutomaticVminScan() {'
if marker not in text:
    raise RuntimeError('runAutomaticVminScan marker missing')
new_helpers = r'''bool sampleCpuVoltageAt(u32 cpuHz, int index, int total, int& outMv) {
    u32 samples[3] = {};
    int count = 0;
    for (int s = 0; s < 3; ++s) {
        consoleClear();
        uiPrintf(1, "\x1b[36mBattery Wizard - CPU VOLTAGE SCAN\x1b[0m");
        uiPrintf(3, "----------------------------------------");
        uiPrintf(5, "Frequency : %d / %d", index + 1, total);
        uiPrintf(7, "CPU       : %s", formatClock(cpuHz).c_str());
        uiPrintf(8, "GPU / RAM : 384 / 1331.2 MHz");
        uiPrintf(10, "Reading CPU voltage sample %d / 3...", s + 1);
        consoleUpdate(nullptr);
        svcSleepThread(700'000'000);

        HocMonClocks cur{};
        if (R_SUCCEEDED(hocmonGetClocks(&cur)) &&
            clockMatches(cur.overrideHz[0], cpuHz) &&
            clockMatches(cur.overrideHz[1], CLOCK_GPU_NORMAL_HZ) &&
            clockMatches(cur.overrideHz[2], CLOCK_RAM_NORMAL_HZ) &&
            clockMatches(cur.targetHz[0], cpuHz) && cur.cpuVoltageUv != 0)
            samples[count++] = cur.cpuVoltageUv;
    }
    if (count != 3) return false;
    if (samples[0] > samples[1]) std::swap(samples[0], samples[1]);
    if (samples[1] > samples[2]) std::swap(samples[1], samples[2]);
    if (samples[0] > samples[1]) std::swap(samples[0], samples[1]);
    outMv = (int)(((samples[1] + 2500U) / 5000U) * 5U);
    return true;
}

void runAutomaticVoltageScan(bool forLowUv) {
    static const u32 cpuHz[6] = {
        CLOCK_CPU_VMIN_510_HZ, CLOCK_CPU_LOW_HZ, CLOCK_CPU_VMIN_714_HZ,
        CLOCK_CPU_VMIN_MID_HZ, CLOCK_CPU_VMIN_918_HZ, CLOCK_CPU_NORMAL_HZ,
    };
    g_scanForLowUv = forLowUv;
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
    rc = hocmonSetOverride(HocMonModule_GPU, CLOCK_GPU_NORMAL_HZ);
    if (R_SUCCEEDED(rc)) rc = hocmonSetOverride(HocMonModule_MEM, CLOCK_RAM_NORMAL_HZ);
    if (R_FAILED(rc)) {
        g_vminScanErrorRc = rc;
        g_vminScanErrorText = "HOC refused an automatic Temporary Override.";
        g_vminScanRestoreOk = restoreTemporaryOverrides(before);
        g_vminScanScreen = true;
        return;
    }

    for (int i = 0; i < 6; ++i) {
        rc = hocmonSetOverride(HocMonModule_CPU, cpuHz[i]);
        if (R_FAILED(rc)) {
            g_vminScanErrorRc = rc;
            g_vminScanErrorText = "Could not switch the CPU Temporary Override.";
            break;
        }
        svcSleepThread(500'000'000);
        int mv = 0;
        if (!sampleCpuVoltageAt(cpuHz[i], i, 6, mv)) {
            g_vminScanErrorText = "Could not obtain three valid voltage samples.";
            break;
        }
        g.vminObsMv[i] = mv;
        g.vminObsMask |= (1u << i);
    }

    g_vminScanRestoreOk = restoreTemporaryOverrides(before);
    if (!g_vminScanErrorText.empty() || g.vminObsMask != 0x3FU) {
        saveState();
        g_vminScanScreen = true;
        return;
    }

    buildVminPlateaus();
    g.stage = forLowUv ? Stage::LowUvValidateQuick : Stage::LowVminPlateauValidate;
    g.stageReadyAfterBoot = true;
    g.pendingConfigMask = Config_None;
    saveState();
    g_vminScanSuccess = true;
    g_vminScanScreen = true;
}

void runAutomaticLowUvScan() {
    runAutomaticVoltageScan(true);
}

void runAutomaticRegionValidation(bool forLowUv) {
    if (g.vminValidateCount <= 0) {
        g_resultAction = "No voltage regions were available. Run the voltage scan again.";
        g_lastKind = stress::Kind::Cpu;
        g_lastResult = stress::Result{};
        g_resultScreen = true;
        return;
    }

    HocMonClocks before{};
    Result rc = hocmonGetClocks(&before);
    if (R_FAILED(rc)) {
        g_resultAction = "Could not read current HOC overrides.";
        g_lastKind = stress::Kind::Cpu;
        g_lastResult = stress::Result{};
        g_resultScreen = true;
        return;
    }

    bool failed = false;
    for (int i = 0; i < g.vminValidateCount; ++i) {
        const u32 hz = g.vminValidateHz[i];
        consoleClear();
        uiPrintf(1, "\x1b[36mBattery Wizard - AUTO CPU VALIDATION\x1b[0m");
        uiPrintf(3, "----------------------------------------");
        uiPrintf(5, "Region %d / %d", i + 1, g.vminValidateCount);
        uiPrintf(7, "CPU : %s @ ~%d mV", formatClock(hz).c_str(), g.vminValidateMv[i]);
        uiPrintf(8, "GPU : 384 MHz");
        uiPrintf(9, "RAM : 1331.2 MHz");
        uiPrintf(11, "Running built-in CPU test for 1 minute...");
        consoleUpdate(nullptr);

        rc = hocmonSetOverride(HocMonModule_CPU, hz);
        if (R_SUCCEEDED(rc)) rc = hocmonSetOverride(HocMonModule_GPU, CLOCK_GPU_NORMAL_HZ);
        if (R_SUCCEEDED(rc)) rc = hocmonSetOverride(HocMonModule_MEM, CLOCK_RAM_NORMAL_HZ);
        if (R_FAILED(rc)) {
            g_resultAction = "Automatic override setup failed. No candidate change was recorded.";
            failed = true;
            break;
        }
        svcSleepThread(500'000'000);

        HocMonClocks cur{};
        rc = hocmonGetClocks(&cur);
        if (R_FAILED(rc) || !clockMatches(cur.overrideHz[0], hz) ||
            !clockMatches(cur.overrideHz[1], CLOCK_GPU_NORMAL_HZ) ||
            !clockMatches(cur.overrideHz[2], CLOCK_RAM_NORMAL_HZ)) {
            g_resultAction = "Automatic override verification failed. No candidate change was recorded.";
            failed = true;
            break;
        }

        g.testRunning = true;
        g.testKind = static_cast<int>(stress::Kind::Cpu);
        g.testDurationSec = 60;
        g.testStage = static_cast<int>(g.stage);
        saveState();
        g_lastKind = stress::Kind::Cpu;
        g_lastResult = stress::run(stress::Kind::Cpu, 60);
        g.testRunning = false;
        g.testKind = g.testDurationSec = g.testStage = 0;
        saveState();

        if (g_lastResult.outcome != stress::Outcome::Pass) {
            failed = true;
            if (g_lastResult.outcome == stress::Outcome::Fail) {
                if (forLowUv) {
                    if (g.lowUvGood > 0) --g.lowUvGood;
                    g.stage = Stage::LowUvLong;
                    g.pendingConfigMask = Config_LowUv;
                    g_resultAction = "CPU validation failed. Low UV was reduced by one level; apply/reboot, then the Wizard will rescan.";
                } else {
                    if (g.lowVminGood < STOCK_LOW_VMIN_MV)
                        g.lowVminGood = std::min(STOCK_LOW_VMIN_MV, g.lowVminGood + LOW_VMIN_STEP_MV);
                    g.stage = Stage::LowVminLong;
                    g.pendingConfigMask = Config_LowVmin;
                    g_resultAction = "CPU validation failed. Low VMIN was raised by 10 mV; apply/reboot, then the Wizard will rescan.";
                }
                g.stageReadyAfterBoot = false;
                clearVminSweepData();
                saveState();
            } else {
                g_resultAction = "Validation was cancelled or the test engine stopped. The tuning candidate was not changed.";
            }
            break;
        }
    }

    const bool restored = restoreTemporaryOverrides(before);
    if (!failed) {
        g_lastResult.outcome = stress::Outcome::Pass;
        if (forLowUv) {
            clearVminSweepData();
            if (g.lowVminGood <= LOW_VMIN_MIN_MV) {
                g.stage = Stage::LowVminLong;
                g.stageReadyAfterBoot = true;
            } else {
                g.stage = Stage::LowVminQuick;
                g.lowVminTest = std::max(LOW_VMIN_MIN_MV, g.lowVminGood - LOW_VMIN_STEP_MV);
                g.stageReadyAfterBoot = false;
            }
            g_resultAction = "All CPU voltage regions passed. CPU Low UV is confirmed; continuing to Low VMIN boot search.";
        } else {
            clearVminSweepData();
            if (g.vddqGood <= VDDQ_MIN_MV) {
                g.stage = Stage::VddqLong;
                g.stageReadyAfterBoot = true;
            } else {
                g.stage = Stage::VddqQuick;
                g.vddqTest = g.vddqGood - VDDQ_STEP_MV;
                g.stageReadyAfterBoot = false;
            }
            g_resultAction = "All CPU voltage regions passed. CPU Low VMIN is confirmed; continuing to RAM tuning.";
        }
        g.pendingConfigMask = Config_None;
        saveState();
    }
    if (!restored) g_resultAction += " WARNING: previous Temporary Overrides could not be fully restored.";
    g_resultScreen = true;
}

'''
text = text.replace(marker, new_helpers + marker, 1)

# Old VMIN scan becomes a thin wrapper around the same six-frequency scanner.
text = replace_func(text, 'void runAutomaticVminScan()', r'''void runAutomaticVminScan() {
    runAutomaticVoltageScan(false);
}''')

# Boot-limit search no longer runs a 1-minute test for every candidate.
text = replace_once(text,
'''        case Stage::LowUvQuick:\n            // Every candidate must both boot and pass the 1-minute CPU test\n            // before it becomes the new last-known-good Low UV value.\n            g.lowUvGood = g.lowUvTest;''',
'''        case Stage::LowUvQuick:\n            // Boot-stable candidate confirmed by the post-reboot check.\n            g.lowUvGood = g.lowUvTest;''')
text = replace_once(text,
'''            if (g.lowUvTest >= LOW_UV_MAX) {\n                g.stage = Stage::LowUvLong;\n                g.stageReadyAfterBoot = true;\n            } else {''',
'''            if (g.lowUvTest >= LOW_UV_MAX) {\n                g.stage = Stage::LowUvLong;\n                g.stageReadyAfterBoot = true;\n            } else {''')

# Low UV / Low VMIN validation failures always back off the same parameter.
old = '''        case Stage::LowUvValidateQuick:\n            if (g.lowUvGood > 0) --g.lowUvGood;\n            g.recoveryNeeded = false;\n            g.pendingConfigMask = Config_LowUv;\n            break;'''
new = '''        case Stage::LowUvValidateQuick:\n            if (g.lowUvGood > 0) --g.lowUvGood;\n            g.stage = Stage::LowUvLong;\n            g.recoveryNeeded = false;\n            g.pendingConfigMask = Config_LowUv;\n            break;'''
text = replace_once(text, old, new)

# Replace the old plateau fallback (which could change Low UV) with a pure VMIN +10 mV backoff.
a, b = find_func_span(text, 'void handleFail(bool didNotBoot)')
block = text[a:b]
start = block.find('        case Stage::LowVminPlateauValidate: {')
end = block.find('        case Stage::VddqQuick:', start)
if start < 0 or end < 0:
    raise RuntimeError('LowVminPlateauValidate fail block not found')
replacement = '''        case Stage::LowVminPlateauValidate:\n            if (g.lowVminGood < STOCK_LOW_VMIN_MV)\n                g.lowVminGood = std::min(STOCK_LOW_VMIN_MV, g.lowVminGood + LOW_VMIN_STEP_MV);\n            g.stage = Stage::LowVminLong;\n            g.pendingConfigMask = Config_LowVmin;\n            clearVminSweepData();\n            break;\n'''
block = block[:start] + replacement + block[end:]
text = text[:a] + block + text[b:]

# Main-loop boot prompt: infer success from the active value, then require explicit no-freeze/no-crash confirmation.
start = text.find('        if (g_bootPrompt) {')
end = text.find('        if (g_vminScanScreen) {', start)
if start < 0 or end < 0:
    raise RuntimeError('boot prompt main-loop block not found')
boot_block = r'''        if (g_bootPrompt) {
            if (k & HidNpadButton_A) {
                int active = 0;
                const BootInference state = inferBootState(&active);
                if (state == BootInference::RequestedActive) {
                    g.rebootPending = false;
                    g_bootPrompt = false;
                    g.pendingConfigMask = Config_None;
                    if (g.stage == Stage::Preparation) {
                        g.stage = Stage::LowUvQuick;
                        g.lowUvTest = std::min(LOW_UV_MAX, g.lowUvGood + 1);
                        g.stageReadyAfterBoot = false;
                    } else if (g.stage == Stage::LowUvQuick || g.stage == Stage::LowVminQuick) {
                        handlePass();
                    } else {
                        g.stageReadyAfterBoot = true;
                        saveState();
                    }
                } else if (state == BootInference::SaferActive) {
                    g.rebootPending = false;
                    g_bootPrompt = false;
                    g.pendingConfigMask = Config_None;
                    if (g.stage == Stage::LowUvQuick) {
                        g.lowUvGood = std::max(0, active);
                        g.stage = Stage::LowUvLong;
                        g.stageReadyAfterBoot = true;
                    } else if (g.stage == Stage::LowVminQuick) {
                        g.lowVminGood = active;
                        g.stage = Stage::LowVminLong;
                        g.stageReadyAfterBoot = true;
                    }
                    clearVminSweepData();
                    saveState();
                }
                redraw = true;
            } else if (k & HidNpadButton_X) {
                g.rebootPending = false;
                g_bootPrompt = false;
                handleFail(true);
                redraw = true;
            } else if (k & HidNpadButton_B) {
                break;
            }
            svcSleepThread(20'000'000);
            continue;
        }

'''
text = text[:start] + boot_block + text[end:]

# Scan result screen knows whether to retry Low UV or Low VMIN scan.
start = text.find('        if (g_vminScanScreen) {')
end = text.find('        if (g_interruptedPrompt) {', start)
if start < 0 or end < 0:
    raise RuntimeError('scan-screen main-loop block not found')
scan_block = r'''        if (g_vminScanScreen) {
            if (k & HidNpadButton_A) {
                if (g_vminScanSuccess) {
                    g_vminScanScreen = false;
                    redraw = true;
                } else {
                    g_vminScanScreen = false;
                    if (g_scanForLowUv) runAutomaticLowUvScan();
                    else runAutomaticVminScan();
                    redraw = true;
                }
            } else if (k & HidNpadButton_B) {
                g_vminScanScreen = false;
                redraw = true;
            }
            svcSleepThread(20'000'000);
            continue;
        }

'''
text = text[:start] + scan_block + text[end:]

# Config prompt: Y can write Prep / Low UV / Low VMIN automatically.
start = text.find('        if (g_configPrompt) {')
end = text.find('        if (g_autoPrepConfirm) {', start)
if start < 0 or end < 0:
    raise RuntimeError('config prompt main-loop block not found')
config_block = r'''        if (g_configPrompt) {
            if ((k & HidNpadButton_Y) && (g_configCheck.mask & (Config_Prepare | Config_LowUv | Config_LowVmin))) {
                g_autoSetMask = g_configCheck.mask;
                g_autoPrepError.clear();
                g_autoPrepConfirm = true;
                redraw = true;
            } else if ((k & HidNpadButton_X) && g.stage == Stage::Preparation) {
                if (captureCurrentSettingsBaseline()) {
                    g_configPrompt = false;
                    continueFromPreparationBaseline();
                }
                redraw = true;
            } else if (k & HidNpadButton_A) {
                const u32 mask = activeConfigMask();
                if (verifyPersistentSettings(mask)) {
                    g_configPrompt = false;
                    g_rebootConfirm = true;
                }
                redraw = true;
            } else if (k & HidNpadButton_B) {
                g_configPrompt = false;
                redraw = true;
            }
            svcSleepThread(20'000'000);
            continue;
        }

'''
text = text[:start] + config_block + text[end:]

# Automatic setter stops on the reboot-information page; it never reboots immediately.
start = text.find('        if (g_autoPrepConfirm) {')
end = text.find('        if (g_rebootConfirm) {', start)
if start < 0 or end < 0:
    raise RuntimeError('auto-set main-loop block not found')
auto_block = r'''        if (g_autoPrepConfirm) {
            if (k & HidNpadButton_A) {
                g_autoPrepError.clear();
                if (applyAutomaticCurrentSetting(g_autoSetMask)) {
                    g_autoPrepConfirm = false;
                    g_configPrompt = false;
                    g_configCheck.mask = g_autoSetMask;
                    g_rebootConfirm = true;
                }
                redraw = true;
            } else if (k & HidNpadButton_B) {
                g_autoPrepConfirm = false;
                g_autoPrepError.clear();
                redraw = true;
            }
            svcSleepThread(20'000'000);
            continue;
        }

'''
text = text[:start] + auto_block + text[end:]

# Preparation shortcut + setting-page Y button.
text = replace_once(text,
'''        } else if (g.stage == Stage::Preparation && (k & HidNpadButton_Y)) {\n            g_autoPrepError.clear();\n            g_autoPrepConfirm = true;\n            redraw = true;''',
'''        } else if (g.stage == Stage::Preparation && (k & HidNpadButton_Y)) {\n            g_autoSetMask = Config_Prepare;\n            g_autoPrepError.clear();\n            g_autoPrepConfirm = true;\n            redraw = true;''')

# Insert generic Y handling before Known PASS.
needle = '''        } else if ((k & HidNpadButton_Plus) && g.stage != Stage::Preparation) {'''
insert = '''        } else if ((k & HidNpadButton_Y) && g.stage != Stage::Preparation) {\n            const u32 cfgMask = activeConfigMask();\n            if (cfgMask & (Config_LowUv | Config_LowVmin)) {\n                g_autoSetMask = cfgMask;\n                g_autoPrepError.clear();\n                g_autoPrepConfirm = true;\n                redraw = true;\n            }\n        } else if ((k & HidNpadButton_Plus) && g.stage != Stage::Preparation) {'''
text = replace_once(text, needle, insert)

# A on scan/validation pages starts the complete automated action.
old = '''            } else if (isVminSweepStage(g.stage)) {\n                runAutomaticVminScan();\n            } else {\n                stress::Kind kind;'''
new = '''            } else if (g.stage == Stage::LowUvLong) {\n                runAutomaticLowUvScan();\n            } else if (g.stage == Stage::LowUvValidateQuick) {\n                runAutomaticRegionValidation(true);\n            } else if (g.stage == Stage::LowVminLong || isVminSweepStage(g.stage)) {\n                runAutomaticVminScan();\n            } else if (g.stage == Stage::LowVminPlateauValidate) {\n                runAutomaticRegionValidation(false);\n            } else {\n                stress::Kind kind;'''
text = replace_once(text, old, new)

p.write_text(text)
print('beta30 flow patch applied')
