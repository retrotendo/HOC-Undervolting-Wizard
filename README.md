# HOC Undervolting Wizard

A step-by-step Nintendo Switch homebrew assistant for finding stable and efficient **Horizon OC undervolting settings** on **Mariko / Switch OLED**.

This project is designed as a companion to **Performance Modes**:

https://github.com/retrotendo/Ultrahand-Performance-Modes

The idea is simple: use **HOC Undervolting Wizard** to find and validate the lowest stable CPU/RAM voltage settings for your own console, then save those proven values into the **Battery profile** used by Performance Modes.

The wizard can also be used independently if you only want help tuning Horizon OC.

## What this app does

HOC Undervolting Wizard guides you through the complete undervolting process and remembers where you are between reboots.

It tells you:

- which Horizon OC value to change next;
- which CPU/GPU/RAM override clocks to use for the test;
- which stress test to run;
- whether the next test should be a quick boundary search or a 1-hour validation;
- what to restore after a failed test or boot failure.

After every test you simply return to the wizard and choose:

- **A — PASS**
- **X — FAIL**
- **Y — DID NOT BOOT**

The next step is calculated automatically.

## Important: the wizard does NOT control Horizon OC

**This app never writes Horizon OC values and never edits `hoc.kip`.**

All voltage and UV changes are made manually by the user inside Horizon OC. This is intentional: the wizard is a tuning assistant, not an automatic overclock/undervolt tool.

Progress is saved automatically before/through reboots and when exiting the app.

State file:

`/switch/HOC-Undervolting-Wizard/state.ini`

Final results:

`/switch/HOC-Undervolting-Wizard/results.txt`

Older beta progress from `/switch/HOC-Battery-Wizard/state.ini` is automatically imported the first time the renamed app starts.

---

# Installation

## Requirements

The current wizard is intended for:

- Nintendo Switch **Mariko / Switch OLED**
- Atmosphere CFW
- Horizon OC installed and working
- Hekate strongly recommended for boot-failure recovery

For the guided stability tests you should also have the test tools used by the wizard, including **StressNX / Matrixprod**, **Benchmark Toolbox / MemTester**, **CPU-Memtester**, and a GPU stress test.

Performance Modes is not technically required to run the wizard, but this wizard was created specifically to help find safe undervolting values for its Battery profile.

## Install the NRO

1. Download `HOC-Undervolting-Wizard.nro`.
2. On the Switch SD card create:

   `/switch/HOC-Undervolting-Wizard/`

3. Copy the NRO to:

   `/switch/HOC-Undervolting-Wizard/HOC-Undervolting-Wizard.nro`

Your SD card should look like this:

```text
SD:/
└── switch/
    └── HOC-Undervolting-Wizard/
        └── HOC-Undervolting-Wizard.nro
```

4. Boot Atmosphere.
5. Open the Homebrew Menu.
6. Start **HOC Undervolting Wizard**.

No separate installer is required.

## Before starting the undervolting process

Because an unstable HOC value can prevent the normal CFW configuration from booting, create or keep a **Hekate CFW entry that does not load Horizon OC / `hoc.kip`**.

If a tested value does not boot, the wizard will instruct you to:

1. power off the Switch;
2. boot Hekate;
3. start the safe CFW entry without `hoc.kip`;
4. open Horizon OC;
5. restore the last known-good value shown by the wizard;
6. Save KIP;
7. reboot normally;
8. continue with the required 1-hour validation.

The wizard state survives this process.

---

# Normal workflow

A typical step looks like this:

1. Open **HOC Undervolting Wizard**.
2. Read the next value it asks you to test.
3. Exit the wizard with **B** if needed — progress is already saved.
4. Open Horizon OC and enter the requested value manually.
5. **Save KIP**.
6. Reboot the Switch.
7. Set the CPU/GPU/RAM overrides shown by the wizard.
8. Run the requested stability test.
9. Open HOC Undervolting Wizard again.
10. Press **PASS**, **FAIL**, or **DID NOT BOOT**.
11. Follow the next instruction.

You do not need to remember the previous voltage yourself; the wizard stores the last known-good value.

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
10. One-hour real-world validation

The wizard uses quick tests to find the stability boundary. Once the first failure is found, the previous working value becomes the candidate for a **1-hour validation**. If that long test fails, the wizard moves one step safer and repeats the validation.

---

# Starting baseline

The current Mariko/OLED workflow begins from:

- CPU UV Table: Default / Normal — not Extreme
- CPU Low UV: 0
- CPU High UV: 0
- CPU Low VMIN: 620 mV
- CPU High VMIN: 750 mV
- RAM VDDQ: 600 mV
- RAM VDD2: 1175 mV

Stock itself is treated as the known-stable baseline, so the wizard does not waste time running a stock stress test before the first undervolting change.

Current HOC search increments used by the wizard:

- CPU Low UV: +1 level
- CPU High UV: +1 level
- CPU Low VMIN: -5 mV
- RAM VDDQ: -5 mV
- RAM VDD2: -12.5 mV

---

# Controls

- **A** — PASS / continue
- **X** — FAIL
- **Y** — DID NOT BOOT during quick-search stages
- **B** — Exit; progress is automatically saved
- **Minus** — Reset all wizard progress

---

# Using the results with Performance Modes

When all validation stages pass, the wizard creates:

`/switch/HOC-Undervolting-Wizard/results.txt`

This contains the final validated values for:

- CPU Low UV
- CPU Low VMIN
- RAM VDDQ
- RAM VDD2
- CPU High UV

These are the values you can then use when preparing/saving your **Battery profile** in Performance Modes.

HOC Undervolting Wizard does not automatically transfer these settings to Performance Modes. The separation is intentional so the tuning process remains transparent and recoverable.

---

# Building from source

Most users do **not** need to compile the app themselves. Use the prebuilt NRO from a release/build artifact when available.

For developers, the project requires devkitPro / devkitA64 with libnx:

```bash
export DEVKITPRO=/opt/devkitpro
make
```

Output:

`HOC-Undervolting-Wizard.nro`

The included GitHub Actions workflow also builds the NRO automatically on every push.

---

## Safety note

Undervolting stability differs from console to console. A value that works on one Switch may fail on another. The wizard therefore does not provide a universal "best" voltage; it guides each user through testing their own hardware and validating the result before using it as a daily profile.
