from pathlib import Path
import re


def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit(f"missing anchor: {label}")
    return text.replace(old, new, 1)

# hoc_monitor.h -------------------------------------------------------------
p = Path("source/hoc_monitor.h")
s = p.read_text()
if "hocmonApplyPreparation251" not in s:
    s = replace_once(
        s,
        "/* Read the persistent Horizon OC/KIP values used by the Battery Wizard. */\nResult hocmonGetConfig(HocMonConfig* out);\n",
        "/* Read the persistent Horizon OC/KIP values used by the Battery Wizard. */\nResult hocmonGetConfig(HocMonConfig* out);\n\n/*\n * Horizon OC 2.5.1 only: apply the Wizard Preparation values through HOC's\n * own SetConfigValues IPC and persist them with SetKipData (Save KIP).\n * Returns a non-zero Result when the running HOC layout/version is unsupported.\n */\nResult hocmonApplyPreparation251(const HocMonConfig* desired);\n",
        "hoc_monitor.h declaration",
    )
    p.write_text(s)

# hoc_monitor.c -------------------------------------------------------------
p = Path("source/hoc_monitor.c")
s = p.read_text()
if "HOCCLK_IPC_CMD_SET_CONFIG_VALUES" not in s:
    s = replace_once(
        s,
        "#define HOCCLK_IPC_CMD_GET_CONFIG_VALUES 9\n",
        "#define HOCCLK_IPC_CMD_GET_CONFIG_VALUES 9\n#define HOCCLK_IPC_CMD_SET_CONFIG_VALUES 10\n#define HOCCLK_IPC_CMD_SET_KIP_DATA 12\n",
        "IPC command constants",
    )

if "CFG251_KIP_VERSION" not in s:
    marker = "/* Oversized read-only buffer. The HOC service only requires >= its current list size. */\n"
    enum_text = r'''/* Exact HocClkConfigValue indexes from Horizon OC tag 2.5.1. */
enum {
    CFG251_UNCAPPED_CLOCKS = 5,
    CFG251_KIP_VERSION = 34,
    CFG251_HP_MODE = 35,
    CFG251_VDD2_UV = 36,
    CFG251_RAM_MAX_KHZ = 39,
    CFG251_VDDQ_UV = 40,
    CFG251_CPU_LOW_UV = 72,
    CFG251_CPU_HIGH_UV = 73,
    CFG251_CPU_TABLE = 74,
    CFG251_CPU_LOW_VMIN_MV = 75,
    CFG251_CPU_HIGH_VMIN_MV = 76,
    CFG251_CPU_MAX_KHZ = 78,
    CFG251_CPU_BOOST_KHZ = 80,
};

'''
    s = replace_once(s, marker, enum_text + marker, "2.5.1 config indexes")

if "Result hocmonApplyPreparation251" not in s:
    anchor = "Result hocmonGetConfigDebug(HocMonConfigDebug* out)\n"
    fn = r'''Result hocmonApplyPreparation251(const HocMonConfig* desired)
{
    if (!desired)
        return 1;

    Service srv = {0};
    u32 api = 0;
    Result rc = hocmonOpen(&srv, &api);
    if (R_FAILED(rc))
        return rc;
    if (api < HOCCLK_API_VERSION_REQUIRED) {
        serviceClose(&srv);
        return 2;
    }

    /* Start from HOC's complete live config list so unrelated settings remain untouched. */
    HocMonRawConfig cfg;
    memset(&cfg, 0, sizeof(cfg));
    rc = serviceDispatch(&srv, HOCCLK_IPC_CMD_GET_CONFIG_VALUES,
        .buffer_attrs = { SfBufferAttr_HipcAutoSelect | SfBufferAttr_Out },
        .buffers = {{ &cfg, sizeof(cfg) }},
    );
    if (R_FAILED(rc)) {
        serviceClose(&srv);
        return rc;
    }

    /* Never write version-dependent indexes unless the running KIP is exactly 2.5.1. */
    if ((u32)cfg.values[CFG251_KIP_VERSION] != 251U) {
        serviceClose(&srv);
        return 4;
    }

    cfg.values[CFG251_UNCAPPED_CLOCKS] = desired->uncappedClocks ? 1U : 0U;
    cfg.values[CFG251_HP_MODE] = desired->hpMode ? 1U : 0U;
    cfg.values[CFG251_VDD2_UV] = desired->vdd2Uv;
    cfg.values[CFG251_RAM_MAX_KHZ] = desired->ramMaxKHz;
    cfg.values[CFG251_VDDQ_UV] = desired->vddqUv;
    cfg.values[CFG251_CPU_LOW_UV] = (u64)desired->lowUv;
    cfg.values[CFG251_CPU_HIGH_UV] = (u64)desired->highUv;
    cfg.values[CFG251_CPU_TABLE] = (u64)desired->tableConf;
    cfg.values[CFG251_CPU_LOW_VMIN_MV] = (u64)desired->lowVminMv;
    cfg.values[CFG251_CPU_HIGH_VMIN_MV] = (u64)desired->highVminMv;
    cfg.values[CFG251_CPU_MAX_KHZ] = desired->cpuMaxKHz;
    cfg.values[CFG251_CPU_BOOST_KHZ] = desired->cpuBoostKHz;

    /* This is the same public IPC path used by the HOC overlay controls. */
    rc = serviceDispatch(&srv, HOCCLK_IPC_CMD_SET_CONFIG_VALUES,
        .buffer_attrs = { SfBufferAttr_HipcAutoSelect | SfBufferAttr_In },
        .buffers = {{ &cfg, sizeof(cfg) }},
    );
    if (R_SUCCEEDED(rc)) {
        /* Equivalent to Horizon OC's Save KIP action. */
        const u32 dummy = 0;
        rc = serviceDispatchIn(&srv, HOCCLK_IPC_CMD_SET_KIP_DATA, dummy);
    }

    serviceClose(&srv);
    return rc;
}

'''
    s = replace_once(s, anchor, fn + anchor, "apply preparation function")

