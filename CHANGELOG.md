# Changelog

## v0.4.0-beta.2

- Added the full Battery-guide starting setup to the Wizard preparation screen.
- Added CPU Max/Boost 1785 MHz, GPU Max 384 MHz and RAM Max 1600 MHz stock limits.
- Added Uncapped Clocks OFF, HP Mode OFF, Overwrite Boost Mode OFF and Auto CPU RAM OC OFF preparation guidance.
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
