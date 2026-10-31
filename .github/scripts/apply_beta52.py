from pathlib import Path
import re


def replace_once(text, old, new, name):
    if old not in text:
        raise SystemExit(f'missing block: {name}')
    return text.replace(old, new, 1)

main_path = Path('source/main.cpp')
hpp_path = Path('source/gui_console.hpp')
cpp_path = Path('source/gui_console.cpp')
make_path = Path('Makefile')

main = main_path.read_text()
hpp = hpp_path.read_text()
cpp = cpp_path.read_text()
make = make_path.read_text()

main = replace_once(main,
'''bool g_guiPulse = false;\n''',
'''bool g_guiPulse = false;\nint g_realWorldPage = 0;\n''', 'realworld page state')

main = replace_once(main,
'''    v.fullWidthLayout = g_resultScreen || g.stage == Stage::RealWorldValidate || g.stage == Stage::Complete;\n''',
'''    v.fullWidthLayout = g_resultScreen || g.stage == Stage::RealWorldValidate || g.stage == Stage::Complete;\n    v.completionLayout = (g.stage == Stage::Complete);\n    if (g.stage == Stage::Complete)\n        v.summaryFooter = "Saved to Performance Modes · Battery Mode";\n    if (g.stage == Stage::RealWorldValidate && g_realWorldPage == 1)\n        v.stageTitle = "If Instability Occurs";\n''', 'view layout flags')

old_real = re.search(r'''void renderRealWorld\(\) \{.*?\n\}\n\nvoid renderComplete\(\) \{.*?\n\}\n''', main, re.S)
if not old_real:
    raise SystemExit('missing real-world/complete block')
new_real = r'''void renderRealWorld() {
    title();
    if (g_realWorldPage == 0) {
        uiPrintf(5, "Play The Legend of Zelda: Tears of the Kingdom for at least 1 hour.");
        uiPrintf(7, "During the check:");
        uiPrintf(8, "1. Use normal gameplay");
        uiPrintf(9, "2. Include battles and fast travel");
        uiPrintf(10, "3. Use loading screens");
        uiPrintf(11, "4. Test Sleep / Wake");
        uiPrintf(13, "Watch for crashes, freezes or unexpected reboots.");
        uiPrintf(17, "A : Next - If instability occurs");
        uiPrintf(18, "+ : Stable / Continue to results");
        uiPrintf(19, "B : Exit");
        printResetHint(19);
        return;
    }

    uiPrintf(5, "Change only ONE setting at a time, then test the game again.");
    uiPrintf(7, "Recommended order:");
    uiPrintf(8, "1. Low VMIN - raise one step");
    uiPrintf(9, "2. VDDQ - raise one step");
    uiPrintf(10, "3. VDD2 - raise one step");
    uiPrintf(11, "4. CPU High UV - one step less aggressive");
    uiPrintf(12, "5. CPU Low UV - one step less aggressive");
    uiPrintf(14, "If the problem remains, restore that setting to its previous value.");
    uiPrintf(15, "Then move to the next setting in the list and test again.");
    uiPrintf(17, "Never change more than one setting at the same time.");
    uiPrintf(20, "A : Continue to results");
    uiPrintf(21, "B : Back");
    printResetHint(21);
}

void renderComplete() {
    title();
    uiPrintf(17, "B : Exit");
    printResetHint(17);
}
'''
main = main[:old_real.start()] + new_real + main[old_real.end():]

main = replace_once(main,
'''        } else if (k & HidNpadButton_B) {\n            saveState();\n            break;\n''',
'''        } else if (k & HidNpadButton_B) {\n            if (g.stage == Stage::RealWorldValidate && g_realWorldPage == 1) {\n                g_realWorldPage = 0;\n                redraw = true;\n            } else {\n                saveState();\n                break;\n            }\n''', 'realworld back handling')

main = replace_once(main,
'''            if (g.stage == Stage::RealWorldValidate) {\n                g_manualPass = true;\n                handlePass();\n                g_manualPass = false;\n''',
'''            if (g.stage == Stage::RealWorldValidate) {\n                if (g_realWorldPage == 0) {\n                    g_manualPass = true;\n                    handlePass();\n                    g_manualPass = false;\n                }\n''', 'realworld plus handling')

