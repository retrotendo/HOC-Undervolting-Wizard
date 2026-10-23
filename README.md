# HOC Undervolting Wizard

A step-by-step Nintendo Switch homebrew assistant for finding and validating efficient **Horizon OC undervolting settings** on **Mariko / Switch OLED**.

The Wizard was created as a companion to **Performance Modes**:

https://github.com/retrotendo/Ultrahand-Performance-Modes

Use it to find stable Battery-profile CPU/RAM values, validate them with built-in stress tests, then save the proven values into Performance Modes.

The Wizard can also be used independently for Horizon OC tuning.

---

# v0.4 integrated test engine

Built-in tests use established open-source workloads:

- **CPU — Stress-NX Matrixprod + Hanoi Verify**
  - Matrixprod workload from the GPLv2 Horizon-OC / Benchmark Toolbox implementation.
  - Hanoi verification detects calculation errors automatically.
  - Benchmark Toolbox credits Stress-NX to **Lineon**.

- **RAM — memtester v4**
  - Stuck Address, Random Value, XOR/SUB/MUL/DIV, Sequential Increment, Solid Bits, Checkerboard, Bit Spread, Bit Flip, Walking Ones/Zeroes and related tests.
  - memtester credits **Simon Kirby** and **Charles Cazabon**.
  - Switch runner adapted from Horizon-OC / Benchmark Toolbox under GPLv2.

- **Combined — CPU + RAM**
  - Matrixprod/Hanoi and RAM stress run together to expose failures that only appear under combined load.

- **GPU — deko3d Compute / Memory Stress**
  - Project-original deko3d compute/memory test.
  - GPU output is verified on the CPU and mismatches fail the test.

Quick boundary tests normally run for **1 minute**. Long validation tests run for **1 hour**. The dynamic Low VMIN floor sweep is measurement-only and does not run a stress test at every frequency.

Before **every built-in test and every VMIN floor probe**, the Wizard reads Horizon OC's live `hoc:clk` context and verifies all three Temporary Overrides:

- CPU
- GPU
- RAM

A missing or wrong override blocks the test. No result is recorded until all three match the requested target.

---

# Full Memory Mode required

The Wizard must be launched from hbmenu in **Full Memory / Application Mode**.

If it is started in **Applet Mode** (for example through Album), the Wizard stops immediately on a dedicated warning screen. The guide and tuning state are not opened and no built-in test can be started.

To launch correctly, hold **R** while starting an installed game and keep holding **R** until hbmenu opens, then start HOC Undervolting Wizard.

This check uses the same `appletGetAppletType()` distinction as nx-hbmenu: only `Application` and `SystemApplication` modes are accepted.

---

# New in v0.4.0-beta.8

## Startup self-updater

Starting with **beta.8**, the Wizard checks its own GitHub releases when it starts in Full Application Mode.

- If the installed build is current, startup continues normally.
- If a newer build exists, the Wizard asks before doing anything: **A = Download & install**, **B = Not now**.
- The new NRO is downloaded to a temporary `.new` file first.
- The matching release `.sha256` file is downloaded and the NRO is verified with libnx SHA256 before replacement.
- Only after verification does the Wizard rename the current NRO to `.bak` and move the verified `.new` file into place.
- If replacement fails, the old NRO is restored.
- After a successful update the Wizard exits; launch it again from hbmenu to run the new build.
- The previous NRO remains beside the app as `.bak` for recovery and is replaced by the next updater run.

The updater is intentionally **not automatic**: it never installs a release without the user's A-button confirmation. Network/update-check failures are non-fatal and simply continue with the installed build.

The GitHub repository must be public for anonymous in-app update checks; no GitHub token is embedded in the NRO.

**beta.8 itself must be installed manually once. Future builds can then update beta.8 in-app.**

---

# New in v0.4.0-beta.7

- Preparation now shows only the exact Battery-guide starting values.
- Removed all "or known-stable/known-working value" alternatives from the setup screen and setup documentation.
- Previously validated personal values are handled only through **KNOWN PASS / SKIP** during the relevant tuning stages.
- Clarified that Full Application Mode is required, matching the beta.6 startup blocker.

