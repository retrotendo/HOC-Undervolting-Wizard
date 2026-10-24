from pathlib import Path
import re

P = Path('source/main.cpp')
s = P.read_text()


def replace_once(old, new):
    global s
    if old not in s:
        raise SystemExit(f'pattern not found: {old[:120]!r}')
    s = s.replace(old, new, 1)


def replace_function(signature, new_text):
    global s
    start = s.find(signature)
    if start < 0:
        raise SystemExit(f'function not found: {signature}')
    brace = s.find('{', start)
    if brace < 0:
        raise SystemExit(f'opening brace not found: {signature}')
    depth = 0
    in_str = False
    in_char = False
    esc = False
    i = brace
    while i < len(s):
        c = s[i]
        if esc:
            esc = False
        elif c == '\\' and (in_str or in_char):
            esc = True
        elif c == '"' and not in_char:
            in_str = not in_str
        elif c == "'" and not in_str:
            in_char = not in_char
        elif not in_str and not in_char:
            if c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    s = s[:start] + new_text.rstrip() + '\n' + s[end:]
                    return
        i += 1
    raise SystemExit(f'closing brace not found: {signature}')


# ---------------------------------------------------------------------------
# Constants + persistent state
# ---------------------------------------------------------------------------
replace_once(
    'constexpr int STOCK_VDDQ_MV = 600;\nconstexpr int STOCK_VDD2_UV = 1175000;',
    'constexpr int STOCK_VDDQ_MV = 600;\nconstexpr int ALT_VDDQ_MV = 640;\nconstexpr int STOCK_VDD2_UV = 1175000;\n'
    'constexpr u32 PREP_RAM_MAX_KHZ = 1600000U;\n'
    'constexpr u32 PREP_CPU_MAX_KHZ = 1963500U;\n'
    'constexpr u32 PREP_CPU_BOOST_KHZ = 1785000U;\n'
    'constexpr int PREP_CPU_TABLE = 3; // 1683 MHz Tbreak\n'
    'constexpr int VMIN_SWEEP_POINT_COUNT = 6;'
)

start = s.index('struct WizardState {')
end_marker = '\n};\n\nWizardState g;'
end = s.index(end_marker, start) + len('\n};')
new_state = r'''struct WizardState {
    Stage stage = Stage::Preparation;
    int lowUvGood = STOCK_LOW_UV;
    int lowUvTest = 1;
    int lowVminGood = STOCK_LOW_VMIN_MV;
    int lowVminTest = STOCK_LOW_VMIN_MV - LOW_VMIN_STEP_MV;
    int vddqStartMv = STOCK_VDDQ_MV;
    int vddqGood = STOCK_VDDQ_MV;
    int vddqTest = STOCK_VDDQ_MV - VDDQ_STEP_MV;
    int vdd2GoodUv = STOCK_VDD2_UV;
    int vdd2TestUv = STOCK_VDD2_UV - VDD2_STEP_UV;
    int highUvGood = STOCK_HIGH_UV;
    int highUvTest = 1;

    bool ramDetectionDone = false;
    bool ramDetectionConfirmed = false;
    int dramId = -1;

    // Last persistent tuning combination confirmed after a normal boot.
    bool bootConfigKnown = false;
    int bootLowUv = STOCK_LOW_UV;
    int bootLowVmin = STOCK_LOW_VMIN_MV;
    int bootVddq = STOCK_VDDQ_MV;
    int bootVdd2Uv = STOCK_VDD2_UV;
    int bootHighUv = STOCK_HIGH_UV;
    bool awaitingBootConfirm = false;

    // CPU voltage plateaus discovered by the automatic 510..1020 MHz scan.
    int vminPlateauCount = 0;
    int vminPlateauIndex = 0;
    u32 vminPlateauHz[VMIN_SWEEP_POINT_COUNT] = {};
    int vminPlateauMv[VMIN_SWEEP_POINT_COUNT] = {};
    u32 vminFloorHz = 0;
    int vminFloorObservedMv = 0;

    // Preserve whatever temporary overrides the user had before managed tests.
    bool savedOverrideValid = false;
    u32 savedOverrideHz[3] = {};

    int ramPairRetryMode = 0;
    bool recoveryNeeded = false;
    bool warningBelow590Seen = false;

    bool testRunning = false;
    int testKind = 0;
    int testDurationSec = 0;
    int testStage = 0;
};'''
s = s[:start] + new_state + s[end:]

replace_once(
    'bool g_manualPass = false;\nbool g_lastVminAtFloor = false;',
    'bool g_manualPass = false;\n'
    'bool g_configVerified = false;\n'
    'bool g_forceConfigPage = false;\n'
    'HocMonConfig g_configRead{};\n'
    'Result g_configRc = 0;\n'
    'Result g_hwRc = 0;\n'
    'bool g_flowErrorScreen = false;\n'
    'std::string g_flowError;'
)

# ---------------------------------------------------------------------------
# Dynamic plateau target for the long CPU validation.
# ---------------------------------------------------------------------------
replace_once(
    '        case Stage::LowVminFinalLong:\n            e = {g.vminFloorHz ? g.vminFloorHz : CLOCK_CPU_VMIN_510_HZ,\n                 CLOCK_GPU_NORMAL_HZ, CLOCK_RAM_NORMAL_HZ};\n            return true;',
    '        case Stage::LowVminFinalLong: {\n'
    '            const int idx = (g.vminPlateauIndex >= 0 && g.vminPlateauIndex < g.vminPlateauCount) ? g.vminPlateauIndex : 0;\n'
    '            const u32 hz = (g.vminPlateauCount > 0 && g.vminPlateauHz[idx]) ? g.vminPlateauHz[idx] : CLOCK_CPU_VMIN_510_HZ;\n'
    '            e = {hz, CLOCK_GPU_NORMAL_HZ, CLOCK_RAM_NORMAL_HZ};\n'
    '            return true;\n'
    '        }'
)

# Remove the old manual floor sample helper; beta16 uses managed overrides and a
# visible scan instead.
replace_function('bool sampleVminVoltage(Stage s)', r'''bool sampleVminVoltage(Stage s) {
    (void)s;
    return false;
}''')

# ---------------------------------------------------------------------------
# Extended state persistence.
# ---------------------------------------------------------------------------
replace_function('bool saveState()', r'''bool saveState() {
    ensureDir();
    std::ofstream f(STATE_TMP, std::ios::trunc);
    if (!f) return false;
    f << "stage=" << static_cast<int>(g.stage) << "\n";
    f << "lowUvGood=" << g.lowUvGood << "\n";
    f << "lowUvTest=" << g.lowUvTest << "\n";
    f << "lowVminGood=" << g.lowVminGood << "\n";
    f << "lowVminTest=" << g.lowVminTest << "\n";
    f << "vddqStartMv=" << g.vddqStartMv << "\n";
    f << "vddqGood=" << g.vddqGood << "\n";
    f << "vddqTest=" << g.vddqTest << "\n";
    f << "vdd2GoodUv=" << g.vdd2GoodUv << "\n";
    f << "vdd2TestUv=" << g.vdd2TestUv << "\n";
    f << "highUvGood=" << g.highUvGood << "\n";
    f << "highUvTest=" << g.highUvTest << "\n";
    f << "ramDetectionDone=" << (g.ramDetectionDone ? 1 : 0) << "\n";
    f << "ramDetectionConfirmed=" << (g.ramDetectionConfirmed ? 1 : 0) << "\n";
    f << "dramId=" << g.dramId << "\n";
    f << "bootConfigKnown=" << (g.bootConfigKnown ? 1 : 0) << "\n";
    f << "bootLowUv=" << g.bootLowUv << "\n";
    f << "bootLowVmin=" << g.bootLowVmin << "\n";
    f << "bootVddq=" << g.bootVddq << "\n";
    f << "bootVdd2Uv=" << g.bootVdd2Uv << "\n";
    f << "bootHighUv=" << g.bootHighUv << "\n";
    f << "awaitingBootConfirm=" << (g.awaitingBootConfirm ? 1 : 0) << "\n";
    f << "vminPlateauCount=" << g.vminPlateauCount << "\n";
    f << "vminPlateauIndex=" << g.vminPlateauIndex << "\n";
    for (int i = 0; i < VMIN_SWEEP_POINT_COUNT; ++i) {
        f << "vminPlateauHz" << i << "=" << g.vminPlateauHz[i] << "\n";
        f << "vminPlateauMv" << i << "=" << g.vminPlateauMv[i] << "\n";
    }
    f << "vminFloorHz=" << g.vminFloorHz << "\n";
    f << "vminFloorObservedMv=" << g.vminFloorObservedMv << "\n";
    f << "savedOverrideValid=" << (g.savedOverrideValid ? 1 : 0) << "\n";
    for (int i = 0; i < 3; ++i) f << "savedOverrideHz" << i << "=" << g.savedOverrideHz[i] << "\n";
    f << "ramPairRetryMode=" << g.ramPairRetryMode << "\n";
    f << "recoveryNeeded=" << (g.recoveryNeeded ? 1 : 0) << "\n";
    f << "warningBelow590Seen=" << (g.warningBelow590Seen ? 1 : 0) << "\n";
    f << "testRunning=" << (g.testRunning ? 1 : 0) << "\n";
    f << "testKind=" << g.testKind << "\n";
    f << "testDurationSec=" << g.testDurationSec << "\n";
    f << "testStage=" << g.testStage << "\n";
    f.flush();
    f.close();
    if (access(STATE, F_OK) == 0) remove(STATE);
    return rename(STATE_TMP, STATE) == 0;
}''')

