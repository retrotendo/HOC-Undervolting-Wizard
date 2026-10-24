from pathlib import Path
import re

p = Path('source/main.cpp')
s = p.read_text()

# Add config path constant.
anchor = 'constexpr const char* LEGACY_STATE = "sdmc:/switch/HOC-Battery-Wizard/state.ini";\n'
insert = anchor + 'constexpr const char* HOC_CONFIG_INI = "sdmc:/config/horizon-oc/config.ini";\n'
if anchor not in s:
    raise SystemExit('config path anchor not found')
s = s.replace(anchor, insert, 1)

# Add parser before configMatchesCurrent.
anchor = 'bool configMatchesCurrent(u32 mask, const HocMonConfig& c) {\n'
parser = r'''std::string trimIni(const std::string& in) {
    const size_t first = in.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return {};
    const size_t last = in.find_last_not_of(" \t\r\n");
    return in.substr(first, last - first + 1);
}

bool readHocConfigIni(HocMonConfig& out) {
    out = HocMonConfig{};
    std::ifstream f(HOC_CONFIG_INI);
    if (!f) return false;

    bool inValues = false;
    bool sawValuesSection = false;
    std::string line;
    while (std::getline(f, line)) {
        line = trimIni(line);
        if (line.empty() || line[0] == ';' || line[0] == '#') continue;

        if (line.front() == '[' && line.back() == ']') {
            inValues = (line == "[values]");
            if (inValues) sawValuesSection = true;
            continue;
        }
        if (!inValues) continue;

        const size_t eq = line.find('=');
        if (eq == std::string::npos) continue;
        const std::string key = trimIni(line.substr(0, eq));
        const std::string valueText = trimIni(line.substr(eq + 1));
        if (key.empty() || valueText.empty()) continue;

        char* end = nullptr;
        const unsigned long long value = std::strtoull(valueText.c_str(), &end, 0);
        if (end == valueText.c_str()) continue;

        if (key == "uncapped_clocks") out.uncappedClocks = (value != 0);
        else if (key == "kip_hp_mode") out.hpMode = (value != 0);
        else if (key == "mariko_emc_max_clock") out.ramMaxKHz = (u32)value;
        else if (key == "common_emc_mem_volt") out.vdd2Uv = (u32)value;
        else if (key == "mariko_emc_vddq_volt") out.vddqUv = (u32)value;
        else if (key == "mariko_cpu_uv_low") out.lowUv = (int)value;
        else if (key == "mariko_cpu_uv_high") out.highUv = (int)value;
        else if (key == "kip_table_conf") out.tableConf = (int)value;
        else if (key == "mariko_cpu_low_vmin") out.lowVminMv = (int)value;
        else if (key == "mariko_cpu_high_vmin") out.highVminMv = (int)value;
        else if (key == "mariko_cpu_max_clock") out.cpuMaxKHz = (u32)value;
        else if (key == "mariko_cpu_boost_clock") out.cpuBoostKHz = (u32)value;
    }

    return sawValuesSection;
}

bool configMatchesCurrent(u32 mask, const HocMonConfig& c) {
'''
if anchor not in s:
    raise SystemExit('configMatchesCurrent anchor not found')
s = s.replace(anchor, parser, 1)

# Replace IPC config read with config.ini read for every persistent wizard setting.
old = '''bool verifyPersistentSettings(u32 mask) {
    g_configCheck = ConfigCheckState{};
    g_configCheck.mask = mask;
    g_configCheck.rc = hocmonGetConfig(&g_configCheck.current);
    g_configCheck.readOk = R_SUCCEEDED(g_configCheck.rc);
    return g_configCheck.readOk && configMatchesCurrent(mask, g_configCheck.current);
}'''
new = '''bool verifyPersistentSettings(u32 mask) {
    g_configCheck = ConfigCheckState{};
    g_configCheck.mask = mask;
    g_configCheck.readOk = readHocConfigIni(g_configCheck.current);
    g_configCheck.rc = g_configCheck.readOk ? 0 : 0xF024;
    return g_configCheck.readOk && configMatchesCurrent(mask, g_configCheck.current);
}'''
if old not in s:
    raise SystemExit('verifyPersistentSettings anchor not found')
s = s.replace(old, new, 1)

# Make the read error clear and keep raw IPC debug available as fallback diagnostics.
s = s.replace('uiPrintf(5, "Could not read Horizon OC settings");',
              'uiPrintf(5, "Could not read Horizon OC config.ini");', 1)

p.write_text(s)

mk = Path('Makefile')
ms = mk.read_text()
if 'APP_VERSION := 0.4.0-beta.23' not in ms:
    raise SystemExit('beta23 Makefile version anchor not found')
mk.write_text(ms.replace('APP_VERSION := 0.4.0-beta.23', 'APP_VERSION := 0.4.0-beta.24', 1))

u = Path('UPDATE.txt')
us = u.read_text()
us = us.replace('version=0.4.0-beta.23', 'version=0.4.0-beta.24')
us = us.replace('/v0.4.0-beta.23/', '/v0.4.0-beta.24/')
u.write_text(us)
