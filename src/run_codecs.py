"""Multi-Codec Comparison Study: x264 vs. x265 (HEVC) vs. SVT-AV1 (AV1) on Screen Content.

Evaluates whether the 8-frame settled sampling advantage and tail VMAF shortfall
generalize across modern video compression standards:
  - AVC / H.264 (libx264)
  - HEVC / H.265 (libx265)
  - AV1 (libsvtav1)

Outputs:
  - results/5_multicodec_comparison.csv
"""

from concurrent.futures import ThreadPoolExecutor
import csv
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from config import DATA, FFMPEG, RESULTS

LOG_CSV = DATA / "clips_1080p" / "log.csv"
OUT_CSV = RESULTS / "5_multicodec_comparison.csv"
WORK_DIR = Path("/tmp/multicodec_work")
WORK_DIR.mkdir(parents=True, exist_ok=True)

EVEN = [56, 168, 281, 393, 506, 618, 731, 843]
TARGET = 90.0

CODEC_CONFIGS = {
    "libx264": {
        "name": "H.264 (libx264)",
        "ladder": (28, 31, 34, 37, 40),
        "enc_args": ["-c:v", "libx264", "-preset", "medium", "-g", "999", "-keyint_min", "999", "-sc_threshold", "0"],
    },
    "libx265": {
        "name": "HEVC (libx265)",
        "ladder": (26, 29, 32, 35, 38),
        "enc_args": ["-c:v", "libx265", "-preset", "faster", "-x265-params", "log-level=error:keyint=999:min-keyint=999:scenecut=0"],
    },
    "libsvtav1": {
        "name": "AV1 (libsvtav1)",
        "ladder": (42, 48, 54, 58, 62),
        "enc_args": ["-c:v", "libsvtav1", "-preset", "10", "-svtav1-params", "keyint=999:scd=0"],
    },
}


def encode_and_score_clip(clip_row: dict, codec_key: str, crf: int) -> dict:
    cid = clip_row["clip"]
    start = int(clip_row["start"])
    hold = int(clip_row["hold"])
    easy = DATA / "slides_1080p" / clip_row["easy"].replace("\\", "/")
    dense = DATA / "slides_1080p" / clip_row["dense"].replace("\\", "/")

    cfg = CODEC_CONFIGS[codec_key]
    mp4_path = WORK_DIR / f"{cid}_{codec_key}_crf{crf}.mp4"
    json_path = WORK_DIR / f"{cid}_{codec_key}_crf{crf}.json"

    graph_enc = (
        f"[0:v]format=rgb24,setsar=1[e];[1:v]format=rgb24,setsar=1[d];"
        f"[e][d]overlay=format=rgb:enable='between(n,{start},{start+hold-1})',format=yuv420p"
    )

    t_enc = time.perf_counter()
    if not mp4_path.exists():
        subprocess.run(
            [
                str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error",
                "-loop", "1", "-framerate", "30", "-i", str(easy),
                "-loop", "1", "-framerate", "30", "-i", str(dense),
                "-filter_complex", graph_enc,
                "-frames:v", "900", "-fps_mode", "cfr", "-an",
                *cfg["enc_args"], "-crf", str(crf),
                str(mp4_path),
            ],
            check=True,
        )
    enc_s = time.perf_counter() - t_enc
    size_bytes = mp4_path.stat().st_size

    # Fast evaluation on the 40 essential frame indices (even, cut transition, settled hold, post-cut)
    subset = sorted(set(EVEN + [8, 9, 10, 11, 12, 13, 14, 15] + list(range(start, start + hold)) + list(range(start + hold, start + hold + 16))))
    sel_expr = "+".join(f"eq(n\\,{i})" for i in subset)

    if not json_path.exists():
        graph_vmaf = (
            f"[1:v]format=rgb24,setsar=1[e];[2:v]format=rgb24,setsar=1[d];"
            f"[e][d]overlay=format=rgb:enable='between(n,{start},{start+hold-1})',select='{sel_expr}',format=yuv420p,setpts=N/30/TB[ref];"
            f"[0:v]select='{sel_expr}',format=yuv420p,setpts=N/30/TB[dist];"
            f"[dist][ref]libvmaf=log_fmt=json:log_path={json_path.name}:n_subsample=1:n_threads=4"
        )
        subprocess.run(
            [
                str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(mp4_path),
                "-loop", "1", "-framerate", "30", "-i", str(easy),
                "-loop", "1", "-framerate", "30", "-i", str(dense),
                "-filter_complex", graph_vmaf,
                "-frames:v", str(len(subset)),
                "-f", "null", "-",
            ],
            cwd=str(WORK_DIR),
            check=True,
        )

    raw_frames = json.loads(json_path.read_text(encoding="utf-8"))["frames"]
    fmap = {subset[int(f["frameNum"])]: float(f["metrics"]["vmaf"]) for f in raw_frames}

    spread_vote = min(fmap[i] for i in EVEN)
    oncut_vote = min(fmap[i] for i in range(start, start + 8))
    settled_vote = min(fmap[i] for i in range(start + 8, start + 16))
    p1_val = sorted(fmap.values())[8]

    return {
        "clip": cid,
        "codec": codec_key,
        "codec_name": cfg["name"],
        "crf": crf,
        "size_kb": round(size_bytes / 1000.0, 1),
        "enc_time_s": round(enc_s, 2),
        "spread_vote": round(spread_vote, 2),
        "oncut_vote": round(oncut_vote, 2),
        "settled_vote": round(settled_vote, 2),
        "p1_vmaf": round(p1_val, 2),
    }


