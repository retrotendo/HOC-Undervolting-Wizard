from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

def between(start, end, new, from_pos=0):
    global s
    a = s.index(start, from_pos)
    b = s.index(end, a)
    s = s[:a] + new + s[b:]

stage_name = r'''const char* stageName(Stage s) {
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

'''
between('const char* stageName(Stage s) {', 'bool isQuickStage(Stage s) {', stage_name)

render_pos = s.index('void renderTestStage() {')
a = s.index('        case Stage::LowVminQuick:', render_pos)
b = s.index('        case Stage::VddqQuick:', a)
render_vmin = r'''        case Stage::LowVminQuick:
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
s = s[:a] + render_vmin + s[b:]

p.write_text(s)
print('beta4 source repaired')
