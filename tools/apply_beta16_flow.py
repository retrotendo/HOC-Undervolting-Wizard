from pathlib import Path
import re

p = Path('source/main.cpp')
s = p.read_text()


def rep(old, new, count=1):
    global s
    actual = s.count(old)
    if actual < count:
        raise SystemExit(f'marker not found ({actual} < {count}): {old[:100]!r}')
    s = s.replace(old, new, count)


def replace_function(signature, replacement):
    global s
    start = s.find(signature)
    if start < 0:
        raise SystemExit(f'function not found: {signature}')
    brace = s.find('{', start)
    if brace < 0:
        raise SystemExit(f'opening brace not found: {signature}')
    depth = 0
    i = brace
    in_str = False
    esc = False
    in_char = False
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
        elif in_char:
            if esc: esc = False
            elif c == '\\': esc = True
            elif c == "'": in_char = False
        else:
            if c == '/' and n == '/':
                line_comment = True
                i += 1
            elif c == '/' and n == '*':
                block_comment = True
                i += 1
            elif c == '"': in_str = True
            elif c == "'": in_char = True
            elif c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    s = s[:start] + replacement.rstrip() + '\n' + s[end:]
                    return
        i += 1
    raise SystemExit(f'unclosed function: {signature}')


# ---------------------------------------------------------------------------
# State / stages
# ---------------------------------------------------------------------------
rep('''    LowVminFinalLong,\n    RamBoostValidate\n};''', '''    LowVminFinalLong,\n    RamBoostValidate,\n    // beta.16: appended to keep every previous persisted stage number valid.\n    HardwareDetection,\n    LowVminPlateauValidate\n};''')
rep('''struct WizardState {\n    Stage stage = Stage::Preparation;''', '''struct WizardState {\n    Stage stage = Stage::HardwareDetection;''')
rep('''    bool recoveryNeeded = false;\n    bool warningBelow590Seen = false;\n\n    // Persisted before every built-in test.''', '''    bool recoveryNeeded = false;\n    bool warningBelow590Seen = false;\n\n    // Hardware-guided VDDQ baseline.\n    int dramId = -1;\n    int consoleType = -1;\n    int vddqStartMv = STOCK_VDDQ_MV;\n    bool ramDetected = false;\n\n    // Persistent-setting / reboot handoff.\n    bool stageReadyAfterBoot = false;\n    bool rebootPending = false;\n    u32 pendingConfigMask = 0;\n\n    // VMIN sweep observations and voltage-plateau representatives.\n    int vminObsMv[6] = {};\n    u32 vminObsMask = 0;\n    int vminValidateCount = 0;\n    int vminValidateIndex = 0;\n    u32 vminValidateHz[6] = {};\n    int vminValidateMv[6] = {};\n    u32 lastProbeHz = 0;\n    int lastProbeMv = 0;\n\n    // Persisted before every built-in test.''')

rep('''OverrideCheckState g_overrideCheck;\n\nstd::string formatVdd2''', '''OverrideCheckState g_overrideCheck;\n\nenum ConfigMask : u32 {\n    Config_None    = 0,\n    Config_LowUv   = 1u << 0,\n    Config_LowVmin = 1u << 1,\n    Config_Vddq    = 1u << 2,\n    Config_Vdd2    = 1u << 3,\n    Config_HighUv  = 1u << 4,\n    Config_Prepare = 1u << 5,\n};\n\nstruct ConfigCheckState {\n    bool readOk = false;\n    Result rc = 0;\n    u32 mask = Config_None;\n    HocMonConfig current{};\n};\n\nbool g_configPrompt = false;\nbool g_rebootConfirm = false;\nbool g_bootPrompt = false;\nConfigCheckState g_configCheck;\nResult g_rebootError = 0;\nResult g_hardwareReadRc = 0;\nHocMonHardware g_hardware{};\n\nstd::string formatVdd2''')

# Labels.
rep('''    switch (s) {\n        case Stage::Preparation: return "Preparation";''', '''    switch (s) {\n        case Stage::HardwareDetection: return "Hardware Detection";\n        case Stage::Preparation: return "Preparation";''')
rep('''        case Stage::LowVminFinalLong: return "CPU Low VMIN - Dynamic 1 Hour Validation";''', '''        case Stage::LowVminFinalLong: return "CPU Low VMIN - Dynamic 1 Hour Validation";\n        case Stage::LowVminPlateauValidate: return "CPU Low VMIN - Plateau Validation";''')

# Add plateau test plan.
rep('''        case Stage::LowUvLong:\n        case Stage::LowVminFinalLong:\n        case Stage::HighUvLong:''', '''        case Stage::LowUvLong:\n        case Stage::LowVminFinalLong:\n        case Stage::LowVminPlateauValidate:\n        case Stage::HighUvLong:''')

# Add plateau override target.
rep('''        case Stage::LowVminFinalLong:\n            e = {g.vminFloorHz ? g.vminFloorHz : CLOCK_CPU_VMIN_510_HZ,\n                 CLOCK_GPU_NORMAL_HZ, CLOCK_RAM_NORMAL_HZ};\n            return true;\n\n        case Stage::VddqQuick:''', '''        case Stage::LowVminFinalLong:\n            e = {g.vminFloorHz ? g.vminFloorHz : CLOCK_CPU_VMIN_510_HZ,\n                 CLOCK_GPU_NORMAL_HZ, CLOCK_RAM_NORMAL_HZ};\n            return true;\n        case Stage::LowVminPlateauValidate:\n            e = {(g.vminValidateIndex >= 0 && g.vminValidateIndex < g.vminValidateCount)\n                    ? g.vminValidateHz[g.vminValidateIndex] : CLOCK_CPU_NORMAL_HZ,\n                 CLOCK_GPU_NORMAL_HZ, CLOCK_RAM_NORMAL_HZ};\n            return true;\n\n        case Stage::VddqQuick:''')

