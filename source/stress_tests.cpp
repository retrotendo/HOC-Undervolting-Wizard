#include "stress_tests.hpp"

#include <switch.h>
#include <deko3d.h>

#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <thread>
#include <vector>

namespace stress {
namespace {

using Clock = std::chrono::steady_clock;

struct Context {
    std::atomic<bool> stop{false};
    std::atomic<bool> failed{false};
    std::atomic<int> initError{0};
    std::atomic<std::uint64_t> iterations{0};
    std::atomic<std::uint64_t> errors{0};
    std::atomic<std::uint64_t> mismatches{0};
    std::atomic<std::uint64_t> mismatchIndex{0};
    std::atomic<std::uint64_t> expected{0};
    std::atomic<std::uint64_t> actual{0};
    std::atomic<std::uint64_t> ramBytes{0};
};

std::uint32_t mix32(std::uint32_t x) {
    x ^= x >> 16;
    x *= 0x7feb352du;
    x ^= x >> 15;
    x *= 0x846ca68bu;
    x ^= x >> 16;
    return x;
}

std::uint64_t cpuKernel(std::uint32_t seed) {
    constexpr int N = 24;
    std::uint32_t a[N * N];
    std::uint32_t b[N * N];

    for (int i = 0; i < N * N; ++i) {
        a[i] = mix32(seed ^ (std::uint32_t(i) * 0x9e3779b9u));
        b[i] = mix32((seed + 0x01234567u) ^ (std::uint32_t(i) * 0x85ebca6bu));
    }

    std::uint64_t h = 0xcbf29ce484222325ULL;
    for (int i = 0; i < N; ++i) {
        for (int j = 0; j < N; ++j) {
            std::uint64_t acc = 0;
            for (int k = 0; k < N; ++k)
                acc += std::uint64_t(a[i * N + k]) * std::uint64_t(b[k * N + j]);
            h ^= acc + (std::uint64_t(std::uint32_t(i)) << 32) + std::uint32_t(j);
            h *= 1099511628211ULL;
        }
    }
    return h;
}

struct CpuVector {
    std::uint32_t seed;
    std::uint64_t expected;
};

constexpr CpuVector CPU_VECTORS[] = {
    {0x10203040u, 0x1fb02e074a8ebe56ULL},
    {0x1a2b3c4du, 0x8c8b5b076470cacfULL},
    {0xdeadbeefu, 0x5f85be67bdae1853ULL},
    {0x13579bdfu, 0x340d2eaf1607b386ULL},
    {0x2468ace0u, 0x661e8f990658bb55ULL},
    {0x55aa33ccu, 0x5adc09c21684cef5ULL},
    {0xc001d00du, 0x4df018d19687af9eULL},
    {0x31415926u, 0x5e90ce327a55fb18ULL},
};

void failMismatch(Context& c, std::uint64_t index, std::uint64_t expected, std::uint64_t actual) {
    c.mismatchIndex.store(index, std::memory_order_relaxed);
    c.expected.store(expected, std::memory_order_relaxed);
    c.actual.store(actual, std::memory_order_relaxed);
    c.mismatches.fetch_add(1, std::memory_order_relaxed);
    c.errors.fetch_add(1, std::memory_order_relaxed);
    c.failed.store(true, std::memory_order_release);
    c.stop.store(true, std::memory_order_release);
}

void cpuWorker(Context& c, unsigned workerId) {
    std::uint64_t n = workerId;
    while (!c.stop.load(std::memory_order_acquire)) {
        const CpuVector& v = CPU_VECTORS[n % (sizeof(CPU_VECTORS) / sizeof(CPU_VECTORS[0]))];
        const std::uint64_t got = cpuKernel(v.seed);
        if (got != v.expected) {
            failMismatch(c, n, v.expected, got);
            return;
        }
        c.iterations.fetch_add(1, std::memory_order_relaxed);
        ++n;
    }
}

void ramWorker(Context& c) {
    static constexpr std::size_t sizes[] = {
        128u * 1024u * 1024u,
         96u * 1024u * 1024u,
         64u * 1024u * 1024u,
         32u * 1024u * 1024u,
         16u * 1024u * 1024u,
    };

    volatile std::uint64_t* mem = nullptr;
    std::size_t bytes = 0;
    for (std::size_t candidate : sizes) {
        void* p = std::malloc(candidate);
        if (p) {
            mem = static_cast<volatile std::uint64_t*>(p);
            bytes = candidate;
            break;
        }
    }

    if (!mem) {
        c.initError.store(1, std::memory_order_release);
        c.stop.store(true, std::memory_order_release);
        return;
    }

    c.ramBytes.store(bytes, std::memory_order_release);
    const std::size_t words = bytes / sizeof(std::uint64_t);
    const std::uint64_t patterns[] = {
        0x0000000000000000ULL,
        0xffffffffffffffffULL,
        0xaaaaaaaaaaaaaaaaULL,
        0x5555555555555555ULL,
        0x0123456789abcdefULL,
        0xfedcba9876543210ULL,
    };

    std::uint64_t round = 0;
    while (!c.stop.load(std::memory_order_acquire)) {
        for (std::uint64_t base : patterns) {
            const std::uint64_t salt = round * 0x9e3779b97f4a7c15ULL;
            for (std::size_t i = 0; i < words; ++i) {
                if ((i & 0x3ffffu) == 0 && c.stop.load(std::memory_order_acquire)) {
                    std::free(const_cast<std::uint64_t*>(mem));
                    return;
                }
                mem[i] = base ^ salt ^ (std::uint64_t(i) * 0xd6e8feb86659fd93ULL);
            }

            for (std::size_t i = 0; i < words; ++i) {
                if ((i & 0x3ffffu) == 0 && c.stop.load(std::memory_order_acquire)) {
                    std::free(const_cast<std::uint64_t*>(mem));
                    return;
                }
                const std::uint64_t exp = base ^ salt ^ (std::uint64_t(i) * 0xd6e8feb86659fd93ULL);
                const std::uint64_t got = mem[i];
                if (got != exp) {
                    failMismatch(c, i, exp, got);
                    std::free(const_cast<std::uint64_t*>(mem));
                    return;
                }
            }
            c.iterations.fetch_add(1, std::memory_order_relaxed);
        }
        ++round;
    }

    std::free(const_cast<std::uint64_t*>(mem));
}

std::uint32_t gpuTransform(std::uint32_t index, std::uint32_t value) {
    std::uint32_t x = value ^ (index * 0x9e3779b9u);
    for (std::uint32_t r = 0; r < 192u; ++r) {
        x ^= x << 13;
        x ^= x >> 17;
        x ^= x << 5;
        x = x * 1664525u + 1013904223u;
        x ^= (r + 1u) * 0x85ebca6bu;
    }
    return x;
}

struct DkshHeader {
    std::uint32_t magic;
    std::uint32_t headerSize;
    std::uint32_t controlSize;
    std::uint32_t codeSize;
    std::uint32_t programsOffset;
    std::uint32_t numPrograms;
};

bool loadComputeShader(DkDevice device, DkShader* outShader, DkMemBlock* outCodeBlock) {
    FILE* f = std::fopen("romfs:/shaders/gpu_stress.dksh", "rb");
    if (!f) return false;

    DkshHeader hdr{};
    if (std::fread(&hdr, sizeof(hdr), 1, f) != 1 || hdr.controlSize == 0 || hdr.codeSize == 0) {
        std::fclose(f);
        return false;
    }

    void* control = std::malloc(hdr.controlSize);
    if (!control) {
        std::fclose(f);
        return false;
    }

    std::rewind(f);
    if (std::fread(control, hdr.controlSize, 1, f) != 1) {
        std::free(control);
        std::fclose(f);
        return false;
    }

    const std::uint32_t required = hdr.codeSize + DK_SHADER_CODE_UNUSABLE_SIZE;
    const std::uint32_t blockSize = (required + DK_MEMBLOCK_ALIGNMENT - 1u) & ~(DK_MEMBLOCK_ALIGNMENT - 1u);
    DkMemBlockMaker mm;
    dkMemBlockMakerDefaults(&mm, device, blockSize);
    mm.flags = DkMemBlockFlags_CpuUncached | DkMemBlockFlags_GpuCached | DkMemBlockFlags_Code;
    DkMemBlock code = dkMemBlockCreate(&mm);
    if (!code) {
        std::free(control);
        std::fclose(f);
        return false;
    }

    if (std::fread(dkMemBlockGetCpuAddr(code), hdr.codeSize, 1, f) != 1) {
        dkMemBlockDestroy(code);
        std::free(control);
        std::fclose(f);
        return false;
    }
    std::fclose(f);

    DkShaderMaker sm;
    dkShaderMakerDefaults(&sm, code, 0);
    sm.control = control;
    sm.programId = 0;
    dkShaderInitialize(outShader, &sm);
    std::free(control);

    *outCodeBlock = code;
    return true;
}

void gpuWorker(Context& c) {
    ::Result rcRom = romfsInit();
    if (R_FAILED(rcRom)) {
        c.initError.store(10, std::memory_order_release);
        c.stop.store(true, std::memory_order_release);
        return;
    }

    DkDeviceMaker dm;
    dkDeviceMakerDefaults(&dm);
    DkDevice dev = dkDeviceCreate(&dm);
    if (!dev) {
        romfsExit();
        c.initError.store(11, std::memory_order_release);
        c.stop.store(true, std::memory_order_release);
        return;
    }

    DkQueueMaker qm;
    dkQueueMakerDefaults(&qm, dev);
    qm.flags = DkQueueFlags_Compute;
    DkQueue queue = dkQueueCreate(&qm);
    if (!queue) {
        dkDeviceDestroy(dev);
        romfsExit();
        c.initError.store(12, std::memory_order_release);
        c.stop.store(true, std::memory_order_release);
        return;
    }

    DkShader shader{};
    DkMemBlock codeBlock = nullptr;
    if (!loadComputeShader(dev, &shader, &codeBlock)) {
        dkQueueDestroy(queue);
        dkDeviceDestroy(dev);
        romfsExit();
        c.initError.store(13, std::memory_order_release);
        c.stop.store(true, std::memory_order_release);
        return;
    }

    constexpr std::uint32_t dataBytes = 4u * 1024u * 1024u;
    constexpr std::uint32_t cmdBytes = 64u * 1024u;
    constexpr std::uint32_t words = dataBytes / sizeof(std::uint32_t);

    DkMemBlockMaker mm;
    dkMemBlockMakerDefaults(&mm, dev, dataBytes);
    mm.flags = DkMemBlockFlags_CpuUncached | DkMemBlockFlags_GpuCached;
    DkMemBlock dataBlock = dkMemBlockCreate(&mm);

    dkMemBlockMakerDefaults(&mm, dev, cmdBytes);
    mm.flags = DkMemBlockFlags_CpuUncached | DkMemBlockFlags_GpuCached;
    DkMemBlock cmdBlock = dkMemBlockCreate(&mm);

    if (!dataBlock || !cmdBlock) {
        if (cmdBlock) dkMemBlockDestroy(cmdBlock);
        if (dataBlock) dkMemBlockDestroy(dataBlock);
        dkMemBlockDestroy(codeBlock);
        dkQueueDestroy(queue);
        dkDeviceDestroy(dev);
        romfsExit();
        c.initError.store(14, std::memory_order_release);
        c.stop.store(true, std::memory_order_release);
        return;
    }

    auto* data = static_cast<std::uint32_t*>(dkMemBlockGetCpuAddr(dataBlock));
    for (std::uint32_t i = 0; i < words; ++i)
        data[i] = 0x12345678u ^ (i * 0x27d4eb2du);

    DkCmdBufMaker cm;
    dkCmdBufMakerDefaults(&cm, dev);
    DkCmdBuf cmd = dkCmdBufCreate(&cm);
    if (!cmd) {
        dkMemBlockDestroy(cmdBlock);
        dkMemBlockDestroy(dataBlock);
        dkMemBlockDestroy(codeBlock);
        dkQueueDestroy(queue);
        dkDeviceDestroy(dev);
        romfsExit();
        c.initError.store(15, std::memory_order_release);
        c.stop.store(true, std::memory_order_release);
        return;
    }

    dkCmdBufAddMemory(cmd, cmdBlock, 0, cmdBytes);
    const DkShader* shaders[] = { &shader };
    dkCmdBufBindShaders(cmd, DkStageFlag_Compute, shaders, 1);
    dkCmdBufBindStorageBuffer(cmd, DkStage_Compute, 0, dkMemBlockGetGpuAddr(dataBlock), dataBytes);
    dkCmdBufDispatchCompute(cmd, words / 128u, 1, 1);
    DkCmdList list = dkCmdBufFinishList(cmd);

    constexpr std::uint32_t sampleCount = 64;
    std::uint32_t sampleIndex[sampleCount];
    std::uint32_t sampleExpected[sampleCount];
    for (std::uint32_t s = 0; s < sampleCount; ++s) {
        const std::uint32_t idx = (s * 16411u + 97u) % words;
        sampleIndex[s] = idx;
        sampleExpected[s] = data[idx];
    }

    while (!c.stop.load(std::memory_order_acquire)) {
        dkQueueSubmitCommands(queue, list);
        DkFence fence{};
        dkQueueSignalFence(queue, &fence, true);
        dkQueueWaitFence(queue, &fence);

        if (dkQueueIsInErrorState(queue)) {
            c.errors.fetch_add(1, std::memory_order_relaxed);
            c.failed.store(true, std::memory_order_release);
            c.stop.store(true, std::memory_order_release);
            break;
        }

        for (std::uint32_t s = 0; s < sampleCount; ++s) {
            sampleExpected[s] = gpuTransform(sampleIndex[s], sampleExpected[s]);
            const std::uint32_t got = data[sampleIndex[s]];
            if (got != sampleExpected[s]) {
                failMismatch(c, sampleIndex[s], sampleExpected[s], got);
                break;
            }
        }
        if (c.failed.load(std::memory_order_acquire)) break;
        c.iterations.fetch_add(1, std::memory_order_relaxed);
    }

    dkQueueWaitIdle(queue);
    dkCmdBufDestroy(cmd);
    dkMemBlockDestroy(cmdBlock);
    dkMemBlockDestroy(dataBlock);
    dkMemBlockDestroy(codeBlock);
    dkQueueDestroy(queue);
    dkDeviceDestroy(dev);
    romfsExit();
}

void renderProgress(Kind kind, int durationSeconds, std::uint64_t elapsedMs, const Context& c) {
    const std::uint64_t totalMs = std::uint64_t(durationSeconds) * 1000ULL;
    const unsigned pct = totalMs ? unsigned((elapsedMs >= totalMs ? totalMs : elapsedMs) * 100ULL / totalMs) : 100u;
    const unsigned barWidth = 36;
    const unsigned filled = pct * barWidth / 100u;

    consoleClear();
    std::printf("\x1b[1;1H\x1b[36mHOC Undervolting Wizard\x1b[0m\n");
    std::printf("Built-in %s\n", kindName(kind));
    std::printf("------------------------------------------------------------\n\n");

    const std::uint64_t sec = elapsedMs / 1000ULL;
    const std::uint64_t target = durationSeconds;
    std::printf("Time       %02llu:%02llu / %02llu:%02llu\n",
        (unsigned long long)(sec / 60ULL), (unsigned long long)(sec % 60ULL),
        (unsigned long long)(target / 60ULL), (unsigned long long)(target % 60ULL));
    std::printf("Iterations %llu\n", (unsigned long long)c.iterations.load(std::memory_order_relaxed));
    std::printf("Errors     %llu\n", (unsigned long long)c.errors.load(std::memory_order_relaxed));
    std::printf("Mismatches %llu\n", (unsigned long long)c.mismatches.load(std::memory_order_relaxed));

    const std::uint64_t ram = c.ramBytes.load(std::memory_order_relaxed);
    if (ram)
        std::printf("RAM tested  %llu MiB per pass\n", (unsigned long long)(ram / 1024ULL / 1024ULL));

    std::printf("\n[");
    for (unsigned i = 0; i < barWidth; ++i) std::putchar(i < filled ? '#' : '-');
    std::printf("] %u%%\n\n", pct);
    std::printf("Do not leave the app while the test is running.\n");
    std::printf("[B] Cancel test (does NOT count as FAIL)\n");
    consoleUpdate(nullptr);
}

} // namespace

const char* kindName(Kind kind) {
    switch (kind) {
        case Kind::Cpu: return "CPU Verify Stress";
        case Kind::Ram: return "RAM Pattern / Mismatch Test";
        case Kind::Combined: return "Combined CPU + RAM Stress";
        case Kind::Gpu: return "GPU Compute / Memory Stress";
    }
    return "Unknown Test";
}

Result run(Kind kind, int durationSeconds) {
    Result out;
    Context c;

    std::vector<std::thread> workers;
    if (kind == Kind::Cpu) {
        workers.emplace_back(cpuWorker, std::ref(c), 0u);
        workers.emplace_back(cpuWorker, std::ref(c), 1u);
        workers.emplace_back(cpuWorker, std::ref(c), 2u);
    } else if (kind == Kind::Ram) {
        workers.emplace_back(ramWorker, std::ref(c));
    } else if (kind == Kind::Combined) {
        workers.emplace_back(cpuWorker, std::ref(c), 0u);
        workers.emplace_back(cpuWorker, std::ref(c), 1u);
        workers.emplace_back(ramWorker, std::ref(c));
    } else if (kind == Kind::Gpu) {
        workers.emplace_back(gpuWorker, std::ref(c));
    }

    PadState pad;
    padInitializeDefault(&pad);

    const auto start = Clock::now();
    auto lastDraw = start - std::chrono::seconds(1);
    bool cancelled = false;

    while (true) {
        if (!appletMainLoop()) {
            cancelled = true;
            break;
        }

        const auto now = Clock::now();
        const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - start).count();

        if (now - lastDraw >= std::chrono::milliseconds(200)) {
            renderProgress(kind, durationSeconds, std::uint64_t(elapsed), c);
            lastDraw = now;
        }

        if (c.failed.load(std::memory_order_acquire) || c.initError.load(std::memory_order_acquire) != 0)
            break;

        if (elapsed >= std::int64_t(durationSeconds) * 1000LL)
            break;

        padUpdate(&pad);
        const u64 down = padGetButtonsDown(&pad);
        if (down & HidNpadButton_B) {
            cancelled = true;
            break;
        }

        svcSleepThread(20'000'000);
    }

