#include <switch.h>

#include "stress_tests.hpp"
#include "hoc_monitor.h"

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
};

bool g_overridePrompt = false;
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
        case Stage::LowVminQuick:
            std::printf("Keep CPU Low UV = %d.\n", g.lowUvGood);
            std::printf("Set CPU Low VMIN = \x1b[1m%d mV\x1b[0m, Save KIP and reboot.\n", g.lowVminTest);
            std::printf("Quick-search Overrides: CPU 510 / GPU 384 / RAM 1331\n");
            break;
        case Stage::LowVminLong:
            if (g.recoveryNeeded) printSafeRecovery("CPU Low VMIN = " + std::to_string(g.lowVminGood) + " mV");
            else std::printf("Use candidate Low VMIN = \x1b[1m%d mV\x1b[0m.\n", g.lowVminGood);
            std::printf("Dynamic floor sweep: 510 MHz. CPU voltage is read from HOC.\n");
            std::printf("Overrides: CPU 510 / GPU 384 / RAM 1331\n");
            break;
        case Stage::LowVminSweep612:
            std::printf("Dynamic floor sweep: 612 MHz.\nOverrides: CPU 612 / GPU 384 / RAM 1331\n");
            break;
        case Stage::LowVminSweep714:
            std::printf("Dynamic floor sweep: 714 MHz.\nOverrides: CPU 714 / GPU 384 / RAM 1331\n");
            break;
        case Stage::LowVminValidate816:
            std::printf("Dynamic floor sweep: 816 MHz.\nOverrides: CPU 816 / GPU 384 / RAM 1331\n");
            break;
        case Stage::LowVminSweep918:
            std::printf("Dynamic floor sweep: 918 MHz.\nOverrides: CPU 918 / GPU 384 / RAM 1331\n");
            break;
        case Stage::LowVminValidate1020:
            std::printf("Dynamic floor sweep: 1020 MHz.\nOverrides: CPU 1020 / GPU 384 / RAM 1331\n");
            break;
        case Stage::LowVminFinalLong:
            std::printf("Detected highest CPU clock still on the VMIN floor:\n");
            std::printf("  %u MHz at about %d mV\n", (g.vminFloorHz ? g.vminFloorHz : CLOCK_CPU_VMIN_510_HZ) / 1000000U,
                        g.vminFloorObservedMv ? g.vminFloorObservedMv : g.lowVminGood);
            std::printf("Run the 1-hour confirmation at that clock.\n");
            std::printf("GPU 384 / RAM 1331 remain fixed.\n");
            std::printf("After PASS also check Home, Sleep/Wake, game launch/close.\n");
            break;
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
        case Stage::LowVminLong:
        case Stage::LowVminSweep612:
        case Stage::LowVminSweep714:
        case Stage::LowVminValidate816:
        case Stage::LowVminSweep918:
        case Stage::LowVminValidate1020:
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
    f << "CPU UV Table: user-selected (recommended: 1683 MHz Tbreak)\n";
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

void title() {
    std::printf("\x1b[1;1H\x1b[36mHOC Undervolting Wizard\x1b[0m   Mariko / OLED\n");
    std::printf("%s\n", stageName(g.stage));
    std::printf("------------------------------------------------------------\n\n");
}

void printSafeRecovery(const std::string& restoreText) {
    std::printf("\x1b[33mPrevious setting did not boot.\x1b[0m\n\n");
    std::printf("1. Boot Hekate.\n");
    std::printf("2. Start CFW WITHOUT Horizon OC / hoc.kip.\n");
    std::printf("3. Open Horizon OC.\n");
    std::printf("4. Restore: %s\n", restoreText.c_str());
    std::printf("5. Save KIP and reboot normally.\n\n");
}

