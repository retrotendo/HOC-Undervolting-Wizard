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
constexpr int STOCK_VDD2_UV = 1175000;

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
    RamBoostValidate,
    // beta.16: appended to keep every previous persisted stage number valid.
    HardwareDetection,
    LowVminPlateauValidate
};

struct WizardState {
    Stage stage = Stage::HardwareDetection;
    int lowUvGood = STOCK_LOW_UV;
    int lowUvTest = 1;
    int lowVminGood = STOCK_LOW_VMIN_MV;
    int lowVminTest = STOCK_LOW_VMIN_MV - LOW_VMIN_STEP_MV;
    int vddqGood = STOCK_VDDQ_MV;
    int vddqTest = STOCK_VDDQ_MV - VDDQ_STEP_MV;
    int vdd2GoodUv = STOCK_VDD2_UV;
    int vdd2TestUv = STOCK_VDD2_UV - VDD2_STEP_UV;
    int highUvGood = STOCK_HIGH_UV;
    int highUvTest = 1;
    u32 vminFloorHz = 0;
    int vminFloorObservedMv = 0;
    int ramPairRetryMode = 0;
    bool recoveryNeeded = false;
    bool warningBelow590Seen = false;

    // Hardware-guided VDDQ baseline.
    int dramId = -1;
    int consoleType = -1;
    int vddqStartMv = STOCK_VDDQ_MV;
    bool ramDetected = false;

    // Persistent-setting / reboot handoff.
    bool stageReadyAfterBoot = false;
    bool rebootPending = false;
    u32 pendingConfigMask = 0;

    // VMIN sweep observations and voltage-plateau representatives.
    int vminObsMv[6] = {};
    u32 vminObsMask = 0;
    int vminValidateCount = 0;
    int vminValidateIndex = 0;
    u32 vminValidateHz[6] = {};
    int vminValidateMv[6] = {};
    u32 lastProbeHz = 0;
    int lastProbeMv = 0;

