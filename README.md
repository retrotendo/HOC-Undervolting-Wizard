# HOC Undervolting Wizard

A step-by-step Nintendo Switch homebrew assistant for finding stable and efficient **Horizon OC undervolting settings** on **Mariko / Switch OLED**.

This project is designed as a companion to **Performance Modes**:

https://github.com/retrotendo/Ultrahand-Performance-Modes

Use the wizard to find and validate the lowest stable CPU/RAM voltage settings for your own console, then save those proven values into the **Battery profile** used by Performance Modes.

The wizard can also be used independently for Horizon OC tuning.

## v0.4 — established open-source stress-test algorithms built in

v0.4 replaces the experimental purpose-built CPU/RAM test kernels from v0.3 with established GPLv2 test algorithms used in the Switch overclocking community.

Built-in tests now include:

- **CPU — Stress-NX Matrixprod + Hanoi Verify**
  - Matrixprod workload taken from the GPLv2 CPU stress implementation in Horizon-OC / Benchmark Toolbox;
  - the original Matrixprod algorithm is left unchanged;
  - after every Matrixprod pass the original Hanoi verification workload runs, allowing the Wizard to detect CPU calculation errors automatically;
  - Benchmark Toolbox / the Switch homebrew ecosystem credits Stress-NX to **Lineon**.

- **RAM — memtester v4 CPU Memory Test**
  - established memtester algorithms including Stuck Address, Random Value, XOR/SUB/MUL/DIV, Sequential Increment, Solid Bits, Checkerboard, Bit Spread, Bit Flip, Walking Ones and Walking Zeroes;
  - memtester credits **Simon Kirby** and **Charles Cazabon**;
  - Switch runner adapted from the GPLv2 implementation in Horizon-OC / Benchmark Toolbox;
  - RAM mismatches are detected and reported automatically.

- **Combined — Matrixprod + memtester / bandwidth burn-in**
  - CPU Matrixprod/Hanoi verification and RAM testing run together to expose failures that only appear under combined load.

- **GPU — deko3d Compute / Memory Stress**
  - project-original GPU test code using the public deko3d API;
  - GPU buffer results are checked on the CPU;
  - GPU queue errors and verification mismatches automatically fail the test.

Quick boundary tests run for **1 minute** and long validation tests run for **1 hour**, with an on-screen timer, progress information and automatic PASS/FAIL handling.

Before **every built-in test**, the Wizard reads Horizon OC's live `hoc:clk` context and verifies **all three Temporary Overrides (CPU + GPU + RAM)**. A missing or incorrect override blocks the test and shows Expected vs Current values; no tuning result is recorded until all three match.

The final real-world gameplay validation remains manual because a game cannot run in the foreground at the same time as the Wizard.

## Crash / reboot detection

Before every built-in test starts, the Wizard saves a persistent `testRunning` marker to the SD card.

If the console freezes, crashes or reboots during a stress test, the marker remains set. On the next start the Wizard asks whether the previous test crashed:

- **YES** — count the unfinished test as FAIL and continue with the safer recovery path;
- **NO** — treat it as a manual interruption and offer the same test again.

Cancelling a running test with **B** does **not** count as FAIL.

## Important: the Wizard does NOT control Horizon OC

**This app never writes Horizon OC values and never edits `hoc.kip`.**

All UV/voltage changes and test clock overrides are still set manually by the user inside Horizon OC. The Wizard manages the workflow, runs the stability tests, records results, and remembers the last known-good values.

Progress:

`/switch/HOC-Undervolting-Wizard/state.ini`

Final results:

`/switch/HOC-Undervolting-Wizard/results.txt`

---

# Installation

## Requirements

- Nintendo Switch **Mariko / Switch OLED**
- Atmosphere CFW
- Horizon OC installed and working
- Hekate strongly recommended for boot-failure recovery

**Performance Modes is optional**, but HOC Undervolting Wizard was created specifically to help find validated Battery-profile values for it.

