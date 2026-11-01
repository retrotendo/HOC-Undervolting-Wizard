# HOC Undervolting Wizard

A guided Nintendo Switch homebrew assistant for finding and validating efficient **Horizon OC undervolting settings** on **Mariko hardware** (Switch V2, Lite and OLED).

The Wizard was built around the Battery-profile workflow used by **Performance Modes**:

https://github.com/retrotendo/Ultrahand-Performance-Modes

It guides the user through CPU Low UV, CPU Low VMIN, RAM VDDQ, RAM VDD2 and CPU High UV tuning, performs automatic clock setup for built-in tests, checks that the active Horizon OC configuration still matches the Wizard state, and records the final validated values.

> This README reflects the current **v0.4.0-beta.53** workflow. Older beta-by-beta notes are available in GitHub Releases.

---

## What the Wizard does

- Detects the installed Mariko RAM profile and chooses the appropriate VDDQ starting point.
- Guides the user through a known Preparation baseline.
- Can use the recommended baseline, import the user's current compatible settings as the baseline, or automatically apply the recommended Preparation values.
- Finds the highest usable **CPU Low UV** level.
- Finds the lowest usable **CPU Low VMIN**, down to the Wizard safety floor of **570 mV**.
- Automatically scans CPU voltage at **510 / 612 / 714 / 816 / 918 / 1020 MHz**.
- Finds and validates efficient **RAM VDDQ** and **RAM VDD2** values.
- Finds the highest usable **CPU High UV** level.
- Runs built-in CPU, RAM and combined validation workloads.
- Automatically sets and restores the Temporary Overrides required by built-in tests.
- Detects crashes/reboots that interrupt a running validation.
- Continuously checks all five tuned values against the state the Wizard expects.
- Provides a final real-world stability recommendation using **The Legend of Zelda: Tears of the Kingdom**.
- Writes the final results to `results.txt` for later use with the Battery profile.

The Wizard is intentionally conservative: it changes one tuning domain at a time and keeps a last-known-good value for recovery.

---

## Requirements

- Nintendo Switch **Mariko** hardware: V2, Lite or OLED
- Atmosphere CFW
- Horizon OC installed and working
- Homebrew Menu in **Full Memory / Application Mode**
- Hekate strongly recommended for boot-failure recovery

The Wizard is not intended for Erista/V1 consoles.

### Full Memory Mode is required

Applet Mode is blocked at startup because the integrated stress tests need Full Memory mode.

Launch hbmenu through title takeover:

1. Hold **R** while starting an installed game.
2. Keep holding **R** until hbmenu opens.
3. Start **HOC Undervolting Wizard**.

---

## Installation

1. Download `HOC-Undervolting-Wizard.nro` from the latest GitHub release.
2. Create:

   ```text
   /switch/HOC-Undervolting-Wizard/
   ```

3. Copy the NRO to:

   ```text
   /switch/HOC-Undervolting-Wizard/HOC-Undervolting-Wizard.nro
   ```

4. Boot Atmosphere and launch the Wizard through hbmenu in Full Application Mode.

An old state file from:

```text
/switch/HOC-Battery-Wizard/state.ini
```

is imported automatically when no current state exists.

---

## In-app updater

The Wizard can check this repository for a newer release at startup.

If an update is available:

- the current and available versions are shown,
- installation requires explicit confirmation,
- the new NRO is downloaded to a temporary file,
- the release SHA256 is downloaded and verified,
- the current NRO is preserved as a `.bak` recovery copy,
- the verified NRO replaces the installed build only after validation succeeds.

Update-check or network failures do not prevent the installed Wizard from starting.

---

# Guided workflow

The graphical guide uses one consistent layout:

- **Left:** what the current step is doing, why it is being done, and the available choices.
- **Right:** the concrete action the user has to perform now.
- **ACTUAL ACTIVE VALUES:** the five tuned values currently reported by Horizon OC.

If an active value does not match the current Wizard state it is highlighted **red**.

Decision questions such as post-reboot boot status are shown as dedicated modal dialogs instead of being mixed into normal instruction pages.

---

## 1. Hardware Detection

Before tuning starts, the Wizard reads Horizon OC hardware information and identifies the installed Mariko RAM profile.

The page shows only the useful tuning information:

- detected memory module,
- VDDQ starting voltage,
- expected RAM OC range as a guide estimate.

Unknown or unsupported RAM information is not silently guessed.

---

## 2. Preparation

Before tuning starts, the Wizard needs a known baseline.

You can:

- **Check settings** and set the recommended values manually,
- **Use my current settings as baseline**, or
- **Set values automatically + reboot**.

### Recommended Preparation values

#### Horizon OC — General

- Uncapped Clocks: **OFF**

#### Horizon OC — RAM Settings

