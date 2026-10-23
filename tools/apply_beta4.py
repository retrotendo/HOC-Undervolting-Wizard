from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

def once(old, new):
    global s
    if old not in s:
        raise SystemExit('missing snippet:\n' + old[:300])
    s = s.replace(old, new, 1)

def between(start, end, new):
    global s
    a = s.index(start)
    b = s.index(end, a)
    s = s[:a] + new + s[b:]

once('''constexpr u32 CLOCK_CPU_NORMAL_HZ = 1020000000U;\nconstexpr u32 CLOCK_CPU_LOW_HZ    = 612000000U;\nconstexpr u32 CLOCK_CPU_VMIN_MID_HZ = 816000000U;\nconstexpr u32 CLOCK_CPU_BOOST_HZ  = 1785000000U;''', '''constexpr u32 CLOCK_CPU_NORMAL_HZ   = 1020000000U;\nconstexpr u32 CLOCK_CPU_VMIN_510_HZ = 510000000U;\nconstexpr u32 CLOCK_CPU_LOW_HZ      = 612000000U;\nconstexpr u32 CLOCK_CPU_VMIN_714_HZ = 714000000U;\nconstexpr u32 CLOCK_CPU_VMIN_MID_HZ = 816000000U;\nconstexpr u32 CLOCK_CPU_VMIN_918_HZ = 918000000U;\nconstexpr u32 CLOCK_CPU_BOOST_HZ    = 1785000000U;''')
once('constexpr int VDDQ_STEP_MV = 5;', 'constexpr int VDDQ_STEP_MV = 10;\nconstexpr u32 VMIN_FLOOR_TOLERANCE_UV = 5000U;')

once('''    LowVminValidate816,\n    LowVminValidate1020\n};''', '''    LowVminValidate816,\n    LowVminValidate1020,\n    // beta.4 additions are appended to preserve older state.ini stage numbers.\n    LowVminSweep612,\n    LowVminSweep714,\n    LowVminSweep918,\n    LowVminFinalLong,\n    RamBoostValidate\n};''')

once('''    int highUvGood = STOCK_HIGH_UV;\n    int highUvTest = 1;\n    bool recoveryNeeded = false;''', '''    int highUvGood = STOCK_HIGH_UV;\n    int highUvTest = 1;\n    u32 vminFloorHz = 0;\n    int vminFloorObservedMv = 0;\n    int ramPairRetryMode = 0;\n    bool recoveryNeeded = false;''')

once('''std::string g_resultAction;''', '''std::string g_resultAction;\nbool g_manualPass = false;\nbool g_lastVminAtFloor = false;''')

between('const char* stageName(Stage s) {', 'bool isQuickStage(Stage s) {', r'''const char* stageName(Stage s) {
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

''')

between('bool testPlan(Stage s, stress::Kind& kind, int& seconds) {', 'bool overridePlan(Stage s, OverrideExpectation& e) {', r'''bool testPlan(Stage s, stress::Kind& kind, int& seconds) {
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

''')

between('bool overridePlan(Stage s, OverrideExpectation& e) {', 'bool clockMatches(u32 current, u32 expected) {', r'''bool overridePlan(Stage s, OverrideExpectation& e) {
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

''')

once('''    f << "highUvGood=" << g.highUvGood << "\\n";\n    f << "highUvTest=" << g.highUvTest << "\\n";''', '''    f << "highUvGood=" << g.highUvGood << "\\n";\n    f << "highUvTest=" << g.highUvTest << "\\n";\n    f << "vminFloorHz=" << g.vminFloorHz << "\\n";\n    f << "vminFloorObservedMv=" << g.vminFloorObservedMv << "\\n";\n    f << "ramPairRetryMode=" << g.ramPairRetryMode << "\\n";''')

once('''    else if (key == "highUvTest") g.highUvTest = v;\n    else if (key == "recoveryNeeded")''', '''    else if (key == "highUvTest") g.highUvTest = v;\n    else if (key == "vminFloorHz") g.vminFloorHz = (u32)v;\n    else if (key == "vminFloorObservedMv") g.vminFloorObservedMv = v;\n    else if (key == "ramPairRetryMode") g.ramPairRetryMode = v;\n    else if (key == "recoveryNeeded")''')

once('''    f << "CPU High UV: " << g.highUvGood << "\\n\\n";''', '''    f << "CPU High UV: " << g.highUvGood << "\\n";\n    if (g.vminFloorHz)\n        f << "Detected highest Low VMIN floor clock: " << (g.vminFloorHz / 1000000U) << " MHz (~" << g.vminFloorObservedMv << " mV)\\n";\n    f << "\\n";''')

between('void footerTest() {', 'void renderPreparation() {', r'''void footerTest() {
    std::printf("\n\x1b[32m[A] START BUILT-IN TEST\x1b[0m   \x1b[36m[+] KNOWN PASS / SKIP\x1b[0m\n");
    std::printf("\x1b[31m[X] KNOWN FAIL / SKIP\x1b[0m\n");
    if (isQuickStage(g.stage)) std::printf("\x1b[33m[Y] DID NOT BOOT\x1b[0m\n");
    std::printf("[B] Exit   [-] Reset wizard\n");
}

''')