p.write_text(s)

# main.cpp -----------------------------------------------------------------
p = Path("source/main.cpp")
s = p.read_text()

# Replace automatic Preparation implementation with HOC IPC + Save KIP.
pattern = re.compile(r"bool applyAutomaticPreparation\(\) \{.*?\n\}\n\nbool preparationFixedSettingsMatch", re.S)
if "hocmonApplyPreparation251" not in s:
    m = pattern.search(s)
    if not m:
        raise SystemExit("missing anchor: applyAutomaticPreparation")
    new_fn = r'''bool applyAutomaticPreparation() {
    HocMonConfig desired{};
    desired.uncappedClocks = false;
    desired.hpMode = false;
    desired.ramMaxKHz = 1600000U;
    desired.vdd2Uv = (u32)STOCK_VDD2_UV;
    desired.vddqUv = (u32)g.vddqStartMv * 1000U;
    desired.lowUv = STOCK_LOW_UV;
    desired.highUv = STOCK_HIGH_UV;
    desired.tableConf = 3;
    desired.lowVminMv = STOCK_LOW_VMIN_MV;
    desired.highVminMv = STOCK_HIGH_VMIN_MV;
    desired.cpuMaxKHz = 1963500U;
    desired.cpuBoostKHz = 1785000U;

    const Result rc = hocmonApplyPreparation251(&desired);
    if (R_FAILED(rc)) {
        if (rc == 4)
            g_autoPrepError = "Automatic setup currently supports Horizon OC 2.5.1 only.";
        else {
            char msg[96];
            std::snprintf(msg, sizeof(msg), "Horizon OC Save KIP failed: 0x%08X", rc);
            g_autoPrepError = msg;
        }
        return false;
    }

    // HOC's SetConfigValues updates config.ini and live config; SetKipData persists
    // the KIP. Read the named INI keys back before allowing a reboot.
    svcSleepThread(150'000'000);
    if (!verifyPersistentSettings(Config_Prepare)) {
        g_autoPrepError = "Horizon OC readback did not match the requested Preparation values.";
        return false;
    }

    resetPreparationBaselineState();
    g.pendingConfigMask = Config_Prepare;
    g.rebootPending = true;
    saveState();
    return true;
}

bool preparationFixedSettingsMatch'''
    s = s[:m.start()] + new_fn + s[m.end():]

# Add a dedicated no-reboot continuation for an already-active baseline.
if "continueFromPreparationBaseline" not in s:
    anchor = "\n\nbool configMatchesCurrent(u32 mask, const HocMonConfig& c) {"
    helper = r'''

void continueFromPreparationBaseline() {
    // Nothing was changed: these values are already the user's active baseline.
    // Do not perform a fake Preparation reboot. Move directly to the first new
    // Low UV candidate, which will get its own normal set -> reboot -> 1 min test.
    g.rebootPending = false;
    g.pendingConfigMask = Config_None;
    if (g.lowUvGood >= LOW_UV_MAX) {
        g.stage = Stage::LowUvLong;
        g.stageReadyAfterBoot = true;
    } else {
        g.stage = Stage::LowUvQuick;
        g.lowUvTest = g.lowUvGood + 1;
        g.stageReadyAfterBoot = false;
    }
    saveState();
}
'''
    s = replace_once(s, anchor, helper + anchor, "baseline continuation helper")

