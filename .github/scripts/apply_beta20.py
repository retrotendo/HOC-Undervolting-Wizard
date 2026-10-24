from pathlib import Path
import re

h = Path('source/hoc_monitor.h')
s = h.read_text()
old = '''typedef struct {
    u32 apiVersion;
    u8 raw400_411[12];
    s32 consoleTypeAt408;
    u8 idAt403;
    u8 is8At404;
    u8 idAt404;
    u8 is8At405;
    bool id403Known;
    bool id404Known;
} HocMonHardwareDebug;'''
new = '''typedef struct {
    u32 apiVersion;
    u8 raw396_411[16];
    s32 consoleTypeAt404;
    s32 consoleTypeAt408;
    u8 idAt400;
    u8 is8At401;
    u8 idAt403;
    u8 is8At404;
    bool id400Known;
    bool id403Known;
} HocMonHardwareDebug;'''
if old not in s:
    raise SystemExit('hoc_monitor.h debug struct anchor not found')
h.write_text(s.replace(old, new))

c = Path('source/hoc_monitor.c')
s = c.read_text()

debug_pat = re.compile(r'Result hocmonGetHardwareDebug\(HocMonHardwareDebug\* out\)\n\{.*?\n\}\n\nResult hocmonGetHardware\(', re.S)
debug_new = r'''Result hocmonGetHardwareDebug(HocMonHardwareDebug* out)
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
    HocMonRawContext raw;
    rc = hocmonReadRawContext(&srv, &raw);
    serviceClose(&srv);
    if (R_FAILED(rc))
        return rc;

    const u8* bytes = (const u8*)&raw;
    memcpy(out->raw396_411, bytes + 396, sizeof(out->raw396_411));
    memcpy(&out->consoleTypeAt404, bytes + 404, sizeof(out->consoleTypeAt404));
    memcpy(&out->consoleTypeAt408, bytes + 408, sizeof(out->consoleTypeAt408));
    out->idAt400 = bytes[400];
    out->is8At401 = bytes[401];
    out->idAt403 = bytes[403];
    out->is8At404 = bytes[404];
    out->id400Known = hocmonIsKnownMarikoDramId(out->idAt400);
    out->id403Known = hocmonIsKnownMarikoDramId(out->idAt403);
    return 0;
}

Result hocmonGetHardware('''
s, n = debug_pat.subn(debug_new, s, count=1)
if n != 1:
    raise SystemExit(f'debug function replacement count={n}')

hw_pat = re.compile(r'Result hocmonGetHardware\(HocMonHardware\* out\)\n\{.*?\n\}\n\nResult hocmonGetConfig\(', re.S)
hw_new = r'''Result hocmonGetHardware(HocMonHardware* out)
{
    if (!out)
        return 1;
    memset(out, 0, sizeof(*out));

    Service srv = {0};
    u32 api = 0;
    Result rc = hocmonOpen(&srv, &api);
    if (R_FAILED(rc))
        return rc;
    if (api < HOCCLK_API_VERSION_REQUIRED) {
        serviceClose(&srv);
        return 2;
    }

    HocMonRawContext raw;
    rc = hocmonReadRawContext(&srv, &raw);
    serviceClose(&srv);
    if (R_FAILED(rc))
        return rc;

    const u8* bytes = (const u8*)&raw;

    /* HOC 2.6.0 tag: dramID@400, isDram8GB@401, consoleType@404. */
    s32 console260 = -1;
    memcpy(&console260, bytes + 404, sizeof(console260));
    const u8 id260 = bytes[400];
    const u8 is8_260 = bytes[401];
    const bool valid260 =
        hocmonIsKnownMarikoDramId(id260) && is8_260 <= 1 &&
        console260 >= 0 && console260 <= 3;

    /* Current HOC main: dramID@403, isDram8GB@404, consoleType@408. */
    s32 consoleCurrent = -1;
    memcpy(&consoleCurrent, bytes + 408, sizeof(consoleCurrent));
    const u8 idCurrent = bytes[403];
    const u8 is8_current = bytes[404];
    const bool validCurrent =
        hocmonIsKnownMarikoDramId(idCurrent) && is8_current <= 1 &&
        consoleCurrent >= 0 && consoleCurrent <= 3;

    if (valid260 == validCurrent)
        return 3;

    if (valid260) {
        out->dramId = id260;
        out->isDram8GB = is8_260 != 0;
        out->consoleType = (u32)console260;
    } else {
        out->dramId = idCurrent;
        out->isDram8GB = is8_current != 0;
        out->consoleType = (u32)consoleCurrent;
    }
    return 0;
}

Result hocmonGetConfig('''
s, n = hw_pat.subn(hw_new, s, count=1)
if n != 1:
    raise SystemExit(f'hardware function replacement count={n}')
c.write_text(s)

m = Path('source/main.cpp')
s = m.read_text()
old = '''        uiPrintf(10, "Raw 400-405: %02X %02X %02X %02X %02X %02X",
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
                 g_hardwareDebug.id404Known ? "YES" : "NO");'''
new = '''        uiPrintf(10, "Raw 396-403: %02X %02X %02X %02X %02X %02X %02X %02X",
                 g_hardwareDebug.raw396_411[0], g_hardwareDebug.raw396_411[1],
                 g_hardwareDebug.raw396_411[2], g_hardwareDebug.raw396_411[3],
                 g_hardwareDebug.raw396_411[4], g_hardwareDebug.raw396_411[5],
                 g_hardwareDebug.raw396_411[6], g_hardwareDebug.raw396_411[7]);
        uiPrintf(11, "Raw 404-411: %02X %02X %02X %02X %02X %02X %02X %02X",
                 g_hardwareDebug.raw396_411[8], g_hardwareDebug.raw396_411[9],
                 g_hardwareDebug.raw396_411[10], g_hardwareDebug.raw396_411[11],
                 g_hardwareDebug.raw396_411[12], g_hardwareDebug.raw396_411[13],
                 g_hardwareDebug.raw396_411[14], g_hardwareDebug.raw396_411[15]);
        uiPrintf(13, "console@404:%d  console@408:%d",
                 g_hardwareDebug.consoleTypeAt404, g_hardwareDebug.consoleTypeAt408);
        uiPrintf(14, "2.6.0  ID@400:%u  8GB@401:%u  known:%s",
                 g_hardwareDebug.idAt400, g_hardwareDebug.is8At401,
                 g_hardwareDebug.id400Known ? "YES" : "NO");
        uiPrintf(15, "current ID@403:%u 8GB@404:%u known:%s",
                 g_hardwareDebug.idAt403, g_hardwareDebug.is8At404,
                 g_hardwareDebug.id403Known ? "YES" : "NO");'''
if old not in s:
    raise SystemExit('main.cpp debug display anchor not found')
m.write_text(s.replace(old, new))

mk = Path('Makefile')
s = mk.read_text()
if 'APP_VERSION := 0.4.0-beta.19' not in s:
    raise SystemExit('beta19 Makefile version anchor not found')
mk.write_text(s.replace('APP_VERSION := 0.4.0-beta.19', 'APP_VERSION := 0.4.0-beta.20'))
