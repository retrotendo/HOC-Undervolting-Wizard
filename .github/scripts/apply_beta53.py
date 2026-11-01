from pathlib import Path
import re


def replace_once(text, old, new, name):
    if old not in text:
        raise SystemExit(f"missing block: {name}")
    return text.replace(old, new, 1)

main_path = Path('source/main.cpp')
make_path = Path('Makefile')
readme_path = Path('README.md')

main = main_path.read_text()
make = make_path.read_text()
readme = readme_path.read_text()

main = replace_once(main,
'''#include <algorithm>\n#include <cstdarg>\n''',
'''#include <algorithm>\n#include <cerrno>\n#include <cstdarg>\n#include <dirent.h>\n''', 'includes')

main = replace_once(main,
'''constexpr const char* HOC_CONFIG_BACKUP = "sdmc:/config/horizon-oc/config.ini.wizard.bak";\n''',
'''constexpr const char* HOC_CONFIG_BACKUP = "sdmc:/config/horizon-oc/config.ini.wizard.bak";\nconstexpr const char* PM_PACKAGE_INI = "sdmc:/switch/.packages/Performance Modes/package.ini";\nconstexpr const char* PM_BATTERY_DIR = "sdmc:/switch/.packages/Performance Modes/Battery";\nconstexpr const char* HOC_KIP = "sdmc:/atmosphere/kips/hoc.kip";\nconstexpr const char* REVERSENX_DIR = "sdmc:/SaltySD/plugins/ReverseNX-RT";\n''', 'performance modes paths')

main = replace_once(main,
'''bool g_guiPulse = false;\nbool g_realWorldHelpPage = false;\n''',
'''bool g_guiPulse = false;\nbool g_realWorldHelpPage = false;\nbool g_performanceSaveNotice = false;\nbool g_performanceSaveSuccess = false;\nstd::string g_performanceSaveError;\n''', 'performance save state')

copy_marker = '''bool copyFile(const char* from, const char* to) {\n    std::ifstream src(from, std::ios::binary);\n    if (!src) return false;\n    std::ofstream dst(to, std::ios::binary | std::ios::trunc);\n    if (!dst) return false;\n    dst << src.rdbuf();\n    return bool(dst);\n}\n'''
copy_insert = copy_marker + r'''

bool ensureDirectory(const std::string& path) {
    if (mkdir(path.c_str(), 0777) == 0) return true;
    return errno == EEXIST;
}

bool copyDirectoryRecursive(const std::string& from, const std::string& to) {
    DIR* dir = opendir(from.c_str());
    if (!dir) return false;
    if (!ensureDirectory(to)) {
        closedir(dir);
        return false;
    }

    bool ok = true;
    while (dirent* entry = readdir(dir)) {
        const std::string name = entry->d_name;
        if (name == "." || name == "..") continue;

        const std::string src = from + "/" + name;
        const std::string dst = to + "/" + name;
        struct stat st{};
        if (stat(src.c_str(), &st) != 0) {
            ok = false;
            break;
        }
        if (S_ISDIR(st.st_mode)) {
            if (!copyDirectoryRecursive(src, dst)) {
                ok = false;
                break;
            }
        } else if (S_ISREG(st.st_mode)) {
            if (!copyFile(src.c_str(), dst.c_str())) {
                ok = false;
                break;
            }
        }
    }
    closedir(dir);
    return ok;
}

bool saveBatteryProfileToPerformanceModes(std::string& errorText) {
    errorText.clear();

    if (access(PM_PACKAGE_INI, F_OK) != 0) {
        errorText = "Performance Modes was not found. Nothing was changed.";
        return false;
    }
    if (access(HOC_CONFIG_INI, F_OK) != 0) {
        errorText = "Horizon OC config.ini was not found.";
        return false;
    }
    if (access(HOC_KIP, F_OK) != 0) {
        errorText = "hoc.kip was not found.";
        return false;
    }

    if (!ensureDirectory("sdmc:/switch/.packages") ||
        !ensureDirectory("sdmc:/switch/.packages/Performance Modes") ||
        !ensureDirectory(PM_BATTERY_DIR)) {
        errorText = "Could not create the Performance Modes Battery folder.";
        return false;
    }

    const std::string batteryConfig = std::string(PM_BATTERY_DIR) + "/config.ini";
    const std::string batteryKip = std::string(PM_BATTERY_DIR) + "/hoc.kip";
    if (!copyFile(HOC_CONFIG_INI, batteryConfig.c_str())) {
        errorText = "Could not copy Horizon OC config.ini.";
        return false;
    }
    if (!copyFile(HOC_KIP, batteryKip.c_str())) {
        errorText = "Could not copy hoc.kip.";
        return false;
    }

    // Match Performance Modes -> Save Settings -> as Battery Mode.
    // ReverseNX-RT is part of the Battery profile as well. An empty source
    // folder is valid and is created by Performance Modes itself too.
    ensureDirectory("sdmc:/SaltySD");
    ensureDirectory("sdmc:/SaltySD/plugins");
    if (!ensureDirectory(REVERSENX_DIR)) {
        errorText = "Could not access the ReverseNX-RT profile folder.";
        return false;
    }
    const std::string batteryReverseNx = std::string(PM_BATTERY_DIR) + "/ReverseNX-RT";
    if (!copyDirectoryRecursive(REVERSENX_DIR, batteryReverseNx)) {
        errorText = "Could not copy the ReverseNX-RT profile.";
        return false;
    }

    fsdevCommitDevice("sdmc");
    return true;
}
'''
main = replace_once(main, copy_marker, copy_insert, 'profile copy helpers')