void footerTest() {
    std::printf("\n\x1b[32m[A] START BUILT-IN TEST\x1b[0m   \x1b[36m[+] KNOWN PASS / SKIP\x1b[0m\n");
    std::printf("\x1b[31m[X] KNOWN FAIL / SKIP\x1b[0m\n");
    if (isQuickStage(g.stage)) std::printf("\x1b[33m[Y] DID NOT BOOT\x1b[0m\n");
    std::printf("[B] Exit   [-] Reset wizard\n");
}

void renderPreparation() {
    title();
    std::printf("Before tuning, prepare the Battery profile once.\n\n");
    std::printf("Horizon OC - Safety / RAM:\n");
    std::printf("  Uncapped Clocks : OFF\n");
    std::printf("  HP Mode          : OFF\n");
    std::printf("  RAM Max Clock    : 1600 MHz\n");
    std::printf("  VDD2             : 1175 mV or known-stable lower value\n");
    std::printf("  VDDQ             : 600 mV or known-stable lower value\n\n");
    std::printf("Horizon OC - CPU:\n");
    std::printf("  CPU Max Clock    : LOWEST SELECTABLE (currently 1963 MHz)\n");
    std::printf("  CPU UV Table     : 1683 MHz Tbreak or known-working table\n");
    std::printf("  Low UV / High UV : 0 / 0, or known-stable values\n");
    std::printf("  Low VMIN         : 620 mV or known-stable value\n");
    std::printf("  High VMIN        : 750 mV\n\n");
    std::printf("HOC Toolkit:\n");
    std::printf("  CPU Boost Clock  : LOWEST SELECTABLE (stock target 1785 MHz)\n\n");
    std::printf("Save/apply Toolkit values, Save KIP, then REBOOT CFW.\n");
    std::printf("After reboot reopen this Wizard and press [A].\n\n");
    std::printf("Already know a value? During any built-in test use [+] to\n");
    std::printf("record a KNOWN PASS without running it, or [X] for KNOWN FAIL.\n\n");
    std::printf("[A] Setup done - start tuning   [B] Exit   [-] Reset\n");
}

