from pathlib import Path

# --- main.cpp: switch from console renderer to retained framebuffer GUI after startup ---
p = Path('source/main.cpp')
s = p.read_text()

old = '''gui::View buildGuiView() {
    gui::View v{};
    v.version = HOC_WIZARD_VERSION;
    v.activeStep = guiProgressStep(g.stage);
'''
new = '''gui::View buildGuiView() {
    gui::View v{};
    v.version = HOC_WIZARD_VERSION;
    v.stageTitle = stageName(g.stage);
    v.activeStep = guiProgressStep(g.stage);
'''
if old not in s:
    raise SystemExit('buildGuiView anchor not found')
s = s.replace(old, new, 1)

old = '''void guiPageClear() {
    gui::draw(buildGuiView());
}

void uiPrintf(int row, const char* fmt, ...) {
'''
new = '''void guiPageClear() {
    gui::begin(buildGuiView());
}

void uiPresent() {
    if (gui::isInitialized()) gui::present();
    else consoleUpdate(nullptr);
}

void uiPrintf(int row, const char* fmt, ...) {
'''
if old not in s:
    raise SystemExit('guiPageClear anchor not found')
s = s.replace(old, new, 1)

# Route all main.cpp screen flushes through the compatibility wrapper. Before
# graphical init it still calls libnx consoleUpdate; afterwards it presents the framebuffer.
s = s.replace('consoleUpdate(nullptr);', 'uiPresent();')

# After updater + warning, close the libnx console and create the real framebuffer UI.
anchor = '''    if (!riskAccepted) {
        consoleExit(nullptr);
        return 0;
    }

    ensureDir();
'''
replacement = '''    if (!riskAccepted) {
        consoleExit(nullptr);
        return 0;
    }

    consoleExit(nullptr);
    if (!gui::init()) {
        consoleInit(nullptr);
        while (appletMainLoop()) {
            padUpdate(&pad);
            consoleClear();
            std::printf("\\x1b[1;1H\\x1b[31mHOC Undervolting Wizard - GUI ERROR\\x1b[0m\\n");
            std::printf("------------------------------------------------------------\\n\\n");
            std::printf("Could not initialize the graphical interface.\\n");
            std::printf("The Switch shared font / framebuffer backend is unavailable.\\n\\n");
            std::printf("[B] Exit\\n");
            consoleUpdate(nullptr);
            if (padGetButtonsDown(&pad) & HidNpadButton_B) break;
            svcSleepThread(20'000'000);
        }
        consoleExit(nullptr);
        return 0;
    }

    ensureDir();
'''
if anchor not in s:
    raise SystemExit('post-risk init anchor not found')
s = s.replace(anchor, replacement, 1)

# Final shutdown now belongs to the framebuffer renderer. Replace only the last one.
tail = '''    consoleExit(nullptr);
    return 0;
}
'''
pos = s.rfind(tail)
if pos < 0:
    raise SystemExit('final consoleExit not found')
s = s[:pos] + '''    gui::shutdown();
    return 0;
}
''' + s[pos + len(tail):]

p.write_text(s)

# --- stress_tests.cpp: render built-in tests in the same graphical UI ---
p = Path('source/stress_tests.cpp')
s = p.read_text()
if '#include "gui_console.hpp"' not in s:
    s = s.replace('#include "mt_cpu.h"\n', '#include "mt_cpu.h"\n#include "gui_console.hpp"\n', 1)

start = s.find('void renderProgress(Kind kind, int durationSeconds, std::uint64_t elapsedMs, const Context& c) {')
end = s.find('\n}\n\n} // namespace', start)
if start < 0 or end < 0:
    raise SystemExit('renderProgress function not found')
end += 2
new_func = r'''void renderProgress(Kind kind, int durationSeconds, std::uint64_t elapsedMs, const Context& c) {
    gui::StressView v{};
    v.title = kindName(kind);
    v.subtitle = creditLine(kind);
    v.detail1 = "Do not leave the app while the test is running.";
    v.detail2 = "The Wizard records PASS/FAIL automatically when the test ends.";
    v.elapsedMs = elapsedMs;
    v.durationSeconds = durationSeconds;
    v.cpuPasses = c.cpuIterations.load(std::memory_order_relaxed);
    v.ramLoops = c.ramLoops.load(std::memory_order_relaxed);
    v.gpuPasses = c.gpuIterations.load(std::memory_order_relaxed);
    v.errors = c.errors.load(std::memory_order_relaxed);
    v.mismatches = c.mismatches.load(std::memory_order_relaxed);
    if (kind == Kind::Ram || kind == Kind::Combined) {
        const char* ramTest = c.ramTest.load(std::memory_order_relaxed);
        v.ramTest = ramTest ? ramTest : "-";
        v.ramBytes = c.ramBytes.load(std::memory_order_relaxed);
    }
    gui::presentStress(v);
}'''
s = s[:start] + new_func + s[end:]
p.write_text(s)
