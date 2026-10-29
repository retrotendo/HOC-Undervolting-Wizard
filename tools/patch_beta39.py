from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()


def rep(old, new, label, count=1):
    global s
    if old not in s:
        raise SystemExit(f'{label} not found')
    s = s.replace(old, new, count)


def replace_between(start_marker, end_marker, replacement, label):
    global s
    a = s.find(start_marker)
    if a < 0:
        raise SystemExit(f'{label} start not found')
    b = s.find(end_marker, a)
    if b < 0:
        raise SystemExit(f'{label} end not found')
    s = s[:a] + replacement + s[b:]

# Robust CPU voltage sampling: discard two settling reads, then use the
# median of nine valid measurements. Retry once when the rail is unusually
# noisy (>20 mV spread) or a full set could not be collected.
new_vmin_sampler = r'''bool sampleVminVoltage(Stage s, int sweepIndex = -1, int sweepTotal = 0) {
    if (!checkAllOverrides(s)) return false;

    constexpr int kSettleReads = 2;
    constexpr int kSamples = 9;
    constexpr int kAttempts = 2;
    constexpr u32 kMaxSpreadUv = 20000U;
    HocMonClocks latest = g_overrideCheck.current;

    for (int attempt = 0; attempt < kAttempts; ++attempt) {
        for (int settle = 0; settle < kSettleReads; ++settle) {
            consoleClear();
            std::printf("\\x1b[1;%dH\\x1b[36mBattery Wizard\\x1b[0m", UI_COL);
            std::printf("\\x1b[2;%dHStep : CPU Low VMIN - AUTO SCAN", UI_COL);
            std::printf("\\x1b[3;%dH----------------------------------------", UI_COL);
            if (sweepIndex >= 0 && sweepTotal > 0)
                std::printf("\\x1b[5;%dHFrequency : %d / %d", UI_COL, sweepIndex + 1, sweepTotal);
            std::printf("\\x1b[7;%dHCPU       : %s", UI_COL, formatClock(g_overrideCheck.expected.cpuHz).c_str());
            std::printf("\\x1b[8;%dHGPU / RAM : 384 / 1331.2 MHz", UI_COL);
            std::printf("\\x1b[10;%dHSettling voltage %d / %d...", UI_COL, settle + 1, kSettleReads);
            consoleUpdate(nullptr);
            svcSleepThread(700'000'000);
            HocMonClocks ignored{};
            if (R_SUCCEEDED(hocmonGetClocks(&ignored))) latest = ignored;
        }

        std::vector<u32> samples;
        samples.reserve(kSamples);
        for (int i = 0; i < kSamples; ++i) {
            consoleClear();
            std::printf("\\x1b[1;%dH\\x1b[36mBattery Wizard\\x1b[0m", UI_COL);
            std::printf("\\x1b[2;%dHStep : CPU Low VMIN - AUTO SCAN", UI_COL);
            std::printf("\\x1b[3;%dH----------------------------------------", UI_COL);
            if (sweepIndex >= 0 && sweepTotal > 0)
                std::printf("\\x1b[5;%dHFrequency : %d / %d", UI_COL, sweepIndex + 1, sweepTotal);
            std::printf("\\x1b[7;%dHCPU       : %s", UI_COL, formatClock(g_overrideCheck.expected.cpuHz).c_str());
            std::printf("\\x1b[8;%dHGPU / RAM : 384 / 1331.2 MHz", UI_COL);
            std::printf("\\x1b[10;%dHReading CPU voltage sample %d / %d...", UI_COL, i + 1, kSamples);
            if (attempt > 0) std::printf("\\x1b[12;%dHRetrying noisy measurement...", UI_COL);
            consoleUpdate(nullptr);
            svcSleepThread(700'000'000);

            HocMonClocks cur{};
            Result rc = hocmonGetClocks(&cur);
            if (R_SUCCEEDED(rc) &&
                clockMatches(cur.overrideHz[0], g_overrideCheck.expected.cpuHz) &&
                clockMatches(cur.overrideHz[1], g_overrideCheck.expected.gpuHz) &&
                clockMatches(cur.overrideHz[2], g_overrideCheck.expected.ramHz) &&
                clockMatches(cur.targetHz[0], g_overrideCheck.expected.cpuHz) &&
                cur.cpuVoltageUv != 0) {
                samples.push_back(cur.cpuVoltageUv);
                latest = cur;
            }
        }

        if ((int)samples.size() != kSamples) {
            if (attempt + 1 < kAttempts) continue;
            break;
        }

        std::sort(samples.begin(), samples.end());
        const u32 spread = samples.back() - samples.front();
        if (spread > kMaxSpreadUv && attempt + 1 < kAttempts) continue;

        latest.cpuVoltageUv = samples[kSamples / 2];
        g_overrideCheck.current = latest;
        g_overrideCheck.readOk = true;
        g_overrideCheck.cpuOk = g_overrideCheck.gpuOk = g_overrideCheck.ramOk = true;
        g_overrideCheck.cpuAppliedOk = true;
        g_overrideCheck.voltageSamplesOk = true;
        return true;
    }

    g_overrideCheck.current = latest;
    g_overrideCheck.readOk = true;
    g_overrideCheck.cpuOk = clockMatches(latest.overrideHz[0], g_overrideCheck.expected.cpuHz);
    g_overrideCheck.gpuOk = clockMatches(latest.overrideHz[1], g_overrideCheck.expected.gpuHz);
    g_overrideCheck.ramOk = clockMatches(latest.overrideHz[2], g_overrideCheck.expected.ramHz);
    g_overrideCheck.cpuAppliedOk = clockMatches(latest.targetHz[0], g_overrideCheck.expected.cpuHz);
    g_overrideCheck.voltageSamplesOk = false;
    return false;
}



'''
replace_between('bool sampleVminVoltage(Stage s, int sweepIndex = -1, int sweepTotal = 0) {', 'void ensureDir() {', new_vmin_sampler, 'sampleVminVoltage')

