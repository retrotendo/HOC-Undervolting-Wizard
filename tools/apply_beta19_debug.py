from pathlib import Path
import re


def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit(f'pattern not found: {label}')
    return text.replace(old, new, 1)


def replace_function(text, signature, new_text):
    start = text.find(signature)
    if start < 0:
        raise SystemExit(f'function not found: {signature}')
    brace = text.find('{', start)
    depth = 0
    in_str = False
    esc = False
    i = brace
    while i < len(text):
        c = text[i]
        if esc:
            esc = False
        elif c == '\\' and in_str:
            esc = True
        elif c == '"':
            in_str = not in_str
        elif not in_str:
            if c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return text[:start] + new_text.rstrip() + '\n' + text[i+1:]
        i += 1
    raise SystemExit(f'closing brace not found: {signature}')

# Header --------------------------------------------------------------------
hp = Path('source/hoc_monitor.h')
h = hp.read_text()
h = replace_once(h,
'''typedef struct {\n    u8 dramId;\n    bool isDram8GB;\n    u32 consoleType;\n} HocMonHardware;\n''',
'''typedef struct {\n    u8 dramId;\n    bool isDram8GB;\n    u32 consoleType;\n} HocMonHardware;\n\ntypedef struct {\n    u32 apiVersion;\n    u8 raw400_411[12];\n    s32 consoleTypeAt408;\n    u8 idAt403;\n    u8 is8At404;\n    u8 idAt404;\n    u8 is8At405;\n    bool id403Known;\n    bool id404Known;\n} HocMonHardwareDebug;\n''', 'hardware debug struct')
h = replace_once(h,
'''/* Read DRAM identity from Horizon OC API-v2 current context. */\nResult hocmonGetHardware(HocMonHardware* out);\n''',
'''/* Read DRAM identity from Horizon OC API-v2 current context. */\nResult hocmonGetHardware(HocMonHardware* out);\n\n/* Raw context diagnostics for hardware-layout troubleshooting. */\nResult hocmonGetHardwareDebug(HocMonHardwareDebug* out);\n''', 'debug declaration')
hp.write_text(h)

# Monitor implementation ----------------------------------------------------
cp = Path('source/hoc_monitor.c')
c = cp.read_text()
insert = '''\nResult hocmonGetHardwareDebug(HocMonHardwareDebug* out)\n{\n    if (!out)\n        return 1;\n    memset(out, 0, sizeof(*out));\n\n    Service srv = {0};\n    u32 api = 0;\n    Result rc = hocmonOpen(&srv, &api);\n    if (R_FAILED(rc))\n        return rc;\n\n    out->apiVersion = api;\n    HocMonRawContext raw;\n    rc = hocmonReadRawContext(&srv, &raw);\n    serviceClose(&srv);\n    if (R_FAILED(rc))\n        return rc;\n\n    const u8* bytes = (const u8*)&raw;\n    memcpy(out->raw400_411, bytes + 400, sizeof(out->raw400_411));\n    memcpy(&out->consoleTypeAt408, bytes + 408, sizeof(out->consoleTypeAt408));\n    out->idAt403 = bytes[403];\n    out->is8At404 = bytes[404];\n    out->idAt404 = bytes[404];\n    out->is8At405 = bytes[405];\n    out->id403Known = hocmonIsKnownMarikoDramId(out->idAt403);\n    out->id404Known = hocmonIsKnownMarikoDramId(out->idAt404);\n    return 0;\n}\n\n'''
needle = 'Result hocmonGetHardware(HocMonHardware* out)\n'
idx = c.find(needle)
if idx < 0:
    raise SystemExit('hocmonGetHardware insertion point not found')
c = c[:idx] + insert + c[idx:]
cp.write_text(c)

# UI ------------------------------------------------------------------------
mp = Path('source/main.cpp')
s = mp.read_text()
s = replace_once(s,
'''Result g_hardwareReadRc = 0;\nHocMonHardware g_hardware{};\n''',
'''Result g_hardwareReadRc = 0;\nHocMonHardware g_hardware{};\nResult g_hardwareDebugRc = 0;\nHocMonHardwareDebug g_hardwareDebug{};\n''', 'debug globals')