replace_function('void assignKV(const std::string& key, const std::string& value)', r'''void assignKV(const std::string& key, const std::string& value) {
    const long long sv = std::strtoll(value.c_str(), nullptr, 10);
    const unsigned long long uv = std::strtoull(value.c_str(), nullptr, 10);
    const int v = (int)sv;
    if (key == "stage") g.stage = static_cast<Stage>(v);
    else if (key == "lowUvGood") g.lowUvGood = v;
    else if (key == "lowUvTest") g.lowUvTest = v;
    else if (key == "lowVminGood") g.lowVminGood = v;
    else if (key == "lowVminTest") g.lowVminTest = v;
    else if (key == "vddqStartMv") g.vddqStartMv = v;
    else if (key == "vddqGood") g.vddqGood = v;
    else if (key == "vddqTest") g.vddqTest = v;
    else if (key == "vdd2GoodUv") g.vdd2GoodUv = v;
    else if (key == "vdd2TestUv") g.vdd2TestUv = v;
    else if (key == "highUvGood") g.highUvGood = v;
    else if (key == "highUvTest") g.highUvTest = v;
    else if (key == "ramDetectionDone") g.ramDetectionDone = (v != 0);
    else if (key == "ramDetectionConfirmed") g.ramDetectionConfirmed = (v != 0);
    else if (key == "dramId") g.dramId = v;
    else if (key == "bootConfigKnown") g.bootConfigKnown = (v != 0);
    else if (key == "bootLowUv") g.bootLowUv = v;
    else if (key == "bootLowVmin") g.bootLowVmin = v;
    else if (key == "bootVddq") g.bootVddq = v;
    else if (key == "bootVdd2Uv") g.bootVdd2Uv = v;
    else if (key == "bootHighUv") g.bootHighUv = v;
    else if (key == "awaitingBootConfirm") g.awaitingBootConfirm = (v != 0);
    else if (key == "vminPlateauCount") g.vminPlateauCount = v;
    else if (key == "vminPlateauIndex") g.vminPlateauIndex = v;
    else if (key == "vminFloorHz") g.vminFloorHz = (u32)uv;
    else if (key == "vminFloorObservedMv") g.vminFloorObservedMv = v;
    else if (key == "savedOverrideValid") g.savedOverrideValid = (v != 0);
    else if (key == "ramPairRetryMode") g.ramPairRetryMode = v;
    else if (key == "recoveryNeeded") g.recoveryNeeded = (v != 0);
    else if (key == "warningBelow590Seen") g.warningBelow590Seen = (v != 0);
    else if (key == "testRunning") g.testRunning = (v != 0);
    else if (key == "testKind") g.testKind = v;
    else if (key == "testDurationSec") g.testDurationSec = v;
    else if (key == "testStage") g.testStage = v;
    else {
        for (int i = 0; i < VMIN_SWEEP_POINT_COUNT; ++i) {
            if (key == "vminPlateauHz" + std::to_string(i)) { g.vminPlateauHz[i] = (u32)uv; return; }
            if (key == "vminPlateauMv" + std::to_string(i)) { g.vminPlateauMv[i] = v; return; }
        }
        for (int i = 0; i < 3; ++i)
            if (key == "savedOverrideHz" + std::to_string(i)) { g.savedOverrideHz[i] = (u32)uv; return; }
    }
}''')

replace_function('bool loadState()', r'''bool loadState() {
    std::ifstream f(STATE);
    if (!f) return false;
    std::string line;
    while (std::getline(f, line)) {
        const auto p = line.find('=');
        if (p != std::string::npos) assignKV(line.substr(0, p), line.substr(p + 1));
    }
    if (g.lowVminGood < LOW_VMIN_MIN_MV) g.lowVminGood = LOW_VMIN_MIN_MV;
    if (g.lowVminTest < LOW_VMIN_MIN_MV) g.lowVminTest = LOW_VMIN_MIN_MV;
    if (g.vddqStartMv != STOCK_VDDQ_MV && g.vddqStartMv != ALT_VDDQ_MV) g.vddqStartMv = STOCK_VDDQ_MV;
    if (g.vminPlateauCount < 0 || g.vminPlateauCount > VMIN_SWEEP_POINT_COUNT) g.vminPlateauCount = 0;
    if (g.vminPlateauIndex < 0 || g.vminPlateauIndex >= VMIN_SWEEP_POINT_COUNT) g.vminPlateauIndex = 0;
    // beta.15 manual sweep states are migrated to the new automatic mapper.
    if (g.stage == Stage::LowVminSweep612 || g.stage == Stage::LowVminSweep714 ||
        g.stage == Stage::LowVminValidate816 || g.stage == Stage::LowVminSweep918 ||
        g.stage == Stage::LowVminValidate1020) {
        g.stage = Stage::LowVminLong;
        g.vminPlateauCount = 0;
        g.vminPlateauIndex = 0;
    }
    return true;
}''')