- HP Mode: **OFF**
- RAM Max: **1600 MHz**
- VDD2: **1175 mV**
- VDDQ: selected automatically from the detected RAM profile

#### Horizon OC — CPU Settings

- CPU Max: **1963 MHz**
- Low VMIN: **620 mV**
- High VMIN: **750 mV**
- UV Table: **1683 MHz Tbreak**
- Low UV: **0**
- High UV: **0**

#### HOC Toolkit

- CPU Boost: **1785 MHz**

The Preparation page shows **SET** and **ACTIVE** side by side. Mismatching ACTIVE values are highlighted red.

### Use my current settings as baseline

A compatible existing configuration can be imported instead of resetting the tuned values to the recommended defaults.

The Wizard then continues from those imported values and searches from there.

### Automatic setting support

With the currently supported Horizon OC interface, the Wizard can automatically apply:

- the complete recommended Preparation baseline,
- CPU Low UV candidates,
- CPU Low VMIN candidates.

The current automatic persistent-setting path is designed for **Horizon OC 2.5.1**. RAM VDDQ, RAM VDD2 and CPU High UV are still changed manually in Horizon OC when the Wizard asks for them.

---

## 3. CPU Low UV

The Wizard searches upward through Low UV levels to find the highest value that can boot normally.

- Search direction: **higher Low UV index = more aggressive undervolt**
- Step size: **+1 level**
- Wizard maximum: **8**

For each new persistent candidate:

1. Set or automatically apply the requested value.
2. Reboot normal CFW.
3. Reopen the Wizard.
4. Confirm whether the console booted normally.

If a candidate is known unstable, the Wizard returns to the previous last-good value.

After the boot limit is found, the Wizard performs an automatic CPU voltage scan and validates the detected voltage regions.

---

## 4. CPU Low VMIN

Low VMIN is searched downward from the current baseline.

- Search direction: **lower voltage = more aggressive undervolt**
- Step size: **10 mV**
- Wizard minimum: **570 mV**

The Wizard deliberately stops at 570 mV. Going lower is outside this guided workflow because very low VMIN values can introduce Sleep / Standby / Wake issues even when short stress tests appear stable.

After the boot boundary is found, the automatic voltage scan runs.

### Automatic CPU voltage scan

The Wizard temporarily uses:

- GPU: **384 MHz**
- RAM: **1331.2 MHz**
- CPU: **510 → 612 → 714 → 816 → 918 → 1020 MHz**

At every CPU frequency it:

1. discards **2 settling measurements**,
2. records **9 valid voltage samples**,
3. uses the median,
4. retries once if the sample set is unusually noisy,
5. groups readings into HOC's 5 mV voltage regions.

The user's previous Temporary Overrides are restored afterward.

Only the **highest frequency in each distinct voltage region** is selected for stability validation. Each selected region is currently tested for **1 minute**.

This avoids repeatedly stress-testing several lower clocks that are running at the same measured voltage.

---

## 5. RAM VDDQ

VDDQ is searched downward one domain at a time.

- Step size: **10 mV**
- Wizard minimum: **400 mV**
- Candidate test: **1 minute**
- Final standalone validation: **30 minutes**

The Wizard automatically applies and verifies the required CPU/GPU/RAM Temporary Overrides for the built-in test.

---

## 6. RAM VDD2

VDD2 is searched after VDDQ has been established.

- Step size: **12.5 mV**
- Wizard minimum: **912.5 mV**
- Candidate test: **1 minute**

The final VDDQ + VDD2 pair is then validated together for **1 hour**.

If the pair fails, the recovery logic changes only one rail at a time so the failing domain can be identified instead of making several voltage changes at once.

---

## 7. Handheld CPU/RAM validation

Before CPU High UV tuning, the Wizard validates the tuned low-side CPU/RAM configuration at the normal handheld operating state:

- CPU: **1020 MHz**
- GPU: **384 MHz**
- RAM: **1331.2 MHz**

This validation runs for **1 hour**.

---

## 8. CPU High UV

CPU High UV is searched upward at Nintendo Boost clocks.

- Search direction: **higher High UV index = more aggressive undervolt**
- Step size: **+1 level**
- Wizard maximum: **13**
- Candidate test: **1 minute**

The Boost test state is:

- CPU: **1785 MHz**
- GPU: **76.8 MHz**
- RAM: **1600 MHz**

After the search, the Wizard performs the final Boost CPU/RAM validation sequence, including a **1-hour CPU memtester/RAM validation** followed by the **1-hour combined CPU + RAM validation** used by the current workflow.

---

## 9. Real-World Stability Check

The final real-world section is a **recommendation**, not another built-in automated stress test.

For final confirmation, play:

**The Legend of Zelda: Tears of the Kingdom**