# ---------------------------------------------------------------------------
# VMIN measurement progress
# ---------------------------------------------------------------------------
replace_function('bool sampleVminVoltage(Stage s)', r'''bool sampleVminVoltage(Stage s) {
    if (!checkAllOverrides(s)) return false;

    u32 samples[3] = {};
    int count = 0;
    HocMonClocks latest = g_overrideCheck.current;

    for (int i = 0; i < 3; ++i) {
        consoleClear();
        std::printf("\x1b[1;%dH\x1b[36mBattery Wizard\x1b[0m", UI_COL);
        std::printf("\x1b[2;%dHStep : CPU Low VMIN - Voltage Scan", UI_COL);
        std::printf("\x1b[3;%dH----------------------------------------", UI_COL);
        std::printf("\x1b[5;%dHReading CPU voltage...", UI_COL);
        std::printf("\x1b[7;%dHCPU : %s", UI_COL, formatClock(g_overrideCheck.expected.cpuHz).c_str());
        char bar[13] = "............";
        for (int j = 0; j < i * 4; ++j) bar[j] = '#';
        std::printf("\x1b[9;%dH[%s] %d/3", UI_COL, bar, i);
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
        std::printf("\x1b[2;%dHStep : CPU Low VMIN - Voltage Scan", UI_COL);
        std::printf("\x1b[3;%dH----------------------------------------", UI_COL);
        std::printf("\x1b[5;%dHReading CPU voltage...", UI_COL);
        std::printf("\x1b[7;%dHCPU : %s", UI_COL, formatClock(g_overrideCheck.expected.cpuHz).c_str());
        char done[13] = "............";
        for (int j = 0; j < (i + 1) * 4; ++j) done[j] = '#';
        std::printf("\x1b[9;%dH[%s] %d/3", UI_COL, done, i + 1);
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

    std::sort(samples, samples + count);
    latest.cpuVoltageUv = samples[count / 2];
    g_overrideCheck.current = latest;
    g_overrideCheck.readOk = true;
    g_overrideCheck.cpuOk = g_overrideCheck.gpuOk = g_overrideCheck.ramOk = true;
    g_overrideCheck.cpuAppliedOk = true;
    g_overrideCheck.voltageSamplesOk = true;
    return true;
}''')

# ---------------------------------------------------------------------------
# Persist beta16 state fields
# ---------------------------------------------------------------------------
rep('''    f << "warningBelow590Seen=" << (g.warningBelow590Seen ? 1 : 0) << "\\n";\n    f << "testRunning="''', '''    f << "warningBelow590Seen=" << (g.warningBelow590Seen ? 1 : 0) << "\\n";\n    f << "dramId=" << g.dramId << "\\n";\n    f << "consoleType=" << g.consoleType << "\\n";\n    f << "vddqStartMv=" << g.vddqStartMv << "\\n";\n    f << "ramDetected=" << (g.ramDetected ? 1 : 0) << "\\n";\n    f << "stageReadyAfterBoot=" << (g.stageReadyAfterBoot ? 1 : 0) << "\\n";\n    f << "rebootPending=" << (g.rebootPending ? 1 : 0) << "\\n";\n    f << "pendingConfigMask=" << g.pendingConfigMask << "\\n";\n    f << "vminObsMask=" << g.vminObsMask << "\\n";\n    f << "vminValidateCount=" << g.vminValidateCount << "\\n";\n    f << "vminValidateIndex=" << g.vminValidateIndex << "\\n";\n    f << "lastProbeHz=" << g.lastProbeHz << "\\n";\n    f << "lastProbeMv=" << g.lastProbeMv << "\\n";\n    for (int i = 0; i < 6; ++i) {\n        f << "vminObsMv" << i << "=" << g.vminObsMv[i] << "\\n";\n        f << "vminValidateHz" << i << "=" << g.vminValidateHz[i] << "\\n";\n        f << "vminValidateMv" << i << "=" << g.vminValidateMv[i] << "\\n";\n    }\n    f << "testRunning="''')

rep('''    else if (key == "warningBelow590Seen") g.warningBelow590Seen = (v != 0);\n    else if (key == "testRunning")''', '''    else if (key == "warningBelow590Seen") g.warningBelow590Seen = (v != 0);\n    else if (key == "dramId") g.dramId = v;\n    else if (key == "consoleType") g.consoleType = v;\n    else if (key == "vddqStartMv") g.vddqStartMv = v;\n    else if (key == "ramDetected") g.ramDetected = (v != 0);\n    else if (key == "stageReadyAfterBoot") g.stageReadyAfterBoot = (v != 0);\n    else if (key == "rebootPending") g.rebootPending = (v != 0);\n    else if (key == "pendingConfigMask") g.pendingConfigMask = (u32)std::strtoul(value.c_str(), nullptr, 10);\n    else if (key == "vminObsMask") g.vminObsMask = (u32)std::strtoul(value.c_str(), nullptr, 10);\n    else if (key == "vminValidateCount") g.vminValidateCount = v;\n    else if (key == "vminValidateIndex") g.vminValidateIndex = v;\n    else if (key == "lastProbeHz") g.lastProbeHz = (u32)std::strtoul(value.c_str(), nullptr, 10);\n    else if (key == "lastProbeMv") g.lastProbeMv = v;\n    else if (key.rfind("vminObsMv", 0) == 0) { int i = std::atoi(key.c_str() + 9); if (i >= 0 && i < 6) g.vminObsMv[i] = v; }\n    else if (key.rfind("vminValidateHz", 0) == 0) { int i = std::atoi(key.c_str() + 14); if (i >= 0 && i < 6) g.vminValidateHz[i] = (u32)std::strtoul(value.c_str(), nullptr, 10); }\n    else if (key.rfind("vminValidateMv", 0) == 0) { int i = std::atoi(key.c_str() + 14); if (i >= 0 && i < 6) g.vminValidateMv[i] = v; }\n    else if (key == "testRunning")''')

# Old beta15 state at Preparation should visit hardware detection once after update.
rep('''    if (g.lowVminTest < LOW_VMIN_MIN_MV) g.lowVminTest = LOW_VMIN_MIN_MV;\n    return true;''', '''    if (g.lowVminTest < LOW_VMIN_MIN_MV) g.lowVminTest = LOW_VMIN_MIN_MV;\n    if (!g.ramDetected && g.stage == Stage::Preparation) g.stage = Stage::HardwareDetection;\n    return true;''')