---

# New in v0.4.0-beta.6

- hard startup block when Applet Mode is detected
- clear on-screen Full Memory Mode launch instructions
- no Wizard state/guide/test access until launched as an Application
- beta.5 dynamic VMIN probe and known-result shortcuts retained

---

# New in v0.4.0-beta.5

## Known-result shortcuts

If a value was already tested before using the Wizard, you do not have to repeat every stress test.

During any built-in test stage:

- **A** — run the built-in test normally
- **+** — **KNOWN PASS / SKIP**: accept the current test/value as already known stable
- **X** — **KNOWN FAIL / SKIP**: record the current test/value as a known failure

These shortcuts deliberately bypass the built-in stress test. Use them only for values you already trust from previous testing.

**Exception:** the dynamic VMIN floor-probe stages are measurements, not PASS/FAIL stability tests. There, `A` performs the required measurement, `+` performs the same measurement for convenience, and `X` is disabled.

## Dynamic CPU Low VMIN detection

The frequency where Low VMIN stops controlling CPU voltage is **not assumed to be identical on every Switch**.

Horizon OC builds the Mariko CPU voltage curve from the CPU's own Speedo data, the selected CPU voltage table and CPU UV tuning, then clamps low-voltage entries to Low VMIN. Because of that, the VMIN-to-normal-curve crossover can differ between consoles/settings.

After the Wizard finds a Low VMIN candidate it performs a short ascending sweep:

**510 -> 612 -> 714 -> 816 -> 918 -> 1020 MHz**

GPU remains **384 MHz** and RAM remains **1331.2 MHz**.

At each step the Wizard verifies CPU/GPU/RAM overrides and reads the **live CPU rail voltage reported by Horizon OC**. The probe takes **3 context samples** and uses the **median of valid readings** and only accepts samples while HOC reports the requested CPU clock as actually applied so a single stale HOC poll does not decide the crossover. It remembers the highest CPU frequency still operating at the configured VMIN floor (within one 5 mV PMIC step).

These sweep points are **measurement-only**. They do not each run another 1-minute stress test. The actual stability confirmation is concentrated at the highest detected floor-bound CPU clock.

As soon as the voltage has clearly risen above VMIN, higher sweep steps are no longer needed. The Wizard then runs the **1-hour Low VMIN confirmation at the highest detected floor-bound CPU clock**.

Example: if a console reports roughly 570 mV through 816 MHz but ~585 mV at 918 MHz, the long VMIN test is run at **816 MHz**, not at 510 and not unnecessarily at 1020.

Lower CPU clocks on the same voltage floor are computationally less demanding, but normal Home/Sleep/Wake/game transitions should still be checked afterward.

---

# Crash / reboot detection

Before every built-in test, the Wizard saves a persistent `testRunning` marker.

If the console freezes, crashes or reboots during a test, the marker remains set. On the next launch the Wizard asks whether the previous test crashed:

- **YES** — count it as FAIL and use the safer recovery path
- **NO** — treat it as a manual interruption and rerun the same test

Cancelling a running test with **B** does not count as FAIL.

---

# The Wizard does not write Horizon OC tuning values

The Wizard reads Horizon OC context data for clocks, overrides and the current CPU rail voltage, but it does **not** write UV/voltage settings and does **not** edit `hoc.kip`.

Horizon OC remains the place where tuning values are changed.

Progress is stored at:

`/switch/HOC-Undervolting-Wizard/state.ini`

Final results are stored at:

`/switch/HOC-Undervolting-Wizard/results.txt`

---

# Installation

## Requirements

- Nintendo Switch **Mariko / Switch OLED**
- Atmosphere CFW
- Horizon OC installed and working
- Hekate strongly recommended for boot-failure recovery

The Wizard requires Homebrew Menu **title takeover / Full Application Mode**. Applet Mode is blocked at startup.

