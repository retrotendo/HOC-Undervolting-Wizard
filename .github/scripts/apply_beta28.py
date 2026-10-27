from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

repls = []

repls.append((
'''#include <sys/stat.h>\n#include <unistd.h>''',
'''#include <sys/stat.h>\n#include <unistd.h>\n#include <vector>'''))

repls.append((
'''constexpr const char* HOC_CONFIG_INI = "sdmc:/config/horizon-oc/config.ini";''',
'''constexpr const char* HOC_CONFIG_INI = "sdmc:/config/horizon-oc/config.ini";\nconstexpr const char* HOC_CONFIG_TMP = "sdmc:/config/horizon-oc/config.ini.wizard.tmp";\nconstexpr const char* HOC_CONFIG_BACKUP = "sdmc:/config/horizon-oc/config.ini.wizard.bak";'''))

repls.append((
'''bool g_rebootConfirm = false;\nbool g_bootPrompt = false;''',
'''bool g_rebootConfirm = false;\nbool g_autoPrepConfirm = false;\nstd::string g_autoPrepError;\nbool g_bootPrompt = false;'''))

for old, new in repls:
    if old not in s:
        raise SystemExit('anchor not found: ' + old[:120])
    s = s.replace(old, new, 1)

anchor = '''bool preparationFixedSettingsMatch(const HocMonConfig& c) {'''
if anchor not in s:
    raise SystemExit('preparationFixedSettingsMatch anchor not found')

insert = r'''bool verifyPersistentSettings(u32 mask);

bool writeAutomaticPreparationConfig(std::string& errorText) {
    errorText.clear();

    std::ifstream src(HOC_CONFIG_INI);
    if (!src) {
        errorText = "Could not open Horizon OC config.ini.";
        return false;
    }

    std::vector<std::string> lines;
    std::string line;
    while (std::getline(src, line)) lines.push_back(line);
    src.close();

    struct PrepValue { const char* key; std::string value; };
    const PrepValue values[] = {
        {"uncapped_clocks", "0"},
        {"kip_hp_mode", "0"},
        {"mariko_emc_max_clock", "1600000"},
        {"common_emc_mem_volt", std::to_string(STOCK_VDD2_UV)},
        {"mariko_emc_vddq_volt", std::to_string(g.vddqStartMv * 1000)},
        {"mariko_cpu_max_clock", "1963500"},
        {"mariko_cpu_low_vmin", std::to_string(STOCK_LOW_VMIN_MV)},
        {"mariko_cpu_high_vmin", std::to_string(STOCK_HIGH_VMIN_MV)},
        {"kip_table_conf", "3"},
        {"mariko_cpu_uv_low", std::to_string(STOCK_LOW_UV)},
        {"mariko_cpu_uv_high", std::to_string(STOCK_HIGH_UV)},
        {"mariko_cpu_boost_clock", "1785000"},
    };
    constexpr size_t valueCount = sizeof(values) / sizeof(values[0]);
    bool written[valueCount] = {};

    std::vector<std::string> out;
    out.reserve(lines.size() + valueCount + 3);
    bool inValues = false;
    bool sawValues = false;

    auto appendMissing = [&]() {
        for (size_t i = 0; i < valueCount; ++i) {
            if (!written[i]) {
                out.push_back(std::string(values[i].key) + "=" + values[i].value);
                written[i] = true;
            }
        }
    };

    for (const std::string& raw : lines) {
        const std::string trimmed = trimIni(raw);
        if (!trimmed.empty() && trimmed.front() == '[' && trimmed.back() == ']') {
            if (inValues) appendMissing();
            inValues = (trimmed == "[values]");
            if (inValues) sawValues = true;
            out.push_back(raw);
            continue;
        }

        if (inValues) {
            const size_t eq = trimmed.find('=');
            if (eq != std::string::npos) {
                const std::string key = trimIni(trimmed.substr(0, eq));
                bool replaced = false;
                for (size_t i = 0; i < valueCount; ++i) {
                    if (key == values[i].key) {
                        out.push_back(std::string(values[i].key) + "=" + values[i].value);
                        written[i] = true;
                        replaced = true;
                        break;
                    }
                }
                if (replaced) continue;
            }
        }
        out.push_back(raw);
    }

    if (inValues) appendMissing();
    if (!sawValues) {
        if (!out.empty() && !out.back().empty()) out.push_back("");
        out.push_back("[values]");
        appendMissing();
    }

    if (!copyFile(HOC_CONFIG_INI, HOC_CONFIG_BACKUP)) {
        errorText = "Could not create config.ini backup.";
        return false;
    }

    std::ofstream dst(HOC_CONFIG_TMP, std::ios::trunc);
    if (!dst) {
        errorText = "Could not create temporary config.ini.";
        return false;
    }
    for (const std::string& outLine : out) dst << outLine << "\n";
    dst.flush();
    const bool writeOk = bool(dst);
    dst.close();
    if (!writeOk) {
        remove(HOC_CONFIG_TMP);
        errorText = "Writing temporary config.ini failed.";
        return false;
    }

    remove(HOC_CONFIG_INI);
    if (rename(HOC_CONFIG_TMP, HOC_CONFIG_INI) != 0) {
        copyFile(HOC_CONFIG_BACKUP, HOC_CONFIG_INI);
        remove(HOC_CONFIG_TMP);
        errorText = "Replacing config.ini failed; backup restored.";
        return false;
    }

    fsdevCommitDevice("sdmc");
    return true;
}

void resetPreparationBaselineState() {
    g.lowUvGood = STOCK_LOW_UV;
    g.lowUvTest = STOCK_LOW_UV + 1;
    g.lowVminGood = STOCK_LOW_VMIN_MV;
    g.lowVminTest = STOCK_LOW_VMIN_MV - LOW_VMIN_STEP_MV;
    g.vddqGood = g.vddqStartMv;
    g.vddqTest = g.vddqStartMv - VDDQ_STEP_MV;
    g.vdd2GoodUv = STOCK_VDD2_UV;
    g.vdd2TestUv = STOCK_VDD2_UV - VDD2_STEP_UV;
    g.highUvGood = STOCK_HIGH_UV;
    g.highUvTest = STOCK_HIGH_UV + 1;
    g.recoveryNeeded = false;
    g.stageReadyAfterBoot = false;
    g.pendingConfigMask = Config_None;
}

bool applyAutomaticPreparation() {
    if (!writeAutomaticPreparationConfig(g_autoPrepError)) return false;
    if (!verifyPersistentSettings(Config_Prepare)) {
        copyFile(HOC_CONFIG_BACKUP, HOC_CONFIG_INI);
        fsdevCommitDevice("sdmc");
        g_autoPrepError = "Readback check failed; previous config restored.";
        return false;
    }
    resetPreparationBaselineState();
    g.pendingConfigMask = Config_Prepare;
    g.rebootPending = true;
    saveState();
    return true;
}

'''