s = replace_once(s,
'''    g_hardware = HocMonHardware{};\n    g_hardwareReadRc = hocmonGetHardware(&g_hardware);\n    if (R_FAILED(g_hardwareReadRc)) return false;\n''',
'''    g_hardware = HocMonHardware{};\n    g_hardwareDebug = HocMonHardwareDebug{};\n    g_hardwareReadRc = hocmonGetHardware(&g_hardware);\n    g_hardwareDebugRc = hocmonGetHardwareDebug(&g_hardwareDebug);\n    if (R_FAILED(g_hardwareReadRc)) return false;\n''', 'capture debug during detection')

s = replace_function(s, 'void renderHardwareDetection()', r'''void renderHardwareDetection() {
    title();
    if (g.ramDetected) {
        const RamProfile rp = ramProfileForId(g.dramId);
        uiPrintf(6, "\x1b[32mRAM detected\x1b[0m");
        uiPrintf(8, "Module     : %s", rp.name);
        uiPrintf(9, "DRAM ID    : %d", g.dramId);
        uiPrintf(11, "VDDQ start : %d mV", g.vddqStartMv);
        uiPrintf(14, "A : Continue to Preparation");
        uiPrintf(15, "B : Exit");
        return;
    }

    uiPrintf(5, "\x1b[31mRAM detection failed\x1b[0m");
    uiPrintf(6, "hoc:clk result : 0x%08X", g_hardwareReadRc);

    if (R_SUCCEEDED(g_hardwareDebugRc)) {
        uiPrintf(8,  "DEBUG - please photograph this screen");
        uiPrintf(9,  "HOC API : %u", g_hardwareDebug.apiVersion);
        uiPrintf(10, "Raw 400-405: %02X %02X %02X %02X %02X %02X",
                 g_hardwareDebug.raw400_411[0], g_hardwareDebug.raw400_411[1],
                 g_hardwareDebug.raw400_411[2], g_hardwareDebug.raw400_411[3],
                 g_hardwareDebug.raw400_411[4], g_hardwareDebug.raw400_411[5]);
        uiPrintf(11, "Raw 406-411: %02X %02X %02X %02X %02X %02X",
                 g_hardwareDebug.raw400_411[6], g_hardwareDebug.raw400_411[7],
                 g_hardwareDebug.raw400_411[8], g_hardwareDebug.raw400_411[9],
                 g_hardwareDebug.raw400_411[10], g_hardwareDebug.raw400_411[11]);
        uiPrintf(13, "console@408 : %d", g_hardwareDebug.consoleTypeAt408);
        uiPrintf(14, "ID@403:%u  8GB@404:%u  known:%s",
                 g_hardwareDebug.idAt403, g_hardwareDebug.is8At404,
                 g_hardwareDebug.id403Known ? "YES" : "NO");
        uiPrintf(15, "ID@404:%u  8GB@405:%u  known:%s",
                 g_hardwareDebug.idAt404, g_hardwareDebug.is8At405,
                 g_hardwareDebug.id404Known ? "YES" : "NO");
    } else {
        uiPrintf(8, "Debug read failed: 0x%08X", g_hardwareDebugRc);
    }

    uiPrintf(18, "A : Retry detection");
    uiPrintf(19, "B : Exit");
}''')
mp.write_text(s)

# Version / updater ---------------------------------------------------------
mkp = Path('Makefile')
mk = mkp.read_text().replace('APP_VERSION := 0.4.0-beta.18', 'APP_VERSION := 0.4.0-beta.19', 1)
mkp.write_text(mk)
Path('UPDATE.txt').write_text(
    'version=0.4.0-beta.19\n'
    'nro_url=https://github.com/retrotendo/HOC-Undervolting-Wizard/releases/download/v0.4.0-beta.19/HOC-Undervolting-Wizard.nro\n'
    'sha_url=https://github.com/retrotendo/HOC-Undervolting-Wizard/releases/download/v0.4.0-beta.19/HOC-Undervolting-Wizard.nro.sha256\n'
)
Path('RELEASE_NOTES_v0.4.0-beta.19.md').write_text('''# HOC Undervolting Wizard v0.4.0-beta.19\n\n## Hardware Detection Diagnostic Build\n\nBeta.19 adds an on-device diagnostic readout when RAM detection fails. The screen shows the HOC API version, raw HocClkContext bytes 400-411, the 32-bit console-type value at byte 408, and both known DRAM-ID layout candidates.\n\nThis build intentionally does not guess a RAM type. Please photograph the diagnostic screen so the exact runtime HOC layout can be identified.\n\nNo tuning, stress-test, updater, reboot, override, or automatic VMIN behavior changed from beta.18.\n''')
print('beta19 debug patch applied')
