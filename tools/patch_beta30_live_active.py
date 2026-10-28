from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError(f'expected one match, found {text.count(old)}: {old[:120]}')
    return text.replace(old, new, 1)

# Add an exact HOC 2.5.1 live-config getter.
h = ROOT / 'source/hoc_monitor.h'
s = h.read_text()
s = replace_once(s,
'''Result hocmonApplyCpuLow251(int lowUv, int lowVminMv, u32 fieldsMask);\n''',
'''Result hocmonApplyCpuLow251(int lowUv, int lowVminMv, u32 fieldsMask);\n\n/* Read the running Horizon OC 2.5.1 config through hoc:clk/GetConfigValues. */\nResult hocmonGetConfig251(HocMonConfig* out);\n''')
h.write_text(s)

c = ROOT / 'source/hoc_monitor.c'
s = c.read_text()
marker = 'Result hocmonGetConfigDebug(HocMonConfigDebug* out)\n'
if s.count(marker) != 1:
    raise RuntimeError('config debug insertion marker missing')
getter = r'''Result hocmonGetConfig251(HocMonConfig* out)
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

    HocMonRawConfig cfg;
    memset(&cfg, 0, sizeof(cfg));
    rc = serviceDispatch(&srv, HOCCLK_IPC_CMD_GET_CONFIG_VALUES,
        .buffer_attrs = { SfBufferAttr_HipcAutoSelect | SfBufferAttr_Out },
        .buffers = {{ &cfg, sizeof(cfg) }},
    );
    serviceClose(&srv);
    if (R_FAILED(rc))
        return rc;

    if ((u32)cfg.values[CFG251_KIP_VERSION] != 251U)
        return 4;

    out->uncappedClocks = cfg.values[CFG251_UNCAPPED_CLOCKS] != 0;
    out->hpMode = cfg.values[CFG251_HP_MODE] != 0;
    out->vdd2Uv = (u32)cfg.values[CFG251_VDD2_UV];
    out->ramMaxKHz = (u32)cfg.values[CFG251_RAM_MAX_KHZ];
    out->vddqUv = (u32)cfg.values[CFG251_VDDQ_UV];
    out->lowUv = (int)cfg.values[CFG251_CPU_LOW_UV];
    out->highUv = (int)cfg.values[CFG251_CPU_HIGH_UV];
    out->tableConf = (int)cfg.values[CFG251_CPU_TABLE];
    out->lowVminMv = (int)cfg.values[CFG251_CPU_LOW_VMIN_MV];
    out->highVminMv = (int)cfg.values[CFG251_CPU_HIGH_VMIN_MV];
    out->cpuMaxKHz = (u32)cfg.values[CFG251_CPU_MAX_KHZ];
    out->cpuBoostKHz = (u32)cfg.values[CFG251_CPU_BOOST_KHZ];
    return 0;
}

'''
s = s.replace(marker, getter + marker, 1)
c.write_text(s)

p = ROOT / 'source/main.cpp'
s = p.read_text()
old = r'''BootInference inferBootState(int* activeValue = nullptr) {
    HocMonConfig c{};
    if (!readHocConfigIni(c)) return BootInference::Unknown;

    if (g.stage == Stage::Preparation)
        return configMatchesCurrent(Config_Prepare, c) ? BootInference::RequestedActive : BootInference::Unknown;
'''
new = r'''BootInference inferBootState(int* activeValue = nullptr) {
    HocMonConfig c{};
    // After reboot, inspect the RUNNING Horizon OC config, not only config.ini.
    // If hoc:clk is unavailable (for example CFW No OC), the boot cannot be
    // counted as a successful normal-HOC boot.
    if (R_FAILED(hocmonGetConfig251(&c))) return BootInference::Unknown;

    if (g.stage == Stage::Preparation)
        return configMatchesCurrent(Config_Prepare, c) ? BootInference::RequestedActive : BootInference::Unknown;
'''
s = replace_once(s, old, new)
p.write_text(s)
print('live active config patch applied')
