from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"missing pattern: {label}")
    return text.replace(old, new, 1)

# stress_tests.hpp
p = Path("source/stress_tests.hpp")
s = p.read_text()
s = replace_once(
    s,
    "Result run(Kind kind, int durationSeconds);",
    "Result run(Kind kind, int durationSeconds, const std::string& displayTitle = {}, const std::string& displayContext = {});",
    "stress run signature"
)
p.write_text(s)

# stress_tests.cpp
p = Path("source/stress_tests.cpp")
s = p.read_text()
s = replace_once(
    s,
    "void renderProgress(Kind kind, int durationSeconds, std::uint64_t elapsedMs, const Context& c) {\n    gui::StressView v{};\n    v.title = kindName(kind);\n    v.subtitle = creditLine(kind);\n    v.detail1 = \"Do not leave the app while the test is running.\";\n    v.detail2 = \"The Wizard records PASS/FAIL automatically when the test ends.\";",
    "void renderProgress(Kind kind, int durationSeconds, std::uint64_t elapsedMs, const Context& c,\n                    const std::string& displayTitle, const std::string& displayContext) {\n    gui::StressView v{};\n    v.title = displayTitle.empty() ? kindName(kind) : displayTitle;\n    v.subtitle = displayContext.empty() ? \"Stability validation in progress\" : displayContext;\n    v.detail1 = std::string(\"Test engine: \") + kindName(kind);\n    v.detail2 = creditLine(kind);",
    "stress progress labels"
)
s = replace_once(
    s,
    "Result run(Kind kind, int durationSeconds) {",
    "Result run(Kind kind, int durationSeconds, const std::string& displayTitle, const std::string& displayContext) {",
    "stress run definition"
)
s = replace_once(
    s,
    "renderProgress(kind, durationSeconds, std::uint64_t(elapsed), c);",
    "renderProgress(kind, durationSeconds, std::uint64_t(elapsed), c, displayTitle, displayContext);",
    "render progress call"
)
p.write_text(s)

# main.cpp
p = Path("source/main.cpp")
s = p.read_text()

old = """        g_lastKind = stress::Kind::Cpu;\n        g_lastResult = stress::run(stress::Kind::Cpu, 60);"""
new = """        g_lastKind = stress::Kind::Cpu;\n        const std::string regionTitle = forLowUv ? \"CPU Low UV Stability\" : \"CPU Low VMIN Stability\";\n        const std::string regionContext =\n            \"CPU \" + formatClock(hz) + \"  |  Region \" + std::to_string(i + 1) +\n            \" of \" + std::to_string(g.vminValidateCount) +\n            \"  |  ~\" + std::to_string(g.vminValidateMv[i]) + \" mV\";\n        g_lastResult = stress::run(stress::Kind::Cpu, 60, regionTitle, regionContext);"""
s = replace_once(s, old, new, "region validation labels")

marker = "void runCurrentTest() {\n"
helper = r'''void stressDisplayForStage(Stage st, const OverrideExpectation& expected,
                           std::string& title, std::string& context) {
    title = "Stability Test";
    context.clear();

    auto clockContext = [&]() {
        std::string out;
        if (expected.cpuHz) out += "CPU " + formatClock(expected.cpuHz);
        if (expected.ramHz) {
            if (!out.empty()) out += "  |  ";
            out += "RAM " + formatClock(expected.ramHz);
        }
        return out;
    };

    switch (st) {
        case Stage::VddqQuick:
            title = "VDDQ Stability";
            context = "VDDQ " + std::to_string(g.vddqTest) + " mV";
            break;
        case Stage::VddqLong:
            title = "VDDQ Final Stability";
            context = "VDDQ " + std::to_string(g.vddqGood) + " mV";
            break;
        case Stage::Vdd2Quick:
            title = "VDD2 Stability";
            context = "VDD2 " + formatVdd2(g.vdd2TestUv);
            break;
        case Stage::Vdd2Long:
            title = "VDDQ + VDD2 Pair Stability";
            context = "VDDQ " + std::to_string(g.vddqGood) + " mV  |  VDD2 " + formatVdd2(g.vdd2GoodUv);
            break;
        case Stage::NormalMatrixValidate:
            title = "CPU Low UV + RAM Stability";
            context = clockContext();
            break;
        case Stage::HighUvQuick:
            title = "CPU High UV Stability";
            context = "High UV " + std::to_string(g.highUvTest);
            if (!clockContext().empty()) context += "  |  " + clockContext();
            break;
        case Stage::HighUvLong:
            title = "CPU High UV Stability";
            context = "High UV " + std::to_string(g.highUvGood);
            if (!clockContext().empty()) context += "  |  " + clockContext();
            break;
        case Stage::BoostCpuRamValidate:
            title = "CPU High UV Stability";
            context = "High UV " + std::to_string(g.highUvGood) + "  |  " + clockContext();
            break;
        case Stage::BoostCpuMemValidate:
            title = "CPU High UV + RAM Stability";
            context = "High UV " + std::to_string(g.highUvGood) + "  |  " + clockContext();
            break;
        case Stage::RamBoostValidate:
            title = "RAM Stability";
            context = "Boost state  |  " + clockContext();
            break;
        case Stage::Ram1331Validate:
            title = "RAM Stability";
            context = "Handheld state  |  " + clockContext();
            break;
        case Stage::LowVminFinalLong:
            title = "CPU Low VMIN Stability";
            context = "Low VMIN " + std::to_string(g.lowVminGood) + " mV  |  " + clockContext();
            break;
        default:
            title = stageName(st);
            context = clockContext();
            break;
    }
}

'''
if marker not in s:
    raise SystemExit("missing runCurrentTest marker")
s = s.replace(marker, helper + marker, 1)

old = """    g_lastKind = kind;\n    g_lastResult = stress::run(kind, seconds);"""
new = """    std::string stressTitle;\n    std::string stressContext;\n    stressDisplayForStage(testedStage, expected, stressTitle, stressContext);\n    g_lastKind = kind;\n    g_lastResult = stress::run(kind, seconds, stressTitle, stressContext);"""
s = replace_once(s, old, new, "current test labels")
p.write_text(s)