# ---------------------------------------------------------------------------
# Hardware/config/plateau helpers after resetState (saveState already exists)
# ---------------------------------------------------------------------------
marker = '''void writeResults() {'''
idx = s.find(marker)
if idx < 0: raise SystemExit('writeResults marker not found')
helpers = r'''
struct RamProfile {
    const char* name;
    int vddqStartMv;
    bool known;
};

RamProfile ramProfileForId(int id) {
    switch (id) {
        case 3: case 5: case 6: return {"NEE 4GB", 640, true};
        case 8: case 12: return {"AM-MGCJ 4GB", 640, true};
        case 9: case 13: return {"AM-MGCJ 8GB", 640, true};
        case 10: case 14: return {"NME 4GB", 640, true};
        case 11: case 15: return {"WT:E 4GB", 600, true};
        case 17: case 19: case 24: return {"AA-MGCL 4GB", 640, true};
        case 18: case 23: case 28: return {"AA-MGCL 8GB", 640, true};
        case 20: case 21: case 22: return {"AB-MGCL 4GB", 640, true};
        case 25: case 26: case 27: return {"WT:F 4GB", 600, true};
        case 29: case 30: case 31: return {"x267 4GB", 640, true};
        case 32: case 33: case 34: return {"WT:B 4GB", 600, true};
        default: return {"Unknown", STOCK_VDDQ_MV, false};
    }
}

bool detectRamHardware() {
    g_hardware = HocMonHardware{};
    g_hardwareReadRc = hocmonGetHardware(&g_hardware);
    if (R_FAILED(g_hardwareReadRc)) return false;
    const RamProfile p = ramProfileForId(g_hardware.dramId);
    // Icosa = Erista/V1, outside this Mariko Battery guide.
    if (!p.known || g_hardware.consoleType == 0) return false;
    g.dramId = g_hardware.dramId;
    g.consoleType = (int)g_hardware.consoleType;
    g.vddqStartMv = p.vddqStartMv;
    g.ramDetected = true;
    g.vddqGood = g.vddqStartMv;
    g.vddqTest = g.vddqStartMv - VDDQ_STEP_MV;
    saveState();
    return true;
}

u32 defaultConfigMaskForStage(Stage st) {
    switch (st) {
        case Stage::Preparation: return Config_Prepare;
        case Stage::LowUvQuick:
        case Stage::LowUvLong: return Config_LowUv;
        case Stage::LowVminQuick: return Config_LowVmin;
        case Stage::VddqQuick:
        case Stage::VddqLong: return Config_Vddq;
        case Stage::Vdd2Quick:
        case Stage::Vdd2Long: return Config_Vdd2;
        case Stage::HighUvQuick:
        case Stage::HighUvLong: return Config_HighUv;
        default: return Config_None;
    }
}

u32 activeConfigMask() {
    if (g.stageReadyAfterBoot) return Config_None;
    if (g.pendingConfigMask) return g.pendingConfigMask;
    return defaultConfigMaskForStage(g.stage);
}

int targetLowUv() {
    return g.stage == Stage::LowUvQuick ? g.lowUvTest : g.lowUvGood;
}
int targetLowVmin() {
    return g.stage == Stage::LowVminQuick ? g.lowVminTest : g.lowVminGood;
}
int targetVddqMv() {
    return g.stage == Stage::VddqQuick ? g.vddqTest : g.vddqGood;
}
int targetVdd2Uv() {
    return g.stage == Stage::Vdd2Quick ? g.vdd2TestUv : g.vdd2GoodUv;
}
int targetHighUv() {
    return g.stage == Stage::HighUvQuick ? g.highUvTest : g.highUvGood;
}

bool configMatchesCurrent(u32 mask, const HocMonConfig& c) {
    if (mask & Config_Prepare) {
        return !c.uncappedClocks && !c.hpMode && c.ramMaxKHz == 1600000U &&
               c.vdd2Uv == (u32)STOCK_VDD2_UV && c.vddqUv == (u32)g.vddqStartMv * 1000U &&
               c.cpuMaxKHz == 1963500U && c.lowVminMv == STOCK_LOW_VMIN_MV &&
               c.highVminMv == STOCK_HIGH_VMIN_MV && c.tableConf == 3 &&
               c.lowUv == STOCK_LOW_UV && c.highUv == STOCK_HIGH_UV &&
               c.cpuBoostKHz == 1785000U;
    }
    if ((mask & Config_LowUv) && c.lowUv != targetLowUv()) return false;
    if ((mask & Config_LowVmin) && c.lowVminMv != targetLowVmin()) return false;
    if ((mask & Config_Vddq) && c.vddqUv != (u32)targetVddqMv() * 1000U) return false;
    if ((mask & Config_Vdd2) && c.vdd2Uv != (u32)targetVdd2Uv()) return false;
    if ((mask & Config_HighUv) && c.highUv != targetHighUv()) return false;
    return true;
}

bool verifyPersistentSettings(u32 mask) {
    g_configCheck = ConfigCheckState{};
    g_configCheck.mask = mask;
    g_configCheck.rc = hocmonGetConfig(&g_configCheck.current);
    g_configCheck.readOk = R_SUCCEEDED(g_configCheck.rc);
    return g_configCheck.readOk && configMatchesCurrent(mask, g_configCheck.current);
}

void clearVminSweepData() {
    g.vminObsMask = 0;
    g.vminValidateCount = 0;
    g.vminValidateIndex = 0;
    g.lastProbeHz = 0;
    g.lastProbeMv = 0;
    g.vminFloorHz = 0;
    g.vminFloorObservedMv = 0;
    for (int i = 0; i < 6; ++i) {
        g.vminObsMv[i] = 0;
        g.vminValidateHz[i] = 0;
        g.vminValidateMv[i] = 0;
    }
}

int vminSweepIndex(Stage st) {
    switch (st) {
        case Stage::LowVminLong: return 0;
        case Stage::LowVminSweep612: return 1;
        case Stage::LowVminSweep714: return 2;
        case Stage::LowVminValidate816: return 3;
        case Stage::LowVminSweep918: return 4;
        case Stage::LowVminValidate1020: return 5;
        default: return -1;
    }
}

void buildVminPlateaus() {
    static const u32 clocks[6] = {
        CLOCK_CPU_VMIN_510_HZ, CLOCK_CPU_LOW_HZ, CLOCK_CPU_VMIN_714_HZ,
        CLOCK_CPU_VMIN_MID_HZ, CLOCK_CPU_VMIN_918_HZ, CLOCK_CPU_NORMAL_HZ
    };
    g.vminValidateCount = 0;
    g.vminValidateIndex = 0;
    g.vminFloorHz = 0;
    g.vminFloorObservedMv = 0;

    for (int i = 0; i < 6; ++i) {
        if (!(g.vminObsMask & (1u << i)) || g.vminObsMv[i] <= 0) continue;
        const int mv = g.vminObsMv[i];
        if (g.vminValidateCount == 0 || g.vminValidateMv[g.vminValidateCount - 1] != mv) {
            const int n = g.vminValidateCount++;
            g.vminValidateMv[n] = mv;
            g.vminValidateHz[n] = clocks[i];
        } else {
            // Same voltage region: only its highest frequency needs the long test.
            g.vminValidateHz[g.vminValidateCount - 1] = clocks[i];
        }
    }

    for (int i = 0; i < g.vminValidateCount; ++i) {
        if (std::abs(g.vminValidateMv[i] - g.lowVminGood) <= 5) {
            g.vminFloorHz = g.vminValidateHz[i];
            g.vminFloorObservedMv = g.vminValidateMv[i];
            break;
        }
    }
    if (!g.vminFloorHz && g.vminValidateCount > 0) {
        g.vminFloorHz = g.vminValidateHz[0];
        g.vminFloorObservedMv = g.vminValidateMv[0];
    }
    saveState();
}

'''
s = s[:idx] + helpers + s[idx:]

