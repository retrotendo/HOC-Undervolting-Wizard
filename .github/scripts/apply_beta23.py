from pathlib import Path
import re

# --- hoc_monitor.h ---
h = Path('source/hoc_monitor.h')
s = h.read_text()
anchor = '''typedef struct {
    bool uncappedClocks;
    bool hpMode;
    u32 ramMaxKHz;
    u32 vdd2Uv;
    u32 vddqUv;
    int lowUv;
    int highUv;
    int tableConf;
    int lowVminMv;
    int highVminMv;
    u32 cpuMaxKHz;
    u32 cpuBoostKHz;
} HocMonConfig;
'''
insert = anchor + '''\n#define HOCMON_CONFIG_DEBUG_VALUE_COUNT 256\ntypedef struct {\n    u32 apiVersion;\n    char version[64];\n    u64 values[HOCMON_CONFIG_DEBUG_VALUE_COUNT];\n} HocMonConfigDebug;\n'''
if anchor not in s:
    raise SystemExit('hoc_monitor.h config struct anchor not found')
s = s.replace(anchor, insert, 1)
anchor = '''/* Read the persistent Horizon OC/KIP values used by the Battery Wizard. */
Result hocmonGetConfig(HocMonConfig* out);
'''
insert = anchor + '''\n/* Raw hoc:clk config-list diagnostics. Read-only; used by debug builds. */\nResult hocmonGetConfigDebug(HocMonConfigDebug* out);\n'''
if anchor not in s:
    raise SystemExit('hoc_monitor.h declaration anchor not found')
s = s.replace(anchor, insert, 1)
h.write_text(s)

# --- hoc_monitor.c ---
c = Path('source/hoc_monitor.c')
s = c.read_text()
old = '#define HOCCLK_IPC_CMD_GET_API_VERSION 0\n#define HOCCLK_IPC_CMD_GET_CURRENT_CONTEXT 2\n'
new = '#define HOCCLK_IPC_CMD_GET_API_VERSION 0\n#define HOCCLK_IPC_CMD_GET_VERSION_STRING 1\n#define HOCCLK_IPC_CMD_GET_CURRENT_CONTEXT 2\n'
if old not in s:
    raise SystemExit('hoc_monitor.c command anchor not found')
s = s.replace(old, new, 1)

append = r'''

Result hocmonGetConfigDebug(HocMonConfigDebug* out)
{
    if (!out)
        return 1;
    memset(out, 0, sizeof(*out));

    Service srv = {0};
    u32 api = 0;
    Result rc = hocmonOpen(&srv, &api);
    if (R_FAILED(rc))
        return rc;

    out->apiVersion = api;
    rc = serviceDispatch(&srv, HOCCLK_IPC_CMD_GET_VERSION_STRING,
        .buffer_attrs = { SfBufferAttr_HipcAutoSelect | SfBufferAttr_Out },
        .buffers = {{ out->version, sizeof(out->version) }},
    );
    if (R_FAILED(rc)) {
        memset(out->version, 0, sizeof(out->version));
        strncpy(out->version, "<version read failed>", sizeof(out->version) - 1);
    }

    rc = serviceDispatch(&srv, HOCCLK_IPC_CMD_GET_CONFIG_VALUES,
        .buffer_attrs = { SfBufferAttr_HipcAutoSelect | SfBufferAttr_Out },
        .buffers = {{ out->values, sizeof(out->values) }},
    );
    serviceClose(&srv);
    return rc;
}
'''
if 'Result hocmonGetConfigDebug(' in s:
    raise SystemExit('hocmonGetConfigDebug already exists')
s = s.rstrip() + append + '\n'
c.write_text(s)

# --- main.cpp ---
m = Path('source/main.cpp')
s = m.read_text()
old = '''bool g_configPrompt = false;
bool g_rebootConfirm = false;
bool g_bootPrompt = false;
ConfigCheckState g_configCheck;
'''
new = '''bool g_configPrompt = false;
bool g_configDebugScreen = false;
int g_configDebugPage = 0;
HocMonConfigDebug g_configDebug{};
Result g_configDebugRc = 0;
bool g_rebootConfirm = false;
bool g_bootPrompt = false;
ConfigCheckState g_configCheck;
'''
if old not in s:
    raise SystemExit('main globals anchor not found')
s = s.replace(old, new, 1)

