from pathlib import Path

p = Path('source/updater.cpp')
s = p.read_text()

s = s.replace(
'''constexpr const char* RELEASES_API =
    "https://api.github.com/repos/retrotendo/HOC-Undervolting-Wizard/releases?per_page=5";
''',
'''constexpr const char* RELEASES_API =
    "https://api.github.com/repos/retrotendo/HOC-Undervolting-Wizard/releases?per_page=5";
constexpr const char* UPDATE_MANIFEST =
    "https://raw.githubusercontent.com/retrotendo/HOC-Undervolting-Wizard/main/UPDATE.txt";
''', 1)

old_headers = '''    char curlError[CURL_ERROR_SIZE]{};
    struct curl_slist* headers = nullptr;
    if (githubApi) {
        headers = curl_slist_append(headers, "Accept: application/vnd.github+json");
        headers = curl_slist_append(headers, "X-GitHub-Api-Version: 2022-11-28");
        curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    }

    setCommonCurlOptions(curl, url.c_str());
'''
new_headers = '''    char curlError[CURL_ERROR_SIZE]{};
    struct curl_slist* headers = nullptr;
    headers = curl_slist_append(headers, "Cache-Control: no-cache");
    headers = curl_slist_append(headers, "Pragma: no-cache");
    if (githubApi) {
        headers = curl_slist_append(headers, "Accept: application/vnd.github+json");
        headers = curl_slist_append(headers, "X-GitHub-Api-Version: 2022-11-28");
    }
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);

    setCommonCurlOptions(curl, url.c_str());
'''
if old_headers not in s:
    raise SystemExit('header block not found')
s = s.replace(old_headers, new_headers, 1)

marker = '''CheckStatus checkLatestRelease(ReleaseInfo& latest, std::string& error) {
'''
insert = r'''bool manifestValue(const std::string& text, const std::string& key, std::string& out) {
    const std::string prefix = key + "=";
    size_t pos = 0;
    while (pos <= text.size()) {
        const size_t end = text.find('\n', pos);
        std::string line = text.substr(pos, end == std::string::npos ? std::string::npos : end - pos);
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.rfind(prefix, 0) == 0) {
            out = line.substr(prefix.size());
            return !out.empty();
        }
        if (end == std::string::npos) break;
        pos = end + 1;
    }
    return false;
}

CheckStatus checkManifestRelease(ReleaseInfo& latest, std::string& error) {
    std::string text;
    const std::string url = std::string(UPDATE_MANIFEST) + "?current=" + HOC_WIZARD_VERSION;
    if (!httpGetString(url, text, error, false)) return CheckStatus::Error;

    std::string version;
    std::string nroUrl;
    std::string shaUrl;
    if (!manifestValue(text, "version", version) ||
        !manifestValue(text, "nro_url", nroUrl) ||
        !manifestValue(text, "sha_url", shaUrl)) {
        error = "Update manifest is incomplete";
        return CheckStatus::Error;
    }

    SemVersion current;
    SemVersion remote;
    if (!parseSemVersion(HOC_WIZARD_VERSION, current)) {
        error = "Current version string is invalid";
        return CheckStatus::Error;
    }
    if (!parseSemVersion(version, remote)) {
        error = "Update manifest version is invalid";
        return CheckStatus::Error;
    }
    if (compareVersion(remote, current) <= 0) return CheckStatus::NoUpdate;

    latest.version = version;
    latest.tag = "v" + version;
    latest.nroUrl = nroUrl;
    latest.shaUrl = shaUrl;
    latest.sem = remote;
    return CheckStatus::UpdateAvailable;
}

'''
if marker not in s:
    raise SystemExit('checkLatestRelease marker not found')
s = s.replace(marker, insert + marker, 1)

marker2 = '''std::string normalizeSelfPath(int argc, char** argv) {
'''
robust = r'''CheckStatus checkLatestReleaseRobust(ReleaseInfo& latest, std::string& error) {
    ReleaseInfo manifestRelease;
    ReleaseInfo apiRelease;
    std::string manifestError;
    std::string apiError;

    const CheckStatus manifestStatus = checkManifestRelease(manifestRelease, manifestError);
    const CheckStatus apiStatus = checkLatestRelease(apiRelease, apiError);

    const bool manifestUpdate = manifestStatus == CheckStatus::UpdateAvailable;
    const bool apiUpdate = apiStatus == CheckStatus::UpdateAvailable;
    if (manifestUpdate || apiUpdate) {
        if (manifestUpdate && apiUpdate)
            latest = compareVersion(manifestRelease.sem, apiRelease.sem) >= 0 ? manifestRelease : apiRelease;
        else
            latest = manifestUpdate ? manifestRelease : apiRelease;
        return CheckStatus::UpdateAvailable;
    }

    // If either source completed successfully and found nothing newer, that is
    // enough to continue without bothering the user about the other source.
    if (manifestStatus == CheckStatus::NoUpdate || apiStatus == CheckStatus::NoUpdate)
        return CheckStatus::NoUpdate;

    error = "Manifest: " + (manifestError.empty() ? std::string("unknown error") : manifestError) +
            "\nGitHub API: " + (apiError.empty() ? std::string("unknown error") : apiError);
    return CheckStatus::Error;
}

'''
if marker2 not in s:
    raise SystemExit('normalize marker not found')