    c.stop.store(true, std::memory_order_release);
    for (auto& t : workers) if (t.joinable()) t.join();

    const auto finish = Clock::now();
    out.elapsedMs = std::uint64_t(std::chrono::duration_cast<std::chrono::milliseconds>(finish - start).count());
    out.iterations = c.iterations.load(std::memory_order_relaxed);
    out.errors = c.errors.load(std::memory_order_relaxed);
    out.mismatches = c.mismatches.load(std::memory_order_relaxed);

    if (cancelled) {
        out.outcome = Outcome::Cancelled;
        out.detail = "Test cancelled by user.";
    } else if (c.initError.load(std::memory_order_acquire) != 0) {
        out.outcome = Outcome::InitError;
        char buf[96];
        std::snprintf(buf, sizeof(buf), "Test engine initialization error %d.", c.initError.load());
        out.detail = buf;
    } else if (c.failed.load(std::memory_order_acquire) || out.errors || out.mismatches) {
        out.outcome = Outcome::Fail;
        if (out.mismatches) {
            char buf[192];
            std::snprintf(buf, sizeof(buf), "Mismatch at index %llu: expected 0x%016llX, got 0x%016llX",
                (unsigned long long)c.mismatchIndex.load(),
                (unsigned long long)c.expected.load(),
                (unsigned long long)c.actual.load());
            out.detail = buf;
        } else {
            out.detail = "The test engine detected an execution/GPU error.";
        }
    } else {
        out.outcome = Outcome::Pass;
        out.detail = "Completed with zero detected errors.";
    }

    return out;
}

} // namespace stress