void renderTestStage() {
    title();
    stress::Kind kind;
    int seconds = 0;
    testPlan(g.stage, kind, seconds);

    switch (g.stage) {
        case Stage::LowUvQuick:
            std::printf("In Horizon OC set CPU Low UV = \x1b[1m%d\x1b[0m\n", g.lowUvTest);
            std::printf("Save KIP and reboot. Then set Overrides:\n");
            std::printf("  CPU 1020 / GPU 384 / RAM 1331\n");
            break;
        case Stage::LowUvLong:
            if (g.recoveryNeeded) printSafeRecovery("CPU Low UV = " + std::to_string(g.lowUvGood));
            else std::printf("Restore CPU Low UV = \x1b[1m%d\x1b[0m, Save KIP and reboot.\n", g.lowUvGood);
            std::printf("Overrides: CPU 1020 / GPU 384 / RAM 1331\n");
            break;
        case Stage::LowVminQuick:
            std::printf("Keep CPU Low UV = %d.\n", g.lowUvGood);
            std::printf("Set CPU Low VMIN = \x1b[1m%d mV\x1b[0m, Save KIP and reboot.\n", g.lowVminTest);
            if (g.lowVminTest < 590) std::printf("\x1b[33mAdvanced low-VMIN range. Wizard floor: 570 mV.\x1b[0m\n");
            std::printf("Quick-search Overrides: CPU 612 / GPU 384 / RAM 1331\n");
            break;
        case Stage::LowVminLong:
            if (g.recoveryNeeded) printSafeRecovery("CPU Low VMIN = " + std::to_string(g.lowVminGood) + " mV");
            else std::printf("Use CPU Low VMIN = \x1b[1m%d mV\x1b[0m, Save KIP and reboot.\n", g.lowVminGood);
            std::printf("Final VMIN validation 1/3.\n");
            std::printf("Overrides: CPU 612 / GPU 384 / RAM 1331\n");
            break;
        case Stage::LowVminValidate816:
            std::printf("Keep CPU Low VMIN = \x1b[1m%d mV\x1b[0m.\n", g.lowVminGood);
            std::printf("Final VMIN validation 2/3. No KIP change required.\n");
            std::printf("Overrides: CPU 816 / GPU 384 / RAM 1331\n");
            break;
        case Stage::LowVminValidate1020:
            std::printf("Keep CPU Low VMIN = \x1b[1m%d mV\x1b[0m.\n", g.lowVminGood);
            std::printf("Final VMIN validation 3/3. No KIP change required.\n");
            std::printf("Overrides: CPU 1020 / GPU 384 / RAM 1331\n");
            std::printf("After PASS also check normal Sleep/Wake transitions.\n");
            break;
        case Stage::VddqQuick:
            std::printf("Keep VDD2 at stock %s.\n", formatVdd2(STOCK_VDD2_UV).c_str());
            std::printf("Set RAM VDDQ = \x1b[1m%d mV\x1b[0m, Save KIP and reboot.\n", g.vddqTest);
            std::printf("Overrides: CPU 1785 / GPU 76.8 / RAM 1600\n");
            break;
        case Stage::VddqLong:
            if (g.recoveryNeeded) printSafeRecovery("RAM VDDQ = " + std::to_string(g.vddqGood) + " mV");
            else std::printf("Restore RAM VDDQ = \x1b[1m%d mV\x1b[0m, Save KIP and reboot.\n", g.vddqGood);
            std::printf("Overrides: CPU 1785 / GPU 76.8 / RAM 1600\n");
            break;
        case Stage::Vdd2Quick:
            std::printf("Keep final VDDQ = %d mV.\n", g.vddqGood);
            std::printf("Set RAM VDD2 = \x1b[1m%s\x1b[0m, Save KIP and reboot.\n", formatVdd2(g.vdd2TestUv).c_str());
            std::printf("Overrides: CPU 1785 / GPU 76.8 / RAM 1600\n");
            break;
        case Stage::Vdd2Long:
            if (g.recoveryNeeded) printSafeRecovery("RAM VDD2 = " + formatVdd2(g.vdd2GoodUv));
            else std::printf("Restore RAM VDD2 = \x1b[1m%s\x1b[0m, Save KIP and reboot.\n", formatVdd2(g.vdd2GoodUv).c_str());
            std::printf("Keep VDDQ = %d mV.\n", g.vddqGood);
            std::printf("Overrides: CPU 1785 / GPU 76.8 / RAM 1600\n");
            break;
        case Stage::RamBoostValidate:
            std::printf("Confirm final VDDQ + VDD2 together at Nintendo Boost clocks.\n");
            std::printf("VDDQ %d mV / VDD2 %s\n", g.vddqGood, formatVdd2(g.vdd2GoodUv).c_str());
            if (g.ramPairRetryMode == 1) std::printf("Retry mode: VDDQ raised by one 10 mV step.\n");
            if (g.ramPairRetryMode == 2) std::printf("Retry mode: VDDQ restored; VDD2 raised by 12.5 mV.\n");
            std::printf("Overrides: CPU 1785 / GPU 76.8 / RAM 1600\n");
            break;
        case Stage::Ram1331Validate:
            std::printf("Final RAM rails: VDDQ %d mV / VDD2 %s\n", g.vddqGood, formatVdd2(g.vdd2GoodUv).c_str());
            std::printf("Overrides: CPU 1020 / GPU 384 / RAM 1331\n");
            break;
        case Stage::HighUvQuick:
            std::printf("Keep final Low UV/VMIN/RAM values.\n");
            std::printf("Set CPU High UV = \x1b[1m%d\x1b[0m, Save KIP and reboot.\n", g.highUvTest);
            std::printf("Overrides: CPU 1785 / GPU 76.8 / RAM 1600\n");
            break;
        case Stage::HighUvLong:
            if (g.recoveryNeeded) printSafeRecovery("CPU High UV = " + std::to_string(g.highUvGood));
            else std::printf("Restore CPU High UV = \x1b[1m%d\x1b[0m, Save KIP and reboot.\n", g.highUvGood);
            std::printf("Overrides: CPU 1785 / GPU 76.8 / RAM 1600\n");
            break;
        case Stage::BoostCpuRamValidate:
            std::printf("Combined CPU + RAM validation.\n");
            std::printf("Overrides: CPU 1785 / GPU 76.8 / RAM 1600\n");
            break;
        case Stage::NormalMatrixValidate:
            std::printf("Final normal CPU validation.\nOverrides: CPU 1020 / GPU 384 / RAM 1331\n"); break;
        case Stage::NormalMemValidate:
            std::printf("Final normal RAM validation.\nOverrides: CPU 1020 / GPU 384 / RAM 1331\n"); break;
        case Stage::NormalGpuValidate:
            std::printf("Final normal GPU compute/memory validation.\nOverrides: CPU 1020 / GPU 384 / RAM 1331\n"); break;
        case Stage::BoostMatrixValidate:
            std::printf("Final Boost CPU validation.\nOverrides: CPU 1785 / GPU 76.8 / RAM 1600\n"); break;
        case Stage::BoostMemValidate:
            std::printf("Final Boost RAM validation.\nOverrides: CPU 1785 / GPU 76.8 / RAM 1600\n"); break;
        case Stage::BoostCpuMemValidate:
            std::printf("Final Boost combined validation.\nOverrides: CPU 1785 / GPU 76.8 / RAM 1600\n"); break;
        default:
            break;
    }

    std::printf("\nBuilt-in test: \x1b[1m%s\x1b[0m\n", stress::kindName(kind));
    std::printf("Duration: \x1b[1m%s\x1b[0m\n", seconds == 60 ? "1 minute" : "1 hour");
    std::printf("Errors/mismatches are detected automatically.\n");
    std::printf("CPU + GPU + RAM Overrides are verified before EVERY test.\n");
    if (kind == stress::Kind::Ram || kind == stress::Kind::Combined)
        std::printf("Do not install/update/copy files while testing unstable RAM.\n");
    footerTest();
}