    // Persisted before every built-in test. If this remains true after a reboot,
    // the wizard knows the previous test did not finish normally.
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
bool g_lastVminAtFloor = false;

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

enum ConfigMask : u32 {
    Config_None    = 0,
    Config_LowUv   = 1u << 0,
    Config_LowVmin = 1u << 1,
    Config_Vddq    = 1u << 2,
    Config_Vdd2    = 1u << 3,
    Config_HighUv  = 1u << 4,
    Config_Prepare = 1u << 5,
};

struct ConfigCheckState {
    bool readOk = false;
    Result rc = 0;
    u32 mask = Config_None;
    HocMonConfig current{};
};

bool g_configPrompt = false;
bool g_rebootConfirm = false;
bool g_bootPrompt = false;
ConfigCheckState g_configCheck;
Result g_rebootError = 0;
Result g_hardwareReadRc = 0;
HocMonHardware g_hardware{};

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
        case Stage::HardwareDetection: return "Hardware Detection";
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
        case Stage::LowVminPlateauValidate: return "CPU Low VMIN - Plateau Validation";
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
        case Stage::LowVminPlateauValidate:
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
        case Stage::LowVminFinalLong:
            e = {g.vminFloorHz ? g.vminFloorHz : CLOCK_CPU_VMIN_510_HZ,
                 CLOCK_GPU_NORMAL_HZ, CLOCK_RAM_NORMAL_HZ};
            return true;
        case Stage::LowVminPlateauValidate:
            e = {(g.vminValidateIndex >= 0 && g.vminValidateIndex < g.vminValidateCount)
                    ? g.vminValidateHz[g.vminValidateIndex] : CLOCK_CPU_NORMAL_HZ,
                 CLOCK_GPU_NORMAL_HZ, CLOCK_RAM_NORMAL_HZ};
            return true;

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
    f << "vddqGood=" << g.vddqGood << "\n";
    f << "vddqTest=" << g.vddqTest << "\n";
    f << "vdd2GoodUv=" << g.vdd2GoodUv << "\n";
    f << "vdd2TestUv=" << g.vdd2TestUv << "\n";
    f << "highUvGood=" << g.highUvGood << "\n";
    f << "highUvTest=" << g.highUvTest << "\n";
    f << "vminFloorHz=" << g.vminFloorHz << "\n";
    f << "vminFloorObservedMv=" << g.vminFloorObservedMv << "\n";
    f << "ramPairRetryMode=" << g.ramPairRetryMode << "\n";
    f << "recoveryNeeded=" << (g.recoveryNeeded ? 1 : 0) << "\n";
    f << "warningBelow590Seen=" << (g.warningBelow590Seen ? 1 : 0) << "\n";
    f << "dramId=" << g.dramId << "\n";
    f << "consoleType=" << g.consoleType << "\n";
    f << "vddqStartMv=" << g.vddqStartMv << "\n";
    f << "ramDetected=" << (g.ramDetected ? 1 : 0) << "\n";
    f << "stageReadyAfterBoot=" << (g.stageReadyAfterBoot ? 1 : 0) << "\n";
    f << "rebootPending=" << (g.rebootPending ? 1 : 0) << "\n";
    f << "pendingConfigMask=" << g.pendingConfigMask << "\n";
    f << "vminObsMask=" << g.vminObsMask << "\n";
    f << "vminValidateCount=" << g.vminValidateCount << "\n";
    f << "vminValidateIndex=" << g.vminValidateIndex << "\n";
    f << "lastProbeHz=" << g.lastProbeHz << "\n";
    f << "lastProbeMv=" << g.lastProbeMv << "\n";
    for (int i = 0; i < 6; ++i) {
        f << "vminObsMv" << i << "=" << g.vminObsMv[i] << "\n";
        f << "vminValidateHz" << i << "=" << g.vminValidateHz[i] << "\n";
        f << "vminValidateMv" << i << "=" << g.vminValidateMv[i] << "\n";
    }
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
    const int v = std::atoi(value.c_str());
    if (key == "stage") g.stage = static_cast<Stage>(v);
    else if (key == "lowUvGood") g.lowUvGood = v;
    else if (key == "lowUvTest") g.lowUvTest = v;
    else if (key == "lowVminGood") g.lowVminGood = v;
    else if (key == "lowVminTest") g.lowVminTest = v;
    else if (key == "vddqGood") g.vddqGood = v;
    else if (key == "vddqTest") g.vddqTest = v;
    else if (key == "vdd2GoodUv") g.vdd2GoodUv = v;
    else if (key == "vdd2TestUv") g.vdd2TestUv = v;
    else if (key == "highUvGood") g.highUvGood = v;
    else if (key == "highUvTest") g.highUvTest = v;
    else if (key == "vminFloorHz") g.vminFloorHz = (u32)v;
    else if (key == "vminFloorObservedMv") g.vminFloorObservedMv = v;
    else if (key == "ramPairRetryMode") g.ramPairRetryMode = v;
    else if (key == "recoveryNeeded") g.recoveryNeeded = (v != 0);
    else if (key == "warningBelow590Seen") g.warningBelow590Seen = (v != 0);
    else if (key == "dramId") g.dramId = v;
    else if (key == "consoleType") g.consoleType = v;
    else if (key == "vddqStartMv") g.vddqStartMv = v;
    else if (key == "ramDetected") g.ramDetected = (v != 0);
    else if (key == "stageReadyAfterBoot") g.stageReadyAfterBoot = (v != 0);
    else if (key == "rebootPending") g.rebootPending = (v != 0);
    else if (key == "pendingConfigMask") g.pendingConfigMask = (u32)std::strtoul(value.c_str(), nullptr, 10);
    else if (key == "vminObsMask") g.vminObsMask = (u32)std::strtoul(value.c_str(), nullptr, 10);
    else if (key == "vminValidateCount") g.vminValidateCount = v;
    else if (key == "vminValidateIndex") g.vminValidateIndex = v;
    else if (key == "lastProbeHz") g.lastProbeHz = (u32)std::strtoul(value.c_str(), nullptr, 10);
    else if (key == "lastProbeMv") g.lastProbeMv = v;
    else if (key.rfind("vminObsMv", 0) == 0) { int i = std::atoi(key.c_str() + 9); if (i >= 0 && i < 6) g.vminObsMv[i] = v; }
    else if (key.rfind("vminValidateHz", 0) == 0) { int i = std::atoi(key.c_str() + 14); if (i >= 0 && i < 6) g.vminValidateHz[i] = (u32)std::strtoul(value.c_str(), nullptr, 10); }
    else if (key.rfind("vminValidateMv", 0) == 0) { int i = std::atoi(key.c_str() + 14); if (i >= 0 && i < 6) g.vminValidateMv[i] = v; }
    else if (key == "testRunning") g.testRunning = (v != 0);
    else if (key == "testKind") g.testKind = v;
    else if (key == "testDurationSec") g.testDurationSec = v;
    else if (key == "testStage") g.testStage = v;
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
    if (!g.ramDetected && g.stage == Stage::Preparation) g.stage = Stage::HardwareDetection;
    return true;
}

void resetState() {
    g = WizardState{};
    saveState();
}


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