# Results include detected RAM + every voltage representative.
rep('''    f << "CPU UV Table: 1683 MHz Tbreak\\n";''', '''    if (g.ramDetected) {\n        const RamProfile rp = ramProfileForId(g.dramId);\n        f << "Detected RAM: " << rp.name << " (ID " << g.dramId << ")\\n";\n        f << "VDDQ starting point: " << g.vddqStartMv << " mV\\n";\n    }\n    f << "CPU UV Table: 1683 MHz Tbreak\\n";''')
rep('''    if (g.vminFloorHz)\n        f << "Detected highest Low VMIN floor clock: " << (g.vminFloorHz / 1000000U) << " MHz (~" << g.vminFloorObservedMv << " mV)\\n";''', '''    if (g.vminFloorHz)\n        f << "Detected highest Low VMIN floor clock: " << (g.vminFloorHz / 1000000U) << " MHz (~" << g.vminFloorObservedMv << " mV)\\n";\n    if (g.vminValidateCount > 0) {\n        f << "CPU voltage regions validated:\\n";\n        for (int i = 0; i < g.vminValidateCount; ++i)\n            f << "  " << (g.vminValidateHz[i] / 1000000U) << " MHz @ ~" << g.vminValidateMv[i] << " mV\\n";\n    }''')

# ---------------------------------------------------------------------------
# UI labels and screens
# ---------------------------------------------------------------------------
rep('''    switch (s) {\n        case Stage::Preparation: return "Preparation";''', '''    switch (s) {\n        case Stage::HardwareDetection: return "Hardware Detection";\n        case Stage::Preparation: return "Preparation";''', 1)
rep('''        case Stage::LowVminFinalLong: return "CPU Low VMIN - Validate";''', '''        case Stage::LowVminFinalLong: return "CPU Low VMIN - Validate";\n        case Stage::LowVminPlateauValidate: return "CPU Low VMIN - Plateau";''', 1)

replace_function('void renderPreparation()', r'''void renderPreparation() {
    title();
    uiPrintf(5, "@ Horizon OC");

    uiPrintf(7, "General:");
    uiPrintf(8, " - Uncapped Clocks : OFF");

    uiPrintf(10, "RAM Settings:");
    uiPrintf(11, " - HP Mode         : OFF");
    uiPrintf(12, " - RAM Max         : 1600 MHz");
    uiPrintf(13, " - VDD2            : 1175 mV");
    uiPrintf(14, " - VDDQ            : %d mV", g.vddqStartMv);

    uiPrintf(16, "CPU Settings:");
    uiPrintf(17, " - CPU Max         : Lowest selectable (1963)");
    uiPrintf(18, " - Low VMIN        : 620 mV");
    uiPrintf(19, " - High VMIN       : 750 mV");
    uiPrintf(20, " - UV Table        : 1683 MHz Tbreak");
    uiPrintf(21, " - Low UV          : 0");
    uiPrintf(22, " - High UV         : 0");

    uiPrintf(24, "@ HOC Toolkit");
    uiPrintf(26, " - CPU Boost       : Lowest selectable / 1785");

    uiPrintf(29, "A : Check settings");
    uiPrintf(30, "+ : Known PASS / Skip");
    uiPrintf(31, "B : Exit    - : Reset");
}''')

# New UI helpers inserted before renderPreparation.
marker = 'void renderPreparation() {'
idx = s.find(marker)
if idx < 0: raise SystemExit('renderPreparation marker missing')
ui_helpers = r'''
void renderHardwareDetection() {
    title();
    if (g.ramDetected) {
        const RamProfile rp = ramProfileForId(g.dramId);
        uiPrintf(6, "\x1b[32mRAM detected\x1b[0m");
        uiPrintf(8, "Module     : %s", rp.name);
        uiPrintf(9, "DRAM ID    : %d", g.dramId);
        uiPrintf(11, "VDDQ start : %d mV", g.vddqStartMv);
        uiPrintf(14, "A : Continue to Preparation");
        uiPrintf(15, "B : Exit");
    } else {
        uiPrintf(6, "\x1b[31mRAM detection failed\x1b[0m");
        if (R_FAILED(g_hardwareReadRc))
            uiPrintf(8, "hoc:clk result : 0x%08X", g_hardwareReadRc);
        else
            uiPrintf(8, "Unsupported / unknown DRAM ID : %u", g_hardware.dramId);
        uiPrintf(10, "The Wizard will not guess a VDDQ baseline.");
        uiPrintf(13, "A : Retry detection");
        uiPrintf(14, "B : Exit");
    }
}

void renderBootPrompt() {
    consoleClear();
    uiPrintf(1, "\x1b[36mBattery Wizard - BOOT CHECK\x1b[0m");
    uiPrintf(3, "Did the console boot normally");
    uiPrintf(4, "with the new Horizon OC setting?");
    uiPrintf(7, "A : YES - continue");
    uiPrintf(8, "X : NO  - setting did not boot");
    uiPrintf(10, "B : Exit and decide later");
    consoleUpdate(nullptr);
}

void printSingleConfigCheck(int row, const char* label, const std::string& required,
                            const std::string& current, bool ok) {
    uiPrintf(row, "%s", label);
    uiPrintf(row + 1, "  Required : %s", required.c_str());
    uiPrintf(row + 2, "  Current  : %s", current.c_str());
    uiPrintf(row + 3, "  Status   : %s", ok ? "\x1b[32mOK\x1b[0m" : "\x1b[31mWRONG\x1b[0m");
}

std::string formatMv(int mv) { return std::to_string(mv) + " mV"; }

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
        uiPrintf(row++, "Preparation contains one or more WRONG values.");
        row++;
        if (g_configCheck.current.vddqUv != (u32)g.vddqStartMv * 1000U)
            printSingleConfigCheck(row, "VDDQ", formatMv(g.vddqStartMv), formatMv((int)(g_configCheck.current.vddqUv / 1000U)), false), row += 5;
        if (g_configCheck.current.vdd2Uv != (u32)STOCK_VDD2_UV)
            printSingleConfigCheck(row, "VDD2", formatVdd2(STOCK_VDD2_UV), formatVdd2((int)g_configCheck.current.vdd2Uv), false), row += 5;
        if (g_configCheck.current.lowVminMv != STOCK_LOW_VMIN_MV)
            printSingleConfigCheck(row, "Low VMIN", formatMv(STOCK_LOW_VMIN_MV), formatMv(g_configCheck.current.lowVminMv), false), row += 5;
        uiPrintf(row++, "Check the remaining Preparation values too.");
    } else if (m & Config_LowUv) {
        printSingleConfigCheck(row, "CPU Low UV", std::to_string(targetLowUv()), std::to_string(g_configCheck.current.lowUv), g_configCheck.current.lowUv == targetLowUv());
        row += 5;
    } else if (m & Config_LowVmin) {
        printSingleConfigCheck(row, "CPU Low VMIN", formatMv(targetLowVmin()), formatMv(g_configCheck.current.lowVminMv), g_configCheck.current.lowVminMv == targetLowVmin());
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

void renderRebootConfirm() {
    consoleClear();
    uiPrintf(1, "\x1b[36mBattery Wizard\x1b[0m");
    uiPrintf(2, "Step : %s", compactStepName(g.stage));
    uiPrintf(3, "----------------------------------------");
    const u32 m = g_configCheck.mask;
    if (m & Config_Prepare)
        uiPrintf(6, "\x1b[32mPreparation settings detected.\x1b[0m");
    else if (m & Config_LowUv)
        uiPrintf(6, "\x1b[32mLow UV %d is set.\x1b[0m", targetLowUv());
    else if (m & Config_LowVmin)
        uiPrintf(6, "\x1b[32mLow VMIN %d mV is set.\x1b[0m", targetLowVmin());
    else if (m & Config_Vddq)
        uiPrintf(6, "\x1b[32mVDDQ %d mV is set.\x1b[0m", targetVddqMv());
    else if (m & Config_Vdd2)
        uiPrintf(6, "\x1b[32mVDD2 %s is set.\x1b[0m", formatVdd2(targetVdd2Uv()).c_str());
    else if (m & Config_HighUv)
        uiPrintf(6, "\x1b[32mHigh UV %d is set.\x1b[0m", targetHighUv());
    uiPrintf(9, "A : Restart console");
    uiPrintf(10, "B : Back");
    consoleUpdate(nullptr);
}

'''
s = s[:idx] + ui_helpers + s[idx:]