between('void renderPreparation() {', 'void renderTestStage() {', r'''void renderPreparation() {
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

''')

# Replace Low VMIN render cases and insert RAM pair stage.
start = s.index('        case Stage::LowVminQuick:')
end = s.index('        case Stage::VddqQuick:', start)
new = r'''        case Stage::LowVminQuick:
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
'''
s = s[:start] + new + s[end:]

once('''        case Stage::Vdd2Long:\n            if (g.recoveryNeeded) printSafeRecovery("RAM VDD2 = " + formatVdd2(g.vdd2GoodUv));\n            else std::printf("Restore RAM VDD2 = \\x1b[1m%s\\x1b[0m, Save KIP and reboot.\\n", formatVdd2(g.vdd2GoodUv).c_str());\n            std::printf("Keep VDDQ = %d mV.\\n", g.vddqGood);\n            std::printf("Overrides: CPU 1785 / GPU 76.8 / RAM 1600\\n");\n            break;\n        case Stage::Ram1331Validate:''', '''        case Stage::Vdd2Long:\n            if (g.recoveryNeeded) printSafeRecovery("RAM VDD2 = " + formatVdd2(g.vdd2GoodUv));\n            else std::printf("Restore RAM VDD2 = \\x1b[1m%s\\x1b[0m, Save KIP and reboot.\\n", formatVdd2(g.vdd2GoodUv).c_str());\n            std::printf("Keep VDDQ = %d mV.\\n", g.vddqGood);\n            std::printf("Overrides: CPU 1785 / GPU 76.8 / RAM 1600\\n");\n            break;\n        case Stage::RamBoostValidate:\n            std::printf("Confirm final VDDQ + VDD2 together at Nintendo Boost clocks.\\n");\n            std::printf("VDDQ %d mV / VDD2 %s\\n", g.vddqGood, formatVdd2(g.vdd2GoodUv).c_str());\n            if (g.ramPairRetryMode == 1) std::printf("Retry mode: VDDQ raised by one 10 mV step.\\n");\n            if (g.ramPairRetryMode == 2) std::printf("Retry mode: VDDQ restored; VDD2 raised by 12.5 mV.\\n");\n            std::printf("Overrides: CPU 1785 / GPU 76.8 / RAM 1600\\n");\n            break;\n        case Stage::Ram1331Validate:''')

# Helpers and state machine.
insert_at = s.index('void enterLowUvLong(bool recovery)')
helpers = r'''bool isVminSweepStage(Stage st) {
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

'''
s = s[:insert_at] + helpers + s[insert_at:]

once('void enterLowVminLong(bool recovery) { g.stage = Stage::LowVminLong; g.recoveryNeeded = recovery; saveState(); }',
     'void enterLowVminLong(bool recovery) { restartVminSweep(recovery); }')

between('void handlePass() {', 'void handleFail(bool didNotBoot) {', r'''void handlePass() {
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

''')

between('void handleFail(bool didNotBoot) {', 'void runCurrentTest() {', r'''void handleFail(bool didNotBoot) {
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

''')

once('''    const Stage testedStage = g.stage;\n    g.testRunning = true;''', '''    const Stage testedStage = g.stage;\n    g_lastVminAtFloor = false;\n    if (isVminSweepStage(testedStage))\n        recordVminObservation(testedStage);\n    g.testRunning = true;''')

# Add voltage note to result action for VMIN sweep.
once('''    if (g_lastResult.outcome == stress::Outcome::Pass) {\n        handlePass();\n        g_resultAction = "PASS recorded automatically. The wizard advanced to the next step.";''', '''    if (g_lastResult.outcome == stress::Outcome::Pass) {\n        handlePass();\n        g_resultAction = "PASS recorded automatically. The wizard advanced to the next step.";\n        if (isVminSweepStage(testedStage)) {\n            const u32 uv = g_overrideCheck.current.cpuVoltageUv;\n            g_resultAction += " CPU rail was about " + std::to_string((uv + 500U) / 1000U) + " mV.";\n        }''')

# New valid-stage bound for interrupted recovery.
s = s.replace('static_cast<int>(Stage::LowVminValidate1020)', 'static_cast<int>(Stage::RamBoostValidate)')

# Manual known-PASS shortcut before manual fail.
once('''        } else if (k & HidNpadButton_Y && isQuickStage(g.stage)) {\n            handleFail(true);\n            redraw = true;\n        } else if (k & HidNpadButton_X) {''', '''        } else if (k & HidNpadButton_Y && isQuickStage(g.stage)) {\n            handleFail(true);\n            redraw = true;\n        } else if (k & HidNpadButton_Plus) {\n            stress::Kind skipKind;\n            int skipSeconds = 0;\n            if (testPlan(g.stage, skipKind, skipSeconds)) {\n                g_manualPass = true;\n                g_lastVminAtFloor = true;\n                handlePass();\n                g_manualPass = false;\n                redraw = true;\n            }\n        } else if (k & HidNpadButton_X) {''')

# Results wording: do not claim a specific table was read.
s = s.replace('CPU UV Table: Default / Normal (not Extreme)', 'CPU UV Table: user-selected (recommended: 1683 MHz Tbreak)')

p.write_text(s)
print('beta4 main.cpp patch applied')