real_complete = re.search(r'''void renderComplete\(\) \{.*?\n\}\n\nvoid renderInterruptedPrompt''', main, re.S)
if not real_complete:
    raise SystemExit('missing renderComplete block')
new_complete = r'''void renderComplete() {
    title();
    uiPrintf(5, "\x1b[32mUNDERVOLTING COMPLETE\x1b[0m");
    uiPrintf(7, "Final values:");
    uiPrintf(8, "CPU Low UV : %d", g.lowUvGood);
    uiPrintf(9, "CPU Low VMIN : %d mV", g.lowVminGood);
    uiPrintf(10, "RAM VDDQ : %d mV", g.vddqGood);
    uiPrintf(11, "RAM VDD2 : %s", formatVdd2(g.vdd2GoodUv).c_str());
    uiPrintf(12, "CPU High UV : %d", g.highUvGood);

    if (g_performanceSaveSuccess) {
        uiPrintf(14, "Saved to Performance Modes -> Battery Mode");
        uiPrintf(17, "B : Exit");
        printResetHint(17);
    } else {
        uiPrintf(16, "A : Save Settings as Battery Profile in Performance Modes");
        uiPrintf(17, "X : Skip");
        uiPrintf(18, "B : Exit");
        printResetHint(18);
    }
}

void renderPerformanceSaveNotice() {
    gui::ModalView m{};
    m.version = HOC_WIZARD_VERSION;
    m.eyebrow = "PERFORMANCE MODES";
    if (g_performanceSaveSuccess) {
        m.title = "Battery profile saved";
        m.body = {
            "Saved to Performance Modes -> Battery Mode.",
            "Horizon OC config.ini, hoc.kip and ReverseNX-RT were copied.",
            "The active Performance Modes profile was not changed."
        };
        m.tone = gui::ModalTone::Green;
    } else {
        m.title = "Battery profile was not saved";
        m.body = {
            g_performanceSaveError.empty() ? "The profile could not be saved." : g_performanceSaveError,
            "No Performance Modes profile switch was performed."
        };
        m.tone = gui::ModalTone::Red;
    }
    m.primaryAction = "Back to results";
    gui::presentModal(m);
}

void renderInterruptedPrompt'''
main = main[:real_complete.start()] + new_complete + main[real_complete.end():]