# Preparation NOT READY X path: capture and continue, no reboot confirmation.
s = replace_once(
    s,
    """            if ((k & HidNpadButton_X) && g.stage == Stage::Preparation) {\n                if (captureCurrentSettingsBaseline()) {\n                    g_configPrompt = false;\n                    g_rebootConfirm = true;\n                }\n                redraw = true;\n""",
    """            if ((k & HidNpadButton_X) && g.stage == Stage::Preparation) {\n                if (captureCurrentSettingsBaseline()) {\n                    g_configPrompt = false;\n                    continueFromPreparationBaseline();\n                }\n                redraw = true;\n""",
    "config prompt baseline path",
)

# Preparation page X path: same behavior.
s = replace_once(
    s,
    """        } else if (g.stage == Stage::Preparation && (k & HidNpadButton_X)) {\n            if (captureCurrentSettingsBaseline()) g_rebootConfirm = true;\n            else g_configPrompt = true;\n            redraw = true;\n""",
    """        } else if (g.stage == Stage::Preparation && (k & HidNpadButton_X)) {\n            if (captureCurrentSettingsBaseline()) continueFromPreparationBaseline();\n            else g_configPrompt = true;\n            redraw = true;\n""",
    "main baseline path",
)

# Update Auto Prep explanation: no direct INI edits/backups; HOC owns the save.
s = s.replace(
    '    uiPrintf(7, "The Wizard will update only the required");\n'
    '    uiPrintf(8, "Preparation keys in Horizon OC config.ini.");\n'
    '    uiPrintf(10, "VDDQ start : %d mV", g.vddqStartMv);\n'
    '    uiPrintf(11, "Other Horizon OC values stay unchanged.");\n'
    '    uiPrintf(13, "Backup: config.ini.wizard.bak");\n'
    '    uiPrintf(15, "Values are read back before reboot.");\n'
    '    uiPrintf(16, "If verification succeeds, reboot is automatic.");',
    '    uiPrintf(7, "Uses Horizon OC SetConfigValues + Save KIP.");\n'
    '    uiPrintf(8, "Only required Preparation values are changed.");\n'
    '    uiPrintf(10, "VDDQ start : %d mV", g.vddqStartMv);\n'
    '    uiPrintf(11, "Other Horizon OC values stay unchanged.");\n'
    '    uiPrintf(13, "Horizon OC 2.5.1 is required for auto setup.");\n'
    '    uiPrintf(15, "Values are read back before reboot.");\n'
    '    uiPrintf(16, "If verification succeeds, reboot is automatic.");',
    1,
)

p.write_text(s)

# Version/update metadata ----------------------------------------------------
p = Path("Makefile")
s = p.read_text().replace("APP_VERSION := 0.4.0-beta.28", "APP_VERSION := 0.4.0-beta.29", 1)
p.write_text(s)

Path("UPDATE.txt").write_text(
    "version=0.4.0-beta.29\n"
    "nro_url=https://github.com/retrotendo/HOC-Undervolting-Wizard/releases/download/v0.4.0-beta.29/HOC-Undervolting-Wizard.nro\n"
    "sha_url=https://github.com/retrotendo/HOC-Undervolting-Wizard/releases/download/v0.4.0-beta.29/HOC-Undervolting-Wizard.nro.sha256\n"
)

Path("RELEASE_NOTES_v0.4.0-beta.29.md").write_text("""# v0.4.0-beta.29\n\nPreparation baseline/automatic-setup fix.\n\n- `Use current settings as baseline` no longer performs an unnecessary Preparation reboot. The captured values are stored and the Wizard moves directly to the next Low UV candidate.\n- Automatic Preparation now uses Horizon OC's own public `SetConfigValues` IPC and `SetKipData` (Save KIP) instead of editing `config.ini` behind the running sysmodule.\n- Automatic writing is guarded to the confirmed Horizon OC 2.5.1 config layout. Unsupported versions fail safely without writing version-dependent indexes.\n- Preparation values are read back from the named config keys before reboot is allowed.\n""")

print("beta29 preparation fix applied")