new_region_sampler = r'''bool sampleCpuVoltageAt(u32 cpuHz, int index, int total, int& outMv) {
    constexpr int kSettleReads = 2;
    constexpr int kSamples = 9;
    constexpr int kAttempts = 2;
    constexpr u32 kMaxSpreadUv = 20000U;

    for (int attempt = 0; attempt < kAttempts; ++attempt) {
        for (int settle = 0; settle < kSettleReads; ++settle) {
            consoleClear();
            uiPrintf(1, "\\x1b[36mBattery Wizard - CPU VOLTAGE SCAN\\x1b[0m");
            uiPrintf(3, "----------------------------------------");
            uiPrintf(5, "Frequency : %d / %d", index + 1, total);
            uiPrintf(7, "CPU       : %s", formatClock(cpuHz).c_str());
            uiPrintf(8, "GPU / RAM : 384 / 1331.2 MHz");
            uiPrintf(10, "Settling voltage %d / %d...", settle + 1, kSettleReads);
            consoleUpdate(nullptr);
            svcSleepThread(700'000'000);
            HocMonClocks ignored{};
            hocmonGetClocks(&ignored);
        }

        std::vector<u32> samples;
        samples.reserve(kSamples);
        for (int sample = 0; sample < kSamples; ++sample) {
            consoleClear();
            uiPrintf(1, "\\x1b[36mBattery Wizard - CPU VOLTAGE SCAN\\x1b[0m");
            uiPrintf(3, "----------------------------------------");
            uiPrintf(5, "Frequency : %d / %d", index + 1, total);
            uiPrintf(7, "CPU       : %s", formatClock(cpuHz).c_str());
            uiPrintf(8, "GPU / RAM : 384 / 1331.2 MHz");
            uiPrintf(10, "Reading CPU voltage sample %d / %d...", sample + 1, kSamples);
            if (attempt > 0) uiPrintf(12, "Retrying noisy measurement...");
            consoleUpdate(nullptr);
            svcSleepThread(700'000'000);

            HocMonClocks cur{};
            if (R_SUCCEEDED(hocmonGetClocks(&cur)) &&
                clockMatches(cur.overrideHz[0], cpuHz) &&
                clockMatches(cur.overrideHz[1], CLOCK_GPU_NORMAL_HZ) &&
                clockMatches(cur.overrideHz[2], CLOCK_RAM_NORMAL_HZ) &&
                clockMatches(cur.targetHz[0], cpuHz) && cur.cpuVoltageUv != 0)
                samples.push_back(cur.cpuVoltageUv);
        }

        if ((int)samples.size() != kSamples) {
            if (attempt + 1 < kAttempts) continue;
            return false;
        }

        std::sort(samples.begin(), samples.end());
        const u32 spread = samples.back() - samples.front();
        if (spread > kMaxSpreadUv && attempt + 1 < kAttempts) continue;

        const u32 medianUv = samples[kSamples / 2];
        outMv = (int)(((medianUv + 2500U) / 5000U) * 5U);
        return true;
    }
    return false;
}

'''
replace_between('bool sampleCpuVoltageAt(u32 cpuHz, int index, int total, int& outMv) {', 'void runAutomaticVoltageScan(bool forLowUv) {', new_region_sampler, 'sampleCpuVoltageAt')

