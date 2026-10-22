# HOC Undervolting Wizard

A step-by-step Nintendo Switch homebrew assistant for finding stable and efficient **Horizon OC undervolting settings** on **Mariko / Switch OLED**.

This project is designed as a companion to **Performance Modes**:

https://github.com/retrotendo/Ultrahand-Performance-Modes

Use the wizard to find and validate the lowest stable CPU/RAM voltage settings for your own console, then save those proven values into the **Battery profile** used by Performance Modes.

The wizard can also be used independently for Horizon OC tuning.

## v0.3 — built-in stability tests

The wizard now contains its own timed stability tests. You no longer need to leave the wizard and launch StressNX, MemTester or a separate GPU test for the normal guided workflow.

Built-in tests include:

- **CPU Verify Stress** — multi-threaded deterministic matrix/integer workload with automatic result verification;
- **RAM Pattern / Mismatch Test** — repeated large-memory write/read patterns with automatic mismatch detection;
- **Combined CPU + RAM Stress** — CPU verification and RAM pattern testing at the same time;
- **GPU Compute / Memory Stress** — deko3d compute-shader workload with GPU-buffer verification;
- **1-minute boundary searches** and **1-hour validation runs** with an on-screen timer and progress display.

A successful timed test is recorded as **PASS automatically**. A detected calculation error, RAM mismatch or GPU execution/verification error is recorded as **FAIL automatically**.

The final real-world gameplay validation remains manual because a game cannot run in the foreground at the same time as the wizard.

## Crash / reboot detection

Before every built-in test starts, the wizard saves a persistent `testRunning` marker to the SD card.

If the console freezes, crashes or reboots during a stress test, the marker remains set. On the next start the wizard asks whether the previous test crashed:

- **YES** — count the unfinished test as FAIL and continue with the safer recovery path;
- **NO** — treat it as a manual interruption and offer the same test again.

Cancelling a running test with **B** does **not** count as FAIL.

## Important: the wizard still does NOT control Horizon OC

**This app never writes Horizon OC values and never edits `hoc.kip`.**

All UV/voltage changes and test clock overrides are still set manually by the user inside Horizon OC. The wizard only manages the workflow, runs the stability tests, records results, and remembers the last known-good values.

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

For the RAM tests, launching Homebrew Menu through **title takeover / full application mode** is recommended so the wizard has more memory available. The RAM test automatically falls back to a smaller allocation if necessary and displays how much RAM is being tested per pass.

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

The wizard now uses:

`/switch/HOC-Undervolting-Wizard/`

If a new `state.ini` does not exist but the old beta state is still present at:

`/switch/HOC-Battery-Wizard/state.ini`

v0.3 automatically imports that old state on first start.

---

# Safe boot recovery

An unstable HOC value can prevent the normal CFW configuration from booting. Keep a **Hekate CFW entry that does not load Horizon OC / `hoc.kip`**.

If a value does not boot:

1. Power off the Switch.
2. Boot Hekate.
3. Start the safe CFW entry without `hoc.kip`.
4. Open HOC Undervolting Wizard and choose **DID NOT BOOT**.
5. The wizard shows the last known-good value to restore.
6. Open Horizon OC, restore that value and **Save KIP**.
7. Reboot normally.
8. Run the required 1-hour built-in validation.

---

# Normal workflow

A typical tuning step is now:

1. Open HOC Undervolting Wizard.
2. Read the next HOC value and required CPU/GPU/RAM override clocks.
3. Exit with **B** if needed; progress is already saved.
4. Set the requested value in Horizon OC.
5. **Save KIP** and reboot.
6. Set the requested clock overrides.
7. Reopen HOC Undervolting Wizard.
8. Press **A — START BUILT-IN TEST**.
9. The wizard runs the test, timer and verification automatically.
10. PASS/FAIL is recorded automatically and the wizard calculates the next step.

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

Quick searches run for **1 minute**. At the first failure, the previous working value becomes the candidate for a **1-hour validation**. If the long validation fails, the wizard moves one step safer and repeats the validation.

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
- **Minus** — reset wizard progress

During a built-in stress test:

- **B** — cancel without recording PASS or FAIL

After a crash/reboot is detected on the next launch:

- **A** — yes, the previous test crashed; record FAIL
- **X** — no, it was interrupted manually; rerun it

---

# Using the results with Performance Modes

After all validation stages pass, the wizard writes:

`/switch/HOC-Undervolting-Wizard/results.txt`

It contains the final validated values for:

- CPU Low UV
- CPU Low VMIN
- RAM VDDQ
- RAM VDD2
- CPU High UV

Use these values when preparing/saving the **Battery profile** in Performance Modes.

The wizard intentionally does not transfer the settings automatically. Horizon OC remains the single place where voltage/UV values are changed.

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

## Credits / implementation notes

The GPU test uses **deko3d** and the devkitPro **uam** shader tool. The deko3d setup follows the public patterns documented in the switchbrew/devkitPro examples. The wizard's CPU/RAM verification routines are purpose-built for this project; GPL test code from external stress-test projects is not embedded in this MIT-licensed application.