# ---------------------------------------------------------------------------
# Hardware detection, desired HOC config, reboot state, managed overrides.
# Insert after formatClock().
# ---------------------------------------------------------------------------
insert_at = s.index('bool checkAllOverrides(Stage s)')
helpers = r'''
struct DesiredConfig {
    bool uncappedClocks = false;
    bool hpMode = false;
    u32 ramMaxKHz = PREP_RAM_MAX_KHZ;
    u32 vdd2Uv = STOCK_VDD2_UV;
    int vddqMv = STOCK_VDDQ_MV;
    int lowUv = STOCK_LOW_UV;
    int highUv = STOCK_HIGH_UV;
    int tableConf = PREP_CPU_TABLE;
    int lowVminMv = STOCK_LOW_VMIN_MV;
    int highVminMv = STOCK_HIGH_VMIN_MV;
    u32 cpuMaxKHz = PREP_CPU_MAX_KHZ;
    u32 cpuBoostKHz = PREP_CPU_BOOST_KHZ;
};

const char* ramNameFromId(int id) {
    switch (id) {
        case 3: case 5: case 6: return "NEE 4GB";
        case 8: case 12: return "AM-MGCJ 4GB";
        case 9: case 13: return "AM-MGCJ 8GB";
        case 10: case 14: return "NME 4GB";
        case 11: case 15: return "WT:E 4GB";
        case 17: case 19: case 24: return "AA-MGCL 4GB";
        case 18: case 23: case 28: return "AA-MGCL 8GB";
        case 20: case 21: case 22: return "AB-MGCL 4GB";
        case 25: case 26: case 27: return "WT:F 4GB";
        case 29: case 30: case 31: return "x267 4GB";
        case 32: case 33: case 34: return "WT:B 4GB";
        default: return "Unknown";
    }
}

int vddqStartForDramId(int id) {
    switch (id) {
        case 11: case 15:
        case 25: case 26: case 27:
        case 32: case 33: case 34:
            return 600;
        case 3: case 5: case 6:
        case 8: case 9: case 10: case 12: case 13: case 14:
        case 17: case 18: case 19: case 20: case 21: case 22: case 23: case 24:
        case 28: case 29: case 30: case 31:
            return 640;
        default:
            return 0;
    }
}

void applyDetectedVddqStart(int mv) {
    g.vddqStartMv = mv;
    if (g.stage == Stage::Preparation) {
        g.vddqGood = mv;
        g.vddqTest = mv - VDDQ_STEP_MV;
    }
}

void detectRamIfNeeded() {
    if (g.ramDetectionDone) return;
    HocMonHardware hw{};
    g_hwRc = hocmonGetHardware(&hw);
    if (R_FAILED(g_hwRc)) return;
    g.dramId = hw.dramId;
    g.ramDetectionDone = true;
    const int startMv = vddqStartForDramId(g.dramId);
    if (startMv) applyDetectedVddqStart(startMv);
    saveState();
}

bool desiredConfigForStage(Stage st, DesiredConfig& d) {
    d = DesiredConfig{};
    d.vddqMv = g.vddqStartMv;

    switch (st) {
        case Stage::Preparation:
            return true;
        case Stage::LowUvQuick:
            d.lowUv = g.lowUvTest;
            return true;
        case Stage::LowUvLong:
            d.lowUv = g.lowUvGood;
            return true;
        case Stage::LowVminQuick:
            d.lowUv = g.lowUvGood;
            d.lowVminMv = g.lowVminTest;
            return true;
        case Stage::LowVminLong:
        case Stage::LowVminSweep612:
        case Stage::LowVminSweep714:
        case Stage::LowVminValidate816:
        case Stage::LowVminSweep918:
        case Stage::LowVminValidate1020:
        case Stage::LowVminFinalLong:
            d.lowUv = g.lowUvGood;
            d.lowVminMv = g.lowVminGood;
            return true;
        case Stage::VddqQuick:
            d.lowUv = g.lowUvGood; d.lowVminMv = g.lowVminGood;
            d.vddqMv = g.vddqTest;
            return true;
        case Stage::VddqLong:
            d.lowUv = g.lowUvGood; d.lowVminMv = g.lowVminGood;
            d.vddqMv = g.vddqGood;
            return true;
        case Stage::Vdd2Quick:
            d.lowUv = g.lowUvGood; d.lowVminMv = g.lowVminGood;
            d.vddqMv = g.vddqGood; d.vdd2Uv = g.vdd2TestUv;
            return true;
        case Stage::Vdd2Long:
        case Stage::RamBoostValidate:
        case Stage::Ram1331Validate:
            d.lowUv = g.lowUvGood; d.lowVminMv = g.lowVminGood;
            d.vddqMv = g.vddqGood; d.vdd2Uv = g.vdd2GoodUv;
            return true;
        case Stage::HighUvQuick:
            d.lowUv = g.lowUvGood; d.lowVminMv = g.lowVminGood;
            d.vddqMv = g.vddqGood; d.vdd2Uv = g.vdd2GoodUv;
            d.highUv = g.highUvTest;
            return true;
        case Stage::HighUvLong:
        case Stage::BoostCpuRamValidate:
        case Stage::NormalMatrixValidate:
        case Stage::NormalMemValidate:
        case Stage::NormalGpuValidate:
        case Stage::BoostMatrixValidate:
        case Stage::BoostMemValidate:
        case Stage::BoostCpuMemValidate:
        case Stage::RealWorldValidate:
        case Stage::Complete:
            d.lowUv = g.lowUvGood; d.lowVminMv = g.lowVminGood;
            d.vddqMv = g.vddqGood; d.vdd2Uv = g.vdd2GoodUv;
            d.highUv = g.highUvGood;
            return true;
    }
    return false;
}

bool configMatches(const HocMonConfig& c, const DesiredConfig& d) {
    return c.uncappedClocks == d.uncappedClocks &&
           c.hpMode == d.hpMode &&
           c.ramMaxKHz == d.ramMaxKHz &&
           c.vdd2Uv == d.vdd2Uv &&
           c.vddqUv == (u32)d.vddqMv * 1000U &&
           c.lowUv == d.lowUv && c.highUv == d.highUv &&
           c.tableConf == d.tableConf &&
           c.lowVminMv == d.lowVminMv && c.highVminMv == d.highVminMv &&
           c.cpuMaxKHz == d.cpuMaxKHz && c.cpuBoostKHz == d.cpuBoostKHz;
}

bool verifyConfigForStage(Stage st) {
    DesiredConfig d{};
    if (!desiredConfigForStage(st, d)) return true;
    g_configRc = hocmonGetConfig(&g_configRead);
    if (R_FAILED(g_configRc)) return false;
    return configMatches(g_configRead, d);
}

bool bootTokenMatches(Stage st) {
    if (!g.bootConfigKnown) return false;
    DesiredConfig d{};
    if (!desiredConfigForStage(st, d)) return true;
    return g.bootLowUv == d.lowUv && g.bootLowVmin == d.lowVminMv &&
           g.bootVddq == d.vddqMv && g.bootVdd2Uv == (int)d.vdd2Uv &&
           g.bootHighUv == d.highUv;
}

void markBootToken(Stage st) {
    DesiredConfig d{};
    if (!desiredConfigForStage(st, d)) return;
    g.bootConfigKnown = true;
    g.bootLowUv = d.lowUv;
    g.bootLowVmin = d.lowVminMv;
    g.bootVddq = d.vddqMv;
    g.bootVdd2Uv = (int)d.vdd2Uv;
    g.bootHighUv = d.highUv;
}

std::string primarySettingText(Stage st) {
    char b[96];
    switch (st) {
        case Stage::Preparation:
            return "All preparation settings were set correctly.";
        case Stage::LowUvQuick: std::snprintf(b, sizeof(b), "Low UV %d was set correctly.", g.lowUvTest); break;
        case Stage::LowUvLong: std::snprintf(b, sizeof(b), "Low UV %d was set correctly.", g.lowUvGood); break;
        case Stage::LowVminQuick: std::snprintf(b, sizeof(b), "Low VMIN %d mV was set correctly.", g.lowVminTest); break;
        case Stage::LowVminLong: std::snprintf(b, sizeof(b), "Low VMIN %d mV was set correctly.", g.lowVminGood); break;
        case Stage::VddqQuick: std::snprintf(b, sizeof(b), "VDDQ %d mV was set correctly.", g.vddqTest); break;
        case Stage::VddqLong: std::snprintf(b, sizeof(b), "VDDQ %d mV was set correctly.", g.vddqGood); break;
        case Stage::Vdd2Quick: std::snprintf(b, sizeof(b), "VDD2 %s was set correctly.", formatVdd2(g.vdd2TestUv).c_str()); break;
        case Stage::Vdd2Long: std::snprintf(b, sizeof(b), "VDD2 %s was set correctly.", formatVdd2(g.vdd2GoodUv).c_str()); break;
        case Stage::HighUvQuick: std::snprintf(b, sizeof(b), "High UV %d was set correctly.", g.highUvTest); break;
        case Stage::HighUvLong: std::snprintf(b, sizeof(b), "High UV %d was set correctly.", g.highUvGood); break;
        default: return "Required Horizon OC settings were set correctly.";
    }
    return b;
}

bool shouldShowConfigPage() {
    if (g.stage == Stage::Complete || g.recoveryNeeded || g.awaitingBootConfirm) return false;
    if (g.stage == Stage::Preparation) return g_forceConfigPage;
    return g_forceConfigPage || !bootTokenMatches(g.stage);
}

bool saveCurrentOverrides() {
    if (g.savedOverrideValid) return true;
    HocMonClocks c{};
    if (R_FAILED(hocmonGetClocks(&c))) return false;
    for (int i = 0; i < 3; ++i) g.savedOverrideHz[i] = c.overrideHz[i];
    g.savedOverrideValid = true;
    saveState();
    return true;
}

void restoreSavedOverrides() {
    if (!g.savedOverrideValid) return;
    if (R_FAILED(hocmonSetOverrides(g.savedOverrideHz[0], g.savedOverrideHz[1], g.savedOverrideHz[2]))) return;
    g.savedOverrideValid = false;
    for (int i = 0; i < 3; ++i) g.savedOverrideHz[i] = 0;
    saveState();
}

bool managedOverrideReady(const OverrideExpectation& e) {
    if (!saveCurrentOverrides()) return false;
    if (R_FAILED(hocmonSetOverrides(e.cpuHz, e.gpuHz, e.ramHz))) {
        restoreSavedOverrides();
        return false;
    }
    svcSleepThread(700'000'000);
    HocMonClocks c{};
    if (R_FAILED(hocmonGetClocks(&c)) ||
        !clockMatches(c.overrideHz[0], e.cpuHz) || !clockMatches(c.targetHz[0], e.cpuHz) ||
        !clockMatches(c.overrideHz[1], e.gpuHz) || !clockMatches(c.overrideHz[2], e.ramHz)) {
        restoreSavedOverrides();
        return false;
    }
    return true;
}

'''
s = s[:insert_at] + helpers + s[insert_at:]