s = s.replace(anchor, insert + anchor, 1)

old = '''void renderRebootConfirm() {'''
if old not in s:
    raise SystemExit('renderRebootConfirm anchor not found')
auto_ui = r'''void renderAutoPrepConfirm() {
    consoleClear();
    uiPrintf(1, "\x1b[36mBattery Wizard\x1b[0m");
    uiPrintf(2, "Step : Automatic Preparation");
    uiPrintf(3, "----------------------------------------");
    uiPrintf(5, "Set all Preparation values automatically?");
    uiPrintf(7, "The Wizard will update only the required");
    uiPrintf(8, "Preparation keys in Horizon OC config.ini.");
    uiPrintf(10, "VDDQ start : %d mV", g.vddqStartMv);
    uiPrintf(11, "Other Horizon OC values stay unchanged.");
    uiPrintf(13, "Backup: config.ini.wizard.bak");
    uiPrintf(15, "Values are read back before reboot.");
    uiPrintf(16, "If verification succeeds, reboot is automatic.");
    if (!g_autoPrepError.empty())
        uiPrintf(18, "\x1b[31m%s\x1b[0m", g_autoPrepError.c_str());
    uiPrintf(21, "A : Confirm - set values and reboot");
    uiPrintf(22, "B : Cancel");
    consoleUpdate(nullptr);
}

'''
s = s.replace(old, auto_ui + old, 1)