for at least **1 hour**.

Include normal gameplay, battles, fast travel, loading screens and Sleep/Wake transitions. Watch for crashes, freezes or unexpected reboots.

### If instability occurs

Change **only ONE setting at a time**, by one step, then play again.

Recommended order:

1. **Low VMIN** — raise voltage one step
2. **VDDQ** — raise voltage one step
3. **VDD2** — raise voltage one step
4. **CPU High UV** — one step less aggressive
5. **CPU Low UV** — one step less aggressive

If the problem still appears, restore that setting to its previous value **before** trying the next setting.

Do not change multiple domains at once. The point is to identify which tuned value actually causes the instability.

---

# Safety-state guard

One of the most important current features is the all-domain state guard.

During an active tuning run, the Wizard compares all five tunable values against the exact state it expects:

- CPU Low UV
- CPU Low VMIN
- RAM VDDQ
- RAM VDD2
- CPU High UV

The expected state follows either:

- the recommended Preparation baseline, or
- the values imported with **Use my current settings as baseline**,

and then follows each last-known-good result as tuning progresses.

The one value the Wizard currently asks you to change is treated as the intended target. An unrelated accidental change is highlighted red immediately.

The same full check is performed before:

- automatic CPU voltage scans,
- automatic region validation,
- every built-in stability/validation test,
- rebooting after a persistent setting change.

If anything is wrong, progression is blocked with **Unexpected setting change** until the red values are restored.

This is specifically intended to prevent accidentally testing two changed domains at the same time.

---

# Built-in test engine

The Wizard integrates several stress workloads.

### CPU — Matrixprod + Hanoi Verify

Derived from the GPLv2 Horizon-OC / Benchmark Toolbox implementation. Hanoi verification can detect calculation errors instead of relying only on whether the console crashes.

Benchmark Toolbox credits the Stress-NX lineage to **Lineon**.

### RAM — memtester v4

Includes the established memtester algorithms such as Stuck Address, Random Value, XOR/SUB/MUL/DIV, Sequential Increment, Solid Bits, Checkerboard, Bit Spread, Bit Flip and Walking Ones/Zeroes.

memtester credits **Simon Kirby** and **Charles Cazabon**. The Switch runner is adapted from Horizon-OC / Benchmark Toolbox under GPLv2.

### Combined CPU + RAM

Runs CPU and RAM stress together to expose failures that may not appear when the domains are tested independently.

### GPU — deko3d Compute / Memory Stress

Project-original deko3d compute/memory workload with CPU-side output verification.

---

## Automatic Temporary Overrides

The user does not need to manually manage Temporary Overrides for built-in tests.

Before a test, the Wizard:

1. saves the existing CPU/GPU/RAM Temporary Overrides,
2. applies the clocks required by the current test,
3. reads them back and verifies that they are active,
4. blocks the test if setup or verification fails,
5. restores the previous overrides afterward.

No test result is accepted when the requested clock setup could not be verified.

---

## Known-result shortcuts

Search and validation pages intentionally use different wording.

### Candidate search

When finding a new boundary:

- **Known stable** — continue in the search direction
- **Known unstable** — return toward the last-good value

For Low UV / High UV this means lowering the UV index after an unstable result.

For Low VMIN / VDDQ / VDD2 this means raising the voltage back toward the last-good value.

### Validation

Long/final validation pages use:

- **Known PASS / Skip validation test**

There is no generic KNOWN FAIL shortcut on the long validation pages. A real built-in failure is recorded by the test engine, and crashes/reboots are handled through interrupted-test detection.

Use skip options only for results you already trust from previous testing.

---

# Crash / reboot detection

Before every built-in test, the Wizard stores a persistent `testRunning` marker.

If the console freezes, crashes or reboots while the test is running, the marker remains set. On the next launch the Wizard asks whether the previous test failed because of the crash/reboot.

- **YES** — count it as FAIL and follow the safer recovery path
- **NO** — treat it as a manual interruption and run the same test again
- **B** during a running test cancels it without recording PASS or FAIL

---

# Persistent settings and reboots

Persistent tuning values remain Horizon OC settings.

The Wizard can verify the active/persistent values and, on supported Horizon OC 2.5.1 paths, automatically apply the Preparation baseline and CPU Low UV / Low VMIN values.

For manually changed values, the Wizard waits until the requested setting is detected before allowing the workflow to continue.

When a persistent change requires a reboot:

1. the requested value is verified,
2. the Wizard shows a **REBOOT REQUIRED** modal,
3. the console can be restarted directly from the Wizard,
4. after normal CFW boots, reopen the Wizard,
5. confirm whether the new value booted normally.

If normal CFW does not boot, use the safe recovery path below.

---

# Safe boot recovery