main = replace_once(main,
'''    if (g_bootPrompt) { renderBootPrompt(); return; }\n''',
'''    if (g_performanceSaveNotice) { renderPerformanceSaveNotice(); return; }\n    if (g_bootPrompt) { renderBootPrompt(); return; }\n''', 'performance save modal render')

result_block = '''        if (g_resultScreen) {\n            if (k & HidNpadButton_A || k & HidNpadButton_B) {\n                g_resultScreen = false;\n                redraw = true;\n            }\n            svcSleepThread(20'000'000);\n            continue;\n        }\n'''
notice_block = r'''        if (g_performanceSaveNotice) {
            if (k & HidNpadButton_A || k & HidNpadButton_B) {
                g_performanceSaveNotice = false;
                redraw = true;
            }
            svcSleepThread(20'000'000);
            continue;
        }

'''
main = replace_once(main, result_block, notice_block + result_block, 'performance save input modal')

main = replace_once(main,
'''        } else if (k & HidNpadButton_X) {\n            // X is only a manual "known unstable" shortcut while searching a\n''',
'''        } else if ((k & HidNpadButton_X) && g.stage == Stage::Complete) {\n            // Skip only skips the optional Performance Modes export for now.\n            // Reopening the completed Wizard will offer it again.\n            saveState();\n            break;\n        } else if (k & HidNpadButton_X) {\n            // X is only a manual "known unstable" shortcut while searching a\n''', 'complete skip handling')

main = replace_once(main,
'''        } else if (k & HidNpadButton_A) {\n            if (g.stage == Stage::RealWorldValidate) {\n''',
'''        } else if (k & HidNpadButton_A) {\n            if (g.stage == Stage::Complete) {\n                g_performanceSaveError.clear();\n                g_performanceSaveSuccess = saveBatteryProfileToPerformanceModes(g_performanceSaveError);\n                g_performanceSaveNotice = true;\n                redraw = true;\n                svcSleepThread(20'000'000);\n                continue;\n            }\n            if (g.stage == Stage::RealWorldValidate) {\n''', 'complete save handling')

make = make.replace('APP_VERSION := 0.4.0-beta.52', 'APP_VERSION := 0.4.0-beta.53', 1)
if 'APP_VERSION := 0.4.0-beta.53' not in make:
    raise SystemExit('Makefile version replacement failed')

readme = readme.replace('current **v0.4.0-beta.52** workflow', 'current **v0.4.0-beta.53** workflow', 1)
results_marker = '''These are the values intended for the **Performance Modes Battery Mode** workflow.\n\n---\n\n# Search limits\n'''
results_replacement = '''These are the values intended for the **Performance Modes Battery Mode** workflow.\n\n### Optional: Save Settings as Battery Profile in Performance Modes\n\nOn the Complete page the Wizard offers an explicit optional export:\n\n- **A — Save Settings as Battery Profile in Performance Modes**\n- **X — Skip**\n- **B — Exit**\n\nNothing is exported automatically. Choosing **A** performs the same profile copy used by `Performance Modes -> Save Settings -> as Battery Mode`:\n\n- `/config/horizon-oc/config.ini` -> `/switch/.packages/Performance Modes/Battery/config.ini`\n- `/atmosphere/kips/hoc.kip` -> `/switch/.packages/Performance Modes/Battery/hoc.kip`\n- `/SaltySD/plugins/ReverseNX-RT/` -> `/switch/.packages/Performance Modes/Battery/ReverseNX-RT/`\n\nThe Wizard does **not** switch or mark the active Performance Modes profile. It only saves the current settings as the Battery profile. If Performance Modes is not installed, the Wizard reports that and does not invent a new installation.\n\n---\n\n# Search limits\n'''
readme = replace_once(readme, results_marker, results_replacement, 'README Performance Modes export section')

main_path.write_text(main)
make_path.write_text(make)
readme_path.write_text(readme)
print('beta53 patch applied')