# ---------------------------------------------------------------------------
# Results include RAM + all detected voltage plateaus.
# ---------------------------------------------------------------------------
replace_function('void writeResults()', r'''void writeResults() {
    ensureDir();
    std::ofstream f(RESULTS, std::ios::trunc);
    if (!f) return;
    f << "HOC Undervolting Wizard - Final Results\n\n";
    f << "RAM module: " << ramNameFromId(g.dramId) << " (ID " << g.dramId << ")\n";
    f << "RAM VDDQ start: " << g.vddqStartMv << " mV\n";
    f << "CPU UV Table: 1683 MHz Tbreak\n";
    f << "CPU Low UV: " << g.lowUvGood << "\n";
    f << "CPU Low VMIN: " << g.lowVminGood << " mV\n";
    f << "RAM VDDQ: " << g.vddqGood << " mV\n";
    f << "RAM VDD2: " << formatVdd2(g.vdd2GoodUv) << "\n";
    f << "CPU High UV: " << g.highUvGood << "\n";
    if (g.vminPlateauCount > 0) {
        f << "\nDetected CPU voltage plateaus (highest clock validated):\n";
        for (int i = 0; i < g.vminPlateauCount; ++i)
            f << "  " << (g.vminPlateauHz[i] / 1000000U) << " MHz @ ~" << g.vminPlateauMv[i] << " mV\n";
    }
    f << "\nBuilt-in CPU/RAM/combined/GPU validation completed.\n";
    f << "Normal handheld target: 1020 / 384 / 1331.\n";
    f << "Nintendo Boost target: 1785 / 76.8 / 1600.\n";
}''')

# ---------------------------------------------------------------------------
# UI: hardware detection, config verification/reboot, boot check, clean tests.
# ---------------------------------------------------------------------------
replace_function('void footerTest(int row)', r'''void footerTest(int row) {
    uiPrintf(row,     "Keys:");
    uiPrintf(row + 1, "A : Start Test");
    uiPrintf(row + 2, "+ : Known PASS / Skip");
    uiPrintf(row + 3, "X : Known FAIL / Skip");
    uiPrintf(row + 4, "B : Exit    - : Reset");
}''')

replace_function('void renderPreparation()', r'''void renderPreparation() {
    title();
    uiPrintf(5, "RAM detected: %s", ramNameFromId(g.dramId));
    uiPrintf(6, "VDDQ start : %d mV", g.vddqStartMv);
    uiPrintf(8, "@ Horizon OC");
    uiPrintf(10, "General:");
    uiPrintf(11, " - Uncapped Clocks : OFF");
    uiPrintf(13, "RAM Settings:");
    uiPrintf(14, " - HP Mode         : OFF");
    uiPrintf(15, " - RAM Max         : 1600 MHz");
    uiPrintf(16, " - VDD2            : 1175 mV");
    uiPrintf(17, " - VDDQ            : %d mV", g.vddqStartMv);
    uiPrintf(19, "CPU Settings:");
    uiPrintf(20, " - CPU Max         : 1963 MHz");
    uiPrintf(21, " - Low VMIN        : 620 mV");
    uiPrintf(22, " - High VMIN       : 750 mV");
    uiPrintf(23, " - UV Table        : 1683 MHz Tbreak");
    uiPrintf(24, " - Low UV          : 0");
    uiPrintf(25, " - High UV         : 0");
    uiPrintf(27, "@ HOC Toolkit");
    uiPrintf(28, " - CPU Boost       : 1785 MHz");
    uiPrintf(30, "A : Verify settings");
    uiPrintf(31, "B : Exit    - : Reset");
}''')

replace_function('void renderTestStage()', r'''void renderTestStage() {
    title();

    if (g.stage == Stage::LowVminLong) {
        uiPrintf(5, "CPU Voltage Mapping");
        uiPrintf(7, "The app will find the CPU voltage plateaus");
        uiPrintf(8, "automatically from 510 to 1020 MHz.");
        uiPrintf(10, "Managed temporary overrides:");
        uiPrintf(11, " - CPU : 510 -> 1020 MHz");
        uiPrintf(12, " - GPU : 384 MHz");
        uiPrintf(13, " - RAM : 1331.2 MHz");
        uiPrintf(15, "No manual override changes are required.");
        uiPrintf(17, "A : Start automatic scan");
        uiPrintf(18, "B : Exit");
        return;
    }

    stress::Kind kind;
    int seconds = 0;
    const bool hasTest = testPlan(g.stage, kind, seconds);
    OverrideExpectation expected{};
    const bool hasOverrides = overridePlan(g.stage, expected);
    int row = 5;

    if (g.stage == Stage::LowVminFinalLong) {
        uiPrintf(row++, "Detected CPU voltage plateaus:");
        for (int i = 0; i < g.vminPlateauCount && row < 15; ++i)
            uiPrintf(row++, " - %s @ ~%d mV", formatClock(g.vminPlateauHz[i]).c_str(), g.vminPlateauMv[i]);
        row++;
        const int idx = (g.vminPlateauIndex < g.vminPlateauCount) ? g.vminPlateauIndex : 0;
        uiPrintf(row++, "Validation %d / %d", idx + 1, g.vminPlateauCount);
        if (g.vminPlateauCount > 0)
            uiPrintf(row++, "CPU : %s @ ~%d mV", formatClock(g.vminPlateauHz[idx]).c_str(), g.vminPlateauMv[idx]);
        uiPrintf(row++, "Overrides: managed automatically");
    } else {
        uiPrintf(row++, "@ Horizon OC");
        row++;
        if (hasOverrides) {
            printOverrides(row, expected);
            row += 5;
        }
    }

    if (hasTest) {
        uiPrintf(row++, "Test:");
        uiPrintf(row++, "%s - %s", seconds == 60 ? "1 min" : "1 hour", compactTestName(kind));
        footerTest(row + 1);
    }
}''')