For RAM testing, launching Homebrew Menu through **title takeover / full application mode** is strongly recommended. The integrated memtester runner maps as much available memory as possible and shows the amount being tested.

## Install the NRO

1. Download `HOC-Undervolting-Wizard.nro`.
2. Create this folder on the Switch SD card:

   `/switch/HOC-Undervolting-Wizard/`

3. Copy the NRO to:

   `/switch/HOC-Undervolting-Wizard/HOC-Undervolting-Wizard.nro`

SD layout:

```text
SD:/
└── switch/
    └── HOC-Undervolting-Wizard/
        └── HOC-Undervolting-Wizard.nro
```

4. Boot Atmosphere.
5. Open Homebrew Menu.
6. Start **HOC Undervolting Wizard**.

No installer is required.

### Updating from HOC Battery Wizard beta / v0.2

The Wizard uses:

`/switch/HOC-Undervolting-Wizard/`

If a new `state.ini` does not exist but an old beta state is still present at:

`/switch/HOC-Battery-Wizard/state.ini`

it is automatically imported on first start.

---

# Safe boot recovery

An unstable HOC value can prevent the normal CFW configuration from booting. Keep a **Hekate CFW entry that does not load Horizon OC / `hoc.kip`**.

If a value does not boot:

1. Power off the Switch.
2. Boot Hekate.
3. Start the safe CFW entry without `hoc.kip`.
4. Open HOC Undervolting Wizard and choose **DID NOT BOOT**.
5. The Wizard shows the last known-good value to restore.
6. Open Horizon OC, restore that value and **Save KIP**.
7. Reboot normally.
8. Run the required 1-hour built-in validation.

---

# Battery starting setup

Before Step 1, prepare the Battery profile once:

- HOC Toolkit / stock clock limits: **CPU Max 1785 MHz**, **CPU Boost 1785 MHz**, **GPU Max 384 MHz**, **RAM Max 1600 MHz**.
- Horizon OC: **Uncapped Clocks OFF**, **HP Mode OFF**, **RAM Max Clock 1600 MHz**, **Overwrite Boost Mode OFF**, **Auto CPU RAM OC OFF**.
- CPU baseline: **UV Table Normal**, **Low UV 0**, **High UV 0**, **Low VMIN 620 mV**, **High VMIN 750 mV**.
- RAM baseline: **VDD2 1175 mV**, **VDDQ 600 mV**.
- Per-game CPU/GPU/RAM clocks: **stock/default**.

Save/apply the Toolkit values, **Save KIP**, then **reboot CFW** before starting the tuning sequence. These are starting limits/baselines, not the final undervolted values the Wizard will discover.

---

# Normal workflow

A typical tuning step is:

1. Open HOC Undervolting Wizard.
2. Read the next HOC value and required CPU/GPU/RAM override clocks.
3. Exit with **B** if needed; progress is already saved.
4. Set the requested value in Horizon OC.
5. **Save KIP** and reboot.
6. Set the requested clock overrides.
7. Reopen HOC Undervolting Wizard.
8. Press **A — START BUILT-IN TEST**.
9. The Wizard runs the requested test and timer automatically.
10. PASS/FAIL is recorded automatically and the Wizard calculates the next step.

You can still press **X — Manual FAIL** if you see instability that the built-in verifier did not catch.

---

# Wizard order

1. CPU Low UV
2. CPU Low VMIN
3. RAM VDDQ
4. RAM VDD2
5. RAM validation at normal handheld clocks
6. CPU High UV for Nintendo Boost
7. CPU + RAM Boost validation
8. Final normal handheld CPU/RAM/GPU tests
9. Final Nintendo Boost CPU/RAM tests
10. One-hour real-world gameplay validation

Quick searches run for **1 minute**. At the first failure, the previous working value becomes the candidate for a **1-hour validation**. If the long validation fails, the Wizard moves one step safer and repeats the validation.

---

# Starting baseline

Current Mariko/OLED workflow:

