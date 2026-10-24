# HOC Undervolting Wizard v0.4.0-beta.16

This beta is a larger workflow update focused on hardware-aware RAM setup, clearer reboot handoffs and more complete CPU Low VMIN validation.

## Automatic RAM detection and VDDQ baseline

Before Preparation, the Wizard now reads Horizon OC's DRAM ID and identifies the installed Mariko RAM module.

The VDDQ starting point is selected automatically from the Horizon OC RAM guidance:

- **640 mV:** NEE/x267, AA-MGCL, AM-MGCJ, AB-MGCL, NME
- **600 mV:** WT:B, WT:F, WT:E

The detected module, DRAM ID and selected baseline are shown before Preparation. Unknown/unsupported DRAM IDs are not guessed.

## Verified setting and guided reboot

Persistent HOC changes now use a separate setting/reboot phase:

1. The Wizard shows only the value that must be changed now.
2. A reads the current Horizon OC persistent configuration.
3. A wrong value blocks reboot and shows **Required / Current / WRONG**.
4. A correct value shows a green confirmation such as **Low VMIN 615 mV is set**.
5. Press A again to request the console restart.
6. After reopening the Wizard, confirm whether CFW booted normally with the new value.
7. The relevant 1-minute or 1-hour test is shown only after a successful boot confirmation.

Already-confirmed persistent values are no longer repeated on later test pages. Temporary Overrides are still shown whenever they must be changed.

## CPU voltage-region scan and validation

The Wizard measures all six CPU points:

**510 -> 612 -> 714 -> 816 -> 918 -> 1020 MHz**

Each measurement now displays a short 3-sample progress bar. The median CPU rail reading is grouped on HOC's 5 mV steps.

Instead of validating only the highest clock still on the Low VMIN floor, beta.16 identifies every distinct measured CPU-voltage region and runs the 1-hour CPU test at the **highest frequency of each region**.

Example:

- 510-816 MHz @ ~570 mV -> validate **816 MHz**
- 918 MHz @ ~585 mV -> validate **918 MHz**
- 1020 MHz @ ~600 mV -> validate **1020 MHz**

Detected voltage regions are written to `results.txt` together with the final tuning values.

## Existing beta.15 behavior retained

- Ultrahand-friendly right-side layout
- vertical TEST BLOCKED Required / Current / OK-WRONG display
- actual live CPU/GPU/RAM override values
- Full Application Mode requirement
- built-in CPU/RAM/Combined/GPU stress engines
- known PASS / FAIL shortcuts
- startup self-updater

## Important beta note

The code builds successfully in the devkitPro CI environment, but the new DRAM detection, persistent-setting verification and automatic reboot handoff still require real-hardware validation. This remains a pre-release.