# Insert new render helpers before renderResultScreen.
idx = s.index('void renderResultScreen()')
ui_helpers = r'''
void renderHardwareDetection() {
    consoleClear();
    uiPrintf(1, "\x1b[36mBattery Wizard\x1b[0m");
    uiPrintf(2, "Hardware Detection");
    uiPrintf(3, "----------------------------------------");
    if (!g.ramDetectionDone) {
        uiPrintf(6, "Reading RAM module from Horizon OC...");
        if (R_FAILED(g_hwRc)) uiPrintf(8, "Last read failed: 0x%08X", g_hwRc);
        uiPrintf(11, "A : Retry detection");
        uiPrintf(12, "B : Exit");
        return;
    }
    uiPrintf(6, "RAM detected:");
    uiPrintf(7, "\x1b[32m%s\x1b[0m", ramNameFromId(g.dramId));
    uiPrintf(8, "DRAM ID: %d", g.dramId);
    if (g.vddqStartMv == 600 || g.vddqStartMv == 640) {
        uiPrintf(10, "Recommended VDDQ start:");
        uiPrintf(11, "\x1b[32m%d mV\x1b[0m", g.vddqStartMv);
        uiPrintf(14, "A : Continue to Preparation");
    } else {
        uiPrintf(10, "RAM ID is not in the Mariko VDDQ table.");
        uiPrintf(12, "A : Use 600 mV (WT:B / WT:E / WT:F)");
        uiPrintf(13, "X : Use 640 mV (NEE/x267/AA/AM/AB/NME)");
    }
    uiPrintf(16, "B : Exit");
}

void printConfigMismatchLine(int& row, const char* label, const std::string& required, const std::string& current) {
    uiPrintf(row++, "%s", label);
    uiPrintf(row++, "  Required : %s", required.c_str());
    uiPrintf(row++, "  Current  : %s", current.c_str());
    uiPrintf(row++, "  Status   : \x1b[31mWRONG\x1b[0m");
}

void renderConfigSetPage() {
    title();
    DesiredConfig d{};
    desiredConfigForStage(g.stage, d);
    g_configRc = hocmonGetConfig(&g_configRead);
    if (R_FAILED(g_configRc)) {
        uiPrintf(6, "Could not read Horizon OC settings.");
        uiPrintf(7, "Result: 0x%08X", g_configRc);
        uiPrintf(10, "A : Check again");
        uiPrintf(11, "B : Exit");
        return;
    }

    int row = 5;
    uiPrintf(row++, "Set the values shown below:");
    row++;
    if (g_configRead.uncappedClocks != d.uncappedClocks)
        printConfigMismatchLine(row, "General - Uncapped Clocks", d.uncappedClocks ? "ON" : "OFF", g_configRead.uncappedClocks ? "ON" : "OFF");
    if (g_configRead.hpMode != d.hpMode)
        printConfigMismatchLine(row, "RAM Settings - HP Mode", d.hpMode ? "ON" : "OFF", g_configRead.hpMode ? "ON" : "OFF");
    if (g_configRead.ramMaxKHz != d.ramMaxKHz)
        printConfigMismatchLine(row, "RAM Settings - RAM Max", std::to_string(d.ramMaxKHz / 1000) + " MHz", std::to_string(g_configRead.ramMaxKHz / 1000) + " MHz");
    if (g_configRead.vdd2Uv != d.vdd2Uv)
        printConfigMismatchLine(row, "RAM Settings - VDD2", formatVdd2((int)d.vdd2Uv), formatVdd2((int)g_configRead.vdd2Uv));
    if (g_configRead.vddqUv != (u32)d.vddqMv * 1000U)
        printConfigMismatchLine(row, "RAM Settings - VDDQ", std::to_string(d.vddqMv) + " mV", std::to_string(g_configRead.vddqUv / 1000U) + " mV");
    if (g_configRead.cpuMaxKHz != d.cpuMaxKHz)
        printConfigMismatchLine(row, "CPU Settings - CPU Max", std::to_string(d.cpuMaxKHz / 1000U) + " MHz", std::to_string(g_configRead.cpuMaxKHz / 1000U) + " MHz");
    if (g_configRead.lowVminMv != d.lowVminMv)
        printConfigMismatchLine(row, "CPU Settings - Low VMIN", std::to_string(d.lowVminMv) + " mV", std::to_string(g_configRead.lowVminMv) + " mV");
    if (g_configRead.highVminMv != d.highVminMv)
        printConfigMismatchLine(row, "CPU Settings - High VMIN", std::to_string(d.highVminMv) + " mV", std::to_string(g_configRead.highVminMv) + " mV");
    if (g_configRead.tableConf != d.tableConf)
        printConfigMismatchLine(row, "CPU Settings - UV Table", "1683 MHz Tbreak", std::to_string(g_configRead.tableConf));
    if (g_configRead.lowUv != d.lowUv)
        printConfigMismatchLine(row, "CPU Settings - Low UV", std::to_string(d.lowUv), std::to_string(g_configRead.lowUv));
    if (g_configRead.highUv != d.highUv)
        printConfigMismatchLine(row, "CPU Settings - High UV", std::to_string(d.highUv), std::to_string(g_configRead.highUv));
    if (g_configRead.cpuBoostKHz != d.cpuBoostKHz)
        printConfigMismatchLine(row, "@ HOC Toolkit - CPU Boost", std::to_string(d.cpuBoostKHz / 1000U) + " MHz", std::to_string(g_configRead.cpuBoostKHz / 1000U) + " MHz");

    if (configMatches(g_configRead, d)) {
        uiPrintf(row++, "All required values currently match.");
    }
    row++;
    uiPrintf(row++, "A : Check settings");
    uiPrintf(row++, "B : Exit");
}

void renderConfigVerified() {
    title();
    uiPrintf(7, "\x1b[32m%s\x1b[0m", primarySettingText(g.stage).c_str());
    uiPrintf(10, "A : Restart console");
    uiPrintf(11, "B : Back");
}

void renderBootConfirm() {
    consoleClear();
    uiPrintf(1, "\x1b[36mBattery Wizard\x1b[0m");
    uiPrintf(2, "Boot Check");
    uiPrintf(3, "----------------------------------------");
    uiPrintf(7, "Did the console boot normally");
    uiPrintf(8, "with the new setting?");
    uiPrintf(11, "A : YES - Continue");
    uiPrintf(12, "X : NO  - Recovery");
    uiPrintf(13, "B : Exit");
}

void renderRecoveryPage() {
    title();
    uiPrintf(5, "\x1b[31mThe previous setting did not boot.\x1b[0m");
    uiPrintf(7, "Recovery:");
    uiPrintf(8, " - Boot Hekate without hoc.kip");
    uiPrintf(9, " - Open Horizon OC and restore the value shown");
    DesiredConfig d{};
    desiredConfigForStage(g.stage, d);
    switch (g.stage) {
        case Stage::LowUvLong: uiPrintf(11, "CPU Settings - Low UV : %d", d.lowUv); break;
        case Stage::LowVminLong: uiPrintf(11, "CPU Settings - Low VMIN : %d mV", d.lowVminMv); break;
        case Stage::VddqLong: uiPrintf(11, "RAM Settings - VDDQ : %d mV", d.vddqMv); break;
        case Stage::Vdd2Long: uiPrintf(11, "RAM Settings - VDD2 : %s", formatVdd2((int)d.vdd2Uv).c_str()); break;
        case Stage::HighUvLong: uiPrintf(11, "CPU Settings - High UV : %d", d.highUv); break;
        default: uiPrintf(11, "Restore the safer value shown by the Wizard."); break;
    }
    uiPrintf(14, "A : Restart after restoring");
    uiPrintf(15, "B : Exit");
}

void renderFlowError() {
    consoleClear();
    uiPrintf(1, "\x1b[31mBattery Wizard - ACTION FAILED\x1b[0m");
    uiPrintf(3, "----------------------------------------");
    uiPrintf(6, "%s", g_flowError.c_str());
    uiPrintf(10, "A : Back / Try again");
    uiPrintf(11, "B : Exit");
}

'''
s = s[:idx] + ui_helpers + s[idx:]

# render() priority.
replace_function('void render()', r'''void render() {
    consoleClear();
    if (g_interruptedPrompt) { renderInterruptedPrompt(); return; }
    if (g.awaitingBootConfirm) { renderBootConfirm(); return; }
    if (!g.ramDetectionConfirmed) { renderHardwareDetection(); return; }
    if (g.recoveryNeeded) { renderRecoveryPage(); return; }
    if (g_flowErrorScreen) { renderFlowError(); return; }
    if (g_overridePrompt) { renderOverridePrompt(); return; }
    if (g_resultScreen) { renderResultScreen(); return; }
    if (g_configVerified) { renderConfigVerified(); return; }
    if (g_resetConfirm) {
        std::printf("\x1b[1;1H\x1b[31mReset ALL wizard progress?\x1b[0m\n\n");
        std::printf("[A] Yes, reset   [B] Cancel\n");
        consoleUpdate(nullptr);
        return;
    }
    if (shouldShowConfigPage()) { renderConfigSetPage(); consoleUpdate(nullptr); return; }

    if (g.stage == Stage::Preparation) renderPreparation();
    else if (g.stage == Stage::RealWorldValidate) renderRealWorld();
    else if (g.stage == Stage::Complete) renderComplete();
    else renderTestStage();
    consoleUpdate(nullptr);
}''')

# ---------------------------------------------------------------------------
# Replace old manual sweep helpers with automatic mapper + progress bar.
# ---------------------------------------------------------------------------
replace_function('bool isVminSweepStage(Stage st)', r'''bool isVminSweepStage(Stage st) {
    return st == Stage::LowVminLong;
}''')

replace_function('u32 vminSweepClock(Stage st)', r'''u32 vminSweepClock(Stage st) {
    return st == Stage::LowVminLong ? CLOCK_CPU_VMIN_510_HZ : 0;
}''')

replace_function('void recordVminObservation(Stage st)', r'''void recordVminObservation(Stage st) {
    (void)st;
}''')

replace_function('void restartVminSweep(bool recovery)', r'''void restartVminSweep(bool recovery) {
    g.stage = Stage::LowVminLong;
    g.recoveryNeeded = recovery;
    g.vminPlateauCount = 0;
    g.vminPlateauIndex = 0;
    for (int i = 0; i < VMIN_SWEEP_POINT_COUNT; ++i) {
        g.vminPlateauHz[i] = 0;
        g.vminPlateauMv[i] = 0;
    }
    g.vminFloorHz = 0;
    g.vminFloorObservedMv = 0;
    g_configVerified = false;
    g_forceConfigPage = false;
    saveState();
}''')