replace_function('void renderTestStage()', r'''void renderTestStage() {
    title();

    // A persistent value that still needs to be set gets its own clean page.
    const u32 configMask = activeConfigMask();
    if (configMask != Config_None) {
        uiPrintf(5, "@ Horizon OC");
        uiPrintf(7, (configMask & (Config_Vddq | Config_Vdd2)) ? "RAM Settings:" : "CPU Settings:");
        if (configMask & Config_LowUv) uiPrintf(8, " - Low UV   : %d", targetLowUv());
        if (configMask & Config_LowVmin) uiPrintf(8, " - Low VMIN : %d mV", targetLowVmin());
        if (configMask & Config_Vddq) uiPrintf(8, " - VDDQ     : %d mV", targetVddqMv());
        if (configMask & Config_Vdd2) uiPrintf(8, " - VDD2     : %s", formatVdd2(targetVdd2Uv()).c_str());
        if (configMask & Config_HighUv) uiPrintf(8, " - High UV  : %d", targetHighUv());
        uiPrintf(11, "A : Check setting");
        uiPrintf(12, "+ : Known PASS / Skip");
        uiPrintf(13, "B : Exit    - : Reset");
        return;
    }

    stress::Kind kind;
    int seconds = 0;
    const bool hasTest = testPlan(g.stage, kind, seconds);
    OverrideExpectation expected{};
    const bool hasOverrides = overridePlan(g.stage, expected);

    int row = 5;
    if (g.recoveryNeeded) {
        uiPrintf(row++, "\x1b[33mRecovery value restored.\x1b[0m");
        g.recoveryNeeded = false;
        row++;
    }

    if (g.stage == Stage::LowVminPlateauValidate && g.vminValidateIndex < g.vminValidateCount) {
        uiPrintf(row++, "Voltage region %d / %d", g.vminValidateIndex + 1, g.vminValidateCount);
        uiPrintf(row++, "Measured : ~%d mV", g.vminValidateMv[g.vminValidateIndex]);
        uiPrintf(row++, "Highest  : %s", formatClock(g.vminValidateHz[g.vminValidateIndex]).c_str());
        row++;
    }

    if (hasOverrides) {
        uiPrintf(row++, "@ Horizon OC");
        row++;
        printOverrides(row, expected);
        row += 5;
    }

    if (isVminSweepStage(g.stage)) {
        uiPrintf(row++, "Voltage scan:");
        uiPrintf(row++, "A : Read voltage");
        uiPrintf(row++, "    (3 samples / progress shown)");
        if (g.lastProbeHz) uiPrintf(row++, "Last: %s @ ~%d mV", formatClock(g.lastProbeHz).c_str(), g.lastProbeMv);
        uiPrintf(row++, "B : Exit");
        return;
    }

    if (hasTest) {
        uiPrintf(row++, "Test:");
        uiPrintf(row++, "%s - %s", seconds == 60 ? "1 min" : "1 hour", compactTestName(kind));
        footerTest(row + 1);
    }
}''')

replace_function('void render()', r'''void render() {
    consoleClear();
    if (g_bootPrompt) { renderBootPrompt(); return; }
    if (g_interruptedPrompt) { renderInterruptedPrompt(); return; }
    if (g_configPrompt) { renderConfigPrompt(); return; }
    if (g_rebootConfirm) { renderRebootConfirm(); return; }
    if (g_overridePrompt) { renderOverridePrompt(); return; }
    if (g_resultScreen) { renderResultScreen(); return; }
    if (g_resetConfirm) {
        std::printf("\x1b[1;1H\x1b[31mReset ALL wizard progress?\x1b[0m\n\n");
        std::printf("[A] Yes, reset   [B] Cancel\n");
        consoleUpdate(nullptr);
        return;
    }

    if (g.stage == Stage::HardwareDetection) renderHardwareDetection();
    else if (g.stage == Stage::Preparation) renderPreparation();
    else if (g.stage == Stage::RealWorldValidate) renderRealWorld();
    else if (g.stage == Stage::Complete) renderComplete();
    else renderTestStage();
    consoleUpdate(nullptr);
}''')

# ---------------------------------------------------------------------------
# VMIN observation + state transitions
# ---------------------------------------------------------------------------
replace_function('void recordVminObservation(Stage st)', r'''void recordVminObservation(Stage st) {
    if (!isVminSweepStage(st) || !g_overrideCheck.readOk) return;
    const int idx = vminSweepIndex(st);
    const u32 hz = vminSweepClock(st);
    const u32 uv = g_overrideCheck.current.cpuVoltageUv;
    if (idx < 0 || !hz || !uv) return;

    // HOC/PMIC steps are 5 mV: group readings into the actual voltage regions.
    const int mv = (int)(((uv + 2500U) / 5000U) * 5U);
    g.vminObsMv[idx] = mv;
    g.vminObsMask |= (1u << idx);
    g.lastProbeHz = hz;
    g.lastProbeMv = mv;

    const int delta = std::abs(mv - g.lowVminGood);
    if (delta <= 5) {
        g.vminFloorHz = hz;
        g.vminFloorObservedMv = mv;
    }
    saveState();
}''')

