from pathlib import Path

r = Path('README.md')
s = r.read_text()

old = '''## CPU voltage-region validation\n\nThe Low VMIN scan still measures **510 -> 612 -> 714 -> 816 -> 918 -> 1020 MHz**, but beta.16 no longer stops after finding the VMIN crossover.\n\n- Pressing A for a scan point shows a short **3-sample progress bar** while HOC voltage is read.\n- All six points are measured.\n- Readings are grouped into distinct 5 mV CPU-voltage regions.\n- For each region, only the **highest frequency in that region** gets the 1-hour CPU stability test.\n\nExample: if 510-816 MHz measure ~570 mV, 918 MHz measures ~585 mV and 1020 MHz measures ~600 mV, the Wizard validates **816 @ 570**, **918 @ 585** and **1020 @ 600**.\n\nThe detected voltage regions are also written to `results.txt`.'''
new = '''## Automatic CPU Low VMIN voltage scan\n\nAfter the Low VMIN candidate has booted successfully, the Wizard offers one **A = START SCAN** action. From that point the voltage scan runs without further user input.\n\n- The currently active CPU/GPU/RAM Temporary Overrides are saved first.\n- GPU is set automatically to **384 MHz** and RAM to **1331.2 MHz**.\n- CPU is switched automatically through **510 -> 612 -> 714 -> 816 -> 918 -> 1020 MHz**.\n- HOC is given time to settle after every frequency change.\n- At every CPU point the Wizard takes **3 valid CPU-rail samples** and uses the median.\n- Readings are grouped into distinct 5 mV CPU-voltage regions.\n- The Temporary Overrides that were active before the scan are restored afterward.\n- For each detected voltage region, only the **highest frequency in that region** gets the later 1-hour CPU stability test.\n\nExample: if 510-816 MHz measure ~570 mV, 918 MHz measures ~585 mV and 1020 MHz measures ~600 mV, the Wizard validates **816 @ 570**, **918 @ 585** and **1020 @ 600**.\n\nThe detected voltage regions are also written to `results.txt`. The Wizard still does not change persistent Low VMIN/UV/RAM voltage settings automatically; this scan writes only Temporary Overrides.'''
if old not in s: raise SystemExit('beta16 scan section missing')
s = s.replace(old, new, 1)

old = '''At each step the Wizard verifies CPU/GPU/RAM overrides and reads the **live CPU rail voltage reported by Horizon OC**. The probe takes **3 context samples** and uses the **median of valid readings** and only accepts samples while HOC reports the requested CPU clock as actually applied so a single stale HOC poll does not decide the crossover. It remembers the highest CPU frequency still operating at the configured VMIN floor (within one 5 mV PMIC step).'''
new = '''Starting with beta.16, the Wizard sets these Temporary Overrides itself for this scan. It saves the previous CPU/GPU/RAM overrides, applies the scan clocks, waits for HOC/governor to settle, then reads the **live CPU rail voltage reported by Horizon OC**. Every point uses **3 valid context samples** and the median; samples are accepted only while HOC reports the requested CPU clock as actually applied. After the full scan, the previous Temporary Overrides are restored.'''
if old not in s: raise SystemExit('dynamic scan paragraph missing')
s = s.replace(old, new, 1)

old = '''# The Wizard does not write Horizon OC tuning values\n\nThe Wizard reads Horizon OC context data for clocks, overrides and the current CPU rail voltage, but it does **not** write UV/voltage settings and does **not** edit `hoc.kip`.\n\nHorizon OC remains the place where tuning values are changed.'''
new = '''# Persistent tuning values remain manual\n\nThe Wizard does **not** write persistent CPU UV, Low/High VMIN, VDDQ or VDD2 tuning values and does **not** edit `hoc.kip`. Horizon OC remains the place where those tuning values are changed.\n\nThe beta.16 automatic Low VMIN scan is the first exception for **Temporary Overrides only**: the Wizard can set CPU/GPU/RAM Temporary Overrides through HOC's public `hoc:clk` IPC, perform the scan, and restore the previous overrides afterward.'''
if old not in s: raise SystemExit('persistent values section missing')
s = s.replace(old, new, 1)

marker = '''When a persistent Horizon OC value must change:\n\n- **A** — verify the requested value against Horizon OC\n- if correct, a green confirmation screen appears\n- **A** again — request console restart\n- after reopening: **A = booted normally**, **X = did not boot**, **B = decide later**\n\n'''
addition = '''Automatic Low VMIN voltage scan:\n\n- **A** — start the complete automatic 510 -> 1020 MHz scan\n- no manual Temporary Override changes are required during the scan\n- after completion, **A** continues to voltage-region validation\n\n'''
if marker not in s: raise SystemExit('controls marker missing')
s = s.replace(marker, marker + addition, 1)

r.write_text(s)

c = Path('CHANGELOG.md')
t = c.read_text()
needle = '''- Add a visible 3-sample progress bar to CPU voltage scans.\n- Scan all 510/612/714/816/918/1020 MHz points and group the observed CPU voltages into 5 mV regions.\n'''
replacement = '''- Add a fully automatic Low VMIN voltage scan using Horizon OC's public Temporary Override IPC.\n- Save the previous CPU/GPU/RAM overrides, automatically apply GPU 384 / RAM 1331.2 and CPU 510/612/714/816/918/1020, then restore the previous overrides after the scan.\n- Add a visible 3-sample progress bar to CPU voltage scans and automatically retry once if HOC/context settling is late.\n- Group the observed CPU voltages into 5 mV regions.\n'''
if needle not in t: raise SystemExit('changelog scan bullets missing')
t = t.replace(needle, replacement, 1)
c.write_text(t)
print('automatic VMIN docs updated')
