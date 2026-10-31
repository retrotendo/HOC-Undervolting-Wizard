from pathlib import Path


def repl(text, old, new, name):
    if old not in text:
        raise SystemExit(f"Missing block: {name}")
    return text.replace(old, new, 1)


main_path = Path("source/main.cpp")
main = main_path.read_text(encoding="utf-8")

main = repl(main,
'''bool g_lastVminAtFloor = false;
bool g_guiPulse = false;
''',
'''bool g_lastVminAtFloor = false;
bool g_guiPulse = false;
bool g_realWorldHelpPage = false;
''',
"real-world page state")

main = repl(main,
'''    v.stageTitle = stageName(g.stage);
    v.activeStep = guiProgressStep(g.stage);
''',
'''    v.stageTitle = stageName(g.stage);
    if (g.stage == Stage::RealWorldValidate && g_realWorldHelpPage)
        v.stageTitle = "If Instability Occurs";
    v.activeStep = guiProgressStep(g.stage);
''',
"real-world page title")

old_realworld = '''void renderRealWorld() {
    title();
    uiPrintf(5, "For final confirmation, play The Legend of Zelda: Tears of the Kingdom for at least 1 hour.");
    uiPrintf(7, "Use normal gameplay, fast travel, battles, loading screens and Sleep/Wake.");
    uiPrintf(9, "If a crash, freeze or reboot occurs, change only ONE setting by one step, then play again.");
    uiPrintf(11, "Recommended order:");
    uiPrintf(12, "Low VMIN -> VDDQ -> VDD2 -> CPU High UV -> CPU Low UV");
    uiPrintf(14, "Low VMIN / VDDQ / VDD2: raise the voltage by one step.");
    uiPrintf(15, "CPU High UV / CPU Low UV: move one step toward a less aggressive undervolt.");
    uiPrintf(17, "If it still fails, restore that setting to its previous value before trying the next one.");
    uiPrintf(18, "Never change more than one setting at a time.");
    uiPrintf(20, "A : Continue to results");
    uiPrintf(21, "B : Exit");
    printResetHint(21);
}

void renderComplete() {
    title();
    uiPrintf(5, "\\x1b[32mUNDERVOLTING COMPLETE\\x1b[0m");
    uiPrintf(7, "Final values:");
    uiPrintf(8, "CPU Low UV   : %d", g.lowUvGood);
    uiPrintf(9, "CPU Low VMIN : %d mV", g.lowVminGood);
    uiPrintf(10, "RAM VDDQ     : %d mV", g.vddqGood);
    uiPrintf(11, "RAM VDD2     : %s", formatVdd2(g.vdd2GoodUv).c_str());
    uiPrintf(12, "CPU High UV  : %d", g.highUvGood);
    uiPrintf(14, "Saved to:");
    uiPrintf(15, "/switch/HOC-Undervolting-Wizard/results.txt");
    uiPrintf(17, "B : Exit");
    printResetHint(17);
}
'''
new_realworld = '''void renderRealWorld() {
    title();
    if (!g_realWorldHelpPage) {
        uiPrintf(5, "For final confirmation, play The Legend of Zelda: Tears of the Kingdom.");
        uiPrintf(7, "Play for at least 1 hour.");
        uiPrintf(9, "During the check:");
        uiPrintf(10, "• Normal gameplay");
        uiPrintf(11, "• Battles and fast travel");
        uiPrintf(12, "• Loading screens");
        uiPrintf(13, "• Sleep / Wake");
        uiPrintf(15, "Watch for crashes, freezes or unexpected reboots.");
        uiPrintf(19, "A : If instability occurs");
        uiPrintf(20, "+ : Stable / Continue to results");
        uiPrintf(21, "B : Exit");
        printResetHint(21);
        return;
    }

    uiPrintf(5, "Change only ONE setting at a time. Change it by one step, then play again.");
    uiPrintf(7, "Recommended order:");
    uiPrintf(9, "1. Low VMIN - raise voltage one step");
    uiPrintf(10, "2. VDDQ - raise voltage one step");
    uiPrintf(11, "3. VDD2 - raise voltage one step");
    uiPrintf(12, "4. CPU High UV - one step less aggressive");
    uiPrintf(13, "5. CPU Low UV - one step less aggressive");
    uiPrintf(15, "If it still fails, restore that setting to its previous value before trying the next one.");
    uiPrintf(17, "Never change multiple settings at the same time.");
    uiPrintf(20, "A : Continue to results");
    uiPrintf(21, "B : Back");
    printResetHint(21);
}

void renderComplete() {
    title();
    uiPrintf(5, "\\x1b[32mUNDERVOLTING COMPLETE\\x1b[0m");
    uiPrintf(7, "Final values:");
    uiPrintf(8, "CPU Low UV : %d", g.lowUvGood);
    uiPrintf(9, "CPU Low VMIN : %d mV", g.lowVminGood);
    uiPrintf(10, "RAM VDDQ : %d mV", g.vddqGood);
    uiPrintf(11, "RAM VDD2 : %s", formatVdd2(g.vdd2GoodUv).c_str());
    uiPrintf(12, "CPU High UV : %d", g.highUvGood);
    uiPrintf(14, "Saved to Performance Modes · Battery Mode");
    uiPrintf(17, "B : Exit");
    printResetHint(17);
}
'''
main = repl(main, old_realworld, new_realworld, "real-world and complete pages")