## Install

1. Download `HOC-Undervolting-Wizard.nro` from the latest GitHub release. For beta.8 this is the final required manual update; later builds can be installed by the in-app updater.
2. Create:

   `/switch/HOC-Undervolting-Wizard/`

3. Copy the NRO to:

   `/switch/HOC-Undervolting-Wizard/HOC-Undervolting-Wizard.nro`

4. Boot Atmosphere and start the Wizard from Homebrew Menu.

An old state at `/switch/HOC-Battery-Wizard/state.ini` is automatically imported when no new state file exists yet.

---

# Safe boot recovery

Keep a Hekate CFW entry that does **not** load Horizon OC / `hoc.kip`.

If a tuning value prevents normal CFW from booting:

1. Boot Hekate.
2. Start CFW without Horizon OC / `hoc.kip`.
3. Open Horizon OC.
4. Restore the previous known-good value shown by the Wizard.
5. Save KIP.
6. Reboot normally.
7. Continue validation.

---

# Battery starting setup

Prepare the Battery profile before tuning using the exact guide starting values below. If you already know stable values, use the Wizard's KNOWN PASS / SKIP controls during the corresponding tuning stages instead of changing the starting baseline.

## Horizon OC

### Safety

- **Uncapped Clocks: OFF**

### RAM

- **HP Mode: OFF**
- **RAM Max Clock: 1600 MHz**
- **VDD2: 1175 mV**
- **VDDQ: 600 mV**

### CPU

- **CPU Max Clock: lowest selectable value**
  - current Mariko HOC builds show **1963 MHz** as the lowest selectable CPU Max Clock
- **CPU UV Table: 1683 MHz Tbreak**
- **Low UV: 0**
- **High UV: 0**
- **Low VMIN: 620 mV**
- **High VMIN: 750 mV**

## HOC Toolkit

- **CPU Boost Clock: lowest selectable value**
  - stock Nintendo Boost target used by this workflow is **1785 MHz**

After changing persistent HOC/Toolkit settings:

**Save KIP -> reboot CFW -> reopen the Wizard**

---

# Wizard tuning order

1. **CPU Low UV**
   - 1020 / 384 / 1331.2
   - +1 UV level per search step
   - 1-minute search, then 1-hour candidate confirmation

2. **CPU Low VMIN**
   - conservative start: 620 mV
   - -5 mV per search step
   - hard Wizard floor: **570 mV**
   - quick boundary search at **510 / 384 / 1331.2**
   - dynamic floor sweep at 510/612/714/816/918/1020
   - 1-hour confirmation at the highest clock still actually on the VMIN floor
   - then verify Home, Sleep/Wake, game launch/close

3. **RAM VDDQ**
   - 1785 / 76.8 / 1600
   - Wizard search interval: **10 mV**
   - Horizon OC itself exposes 5 mV VDDQ steps, so one Wizard step equals two HOC UI steps
   - 1-minute search, then 1-hour confirmation

4. **RAM VDD2**
   - 1785 / 76.8 / 1600
   - **12.5 mV** per step
   - 1-minute search, then 1-hour confirmation

5. **Final VDDQ + VDD2 together at Boost clocks**
   - 1785 / 76.8 / 1600
   - Memtester for 1 hour
   - if it fails, first try **VDDQ +10 mV**
   - if that still fails, restore VDDQ and try **VDD2 +12.5 mV**

6. **RAM at normal handheld clocks**
   - 1020 / 384 / 1331.2
   - Memtester for 1 hour

7. **CPU High UV**
   - 1785 / 76.8 / 1600
   - +1 UV level per search step
   - 1-minute search, then 1-hour confirmation

8. **High UV + final RAM voltages**
   - 1785 / 76.8 / 1600
   - combined CPU + RAM test for 1 hour
   - if it fails, make High UV one level safer before blaming RAM rails

9. **Final normal handheld validation**
   - 1020 / 384 / 1331.2
   - CPU 1 hour
   - RAM 1 hour
   - GPU 1 hour