main = replace_once(main,
'''        } else if (k & HidNpadButton_A) {\n            const bool bootSearch = g.stage == Stage::LowUvQuick || g.stage == Stage::LowVminQuick;\n''',
'''        } else if (k & HidNpadButton_A) {\n            if (g.stage == Stage::RealWorldValidate) {\n                if (g_realWorldPage == 0)\n                    g_realWorldPage = 1;\n                else\n                    handlePass();\n                redraw = true;\n                svcSleepThread(20'000'000);\n                continue;\n            }\n            const bool bootSearch = g.stage == Stage::LowUvQuick || g.stage == Stage::LowVminQuick;\n''', 'realworld A navigation')

# Whenever the Wizard enters the Real-World stage, start at page 1 of the new two-page guide.
main = main.replace('g.stage = Stage::RealWorldValidate;\n            break;', 'g.stage = Stage::RealWorldValidate;\n            g_realWorldPage = 0;\n            break;')

hpp = replace_once(hpp,
'''    bool fullWidthLayout = false;\n    bool havePreparationActiveValues = false;\n''',
'''    bool fullWidthLayout = false;\n    bool completionLayout = false;\n    std::string summaryFooter;\n    bool havePreparationActiveValues = false;\n''', 'completion view fields')

marker = '''    body.swap(compactBody);\n\n    if (g_view.preparationLayout) {\n'''
insert = '''    body.swap(compactBody);\n\n    if (g_view.completionLayout) {\n        const int cx = x + w / 2;\n        const std::string done = "UNDERVOLTING COMPLETE";\n        drawText(cx - textWidth(done, 18) / 2, y + 122, 18, C_GREEN, done);\n\n        const std::string heading = "Final values";\n        drawText(cx - textWidth(heading, 16) / 2, y + 160, 16, C_CYAN, heading);\n\n        const int blockW = 430;\n        const int blockX = cx - blockW / 2;\n        const int blockY = y + 195;\n        const int rowH = 42;\n        roundedRect(blockX, blockY, blockW, rowH * 5, 15, C_PANEL_2);\n        for (int i = 0; i < 5; ++i) {\n            if (i) fillRect(blockX + 18, blockY + i * rowH, blockW - 36, 1, mix(C_PANEL_2, C_BORDER, 72));\n            const ValueRow& value = g_view.values[i];\n            drawText(blockX + 24, blockY + i * rowH + 10, 16, C_MUTED, value.label);\n            drawTextRight(blockX + blockW - 24, blockY + i * rowH + 9, 18, C_TEXT, value.value);\n        }\n\n        if (!g_view.summaryFooter.empty()) {\n            drawText(cx - textWidth(g_view.summaryFooter, 17) / 2, blockY + rowH * 5 + 27, 17, C_TEXT, g_view.summaryFooter);\n        }\n\n        if (!actions.empty()) {\n            const int ah = 39;\n            const int gap = 8;\n            const int total = int(actions.size()) * ah + (int(actions.size()) - 1) * gap;\n            int ay = y + h - 24 - total - (reset.empty() ? 0 : 28);\n            for (const auto& a : actions) {\n                drawActionButton(x + 26, ay, w - 52, ah, a);\n                ay += ah + gap;\n            }\n        }\n        if (!reset.empty()) drawText(x + 28, y + h - 24, 14, C_MUTED, reset);\n        return;\n    }\n\n    if (g_view.preparationLayout) {\n'''
cpp = replace_once(cpp, marker, insert, 'completion summary renderer')

make = re.sub(r'APP_VERSION := 0\.4\.0-beta\.51', 'APP_VERSION := 0.4.0-beta.52', make, count=1)
if '0.4.0-beta.52' not in make:
    raise SystemExit('Makefile version replacement failed')

main_path.write_text(main)
hpp_path.write_text(hpp)
cpp_path.write_text(cpp)
make_path.write_text(make)
print('beta52 patch applied')
