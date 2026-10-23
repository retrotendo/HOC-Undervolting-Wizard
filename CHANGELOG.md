# Changelog

## v0.4.0-beta.9

- Redesign tuning-stage UI into a compact right-side table layout for use alongside the Ultrahand/Horizon OC overlay.
- Keep Set in HOC values, Temporary Overrides, test type/duration and controls visible on the right half of the screen.
- Preserve beta.8 tuning/test/reboot/skip logic unchanged.
- Hide dynamic VMIN probe implementation details from the normal workflow while retaining the same automatic voltage measurement.
- Show Save KIP + Reboot only when a persistent HOC setting was changed.

## v0.4.0-beta.8

- Add an opt-in startup self-updater for public GitHub releases.
- Check the newest release before loading Wizard state, only in Full Application Mode.
- Ask before installation: A installs, B continues the current build.
- Download updates to `.new`, verify against the release SHA256, then replace the current NRO.
- Keep the previous NRO as `.bak` and restore it automatically if replacement fails.
- Use the actual hbloader `argv[0]` NRO path when available, with the standard Wizard path as fallback.
- Network/update failures are non-fatal and do not affect tuning state.
- Link the devkitPro `switch-curl` portlib for HTTPS GitHub access.

## v0.4.0-beta.7

- Use only the exact Battery-guide baseline values on the Preparation screen.
- Remove alternative "known-stable" and "known-working" setup values.
- Keep previously validated user values supported through KNOWN PASS / SKIP at the relevant test stages.
- Clarify Full Application Mode as required rather than recommended.

## v0.4.0-beta.6

- Block startup completely when hbmenu launches the Wizard in Applet Mode.
- Detect Full Memory Mode using `appletGetAppletType()`; only Application/SystemApplication are accepted.
- Show a dedicated warning with R-button title-takeover instructions instead of opening the guide.
- Keep beta.5 dynamic VMIN probing and known PASS/FAIL shortcuts unchanged.

## v0.4.0-beta.5

- Changed the dynamic CPU Low VMIN crossover sweep from repeated 1-minute stress tests to a fast **measurement-only floor probe**.
- Floor probing still verifies all three Horizon OC Temporary Overrides before every step.
- At each probe point, the Wizard samples the live CPU rail voltage **3 times with 1.1 seconds between reads** and uses the **median** of valid samples and only accepts them while HOC reports the requested CPU clock as actually applied so a stale single HOC poll cannot decide the crossover.
- Probe sequence remains **510 -> 612 -> 714 -> 816 -> 918 -> 1020 MHz** with GPU 384 / RAM 1331.2.
- The Wizard still selects the **highest CPU clock actually operating on the configured Low VMIN floor** and runs the single 1-hour CPU confirmation there.
- Lower CPU clocks on the same voltage floor are no longer stress-tested redundantly; transition checks such as Home, Sleep/Wake and game launch/close remain part of final validation.
- `[+] KNOWN PASS / SKIP` remains available for real test stages. During VMIN floor-probe stages, pressing `+` performs the required live-voltage measurement instead of blindly skipping it.
- `[X] KNOWN FAIL / SKIP` is disabled during measurement-only VMIN floor-probe stages because a voltage probe itself is not a stability PASS/FAIL test.
- Override-block screens now distinguish between a blocked stress test and a blocked VMIN measurement.

## v0.4.0-beta.4