# handlePass with multi-plateau validation + dynamic VDDQ start.
replace_function('void handlePass()', r'''void handlePass() {
    switch (g.stage) {
        case Stage::Preparation: g.stage = Stage::LowUvQuick; break;
        case Stage::LowUvQuick:
            g.lowUvGood = g.lowUvTest;
            if (g.lowUvTest >= LOW_UV_MAX) { enterLowUvLong(false); return; }
            ++g.lowUvTest; break;
        case Stage::LowUvLong:
            g.recoveryNeeded = false; g.stage = Stage::LowVminQuick;
            g.lowVminTest = g.lowVminGood - LOW_VMIN_STEP_MV; break;
        case Stage::LowVminQuick:
            g.lowVminGood = g.lowVminTest;
            if (g.lowVminTest <= LOW_VMIN_MIN_MV) { enterLowVminLong(false); return; }
            g.lowVminTest -= LOW_VMIN_STEP_MV; break;
        case Stage::LowVminLong:
            break; // automatic mapper advances this stage itself
        case Stage::LowVminSweep612:
        case Stage::LowVminSweep714:
        case Stage::LowVminValidate816:
        case Stage::LowVminSweep918:
        case Stage::LowVminValidate1020:
            restartVminSweep(false); return;
        case Stage::LowVminFinalLong:
            if (g.vminPlateauIndex + 1 < g.vminPlateauCount) {
                ++g.vminPlateauIndex;
            } else {
                g.recoveryNeeded = false;
                g.stage = Stage::VddqQuick;
                g.vddqTest = g.vddqStartMv - VDDQ_STEP_MV;
            }
            break;
        case Stage::VddqQuick:
            g.vddqGood = g.vddqTest;
            if (g.vddqTest <= VDDQ_MIN_MV) { enterVddqLong(false); return; }
            g.vddqTest -= VDDQ_STEP_MV; break;
        case Stage::VddqLong:
            g.recoveryNeeded = false; g.stage = Stage::Vdd2Quick;
            g.vdd2TestUv = STOCK_VDD2_UV - VDD2_STEP_UV; break;
        case Stage::Vdd2Quick:
            g.vdd2GoodUv = g.vdd2TestUv;
            if (g.vdd2TestUv <= VDD2_MIN_UV) { enterVdd2Long(false); return; }
            g.vdd2TestUv -= VDD2_STEP_UV; break;
        case Stage::Vdd2Long:
            g.recoveryNeeded = false; g.ramPairRetryMode = 0; g.stage = Stage::RamBoostValidate; break;
        case Stage::RamBoostValidate:
            g.ramPairRetryMode = 0; g.stage = Stage::Ram1331Validate; break;
        case Stage::Ram1331Validate: g.stage = Stage::HighUvQuick; g.highUvTest = 1; break;
        case Stage::HighUvQuick:
            g.highUvGood = g.highUvTest;
            if (g.highUvTest >= HIGH_UV_MAX) { enterHighUvLong(false); return; }
            ++g.highUvTest; break;
        case Stage::HighUvLong: g.recoveryNeeded = false; g.stage = Stage::BoostCpuRamValidate; break;
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
    g_configVerified = false;
    g_forceConfigPage = false;
    saveState();
}''')

# Keep existing fail policy but reset UI verification state and route all VMIN
# plateau failures through a safer Low VMIN + fresh automatic scan.
old_fail_start = s.index('void handleFail(bool didNotBoot)')
# modify function text after extracting it by replacing the full function below
replace_function('void handleFail(bool didNotBoot)', r'''void handleFail(bool didNotBoot) {
    switch (g.stage) {
        case Stage::LowUvQuick: enterLowUvLong(didNotBoot); return;
        case Stage::LowUvLong: if (g.lowUvGood > 0) --g.lowUvGood; g.recoveryNeeded = didNotBoot; break;
        case Stage::LowVminQuick: enterLowVminLong(didNotBoot); return;
        case Stage::LowVminLong:
        case Stage::LowVminSweep612:
        case Stage::LowVminSweep714:
        case Stage::LowVminValidate816:
        case Stage::LowVminSweep918:
        case Stage::LowVminValidate1020:
        case Stage::LowVminFinalLong:
            if (g.lowVminGood < STOCK_LOW_VMIN_MV) g.lowVminGood += LOW_VMIN_STEP_MV;
            restartVminSweep(didNotBoot);
            return;
        case Stage::VddqQuick: enterVddqLong(didNotBoot); return;
        case Stage::VddqLong: g.vddqGood += VDDQ_STEP_MV; g.recoveryNeeded = didNotBoot; break;
        case Stage::Vdd2Quick: enterVdd2Long(didNotBoot); return;
        case Stage::Vdd2Long: g.vdd2GoodUv += VDD2_STEP_UV; g.recoveryNeeded = didNotBoot; break;
        case Stage::RamBoostValidate:
            if (g.ramPairRetryMode == 0) { g.vddqGood += VDDQ_STEP_MV; g.ramPairRetryMode = 1; }
            else if (g.ramPairRetryMode == 1) { g.vddqGood -= VDDQ_STEP_MV; g.vdd2GoodUv += VDD2_STEP_UV; g.ramPairRetryMode = 2; }
            else g.vdd2GoodUv += VDD2_STEP_UV;
            break;
        case Stage::Ram1331Validate: g.vddqGood += VDDQ_STEP_MV; break;
        case Stage::HighUvQuick: enterHighUvLong(didNotBoot); return;
        case Stage::HighUvLong: if (g.highUvGood > 0) --g.highUvGood; g.recoveryNeeded = didNotBoot; break;
        case Stage::BoostCpuRamValidate: if (g.highUvGood > 0) --g.highUvGood; break;
        case Stage::NormalMatrixValidate: if (g.lowUvGood > 0) --g.lowUvGood; break;
        case Stage::NormalMemValidate: g.vddqGood += VDDQ_STEP_MV; break;
        case Stage::NormalGpuValidate: break;
        case Stage::BoostMatrixValidate: if (g.highUvGood > 0) --g.highUvGood; break;
        case Stage::BoostMemValidate: g.vddqGood += VDDQ_STEP_MV; break;
        case Stage::BoostCpuMemValidate: if (g.highUvGood > 0) --g.highUvGood; break;
        case Stage::RealWorldValidate: break;
        default: break;
    }
    g_configVerified = false;
    g_forceConfigPage = false;
    saveState();
}''')

# New automatic scan / reboot helpers replace runVminProbe().
replace_function('void runVminProbe()', r'''void drawVminSweepProgress(int activeIndex, const int observedMv[VMIN_SWEEP_POINT_COUNT]) {
    consoleClear();
    uiPrintf(1, "\x1b[36mBattery Wizard\x1b[0m");
    uiPrintf(2, "CPU Voltage Mapping");
    uiPrintf(3, "----------------------------------------");
    const int done = activeIndex < 0 ? VMIN_SWEEP_POINT_COUNT : activeIndex;
    std::string bar = "[";
    for (int i = 0; i < VMIN_SWEEP_POINT_COUNT; ++i) bar += (i < done ? "###" : "---");
    bar += "]";
    uiPrintf(5, "%s %d/%d", bar.c_str(), done, VMIN_SWEEP_POINT_COUNT);
    const u32 freqs[VMIN_SWEEP_POINT_COUNT] = {CLOCK_CPU_VMIN_510_HZ, CLOCK_CPU_LOW_HZ, CLOCK_CPU_VMIN_714_HZ, CLOCK_CPU_VMIN_MID_HZ, CLOCK_CPU_VMIN_918_HZ, CLOCK_CPU_NORMAL_HZ};
    if (activeIndex >= 0 && activeIndex < VMIN_SWEEP_POINT_COUNT) {
        uiPrintf(7, "Reading: %s", formatClock(freqs[activeIndex]).c_str());
        uiPrintf(8, "Voltage: reading...");
    } else {
        uiPrintf(7, "Scan complete");
    }
    uiPrintf(10, "Measured:");
    int row = 11;
    for (int i = 0; i < VMIN_SWEEP_POINT_COUNT; ++i)
        if (observedMv[i] > 0) uiPrintf(row++, " - %s : %d mV", formatClock(freqs[i]).c_str(), observedMv[i]);
    consoleUpdate(nullptr);
}''')