s = s.replace(marker2, robust + marker2, 1)

marker3 = '''void drawInstallFailed(const std::string& error) {
'''
check_failed = r'''void drawCheckFailed(const std::string& error) {
    consoleClear();
    std::printf("\x1b[1;1H\x1b[31mUpdate check failed\x1b[0m\n");
    std::printf("------------------------------------------------------------\n\n");
    std::printf("%s\n\n", error.c_str());
    std::printf("[A] Retry\n");
    std::printf("[B] Continue current version\n");
    consoleUpdate(nullptr);
}

'''
if marker3 not in s:
    raise SystemExit('drawInstallFailed marker not found')
s = s.replace(marker3, check_failed + marker3, 1)

old_check = '''    ReleaseInfo latest;
    std::string error;
    const CheckStatus status = checkLatestRelease(latest, error);
    if (status != CheckStatus::UpdateAvailable) {
        curl_global_cleanup();
        socketExit();
        return false;
    }

    const std::string selfPath = normalizeSelfPath(argc, argv);
'''
new_check = '''    ReleaseInfo latest;
    std::string error;
    while (true) {
        latest = ReleaseInfo{};
        error.clear();
        const CheckStatus status = checkLatestReleaseRobust(latest, error);
        if (status == CheckStatus::UpdateAvailable) break;
        if (status == CheckStatus::NoUpdate) {
            curl_global_cleanup();
            socketExit();
            return false;
        }

        drawCheckFailed(error);
        bool retry = false;
        while (appletMainLoop()) {
            padUpdate(&pad);
            const u64 k = padGetButtonsDown(&pad);
            if (k & HidNpadButton_A) { retry = true; break; }
            if (k & HidNpadButton_B) {
                curl_global_cleanup();
                socketExit();
                return false;
            }
            svcSleepThread(20'000'000);
        }
        if (!retry) {
            curl_global_cleanup();
            socketExit();
            return true;
        }
        drawChecking();
    }

    const std::string selfPath = normalizeSelfPath(argc, argv);
'''
if old_check not in s:
    raise SystemExit('startup check block not found')
s = s.replace(old_check, new_check, 1)
p.write_text(s)

p = Path('Makefile')
s = p.read_text().replace('APP_VERSION := 0.4.0-beta.10', 'APP_VERSION := 0.4.0-beta.11')
p.write_text(s)

Path('UPDATE.txt').write_text('''version=0.4.0-beta.11\nnro_url=https://github.com/retrotendo/HOC-Undervolting-Wizard/releases/download/v0.4.0-beta.11/HOC-Undervolting-Wizard.nro\nsha_url=https://github.com/retrotendo/HOC-Undervolting-Wizard/releases/download/v0.4.0-beta.11/HOC-Undervolting-Wizard.nro.sha256\n''')

p = Path('CHANGELOG.md')
s = p.read_text()
entry = '''## v0.4.0-beta.11\n\n- Make startup update checks resilient to GitHub API failures.\n- Add a lightweight public `UPDATE.txt` manifest as a second update source.\n- Keep the GitHub Releases API as a fallback and choose the newest version returned by either source.\n- Show update-check errors instead of silently continuing, with A = Retry and B = Continue.\n- Send no-cache headers for update metadata requests.\n- No tuning/test/UI-position logic changes from beta.10.\n\n'''
if '## v0.4.0-beta.11' not in s:
    s = s.replace('# Changelog\n\n', '# Changelog\n\n' + entry, 1)
p.write_text(s)

p = Path('README.md')
s = p.read_text()
entry = '''# New in v0.4.0-beta.11\n\n- More robust startup updater with two independent metadata sources.\n- A simple public `UPDATE.txt` manifest avoids depending only on the unauthenticated GitHub Releases API.\n- Update-check failures are shown on screen and can be retried instead of being silently ignored.\n- beta.10 tuning and right-side UI behavior are unchanged.\n\n---\n\n'''
if '# New in v0.4.0-beta.11' not in s:
    s = s.replace('# New in v0.4.0-beta.10\n', entry + '# New in v0.4.0-beta.10\n', 1)
p.write_text(s)
