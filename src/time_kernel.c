/* Time the brightness sum only. Frame bytes are already in memory.
   Ordinary C, auto-vectorized C, and AVX2 assembly are timed apart.
   Each timed pass is one clock around every pair, not one clock per pair. */

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <io.h>
#include <fcntl.h>
#include <windows.h>

uint64_t sad_plain(const uint8_t *a, const uint8_t *b, size_t n);
uint64_t sad_autovec(const uint8_t *a, const uint8_t *b, size_t n);
uint64_t sad_avx2_asm(const uint8_t *a, const uint8_t *b, size_t n);

typedef uint64_t (*sad_fn)(const uint8_t *a, const uint8_t *b, size_t n);

static double seconds_between(LARGE_INTEGER start, LARGE_INTEGER end, LARGE_INTEGER freq) {
    return (double)(end.QuadPart - start.QuadPart) / (double)freq.QuadPart;
}

static uint64_t pass(sad_fn fn, const uint8_t *frames, int nframes, size_t npix) {
    uint64_t sink = 0;
    int i;
    for (i = 1; i < nframes; i++) {
        const uint8_t *prev = frames + (size_t)(i - 1) * npix;
        const uint8_t *curr = frames + (size_t)i * npix;
        sink += fn(prev, curr, npix);
    }
    return sink;
}

static double time_pass(sad_fn fn, const uint8_t *frames, int nframes, size_t npix, LARGE_INTEGER freq) {
    LARGE_INTEGER t0, t1;
    volatile uint64_t sink;
    QueryPerformanceCounter(&t0);
    sink = pass(fn, frames, nframes, npix);
    QueryPerformanceCounter(&t1);
    (void)sink;
    return seconds_between(t0, t1, freq);
}

static int cmp_double(const void *a, const void *b) {
    double da = *(const double *)a;
    double db = *(const double *)b;
    return (da > db) - (da < db);
}

static void report(const char *name, sad_fn fn, const uint8_t *frames, int nframes, size_t npix, LARGE_INTEGER freq) {
    double runs[5];
    int i;
    time_pass(fn, frames, nframes, npix, freq);
    for (i = 0; i < 5; i++) {
        runs[i] = time_pass(fn, frames, nframes, npix, freq);
    }
    qsort(runs, 5, sizeof(double), cmp_double);
    printf("%s median %.6f runs %.6f %.6f %.6f %.6f %.6f\n",
           name, runs[2], runs[0], runs[1], runs[2], runs[3], runs[4]);
}

int main(int argc, char **argv) {
    int width;
    int height;
    int nframes;
    size_t npix;
    uint8_t *frames;
    FILE *in;
    LARGE_INTEGER freq;
    int mismatches = 0;
    int i;

    if (argc < 4 || argc > 5) {
        fprintf(stderr, "usage: time_kernel width height frames [gray.raw]\n");
        return 2;
    }
    width = atoi(argv[1]);
    height = atoi(argv[2]);
    nframes = atoi(argv[3]);
    if (width <= 0 || height <= 0 || nframes < 2) {
        fprintf(stderr, "bad size\n");
        return 2;
    }
    npix = (size_t)width * (size_t)height;
    frames = (uint8_t *)malloc(npix * (size_t)nframes);
    if (!frames) {
        fprintf(stderr, "out of memory\n");
        return 2;
    }
    if (argc == 5 && strcmp(argv[4], "-") != 0) {
        in = fopen(argv[4], "rb");
        if (!in) {
            perror(argv[4]);
            free(frames);
            return 2;
        }
    } else {
        _setmode(_fileno(stdin), _O_BINARY);
        in = stdin;
    }
    if (fread(frames, npix, (size_t)nframes, in) != (size_t)nframes) {
        fprintf(stderr, "short read\n");
        if (in != stdin) {
            fclose(in);
        }
        free(frames);
        return 2;
    }
    if (in != stdin) {
        fclose(in);
    }

    for (i = 1; i < nframes; i++) {
        const uint8_t *prev = frames + (size_t)(i - 1) * npix;
        const uint8_t *curr = frames + (size_t)i * npix;
        uint64_t plain = sad_plain(prev, curr, npix);
        if (plain != sad_autovec(prev, curr, npix) || plain != sad_avx2_asm(prev, curr, npix)) {
            mismatches++;
        }
    }

    QueryPerformanceFrequency(&freq);
    printf("pairs %d mismatches %d pixels %zu\n", nframes - 1, mismatches, npix);
    report("plain_c", sad_plain, frames, nframes, npix, freq);
    report("autovectorized_c", sad_autovec, frames, nframes, npix, freq);
    report("avx2_asm", sad_avx2_asm, frames, nframes, npix, freq);
    free(frames);
    return mismatches == 0 ? 0 : 1;
}