# Add the actual mapper immediately after drawVminSweepProgress.
marker = s.index('void runCurrentTest()')
auto_scan = r'''
bool sampleManagedCpuVoltage(u32 cpuHz, int& outMv) {
    u32 samples[3] = {};
    int count = 0;
    for (int attempt = 0; attempt < 8 && count < 3; ++attempt) {
        HocMonClocks c{};
        if (R_SUCCEEDED(hocmonGetClocks(&c)) &&
            clockMatches(c.overrideHz[0], cpuHz) && clockMatches(c.targetHz[0], cpuHz) &&
            clockMatches(c.overrideHz[1], CLOCK_GPU_NORMAL_HZ) &&
            clockMatches(c.overrideHz[2], CLOCK_RAM_NORMAL_HZ) && c.cpuVoltageUv) {
            samples[count++] = c.cpuVoltageUv;
        }
        svcSleepThread(300'000'000);
    }
    if (count != 3) return false;
    if (samples[0] > samples[1]) std::swap(samples[0], samples[1]);
    if (samples[1] > samples[2]) std::swap(samples[1], samples[2]);
    if (samples[0] > samples[1]) std::swap(samples[0], samples[1]);
    int mv = (int)((samples[1] + 500U) / 1000U);
    outMv = ((mv + 2) / 5) * 5;
    return true;
}

void runAutomaticVminSweep() {
    if (!verifyConfigForStage(g.stage)) {
        g_forceConfigPage = true;
        return;
    }
    const u32 freqs[VMIN_SWEEP_POINT_COUNT] = {CLOCK_CPU_VMIN_510_HZ, CLOCK_CPU_LOW_HZ, CLOCK_CPU_VMIN_714_HZ, CLOCK_CPU_VMIN_MID_HZ, CLOCK_CPU_VMIN_918_HZ, CLOCK_CPU_NORMAL_HZ};
    int observed[VMIN_SWEEP_POINT_COUNT] = {};
    if (!saveCurrentOverrides()) {
        g_flowError = "Could not save the current Horizon OC overrides.";
        g_flowErrorScreen = true;
        return;
    }

    for (int i = 0; i < VMIN_SWEEP_POINT_COUNT; ++i) {
        drawVminSweepProgress(i, observed);
        if (R_FAILED(hocmonSetOverrides(freqs[i], CLOCK_GPU_NORMAL_HZ, CLOCK_RAM_NORMAL_HZ))) {
            restoreSavedOverrides();
            g_flowError = "Horizon OC rejected a temporary override during the CPU scan.";
            g_flowErrorScreen = true;
            return;
        }
        svcSleepThread(650'000'000);
        if (!sampleManagedCpuVoltage(freqs[i], observed[i])) {
            restoreSavedOverrides();
            g_flowError = "Could not obtain stable CPU voltage samples. Try the scan again.";
            g_flowErrorScreen = true;
            return;
        }
        drawVminSweepProgress(i + 1 < VMIN_SWEEP_POINT_COUNT ? i + 1 : -1, observed);
    }
    restoreSavedOverrides();

    g.vminPlateauCount = 0;
    g.vminPlateauIndex = 0;
    for (int i = 0; i < VMIN_SWEEP_POINT_COUNT; ++i) {
        const bool endOfPlateau = (i == VMIN_SWEEP_POINT_COUNT - 1) || observed[i + 1] != observed[i];
        if (endOfPlateau && g.vminPlateauCount < VMIN_SWEEP_POINT_COUNT) {
            const int p = g.vminPlateauCount++;
            g.vminPlateauHz[p] = freqs[i];
            g.vminPlateauMv[p] = observed[i];
        }
    }
    if (g.vminPlateauCount > 0) {
        g.vminFloorHz = g.vminPlateauHz[0];
        g.vminFloorObservedMv = g.vminPlateauMv[0];
    }
    g.stage = Stage::LowVminFinalLong;
    saveState();
}

bool requestSystemReboot() {
    g.awaitingBootConfirm = true;
    saveState();
    consoleClear();
    uiPrintf(8, "\x1b[32mSetting verified.\x1b[0m");
    uiPrintf(10, "Restarting console...");
    consoleUpdate(nullptr);
    Result rc = appletRequestToReboot();
    if (R_FAILED(rc)) {
        g.awaitingBootConfirm = false;
        saveState();
        g_flowError = "System reboot request failed: 0x";
        char b[16]; std::snprintf(b, sizeof(b), "%08X", rc); g_flowError += b;
        g_flowErrorScreen = true;
        return false;
    }
    svcSleepThread(1'000'000'000);
    return true;
}

void handleBootConfirmed() {
    g.awaitingBootConfirm = false;
    if (!verifyConfigForStage(g.stage)) {
        g_forceConfigPage = true;
        g_configVerified = false;
        saveState();
        return;
    }
    markBootToken(g.stage);
    g_forceConfigPage = false;
    g_configVerified = false;
    if (g.stage == Stage::Preparation) handlePass();
    else saveState();
}

'''
s = s[:marker] + auto_scan + s[marker:]

# runCurrentTest: live config verification and app-managed overrides for plateau tests.
replace_function('void runCurrentTest()', r'''void runCurrentTest() {
    stress::Kind kind;
    int seconds = 0;
    if (!testPlan(g.stage, kind, seconds)) return;

    if (!verifyConfigForStage(g.stage)) {
        g_forceConfigPage = true;
        return;
    }

    OverrideExpectation expected{};
    const bool hasExpected = overridePlan(g.stage, expected);
    const bool managed = g.stage == Stage::LowVminFinalLong;
    if (managed) {
        if (!hasExpected || !managedOverrideReady(expected)) {
            g_flowError = "Could not apply the temporary overrides for CPU plateau validation.";
            g_flowErrorScreen = true;
            return;
        }
    } else {
        g_overrideAction = PendingOverrideAction::StartTest;
        if (!checkAllOverrides(g.stage)) {
            g_overridePrompt = true;
            return;
        }
        g_overridePrompt = false;
    }

    const Stage testedStage = g.stage;
    const int testedPlateau = g.vminPlateauIndex;
    g.testRunning = true;
    g.testKind = static_cast<int>(kind);
    g.testDurationSec = seconds;
    g.testStage = static_cast<int>(testedStage);
    saveState();

    g_lastKind = kind;
    g_lastResult = stress::run(kind, seconds);

    if (managed) restoreSavedOverrides();
    g.testRunning = false;
    g.testKind = 0;
    g.testDurationSec = 0;
    g.testStage = 0;
    saveState();

    g_resultAction.clear();
    if (g_lastResult.outcome == stress::Outcome::Pass) {
        if (testedStage == Stage::LowVminFinalLong && testedPlateau < g.vminPlateauCount) {
            g_resultAction = "PASS: " + formatClock(g.vminPlateauHz[testedPlateau]) + " @ ~" + std::to_string(g.vminPlateauMv[testedPlateau]) + " mV validated.";
        } else {
            g_resultAction = "PASS recorded automatically. The wizard advanced to the next step.";
        }
        handlePass();
    } else if (g_lastResult.outcome == stress::Outcome::Fail) {
        handleFail(false);
        g_resultAction = "FAIL recorded automatically. Follow the safer value shown on the next step.";
    } else if (g_lastResult.outcome == stress::Outcome::Cancelled) {
        g_resultAction = "No tuning result was recorded. You can run the same test again.";
    } else {
        g_resultAction = "The tuning value was NOT marked failed. Fix the test-engine problem and retry.";
    }
    g_resultScreen = true;
}''')

# ---------------------------------------------------------------------------
# Main-loop startup and interaction states.
# ---------------------------------------------------------------------------
replace_once(
    '    if (!loadState()) saveState();\n    g_interruptedPrompt = g.testRunning;',
    '    if (!loadState()) saveState();\n'
    '    // If a managed override session was interrupted, restore the user\'s previous overrides first.\n'
    '    if (g.savedOverrideValid) restoreSavedOverrides();\n'
    '    detectRamIfNeeded();\n'
    '    g_interruptedPrompt = g.testRunning;'
)

