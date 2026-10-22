#include <switch.h>

#include "stress_tests.hpp"

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

constexpr int LOW_UV_MAX = 8;
constexpr int HIGH_UV_MAX = 13;
constexpr int LOW_VMIN_MIN_MV = 550;
constexpr int VDDQ_MIN_MV = 400;
constexpr int VDD2_MIN_UV = 912500;
constexpr int LOW_VMIN_STEP_MV = 5;
constexpr int VDDQ_STEP_MV = 5;
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
    Complete
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
        case Stage::LowVminQuick: return "CPU Low VMIN - Quick Search";
        case Stage::LowVminLong: return "CPU Low VMIN - 1 Hour Validation";
        case Stage::VddqQuick: return "VDDQ - Quick Search";
        case Stage::VddqLong: return "VDDQ - 1 Hour Validation";
        case Stage::Vdd2Quick: return "VDD2 - Quick Search";
        case Stage::Vdd2Long: return "VDD2 - 1 Hour Validation";
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
        case Stage::LowVminLong:
        case Stage::HighUvLong:
        case Stage::NormalMatrixValidate:
        case Stage::BoostMatrixValidate:
            kind = stress::Kind::Cpu; seconds = 3600; return true;
        case Stage::VddqQuick:
        case Stage::Vdd2Quick:
            kind = stress::Kind::Ram; seconds = 60; return true;
        case Stage::VddqLong:
        case Stage::Vdd2Long:
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
    f << "CPU UV Table: Default / Normal (not Extreme)\n";
    f << "CPU Low UV: " << g.lowUvGood << "\n";
    f << "CPU Low VMIN: " << g.lowVminGood << " mV\n";
    f << "RAM VDDQ: " << g.vddqGood << " mV\n";
    f << "RAM VDD2: " << formatVdd2(g.vdd2GoodUv) << "\n";
    f << "CPU High UV: " << g.highUvGood << "\n\n";
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
    std::printf("\n\x1b[32m[A] START BUILT-IN TEST\x1b[0m   \x1b[31m[X] Manual FAIL\x1b[0m\n");
    if (isQuickStage(g.stage)) std::printf("\x1b[33m[Y] DID NOT BOOT\x1b[0m\n");
    std::printf("[B] Exit   [-] Reset wizard\n");
}

void renderPreparation() {
    title();
    std::printf("This app does NOT write Horizon OC settings.\n");
    std::printf("You still set each HOC value manually and Save KIP.\n");
    std::printf("v0.3 runs CPU, RAM, combined and GPU tests internally.\n\n");
    std::printf("Start from:\n");
    std::printf("  CPU UV Table  : Default / Normal (NOT Extreme)\n");
    std::printf("  CPU Low UV    : 0\n");
    std::printf("  CPU High UV   : 0\n");
    std::printf("  CPU Low VMIN  : %d mV\n", STOCK_LOW_VMIN_MV);
    std::printf("  CPU High VMIN : %d mV\n", STOCK_HIGH_VMIN_MV);
    std::printf("  RAM VDDQ      : %d mV\n", STOCK_VDDQ_MV);
    std::printf("  RAM VDD2      : %s\n\n", formatVdd2(STOCK_VDD2_UV).c_str());
    std::printf("Set these values, Save KIP and reboot once.\n");
    std::printf("Then reopen the wizard and press [A].\n\n");
    std::printf("[A] Start tuning   [B] Exit   [-] Reset\n");
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
            if (g.lowVminTest < 590) std::printf("\x1b[33mNote: HOC recommends >=590 mV.\x1b[0m\n");
            std::printf("Overrides: CPU 1020 / GPU 384 / RAM 1331\n");
            break;
        case Stage::LowVminLong:
            if (g.recoveryNeeded) printSafeRecovery("CPU Low VMIN = " + std::to_string(g.lowVminGood) + " mV");
            else std::printf("Restore CPU Low VMIN = \x1b[1m%d mV\x1b[0m, Save KIP and reboot.\n", g.lowVminGood);
            std::printf("Overrides: CPU 510 / GPU 384 / RAM 1331\n");
            std::printf("After validation also check normal Sleep/Wake transitions.\n");
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

void enterLowUvLong(bool recovery) { g.stage = Stage::LowUvLong; g.recoveryNeeded = recovery; saveState(); }
void enterLowVminLong(bool recovery) { g.stage = Stage::LowVminLong; g.recoveryNeeded = recovery; saveState(); }
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
        case Stage::Vdd2Long: g.recoveryNeeded = false; g.stage = Stage::Ram1331Validate; break;
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
        case Stage::LowVminLong: g.lowVminGood += LOW_VMIN_STEP_MV; g.recoveryNeeded = false; break;
        case Stage::VddqQuick: enterVddqLong(didNotBoot); return;
        case Stage::VddqLong: g.vddqGood += VDDQ_STEP_MV; g.recoveryNeeded = false; break;
        case Stage::Vdd2Quick: enterVdd2Long(didNotBoot); return;
        case Stage::Vdd2Long: g.vdd2GoodUv += VDD2_STEP_UV; g.recoveryNeeded = false; break;
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

    const Stage testedStage = g.stage;
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
                if (g.testStage >= 0 && g.testStage <= static_cast<int>(Stage::Complete))
                    g.stage = static_cast<Stage>(g.testStage);
                g.testKind = g.testDurationSec = g.testStage = 0;
                saveState();
                handleFail(false);
                g_interruptedPrompt = false;
                redraw = true;
            } else if (k & HidNpadButton_X) {
                g.testRunning = false;
                if (g.testStage >= 0 && g.testStage <= static_cast<int>(Stage::Complete))
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