def analyze_clip(clip_row: dict) -> list[dict]:
    cid = clip_row["clip"]
    records = []
    for codec_key, cfg in CODEC_CONFIGS.items():
        ladder_results = []
        for crf in cfg["ladder"]:
            res = encode_and_score_clip(clip_row, codec_key, crf)
            ladder_results.append(res)

        # Select CRF for each selector rule:
        # Uniform: picks highest CRF whose spread_vote >= TARGET
        passing_spread = [r for r in ladder_results if r["spread_vote"] >= TARGET]
        c_spread = max(passing_spread, key=lambda x: x["crf"]) if passing_spread else ladder_results[0]

        # Settled: picks highest CRF whose settled_vote >= TARGET
        passing_settled = [r for r in ladder_results if r["settled_vote"] >= TARGET]
        c_settled = max(passing_settled, key=lambda x: x["crf"]) if passing_settled else ladder_results[0]

        # On-Cut: picks highest CRF whose oncut_vote >= TARGET
        passing_oncut = [r for r in ladder_results if r["oncut_vote"] >= TARGET]
        c_oncut = max(passing_oncut, key=lambda x: x["crf"]) if passing_oncut else ladder_results[0]

        sf_spread = max(0.0, TARGET - c_spread["p1_vmaf"])
        sf_settled = max(0.0, TARGET - c_settled["p1_vmaf"])
        sf_oncut = max(0.0, TARGET - c_oncut["p1_vmaf"])

        records.append({
            "clip": cid,
            "codec": codec_key,
            "codec_name": cfg["name"],
            "uniform_crf": c_spread["crf"],
            "uniform_shortfall": round(sf_spread, 2),
            "uniform_size_kb": c_spread["size_kb"],
            "settled_crf": c_settled["crf"],
            "settled_shortfall": round(sf_settled, 2),
            "settled_size_kb": c_settled["size_kb"],
            "oncut_crf": c_oncut["crf"],
            "oncut_shortfall": round(sf_oncut, 2),
            "oncut_valid": 1 if passing_oncut else 0,
        })
    return records


def main():
    with LOG_CSV.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    # Evaluate representative subset of clips (Clips 01 to 04 covering diverse UI and text layouts)
    test_clips = rows[:4]
    print(f"Running multi-codec comparison across {len(test_clips)} clips for x264, x265, and SVT-AV1...")

    all_records = []
    for r in test_clips:
        print(f"  Evaluating Clip {r['clip']} ({r['easy']} -> {r['dense']})...", flush=True)
        clip_records = analyze_clip(r)
        all_records.extend(clip_records)

    RESULTS.mkdir(parents=True, exist_ok=True)
    fieldnames = list(all_records[0].keys())
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_records)

    print(f"\nSaved multi-codec results to {OUT_CSV}")

    # Print summary
    print("\n=== Multi-Codec Summary Averages (Target VMAF = 90.0) ===")
    for ckey, cfg in CODEC_CONFIGS.items():
        sub = [r for r in all_records if r["codec"] == ckey]
        m_u_sf = sum(r["uniform_shortfall"] for r in sub) / len(sub)
        m_s_sf = sum(r["settled_shortfall"] for r in sub) / len(sub)
        m_u_sz = sum(r["uniform_size_kb"] for r in sub) / len(sub)
        m_s_sz = sum(r["settled_size_kb"] for r in sub) / len(sub)
        pass_u = sum(1 for r in sub if r["uniform_shortfall"] == 0.0)
        pass_s = sum(1 for r in sub if r["settled_shortfall"] == 0.0)
        print(
            f"[{cfg['name']}] Uniform: Pass {pass_u}/{len(sub)} | Mean Shortfall: {m_u_sf:.2f} | Mean Size: {m_u_sz:.1f} KB\n"
            f"             Settled: Pass {pass_s}/{len(sub)} | Mean Shortfall: {m_s_sf:.2f} | Mean Size: {m_s_sz:.1f} KB"
        )


if __name__ == "__main__":
    main()
