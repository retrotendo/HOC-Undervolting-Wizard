from pathlib import Path

# Fix libcurl file callback: curl expects number of bytes consumed.
p = Path('source/updater.cpp')
s = p.read_text()
old = '''size_t writeFile(void* ptr, size_t size, size_t nmemb, void* userdata) {\n    return std::fwrite(ptr, size, nmemb, static_cast<FILE*>(userdata));\n}\n'''
new = '''size_t writeFile(void* ptr, size_t size, size_t nmemb, void* userdata) {\n    const size_t total = size * nmemb;\n    FILE* f = static_cast<FILE*>(userdata);\n    return std::fwrite(ptr, 1, total, f) == total ? total : 0;\n}\n'''
if old not in s:
    raise SystemExit('updater write callback marker not found')
p.write_text(s.replace(old, new, 1))

# README updater documentation.
p = Path('README.md')
s = p.read_text()
marker = '# New in v0.4.0-beta.7\n'
block = '''# New in v0.4.0-beta.8\n\n## Startup self-updater\n\nStarting with **beta.8**, the Wizard checks its own GitHub releases when it starts in Full Application Mode.\n\n- If the installed build is current, startup continues normally.\n- If a newer build exists, the Wizard asks before doing anything: **A = Download & install**, **B = Not now**.\n- The new NRO is downloaded to a temporary `.new` file first.\n- The matching release `.sha256` file is downloaded and the NRO is verified with libnx SHA256 before replacement.\n- Only after verification does the Wizard rename the current NRO to `.bak` and move the verified `.new` file into place.\n- If replacement fails, the old NRO is restored.\n- After a successful update the Wizard exits; launch it again from hbmenu to run the new build.\n- The previous NRO remains beside the app as `.bak` for recovery and is replaced by the next updater run.\n\nThe updater is intentionally **not automatic**: it never installs a release without the user's A-button confirmation. Network/update-check failures are non-fatal and simply continue with the installed build.\n\nThe GitHub repository must be public for anonymous in-app update checks; no GitHub token is embedded in the NRO.\n\n**beta.8 itself must be installed manually once. Future builds can then update beta.8 in-app.**\n\n---\n\n# New in v0.4.0-beta.7\n'''
if marker not in s:
    raise SystemExit('README beta7 marker not found')
s = s.replace(marker, block, 1)

old = '1. Download `HOC-Undervolting-Wizard.nro` from the latest GitHub release.\n'
new = ('1. Download `HOC-Undervolting-Wizard.nro` from the latest GitHub release. '\
       'For beta.8 this is the final required manual update; later builds can be installed by the in-app updater.\n')
if old not in s:
    raise SystemExit('README install marker not found')
s = s.replace(old, new, 1)
p.write_text(s)

# Changelog.
p = Path('CHANGELOG.md')
s = p.read_text()
entry = '''## v0.4.0-beta.8\n\n- Add an opt-in startup self-updater for public GitHub releases.\n- Check the newest release before loading Wizard state, only in Full Application Mode.\n- Ask before installation: A installs, B continues the current build.\n- Download updates to `.new`, verify against the release SHA256, then replace the current NRO.\n- Keep the previous NRO as `.bak` and restore it automatically if replacement fails.\n- Use the actual hbloader `argv[0]` NRO path when available, with the standard Wizard path as fallback.\n- Network/update failures are non-fatal and do not affect tuning state.\n- Link the devkitPro `switch-curl` portlib for HTTPS GitHub access.\n\n'''
if '## v0.4.0-beta.8' not in s:
    marker = '# Changelog\n\n'
    if marker not in s:
        raise SystemExit('CHANGELOG marker not found')
    s = s.replace(marker, marker + entry, 1)
p.write_text(s)

# Third-party libcurl notice required by the curl license.
p = Path('THIRD_PARTY_LICENSES.md')
s = p.read_text()
marker = '## Distribution note\n'
section = '''## 6. libcurl\n\nThe startup self-updater links the devkitPro **switch-curl** port of libcurl for HTTPS access to the GitHub Releases API and release assets.\n\nProject: https://github.com/curl/curl\n\nCOPYRIGHT AND PERMISSION NOTICE\n\nCopyright (c) 1996 - 2026, Daniel Stenberg, <daniel@haxx.se>, and many contributors, see the THANKS file.\n\nAll rights reserved.\n\nPermission to use, copy, modify, and distribute this software for any purpose with or without fee is hereby granted, provided that the above copyright notice and this permission notice appear in all copies.\n\nTHE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT OF THIRD PARTY RIGHTS. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.\n\nExcept as contained in this notice, the name of a copyright holder shall not be used in advertising or otherwise to promote the sale, use or other dealings in this Software without prior written authorization of the copyright holder.\n\n---\n\n## Distribution note\n'''
if '## 6. libcurl' not in s:
    if marker not in s:
        raise SystemExit('THIRD_PARTY marker not found')
    s = s.replace(marker, section, 1)
p.write_text(s)

# Keep build artifact naming version-neutral from now on.
p = Path('.github/workflows/build.yml')
s = p.read_text()
s = s.replace('name: HOC-Undervolting-Wizard-v0.4.0-beta.5', 'name: HOC-Undervolting-Wizard-build')
p.write_text(s)