- CPU UV Table: Default / Normal — not Extreme
- CPU Low UV: 0
- CPU High UV: 0
- CPU Low VMIN: 620 mV
- CPU High VMIN: 750 mV
- RAM VDDQ: 600 mV
- RAM VDD2: 1175 mV

Search increments:

- CPU Low UV: +1 level
- CPU High UV: +1 level
- CPU Low VMIN: -5 mV
- RAM VDDQ: -5 mV
- RAM VDD2: -12.5 mV

Stock is treated as the known-stable baseline, so testing starts after the first undervolt change.

---

# Controls

Normal test stages:

- **A** — start the built-in test
- **X** — manual FAIL
- **Y** — DID NOT BOOT on quick-search stages
- **B** — exit; progress is automatically saved
- **Minus** — reset Wizard progress

During a built-in stress test:

- **B** — cancel without recording PASS or FAIL

After a crash/reboot is detected on the next launch:

- **A** — yes, the previous test crashed; record FAIL
- **X** — no, it was interrupted manually; rerun it

---

# Using the results with Performance Modes

After all validation stages pass, the Wizard writes:

`/switch/HOC-Undervolting-Wizard/results.txt`

It contains the final validated values for:

- CPU Low UV
- CPU Low VMIN
- RAM VDDQ
- RAM VDD2
- CPU High UV

Use these values when preparing/saving the **Battery profile** in Performance Modes.

The Wizard intentionally does not transfer settings automatically. Horizon OC remains the single place where voltage/UV values are changed.

---

# License and source availability

**HOC Undervolting Wizard v0.4 is free software licensed under GNU GPL version 2 only (`GPL-2.0-only`).**

This is required because GPLv2 CPU/RAM test code is incorporated into the same executable.

- Complete project license: [`LICENSE`](LICENSE)
- Upstream authors, source paths, modification notes and permissive-library notices: [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md)

The built-in test screen also displays the active engine's credits and a GPL/no-warranty notice.

When distributing an NRO, the corresponding complete buildable source must remain available under GPLv2. The intended release model is to publish the NRO and its source from this same repository.

### Important Stress-NX provenance note

The Wizard does **not** copy code from an unidentified or unlicensed standalone Stress-NX repository. The Matrixprod/Hanoi implementation incorporated here is sourced from the **GPLv2 Horizon-OC / Benchmark Toolbox** source tree, which bundles these Stress-NX workloads and credits Stress-NX to Lineon.

### memtester provenance

The memory algorithms are from **memtester v4**, whose upstream project states that the v4 rewrite is Copyright (C) 2004-2020 Charles Cazabon and licensed under **GNU GPL version 2 only**. The Switch runner is adapted from Horizon-OC / Benchmark Toolbox.

---

# Building from source

Most users should use the prebuilt NRO artifact/release.

Developers need devkitPro / devkitA64, libnx, deko3d and `uam` (shader compiler):

```bash
export DEVKITPRO=/opt/devkitpro
make
```

The build compiles `source/gpu_stress.glsl` into a deko3d `.dksh` compute shader and embeds it in the NRO RomFS.

Output:

`HOC-Undervolting-Wizard.nro`

GitHub Actions builds the NRO automatically on pushes and pull requests.

---

## Safety notes

Undervolting stability differs from console to console. A value that works on one Switch may fail on another.

During deliberately unstable RAM boundary testing, avoid installing/updating software or copying important files. A RAM instability can corrupt data before an application has a chance to report a mismatch.

The built-in tests improve automation and repeatability, but they cannot prove absolute stability. Keep the final real-world validation and normal-use transition testing.

## Credits summary

- **Lineon** — Stress-NX / Matrixprod lineage
- **Horizon-OC / Benchmark Toolbox contributors** — GPLv2 Switch CPU and memtester implementations used as the integration source
- **Simon Kirby** — original memtester work
- **Charles Cazabon** — memtester v2 and v4 rewrite
- **fincs / devkitPro** — deko3d
- **switchbrew / libnx authors** — libnx

See `THIRD_PARTY_LICENSES.md` for the full notices.