void writeResults() {
    ensureDir();
    std::ofstream f(RESULTS, std::ios::trunc);
    if (!f) return;
    f << "HOC Undervolting Wizard - Final Results\n\n";
    if (g.ramDetected) {
        const RamProfile rp = ramProfileForId(g.dramId);
        f << "Detected RAM: " << rp.name << " (ID " << g.dramId << ")\n";
        f << "VDDQ starting point: " << g.vddqStartMv << " mV\n";
    }
    f << "CPU UV Table: 1683 MHz Tbreak\n";
    f << "CPU Low UV: " << g.lowUvGood << "\n";
    f << "CPU Low VMIN: " << g.lowVminGood << " mV\n";
    f << "RAM VDDQ: " << g.vddqGood << " mV\n";
    f << "RAM VDD2: " << formatVdd2(g.vdd2GoodUv) << "\n";
    f << "CPU High UV: " << g.highUvGood << "\n";
    if (g.vminFloorHz)
        f << "Detected highest Low VMIN floor clock: " << (g.vminFloorHz / 1000000U) << " MHz (~" << g.vminFloorObservedMv << " mV)\n";
    if (g.vminValidateCount > 0) {
        f << "CPU voltage regions validated:\n";
        for (int i = 0; i < g.vminValidateCount; ++i)
            f << "  " << (g.vminValidateHz[i] / 1000000U) << " MHz @ ~" << g.vminValidateMv[i] << " mV\n";
    }
    f << "\n";
    f << "Built-in CPU/RAM/combined/GPU validation completed.\n";
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
        case Stage::HardwareDetection: return "Hardware Detection";
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
        case Stage::LowVminPlateauValidate: return "CPU Low VMIN - Plateau";
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
    if (isQuickStage(g.stage)) uiPrintf(row + 4, "Y : Did Not Boot");
    uiPrintf(row + 5, "B : Exit    - : Reset");
}


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

void renderPreparation() {
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
}


bool isVminSweepStage(Stage st);

void renderTestStage() {
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
}


bool isVminSweepStage(Stage st) {
    return st == Stage::LowVminLong || st == Stage::LowVminSweep612 ||
           st == Stage::LowVminSweep714 || st == Stage::LowVminValidate816 ||
           st == Stage::LowVminSweep918 || st == Stage::LowVminValidate1020;
}

u32 vminSweepClock(Stage st) {
    switch (st) {
        case Stage::LowVminLong: return CLOCK_CPU_VMIN_510_HZ;
        case Stage::LowVminSweep612: return CLOCK_CPU_LOW_HZ;
        case Stage::LowVminSweep714: return CLOCK_CPU_VMIN_714_HZ;
        case Stage::LowVminValidate816: return CLOCK_CPU_VMIN_MID_HZ;
        case Stage::LowVminSweep918: return CLOCK_CPU_VMIN_918_HZ;
        case Stage::LowVminValidate1020: return CLOCK_CPU_NORMAL_HZ;
        default: return 0;
    }
}

void recordVminObservation(Stage st) {
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
}


void restartVminSweep(bool recovery) {
    const u32 keepMask = g.pendingConfigMask;
    g.stage = Stage::LowVminLong;
    g.recoveryNeeded = recovery;
    clearVminSweepData();
    g.pendingConfigMask = keepMask;
    saveState();
}


void enterLowUvLong(bool recovery) { g.stage = Stage::LowUvLong; g.recoveryNeeded = recovery; saveState(); }
void enterLowVminLong(bool recovery) { restartVminSweep(recovery); }
void enterVddqLong(bool recovery) { g.stage = Stage::VddqLong; g.recoveryNeeded = recovery; saveState(); }
void enterVdd2Long(bool recovery) { g.stage = Stage::Vdd2Long; g.recoveryNeeded = recovery; saveState(); }
void enterHighUvLong(bool recovery) { g.stage = Stage::HighUvLong; g.recoveryNeeded = recovery; saveState(); }

void handlePass() {
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
}


void handleFail(bool didNotBoot) {
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
}


void runVminProbe() {
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
}


void runCurrentTest() {
    stress::Kind kind;
    int seconds = 0;
    if (!testPlan(g.stage, kind, seconds)) return;

    // Hard pre-flight: every built-in test requires all three expected
    // Horizon OC Temporary Overrides. A missing/wrong override blocks the test.
    g_overrideAction = PendingOverrideAction::StartTest;
    if (!checkAllOverrides(g.stage)) {
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
    g_resultScreen = true;
}

} // namespace

int main(int argc, char** argv) {
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
}

