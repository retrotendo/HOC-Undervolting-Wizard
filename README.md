# HOC Battery Wizard

A standalone Nintendo Switch homebrew wizard for finding efficient **Horizon OC Battery Profile** settings on **Mariko / Switch OLED**.

## Important design rule

**This app never writes to Horizon OC and never edits `hoc.kip`.**

The user changes every HOC value manually. The wizard only:

- tells the user which value to try next;
- tells the user which CPU/GPU/RAM overrides to set;
- tells the user which Benchmark Toolbox / StressNX test to run;
- stores progress on the SD card before/through reboots and crashes;
- accepts **PASS**, **FAIL**, or **DID NOT BOOT**;
- calculates the next value or recovery step;
- saves the final results.

Progress is stored at:

`/switch/HOC-Battery-Wizard/state.ini`

Final results are written to:

`/switch/HOC-Battery-Wizard/results.txt`

## Wizard order

1. CPU Low UV
2. CPU Low VMIN
3. RAM VDDQ
4. RAM VDD2
5. RAM validation at 1331 MHz
6. CPU High UV for Nintendo Boost
7. CPU + RAM Boost validation
8. Final 1020 / 384 / 1331 tests
9. Final 1785 / 76.8 / 1600 tests
10. One-hour real-world test

## Starting values

The wizard starts from the Mariko/OLED HOC baseline used for this workflow:

- CPU UV Table: Default / Normal (not Extreme)
- CPU Low UV: 0
- CPU High UV: 0
- CPU Low VMIN: 620 mV
- CPU High VMIN: 750 mV
- VDDQ: 600 mV
- VDD2: 1175 mV

It does **not** waste time stress-testing stock first. The first stress test happens after the first undervolt change.

## Search increments

These follow the current Horizon OC UI ranges:

- CPU Low UV: +1 level
- CPU High UV: +1 level
- CPU Low VMIN: -5 mV
- VDDQ: -5 mV
- VDD2: -12.5 mV

The first failed value is rejected. The previous working value is then validated for **1 hour**.

## Boot failure recovery

If a test value prevents booting:

1. Boot Hekate.
2. Start a CFW entry without Horizon OC / `hoc.kip`.
3. Open this wizard; its pending test is still saved.
4. Press **Y – DID NOT BOOT**.
5. The wizard tells you exactly which previous value to restore in HOC.
6. Save KIP, reboot normally, then perform the one-hour validation.

## Controls

- **A** — PASS / continue
- **X** — FAIL
- **Y** — DID NOT BOOT (quick-search stages)
- **B** — Exit; progress stays saved
- **Minus** — Reset wizard progress

## Building

Requires devkitPro / devkitA64 with libnx.

```bash
export DEVKITPRO=/opt/devkitpro
make
```

Output:

`HOC-Battery-Wizard.nro`

Copy it to e.g.:

`/switch/HOC-Battery-Wizard/HOC-Battery-Wizard.nro`

## GitHub Actions

A workflow is included that builds the NRO using the official devkitPro devkitA64 container.
