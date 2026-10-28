from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

replacements = {
    'X : Use current settings as baseline': 'X : Use my current settings as baseline',
    ' - CPU Boost       : Lowest selectable / 1785': ' - CPU Boost : lowest / 1785 MHz',
    'Set all required Preparation values automatically?': 'Auto-set required Preparation values?',
    'Uses Horizon OC SetConfigValues + Save KIP.': 'Uses HOC SetConfigValues + Save KIP.',
    'Unrelated Horizon OC values stay unchanged.': 'Other Horizon OC values stay unchanged.',
    'The value is read back before reboot is offered.': 'Value is read back before reboot.',
    'Preparation values are saved and verified.': 'Preparation values saved and verified.',
    'Low UV %d is saved and verified.': 'Low UV %d saved and verified.',
    'Low VMIN %d mV is saved and verified.': 'Low VMIN %d mV saved and verified.',
    'Requested setting is saved and verified.': 'Requested setting saved and verified.',
    'A reboot is required to apply the KIP value.': 'Reboot required to apply the KIP value.',
    'After normal CFW boots, open this Wizard again.': 'After reboot, open this Wizard again.',
    'If normal CFW does not boot, freezes or crashes:': 'If normal CFW fails to boot or crashes:',
    'The console appears to have booted with it.': 'Console booted with requested value.',
    'successfully with the requested value and': 'Requested value likely did not boot.',
    'was recovered to the previous working value.': 'Recovery restored last working value.',
    'Confirm only if this matches your recovery.': 'Confirm this matches your recovery.',
    'Could not confirm the expected active value.': 'Could not confirm active value.',
    'Check Horizon OC / recovery state first.': 'Check Horizon OC / recovery state.',
    'Find the highest Low UV that can boot normally.': 'Find highest Low UV that boots.',
    'Lower Low VMIN in 10 mV steps until boot fails.': 'Lower Low VMIN 10 mV until boot fails.',
    'Next the Wizard maps the CPU voltage curve at:': 'Next, Wizard maps CPU voltage at:',
    'and keeps only the highest frequency of each': 'It keeps highest frequency from each',
    'different voltage region for stability testing.': 'different voltage region for testing.',
    'The Wizard will set every override automatically': 'Wizard sets each override.',
    'and run each listed CPU frequency for 1 minute.': 'Each CPU frequency runs for 1 minute.',
    'A : Continue to automatic 1-minute tests': 'A : Start automatic 1-minute tests',
}

missing = []
for old, new in replacements.items():
    if old not in s:
        missing.append(old)
    else:
        s = s.replace(old, new)

if missing:
    raise SystemExit('Missing expected strings:\n' + '\n'.join(missing))

p.write_text(s)

# Guard the beta31 strings we intentionally show as single terminal lines.
visible_lines = [
    'X : Use my current settings as baseline',
    'Y : Set required value(s) automatically',
    'Auto-set required Preparation values?',
    'Uses HOC SetConfigValues + Save KIP.',
    'Other Horizon OC values stay unchanged.',
    'Value is read back before reboot.',
    'Preparation values saved and verified.',
    'Reboot required to apply the KIP value.',
    'After reboot, open this Wizard again.',
    'If normal CFW fails to boot or crashes:',
    'Console booted with requested value.',
    'Requested value likely did not boot.',
    'Recovery restored last working value.',
    'Confirm this matches your recovery.',
    'Could not confirm active value.',
    'Check Horizon OC / recovery state.',
    'Find highest Low UV that boots.',
    'Lower Low VMIN 10 mV until boot fails.',
    'Next, Wizard maps CPU voltage at:',
    '510 / 612 / 714 / 816 / 918 / 1020 MHz',
    'It keeps highest frequency from each',
    'different voltage region for testing.',
    'Wizard sets each override.',
    'Each CPU frequency runs for 1 minute.',
    'A : Start automatic 1-minute tests',
]
for line in visible_lines:
    if len(line) > 39:
        raise SystemExit(f'beta31 line too wide ({len(line)}): {line}')

print('beta31 UI width patch applied; guarded lines <= 39 characters')