void renderRealWorld() {
    title();
    std::printf("Remove manual Overrides and use the console normally.\n\n");
    std::printf("Play Tears of the Kingdom for at least 1 HOUR.\n");
    std::printf("Include fast travel, battles, loading, Home and Sleep/Wake.\n");
    std::printf("No crash, freeze or reboot is allowed.\n\n");
    std::printf("\x1b[32m[A] PASS\x1b[0m   \x1b[31m[X] FAIL\x1b[0m   [B] Exit\n");
}

void renderComplete() {
    title();
    std::printf("\x1b[32mUNDERVOLTING COMPLETE\x1b[0m\n\n");
    std::printf("Final values:\n");
    std::printf("  CPU Low UV   : %d\n", g.lowUvGood);
    std::printf("  CPU Low VMIN : %d mV\n", g.lowVminGood);
    std::printf("  RAM VDDQ     : %d mV\n", g.vddqGood);
    std::printf("  RAM VDD2     : %s\n", formatVdd2(g.vdd2GoodUv).c_str());
    std::printf("  CPU High UV  : %d\n\n", g.highUvGood);
    std::printf("Results: /switch/HOC-Undervolting-Wizard/results.txt\n\n");
    std::printf("These values can now be saved to the Battery profile in Performance Modes.\n\n");
    std::printf("[B] Exit   [-] Reset wizard\n");
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
    std::printf("\x1b[1;1H\x1b[31mHOC Undervolting Wizard - TEST BLOCKED\x1b[0m\n");
    std::printf("------------------------------------------------------------\n\n");

    if (!g_overrideCheck.readOk) {
        std::printf("Could not read Horizon OC service 'hoc:clk'.\n");
        std::printf("Result: 0x%08X\n\n", g_overrideCheck.rc);
        std::printf("Boot normal CFW with Horizon OC / hoc.kip loaded, then retry.\n");
    } else {
        const char* ok = "\x1b[32mOK\x1b[0m";
        const char* bad = "\x1b[31mWRONG\x1b[0m";
        std::printf("All three Temporary Overrides must match the test target.\n\n");
        std::printf("       Expected       Current        Status\n");
        std::printf("CPU    %-13s  %-13s  %s\n",
                    formatClock(g_overrideCheck.expected.cpuHz).c_str(),
                    formatClock(g_overrideCheck.current.overrideHz[0]).c_str(),
                    g_overrideCheck.cpuOk ? ok : bad);
        std::printf("GPU    %-13s  %-13s  %s\n",
                    formatClock(g_overrideCheck.expected.gpuHz).c_str(),
                    formatClock(g_overrideCheck.current.overrideHz[1]).c_str(),
                    g_overrideCheck.gpuOk ? ok : bad);
        std::printf("RAM    %-13s  %-13s  %s\n\n",
                    formatClock(g_overrideCheck.expected.ramHz).c_str(),
                    formatClock(g_overrideCheck.current.overrideHz[2]).c_str(),
                    g_overrideCheck.ramOk ? ok : bad);
        std::printf("Open Horizon OC -> Temporary Overrides and correct ALL red values.\n");
    }

    std::printf("\nThe stability test has NOT started and no result was recorded.\n\n");
    std::printf("[A] Check again + start when correct   [B] Back\n");
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
            if (!g_manualPass && !g_lastVminAtFloor) { g.vminFloorHz = CLOCK_CPU_VMIN_510_HZ; g.vminFloorObservedMv = g.lowVminGood; g.stage = Stage::LowVminFinalLong; }
            else g.stage = Stage::LowVminSweep612;
            break;
        case Stage::LowVminSweep612:
            if (!g_manualPass && !g_lastVminAtFloor) g.stage = Stage::LowVminFinalLong;
            else g.stage = Stage::LowVminSweep714;
            break;
        case Stage::LowVminSweep714:
            if (!g_manualPass && !g_lastVminAtFloor) g.stage = Stage::LowVminFinalLong;
            else g.stage = Stage::LowVminValidate816;
            break;
        case Stage::LowVminValidate816:
            if (!g_manualPass && !g_lastVminAtFloor) g.stage = Stage::LowVminFinalLong;
            else g.stage = Stage::LowVminSweep918;
            break;
        case Stage::LowVminSweep918:
            if (!g_manualPass && !g_lastVminAtFloor) g.stage = Stage::LowVminFinalLong;
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

void runCurrentTest() {
    stress::Kind kind;
    int seconds = 0;
    if (!testPlan(g.stage, kind, seconds)) return;

    // Hard pre-flight: every built-in test requires all three expected
    // Horizon OC Temporary Overrides. A missing/wrong override blocks the test.
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

int main() {
    consoleInit(nullptr);
    padConfigureInput(1, HidNpadStyleSet_NpadStandard);
    PadState pad;
    padInitializeDefault(&pad);

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
            stress::Kind skipKind;
            int skipSeconds = 0;
            if (testPlan(g.stage, skipKind, skipSeconds)) {
                g_manualPass = true;
                g_lastVminAtFloor = true;
                handlePass();
                g_manualPass = false;
                redraw = true;
            }
        } else if (k & HidNpadButton_X) {
            if (g.stage != Stage::Preparation && g.stage != Stage::Complete) {
                handleFail(false);
                redraw = true;
            }
        } else if (k & HidNpadButton_A) {
            stress::Kind kind;
            int seconds = 0;
            if (testPlan(g.stage, kind, seconds)) {
                runCurrentTest();
            } else {
                handlePass();
            }
            redraw = true;
        }

        svcSleepThread(20'000'000);
    }

    consoleExit(nullptr);
    return 0;
}
