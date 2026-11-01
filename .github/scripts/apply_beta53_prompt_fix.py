from pathlib import Path


def replace_once(text, old, new, name):
    if old not in text:
        raise SystemExit(f"missing block: {name}")
    return text.replace(old, new, 1)

main_path = Path('source/main.cpp')
readme_path = Path('README.md')
main = main_path.read_text()
readme = readme_path.read_text()

main = replace_once(main,
'''    int testDurationSec = 0;\n    int testStage = 0;\n};\n''',
'''    int testDurationSec = 0;\n    int testStage = 0;\n\n    // Optional final export to Performance Modes.\n    // 0 = decision pending, 1 = saved, 2 = skipped.\n    int batteryProfileSaveChoice = 0;\n};\n''', 'persisted Performance Modes choice')

main = replace_once(main,
'''bool g_guiPulse = false;\nbool g_realWorldHelpPage = false;\nbool g_performanceSaveNotice = false;\nbool g_performanceSaveSuccess = false;\nstd::string g_performanceSaveError;\n''',
'''bool g_guiPulse = false;\nbool g_realWorldHelpPage = false;\nbool g_saveBatteryPrompt = false;\nbool g_performanceSaveNotice = false;\nstd::string g_performanceSaveError;\n''', 'save UI state')

main = replace_once(main,
'''    f << "testDurationSec=" << g.testDurationSec << "\\n";\n    f << "testStage=" << g.testStage << "\\n";\n    f.flush();\n''',
'''    f << "testDurationSec=" << g.testDurationSec << "\\n";\n    f << "testStage=" << g.testStage << "\\n";\n    f << "batteryProfileSaveChoice=" << g.batteryProfileSaveChoice << "\\n";\n    f.flush();\n''', 'save choice to state')

main = replace_once(main,
'''    else if (key == "testDurationSec") g.testDurationSec = v;\n    else if (key == "testStage") g.testStage = v;\n}\n''',
'''    else if (key == "testDurationSec") g.testDurationSec = v;\n    else if (key == "testStage") g.testStage = v;\n    else if (key == "batteryProfileSaveChoice") g.batteryProfileSaveChoice = v;\n}\n''', 'load choice from state')

main = replace_once(main,
'''        case Stage::RealWorldValidate:\n            g_realWorldHelpPage = false;\n            g.stage = Stage::Complete;\n            writeResults();\n            break;\n''',
'''        case Stage::RealWorldValidate:\n            g_realWorldHelpPage = false;\n            g.stage = Stage::Complete;\n            g.batteryProfileSaveChoice = 0;\n            g_performanceSaveError.clear();\n            g_saveBatteryPrompt = true;\n            writeResults();\n            break;\n''', 'open final save prompt')

