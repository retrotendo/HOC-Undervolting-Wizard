from pathlib import Path

r=Path('README.md')
s=r.read_text()
s=s.replace('on **Mariko / Switch OLED**.', 'on **Mariko / Switch V2 / Lite / OLED**.')

marker='# New in v0.4.0-beta.15\n'
section='''# New in v0.4.0-beta.16

## Hardware-aware VDDQ start

- Before Preparation, the Wizard reads Horizon OC's `dramID` and identifies the installed Mariko RAM module.
- The VDDQ baseline is selected automatically from the Horizon OC RAM guidance: **640 mV** for NEE/x267, AA-MGCL, AM-MGCJ, AB-MGCL and NME; **600 mV** for WT:B, WT:F and WT:E.
- The detected RAM module, DRAM ID and chosen VDDQ start are shown before Preparation.
- Unknown/unsupported DRAM IDs are not guessed; detection must succeed before the guided setup continues.

## Verified setting -> guided reboot

Persistent HOC changes now use a dedicated handoff instead of mixing setting instructions and stress tests on one page:

1. The Wizard shows only the **new value that must be changed now**.
2. Press **A** and the Wizard reads Horizon OC's current persistent configuration.
3. A wrong value is shown as **Required / Current / WRONG** and reboot is blocked.
4. A correct value gets a green confirmation such as **Low VMIN 615 mV is set**.
5. Press **A** again to request the console restart.
6. After reopening the Wizard, it first asks whether the console booted normally with the new value.
7. Only after **YES** does the 1-minute/1-hour test page appear.

Values that were already confirmed are no longer repeated as set points on later pages. Temporary Overrides are still shown whenever they must be changed for a test.

## CPU voltage-region validation

The Low VMIN scan still measures **510 -> 612 -> 714 -> 816 -> 918 -> 1020 MHz**, but beta.16 no longer stops after finding the VMIN crossover.

- Pressing A for a scan point shows a short **3-sample progress bar** while HOC voltage is read.
- All six points are measured.
- Readings are grouped into distinct 5 mV CPU-voltage regions.
- For each region, only the **highest frequency in that region** gets the 1-hour CPU stability test.

Example: if 510-816 MHz measure ~570 mV, 918 MHz measures ~585 mV and 1020 MHz measures ~600 mV, the Wizard validates **816 @ 570**, **918 @ 585** and **1020 @ 600**.

The detected voltage regions are also written to `results.txt`.

---

'''
if marker not in s: raise SystemExit('beta15 marker missing')
s=s.replace(marker, section+marker,1)

s=s.replace('Quick boundary tests normally run for **1 minute**. Long validation tests run for **1 hour**. The dynamic Low VMIN floor sweep is measurement-only and does not run a stress test at every frequency.',
'''Quick boundary tests normally run for **1 minute**. Long validation tests run for **1 hour**. The Low VMIN voltage scan is measurement-only; after the scan, the Wizard runs a long CPU test only at the highest frequency of each distinct measured voltage region.''')

old='''These sweep points are **measurement-only**. They do not each run another 1-minute stress test. The actual stability confirmation is concentrated at the highest detected floor-bound CPU clock.

As soon as the voltage has clearly risen above VMIN, higher sweep steps are no longer needed. The Wizard then runs the **1-hour Low VMIN confirmation at the highest detected floor-bound CPU clock**.

Example: if a console reports roughly 570 mV through 816 MHz but ~585 mV at 918 MHz, the long VMIN test is run at **816 MHz**, not at 510 and not unnecessarily at 1020.

Lower CPU clocks on the same voltage floor are computationally less demanding, but normal Home/Sleep/Wake/game transitions should still be checked afterward.'''
new='''These sweep points are **measurement-only**. They do not each run another 1-minute stress test. Starting with beta.16, all six points are measured so the Wizard can identify every distinct CPU-voltage region, not only the VMIN floor.

Readings are rounded/grouped on HOC's 5 mV voltage steps. The Wizard then selects the **highest CPU frequency in each observed voltage region** for 1-hour CPU validation.

Example: if a console reports roughly 570 mV through 816 MHz, ~585 mV at 918 MHz and ~600 mV at 1020 MHz, the long validations are **816 @ 570**, **918 @ 585** and **1020 @ 600**.

Lower CPU clocks within the same voltage region are computationally less demanding, while normal Home/Sleep/Wake/game transitions remain part of final validation.'''
if old not in s: raise SystemExit('old beta5 VMIN text missing')
s=s.replace(old,new,1)