anchor = '''void renderConfigPrompt() {
'''
debug_funcs = r'''void openConfigDebug() {
    g_configDebug = HocMonConfigDebug{};
    g_configDebugRc = hocmonGetConfigDebug(&g_configDebug);
    g_configDebugPage = 0;
    g_configDebugScreen = true;
}

void renderConfigDebug() {
    consoleClear();
    uiPrintf(1, "\x1b[36mBattery Wizard - CONFIG DEBUG\x1b[0m");
    uiPrintf(2, "HOC : %s", g_configDebug.version[0] ? g_configDebug.version : "<unknown>");
    uiPrintf(3, "API : %u", g_configDebug.apiVersion);
    uiPrintf(4, "----------------------------------------");

    if (R_FAILED(g_configDebugRc)) {
        uiPrintf(7, "\x1b[31mRaw config read failed\x1b[0m");
        uiPrintf(8, "Result : 0x%08X", g_configDebugRc);
        uiPrintf(11, "B : Back");
        consoleUpdate(nullptr);
        return;
    }

    constexpr int perPage = 24;
    constexpr int rows = 12;
    constexpr int pages = 4; // indexes 0..95 cover every Battery Wizard field
    const int base = g_configDebugPage * perPage;
    uiPrintf(5, "Raw GetConfigValues  Page %d / %d", g_configDebugPage + 1, pages);
    uiPrintf(6, " index:value               index:value");
    for (int r = 0; r < rows; ++r) {
        const int a = base + r;
        const int b = base + rows + r;
        uiPrintf(7 + r, " %3d:%-12llu       %3d:%llu",
                 a, (unsigned long long)g_configDebug.values[a],
                 b, (unsigned long long)g_configDebug.values[b]);
    }
    uiPrintf(21, "A : Next page    X : Previous page");
    uiPrintf(22, "B : Back to Preparation check");
    consoleUpdate(nullptr);
}

'''
if anchor not in s:
    raise SystemExit('renderConfigPrompt anchor not found')
s = s.replace(anchor, debug_funcs + anchor, 1)

old = '''    uiPrintf(3, "----------------------------------------");
    if (!g_configCheck.readOk) {
'''
new = '''    uiPrintf(3, "----------------------------------------");
    if (g.stage == Stage::Preparation)
        uiPrintf(4, "\x1b[33mY : RAW CONFIG DEBUG\x1b[0m");
    if (!g_configCheck.readOk) {
'''
if old not in s:
    raise SystemExit('renderConfigPrompt header anchor not found')
s = s.replace(old, new, 1)

old = '''    if (g_bootPrompt) { renderBootPrompt(); return; }
    if (g_vminScanScreen) { renderVminScanScreen(); return; }
    if (g_interruptedPrompt) { renderInterruptedPrompt(); return; }
    if (g_configPrompt) { renderConfigPrompt(); return; }
'''
new = '''    if (g_bootPrompt) { renderBootPrompt(); return; }
    if (g_vminScanScreen) { renderVminScanScreen(); return; }
    if (g_interruptedPrompt) { renderInterruptedPrompt(); return; }
    if (g_configDebugScreen) { renderConfigDebug(); return; }
    if (g_configPrompt) { renderConfigPrompt(); return; }
'''
if old not in s:
    raise SystemExit('render dispatch anchor not found')
s = s.replace(old, new, 1)

old = '''        if (g_configPrompt) {
            if (k & HidNpadButton_A) {
'''
new = '''        if (g_configDebugScreen) {
            if (k & HidNpadButton_A) {
                g_configDebugPage = (g_configDebugPage + 1) % 4;
                redraw = true;
            } else if (k & HidNpadButton_X) {
                g_configDebugPage = (g_configDebugPage + 3) % 4;
                redraw = true;
            } else if (k & HidNpadButton_B) {
                g_configDebugScreen = false;
                redraw = true;
            }
            svcSleepThread(20'000'000);
            continue;
        }

        if (g_configPrompt) {
            if ((k & HidNpadButton_Y) && g.stage == Stage::Preparation) {
                openConfigDebug();
                redraw = true;
            } else if (k & HidNpadButton_A) {
'''
if old not in s:
    raise SystemExit('config prompt handler anchor not found')
s = s.replace(old, new, 1)
m.write_text(s)

# --- version/update metadata ---
mk = Path('Makefile')
ms = mk.read_text()
if 'APP_VERSION := 0.4.0-beta.22' not in ms:
    raise SystemExit('beta22 Makefile version anchor not found')
mk.write_text(ms.replace('APP_VERSION := 0.4.0-beta.22', 'APP_VERSION := 0.4.0-beta.23'))

u = Path('UPDATE.txt')
us = u.read_text()
us = us.replace('version=0.4.0-beta.22', 'version=0.4.0-beta.23')
us = us.replace('/v0.4.0-beta.22/', '/v0.4.0-beta.23/')
u.write_text(us)