old = '''    if (g_configPrompt) { renderConfigPrompt(); return; }\n    if (g_rebootConfirm) { renderRebootConfirm(); return; }'''
new = '''    if (g_configPrompt) { renderConfigPrompt(); return; }\n    if (g_autoPrepConfirm) { renderAutoPrepConfirm(); return; }\n    if (g_rebootConfirm) { renderRebootConfirm(); return; }'''
if old not in s:
    raise SystemExit('render dispatcher anchor not found')
s = s.replace(old, new, 1)

old = '''    uiPrintf(29, "A : Check settings");\n    uiPrintf(30, "X : Use current settings as baseline");\n    uiPrintf(31, "B : Exit    - : Reset");'''
new = '''    uiPrintf(28, "A : Check settings");\n    uiPrintf(29, "X : Use current settings as baseline");\n    uiPrintf(30, "Y : Set values automatically + reboot");\n    uiPrintf(31, "B : Exit    - : Reset");'''
if old not in s:
    raise SystemExit('preparation footer anchor not found')
s = s.replace(old, new, 1)

old = '''        if (g_rebootConfirm) {\n            if (k & HidNpadButton_A) {'''
new = r'''        if (g_autoPrepConfirm) {
            if (k & HidNpadButton_A) {
                g_autoPrepError.clear();
                if (applyAutomaticPreparation()) {
                    g_autoPrepConfirm = false;
                    consoleClear();
                    uiPrintf(6, "\x1b[32mPreparation values written + verified.\x1b[0m");
                    uiPrintf(8, "Restarting console...");
                    consoleUpdate(nullptr);
                    svcSleepThread(400'000'000);

                    g_rebootError = appletRequestToReboot();
                    if (R_FAILED(g_rebootError)) {
                        saveState();
                        consoleClear();
                        uiPrintf(5, "\x1b[31mAutomatic restart failed.\x1b[0m");
                        uiPrintf(7, "Result : 0x%08X", g_rebootError);
                        uiPrintf(9, "Preparation values ARE already saved.");
                        uiPrintf(10, "Restart CFW manually, then reopen Wizard.");
                        uiPrintf(12, "B : Exit");
                        consoleUpdate(nullptr);
                        while (appletMainLoop()) {
                            padUpdate(&pad);
                            if (padGetButtonsDown(&pad) & HidNpadButton_B) break;
                            svcSleepThread(20'000'000);
                        }
                        break;
                    }
                }
                redraw = true;
            } else if (k & HidNpadButton_B) {
                g_autoPrepConfirm = false;
                g_autoPrepError.clear();
                redraw = true;
            }
            svcSleepThread(20'000'000);
            continue;
        }

        if (g_rebootConfirm) {
            if (k & HidNpadButton_A) {'''
if old not in s:
    raise SystemExit('reboot handler anchor not found')
s = s.replace(old, new, 1)

old = '''        } else if (g.stage == Stage::Preparation && (k & HidNpadButton_X)) {\n            if (captureCurrentSettingsBaseline()) g_rebootConfirm = true;\n            else g_configPrompt = true;\n            redraw = true;\n        } else if ((k & HidNpadButton_Plus) && g.stage != Stage::Preparation) {'''
new = '''        } else if (g.stage == Stage::Preparation && (k & HidNpadButton_Y)) {\n            g_autoPrepError.clear();\n            g_autoPrepConfirm = true;\n            redraw = true;\n        } else if (g.stage == Stage::Preparation && (k & HidNpadButton_X)) {\n            if (captureCurrentSettingsBaseline()) g_rebootConfirm = true;\n            else g_configPrompt = true;\n            redraw = true;\n        } else if ((k & HidNpadButton_Plus) && g.stage != Stage::Preparation) {'''
if old not in s:
    raise SystemExit('Preparation X input anchor not found')
s = s.replace(old, new, 1)

p.write_text(s)

mk = Path('Makefile')
ms = mk.read_text()
if 'APP_VERSION := 0.4.0-beta.27' not in ms:
    raise SystemExit('beta27 version anchor not found')
mk.write_text(ms.replace('APP_VERSION := 0.4.0-beta.27', 'APP_VERSION := 0.4.0-beta.28', 1))

u = Path('UPDATE.txt')
us = u.read_text()
us = us.replace('version=0.4.0-beta.27', 'version=0.4.0-beta.28')
us = us.replace('/v0.4.0-beta.27/', '/v0.4.0-beta.28/')
u.write_text(us)
