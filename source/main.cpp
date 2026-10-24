#include <switch.h>

#include "stress_tests.hpp"
#include "hoc_monitor.h"
#include "updater.hpp"

#include <algorithm>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <string>
#include <sys/stat.h>
#include <unistd.h>

namespace {

constexpr const char* APP_DIR   = "sdmc:/switch/HOC-Undervolting-Wizard";
constexpr const char* STATE     = "sdmc:/switch/HOC-Undervolting-Wizard/state.ini";
constexpr const char* STATE_TMP = "sdmc:/switch/HOC-Undervolting-Wizard/state.tmp";
constexpr const char* RESULTS   = "sdmc:/switch/HOC-Undervolting-Wizard/results.txt";
constexpr const char* LEGACY_STATE = "sdmc:/switch/HOC-Battery-Wizard/state.ini";

constexpr int STOCK_LOW_UV = 0;
constexpr int STOCK_HIGH_UV = 0;
constexpr int STOCK_LOW_VMIN_MV = 620;
constexpr int STOCK_HIGH_VMIN_MV = 750;
constexpr int STOCK_VDDQ_MV = 600;
constexpr int ALT_VDDQ_MV = 640;
constexpr int STOCK_VDD2_UV = 1175000;
constexpr u32 PREP_RAM_MAX_KHZ = 1600000U;
constexpr u32 PREP_CPU_MAX_KHZ = 1963500U;
constexpr u32 PREP_CPU_BOOST_KHZ = 1785000U;
constexpr int PREP_CPU_TABLE = 3; // 1683 MHz Tbreak
constexpr int VMIN_SWEEP_POINT_COUNT = 6;

// Horizon OC temporary-override targets used by the Battery guide.
constexpr u32 CLOCK_CPU_NORMAL_HZ   = 1020000000U;
constexpr u32 CLOCK_CPU_VMIN_510_HZ = 510000000U;
constexpr u32 CLOCK_CPU_LOW_HZ      = 612000000U;
constexpr u32 CLOCK_CPU_VMIN_714_HZ = 714000000U;
constexpr u32 CLOCK_CPU_VMIN_MID_HZ = 816000000U;
constexpr u32 CLOCK_CPU_VMIN_918_HZ = 918000000U;
constexpr u32 CLOCK_CPU_BOOST_HZ    = 1785000000U;
constexpr u32 CLOCK_GPU_NORMAL_HZ = 384000000U;
constexpr u32 CLOCK_GPU_BOOST_HZ  = 76800000U;
constexpr u32 CLOCK_RAM_NORMAL_HZ = 1331200000U;
constexpr u32 CLOCK_RAM_BOOST_HZ  = 1600000000U;

constexpr int LOW_UV_MAX = 8;
constexpr int HIGH_UV_MAX = 13;
constexpr int LOW_VMIN_MIN_MV = 570;
constexpr int VDDQ_MIN_MV = 400;
constexpr int VDD2_MIN_UV = 912500;
constexpr int LOW_VMIN_STEP_MV = 5;
constexpr int VDDQ_STEP_MV = 10;
constexpr u32 VMIN_FLOOR_TOLERANCE_UV = 5000U;
constexpr int VDD2_STEP_UV = 12500;

enum class Stage : int {
    Preparation = 0,
    LowUvQuick,
    LowUvLong,
    LowVminQuick,
    LowVminLong,
    VddqQuick,
    VddqLong,
    Vdd2Quick,
    Vdd2Long,
    Ram1331Validate,
    HighUvQuick,
    HighUvLong,
    BoostCpuRamValidate,
    NormalMatrixValidate,
    NormalMemValidate,
    NormalGpuValidate,
    BoostMatrixValidate,
    BoostMemValidate,
    BoostCpuMemValidate,
    RealWorldValidate,
    Complete,
    // Appended to preserve all existing beta.2 stage numbers in state.ini.
    LowVminValidate816,
    LowVminValidate1020,
    // beta.4 additions are appended to preserve older state.ini stage numbers.
    LowVminSweep612,
    LowVminSweep714,
    LowVminSweep918,
    LowVminFinalLong,
    RamBoostValidate
};

struct WizardState {
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
};

WizardState g;
bool g_resetConfirm = false;
bool g_interruptedPrompt = false;
bool g_resultScreen = false;
stress::Result g_lastResult;
stress::Kind g_lastKind = stress::Kind::Cpu;
std::string g_resultAction;
bool g_manualPass = false;
bool g_configVerified = false;
bool g_forceConfigPage = false;
HocMonConfig g_configRead{};
Result g_configRc = 0;
Result g_hwRc = 0;
bool g_flowErrorScreen = false;
std::string g_flowError;

struct OverrideExpectation {
    u32 cpuHz = 0;
    u32 gpuHz = 0;
    u32 ramHz = 0;
};

struct OverrideCheckState {
    bool readOk = false;
    Result rc = 0;
    OverrideExpectation expected;
    HocMonClocks current{};
    bool cpuOk = false;
    bool gpuOk = false;
    bool ramOk = false;
    bool cpuAppliedOk = true;
    bool voltageSamplesOk = true;
};

enum class PendingOverrideAction { StartTest, VminProbe };
bool g_overridePrompt = false;
PendingOverrideAction g_overrideAction = PendingOverrideAction::StartTest;
OverrideCheckState g_overrideCheck;

std::string formatVdd2(int uv) {
    const int whole = uv / 1000;
    const int rem = uv % 1000;
    std::ostringstream os;
    os << whole;
    if (rem == 500) os << ".5";
    os << " mV";
    return os.str();
}

const char* stageName(Stage s) {
    switch (s) {
        case Stage::Preparation: return "Preparation";
        case Stage::LowUvQuick: return "CPU Low UV - Quick Search";
        case Stage::LowUvLong: return "CPU Low UV - 1 Hour Validation";
        case Stage::LowVminQuick: return "CPU Low VMIN - Quick Search @ 510";
        case Stage::LowVminLong: return "CPU Low VMIN - Floor Sweep @ 510";
        case Stage::LowVminSweep612: return "CPU Low VMIN - Floor Sweep @ 612";
        case Stage::LowVminSweep714: return "CPU Low VMIN - Floor Sweep @ 714";
        case Stage::LowVminValidate816: return "CPU Low VMIN - Floor Sweep @ 816";
        case Stage::LowVminSweep918: return "CPU Low VMIN - Floor Sweep @ 918";
        case Stage::LowVminValidate1020: return "CPU Low VMIN - Floor Sweep @ 1020";
        case Stage::LowVminFinalLong: return "CPU Low VMIN - Dynamic 1 Hour Validation";
        case Stage::VddqQuick: return "VDDQ - Quick Search";
        case Stage::VddqLong: return "VDDQ - 1 Hour Validation";
        case Stage::Vdd2Quick: return "VDD2 - Quick Search";
        case Stage::Vdd2Long: return "VDD2 - 1 Hour Validation";
        case Stage::RamBoostValidate: return "RAM Rails - Boost Combined Validation";
        case Stage::Ram1331Validate: return "RAM - Normal Handheld Validation";
        case Stage::HighUvQuick: return "CPU High UV - Quick Search";
        case Stage::HighUvLong: return "CPU High UV - 1 Hour Validation";
        case Stage::BoostCpuRamValidate: return "Boost CPU + RAM Validation";
        case Stage::NormalMatrixValidate: return "Final Normal - CPU";
        case Stage::NormalMemValidate: return "Final Normal - RAM";
        case Stage::NormalGpuValidate: return "Final Normal - GPU";
        case Stage::BoostMatrixValidate: return "Final Boost - CPU";
        case Stage::BoostMemValidate: return "Final Boost - RAM";
        case Stage::BoostCpuMemValidate: return "Final Boost - CPU + RAM";
        case Stage::RealWorldValidate: return "Final Real-World Test";
        case Stage::Complete: return "Complete";
    }
    return "Unknown";
}

bool isQuickStage(Stage s) {
    return s == Stage::LowUvQuick || s == Stage::LowVminQuick ||
           s == Stage::VddqQuick || s == Stage::Vdd2Quick ||
           s == Stage::HighUvQuick;
}

bool testPlan(Stage s, stress::Kind& kind, int& seconds) {
    switch (s) {
        case Stage::LowUvQuick:
        case Stage::LowVminQuick:
        case Stage::HighUvQuick:
            kind = stress::Kind::Cpu; seconds = 60; return true;
        case Stage::LowUvLong:
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
}

bool overridePlan(Stage s, OverrideExpectation& e) {
    switch (s) {
        case Stage::LowUvQuick:
        case Stage::LowUvLong:
        case Stage::Ram1331Validate:
        case Stage::NormalMatrixValidate:
        case Stage::NormalMemValidate:
        case Stage::NormalGpuValidate:
            e = {CLOCK_CPU_NORMAL_HZ, CLOCK_GPU_NORMAL_HZ, CLOCK_RAM_NORMAL_HZ};
            return true;

        case Stage::LowVminQuick:
        case Stage::LowVminLong:
            e = {CLOCK_CPU_VMIN_510_HZ, CLOCK_GPU_NORMAL_HZ, CLOCK_RAM_NORMAL_HZ};
            return true;
        case Stage::LowVminSweep612:
            e = {CLOCK_CPU_LOW_HZ, CLOCK_GPU_NORMAL_HZ, CLOCK_RAM_NORMAL_HZ};
            return true;
        case Stage::LowVminSweep714:
            e = {CLOCK_CPU_VMIN_714_HZ, CLOCK_GPU_NORMAL_HZ, CLOCK_RAM_NORMAL_HZ};
            return true;
        case Stage::LowVminValidate816:
            e = {CLOCK_CPU_VMIN_MID_HZ, CLOCK_GPU_NORMAL_HZ, CLOCK_RAM_NORMAL_HZ};
            return true;
        case Stage::LowVminSweep918:
            e = {CLOCK_CPU_VMIN_918_HZ, CLOCK_GPU_NORMAL_HZ, CLOCK_RAM_NORMAL_HZ};
            return true;
        case Stage::LowVminValidate1020:
            e = {CLOCK_CPU_NORMAL_HZ, CLOCK_GPU_NORMAL_HZ, CLOCK_RAM_NORMAL_HZ};
            return true;
        case Stage::LowVminFinalLong: {
            const int idx = (g.vminPlateauIndex >= 0 && g.vminPlateauIndex < g.vminPlateauCount) ? g.vminPlateauIndex : 0;
            const u32 hz = (g.vminPlateauCount > 0 && g.vminPlateauHz[idx]) ? g.vminPlateauHz[idx] : CLOCK_CPU_VMIN_510_HZ;
            e = {hz, CLOCK_GPU_NORMAL_HZ, CLOCK_RAM_NORMAL_HZ};
            return true;
        }

        case Stage::VddqQuick:
        case Stage::VddqLong:
        case Stage::Vdd2Quick:
        case Stage::Vdd2Long:
        case Stage::RamBoostValidate:
        case Stage::HighUvQuick:
        case Stage::HighUvLong:
        case Stage::BoostCpuRamValidate:
        case Stage::BoostMatrixValidate:
        case Stage::BoostMemValidate:
        case Stage::BoostCpuMemValidate:
            e = {CLOCK_CPU_BOOST_HZ, CLOCK_GPU_BOOST_HZ, CLOCK_RAM_BOOST_HZ};
            return true;

        default:
            return false;
    }
}

bool clockMatches(u32 current, u32 expected) {
    if (current == 0 || expected == 0) return false;
    const u32 tolerance = 2000000U; // tolerate display/list rounding such as 1331 vs 1331.2 MHz
    return current > expected ? (current - expected <= tolerance) : (expected - current <= tolerance);
}

std::string formatClock(u32 hz) {
    if (hz == 0) return "NOT SET";
    char buf[32];
    if (hz % 1000000U == 0)
        std::snprintf(buf, sizeof(buf), "%u MHz", hz / 1000000U);
    else
        std::snprintf(buf, sizeof(buf), "%.1f MHz", (double)hz / 1000000.0);
    return std::string(buf);
}


bool saveState();

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

bool checkAllOverrides(Stage s) {
    g_overrideCheck = OverrideCheckState{};
    if (!overridePlan(s, g_overrideCheck.expected)) return true;

    g_overrideCheck.rc = hocmonGetClocks(&g_overrideCheck.current);
    if (R_FAILED(g_overrideCheck.rc)) {
        g_overrideCheck.readOk = false;
        return false;
    }

    g_overrideCheck.readOk = true;
    g_overrideCheck.cpuOk = clockMatches(g_overrideCheck.current.overrideHz[0], g_overrideCheck.expected.cpuHz);
    g_overrideCheck.gpuOk = clockMatches(g_overrideCheck.current.overrideHz[1], g_overrideCheck.expected.gpuHz);
    g_overrideCheck.ramOk = clockMatches(g_overrideCheck.current.overrideHz[2], g_overrideCheck.expected.ramHz);
    return g_overrideCheck.cpuOk && g_overrideCheck.gpuOk && g_overrideCheck.ramOk;
}

// VMIN floor probing is measurement-only. Read several HOC context samples so a
// stale single poll cannot decide the floor crossover. The median CPU rail
// voltage from matching override samples is used.
bool sampleVminVoltage(Stage s) {
    (void)s;
    return false;
}


void ensureDir() {
    mkdir("sdmc:/switch", 0777);
    mkdir(APP_DIR, 0777);
}

bool copyFile(const char* from, const char* to) {
    std::ifstream src(from, std::ios::binary);
    if (!src) return false;
    std::ofstream dst(to, std::ios::binary | std::ios::trunc);
    if (!dst) return false;
    dst << src.rdbuf();
    return bool(dst);
}

void migrateLegacyState() {
    ensureDir();
    if (access(STATE, F_OK) != 0 && access(LEGACY_STATE, F_OK) == 0)
        copyFile(LEGACY_STATE, STATE);
}

bool saveState() {
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
}


void assignKV(const std::string& key, const std::string& value) {
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
}


bool loadState() {
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
}


void resetState() {
    g = WizardState{};
    saveState();
}

void writeResults() {
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
}


constexpr int UI_COL = 36;

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
    uiPrintf(3, "----------------------------------------");
}

void printSafeRecovery(const char* menu, const std::string& restoreText) {
    uiPrintf(5, "@ Horizon OC");
    uiPrintf(7, "\x1b[33mPrevious setting did not boot\x1b[0m");
    uiPrintf(9, "Recovery:");
    uiPrintf(10, " - Boot Hekate without hoc.kip");
    uiPrintf(11, " - Open Horizon OC");
    uiPrintf(12, "%s:", menu);
    uiPrintf(13, " - Restore : %s", restoreText.c_str());
    uiPrintf(14, " - Reboot CFW");
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
    uiPrintf(row,     "Temporary Overrides:");
    uiPrintf(row + 1, " - CPU : %s", formatClock(e.cpuHz).c_str());
    uiPrintf(row + 2, " - GPU : %s", formatClock(e.gpuHz).c_str());
    uiPrintf(row + 3, " - RAM : %s", formatClock(e.ramHz).c_str());
}

void footerTest(int row) {
    uiPrintf(row,     "Keys:");
    uiPrintf(row + 1, "A : Start Test");
    uiPrintf(row + 2, "+ : Known PASS / Skip");
    uiPrintf(row + 3, "X : Known FAIL / Skip");
    uiPrintf(row + 4, "B : Exit    - : Reset");
}


void renderPreparation() {
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
}


bool isVminSweepStage(Stage st);

void renderTestStage() {
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
}


void renderRealWorld() {
    title();
    uiPrintf(5, "@ Horizon OC");
    uiPrintf(7, "Temporary Overrides:");
    uiPrintf(8, " - Remove all Overrides");
    uiPrintf(10, "Test:");
    uiPrintf(11, "1 hour Tears of the Kingdom");
    uiPrintf(12, "Fast travel / battles / loading");
    uiPrintf(13, "Home + Sleep/Wake");
    uiPrintf(15, "Keys:");
    uiPrintf(16, "A : PASS");
    uiPrintf(17, "X : FAIL");
    uiPrintf(18, "B : Exit");
}

void renderComplete() {
    title();
    uiPrintf(5, "\x1b[32mUNDERVOLTING COMPLETE\x1b[0m");
    uiPrintf(7, "Final values:");
    uiPrintf(8, "CPU Low UV   : %d", g.lowUvGood);
    uiPrintf(9, "CPU Low VMIN : %d mV", g.lowVminGood);
    uiPrintf(10, "RAM VDDQ     : %d mV", g.vddqGood);
    uiPrintf(11, "RAM VDD2     : %s", formatVdd2(g.vdd2GoodUv).c_str());
    uiPrintf(12, "CPU High UV  : %d", g.highUvGood);
    uiPrintf(14, "Saved to:");
    uiPrintf(15, "/switch/HOC-Undervolting-Wizard/results.txt");
    uiPrintf(17, "B : Exit    - : Reset");
}

void renderInterruptedPrompt() {
    consoleClear();
    std::printf("\x1b[1;1H\x1b[33mHOC Undervolting Wizard - Interrupted Test\x1b[0m\n");
    std::printf("------------------------------------------------------------\n\n");
    std::printf("The previous built-in test was marked RUNNING but never finished.\n\n");
    std::printf("Stage: %s\n", stageName(static_cast<Stage>(g.testStage)));
    std::printf("Test : %s\n", stress::kindName(static_cast<stress::Kind>(g.testKind)));
    std::printf("Time : %s\n\n", g.testDurationSec == 60 ? "1 minute" : "1 hour");
    std::printf("Did the console freeze, crash or reboot during the test?\n\n");
    std::printf("\x1b[31m[A] YES - count as FAIL\x1b[0m\n");
    std::printf("[X] NO - test was interrupted manually; run it again\n");
    std::printf("[B] Exit and decide later\n");
    consoleUpdate(nullptr);
}

void renderOverridePrompt() {
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

void renderResultScreen() {
    consoleClear();
    std::printf("\x1b[1;1H\x1b[36mHOC Undervolting Wizard\x1b[0m\n");
    std::printf("Built-in %s\n", stress::kindName(g_lastKind));
    std::printf("------------------------------------------------------------\n\n");
    if (g_lastResult.outcome == stress::Outcome::Pass)
        std::printf("\x1b[32mPASS\x1b[0m\n\n");
    else if (g_lastResult.outcome == stress::Outcome::Fail)
        std::printf("\x1b[31mFAIL\x1b[0m\n\n");
    else if (g_lastResult.outcome == stress::Outcome::Cancelled)
        std::printf("\x1b[33mCANCELLED\x1b[0m\n\n");
    else
        std::printf("\x1b[31mTEST ENGINE ERROR\x1b[0m\n\n");

    std::printf("Elapsed    : %llu ms\n", (unsigned long long)g_lastResult.elapsedMs);
    std::printf("Iterations : %llu\n", (unsigned long long)g_lastResult.iterations);
    std::printf("Errors     : %llu\n", (unsigned long long)g_lastResult.errors);
    std::printf("Mismatches : %llu\n\n", (unsigned long long)g_lastResult.mismatches);
    std::printf("%s\n", g_lastResult.detail.c_str());
    if (!g_resultAction.empty()) std::printf("\n%s\n", g_resultAction.c_str());
    std::printf("\n[A] Continue\n");
    consoleUpdate(nullptr);
}

void render() {
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
}


bool isVminSweepStage(Stage st) {
    return st == Stage::LowVminLong;
}


u32 vminSweepClock(Stage st) {
    return st == Stage::LowVminLong ? CLOCK_CPU_VMIN_510_HZ : 0;
}


void recordVminObservation(Stage st) {
    (void)st;
}


void restartVminSweep(bool recovery) {
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
}


void enterLowUvLong(bool recovery) { g.stage = Stage::LowUvLong; g.recoveryNeeded = recovery; saveState(); }
void enterLowVminLong(bool recovery) { restartVminSweep(recovery); }
void enterVddqLong(bool recovery) { g.stage = Stage::VddqLong; g.recoveryNeeded = recovery; saveState(); }
void enterVdd2Long(bool recovery) { g.stage = Stage::Vdd2Long; g.recoveryNeeded = recovery; saveState(); }
void enterHighUvLong(bool recovery) { g.stage = Stage::HighUvLong; g.recoveryNeeded = recovery; saveState(); }

void handlePass() {
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
}


void handleFail(bool didNotBoot) {
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
}


void drawVminSweepProgress(int activeIndex, const int observedMv[VMIN_SWEEP_POINT_COUNT]) {
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
}



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

void runCurrentTest() {
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
}


} // namespace

int main(int argc, char** argv) {
    consoleInit(nullptr);
    padConfigureInput(1, HidNpadStyleSet_NpadStandard);
    PadState pad;
    padInitializeDefault(&pad);

    // The built-in CPU/RAM/Combined/GPU stability tests require hbmenu to be
    // launched with full application memory. Match nx-hbmenu's own Applet Mode
    // detection: only Application/SystemApplication are accepted.
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

    // Full Application Mode only: check the public GitHub releases before
    // touching Wizard state. Network/update failures are non-fatal and simply
    // continue with the currently installed build.
    if (updater::startupCheckAndPrompt(pad, argc, argv)) {
        consoleExit(nullptr);
        return 0;
    }

    ensureDir();
    migrateLegacyState();
    if (!loadState()) saveState();
    // If a managed override session was interrupted, restore the user's previous overrides first.
    if (g.savedOverrideValid) restoreSavedOverrides();
    detectRamIfNeeded();
    g_interruptedPrompt = g.testRunning;

    bool redraw = true;
    while (appletMainLoop()) {
        padUpdate(&pad);
        const u64 k = padGetButtonsDown(&pad);

        if (redraw) {
            render();
            redraw = false;
        }

        if (g_interruptedPrompt) {
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

        svcSleepThread(20'000'000);
    }

    consoleExit(nullptr);
    return 0;
}