# Replace the complete input loop body from the first prompt handling through
# the normal key handling; keep loop setup/sleep structure.
loop_start = s.index('        if (g_interruptedPrompt) {', s.index('while (appletMainLoop())'))
loop_end_marker = "\n        svcSleepThread(20'000'000);\n    }"
loop_end = s.index(loop_end_marker, loop_start)
new_loop = r'''        if (g_interruptedPrompt) {
            if (k & HidNpadButton_A) {
                g.testRunning = false;
                if (g.testStage >= 0 && g.testStage <= static_cast<int>(Stage::RamBoostValidate))
                    g.stage = static_cast<Stage>(g.testStage);
                g.testKind = g.testDurationSec = g.testStage = 0;
                restoreSavedOverrides();
                saveState();
                handleFail(false);
                g_interruptedPrompt = false;
                redraw = true;
            } else if (k & HidNpadButton_X) {
                g.testRunning = false;
                if (g.testStage >= 0 && g.testStage <= static_cast<int>(Stage::RamBoostValidate))
                    g.stage = static_cast<Stage>(g.testStage);
                g.testKind = g.testDurationSec = g.testStage = 0;
                restoreSavedOverrides();
                saveState();
                g_interruptedPrompt = false;
                redraw = true;
            } else if (k & HidNpadButton_B) break;
            svcSleepThread(20'000'000);
            continue;
        }

        if (g.awaitingBootConfirm) {
            if (k & HidNpadButton_A) { handleBootConfirmed(); redraw = true; }
            else if (k & HidNpadButton_X) {
                g.awaitingBootConfirm = false;
                saveState();
                if (g.stage == Stage::Preparation) {
                    g_flowError = "Preparation did not boot normally. Restore the previous HOC configuration from safe CFW.";
                    g_flowErrorScreen = true;
                } else {
                    handleFail(true);
                }
                redraw = true;
            } else if (k & HidNpadButton_B) break;
            svcSleepThread(20'000'000);
            continue;
        }

        if (!g.ramDetectionConfirmed) {
            if (!g.ramDetectionDone) {
                if (k & HidNpadButton_A) { detectRamIfNeeded(); redraw = true; }
            } else if (g.vddqStartMv == 600 || g.vddqStartMv == 640) {
                if (k & HidNpadButton_A) { g.ramDetectionConfirmed = true; saveState(); redraw = true; }
            } else {
                if (k & HidNpadButton_A) { applyDetectedVddqStart(600); g.ramDetectionConfirmed = true; saveState(); redraw = true; }
                else if (k & HidNpadButton_X) { applyDetectedVddqStart(640); g.ramDetectionConfirmed = true; saveState(); redraw = true; }
            }
            if (k & HidNpadButton_B) break;
            svcSleepThread(20'000'000);
            continue;
        }

        if (g.recoveryNeeded) {
            if (k & HidNpadButton_A) {
                g.recoveryNeeded = false;
                saveState();
                if (requestSystemReboot()) break;
                redraw = true;
            } else if (k & HidNpadButton_B) break;
            svcSleepThread(20'000'000);
            continue;
        }

        if (g_flowErrorScreen) {
            if (k & HidNpadButton_A) { g_flowErrorScreen = false; redraw = true; }
            else if (k & HidNpadButton_B) break;
            svcSleepThread(20'000'000);
            continue;
        }

        if (g_overridePrompt) {
            if (k & HidNpadButton_A) {
                g_overridePrompt = false;
                runCurrentTest();
                redraw = true;
            } else if (k & HidNpadButton_B) {
                g_overridePrompt = false;
                redraw = true;
            }
            svcSleepThread(20'000'000);
            continue;
        }

        if (g_resultScreen) {
            if (k & HidNpadButton_A || k & HidNpadButton_B) { g_resultScreen = false; redraw = true; }
            svcSleepThread(20'000'000);
            continue;
        }

        if (g_configVerified) {
            if (k & HidNpadButton_A) {
                if (requestSystemReboot()) break;
                redraw = true;
            } else if (k & HidNpadButton_B) { g_configVerified = false; redraw = true; }
            svcSleepThread(20'000'000);
            continue;
        }

        if (g_resetConfirm) {
            if (k & HidNpadButton_A) { resetState(); detectRamIfNeeded(); g_resetConfirm = false; redraw = true; }
            else if (k & HidNpadButton_B) { g_resetConfirm = false; redraw = true; }
            svcSleepThread(20'000'000);
            continue;
        }

        if (shouldShowConfigPage()) {
            if (k & HidNpadButton_A) {
                if (verifyConfigForStage(g.stage)) { g_configVerified = true; g_forceConfigPage = false; }
                else g_forceConfigPage = true;
                redraw = true;
            } else if (k & HidNpadButton_B) break;
            svcSleepThread(20'000'000);
            continue;
        }

        if (k & HidNpadButton_Minus) {
            g_resetConfirm = true;
            redraw = true;
        } else if (k & HidNpadButton_B) {
            saveState();
            break;
        } else if (k & HidNpadButton_Plus) {
            stress::Kind skipKind; int skipSeconds = 0;
            if (testPlan(g.stage, skipKind, skipSeconds)) {
                g_manualPass = true; handlePass(); g_manualPass = false; redraw = true;
            }
        } else if (k & HidNpadButton_X) {
            if (g.stage != Stage::Preparation && g.stage != Stage::Complete && g.stage != Stage::LowVminLong) {
                handleFail(false); redraw = true;
            }
        } else if (k & HidNpadButton_A) {
            if (g.stage == Stage::Preparation) {
                if (verifyConfigForStage(g.stage)) { g_configVerified = true; g_forceConfigPage = false; }
                else g_forceConfigPage = true;
            } else if (g.stage == Stage::LowVminLong) {
                runAutomaticVminSweep();
            } else {
                stress::Kind kind; int seconds = 0;
                if (testPlan(g.stage, kind, seconds)) runCurrentTest();
                else handlePass();
            }
            redraw = true;
        }
'''
s = s[:loop_start] + new_loop + s[loop_end:]

# ---------------------------------------------------------------------------
# Metadata/docs for beta16.
# ---------------------------------------------------------------------------
P.write_text(s)

mk = Path('Makefile').read_text()
mk = re.sub(r'APP_VERSION := .*', 'APP_VERSION := 0.4.0-beta.16', mk)
Path('Makefile').write_text(mk)

Path('UPDATE.txt').write_text(
    'version=0.4.0-beta.16\n'
    'nro_url=https://github.com/retrotendo/HOC-Undervolting-Wizard/releases/download/v0.4.0-beta.16/HOC-Undervolting-Wizard.nro\n'
    'sha_url=https://github.com/retrotendo/HOC-Undervolting-Wizard/releases/download/v0.4.0-beta.16/HOC-Undervolting-Wizard.nro.sha256\n'
)

notes = '''# v0.4.0-beta.16\n\n- Detects the installed Mariko DRAM module before Preparation and selects the 600/640 mV VDDQ starting point from the Horizon OC RAM table.\n- Persistent HOC changes now use a guided verify -> green confirmation -> user-confirmed system reboot flow.\n- After every app-requested reboot, the Wizard asks whether the console booted normally before testing.\n- Already validated persistent settings are no longer repeated on later test pages.\n- CPU Low VMIN mapping is automatic: the Wizard controls temporary CPU/GPU/RAM overrides and scans 510/612/714/816/918/1020 MHz with a visible progress bar.\n- Distinct measured CPU voltage plateaus are detected and the highest frequency of every plateau is scheduled for 1-hour CPU validation.\n- Temporary overrides used by the automatic mapper/plateau tests are restored afterwards.\n'''
Path('RELEASE_NOTES_v0.4.0-beta.16.md').write_text(notes)

readme = Path('README.md').read_text()
anchor = '## Battery tuning workflow'
extra = '''\n### Guided hardware and reboot flow (beta.16)\n\nThe Wizard reads the Horizon OC DRAM ID before Preparation and selects the RAM-specific VDDQ starting point. Persistent voltage/UV changes remain manual in Horizon OC: the Wizard verifies the requested value, shows a green confirmation, and only reboots when the user presses A. After reboot it asks whether the console booted normally before any stress test starts.\n\nThe Low VMIN CPU map is automated. The app temporarily controls CPU/GPU/RAM overrides, scans 510 through 1020 MHz, records the observed CPU rail voltage at every point, groups equal voltage plateaus, and validates the highest clock of each detected plateau.\n\n'''
if extra.strip() not in readme:
    if anchor in readme:
        readme = readme.replace(anchor, extra + anchor, 1)
    else:
        readme += extra
Path('README.md').write_text(readme)

print('beta16 flow patch applied')
