#include <switch.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <string>
#include <sys/stat.h>
#include <unistd.h>

namespace {

constexpr const char* APP_DIR   = "sdmc:/switch/HOC-Battery-Wizard";
constexpr const char* STATE     = "sdmc:/switch/HOC-Battery-Wizard/state.ini";
constexpr const char* STATE_TMP = "sdmc:/switch/HOC-Battery-Wizard/state.tmp";
constexpr const char* RESULTS   = "sdmc:/switch/HOC-Battery-Wizard/results.txt";

// Mariko / OLED stock HOC starting values used by this wizard.
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
constexpr int VDD2_STEP_UV = 12500; // 12.5 mV

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
};

WizardState g;
bool g_resetConfirm = false;

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

void ensureDir() {
    mkdir("sdmc:/switch", 0777);
    mkdir(APP_DIR, 0777);
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
    f.flush();
    f.close();
    if (access(STATE, F_OK) == 0) remove(STATE);
    return rename(STATE_TMP, STATE) == 0;
}

void assignKV(const std::string& key, const std::string& value) {
    int v = std::atoi(value.c_str());
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
}

bool loadState() {
    std::ifstream f(STATE);
    if (!f) return false;
    std::string line;
    while (std::getline(f, line)) {
        auto p = line.find('=');
        if (p == std::string::npos) continue;
        assignKV(line.substr(0, p), line.substr(p + 1));
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
    f << "HOC Battery Wizard - Final Results\n\n";
    f << "CPU UV Table: Default / Normal (not Extreme)\n";
    f << "CPU Low UV: " << g.lowUvGood << "\n";
    f << "CPU Low VMIN: " << g.lowVminGood << " mV\n";
    f << "RAM VDDQ: " << g.vddqGood << " mV\n";
    f << "RAM VDD2: " << formatVdd2(g.vdd2GoodUv) << "\n";
    f << "CPU High UV: " << g.highUvGood << "\n\n";
    f << "Normal handheld validated at 1020 / 384 / 1331.\n";
    f << "Nintendo Boost validated at 1785 / 76.8 / 1600.\n";
}

void title() {
    printf("\x1b[1;1H\x1b[36mHOC Battery Wizard\x1b[0m   Mariko / OLED\n");
    printf("%s\n", stageName(g.stage));
    printf("------------------------------------------------------------\n\n");
}

void footerTrial() {
    printf("\n\x1b[32m[A] PASS\x1b[0m   \x1b[31m[X] FAIL\x1b[0m   \x1b[33m[Y] DID NOT BOOT\x1b[0m\n");
    printf("[B] Exit   [-] Reset wizard\n");
}

void footerValidation() {
    printf("\n\x1b[32m[A] PASS\x1b[0m   \x1b[31m[X] FAIL\x1b[0m\n");
    printf("[B] Exit   [-] Reset wizard\n");
}

void printSafeRecovery(const std::string& restoreText) {
    printf("\x1b[33mPrevious setting did not boot.\x1b[0m\n\n");
    printf("1. Boot Hekate.\n");
    printf("2. Start CFW WITHOUT Horizon OC / hoc.kip.\n");
    printf("3. Open Horizon OC.\n");
    printf("4. Restore: %s\n", restoreText.c_str());
    printf("5. Save KIP and reboot normally.\n\n");
}

void renderPreparation() {
    title();
    printf("This app DOES NOT change Horizon OC settings.\n");
    printf("You set every value manually in Horizon OC.\n");
    printf("The wizard only remembers progress and tells you what to do.\n\n");
    printf("Start from these stock HOC values:\n\n");
    printf("  CPU UV Table : Default / Normal (NOT Extreme)\n");
    printf("  CPU Low UV   : 0\n");
    printf("  CPU High UV  : 0\n");
    printf("  CPU Low VMIN : %d mV\n", STOCK_LOW_VMIN_MV);
    printf("  CPU High VMIN: %d mV\n", STOCK_HIGH_VMIN_MV);
    printf("  RAM VDDQ     : %d mV\n", STOCK_VDDQ_MV);
    printf("  RAM VDD2     : %s\n", formatVdd2(STOCK_VDD2_UV).c_str());
    printf("\nNo stock stress test is needed. Stock is the baseline.\n");
    printf("Set these values, Save KIP and reboot once.\n");
    printf("Then reopen this wizard and press [A].\n\n");
    printf("[A] Start tuning   [B] Exit   [-] Reset\n");
}

void renderLowUvQuick() {
    title();
    printf("In Horizon OC set:\n");
    printf("  CPU Low UV = \x1b[1m%d\x1b[0m\n", g.lowUvTest);
    printf("Do not change anything else. Save KIP and reboot.\n\n");
    printf("If it boots, open Horizon OC and set Overrides:\n");
    printf("  CPU 1020 MHz / GPU 384 MHz / RAM 1331 MHz\n\n");
    printf("Run: StressNX -> Matrixprod -> \x1b[1m1 minute\x1b[0m\n");
    printf("Return here and report the result.\n");
    footerTrial();
}

void renderLowUvLong() {
    title();
    if (g.recoveryNeeded) printSafeRecovery("CPU Low UV = " + std::to_string(g.lowUvGood));
    else {
        printf("Restore in Horizon OC:\n  CPU Low UV = \x1b[1m%d\x1b[0m\n", g.lowUvGood);
        printf("Save KIP and reboot.\n\n");
    }
    printf("Set Overrides:\n  CPU 1020 / GPU 384 / RAM 1331\n\n");
    printf("Run: StressNX -> Matrixprod -> \x1b[1m1 HOUR\x1b[0m\n");
    printf("If it fails, the wizard will move one UV level safer.\n");
    footerValidation();
}

void renderLowVminQuick() {
    title();
    printf("Keep CPU Low UV = %d.\n", g.lowUvGood);
    printf("In Horizon OC set:\n  CPU Low VMIN = \x1b[1m%d mV\x1b[0m\n", g.lowVminTest);
    if (g.lowVminTest < 590)
        printf("\x1b[33mNote: HOC documentation recommends >=590 mV.\x1b[0m\n");
    printf("Save KIP and reboot.\n\n");
    printf("If it boots, set Overrides:\n  CPU 1020 / GPU 384 / RAM 1331\n");
    printf("Run Matrixprod for 1 minute at 1020 MHz.\n");
    printf("Then briefly check CPU 510, 612 and 816 MHz too.\n");
    printf("Any error at any clock = FAIL.\n");
    footerTrial();
}

void renderLowVminLong() {
    title();
    if (g.recoveryNeeded) printSafeRecovery("CPU Low VMIN = " + std::to_string(g.lowVminGood) + " mV");
    else {
        printf("Restore CPU Low VMIN = \x1b[1m%d mV\x1b[0m\n", g.lowVminGood);
        printf("Save KIP and reboot.\n\n");
    }
    printf("Set Overrides: GPU 384 / RAM 1331.\n");
    printf("Set CPU to 510 MHz and run Matrixprod for \x1b[1m1 HOUR\x1b[0m.\n");
    printf("Afterwards also check Sleep/Wake, Home Menu and game launch.\n");
    footerValidation();
}

void renderVddqQuick() {
    title();
    printf("Keep VDD2 at stock: %s\n", formatVdd2(STOCK_VDD2_UV).c_str());
    printf("In Horizon OC set:\n  RAM VDDQ = \x1b[1m%d mV\x1b[0m\n", g.vddqTest);
    printf("Save KIP and reboot.\n\n");
    printf("If it boots, set Overrides:\n");
    printf("  CPU 1785 MHz / GPU 76.8 MHz / RAM 1600 MHz\n\n");
    printf("Run: Benchmark Toolbox -> MemTester -> \x1b[1m1 minute\x1b[0m\n");
    printf("Any error/mismatch = FAIL.\n");
    footerTrial();
}

void renderVddqLong() {
    title();
    if (g.recoveryNeeded) printSafeRecovery("RAM VDDQ = " + std::to_string(g.vddqGood) + " mV");
    else {
        printf("Restore RAM VDDQ = \x1b[1m%d mV\x1b[0m\n", g.vddqGood);
        printf("Save KIP and reboot.\n\n");
    }
    printf("Set Overrides: CPU 1785 / GPU 76.8 / RAM 1600\n");
    printf("Run: Benchmark Toolbox -> MemTester -> \x1b[1m1 HOUR\x1b[0m\n");
    footerValidation();
}

void renderVdd2Quick() {
    title();
    printf("Keep final VDDQ = %d mV.\n", g.vddqGood);
    printf("In Horizon OC set:\n  RAM VDD2 = \x1b[1m%s\x1b[0m\n", formatVdd2(g.vdd2TestUv).c_str());
    printf("Save KIP and reboot.\n\n");
    printf("If it boots, set Overrides:\n");
    printf("  CPU 1785 MHz / GPU 76.8 MHz / RAM 1600 MHz\n\n");
    printf("Run: Benchmark Toolbox -> MemTester -> \x1b[1m1 minute\x1b[0m\n");
    printf("Any error/mismatch = FAIL.\n");
    footerTrial();
}

void renderVdd2Long() {
    title();
    if (g.recoveryNeeded) printSafeRecovery("RAM VDD2 = " + formatVdd2(g.vdd2GoodUv));
    else {
        printf("Restore RAM VDD2 = \x1b[1m%s\x1b[0m\n", formatVdd2(g.vdd2GoodUv).c_str());
        printf("Save KIP and reboot.\n\n");
    }
    printf("Keep VDDQ = %d mV.\n", g.vddqGood);
    printf("Set Overrides: CPU 1785 / GPU 76.8 / RAM 1600\n");
    printf("Run: Benchmark Toolbox -> MemTester -> \x1b[1m1 HOUR\x1b[0m\n");
    footerValidation();
}

void renderRam1331() {
    title();
    printf("Keep final RAM voltages:\n");
    printf("  VDDQ %d mV / VDD2 %s\n\n", g.vddqGood, formatVdd2(g.vdd2GoodUv).c_str());
    printf("Set Overrides:\n  CPU 1020 / GPU 384 / RAM 1331\n\n");
    printf("Run: Benchmark Toolbox -> MemTester -> \x1b[1m1 HOUR\x1b[0m\n");
    printf("If this fails, mark FAIL. The wizard will raise RAM voltage safely.\n");
    footerValidation();
}

void renderHighUvQuick() {
    title();
    printf("Keep all final Low UV/VMIN/RAM values.\n");
    printf("In Horizon OC set:\n  CPU High UV = \x1b[1m%d\x1b[0m\n", g.highUvTest);
    printf("Save KIP and reboot.\n\n");
    printf("If it boots, set Overrides:\n");
    printf("  CPU 1785 MHz / GPU 76.8 MHz / RAM 1600 MHz\n\n");
    printf("Run: StressNX -> Matrixprod -> \x1b[1m1 minute\x1b[0m\n");
    footerTrial();
}

void renderHighUvLong() {
    title();
    if (g.recoveryNeeded) printSafeRecovery("CPU High UV = " + std::to_string(g.highUvGood));
    else {
        printf("Restore CPU High UV = \x1b[1m%d\x1b[0m\n", g.highUvGood);
        printf("Save KIP and reboot.\n\n");
    }
    printf("Set Overrides: CPU 1785 / GPU 76.8 / RAM 1600\n");
    printf("Run: StressNX -> Matrixprod -> \x1b[1m1 HOUR\x1b[0m\n");
    footerValidation();
}

void renderSimpleValidation(const char* test, const char* clocks, const char* note = nullptr) {
    title();
    printf("Set Overrides:\n  %s\n\n", clocks);
    printf("Run: %s -> \x1b[1m1 HOUR\x1b[0m\n", test);
    if (note) printf("\n%s\n", note);
    footerValidation();
}

void renderRealWorld() {
    title();
    printf("Remove manual Overrides and use the console normally.\n\n");
    printf("Play Tears of the Kingdom for at least \x1b[1m1 HOUR\x1b[0m.\n");
    printf("Include fast travel, battles, loading, Home Menu and Sleep/Wake.\n");
    printf("Make sure the console transitions normally between:\n");
    printf("  1020 / 384 / 1331\n");
    printf("  1785 / 76.8 / 1600 Boost\n\n");
    printf("No crash, freeze or reboot is allowed.\n");
    footerValidation();
}

void renderComplete() {
    title();
    printf("\x1b[32mBATTERY TUNING COMPLETE\x1b[0m\n\n");
    printf("Final values:\n");
    printf("  CPU Low UV   : %d\n", g.lowUvGood);
    printf("  CPU Low VMIN : %d mV\n", g.lowVminGood);
    printf("  RAM VDDQ     : %d mV\n", g.vddqGood);
    printf("  RAM VDD2     : %s\n", formatVdd2(g.vdd2GoodUv).c_str());
    printf("  CPU High UV  : %d\n\n", g.highUvGood);
    printf("Results saved to:\n  /switch/HOC-Battery-Wizard/results.txt\n\n");
    printf("[B] Exit   [-] Reset wizard\n");
}

void render() {
    consoleClear();
    if (g_resetConfirm) {
        printf("\x1b[1;1H\x1b[31mReset ALL wizard progress?\x1b[0m\n\n");
        printf("[A] Yes, reset   [B] Cancel\n");
        consoleUpdate(nullptr);
        return;
    }

    switch (g.stage) {
        case Stage::Preparation: renderPreparation(); break;
        case Stage::LowUvQuick: renderLowUvQuick(); break;
        case Stage::LowUvLong: renderLowUvLong(); break;
        case Stage::LowVminQuick: renderLowVminQuick(); break;
        case Stage::LowVminLong: renderLowVminLong(); break;
        case Stage::VddqQuick: renderVddqQuick(); break;
        case Stage::VddqLong: renderVddqLong(); break;
        case Stage::Vdd2Quick: renderVdd2Quick(); break;
        case Stage::Vdd2Long: renderVdd2Long(); break;
        case Stage::Ram1331Validate: renderRam1331(); break;
        case Stage::HighUvQuick: renderHighUvQuick(); break;
        case Stage::HighUvLong: renderHighUvLong(); break;
        case Stage::BoostCpuRamValidate:
            renderSimpleValidation("Benchmark Toolbox -> CPU-Memtester", "CPU 1785 / GPU 76.8 / RAM 1600",
                "If this fails after RAM-only tests passed, first make High UV one level safer.");
            break;
        case Stage::NormalMatrixValidate:
            renderSimpleValidation("StressNX -> Matrixprod", "CPU 1020 / GPU 384 / RAM 1331"); break;
        case Stage::NormalMemValidate:
            renderSimpleValidation("Benchmark Toolbox -> MemTester", "CPU 1020 / GPU 384 / RAM 1331"); break;
        case Stage::NormalGpuValidate:
            renderSimpleValidation("GPU Stress Test", "CPU 1020 / GPU 384 / RAM 1331"); break;
        case Stage::BoostMatrixValidate:
            renderSimpleValidation("StressNX -> Matrixprod", "CPU 1785 / GPU 76.8 / RAM 1600"); break;
        case Stage::BoostMemValidate:
            renderSimpleValidation("Benchmark Toolbox -> MemTester", "CPU 1785 / GPU 76.8 / RAM 1600"); break;
        case Stage::BoostCpuMemValidate:
            renderSimpleValidation("Benchmark Toolbox -> CPU-Memtester", "CPU 1785 / GPU 76.8 / RAM 1600"); break;
        case Stage::RealWorldValidate: renderRealWorld(); break;
        case Stage::Complete: renderComplete(); break;
    }
    consoleUpdate(nullptr);
}

void enterLowUvLong(bool recovery) {
    g.stage = Stage::LowUvLong;
    g.recoveryNeeded = recovery;
    saveState();
}
void enterLowVminLong(bool recovery) {
    g.stage = Stage::LowVminLong;
    g.recoveryNeeded = recovery;
    saveState();
}
void enterVddqLong(bool recovery) {
    g.stage = Stage::VddqLong;
    g.recoveryNeeded = recovery;
    saveState();
}
void enterVdd2Long(bool recovery) {
    g.stage = Stage::Vdd2Long;
    g.recoveryNeeded = recovery;
    saveState();
}
void enterHighUvLong(bool recovery) {
    g.stage = Stage::HighUvLong;
    g.recoveryNeeded = recovery;
    saveState();
}

void handlePass() {
    switch (g.stage) {
        case Stage::Preparation:
            g.stage = Stage::LowUvQuick;
            break;
        case Stage::LowUvQuick:
            g.lowUvGood = g.lowUvTest;
            if (g.lowUvTest >= LOW_UV_MAX) enterLowUvLong(false);
            else g.lowUvTest++;
            break;
        case Stage::LowUvLong:
            g.recoveryNeeded = false;
            g.stage = Stage::LowVminQuick;
            g.lowVminTest = g.lowVminGood - LOW_VMIN_STEP_MV;
            break;
        case Stage::LowVminQuick:
            g.lowVminGood = g.lowVminTest;
            if (g.lowVminTest <= LOW_VMIN_MIN_MV) enterLowVminLong(false);
            else g.lowVminTest -= LOW_VMIN_STEP_MV;
            break;
        case Stage::LowVminLong:
            g.recoveryNeeded = false;
            g.stage = Stage::VddqQuick;
            g.vddqTest = STOCK_VDDQ_MV - VDDQ_STEP_MV;
            break;
        case Stage::VddqQuick:
            g.vddqGood = g.vddqTest;
            if (g.vddqTest <= VDDQ_MIN_MV) enterVddqLong(false);
            else g.vddqTest -= VDDQ_STEP_MV;
            break;
        case Stage::VddqLong:
            g.recoveryNeeded = false;
            g.stage = Stage::Vdd2Quick;
            g.vdd2TestUv = STOCK_VDD2_UV - VDD2_STEP_UV;
            break;
        case Stage::Vdd2Quick:
            g.vdd2GoodUv = g.vdd2TestUv;
            if (g.vdd2TestUv <= VDD2_MIN_UV) enterVdd2Long(false);
            else g.vdd2TestUv -= VDD2_STEP_UV;
            break;
        case Stage::Vdd2Long:
            g.recoveryNeeded = false;
            g.stage = Stage::Ram1331Validate;
            break;
        case Stage::Ram1331Validate:
            g.stage = Stage::HighUvQuick;
            g.highUvTest = 1;
            break;
        case Stage::HighUvQuick:
            g.highUvGood = g.highUvTest;
            if (g.highUvTest >= HIGH_UV_MAX) enterHighUvLong(false);
            else g.highUvTest++;
            break;
        case Stage::HighUvLong:
            g.recoveryNeeded = false;
            g.stage = Stage::BoostCpuRamValidate;
            break;
        case Stage::BoostCpuRamValidate:
            g.stage = Stage::NormalMatrixValidate;
            break;
        case Stage::NormalMatrixValidate:
            g.stage = Stage::NormalMemValidate;
            break;
        case Stage::NormalMemValidate:
            g.stage = Stage::NormalGpuValidate;
            break;
        case Stage::NormalGpuValidate:
            g.stage = Stage::BoostMatrixValidate;
            break;
        case Stage::BoostMatrixValidate:
            g.stage = Stage::BoostMemValidate;
            break;
        case Stage::BoostMemValidate:
            g.stage = Stage::BoostCpuMemValidate;
            break;
        case Stage::BoostCpuMemValidate:
            g.stage = Stage::RealWorldValidate;
            break;
        case Stage::RealWorldValidate:
            g.stage = Stage::Complete;
            writeResults();
            break;
        case Stage::Complete:
            break;
    }
    saveState();
}

void handleFail(bool didNotBoot) {
    switch (g.stage) {
        case Stage::LowUvQuick: enterLowUvLong(didNotBoot); return;
        case Stage::LowUvLong:
            if (g.lowUvGood > 0) g.lowUvGood--;
            g.recoveryNeeded = false;
            break;
        case Stage::LowVminQuick: enterLowVminLong(didNotBoot); return;
        case Stage::LowVminLong:
            g.lowVminGood += LOW_VMIN_STEP_MV;
            g.recoveryNeeded = false;
            break;
        case Stage::VddqQuick: enterVddqLong(didNotBoot); return;
        case Stage::VddqLong:
            g.vddqGood += VDDQ_STEP_MV;
            g.recoveryNeeded = false;
            break;
        case Stage::Vdd2Quick: enterVdd2Long(didNotBoot); return;
        case Stage::Vdd2Long:
            g.vdd2GoodUv += VDD2_STEP_UV;
            g.recoveryNeeded = false;
            break;
        case Stage::Ram1331Validate:
            // First raise VDDQ by 5 mV, keeping diagnosis simple.
            g.vddqGood += VDDQ_STEP_MV;
            break;
        case Stage::HighUvQuick: enterHighUvLong(didNotBoot); return;
        case Stage::HighUvLong:
            if (g.highUvGood > 0) g.highUvGood--;
            g.recoveryNeeded = false;
            break;
        case Stage::BoostCpuRamValidate:
            if (g.highUvGood > 0) g.highUvGood--;
            break;
        case Stage::NormalMatrixValidate:
            if (g.lowUvGood > 0) g.lowUvGood--;
            break;
        case Stage::NormalMemValidate:
            g.vddqGood += VDDQ_STEP_MV;
            break;
        case Stage::NormalGpuValidate:
            // The wizard does not tune GPU voltage. Stay on this stage and ask user to investigate GPU separately.
            break;
        case Stage::BoostMatrixValidate:
            if (g.highUvGood > 0) g.highUvGood--;
            break;
        case Stage::BoostMemValidate:
            g.vddqGood += VDDQ_STEP_MV;
            break;
        case Stage::BoostCpuMemValidate:
            if (g.highUvGood > 0) g.highUvGood--;
            break;
        case Stage::RealWorldValidate:
            // Stay here. User must inspect which domain failed before changing values blindly.
            break;
        default:
            break;
    }
    saveState();
}

} // namespace

int main() {
    consoleInit(nullptr);
    padConfigureInput(1, HidNpadStyleSet_NpadStandard);
    PadState pad;
    padInitializeDefault(&pad);

    ensureDir();
    if (!loadState()) saveState();

    bool redraw = true;
    while (appletMainLoop()) {
        padUpdate(&pad);
        const u64 k = padGetButtonsDown(&pad);

        if (redraw) {
            render();
            redraw = false;
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
        } else if (k & HidNpadButton_A) {
            handlePass();
            redraw = true;
        } else if (k & HidNpadButton_X) {
            handleFail(false);
            redraw = true;
        } else if ((k & HidNpadButton_Y) &&
                   (g.stage == Stage::LowUvQuick || g.stage == Stage::LowVminQuick ||
                    g.stage == Stage::VddqQuick || g.stage == Stage::Vdd2Quick ||
                    g.stage == Stage::HighUvQuick)) {
            handleFail(true);
            redraw = true;
        }

        svcSleepThread(20'000'000);
    }

    consoleExit(nullptr);
    return 0;
}