old_complete = '''void renderComplete() {\n    title();\n    uiPrintf(5, "\\x1b[32mUNDERVOLTING COMPLETE\\x1b[0m");\n    uiPrintf(7, "Final values:");\n    uiPrintf(8, "CPU Low UV : %d", g.lowUvGood);\n    uiPrintf(9, "CPU Low VMIN : %d mV", g.lowVminGood);\n    uiPrintf(10, "RAM VDDQ : %d mV", g.vddqGood);\n    uiPrintf(11, "RAM VDD2 : %s", formatVdd2(g.vdd2GoodUv).c_str());\n    uiPrintf(12, "CPU High UV : %d", g.highUvGood);\n\n    if (g_performanceSaveSuccess) {\n        uiPrintf(14, "Saved to Performance Modes -> Battery Mode");\n        uiPrintf(17, "B : Exit");\n        printResetHint(17);\n    } else {\n        uiPrintf(16, "A : Save Settings as Battery Profile in Performance Modes");\n        uiPrintf(17, "X : Skip");\n        uiPrintf(18, "B : Exit");\n        printResetHint(18);\n    }\n}\n\nvoid renderPerformanceSaveNotice() {\n    gui::ModalView m{};\n    m.version = HOC_WIZARD_VERSION;\n    m.eyebrow = "PERFORMANCE MODES";\n    if (g_performanceSaveSuccess) {\n        m.title = "Battery profile saved";\n        m.body = {\n            "Saved to Performance Modes -> Battery Mode.",\n            "Horizon OC config.ini, hoc.kip and ReverseNX-RT were copied.",\n            "The active Performance Modes profile was not changed."\n        };\n        m.tone = gui::ModalTone::Green;\n    } else {\n        m.title = "Battery profile was not saved";\n        m.body = {\n            g_performanceSaveError.empty() ? "The profile could not be saved." : g_performanceSaveError,\n            "No Performance Modes profile switch was performed."\n        };\n        m.tone = gui::ModalTone::Red;\n    }\n    m.primaryAction = "Back to results";\n    gui::presentModal(m);\n}\n'''
new_complete = '''void renderComplete() {\n    title();\n    uiPrintf(5, "\\x1b[32mUNDERVOLTING COMPLETE\\x1b[0m");\n    uiPrintf(7, "Final values:");\n    uiPrintf(8, "CPU Low UV : %d", g.lowUvGood);\n    uiPrintf(9, "CPU Low VMIN : %d mV", g.lowVminGood);\n    uiPrintf(10, "RAM VDDQ : %d mV", g.vddqGood);\n    uiPrintf(11, "RAM VDD2 : %s", formatVdd2(g.vdd2GoodUv).c_str());\n    uiPrintf(12, "CPU High UV : %d", g.highUvGood);\n    if (g.batteryProfileSaveChoice == 1)\n        uiPrintf(14, "Saved to Performance Modes -> Battery Mode");\n    uiPrintf(17, "B : Exit");\n    printResetHint(17);\n}\n\nvoid renderPerformanceSavePrompt() {\n    gui::ModalView m{};\n    m.version = HOC_WIZARD_VERSION;\n    m.eyebrow = "PERFORMANCE MODES";\n    m.title = "Save Settings as Battery Profile in Performance Modes?";\n    m.body = {\n        "This performs the same save as Performance Modes -> Save Settings -> as Battery Mode.",\n        "The current Horizon OC config.ini, hoc.kip and ReverseNX-RT profile will be copied to the Performance Modes Battery profile.",\n        "The active Performance Modes profile will not be changed."\n    };\n    if (!g_performanceSaveError.empty())\n        m.body.push_back("Save failed: " + g_performanceSaveError);\n    m.primaryAction = "Save Settings as Battery Profile";\n    m.tertiaryAction = "Skip";\n    m.secondaryAction = "Back";\n    m.tone = g_performanceSaveError.empty() ? gui::ModalTone::Cyan : gui::ModalTone::Red;\n    gui::presentModal(m);\n}\n\nvoid renderPerformanceSaveNotice() {\n    gui::ModalView m{};\n    m.version = HOC_WIZARD_VERSION;\n    m.eyebrow = "PERFORMANCE MODES";\n    m.title = "Battery profile saved";\n    m.body = {\n        "Saved to Performance Modes -> Battery Mode.",\n        "Horizon OC config.ini, hoc.kip and ReverseNX-RT were copied.",\n        "The active Performance Modes profile was not changed."\n    };\n    m.primaryAction = "Continue to results";\n    m.tone = gui::ModalTone::Green;\n    gui::presentModal(m);\n}\n'''
main = replace_once(main, old_complete, new_complete, 'final save/complete screens')

main = replace_once(main,
'''    if (g_performanceSaveNotice) { renderPerformanceSaveNotice(); return; }\n    if (g_bootPrompt) { renderBootPrompt(); return; }\n''',
'''    if (g_performanceSaveNotice) { renderPerformanceSaveNotice(); return; }\n    if (g_saveBatteryPrompt) { renderPerformanceSavePrompt(); return; }\n    if (g_bootPrompt) { renderBootPrompt(); return; }\n''', 'save prompt render priority')

main = replace_once(main,
'''    g_interruptedPrompt = g.testRunning;\n    g_bootPrompt = g.rebootPending;\n\n    bool redraw = true;\n''',
'''    g_interruptedPrompt = g.testRunning;\n    g_bootPrompt = g.rebootPending;\n    g_saveBatteryPrompt = (g.stage == Stage::Complete && g.batteryProfileSaveChoice == 0);\n\n    bool redraw = true;\n''', 'resume pending prompt')