s=s.replace('- **VDDQ: 600 mV**', '''- **VDDQ: automatically selected from detected RAM**
  - **640 mV:** NEE/x267, AA-MGCL, AM-MGCJ, AB-MGCL, NME
  - **600 mV:** WT:B, WT:F, WT:E''',1)
s=s.replace('\n### CPU UV\n\n- **CPU UV Table: 1683 MHz Tbreak**', '\n- **CPU UV Table: 1683 MHz Tbreak**',1)

old='''After changing persistent HOC/Toolkit settings:

**Reboot CFW -> reopen the Wizard**'''
new='''The Wizard verifies persistent HOC values before rebooting. When the requested value is detected, a green confirmation is shown and **A** requests the restart. After reopening, confirm whether the console booted normally before the Wizard continues to the stability test.'''
if old not in s: raise SystemExit('old reboot docs missing')
s=s.replace(old,new,1)

s=s.replace('''   - dynamic floor sweep at 510/612/714/816/918/1020
   - 1-hour confirmation at the highest clock still actually on the VMIN floor
   - then verify Home, Sleep/Wake, game launch/close''', '''   - full voltage scan at 510/612/714/816/918/1020 with visible 3-sample progress
   - group the measured values into distinct 5 mV CPU-voltage regions
   - 1-hour confirmation at the **highest frequency of every detected voltage region**
   - then verify Home, Sleep/Wake, game launch/close''',1)

s=s.replace('''- **Y** — DID NOT BOOT on quick-search stages
- **B** — exit and save progress''', '''- **B** — exit and save progress''',1)

controls_marker='''During a running stress test:
'''
controls_add='''When a persistent Horizon OC value must change:

- **A** — verify the requested value against Horizon OC
- if correct, a green confirmation screen appears
- **A** again — request console restart
- after reopening: **A = booted normally**, **X = did not boot**, **B = decide later**

'''
if controls_marker not in s: raise SystemExit('controls marker missing')
s=s.replace(controls_marker, controls_add+controls_marker,1)

s=s.replace('''- CPU Low UV
- CPU Low VMIN
- dynamically detected highest Low VMIN floor clock when available
- RAM VDDQ''', '''- detected RAM module and VDDQ starting point
- CPU Low UV
- CPU Low VMIN
- dynamically detected highest Low VMIN floor clock when available
- every detected CPU voltage region and its highest validated frequency
- RAM VDDQ''',1)

s=s.replace('- Nintendo Switch **Mariko / Switch OLED**', '- Nintendo Switch **Mariko / Switch V2 / Lite / OLED**',1)

r.write_text(s)

c=Path('CHANGELOG.md')
t=c.read_text()
entry='''## v0.4.0-beta.16
- Detect the installed Mariko DRAM through Horizon OC before Preparation and choose the RAM-specific VDDQ baseline automatically (600 or 640 mV).
- Read persistent Horizon OC config values before every reboot-required tuning step.
- Block reboot if the requested value is not actually set; show Required / Current / WRONG.
- Show a green confirmation when the requested value is detected, then reboot only after a second A-button confirmation.
- Persist the reboot handoff and ask whether CFW booted normally when the Wizard is reopened.
- Separate setting pages from test pages so already-confirmed UV/voltage values are not repeatedly shown.
- Add a visible 3-sample progress bar to CPU voltage scans.
- Scan all 510/612/714/816/918/1020 MHz points and group the observed CPU voltages into 5 mV regions.
- Run the 1-hour CPU validation at the highest frequency of **each** detected voltage region instead of only the Low VMIN floor region.
- Record detected RAM and CPU voltage regions in `results.txt`.
- Keep beta.15's vertical Required / Current / OK-WRONG Temporary Override blocker.

'''
if not t.startswith('## v0.4.0-beta.15'):
    raise SystemExit('unexpected changelog head')
c.write_text(entry+t)
print('beta16 docs updated')
