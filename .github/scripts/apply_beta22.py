from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

old = '''struct RamProfile {
    const char* name;
    int vddqStartMv;
    bool known;
};

RamProfile ramProfileForId(int id) {
    switch (id) {
        case 3: case 5: case 6: return {"NEE 4GB", 640, true};
        case 8: case 12: return {"AM-MGCJ 4GB", 640, true};
        case 9: case 13: return {"AM-MGCJ 8GB", 640, true};
        case 10: case 14: return {"NME 4GB", 640, true};
        case 11: case 15: return {"WT:E 4GB", 600, true};
        case 17: case 19: case 24: return {"AA-MGCL 4GB", 640, true};
        case 18: case 23: case 28: return {"AA-MGCL 8GB", 640, true};
        case 20: case 21: case 22: return {"AB-MGCL 4GB", 640, true};
        case 25: case 26: case 27: return {"WT:F 4GB", 600, true};
        case 29: case 30: case 31: return {"x267 4GB", 640, true};
        case 32: case 33: case 34: return {"WT:B 4GB", 600, true};
        default: return {"Unknown", STOCK_VDDQ_MV, false};
    }
}'''
new = '''struct RamProfile {
    const char* name;
    int vddqStartMv;
    const char* ocRange;
    bool known;
};

RamProfile ramProfileForId(int id) {
    switch (id) {
        case 3: case 5: case 6: return {"NEE 4GB", 640, "3100-3300 MHz", true};
        case 8: case 12: return {"AM-MGCJ 4GB", 640, "2633-2933 MHz", true};
        case 9: case 13: return {"AM-MGCJ 8GB", 640, "2633-2933 MHz", true};
        case 10: case 14: return {"NME 4GB", 640, "2300-2766 MHz", true};
        case 11: case 15: return {"WT:E 4GB", 600, "2500?-3033 MHz", true};
        case 17: case 19: case 24: return {"AA-MGCL 4GB", 640, "2766-3100 MHz", true};
        case 18: case 23: case 28: return {"AA-MGCL 8GB", 640, "2766-3100 MHz", true};
        case 20: case 21: case 22: return {"AB-MGCL 4GB", 640, "2500-2766 MHz", true};
        case 25: case 26: case 27: return {"WT:F 4GB", 600, "2633-2800 MHz", true};
        case 29: case 30: case 31: return {"x267 4GB", 640, "3100-3300 MHz", true};
        case 32: case 33: case 34: return {"WT:B 4GB", 600, "3066-3200 MHz", true};
        default: return {"Unknown", STOCK_VDDQ_MV, "Unknown", false};
    }
}'''
if old not in s:
    raise SystemExit('RamProfile anchor not found')
s = s.replace(old, new)

old = '''        uiPrintf(8, "Module     : %s", rp.name);
        uiPrintf(9, "DRAM ID    : %d", g.dramId);
        uiPrintf(11, "VDDQ start : %d mV", g.vddqStartMv);
        uiPrintf(14, "A : Continue to Preparation");
        uiPrintf(15, "B : Exit");'''
new = '''        uiPrintf(8, "Module     : %s", rp.name);
        uiPrintf(9, "DRAM ID    : %d", g.dramId);
        uiPrintf(11, "VDDQ start : %d mV", g.vddqStartMv);
        uiPrintf(12, "OC range   : %s", rp.ocRange);
        uiPrintf(13, "             Guide estimate - silicon varies");
        uiPrintf(16, "A : Continue to Preparation");
        uiPrintf(17, "B : Exit");'''
if old not in s:
    raise SystemExit('hardware screen anchor not found')
s = s.replace(old, new)
p.write_text(s)

mk = Path('Makefile')
ms = mk.read_text()
if 'APP_VERSION := 0.4.0-beta.21' not in ms:
    raise SystemExit('beta21 version anchor not found')
mk.write_text(ms.replace('APP_VERSION := 0.4.0-beta.21', 'APP_VERSION := 0.4.0-beta.22'))

u = Path('UPDATE.txt')
us = u.read_text()
us = us.replace('version=0.4.0-beta.21', 'version=0.4.0-beta.22')
us = us.replace('/v0.4.0-beta.21/', '/v0.4.0-beta.22/')
u.write_text(us)
