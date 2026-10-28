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
#include <vector>

namespace {

constexpr const char* APP_DIR   = "sdmc:/switch/HOC-Undervolting-Wizard";
constexpr const char* STATE     = "sdmc:/switch/HOC-Undervolting-Wizard/state.ini";
constexpr const char* STATE_TMP = "sdmc:/switch/HOC-Undervolting-Wizard/state.tmp";
constexpr const char* RESULTS   = "sdmc:/switch/HOC-Undervolting-Wizard/results.txt";
constexpr const char* LEGACY_STATE = "sdmc:/switch/HOC-Battery-Wizard/state.ini";
constexpr const char* HOC_CONFIG_INI = "sdmc:/config/horizon-oc/config.ini";
constexpr const char* HOC_CONFIG_TMP = "sdmc:/config/horizon-oc/config.ini.wizard.tmp";
constexpr const char* HOC_CONFIG_BACKUP = "sdmc:/config/horizon-oc/config.ini.wizard.bak";

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
constexpr int LOW_VMIN_STEP_MV = 10;
constexpr int VDDQ_STEP_MV = 10;
constexpr u32 VMIN_FLOOR_TOLERANCE_UV = 5000U;
constexpr int VDD2_STEP_UV = 12500;
constexpr int UI_COL = 36;

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
    LowVminPlateauValidate,
    // beta.25: LowUvQuick is boot-limit discovery; validation is separate.
    LowUvValidateQuick
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
bool g_configDebugScreen = false;
int g_configDebugPage = 0;
HocMonConfigDebug g_configDebug{};
Result g_configDebugRc = 0;
bool g_rebootConfirm = false;
bool g_autoPrepConfirm = false;
u32 g_autoSetMask = Config_Prepare;
std::string g_autoPrepError;
bool g_bootPrompt = false;
bool g_scanForLowUv = false;
ConfigCheckState g_configCheck;
Result g_rebootError = 0;
Result g_hardwareReadRc = 0;
HocMonHardware g_hardware{};
Result g_hardwareDebugRc = 0;
HocMonHardwareDebug g_hardwareDebug{};

bool g_vminScanScreen = false;
bool g_vminScanSuccess = false;
bool g_vminScanRestoreOk = true;
Result g_vminScanErrorRc = 0;
std::string g_vminScanErrorText;

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
        case Stage::LowUvQuick: return "CPU Low UV - Boot Search";
        case Stage::LowUvValidateQuick: return "CPU Low UV - Region Validation";
        case Stage::LowUvLong: return "CPU Low UV - Voltage Scan";
        case Stage::LowVminQuick: return "CPU Low VMIN - Boot Search";
        case Stage::LowVminLong: return "CPU Low VMIN - Floor Sweep @ 510";
        case Stage::LowVminSweep612: return "CPU Low VMIN - Floor Sweep @ 612";
        case Stage::LowVminSweep714: return "CPU Low VMIN - Floor Sweep @ 714";
        case Stage::LowVminValidate816: return "CPU Low VMIN - Floor Sweep @ 816";
        case Stage::LowVminSweep918: return "CPU Low VMIN - Floor Sweep @ 918";
        case Stage::LowVminValidate1020: return "CPU Low VMIN - Floor Sweep @ 1020";
        case Stage::LowVminFinalLong: return "CPU Low VMIN - Dynamic 1 Hour Validation";
        case Stage::LowVminPlateauValidate: return "CPU Low VMIN - Region Validation";
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

bool testPlan(Stage s, stress::Kind& kind, int& seconds) {
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
}

bool overridePlan(Stage s, OverrideExpectation& e) {
    switch (s) {
        case Stage::LowUvQuick:
        case Stage::LowUvValidateQuick:
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
bool sampleVminVoltage(Stage s, int sweepIndex = -1, int sweepTotal = 0) {
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

    // States written by beta.15 used a manual 510->1020 MHz sweep. If an old
    // state is resumed in the middle/end of that flow, restart at beta.16+'s
    // automatic scan instead of entering plateau validation with empty data.
    const bool legacyVminState =
        g.stage == Stage::LowVminSweep612 || g.stage == Stage::LowVminSweep714 ||
        g.stage == Stage::LowVminValidate816 || g.stage == Stage::LowVminSweep918 ||
        g.stage == Stage::LowVminValidate1020 ||
        (g.stage == Stage::LowVminFinalLong && g.vminValidateCount == 0);
    if (legacyVminState) {
        g.stage = Stage::LowVminLong;
        g.stageReadyAfterBoot = true;
        g.pendingConfigMask = Config_None;
        g.vminObsMask = 0;
        g.vminValidateCount = 0;
        g.vminValidateIndex = 0;
        g.lastProbeHz = 0;
        g.lastProbeMv = 0;
        for (int i = 0; i < 6; ++i) {
            g.vminObsMv[i] = 0;
            g.vminValidateHz[i] = 0;
            g.vminValidateMv[i] = 0;
        }
    }
    return true;
}

void resetState() {
    g = WizardState{};
    saveState();
}


struct RamProfile {
    const char* name;
    int vddqStartMv;
    const char* ocRange;
    bool known;
};

RamProfile ramProfileForId(int id) {
    switch (id) {
        case 3: case 5: case 6: return {"NEE 4GB", 640, "3100-3300 MHz", true};
        case 8: case 12: return {"AM-MGCJ 4GB", 640, "2633-2933 MHz", true};
        case 9: case 13: return {"AM-MGCJ 8GB", 640, "2633-2933 MHz", true};
        case 10: case 14: return {"NME 4GB", 640, "2300-2766 MHz", true};
        case 11: case 15: return {"WT:E 4GB", 600, "2500?-3033 MHz", true};
        case 17: case 19: case 24: return {"AA-MGCL 4GB", 640, "2766-3100 MHz", true};
        case 18: case 23: case 28: return {"AA-MGCL 8GB", 640, "2766-3100 MHz", true};
        case 20: case 21: case 22: return {"AB-MGCL 4GB", 640, "2500-2766 MHz", true};
        case 25: case 26: case 27: return {"WT:F 4GB", 600, "2633-2800 MHz", true};
        case 29: case 30: case 31: return {"x267 4GB", 640, "3100-3300 MHz", true};
        case 32: case 33: case 34: return {"WT:B 4GB", 600, "3066-3200 MHz", true};
        default: return {"Unknown", STOCK_VDDQ_MV, "Unknown", false};
    }
}

bool ramTuningAlreadyStarted(Stage st) {
    switch (st) {
        case Stage::VddqQuick:
        case Stage::VddqLong:
        case Stage::Vdd2Quick:
        case Stage::Vdd2Long:
        case Stage::RamBoostValidate:
        case Stage::Ram1331Validate:
        case Stage::HighUvQuick:
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
            return true;
        default:
            return false;
    }
}

bool detectRamHardware() {
    g_hardware = HocMonHardware{};
    g_hardwareDebug = HocMonHardwareDebug{};
    g_hardwareReadRc = hocmonGetHardware(&g_hardware);
    g_hardwareDebugRc = hocmonGetHardwareDebug(&g_hardwareDebug);
    if (R_FAILED(g_hardwareReadRc)) return false;
    const RamProfile p = ramProfileForId(g_hardware.dramId);
    // Icosa = Erista/V1, outside this Mariko Battery guide.
    if (!p.known || g_hardware.consoleType == 0) return false;
    const bool keepExistingRamTune = ramTuningAlreadyStarted(g.stage);
    g.dramId = g_hardware.dramId;
    g.consoleType = (int)g_hardware.consoleType;
    g.vddqStartMv = p.vddqStartMv;
    g.ramDetected = true;
    if (!keepExistingRamTune) {
        g.vddqGood = g.vddqStartMv;
        g.vddqTest = g.vddqStartMv - VDDQ_STEP_MV;
    }
    saveState();
    return true;
}

u32 defaultConfigMaskForStage(Stage st) {
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
}

u32 activeConfigMask() {
    if (g.stageReadyAfterBoot) return Config_None;
    if (g.pendingConfigMask) return g.pendingConfigMask;
    return defaultConfigMaskForStage(g.stage);
}

int targetLowUv() {
    // LowUvQuick is the boot-limit search. Validation uses the last value
    // that actually booted.
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

std::string trimIni(const std::string& in) {
    const size_t first = in.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return {};
    const size_t last = in.find_last_not_of(" \t\r\n");
    return in.substr(first, last - first + 1);
}

bool readHocConfigIni(HocMonConfig& out) {
    out = HocMonConfig{};
    std::ifstream f(HOC_CONFIG_INI);
    if (!f) return false;

    bool inValues = false;
    bool sawValuesSection = false;
    std::string line;
    while (std::getline(f, line)) {
        line = trimIni(line);
        if (line.empty() || line[0] == ';' || line[0] == '#') continue;

        if (line.front() == '[' && line.back() == ']') {
            inValues = (line == "[values]");
            if (inValues) sawValuesSection = true;
            continue;
        }
        if (!inValues) continue;

        const size_t eq = line.find('=');
        if (eq == std::string::npos) continue;
        const std::string key = trimIni(line.substr(0, eq));
        const std::string valueText = trimIni(line.substr(eq + 1));
        if (key.empty() || valueText.empty()) continue;

        char* end = nullptr;
        const unsigned long long value = std::strtoull(valueText.c_str(), &end, 0);
        if (end == valueText.c_str()) continue;

        if (key == "uncapped_clocks") out.uncappedClocks = (value != 0);
        else if (key == "kip_hp_mode") out.hpMode = (value != 0);
        else if (key == "mariko_emc_max_clock") out.ramMaxKHz = (u32)value;
        else if (key == "common_emc_mem_volt") out.vdd2Uv = (u32)value;
        else if (key == "mariko_emc_vddq_volt") out.vddqUv = (u32)value;
        else if (key == "mariko_cpu_uv_low") out.lowUv = (int)value;
        else if (key == "mariko_cpu_uv_high") out.highUv = (int)value;
        else if (key == "kip_table_conf") out.tableConf = (int)value;
        else if (key == "mariko_cpu_low_vmin") out.lowVminMv = (int)value;
        else if (key == "mariko_cpu_high_vmin") out.highVminMv = (int)value;
        else if (key == "mariko_cpu_max_clock") out.cpuMaxKHz = (u32)value;
        else if (key == "mariko_cpu_boost_clock") out.cpuBoostKHz = (u32)value;
    }

    return sawValuesSection;
}

bool verifyPersistentSettings(u32 mask);

bool writeAutomaticPreparationConfig(std::string& errorText) {
    errorText.clear();

    std::ifstream src(HOC_CONFIG_INI);
    if (!src) {
        errorText = "Could not open Horizon OC config.ini.";
        return false;
    }

    std::vector<std::string> lines;
    std::string line;
    while (std::getline(src, line)) lines.push_back(line);
    src.close();

    struct PrepValue { const char* key; std::string value; };
    const PrepValue values[] = {
        {"uncapped_clocks", "0"},
        {"kip_hp_mode", "0"},
        {"mariko_emc_max_clock", "1600000"},
        {"common_emc_mem_volt", std::to_string(STOCK_VDD2_UV)},
        {"mariko_emc_vddq_volt", std::to_string(g.vddqStartMv * 1000)},
        {"mariko_cpu_max_clock", "1963500"},
        {"mariko_cpu_low_vmin", std::to_string(STOCK_LOW_VMIN_MV)},
        {"mariko_cpu_high_vmin", std::to_string(STOCK_HIGH_VMIN_MV)},
        {"kip_table_conf", "3"},
        {"mariko_cpu_uv_low", std::to_string(STOCK_LOW_UV)},
        {"mariko_cpu_uv_high", std::to_string(STOCK_HIGH_UV)},
        {"mariko_cpu_boost_clock", "1785000"},
    };
    constexpr size_t valueCount = sizeof(values) / sizeof(values[0]);
    bool written[valueCount] = {};

    std::vector<std::string> out;
    out.reserve(lines.size() + valueCount + 3);
    bool inValues = false;
    bool sawValues = false;

    auto appendMissing = [&]() {
        for (size_t i = 0; i < valueCount; ++i) {
            if (!written[i]) {
                out.push_back(std::string(values[i].key) + "=" + values[i].value);
                written[i] = true;
            }
        }
    };

    for (const std::string& raw : lines) {
        const std::string trimmed = trimIni(raw);
        if (!trimmed.empty() && trimmed.front() == '[' && trimmed.back() == ']') {
            if (inValues) appendMissing();
            inValues = (trimmed == "[values]");
            if (inValues) sawValues = true;
            out.push_back(raw);
            continue;
        }

        if (inValues) {
            const size_t eq = trimmed.find('=');
            if (eq != std::string::npos) {
                const std::string key = trimIni(trimmed.substr(0, eq));
                bool replaced = false;
                for (size_t i = 0; i < valueCount; ++i) {
                    if (key == values[i].key) {
                        out.push_back(std::string(values[i].key) + "=" + values[i].value);
                        written[i] = true;
                        replaced = true;
                        break;
                    }
                }
                if (replaced) continue;
            }
        }
        out.push_back(raw);
    }

    if (inValues) appendMissing();
    if (!sawValues) {
        if (!out.empty() && !out.back().empty()) out.push_back("");
        out.push_back("[values]");
        appendMissing();
    }

    if (!copyFile(HOC_CONFIG_INI, HOC_CONFIG_BACKUP)) {
        errorText = "Could not create config.ini backup.";
        return false;
    }

    std::ofstream dst(HOC_CONFIG_TMP, std::ios::trunc);
    if (!dst) {
        errorText = "Could not create temporary config.ini.";
        return false;
    }
    for (const std::string& outLine : out) dst << outLine << "\n";
    dst.flush();
    const bool writeOk = bool(dst);
    dst.close();
    if (!writeOk) {
        remove(HOC_CONFIG_TMP);
        errorText = "Writing temporary config.ini failed.";
        return false;
    }

    remove(HOC_CONFIG_INI);
    if (rename(HOC_CONFIG_TMP, HOC_CONFIG_INI) != 0) {
        copyFile(HOC_CONFIG_BACKUP, HOC_CONFIG_INI);
        remove(HOC_CONFIG_TMP);
        errorText = "Replacing config.ini failed; backup restored.";
        return false;
    }

    fsdevCommitDevice("sdmc");
    return true;
}

void resetPreparationBaselineState() {
    g.lowUvGood = STOCK_LOW_UV;
    g.lowUvTest = STOCK_LOW_UV + 1;
    g.lowVminGood = STOCK_LOW_VMIN_MV;
    g.lowVminTest = STOCK_LOW_VMIN_MV - LOW_VMIN_STEP_MV;
    g.vddqGood = g.vddqStartMv;
    g.vddqTest = g.vddqStartMv - VDDQ_STEP_MV;
    g.vdd2GoodUv = STOCK_VDD2_UV;
    g.vdd2TestUv = STOCK_VDD2_UV - VDD2_STEP_UV;
    g.highUvGood = STOCK_HIGH_UV;
    g.highUvTest = STOCK_HIGH_UV + 1;
    g.recoveryNeeded = false;
    g.stageReadyAfterBoot = false;
    g.pendingConfigMask = Config_None;
}

bool applyAutomaticPreparation() {
    HocMonConfig desired{};
    desired.uncappedClocks = false;
    desired.hpMode = false;
    desired.ramMaxKHz = 1600000U;
    desired.vdd2Uv = (u32)STOCK_VDD2_UV;
    desired.vddqUv = (u32)g.vddqStartMv * 1000U;
    desired.lowUv = STOCK_LOW_UV;
    desired.highUv = STOCK_HIGH_UV;
    desired.tableConf = 3;
    desired.lowVminMv = STOCK_LOW_VMIN_MV;
    desired.highVminMv = STOCK_HIGH_VMIN_MV;
    desired.cpuMaxKHz = 1963500U;
    desired.cpuBoostKHz = 1785000U;

    const Result rc = hocmonApplyPreparation251(&desired);
    if (R_FAILED(rc)) {
        if (rc == 4)
            g_autoPrepError = "Automatic setup currently supports Horizon OC 2.5.1 only.";
        else {
            char msg[96];
            std::snprintf(msg, sizeof(msg), "Horizon OC Save KIP failed: 0x%08X", rc);
            g_autoPrepError = msg;
        }
        return false;
    }

    // HOC's SetConfigValues updates config.ini and live config; SetKipData persists
    // the KIP. Read the named INI keys back before allowing a reboot.
    svcSleepThread(150'000'000);
    if (!verifyPersistentSettings(Config_Prepare)) {
        g_autoPrepError = "Horizon OC readback did not match the requested Preparation values.";
        return false;
    }

    resetPreparationBaselineState();
    g.pendingConfigMask = Config_Prepare;
    g.rebootPending = false;
    saveState();
    return true;
}

bool applyAutomaticCurrentSetting(u32 mask) {
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

bool preparationFixedSettingsMatch(const HocMonConfig& c) {
    return !c.uncappedClocks && !c.hpMode &&
           c.ramMaxKHz == 1600000U &&
           c.cpuMaxKHz == 1963500U &&
           c.tableConf == 3 &&
           c.cpuBoostKHz == 1785000U &&
           c.vdd2Uv != 0 && c.vddqUv != 0 &&
           c.lowVminMv != 0 && c.highVminMv != 0;
}

bool captureCurrentSettingsBaseline() {
    g_configCheck = ConfigCheckState{};
    g_configCheck.mask = Config_Prepare;
    g_configCheck.readOk = readHocConfigIni(g_configCheck.current);
    g_configCheck.rc = g_configCheck.readOk ? 0 : 0xF024;
    if (!g_configCheck.readOk || !preparationFixedSettingsMatch(g_configCheck.current))
        return false;

    const HocMonConfig& c = g_configCheck.current;
    g.lowUvGood = std::max(0, c.lowUv);
    g.lowUvTest = (g.lowUvGood < LOW_UV_MAX) ? g.lowUvGood + 1 : g.lowUvGood;
    g.lowVminGood = c.lowVminMv;
    g.lowVminTest = (g.lowVminGood > LOW_VMIN_MIN_MV) ? g.lowVminGood - LOW_VMIN_STEP_MV : g.lowVminGood;
    g.vddqGood = (int)(c.vddqUv / 1000U);
    g.vddqTest = (g.vddqGood > VDDQ_MIN_MV) ? g.vddqGood - VDDQ_STEP_MV : g.vddqGood;
    g.vdd2GoodUv = (int)c.vdd2Uv;
    g.vdd2TestUv = (g.vdd2GoodUv > VDD2_MIN_UV) ? g.vdd2GoodUv - VDD2_STEP_UV : g.vdd2GoodUv;
    g.highUvGood = std::max(0, c.highUv);
    g.highUvTest = (g.highUvGood < HIGH_UV_MAX) ? g.highUvGood + 1 : g.highUvGood;
    g.stageReadyAfterBoot = false;
    g.pendingConfigMask = Config_None;
    saveState();
    return true;
}

void continueFromPreparationBaseline() {
    // Nothing was changed: these values are already the user's active baseline.
    // Do not perform a fake Preparation reboot. Move directly to the first new
    // Low UV candidate, which will get its own normal set -> reboot -> 1 min test.
    g.rebootPending = false;
    g.pendingConfigMask = Config_None;
    if (g.lowUvGood >= LOW_UV_MAX) {
        g.stage = Stage::LowUvLong;
        g.stageReadyAfterBoot = true;
    } else {
        g.stage = Stage::LowUvQuick;
        g.lowUvTest = g.lowUvGood + 1;
        g.stageReadyAfterBoot = false;
    }
    saveState();
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
    g_configCheck.readOk = readHocConfigIni(g_configCheck.current);
    g_configCheck.rc = g_configCheck.readOk ? 0 : 0xF024;
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
        case Stage::LowUvQuick: return "CPU Low UV - Boot Search";
        case Stage::LowUvValidateQuick: return "CPU Low UV - Region Test";
        case Stage::LowUvLong: return "CPU Low UV - Voltage Scan";
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
    uiPrintf(row++, "A : Start automatic 1-minute tests");
    uiPrintf(row++, "B : Exit");
    consoleUpdate(nullptr);
}

void renderHardwareDetection() {
    title();
    if (g.ramDetected) {
        const RamProfile rp = ramProfileForId(g.dramId);
        uiPrintf(6, "\x1b[32mRAM detected\x1b[0m");
        uiPrintf(8, "Module     : %s", rp.name);
        uiPrintf(9, "DRAM ID    : %d", g.dramId);
        uiPrintf(11, "VDDQ start : %d mV", g.vddqStartMv);
        uiPrintf(12, "OC range   : %s", rp.ocRange);
        uiPrintf(13, "             Guide estimate - silicon varies");
        uiPrintf(16, "A : Continue to Preparation");
        uiPrintf(17, "B : Exit");
        return;
    }

    uiPrintf(5, "\x1b[31mRAM detection failed\x1b[0m");
    uiPrintf(6, "hoc:clk result : 0x%08X", g_hardwareReadRc);

    if (R_SUCCEEDED(g_hardwareDebugRc)) {
        uiPrintf(8,  "DEBUG - please photograph this screen");
        uiPrintf(9,  "HOC API : %u", g_hardwareDebug.apiVersion);
        uiPrintf(10, "Raw 400-405: %02X %02X %02X %02X %02X %02X",
                 g_hardwareDebug.raw400_411[0], g_hardwareDebug.raw400_411[1],
                 g_hardwareDebug.raw400_411[2], g_hardwareDebug.raw400_411[3],
                 g_hardwareDebug.raw400_411[4], g_hardwareDebug.raw400_411[5]);
        uiPrintf(11, "Raw 406-411: %02X %02X %02X %02X %02X %02X",
                 g_hardwareDebug.raw400_411[6], g_hardwareDebug.raw400_411[7],
                 g_hardwareDebug.raw400_411[8], g_hardwareDebug.raw400_411[9],
                 g_hardwareDebug.raw400_411[10], g_hardwareDebug.raw400_411[11]);
        uiPrintf(13, "console@408 : %d", g_hardwareDebug.consoleTypeAt408);
        uiPrintf(14, "ID@403:%u  8GB@404:%u  known:%s",
                 g_hardwareDebug.idAt403, g_hardwareDebug.is8At404,
                 g_hardwareDebug.id403Known ? "YES" : "NO");
        uiPrintf(15, "ID@404:%u  8GB@405:%u  known:%s",
                 g_hardwareDebug.idAt404, g_hardwareDebug.is8At405,
                 g_hardwareDebug.id404Known ? "YES" : "NO");
    } else {
        uiPrintf(8, "Debug read failed: 0x%08X", g_hardwareDebugRc);
    }

    uiPrintf(18, "A : Retry detection");
    uiPrintf(19, "B : Exit");
}


enum class BootInference { Unknown, RequestedActive, SaferActive };

BootInference inferBootState(int* activeValue = nullptr) {
    HocMonConfig c{};
    // After reboot, inspect the RUNNING Horizon OC config, not only config.ini.
    // If hoc:clk is unavailable (for example CFW No OC), the boot cannot be
    // counted as a successful normal-HOC boot.
    if (R_FAILED(hocmonGetConfig251(&c))) return BootInference::Unknown;

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

void renderBootPrompt() {
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
        uiPrintf(row++, "Console booted with requested value.");
        row++;
        uiPrintf(row++, "Only continue if normal CFW booted AND:");
        uiPrintf(row++, " - no system freeze");
        uiPrintf(row++, " - no crash");
        uiPrintf(row++, " - no spontaneous reboot/system failure");
        row += 2;
        uiPrintf(row++, "A : Stable boot - continue");
        uiPrintf(row++, "X : Not stable / crashed / froze");
    } else if (state == BootInference::SaferActive) {
        uiPrintf(row++, "\x1b[33mRequested value is NOT active.\x1b[0m");
        uiPrintf(row++, "It looks like this value did not boot.");
        uiPrintf(row++, "Recovery restored last working value.");
        row++;
        if (g.stage == Stage::LowUvQuick)
            uiPrintf(row++, "\x1b[32mLast good value: Low UV %d\x1b[0m", active);
        else if (g.stage == Stage::LowVminQuick)
            uiPrintf(row++, "\x1b[32mLast good value: Low VMIN %d mV\x1b[0m", active);
        row++;
        uiPrintf(row++, "Confirm this matches your recovery.");
        uiPrintf(row++, "A : Confirm last good value");
        uiPrintf(row++, "X : This is not correct");
    } else {
        uiPrintf(row++, "\x1b[31mCould not confirm active value.\x1b[0m");
        uiPrintf(row++, "Check Horizon OC / recovery state.");
        row += 2;
        uiPrintf(row++, "A : Check again");
        uiPrintf(row++, "X : Treat as unstable and recover");
    }
    uiPrintf(row + 1, "B : Exit and decide later");
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

const char* cpuTableLabel(int table) {
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

void openConfigDebug() {
    g_configDebug = HocMonConfigDebug{};
    g_configDebugRc = hocmonGetConfigDebug(&g_configDebug);
    g_configDebugPage = 0;
    g_configDebugScreen = true;
}

void renderConfigDebug() {
    consoleClear();
    uiPrintf(1, "\x1b[36mBattery Wizard - CONFIG DEBUG\x1b[0m");
    uiPrintf(2, "HOC : %s", g_configDebug.version[0] ? g_configDebug.version : "<unknown>");
    uiPrintf(3, "API : %u", g_configDebug.apiVersion);
    uiPrintf(4, "----------------------------------------");

    if (R_FAILED(g_configDebugRc)) {
        uiPrintf(7, "\x1b[31mRaw config read failed\x1b[0m");
        uiPrintf(8, "Result : 0x%08X", g_configDebugRc);
        uiPrintf(11, "B : Back");
        consoleUpdate(nullptr);
        return;
    }

    constexpr int perPage = 24;
    constexpr int rows = 12;
    constexpr int pages = 4; // indexes 0..95 cover every Battery Wizard field
    const int base = g_configDebugPage * perPage;
    uiPrintf(5, "Raw GetConfigValues  Page %d / %d", g_configDebugPage + 1, pages);
    uiPrintf(6, " index:value               index:value");
    for (int r = 0; r < rows; ++r) {
        const int a = base + r;
        const int b = base + rows + r;
        uiPrintf(7 + r, " %3d:%-12llu       %3d:%llu",
                 a, (unsigned long long)g_configDebug.values[a],
                 b, (unsigned long long)g_configDebug.values[b]);
    }
    uiPrintf(21, "A : Next page    X : Previous page");
    uiPrintf(22, "B : Back to Preparation check");
    consoleUpdate(nullptr);
}

void renderConfigPrompt() {
    consoleClear();
    uiPrintf(1, "\x1b[31mBattery Wizard - SETTING NOT READY\x1b[0m");
    uiPrintf(2, "Step : %s", compactStepName(g.stage));
    uiPrintf(3, "----------------------------------------");
    if (!g_configCheck.readOk) {
        const int r = 5;
        uiPrintf(r, "Could not read Horizon OC config.ini");
        uiPrintf(r + 1, "Result : 0x%08X", g_configCheck.rc);
        uiPrintf(r + 4, "A : Check again");
        uiPrintf(r + 5, "B : Back");
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
    if (m & (Config_Prepare | Config_LowUv | Config_LowVmin))
        uiPrintf(row + 4, "Y : Set required value(s) automatically");
    if (g.stage == Stage::Preparation) {
        uiPrintf(row + 5, "X : Use my current settings as baseline");
        uiPrintf(row + 6, "B : Back");
    } else {
        uiPrintf(row + 5, "B : Back");
    }
    consoleUpdate(nullptr);
}

void renderAutoPrepConfirm() {
    consoleClear();
    uiPrintf(1, "\x1b[36mBattery Wizard\x1b[0m");
    uiPrintf(2, "Step : Automatic Setting");
    uiPrintf(3, "----------------------------------------");
    if (g_autoSetMask & Config_Prepare)
        uiPrintf(5, "Auto-set required Preparation values?");
    else if (g_autoSetMask & Config_LowUv)
        uiPrintf(5, "Set CPU Low UV %d automatically?", targetLowUv());
    else if (g_autoSetMask & Config_LowVmin)
        uiPrintf(5, "Set CPU Low VMIN %d mV automatically?", targetLowVmin());
    uiPrintf(7, "Uses HOC SetConfigValues + Save KIP.");
    uiPrintf(8, "Other Horizon OC values stay unchanged.");
    uiPrintf(10, "Horizon OC 2.5.1 is required.");
    uiPrintf(12, "Value is read back before reboot.");
    if (!g_autoPrepError.empty())
        uiPrintf(15, "\x1b[31m%s\x1b[0m", g_autoPrepError.c_str());
    uiPrintf(20, "A : Confirm - set value(s)");
    uiPrintf(21, "B : Cancel");
    consoleUpdate(nullptr);
}

void renderRebootConfirm() {
    consoleClear();
    uiPrintf(1, "\x1b[36mBattery Wizard\x1b[0m");
    uiPrintf(2, "Step : %s", compactStepName(g.stage));
    uiPrintf(3, "----------------------------------------");
    const u32 m = g_configCheck.mask;
    if (m & Config_Prepare)
        uiPrintf(5, "\x1b[32mPreparation values saved and verified.\x1b[0m");
    else if (m & Config_LowUv)
        uiPrintf(5, "\x1b[32mLow UV %d saved and verified.\x1b[0m", targetLowUv());
    else if (m & Config_LowVmin)
        uiPrintf(5, "\x1b[32mLow VMIN %d mV saved and verified.\x1b[0m", targetLowVmin());
    else
        uiPrintf(5, "\x1b[32mRequested setting saved and verified.\x1b[0m");

    uiPrintf(7, "Reboot required to apply the KIP value.");
    uiPrintf(8, "After reboot, open this Wizard again.");
    uiPrintf(10, "\x1b[33mIf normal CFW fails to boot or crashes:\x1b[0m");
    uiPrintf(11, "1. Boot Hekate.");
    uiPrintf(12, "2. Start CFW No OC / without hoc.kip.");
    uiPrintf(13, "3. Restore the previous safe value.");
    uiPrintf(14, "4. Reboot normal CFW.");
    uiPrintf(15, "5. Open this Wizard again.");
    uiPrintf(18, "A : Reboot now");
    uiPrintf(19, "B : Back");
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
    uiPrintf(26, " - CPU Boost : lowest / 1785 MHz");

    uiPrintf(28, "A : Check settings");
    uiPrintf(29, "X : Use my current settings as baseline");
    uiPrintf(30, "Y : Set values automatically + reboot");
    uiPrintf(31, "B : Exit    - : Reset");
}


bool isVminSweepStage(Stage st);

void renderTestStage() {
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
            uiPrintf(setRow++, "Find highest Low UV that boots.");
        else if (g.stage == Stage::LowVminQuick)
            uiPrintf(setRow++, "Lower Low VMIN 10 mV until boot fails.");
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
        uiPrintf(row++, "Next, Wizard maps CPU voltage at:");
        uiPrintf(row++, "510 / 612 / 714 / 816 / 918 / 1020 MHz");
        uiPrintf(row++, "It keeps highest frequency from each");
        uiPrintf(row++, "different voltage region for testing.");
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
        uiPrintf(row++, "Wizard sets each override.");
        uiPrintf(row++, "Each CPU frequency runs for 1 minute.");
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
    if (g_vminScanScreen) { renderVminScanScreen(); return; }
    if (g_interruptedPrompt) { renderInterruptedPrompt(); return; }
    if (g_configDebugScreen) { renderConfigDebug(); return; }
    if (g_configPrompt) { renderConfigPrompt(); return; }
    if (g_autoPrepConfirm) { renderAutoPrepConfirm(); return; }
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
            // Boot-stable candidate confirmed by the post-reboot check.
            g.lowUvGood = g.lowUvTest;
            if (g.lowUvTest >= LOW_UV_MAX) {
                g.stage = Stage::LowUvLong;
                g.stageReadyAfterBoot = true;
            } else {
                ++g.lowUvTest;
                g.stageReadyAfterBoot = false;
            }
            break;
        case Stage::LowUvValidateQuick:
            g.stage = Stage::LowUvLong;
            g.stageReadyAfterBoot = true;
            break;
        case Stage::LowUvLong:
            g.recoveryNeeded = false;
            if (g.lowVminGood <= LOW_VMIN_MIN_MV) {
                restartVminSweep(false);
                g.stageReadyAfterBoot = true;
            } else {
                g.stage = Stage::LowVminQuick;
                g.lowVminTest = g.lowVminGood - LOW_VMIN_STEP_MV;
                g.stageReadyAfterBoot = false;
            }
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
                if (g.vddqGood <= VDDQ_MIN_MV) {
                    g.stage = Stage::VddqLong;
                    g.stageReadyAfterBoot = true;
                } else {
                    g.stage = Stage::VddqQuick;
                    g.vddqTest = g.vddqGood - VDDQ_STEP_MV;
                    g.stageReadyAfterBoot = false;
                }
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
            if (g.vdd2GoodUv <= VDD2_MIN_UV) {
                g.stage = Stage::Vdd2Long;
                g.stageReadyAfterBoot = true;
            } else {
                g.stage = Stage::Vdd2Quick;
                g.vdd2TestUv = g.vdd2GoodUv - VDD2_STEP_UV;
                g.stageReadyAfterBoot = false;
            }
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
            if (g.highUvGood >= HIGH_UV_MAX) {
                g.stage = Stage::HighUvLong;
                g.stageReadyAfterBoot = true;
            } else {
                g.stage = Stage::HighUvQuick;
                g.highUvTest = g.highUvGood + 1;
                g.stageReadyAfterBoot = false;
            }
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
            // Candidate failed either to boot or to pass its 1-minute test.
            // Restore the previous last-known-good value, reboot, then run
            // the 1-hour validation on that recovered value.
            g.stage = Stage::LowUvLong;
            g.recoveryNeeded = didNotBoot;
            g.pendingConfigMask = Config_LowUv;
            break;
        case Stage::LowUvValidateQuick:
            if (g.lowUvGood > 0) --g.lowUvGood;
            g.stage = Stage::LowUvLong;
            g.recoveryNeeded = false;
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
        case Stage::LowVminPlateauValidate:
            if (g.lowVminGood < STOCK_LOW_VMIN_MV)
                g.lowVminGood = std::min(STOCK_LOW_VMIN_MV, g.lowVminGood + LOW_VMIN_STEP_MV);
            g.stage = Stage::LowVminLong;
            g.pendingConfigMask = Config_LowVmin;
            clearVminSweepData();
            break;
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


bool sampleCpuVoltageAt(u32 cpuHz, int index, int total, int& outMv) {
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

void runAutomaticVminScan() {
    runAutomaticVoltageScan(false);
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

    // Identify Mariko DRAM on every upgraded state that does not have it yet.
    // New users remain on the dedicated Hardware Detection page; progressed
    // users are enriched silently without losing already-tuned RAM values.
    if (!g.ramDetected)
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

        if (g_vminScanScreen) {
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

        if (g_interruptedPrompt) {
            if (k & HidNpadButton_A) {
                g.testRunning = false;
                if (g.testStage >= 0 && g.testStage <= static_cast<int>(Stage::LowUvValidateQuick))
                    g.stage = static_cast<Stage>(g.testStage);
                g.testKind = g.testDurationSec = g.testStage = 0;
                saveState();
                handleFail(false);
                g_interruptedPrompt = false;
                redraw = true;
            } else if (k & HidNpadButton_X) {
                g.testRunning = false;
                if (g.testStage >= 0 && g.testStage <= static_cast<int>(Stage::LowUvValidateQuick))
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

        if (g_configDebugScreen) {
            if (k & HidNpadButton_A) {
                g_configDebugPage = (g_configDebugPage + 1) % 4;
                redraw = true;
            } else if (k & HidNpadButton_X) {
                g_configDebugPage = (g_configDebugPage + 3) % 4;
                redraw = true;
            } else if (k & HidNpadButton_B) {
                g_configDebugScreen = false;
                redraw = true;
            }
            svcSleepThread(20'000'000);
            continue;
        }

        if (g_configPrompt) {
            if ((k & HidNpadButton_Y) && (g_configCheck.mask & (Config_Prepare | Config_LowUv | Config_LowVmin))) {
                g_autoSetMask = g_configCheck.mask;
                g_autoPrepError.clear();
                g_configPrompt = false;
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

        if (g_autoPrepConfirm) {
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
                g_configPrompt = true;
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
                if (g_overrideAction == PendingOverrideAction::VminProbe) runAutomaticVminScan();
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
        } else if (g.stage == Stage::Preparation && (k & HidNpadButton_Y)) {
            g_autoSetMask = Config_Prepare;
            g_autoPrepError.clear();
            g_autoPrepConfirm = true;
            redraw = true;
        } else if (g.stage == Stage::Preparation && (k & HidNpadButton_X)) {
            if (captureCurrentSettingsBaseline()) continueFromPreparationBaseline();
            else g_configPrompt = true;
            redraw = true;
        } else if ((k & HidNpadButton_Y) && g.stage != Stage::Preparation) {
            const u32 cfgMask = activeConfigMask();
            if (cfgMask & (Config_LowUv | Config_LowVmin)) {
                g_autoSetMask = cfgMask;
                g_autoPrepError.clear();
                g_autoPrepConfirm = true;
                redraw = true;
            }
        } else if ((k & HidNpadButton_Plus) && g.stage != Stage::Preparation) {
            if (isVminSweepStage(g.stage)) {
                runAutomaticVminScan();
            } else {
                const u32 cfgMask = activeConfigMask();
                stress::Kind skipKind;
                int skipSeconds = 0;
                if (cfgMask != Config_None) {
                    // KNOWN PASS skips the reboot/stress validation, not the
                    // requirement to actually have the requested HOC value set.
                    if (verifyPersistentSettings(cfgMask)) {
                        g_manualPass = true;
                        handlePass();
                        g_manualPass = false;
                    } else {
                        g_configPrompt = true;
                    }
                } else if (testPlan(g.stage, skipKind, skipSeconds)) {
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
            } else if (g.stage == Stage::LowUvLong) {
                runAutomaticLowUvScan();
            } else if (g.stage == Stage::LowUvValidateQuick) {
                runAutomaticRegionValidation(true);
            } else if (g.stage == Stage::LowVminLong || isVminSweepStage(g.stage)) {
                runAutomaticVminScan();
            } else if (g.stage == Stage::LowVminPlateauValidate) {
                runAutomaticRegionValidation(false);
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

