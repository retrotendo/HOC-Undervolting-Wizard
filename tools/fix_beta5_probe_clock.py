from pathlib import Path
p = Path('source/main.cpp')
s = p.read_text()

s = s.replace(
'''    bool cpuOk = false;\n    bool gpuOk = false;\n    bool ramOk = false;\n};\n''',
'''    bool cpuOk = false;\n    bool gpuOk = false;\n    bool ramOk = false;\n    bool cpuAppliedOk = true;\n    bool voltageSamplesOk = true;\n};\n''', 1)

s = s.replace(
'''            clockMatches(cur.overrideHz[2], g_overrideCheck.expected.ramHz) &&\n            cur.cpuVoltageUv != 0) {\n''',
'''            clockMatches(cur.overrideHz[2], g_overrideCheck.expected.ramHz) &&\n            clockMatches(cur.targetHz[0], g_overrideCheck.expected.cpuHz) &&\n            cur.cpuVoltageUv != 0) {\n''', 1)

s = s.replace(
'''        g_overrideCheck.cpuOk = clockMatches(latest.overrideHz[0], g_overrideCheck.expected.cpuHz);\n        g_overrideCheck.gpuOk = clockMatches(latest.overrideHz[1], g_overrideCheck.expected.gpuHz);\n        g_overrideCheck.ramOk = clockMatches(latest.overrideHz[2], g_overrideCheck.expected.ramHz);\n        return false;\n''',
'''        g_overrideCheck.cpuOk = clockMatches(latest.overrideHz[0], g_overrideCheck.expected.cpuHz);\n        g_overrideCheck.gpuOk = clockMatches(latest.overrideHz[1], g_overrideCheck.expected.gpuHz);\n        g_overrideCheck.ramOk = clockMatches(latest.overrideHz[2], g_overrideCheck.expected.ramHz);\n        g_overrideCheck.cpuAppliedOk = clockMatches(latest.targetHz[0], g_overrideCheck.expected.cpuHz);\n        g_overrideCheck.voltageSamplesOk = false;\n        return false;\n''', 1)

s = s.replace(
'''    g_overrideCheck.readOk = true;\n    g_overrideCheck.cpuOk = g_overrideCheck.gpuOk = g_overrideCheck.ramOk = true;\n    return true;\n}\n''',
'''    g_overrideCheck.readOk = true;\n    g_overrideCheck.cpuOk = g_overrideCheck.gpuOk = g_overrideCheck.ramOk = true;\n    g_overrideCheck.cpuAppliedOk = true;\n    g_overrideCheck.voltageSamplesOk = true;\n    return true;\n}\n''', 1)

needle = '''        std::printf("CPU    %-13s  %-13s  %s\\n",\n                    formatClock(g_overrideCheck.expected.cpuHz).c_str(),\n                    formatClock(g_overrideCheck.current.overrideHz[0]).c_str(),\n                    g_overrideCheck.cpuOk ? ok : bad);\n'''
replacement = needle + '''        if (g_overrideAction == PendingOverrideAction::VminProbe) {\n            std::printf("CPU applied %-11s  %-13s  %s\\n",\n                        formatClock(g_overrideCheck.expected.cpuHz).c_str(),\n                        formatClock(g_overrideCheck.current.targetHz[0]).c_str(),\n                        g_overrideCheck.cpuAppliedOk ? ok : bad);\n        }\n'''
if needle not in s:
    raise SystemExit('CPU override render block not found')
s = s.replace(needle, replacement, 1)

needle = '''        std::printf("Open Horizon OC -> Temporary Overrides and correct ALL red values.\\n");\n'''
replacement = '''        if (g_overrideAction == PendingOverrideAction::VminProbe &&\n            g_overrideCheck.cpuOk && g_overrideCheck.gpuOk && g_overrideCheck.ramOk &&\n            !g_overrideCheck.cpuAppliedOk) {\n            std::printf("CPU Override is set, but HOC has not applied that CPU clock.\\n");\n            std::printf("Disable CPU governor/automatic CPU scaling for the probe, then retry.\\n");\n        } else if (g_overrideAction == PendingOverrideAction::VminProbe &&\n                   g_overrideCheck.cpuOk && g_overrideCheck.gpuOk && g_overrideCheck.ramOk &&\n                   g_overrideCheck.cpuAppliedOk && !g_overrideCheck.voltageSamplesOk) {\n            std::printf("Overrides and applied CPU clock are correct, but too few fresh\\n");\n            std::printf("CPU-voltage samples were received. Keep them active and retry.\\n");\n        } else {\n            std::printf("Open Horizon OC -> Temporary Overrides and correct ALL red values.\\n");\n        }\n'''
if needle not in s:
    raise SystemExit('override hint block not found')
s = s.replace(needle, replacement, 1)

p.write_text(s)

for name in ['README.md','CHANGELOG.md','RELEASE_NOTES_v0.4.0-beta.5.md']:
    p = Path(name)
    t = p.read_text()
    phrase = 'uses the **median of valid readings**'
    if phrase in t:
        t = t.replace(phrase, 'uses the **median of valid readings** and only accepts samples while HOC reports the requested CPU clock as actually applied', 1)
    elif 'uses the **median** of valid samples' in t:
        t = t.replace('uses the **median** of valid samples', 'uses the **median** of valid samples and only accepts them while HOC reports the requested CPU clock as actually applied', 1)
    p.write_text(t)
