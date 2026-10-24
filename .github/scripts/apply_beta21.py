from pathlib import Path
import re

p = Path('source/hoc_monitor.c')
s = p.read_text()
pat = re.compile(r'Result hocmonGetHardware\(HocMonHardware\* out\)\n\{.*?\n\}\n\nResult hocmonGetConfig\(', re.S)
new = r'''Result hocmonGetHardware(HocMonHardware* out)
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

    /* Horizon OC 2.6.0: dramID@400, isDram8GB@401, consoleType@404. */
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
s, n = pat.subn(new, s, count=1)
if n != 1:
    raise SystemExit(f'hocmonGetHardware replacement count={n}')
p.write_text(s)

mk = Path('Makefile')
ms = mk.read_text()
if 'APP_VERSION := 0.4.0-beta.20' not in ms:
    raise SystemExit('beta20 version anchor not found')
mk.write_text(ms.replace('APP_VERSION := 0.4.0-beta.20', 'APP_VERSION := 0.4.0-beta.21'))
