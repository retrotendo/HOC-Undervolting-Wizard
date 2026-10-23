from pathlib import Path

for name in ['source/main.cpp','README.md','CHANGELOG.md','RELEASE_NOTES_v0.4.0-beta.5.md']:
    p = Path(name)
    s = p.read_text()
    if name == 'source/main.cpp':
        s = s.replace('u32 samples[7] = {};', 'u32 samples[3] = {};', 1)
        s = s.replace('for (int i = 0; i < 7; ++i)', 'for (int i = 0; i < 3; ++i)', 1)
        s = s.replace("svcSleepThread(120'000'000);", "svcSleepThread(1'100'000'000);", 1)
    s = s.replace('7 context samples', '3 context samples')
    s = s.replace('median of 7 samples', 'median of 3 samples')
    s = s.replace('samples the live CPU rail voltage **7 times**', 'samples the live CPU rail voltage **3 times with 1.1 seconds between reads**')
    s = s.replace('The probe takes **7 context samples**', 'The probe takes **3 context samples spaced 1.1 seconds apart**')
    p.write_text(s)