replace_function('void restartVminSweep(bool recovery)', r'''void restartVminSweep(bool recovery) {
    g.stage = Stage::LowVminLong;
    g.recoveryNeeded = recovery;
    clearVminSweepData();
    saveState();
}''')

replace_function('void handlePass()', r'''void handlePass() {
    switch (g.stage) {
        case Stage::HardwareDetection:
            g.stage = Stage::Preparation;
            g.stageReadyAfterBoot = false;
            break;
        case Stage::Preparation:
            g.stage = Stage::LowUvQuick;
            g.stageReadyAfterBoot = false;
            break;
        case Stage::LowUvQuick:
            g.lowUvGood = g.lowUvTest;
            if (g.lowUvTest >= LOW_UV_MAX) {
                g.stage = Stage::LowUvLong;
                g.stageReadyAfterBoot = true; // same already-booted value
            } else {
                ++g.lowUvTest;
                g.stageReadyAfterBoot = false;
            }
            break;
        case Stage::LowUvLong:
            g.recoveryNeeded = false;
            g.stage = Stage::LowVminQuick;
            g.lowVminTest = g.lowVminGood - LOW_VMIN_STEP_MV;
            g.stageReadyAfterBoot = false;
            break;
        case Stage::LowVminQuick:
            g.lowVminGood = g.lowVminTest;
            if (g.lowVminTest <= LOW_VMIN_MIN_MV) {
                restartVminSweep(false);
                g.stageReadyAfterBoot = true; // 570 was already booted for quick test
                return;
            }
            g.lowVminTest -= LOW_VMIN_STEP_MV;
            g.stageReadyAfterBoot = false;
            break;
        case Stage::LowVminLong: g.stage = Stage::LowVminSweep612; break;
        case Stage::LowVminSweep612: g.stage = Stage::LowVminSweep714; break;
        case Stage::LowVminSweep714: g.stage = Stage::LowVminValidate816; break;
        case Stage::LowVminValidate816: g.stage = Stage::LowVminSweep918; break;
        case Stage::LowVminSweep918: g.stage = Stage::LowVminValidate1020; break;
        case Stage::LowVminValidate1020:
            buildVminPlateaus();
            g.stage = Stage::LowVminPlateauValidate;
            g.stageReadyAfterBoot = true;
            break;
        case Stage::LowVminFinalLong:
            // Legacy state compatibility: move into the new plateau workflow.
            buildVminPlateaus();
            g.stage = Stage::LowVminPlateauValidate;
            g.stageReadyAfterBoot = true;
            break;
        case Stage::LowVminPlateauValidate:
            ++g.vminValidateIndex;
            if (g.vminValidateIndex >= g.vminValidateCount) {
                g.stage = Stage::VddqQuick;
                g.vddqTest = g.vddqStartMv - VDDQ_STEP_MV;
                g.stageReadyAfterBoot = false;
            }
            break;
        case Stage::VddqQuick:
            g.vddqGood = g.vddqTest;
            if (g.vddqTest <= VDDQ_MIN_MV) {
                g.stage = Stage::VddqLong;
                g.stageReadyAfterBoot = true;
            } else {
                g.vddqTest -= VDDQ_STEP_MV;
                g.stageReadyAfterBoot = false;
            }
            break;
        case Stage::VddqLong:
            g.recoveryNeeded = false;
            g.stage = Stage::Vdd2Quick;
            g.vdd2TestUv = STOCK_VDD2_UV - VDD2_STEP_UV;
            g.stageReadyAfterBoot = false;
            break;
        case Stage::Vdd2Quick:
            g.vdd2GoodUv = g.vdd2TestUv;
            if (g.vdd2TestUv <= VDD2_MIN_UV) {
                g.stage = Stage::Vdd2Long;
                g.stageReadyAfterBoot = true;
            } else {
                g.vdd2TestUv -= VDD2_STEP_UV;
                g.stageReadyAfterBoot = false;
            }
            break;
        case Stage::Vdd2Long:
            g.recoveryNeeded = false;
            g.ramPairRetryMode = 0;
            g.stage = Stage::RamBoostValidate;
            break;
        case Stage::RamBoostValidate:
            g.ramPairRetryMode = 0;
            g.stage = Stage::Ram1331Validate;
            break;
        case Stage::Ram1331Validate:
            g.stage = Stage::HighUvQuick;
            g.highUvTest = 1;
            g.stageReadyAfterBoot = false;
            break;
        case Stage::HighUvQuick:
            g.highUvGood = g.highUvTest;
            if (g.highUvTest >= HIGH_UV_MAX) {
                g.stage = Stage::HighUvLong;
                g.stageReadyAfterBoot = true;
            } else {
                ++g.highUvTest;
                g.stageReadyAfterBoot = false;
            }
            break;
        case Stage::HighUvLong:
            g.recoveryNeeded = false;
            g.stage = Stage::BoostCpuRamValidate;
            break;
        case Stage::BoostCpuRamValidate: g.stage = Stage::NormalMatrixValidate; break;
        case Stage::NormalMatrixValidate: g.stage = Stage::NormalMemValidate; break;
        case Stage::NormalMemValidate: g.stage = Stage::NormalGpuValidate; break;
        case Stage::NormalGpuValidate: g.stage = Stage::BoostMatrixValidate; break;
        case Stage::BoostMatrixValidate: g.stage = Stage::BoostMemValidate; break;
        case Stage::BoostMemValidate: g.stage = Stage::BoostCpuMemValidate; break;
        case Stage::BoostCpuMemValidate: g.stage = Stage::RealWorldValidate; break;
        case Stage::RealWorldValidate: g.stage = Stage::Complete; writeResults(); break;
        case Stage::Complete: break;
    }
    g.pendingConfigMask = Config_None;
    saveState();
}''')