main = replace_once(main,
'''        if (g_performanceSaveNotice) {\n            if (k & HidNpadButton_A || k & HidNpadButton_B) {\n                g_performanceSaveNotice = false;\n                redraw = true;\n            }\n            svcSleepThread(20'000'000);\n            continue;\n        }\n\n        if (g_resultScreen) {\n''',
'''        if (g_performanceSaveNotice) {\n            if (k & HidNpadButton_A || k & HidNpadButton_B) {\n                g_performanceSaveNotice = false;\n                redraw = true;\n            }\n            svcSleepThread(20'000'000);\n            continue;\n        }\n\n        if (g_saveBatteryPrompt) {\n            if (k & HidNpadButton_A) {\n                g_performanceSaveError.clear();\n                if (saveBatteryProfileToPerformanceModes(g_performanceSaveError)) {\n                    g.batteryProfileSaveChoice = 1;\n                    g_saveBatteryPrompt = false;\n                    g_performanceSaveNotice = true;\n                    saveState();\n                }\n                redraw = true;\n            } else if (k & HidNpadButton_X) {\n                g.batteryProfileSaveChoice = 2;\n                g_saveBatteryPrompt = false;\n                g_performanceSaveError.clear();\n                saveState();\n                redraw = true;\n            } else if (k & HidNpadButton_B) {\n                g.batteryProfileSaveChoice = 0;\n                g_saveBatteryPrompt = false;\n                g_performanceSaveError.clear();\n                g.stage = Stage::RealWorldValidate;\n                g_realWorldHelpPage = true;\n                saveState();\n                redraw = true;\n            }\n            svcSleepThread(20'000'000);\n            continue;\n        }\n\n        if (g_resultScreen) {\n''', 'save prompt input')

main = replace_once(main,
'''        } else if ((k & HidNpadButton_X) && g.stage == Stage::Complete) {\n            // Skip only skips the optional Performance Modes export for now.\n            // Reopening the completed Wizard will offer it again.\n            saveState();\n            break;\n        } else if (k & HidNpadButton_X) {\n''',
'''        } else if (k & HidNpadButton_X) {\n''', 'remove old Complete X handler')

main = replace_once(main,
'''        } else if (k & HidNpadButton_A) {\n            if (g.stage == Stage::Complete) {\n                g_performanceSaveError.clear();\n                g_performanceSaveSuccess = saveBatteryProfileToPerformanceModes(g_performanceSaveError);\n                g_performanceSaveNotice = true;\n                redraw = true;\n                svcSleepThread(20'000'000);\n                continue;\n            }\n            if (g.stage == Stage::RealWorldValidate) {\n''',
'''        } else if (k & HidNpadButton_A) {\n            if (g.stage == Stage::RealWorldValidate) {\n''', 'remove old Complete A handler')

old_readme = '''### Optional: Save Settings as Battery Profile in Performance Modes\n\nOn the Complete page the Wizard offers an explicit optional export:\n\n- **A — Save Settings as Battery Profile in Performance Modes**\n- **X — Skip**\n- **B — Exit**\n\nNothing is exported automatically. Choosing **A** performs the same profile copy used by `Performance Modes -> Save Settings -> as Battery Mode`:\n'''
new_readme = '''### Optional: Save Settings as Battery Profile in Performance Modes\n\nAfter the final real-world guidance, the Wizard opens a separate confirmation:\n\n**Save Settings as Battery Profile in Performance Modes?**\n\n- **A — Save Settings as Battery Profile**\n- **X — Skip**\n- **B — Back** to the final real-world guidance page\n\nNothing is exported automatically. Choosing **A** performs the same profile copy used by `Performance Modes -> Save Settings -> as Battery Mode`:\n'''
readme = replace_once(readme, old_readme, new_readme, 'README prompt wording')

main_path.write_text(main)
readme_path.write_text(readme)
print('beta53 final prompt patch applied')