10. **Final Nintendo Boost validation**
    - 1785 / 76.8 / 1600
    - CPU 1 hour
    - RAM 1 hour
    - combined CPU + RAM 1 hour

11. **Final real-world validation**
    - remove Temporary Overrides
    - use Home, loading, Sleep/Wake and CPU Boost transitions normally
    - play **The Legend of Zelda: Tears of the Kingdom** for at least 1 hour

---

# Search increments / limits

- CPU Low UV: **+1 level**
- CPU High UV: **+1 level**
- CPU Low VMIN: **-5 mV**, minimum **570 mV**
- RAM VDDQ Wizard search: **-10 mV**
- RAM VDD2: **-12.5 mV**

Horizon OC currently exposes VDDQ in 5 mV increments; the Wizard deliberately uses a coarser 10 mV search to keep the Battery workflow shorter.

---

# Controls

Normal built-in test stages:

- **A** — start built-in test
- **+** — known PASS / skip test
- **X** — known FAIL / skip test
- **Y** — DID NOT BOOT on quick-search stages
- **B** — exit and save progress
- **Minus** — reset Wizard progress

During a running stress test:

- **B** — cancel without recording PASS or FAIL

After an interrupted/crashed test is detected:

- **A** — previous test crashed; record FAIL
- **X** — it was interrupted manually; rerun it

---

# Results and Performance Modes

When the workflow is complete, the Wizard writes:

`/switch/HOC-Undervolting-Wizard/results.txt`

It contains:

- CPU Low UV
- CPU Low VMIN
- dynamically detected highest Low VMIN floor clock when available
- RAM VDDQ
- RAM VDD2
- CPU High UV

Use the final values in:

`Performance Modes -> Save Settings -> as Battery Mode`

The Wizard intentionally does not transfer persistent HOC settings automatically.

---

# License and source availability

**HOC Undervolting Wizard v0.4 is free software licensed under GNU GPL version 2 only (`GPL-2.0-only`).**

GPLv2 CPU/RAM test code is incorporated into the executable.

- Complete project license: [`LICENSE`](LICENSE)
- Upstream authors, source paths, modification notes and permissive-library notices: [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md)

The built-in test screen displays the active engine's credits and GPL/no-warranty notice.

When distributing an NRO, the corresponding complete buildable source must remain available under GPLv2. The intended release model is to publish the NRO and its source from this same repository.

### Stress-NX provenance

The Wizard does **not** copy code from an unidentified/unlicensed standalone Stress-NX repository. Matrixprod/Hanoi is sourced from the **GPLv2 Horizon-OC / Benchmark Toolbox** source tree, which credits Stress-NX to Lineon.

### memtester provenance

The memory algorithms are from **memtester v4**. The Switch runner is adapted from Horizon-OC / Benchmark Toolbox.

---

# Building from source

Most users should use the prebuilt NRO release.

Developers need devkitPro / devkitA64, libnx, deko3d and `uam`:

```bash
export DEVKITPRO=/opt/devkitpro
make
```

Output:

`HOC-Undervolting-Wizard.nro`

GitHub Actions builds the NRO automatically on pushes and pull requests.

---

# Safety notes

Undervolting stability differs from console to console. A value that works on one Switch may fail on another.

During deliberately unstable RAM testing, avoid installing/updating software or copying important files. RAM instability can corrupt data before an application reports a mismatch.

The built-in tests improve repeatability, but cannot prove absolute stability. Keep the final normal-use and gameplay validation.

## Credits summary

- **Lineon** — Stress-NX / Matrixprod lineage
- **Horizon-OC / Benchmark Toolbox contributors** — GPLv2 CPU and memtester integration source and `hoc:clk` interfaces
- **Simon Kirby** — original memtester work
- **Charles Cazabon** — memtester v2/v4 rewrite
- **fincs / devkitPro** — deko3d
- **switchbrew / libnx authors** — libnx

See `THIRD_PARTY_LICENSES.md` for full notices.