rep('g_vminScanErrorText = "Could not obtain three valid voltage samples.";',
    'g_vminScanErrorText = "Could not obtain a stable nine-sample CPU voltage set.";',
    'voltage scan error text')

# beta39 final validation: keep the meaningful integration tests, skip the
# redundant duplicate RAM/GPU/Boost passes at the very end.
rep('case Stage::BoostCpuRamValidate: g.stage = Stage::NormalMatrixValidate; break;\n    case Stage::NormalMatrixValidate: g.stage = Stage::NormalMemValidate; break;\n    case Stage::NormalMemValidate: g.stage = Stage::NormalGpuValidate; break;\n    case Stage::NormalGpuValidate: g.stage = Stage::BoostMatrixValidate; break;\n    case Stage::BoostMatrixValidate: g.stage = Stage::BoostMemValidate; break;\n    case Stage::BoostMemValidate: g.stage = Stage::BoostCpuMemValidate; break;\n    case Stage::BoostCpuMemValidate: g.stage = Stage::RealWorldValidate; break;',
    'case Stage::BoostCpuRamValidate: g.stage = Stage::NormalMatrixValidate; break;\n    case Stage::NormalMatrixValidate: g.stage = Stage::RealWorldValidate; break;\n    case Stage::NormalMemValidate:\n    case Stage::NormalGpuValidate:\n    case Stage::BoostMatrixValidate:\n    case Stage::BoostMemValidate:\n    case Stage::BoostCpuMemValidate:\n        // Legacy beta states: these tests are redundant in beta39+.\n        g.stage = Stage::RealWorldValidate;\n        break;',
    'final validation transitions')

# Existing saved beta38 states that were already inside one of the removed
# duplicate final tests should continue at Real-World validation after update.
needle = '''    if (legacyVminState) {
        g.stage = Stage::LowVminLong;
        g.stageReadyAfterBoot = true;
        g.pendingConfigMask = Config_None;
        g.vminObsMask = 0;
        g.vminValidateCount = 0;
        g.vminValidateIndex = 0;
        g.lastProbeHz = 0;
        g.lastProbeMv = 0;
        for (int i = 0; i < 6; ++i) {
            g.vminObsMv[i] = 0;
            g.vminValidateHz[i] = 0;
            g.vminValidateMv[i] = 0;
        }
    }
    return true;
'''
replacement = '''    if (legacyVminState) {
        g.stage = Stage::LowVminLong;
        g.stageReadyAfterBoot = true;
        g.pendingConfigMask = Config_None;
        g.vminObsMask = 0;
        g.vminValidateCount = 0;
        g.vminValidateIndex = 0;
        g.lastProbeHz = 0;
        g.lastProbeMv = 0;
        for (int i = 0; i < 6; ++i) {
            g.vminObsMv[i] = 0;
            g.vminValidateHz[i] = 0;
            g.vminValidateMv[i] = 0;
        }
    }

    const bool removedFinalValidationStage =
        g.stage == Stage::NormalMemValidate || g.stage == Stage::NormalGpuValidate ||
        g.stage == Stage::BoostMatrixValidate || g.stage == Stage::BoostMemValidate ||
        g.stage == Stage::BoostCpuMemValidate;
    if (removedFinalValidationStage) {
        g.stage = Stage::RealWorldValidate;
        g.stageReadyAfterBoot = true;
        g.pendingConfigMask = Config_None;
    }
    return true;
'''
rep(needle, replacement, 'legacy final-stage migration')

p.write_text(s)

m = Path('Makefile')
ms = m.read_text()
if 'APP_VERSION := 0.4.0-beta.38' not in ms:
    raise SystemExit('beta38 Makefile version not found')
ms = ms.replace('APP_VERSION := 0.4.0-beta.38', 'APP_VERSION := 0.4.0-beta.39', 1)
m.write_text(ms)
