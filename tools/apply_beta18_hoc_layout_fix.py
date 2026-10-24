from pathlib import Path
import re

p = Path('source/hoc_monitor.c')
s = p.read_text()

old = '_Static_assert(offsetof(HocMonContextPrefix, dramID) == 403, "Unexpected Horizon OC API-v2 context layout");\n'
if old not in s:
    raise SystemExit('dramID static assert not found')
s = s.replace(old, '', 1)

needle = '''Result hocmonGetHardware(HocMonHardware* out)\n{\n    if (!out)\n        return 1;\n    memset(out, 0, sizeof(*out));\n\n    Service srv = {0};\n    u32 api = 0;\n    Result rc = hocmonOpen(&srv, &api);\n    if (R_FAILED(rc))\n        return rc;\n    if (api < HOCCLK_API_VERSION_REQUIRED) {\n        serviceClose(&srv);\n        return 2;\n    }\n\n    HocMonRawContext raw;\n    rc = hocmonReadRawContext(&srv, &raw);\n    serviceClose(&srv);\n    if (R_FAILED(rc))\n        return rc;\n\n    const HocMonContextPrefix* ctx = (const HocMonContextPrefix*)&raw;\n    /* Current HOC IDs are 0..34 and console types 0..3. Reject layout garbage. */\n    if (ctx->dramID > 34 || ctx->consoleType < 0 || ctx->consoleType > 3)\n        return 3;\n\n    out->dramId = ctx->dramID;\n    out->isDram8GB = ctx->isDram8GB;\n    out->consoleType = (u32)ctx->consoleType;\n    return 0;\n}\n'''

replacement = '''static bool hocmonIsKnownMarikoDramId(u8 id)\n{\n    switch (id) {\n        case 3: case 5: case 6:\n        case 8: case 9: case 10: case 11: case 12: case 13: case 14: case 15:\n        case 17: case 18: case 19: case 20: case 21: case 22: case 23: case 24:\n        case 25: case 26: case 27: case 28: case 29: case 30: case 31:\n        case 32: case 33: case 34:\n            return true;\n        default:\n            return false;\n    }\n}\n\nResult hocmonGetHardware(HocMonHardware* out)\n{\n    if (!out)\n        return 1;\n    memset(out, 0, sizeof(*out));\n\n    Service srv = {0};\n    u32 api = 0;\n    Result rc = hocmonOpen(&srv, &api);\n    if (R_FAILED(rc))\n        return rc;\n    if (api < HOCCLK_API_VERSION_REQUIRED) {\n        serviceClose(&srv);\n        return 2;\n    }\n\n    HocMonRawContext raw;\n    rc = hocmonReadRawContext(&srv, &raw);\n    serviceClose(&srv);\n    if (R_FAILED(rc))\n        return rc;\n\n    /*\n     * HOC 2.6.0 and current HOC use the same 0x500 context size but differ by\n     * one byte before maxDisplayFreq/dramID:\n     *\n     *   current main : [402]=maxDisplayFreq [403]=dramID [404]=isDram8GB\n     *   HOC 2.6.0   : [402]=isUsingRetroSuper [403]=maxDisplayFreq\n     *                  [404]=dramID [405]=isDram8GB\n     *\n     * consoleType remains 32-bit aligned at byte 408 in both layouts. Do not\n     * guess from maxDisplayFreq; validate both layouts against HOC's known\n     * Mariko DRAM IDs and the adjacent boolean instead.\n     */\n    const u8* bytes = (const u8*)&raw;\n    s32 consoleType = -1;\n    memcpy(&consoleType, bytes + 408, sizeof(consoleType));\n    if (consoleType < 0 || consoleType > 3)\n        return 3;\n\n    const u8 currentId = bytes[403];\n    const u8 currentIs8GB = bytes[404];\n    const bool currentValid =\n        hocmonIsKnownMarikoDramId(currentId) && currentIs8GB <= 1;\n\n    const u8 hoc260Id = bytes[404];\n    const u8 hoc260Is8GB = bytes[405];\n    const bool hoc260Valid =\n        hocmonIsKnownMarikoDramId(hoc260Id) && hoc260Is8GB <= 1;\n\n    /* Exactly one known layout must validate. Ambiguous/unknown future layouts\n       deliberately fail instead of selecting a RAM family by accident. */\n    if (currentValid == hoc260Valid)\n        return 3;\n\n    if (currentValid) {\n        out->dramId = currentId;\n        out->isDram8GB = currentIs8GB != 0;\n    } else {\n        out->dramId = hoc260Id;\n        out->isDram8GB = hoc260Is8GB != 0;\n    }\n    out->consoleType = (u32)consoleType;\n    return 0;\n}\n'''

if needle not in s:
    raise SystemExit('hocmonGetHardware block not found')
s = s.replace(needle, replacement, 1)
p.write_text(s)

mk = Path('Makefile').read_text()
mk = re.sub(r'APP_VERSION := .*', 'APP_VERSION := 0.4.0-beta.18', mk)
Path('Makefile').write_text(mk)

Path('UPDATE.txt').write_text(
    'version=0.4.0-beta.18\n'
    'nro_url=https://github.com/retrotendo/HOC-Undervolting-Wizard/releases/download/v0.4.0-beta.18/HOC-Undervolting-Wizard.nro\n'
    'sha_url=https://github.com/retrotendo/HOC-Undervolting-Wizard/releases/download/v0.4.0-beta.18/HOC-Undervolting-Wizard.nro.sha256\n'
)

Path('RELEASE_NOTES_v0.4.0-beta.18.md').write_text('''# HOC Undervolting Wizard v0.4.0-beta.18\n\n## Fix: RAM detection on Horizon OC 2.6.0\n\nHorizon OC 2.6.0 contains an additional `isUsingRetroSuper` byte in `HocClkContext` compared with current HOC main. That shifts `maxDisplayFreq`, `dramID`, and `isDram8GB` by one byte while keeping the full context size at 0x500.\n\nThe Wizard previously assumed the current-main layout and therefore read HOC 2.6.0 `maxDisplayFreq` as the DRAM ID, producing `hoc:clk result : 0x00000003` during Hardware Detection.\n\nBeta.18 now supports both known layouts:\n\n- current HOC main: DRAM ID at byte 403\n- Horizon OC 2.6.0: DRAM ID at byte 404\n\nBoth candidates are validated against the known Mariko DRAM-ID table and the adjacent `isDram8GB` boolean. Ambiguous or unknown future layouts are rejected rather than guessed.\n\nNo tuning logic, stress tests, automatic VMIN scan, or override behavior changed from beta.17.\n''')

print('beta18 HOC layout compatibility patch applied')