replace_function('void handleFail(bool didNotBoot)', r'''void handleFail(bool didNotBoot) {
    g.stageReadyAfterBoot = false;
    switch (g.stage) {
        case Stage::Preparation:
            g.recoveryNeeded = didNotBoot;
            break;
        case Stage::LowUvQuick:
            g.stage = Stage::LowUvLong;
            g.recoveryNeeded = didNotBoot;
            g.pendingConfigMask = Config_LowUv;
            break;
        case Stage::LowUvLong:
            if (g.lowUvGood > 0) --g.lowUvGood;
            g.pendingConfigMask = Config_LowUv;
            break;
        case Stage::LowVminQuick:
            // Restore the last passing VMIN before the full voltage scan.
            restartVminSweep(didNotBoot);
            g.pendingConfigMask = Config_LowVmin;
            return;
        case Stage::LowVminLong:
        case Stage::LowVminSweep612:
        case Stage::LowVminSweep714:
        case Stage::LowVminValidate816:
        case Stage::LowVminSweep918:
        case Stage::LowVminValidate1020:
            restartVminSweep(false);
            break;
        case Stage::LowVminFinalLong:
            restartVminSweep(false);
            break;
        case Stage::LowVminPlateauValidate: {
            const int mv = (g.vminValidateIndex < g.vminValidateCount) ? g.vminValidateMv[g.vminValidateIndex] : g.lowVminGood;
            if (mv <= g.lowVminGood + 5) {
                if (g.lowVminGood < STOCK_LOW_VMIN_MV) g.lowVminGood += LOW_VMIN_STEP_MV;
                g.pendingConfigMask = Config_LowVmin;
            } else if (g.lowUvGood > 0) {
                --g.lowUvGood;
                g.pendingConfigMask = Config_LowUv;
            } else {
                if (g.lowVminGood < STOCK_LOW_VMIN_MV) g.lowVminGood += LOW_VMIN_STEP_MV;
                g.pendingConfigMask = Config_LowVmin;
            }
            restartVminSweep(false);
            // restartVminSweep clears state but intentionally keeps pendingConfigMask.
            break;
        }
        case Stage::VddqQuick:
            g.stage = Stage::VddqLong;
            g.recoveryNeeded = didNotBoot;
            g.pendingConfigMask = Config_Vddq;
            break;
        case Stage::VddqLong:
            g.vddqGood += VDDQ_STEP_MV;
            g.pendingConfigMask = Config_Vddq;
            break;
        case Stage::Vdd2Quick:
            g.stage = Stage::Vdd2Long;
            g.recoveryNeeded = didNotBoot;
            g.pendingConfigMask = Config_Vdd2;
            break;
        case Stage::Vdd2Long:
            g.vdd2GoodUv += VDD2_STEP_UV;
            g.pendingConfigMask = Config_Vdd2;
            break;
        case Stage::RamBoostValidate:
            if (g.ramPairRetryMode == 0) {
                g.vddqGood += VDDQ_STEP_MV;
                g.ramPairRetryMode = 1;
                g.pendingConfigMask = Config_Vddq;
            } else if (g.ramPairRetryMode == 1) {
                g.vddqGood -= VDDQ_STEP_MV;
                g.vdd2GoodUv += VDD2_STEP_UV;
                g.ramPairRetryMode = 2;
                g.pendingConfigMask = Config_Vddq | Config_Vdd2;
            } else {
                g.vdd2GoodUv += VDD2_STEP_UV;
                g.pendingConfigMask = Config_Vdd2;
            }
            break;
        case Stage::Ram1331Validate:
            g.vddqGood += VDDQ_STEP_MV;
            g.pendingConfigMask = Config_Vddq;
            break;
        case Stage::HighUvQuick:
            g.stage = Stage::HighUvLong;
            g.recoveryNeeded = didNotBoot;
            g.pendingConfigMask = Config_HighUv;
            break;
        case Stage::HighUvLong:
            if (g.highUvGood > 0) --g.highUvGood;
            g.pendingConfigMask = Config_HighUv;
            break;
        case Stage::BoostCpuRamValidate:
            if (g.highUvGood > 0) --g.highUvGood;
            g.pendingConfigMask = Config_HighUv;
            break;
        case Stage::NormalMatrixValidate:
            if (g.lowUvGood > 0) --g.lowUvGood;
            g.pendingConfigMask = Config_LowUv;
            break;
        case Stage::NormalMemValidate:
        case Stage::BoostMemValidate:
            g.vddqGood += VDDQ_STEP_MV;
            g.pendingConfigMask = Config_Vddq;
            break;
        case Stage::BoostMatrixValidate:
        case Stage::BoostCpuMemValidate:
            if (g.highUvGood > 0) --g.highUvGood;
            g.pendingConfigMask = Config_HighUv;
            break;
        case Stage::NormalGpuValidate:
        case Stage::RealWorldValidate:
        default:
            break;
    }
    saveState();
}''')

# Preserve pending config when restartVminSweep is called from plateau failure.
rep('''void restartVminSweep(bool recovery) {\n    g.stage = Stage::LowVminLong;\n    g.recoveryNeeded = recovery;\n    clearVminSweepData();\n    saveState();\n}''', '''void restartVminSweep(bool recovery) {\n    const u32 keepMask = g.pendingConfigMask;\n    g.stage = Stage::LowVminLong;\n    g.recoveryNeeded = recovery;\n    clearVminSweepData();\n    g.pendingConfigMask = keepMask;\n    saveState();\n}''')

replace_function('void runVminProbe()', r'''void runVminProbe() {
    if (!isVminSweepStage(g.stage)) return;

    g_overrideAction = PendingOverrideAction::VminProbe;
    if (!sampleVminVoltage(g.stage)) {
        g_overridePrompt = true;
        return;
    }
    g_overridePrompt = false;

    const Stage probedStage = g.stage;
    recordVminObservation(probedStage);

    consoleClear();
    uiPrintf(5, "\x1b[32mVoltage read complete\x1b[0m");
    uiPrintf(7, "%s", formatClock(g.lastProbeHz).c_str());
    uiPrintf(8, "~%d mV", g.lastProbeMv);
    consoleUpdate(nullptr);
    svcSleepThread(600'000'000);

    handlePass();
}''')