main = repl(main,
'''        case Stage::RealWorldValidate: g.stage = Stage::Complete; writeResults(); break;
''',
'''        case Stage::RealWorldValidate:
            g_realWorldHelpPage = false;
            g.stage = Stage::Complete;
            writeResults();
            break;
''',
"real-world completion")

main = repl(main,
'''        if (k & HidNpadButton_Minus) {
            g_resetConfirm = true;
            redraw = true;
        } else if (k & HidNpadButton_B) {
            saveState();
            break;
''',
'''        if (k & HidNpadButton_Minus) {
            g_resetConfirm = true;
            redraw = true;
        } else if ((k & HidNpadButton_B) && g.stage == Stage::RealWorldValidate && g_realWorldHelpPage) {
            g_realWorldHelpPage = false;
            redraw = true;
        } else if (k & HidNpadButton_B) {
            saveState();
            break;
''',
"real-world back button")

main = repl(main,
'''        } else if ((k & HidNpadButton_Plus) && g.stage != Stage::Preparation) {
            if (g.stage == Stage::RealWorldValidate) {
                g_manualPass = true;
                handlePass();
                g_manualPass = false;
''',
'''        } else if ((k & HidNpadButton_Plus) && g.stage != Stage::Preparation) {
            if (g.stage == Stage::RealWorldValidate && !g_realWorldHelpPage) {
                g_manualPass = true;
                handlePass();
                g_manualPass = false;
''',
"real-world stable shortcut")

main = repl(main,
'''        } else if (k & HidNpadButton_A) {
            const bool bootSearch = g.stage == Stage::LowUvQuick || g.stage == Stage::LowVminQuick;
''',
'''        } else if (k & HidNpadButton_A) {
            if (g.stage == Stage::RealWorldValidate) {
                if (!g_realWorldHelpPage) {
                    g_realWorldHelpPage = true;
                } else {
                    g_manualPass = true;
                    handlePass();
                    g_manualPass = false;
                }
                redraw = true;
                svcSleepThread(20'000'000);
                continue;
            }
            const bool bootSearch = g.stage == Stage::LowUvQuick || g.stage == Stage::LowVminQuick;
''',
"real-world A navigation")

main_path.write_text(main, encoding="utf-8")


gui_path = Path("source/gui_console.cpp")
gui = gui_path.read_text(encoding="utf-8")

gui = repl(gui,
'''    body.swap(compactBody);

    if (g_view.preparationLayout) {
''',
'''    body.swap(compactBody);

    const bool completeSummary = g_view.fullWidthLayout && g_view.stageTitle == "Complete";
    if (completeSummary) {
        auto drawCentered = [&](int yy, int size, u32 color, const std::string& text) {
            drawText(x + (w - textWidth(text, size)) / 2, yy, size, color, text);
        };

        drawCentered(y + 124, 20, C_GREEN, "UNDERVOLTING COMPLETE");
        drawCentered(y + 164, 16, C_CYAN, "Final values");

        const int tableW = 470;
        const int tableX = x + (w - tableW) / 2;
        int sy = y + 205;
        int rows = 0;
        std::string savedLine;
        for (const std::string& raw : body) {
            if (raw == "UNDERVOLTING COMPLETE" || raw == "Final values:") continue;
            if (startsWith(raw, "Saved to ")) {
                savedLine = raw;
                continue;
            }
            const size_t colon = raw.find(':');
            if (colon == std::string::npos || colon == 0 || colon >= raw.size() - 1) continue;
            const std::string label = trim(raw.substr(0, colon));
            const std::string value = trim(raw.substr(colon + 1));
            if (rows) fillRect(tableX, sy - 8, tableW, 1, mix(C_PANEL, C_BORDER, 65));
            drawText(tableX + 8, sy, 17, C_MUTED, label);
            drawTextRight(tableX + tableW - 8, sy, 18, C_TEXT, value);
            sy += 39;
            ++rows;
        }
        if (!savedLine.empty()) {
            sy += 12;
            drawCentered(sy, 17, C_CYAN, savedLine);
        }
    } else if (g_view.preparationLayout) {
''',
"complete centered summary")

gui_path.write_text(gui, encoding="utf-8")


make_path = Path("Makefile")
make = make_path.read_text(encoding="utf-8")
make = repl(make, "APP_VERSION := 0.4.0-beta.51", "APP_VERSION := 0.4.0-beta.52", "version")
make_path.write_text(make, encoding="utf-8")

print("beta52 patch applied")
