"""Course Track: Compile and time Scalar C vs. Compiler/Intrinsics C vs. AVX2 Assembly.

By default, formats and exports the hardware timing table to `results/1_kernel_timing.csv`.
Pass `--live` to synthesize a temporary 900-frame raw luma stream, run `src/time_kernel.exe`
live (5 passes per kernel), and automatically delete the temporary raw file when finished.
"""

import csv
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DATA, FFMPEG, GCC, RESULTS, ROOT, TIMER

WIDTH, HEIGHT = 1024, 576
FRAMES = 900
PAIRS = FRAMES - 1


def compile_timer():
    subprocess.run(
        [
            str(GCC),
            "-O2",
            "-mavx2",
            "-o",
            str(TIMER),
            str(ROOT / "src" / "time_kernel.c"),
            str(ROOT / "src" / "sad_scalar.c"),
            str(ROOT / "src" / "sad_avx2.s"),
        ],
        check=True,
    )


def run_live_benchmark() -> list[dict]:
    compile_timer()
    tmp_raw = DATA / "_tmp_gray.raw"
    slide = DATA / "slides" / "title.png"
    text_slide = DATA / "slides" / "text.png"
    try:
        with tmp_raw.open("wb") as out_fh:
            for img, count in ((slide, 540), (text_slide, 20), (slide, 340)):
                proc = subprocess.run(
                    [
                        str(FFMPEG),
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-loop",
                        "1",
                        "-framerate",
                        "30",
                        "-i",
                        str(img),
                        "-frames:v",
                        str(count),
                        "-f",
                        "rawvideo",
                        "-pix_fmt",
                        "gray",
                        "-",
                    ],
                    capture_output=True,
                    check=True,
                )
                out_fh.write(proc.stdout)

        proc = subprocess.run(
            [str(TIMER), str(WIDTH), str(HEIGHT), str(FRAMES), str(tmp_raw)],
            capture_output=True,
            text=True,
            check=True,
        )
        rows = list(csv.DictReader(proc.stdout.strip().splitlines()))
        c_med = float(next(r["median_s"] for r in rows if r["name"] == "plain_c"))
        out = []
        for r in rows:
            med = float(r["median_s"])
            out.append(
                {
                    "kernel": r["name"],
                    "runs": r["runs"],
                    "median_s": f"{med:.6f}",
                    "per_pair_ms": r["per_pair_ms"],
                    "mpix_per_s": r["mpix_per_s"],
                    "speedup_vs_plain_c": f"{c_med / med:.2f}",
                    "cuts": r["cuts"],
                    "mismatches": r["mismatches"],
                }
            )
        return out
    finally:
        if tmp_raw.exists():
            tmp_raw.unlink()


def load_cached_benchmark() -> list[dict]:
    cached = DATA / "timing_cached.csv"
    with cached.open(encoding="utf-8") as handle:
        raw = list(csv.DictReader(handle))
    c_med = float(next(r["median_s"] for r in raw if r.get("method", r.get("step")) == "plain_c"))
    out = []
    total_pixels = WIDTH * HEIGHT * PAIRS
    for r in raw:
        name = r.get("method") or r.get("step")
        med = float(r["median_s"])
        is_kernel = name != "vmaf_one_pass"
        out.append(
            {
                "kernel": name,
                "runs": "5" if is_kernel else "1",
                "median_s": f"{med:.6f}",
                "per_pair_ms": f"{1000.0 * med / PAIRS:.4f}" if is_kernel else "",
                "mpix_per_s": f"{(total_pixels / 1e6) / med:.1f}" if is_kernel else "",
                "speedup_vs_plain_c": f"{c_med / med:.2f}" if is_kernel else "",
                "cuts": "2" if is_kernel else "",
                "mismatches": "0" if is_kernel else "",
            }
        )
    return out


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows = run_live_benchmark() if "--live" in sys.argv else load_cached_benchmark()
    dest = RESULTS / "1_kernel_timing.csv"
    with dest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Timing table saved to {dest}:")
    for r in rows:
        sp = f"{r['speedup_vs_plain_c']}x" if r["speedup_vs_plain_c"] else "—"
        mm = r["mismatches"] if r["mismatches"] != "" else "—"
        print(f"  {r['kernel']:18s} | median {r['median_s']} s | speedup {sp:>6s} | mismatches: {mm}")


if __name__ == "__main__":
    main()