# ---------------------------------------------------------------------------
# Main input loop with setting verify -> green confirm -> reboot -> boot check.
# ---------------------------------------------------------------------------
replace_function('int main(int argc, char** argv)', r'''int main(int argc, char** argv) {
    consoleInit(nullptr);
    padConfigureInput(1, HidNpadStyleSet_NpadStandard);
    PadState pad;
    padInitializeDefault(&pad);

    const AppletType appletType = appletGetAppletType();
    const bool fullMemoryMode =
        appletType == AppletType_Application || appletType == AppletType_SystemApplication;

    if (!fullMemoryMode) {
        while (appletMainLoop()) {
            padUpdate(&pad);
            const u64 k = padGetButtonsDown(&pad);
            consoleClear();
            std::printf("\x1b[1;1H\x1b[31mHOC Undervolting Wizard - CANNOT START\x1b[0m\n");
            std::printf("------------------------------------------------------------\n\n");
            std::printf("\x1b[1mApplet Mode detected.\x1b[0m\n\n");
            std::printf("The Wizard's stability tests require Full Memory Mode.\n");
            std::printf("Applet Mode is therefore not supported.\n\n");
            std::printf("Start hbmenu correctly:\n");
            std::printf("  1. Return to the HOME Menu.\n");
            std::printf("  2. Highlight any installed game.\n");
            std::printf("  3. Hold [R] while starting the game.\n");
            std::printf("  4. Keep holding [R] until hbmenu opens.\n");
            std::printf("  5. Start HOC Undervolting Wizard again.\n\n");
            std::printf("Do NOT launch hbmenu from the Album for stability testing.\n\n");
            std::printf("[B] Exit\n");
            consoleUpdate(nullptr);
            if (k & HidNpadButton_B) break;
            svcSleepThread(20'000'000);
        }
        consoleExit(nullptr);
        return 0;
    }

    if (updater::startupCheckAndPrompt(pad, argc, argv)) {
        consoleExit(nullptr);
        return 0;
    }

    ensureDir();
    migrateLegacyState();
    if (!loadState()) saveState();

    // First beta16 start: identify Mariko DRAM before Preparation.
    if (g.stage == Stage::HardwareDetection && !g.ramDetected)
        detectRamHardware();

    g_interruptedPrompt = g.testRunning;
    g_bootPrompt = g.rebootPending;

    bool redraw = true;
    while (appletMainLoop()) {
        padUpdate(&pad);
        const u64 k = padGetButtonsDown(&pad);

        if (redraw) {
            render();
            redraw = false;
        }

        if (g_bootPrompt) {
            if (k & HidNpadButton_A) {
                g.rebootPending = false;
                g_bootPrompt = false;
                g.pendingConfigMask = Config_None;
                if (g.stage == Stage::Preparation) {
                    g.stage = Stage::LowUvQuick;
                    g.stageReadyAfterBoot = false;
                } else {
                    g.stageReadyAfterBoot = true;
                }
                saveState();
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

        if (g_interruptedPrompt) {
            if (k & HidNpadButton_A) {
                g.testRunning = false;
                if (g.testStage >= 0 && g.testStage <= static_cast<int>(Stage::LowVminPlateauValidate))
                    g.stage = static_cast<Stage>(g.testStage);
                g.testKind = g.testDurationSec = g.testStage = 0;
                saveState();
                handleFail(false);
                g_interruptedPrompt = false;
                redraw = true;
            } else if (k & HidNpadButton_X) {
                g.testRunning = false;
                if (g.testStage >= 0 && g.testStage <= static_cast<int>(Stage::LowVminPlateauValidate))
                    g.stage = static_cast<Stage>(g.testStage);
                g.testKind = g.testDurationSec = g.testStage = 0;
                saveState();
                g_interruptedPrompt = false;
                redraw = true;
            } else if (k & HidNpadButton_B) {
                break;
            }
            svcSleepThread(20'000'000);
            continue;
        }

        if (g_configPrompt) {
            if (k & HidNpadButton_A) {
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

        if (g_rebootConfirm) {
            if (k & HidNpadButton_A) {
                g.pendingConfigMask = g_configCheck.mask;
                g.rebootPending = true;
                g_rebootConfirm = false;
                saveState();

                consoleClear();
                uiPrintf(6, "\x1b[32mSetting verified.\x1b[0m");
                uiPrintf(8, "Restarting console...");
                consoleUpdate(nullptr);
                svcSleepThread(400'000'000);

                g_rebootError = appletRequestToReboot();
                if (R_FAILED(g_rebootError)) {
                    g.rebootPending = false;
                    saveState();
                    consoleClear();
                    uiPrintf(5, "\x1b[31mAutomatic restart failed.\x1b[0m");
                    uiPrintf(7, "Result : 0x%08X", g_rebootError);
                    uiPrintf(9, "Restart CFW manually, then reopen Wizard.");
                    uiPrintf(11, "B : Exit");
                    consoleUpdate(nullptr);
                    while (appletMainLoop()) {
                        padUpdate(&pad);
                        if (padGetButtonsDown(&pad) & HidNpadButton_B) break;
                        svcSleepThread(20'000'000);
                    }
                    break;
                }
            } else if (k & HidNpadButton_B) {
                g_rebootConfirm = false;
                redraw = true;
            }
            svcSleepThread(20'000'000);
            continue;
        }

        if (g_overridePrompt) {
            if (k & HidNpadButton_A) {
                g_overridePrompt = false;
                if (g_overrideAction == PendingOverrideAction::VminProbe) runVminProbe();
                else runCurrentTest();
                redraw = true;
            } else if (k & HidNpadButton_B) {
                g_overridePrompt = false;
                redraw = true;
            }
            svcSleepThread(20'000'000);
            continue;
        }

        if (g_resultScreen) {
            if (k & HidNpadButton_A || k & HidNpadButton_B) {
                g_resultScreen = false;
                redraw = true;
            }
            svcSleepThread(20'000'000);
            continue;
        }

        if (g_resetConfirm) {
            if (k & HidNpadButton_A) {
                resetState();
                detectRamHardware();
                g_resetConfirm = false;
                redraw = true;
            } else if (k & HidNpadButton_B) {
                g_resetConfirm = false;
                redraw = true;
            }
            svcSleepThread(20'000'000);
            continue;
        }

        if (k & HidNpadButton_Minus) {
            g_resetConfirm = true;
            redraw = true;
        } else if (k & HidNpadButton_B) {
            saveState();
            break;
        } else if (g.stage == Stage::HardwareDetection) {
            if (k & HidNpadButton_A) {
                if (!g.ramDetected) detectRamHardware();
                else handlePass();
                redraw = true;
            }
        } else if (k & HidNpadButton_Plus) {
            if (isVminSweepStage(g.stage)) {
                runVminProbe();
            } else {
                stress::Kind skipKind;
                int skipSeconds = 0;
                if (testPlan(g.stage, skipKind, skipSeconds) || activeConfigMask() != Config_None) {
                    g_manualPass = true;
                    handlePass();
                    g_manualPass = false;
                }
            }
            redraw = true;
        } else if (k & HidNpadButton_X) {
            if (!isVminSweepStage(g.stage) && g.stage != Stage::Preparation && g.stage != Stage::Complete) {
                handleFail(false);
                redraw = true;
            }
        } else if (k & HidNpadButton_A) {
            const u32 cfgMask = activeConfigMask();
            if (cfgMask != Config_None) {
                if (verifyPersistentSettings(cfgMask)) g_rebootConfirm = true;
                else g_configPrompt = true;
            } else if (isVminSweepStage(g.stage)) {
                runVminProbe();
            } else {
                stress::Kind kind;
                int seconds = 0;
                if (testPlan(g.stage, kind, seconds)) runCurrentTest();
                else handlePass();
            }
            redraw = true;
        }

        svcSleepThread(20'000'000);
    }

    consoleExit(nullptr);
    return 0;
}''')

# The setup page itself is now verified/rebooted, so A no longer advances directly.
# Version is bumped here so generated NRO metadata/updater compare correctly.
make = Path('Makefile')
mt = make.read_text()
mt = mt.replace('APP_VERSION := 0.4.0-beta.15', 'APP_VERSION := 0.4.0-beta.16')
make.write_text(mt)

p.write_text(s)
print('beta16 guided flow transformation applied')