Keep a Hekate boot entry that starts CFW **without Horizon OC / `hoc.kip`**.

If an undervolt prevents normal CFW from booting:

1. Boot Hekate.
2. Start **CFW No OC**.
3. Restore the previous known-good value in Horizon OC.
4. Reboot normal CFW.
5. Open the Wizard again and continue.

The Wizard keeps the last-known-good value so the recovery target remains clear.

---

# Results

Wizard progress is stored at:

```text
/switch/HOC-Undervolting-Wizard/state.ini
```

Final results are written to:

```text
/switch/HOC-Undervolting-Wizard/results.txt
```

The result file includes:

- detected RAM module,
- VDDQ starting point,
- CPU UV table,
- final CPU Low UV,
- final CPU Low VMIN,
- final RAM VDDQ,
- final RAM VDD2,
- final CPU High UV,
- detected CPU voltage regions and representative clocks when available.

These are the values intended for the **Performance Modes Battery Mode** workflow.

### Optional: Save Settings as Battery Profile in Performance Modes

After the final real-world guidance, the Wizard opens a separate confirmation:

**Save Settings as Battery Profile in Performance Modes?**

- **A — Save Settings as Battery Profile**
- **X — Skip**
- **B — Back** to the final real-world guidance page

Nothing is exported automatically. Choosing **A** performs the same profile copy used by `Performance Modes -> Save Settings -> as Battery Mode`:

- `/config/horizon-oc/config.ini` -> `/switch/.packages/Performance Modes/Battery/config.ini`
- `/atmosphere/kips/hoc.kip` -> `/switch/.packages/Performance Modes/Battery/hoc.kip`
- `/SaltySD/plugins/ReverseNX-RT/` -> `/switch/.packages/Performance Modes/Battery/ReverseNX-RT/`

The Wizard does **not** switch or mark the active Performance Modes profile. It only saves the current settings as the Battery profile. If Performance Modes is not installed, the Wizard reports that and does not invent a new installation.

---

# Search limits

The current Wizard limits are deliberately bounded:

| Setting | Direction | Step | Wizard limit |
| --- | --- | ---: | ---: |
| CPU Low UV | higher index | +1 | 8 |
| CPU Low VMIN | lower voltage | -10 mV | 570 mV minimum |
| RAM VDDQ | lower voltage | -10 mV | 400 mV minimum |
| RAM VDD2 | lower voltage | -12.5 mV | 912.5 mV minimum |
| CPU High UV | higher index | +1 | 13 |

Reaching a Wizard limit does not mean the hardware could never go further. It means the guided workflow intentionally stops there and moves to validation.

---

# Controls

Controls change slightly with the current page, but the general model is:

- **A** — check / continue / start the requested test
- **Y** — automatic persistent setting where supported
- **+** — known stable / known PASS shortcut where available
- **X** — known unstable during boundary search, or negative answer in decision dialogs
- **B** — back / exit without discarding saved Wizard progress
- **Minus** — reset Wizard progress

A reset also clears the one-time disclaimer acceptance so the safety notice is shown again when a new tuning run starts.

---

# Safety

Undervolting and overclocking are experimental. Stability differs from console to console.

Possible consequences of unstable settings include:

- crashes,
- freezes,
- boot failures,
- save/data corruption,
- unexpected reboots,
- potentially hardware damage.

Use the Wizard at your own risk. Built-in stress tests improve repeatability but cannot prove absolute stability.

During deliberately unstable RAM testing, avoid installing/updating software or copying important files. RAM instability can corrupt data before a test reports a mismatch.

The final real-world check is therefore still recommended even after all built-in tests pass.

---

# Building from source

Most users should use the prebuilt NRO from GitHub Releases.

Developers need devkitPro / devkitA64, libnx, deko3d and the project build dependencies.

```bash
export DEVKITPRO=/opt/devkitpro
make
```

Output:

```text
HOC-Undervolting-Wizard.nro
```

GitHub Actions also builds the NRO automatically.

---

# License and credits

**HOC Undervolting Wizard v0.4 is free software licensed under GNU GPL version 2 only (`GPL-2.0-only`).**

GPLv2 CPU/RAM test code is incorporated into the executable.

- Complete project license: [`LICENSE`](LICENSE)
- Full upstream attribution and notices: [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md)

Credits summary:

- **Lineon** — Stress-NX / Matrixprod lineage
- **Horizon-OC / Benchmark Toolbox contributors** — GPLv2 CPU/memtester integration and HOC interfaces
- **Simon Kirby** — original memtester work
- **Charles Cazabon** — memtester v2/v4 rewrite
- **fincs / devkitPro** — deko3d
- **switchbrew / libnx authors** — libnx

When distributing an NRO, the corresponding complete buildable source must remain available under GPLv2.
