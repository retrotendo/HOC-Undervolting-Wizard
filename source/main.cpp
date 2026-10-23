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
    RamBoostValidate
};

struct WizardState {
    Stage stage = Stage::Preparation;
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
        case Stage::LowVminFinalLong:
            e = {g.vminFloorHz ? g.vminFloorHz : CLOCK_CPU_VMIN_510_HZ,
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
        svcSleepThread(1'100'000'000);
    }

    if (count < 3) {
        // Preserve the latest context for the Expected/Current error screen.
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
    f << "CPU UV Table: 1683 MHz Tbreak\n";
    f << "CPU Low UV: " << g.lowUvGood << "\n";
    f << "CPU Low VMIN: " << g.lowVminGood << " mV\n";
    f << "RAM VDDQ: " << g.vddqGood << " mV\n";
    f << "RAM VDD2: " << formatVdd2(g.vdd2GoodUv) << "\n";
    f << "CPU High UV: " << g.highUvGood << "\n";
    if (g.vminFloorHz)
        f << "Detected highest Low VMIN floor clock: " << (g.vminFloorHz / 1000000U) << " MHz (~" << g.vminFloorObservedMv << " mV)\n";
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
    if (isQuickStage(g.stage)) uiPrintf(row + 4, "Y : Did Not Boot");
    uiPrintf(row + 5, "B : Exit    - : Reset");
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
    uiPrintf(14, " - VDDQ            : 600 mV");

    uiPrintf(16, "CPU Settings:");
    uiPrintf(17, " - CPU Max         : Lowest selectable (1963)");
    uiPrintf(18, " - Low VMIN        : 620 mV");
    uiPrintf(19, " - High VMIN       : 750 mV");
    uiPrintf(20, " - UV Table        : 1683 MHz Tbreak");
    uiPrintf(21, " - Low UV          : 0");
    uiPrintf(22, " - High UV         : 0");

    uiPrintf(24, "@ HOC Toolkit");
    uiPrintf(26, " - CPU Boost       : Lowest selectable / 1785");

    uiPrintf(28, "Then:");
    uiPrintf(29, " - Reboot CFW and reopen Wizard");
    uiPrintf(31, "Keys:");
    uiPrintf(32, "A : Setup done / Start");
    uiPrintf(33, "B : Exit    - : Reset");
}

bool isVminSweepStage(Stage st);

void renderTestStage() {
    title();

    stress::Kind kind;
    int seconds = 0;
    const bool hasTest = testPlan(g.stage, kind, seconds);
    OverrideExpectation expected{};
    const bool hasOverrides = overridePlan(g.stage, expected);

    int row = 5;
    const bool recoveryPage = g.recoveryNeeded &&
        (g.stage == Stage::LowUvLong || g.stage == Stage::VddqLong ||
         g.stage == Stage::Vdd2Long || g.stage == Stage::HighUvLong);
    if (!recoveryPage) {
        uiPrintf(row++, "@ Horizon OC");
        row++;
    }

    switch (g.stage) {
        case Stage::LowUvQuick:
            uiPrintf(row++, "CPU Settings:");
            uiPrintf(row++, " - Low UV : %d", g.lowUvTest);
            uiPrintf(row++, "Action : Reboot CFW");
            break;
        case Stage::LowUvLong:
            if (g.recoveryNeeded) { printSafeRecovery("CPU Settings", "Low UV = " + std::to_string(g.lowUvGood)); row = 16; }
            else {
                uiPrintf(row++, "CPU Settings:");
                uiPrintf(row++, " - Low UV : %d", g.lowUvGood);
                uiPrintf(row++, "Action : Reboot CFW");
            }
            break;
        case Stage::LowVminQuick:
            uiPrintf(row++, "CPU Settings:");
            uiPrintf(row++, " - Low UV   : %d", g.lowUvGood);
            uiPrintf(row++, " - Low VMIN : %d mV", g.lowVminTest);
            uiPrintf(row++, "Action   : Reboot CFW");
            break;
        case Stage::LowVminLong:
        case Stage::LowVminSweep612:
        case Stage::LowVminSweep714:
        case Stage::LowVminValidate816:
        case Stage::LowVminSweep918:
        case Stage::LowVminValidate1020:
            uiPrintf(row++, "CPU Settings:");
            uiPrintf(row++, " - Low VMIN : %d mV", g.lowVminGood);
            break;
        case Stage::LowVminFinalLong:
            uiPrintf(row++, "CPU Settings:");
            uiPrintf(row++, " - Low VMIN : %d mV", g.lowVminGood);
            uiPrintf(row++, " - Floor CPU: %s", formatClock(g.vminFloorHz ? g.vminFloorHz : CLOCK_CPU_VMIN_510_HZ).c_str());
            break;
        case Stage::VddqQuick:
            uiPrintf(row++, "RAM Settings:");
            uiPrintf(row++, " - VDD2 : %s", formatVdd2(STOCK_VDD2_UV).c_str());
            uiPrintf(row++, " - VDDQ : %d mV", g.vddqTest);
            uiPrintf(row++, "Action: Reboot CFW");
            break;
        case Stage::VddqLong:
            if (g.recoveryNeeded) { printSafeRecovery("RAM Settings", "VDDQ = " + std::to_string(g.vddqGood) + " mV"); row = 16; }
            else {
                uiPrintf(row++, "RAM Settings:");
                uiPrintf(row++, " - VDDQ : %d mV", g.vddqGood);
                uiPrintf(row++, "Action: Reboot CFW");
            }
            break;
        case Stage::Vdd2Quick:
            uiPrintf(row++, "RAM Settings:");
            uiPrintf(row++, " - VDDQ : %d mV", g.vddqGood);
            uiPrintf(row++, " - VDD2 : %s", formatVdd2(g.vdd2TestUv).c_str());
            uiPrintf(row++, "Action: Reboot CFW");
            break;
        case Stage::Vdd2Long:
            if (g.recoveryNeeded) { printSafeRecovery("RAM Settings", "VDD2 = " + formatVdd2(g.vdd2GoodUv)); row = 16; }
            else {
                uiPrintf(row++, "RAM Settings:");
                uiPrintf(row++, " - VDDQ : %d mV", g.vddqGood);
                uiPrintf(row++, " - VDD2 : %s", formatVdd2(g.vdd2GoodUv).c_str());
                uiPrintf(row++, "Action: Reboot CFW");
            }
            break;
        case Stage::RamBoostValidate:
            uiPrintf(row++, "RAM Settings:");
            uiPrintf(row++, " - VDDQ : %d mV", g.vddqGood);
            uiPrintf(row++, " - VDD2 : %s", formatVdd2(g.vdd2GoodUv).c_str());
            if (g.ramPairRetryMode == 1) uiPrintf(row++, "Retry: VDDQ +10 mV");
            if (g.ramPairRetryMode == 2) uiPrintf(row++, "Retry: VDD2 +12.5 mV");
            break;
        case Stage::Ram1331Validate:
            uiPrintf(row++, "RAM Settings:");
            uiPrintf(row++, " - VDDQ : %d mV", g.vddqGood);
            uiPrintf(row++, " - VDD2 : %s", formatVdd2(g.vdd2GoodUv).c_str());
            break;
        case Stage::HighUvQuick:
            uiPrintf(row++, "CPU Settings:");
            uiPrintf(row++, " - High UV : %d", g.highUvTest);
            uiPrintf(row++, "Action  : Reboot CFW");
            break;
        case Stage::HighUvLong:
            if (g.recoveryNeeded) { printSafeRecovery("CPU Settings", "High UV = " + std::to_string(g.highUvGood)); row = 16; }
            else {
                uiPrintf(row++, "CPU Settings:");
                uiPrintf(row++, " - High UV : %d", g.highUvGood);
                uiPrintf(row++, "Action  : Reboot CFW");
            }
            break;
        case Stage::BoostCpuRamValidate:
            uiPrintf(row++, "CPU Settings:");
            uiPrintf(row++, " - Low UV   : %d", g.lowUvGood);
            uiPrintf(row++, " - High UV  : %d", g.highUvGood);
            uiPrintf(row++, " - Low VMIN : %d mV", g.lowVminGood);
            break;
        case Stage::NormalMatrixValidate:
        case Stage::NormalMemValidate:
        case Stage::NormalGpuValidate:
        case Stage::BoostMatrixValidate:
        case Stage::BoostMemValidate:
        case Stage::BoostCpuMemValidate:
            uiPrintf(row++, "HOC Settings:");
            uiPrintf(row++, "Use final validated values");
            break;
        default:
            break;
    }

    row++;
    if (hasOverrides) {
        printOverrides(row, expected);
        row += 5;
    }

    if (isVminSweepStage(g.stage)) {
        uiPrintf(row++, "Next:");
        uiPrintf(row++, "A : Continue");
        uiPrintf(row++, "    (CPU voltage checked automatically)");
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
    } else {
        const char* ok = "OK";
        const char* bad = "WRONG";
        uiPrintf(5, "Overrides - Expected / Current");
        uiPrintf(7, "CPU : %s / %s  %s",
                 formatClock(g_overrideCheck.expected.cpuHz).c_str(),
                 formatClock(g_overrideCheck.current.overrideHz[0]).c_str(),
                 g_overrideCheck.cpuOk ? ok : bad);
        uiPrintf(8, "GPU : %s / %s  %s",
                 formatClock(g_overrideCheck.expected.gpuHz).c_str(),
                 formatClock(g_overrideCheck.current.overrideHz[1]).c_str(),
                 g_overrideCheck.gpuOk ? ok : bad);
        uiPrintf(9, "RAM : %s / %s  %s",
                 formatClock(g_overrideCheck.expected.ramHz).c_str(),
                 formatClock(g_overrideCheck.current.overrideHz[2]).c_str(),
                 g_overrideCheck.ramOk ? ok : bad);
        if (g_overrideAction == PendingOverrideAction::VminProbe) {
            uiPrintf(10, "Applied CPU : %s  %s",
                     formatClock(g_overrideCheck.current.targetHz[0]).c_str(),
                     g_overrideCheck.cpuAppliedOk ? ok : bad);
        }
        uiPrintf(12, "Correct every WRONG value in Horizon OC");
    }

    uiPrintf(15, "A : Check again / Continue");
    uiPrintf(16, "B : Back");
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
    if (g_interruptedPrompt) { renderInterruptedPrompt(); return; }
    if (g_overridePrompt) { renderOverridePrompt(); return; }
    if (g_resultScreen) { renderResultScreen(); return; }
    if (g_resetConfirm) {
        std::printf("\x1b[1;1H\x1b[31mReset ALL wizard progress?\x1b[0m\n\n");
        std::printf("[A] Yes, reset   [B] Cancel\n");
        consoleUpdate(nullptr);
        return;
    }

    if (g.stage == Stage::Preparation) renderPreparation();
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
    g_lastVminAtFloor = false;
    if (!isVminSweepStage(st) || !g_overrideCheck.readOk) return;
    const u32 hz = vminSweepClock(st);
    const u32 uv = g_overrideCheck.current.cpuVoltageUv;
    if (!hz || !uv) return;
    const u32 floorUv = (u32)g.lowVminGood * 1000U;
    const u32 delta = uv > floorUv ? uv - floorUv : floorUv - uv;
    g_lastVminAtFloor = delta <= VMIN_FLOOR_TOLERANCE_UV;
    if (g_lastVminAtFloor) {
        g.vminFloorHz = hz;
        g.vminFloorObservedMv = (int)((uv + 500U) / 1000U);
        saveState();
    }
}

void restartVminSweep(bool recovery) {
    g.stage = Stage::LowVminLong;
    g.recoveryNeeded = recovery;
    g.vminFloorHz = 0;
    g.vminFloorObservedMv = 0;
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
            if (!g_lastVminAtFloor) { g.vminFloorHz = CLOCK_CPU_VMIN_510_HZ; g.vminFloorObservedMv = g.lowVminGood; g.stage = Stage::LowVminFinalLong; }
            else g.stage = Stage::LowVminSweep612;
            break;
        case Stage::LowVminSweep612:
            if (!g_lastVminAtFloor) g.stage = Stage::LowVminFinalLong;
            else g.stage = Stage::LowVminSweep714;
            break;
        case Stage::LowVminSweep714:
            if (!g_lastVminAtFloor) g.stage = Stage::LowVminFinalLong;
            else g.stage = Stage::LowVminValidate816;
            break;
        case Stage::LowVminValidate816:
            if (!g_lastVminAtFloor) g.stage = Stage::LowVminFinalLong;
            else g.stage = Stage::LowVminSweep918;
            break;
        case Stage::LowVminSweep918:
            if (!g_lastVminAtFloor) g.stage = Stage::LowVminFinalLong;
            else g.stage = Stage::LowVminValidate1020;
            break;
        case Stage::LowVminValidate1020:
            g.stage = Stage::LowVminFinalLong; break;
        case Stage::LowVminFinalLong:
            g.recoveryNeeded = false; g.stage = Stage::VddqQuick;
            g.vddqTest = STOCK_VDDQ_MV - VDDQ_STEP_MV; break;
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
    saveState();
}

void handleFail(bool didNotBoot) {
    switch (g.stage) {
        case Stage::LowUvQuick: enterLowUvLong(didNotBoot); return;
        case Stage::LowUvLong: if (g.lowUvGood > 0) --g.lowUvGood; g.recoveryNeeded = false; break;
        case Stage::LowVminQuick: enterLowVminLong(didNotBoot); return;
        case Stage::LowVminLong:
        case Stage::LowVminSweep612:
        case Stage::LowVminSweep714:
        case Stage::LowVminValidate816:
        case Stage::LowVminSweep918:
        case Stage::LowVminValidate1020:
        case Stage::LowVminFinalLong:
            if (g.lowVminGood < STOCK_LOW_VMIN_MV) g.lowVminGood += LOW_VMIN_STEP_MV;
            g.recoveryNeeded = false;
            restartVminSweep(false);
            return;
        case Stage::VddqQuick: enterVddqLong(didNotBoot); return;
        case Stage::VddqLong: g.vddqGood += VDDQ_STEP_MV; g.recoveryNeeded = false; break;
        case Stage::Vdd2Quick: enterVdd2Long(didNotBoot); return;
        case Stage::Vdd2Long: g.vdd2GoodUv += VDD2_STEP_UV; g.recoveryNeeded = false; break;
        case Stage::RamBoostValidate:
            if (g.ramPairRetryMode == 0) {
                g.vddqGood += VDDQ_STEP_MV;
                g.ramPairRetryMode = 1;
            } else if (g.ramPairRetryMode == 1) {
                g.vddqGood -= VDDQ_STEP_MV;
                g.vdd2GoodUv += VDD2_STEP_UV;
                g.ramPairRetryMode = 2;
            } else {
                g.vdd2GoodUv += VDD2_STEP_UV;
            }
            break;
        case Stage::Ram1331Validate: g.vddqGood += VDDQ_STEP_MV; break;
        case Stage::HighUvQuick: enterHighUvLong(didNotBoot); return;
        case Stage::HighUvLong: if (g.highUvGood > 0) --g.highUvGood; g.recoveryNeeded = false; break;
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
                saveState();
                handleFail(false);
                g_interruptedPrompt = false;
                redraw = true;
            } else if (k & HidNpadButton_X) {
                g.testRunning = false;
                if (g.testStage >= 0 && g.testStage <= static_cast<int>(Stage::RamBoostValidate))
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
        } else if (k & HidNpadButton_Y && isQuickStage(g.stage)) {
            handleFail(true);
            redraw = true;
        } else if (k & HidNpadButton_Plus) {
            if (isVminSweepStage(g.stage)) {
                runVminProbe();
                redraw = true;
            } else {
                stress::Kind skipKind;
                int skipSeconds = 0;
                if (testPlan(g.stage, skipKind, skipSeconds)) {
                    g_manualPass = true;
                    handlePass();
                    g_manualPass = false;
                    redraw = true;
                }
            }
        } else if (k & HidNpadButton_X) {
            if (!isVminSweepStage(g.stage) && g.stage != Stage::Preparation && g.stage != Stage::Complete) {
                handleFail(false);
                redraw = true;
            }
        } else if (k & HidNpadButton_A) {
            if (isVminSweepStage(g.stage)) {
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