- Synced the Wizard with the revised Battery Tuning guide.
- Added **[+] KNOWN PASS / SKIP** so already-proven settings can be accepted without rerunning every built-in test.
- Kept **[X] KNOWN FAIL / SKIP** for manually known failures.
- Corrected preparation guidance: CPU Max Clock is the **lowest selectable Horizon OC value** (currently 1963 MHz on Mariko), while Nintendo CPU Boost is handled separately through HOC Toolkit.
- Changed the recommended CPU UV table guidance to **1683 MHz Tbreak** (or another user-known stable table).
- Kept CPU Low VMIN at a **620 mV conservative baseline** with a hard Wizard floor of **570 mV**.
- Reworked Low VMIN tuning to use **dynamic floor detection** instead of assuming the same crossover frequency on every console.
- The Wizard now reads Horizon OC's live CPU rail voltage from `hoc:clk` during the Low VMIN sweep.
- Low VMIN quick search now runs at **510 / 384 / 1331.2 MHz**.
- After the VMIN candidate is found, the Wizard sweeps CPU **510 -> 612 -> 714 -> 816 -> 918 -> 1020 MHz** and automatically remembers the highest CPU clock still operating at the configured VMIN floor (within one 5 mV PMIC step).
- The long 1-hour Low VMIN confirmation is then run only at that dynamically detected highest floor-bound CPU clock.
- Added a separate **VDDQ + VDD2 combined RAM validation at 1785 / 76.8 / 1600** before normal-handheld RAM validation.
- Changed the Wizard's VDDQ search interval to **10 mV** to match the simplified guide workflow (two 5 mV Horizon OC UI steps).
- Added guide-style RAM-pair recovery: first retry combined RAM validation with VDDQ +10 mV; if it still fails, restore VDDQ and try VDD2 +12.5 mV.
- Results now record the dynamically detected highest Low VMIN floor clock when available.

## v0.4.0-beta.3

- Changed CPU Low VMIN hard floor from 550 mV to **570 mV**.
- Moved Low VMIN quick search to **612 / 384 / 1331.2 MHz**.
- Added sequential 1-hour Low VMIN validation at **612 -> 816 -> 1020 MHz**.
- CPU/GPU/RAM Temporary Overrides are verified before every validation run.
- Any failure in the three-stage VMIN validation raises Low VMIN by **5 mV** and restarts validation.
- Existing beta.2 state files are clamped to the new 570 mV minimum on load.

## v0.4.0-beta.2

- Added the full Battery-guide starting setup to the Wizard preparation screen.
- Added a hard Horizon OC pre-flight before every built-in test.
- CPU, GPU and RAM Temporary Overrides are all read from `hoc:clk` and compared with the exact test target.
- A missing/wrong override blocks the test and shows Expected vs Current values; no PASS/FAIL is recorded.

All notable changes to HOC Undervolting Wizard are documented here.

The project follows semantic versioning where practical. Pre-release builds are used until the integrated stress-test engine has been validated on real Switch hardware.

## [0.4.0-beta.1] - 2026-10-22

### Added
- Integrated CPU stability testing using the GPLv2 Matrixprod workload from Horizon-OC / Benchmark Toolbox plus Hanoi verification.
- Integrated memtester v4 RAM validation with automatic mismatch detection.
- Combined CPU + RAM validation mode.
- Integrated deko3d GPU compute / memory stress test with result verification.
- 1-minute quick-search tests and 1-hour validation tests with on-screen timer and progress.
- Persistent `testRunning` marker for crash/reboot detection.
- Automatic PASS/FAIL handling for detected test results.
- Recovery flow for unfinished tests and no-boot HOC settings.
- `THIRD_PARTY_LICENSES.md` with upstream attribution and provenance.

### Changed
- Project renamed to **HOC Undervolting Wizard**.
- Project license changed to **GPL-2.0-only** because GPLv2 CPU/RAM test code is incorporated into the executable.
- README expanded with installation, safe-boot recovery, test workflow and Performance Modes integration guidance.
- GitHub Actions now builds `HOC-Undervolting-Wizard.nro`.

### Notes
- This is a **beta pre-release**. The source compiles successfully in GitHub Actions, but the integrated test engines still require validation on real Mariko / Switch OLED hardware before a stable v0.4.0 release.
- HOC settings are still changed manually in Horizon OC. The Wizard never edits `hoc.kip` directly.

## [0.2.0] - 2026-10-22

### Added
- Guided undervolting workflow with persistent state.
- Battery-profile-oriented CPU and RAM tuning sequence.
- Safe recovery guidance after no-boot settings.
- Migration from the original HOC Battery Wizard state path.

### Changed
- Renamed from HOC Battery Wizard to HOC Undervolting Wizard.
