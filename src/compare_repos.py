"""Fair Apples-to-Apples Comparison on the Exact Same 18 Full-HD (1080p) Clips (`01..18`).

Runs both repositories' approaches on the EXACT SAME 18 1920x1080 900-frame clips:
  1. Baseline (`Evenly Spread`, 8 bin centers / `libvmaf:n_subsample=112`)
  2. Old Repo (`img-proof-of-concept`: Single-Cut Settled Global CRF)
  3. Overhauled Repo (`CSC612M-Paper`: Multi-Cut Settled Per-Segment `x264 --zones`)

If `data/clips_1080p/zoned_1080p_summary.csv` does not yet exist (or `--rebuild` is passed),
encodes all 18 clips with `x264 --zones` and scores all 900 frames of each clip with `libvmaf`.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import json
from pathlib import Path
import subprocess
import sys
import time
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DATA, FFMPEG, RESULTS
import run_study

LOG_CSV = DATA / "clips_1080p" / "log.csv"
DECISIONS_CSV = DATA / "clips_1080p" / "decisions.csv"
ZONED_CSV = DATA / "clips_1080p" / "zoned_1080p_summary.csv"


def pic_filter(path: Path) -> str:
    with Image.open(path) as im:
        sz = im.size
    if sz == (1920, 1080):
        return "format=rgb24,setsar=1"
    return "scale=1920:1080:flags=lanczos,format=rgb24,setsar=1"


def encode_and_score_zoned_clip(row: dict, poc_row: dict) -> dict:
    cid = row["clip"]
    start = int(row["start"])
    hold = int(row["hold"])
    easy = DATA / "slides_1080p" / row["easy"].replace("\\", "/")
    dense = DATA / "slides_1080p" / row["dense"].replace("\\", "/")
    sdir = DATA / "clips_1080p" / "work" / cid / "scores"

    seg1 = range(8, 16)
    seg2 = range(start + 8, start + 16)
    seg3 = range(start + hold + 8, start + hold + 16)
    crf1 = crf2 = crf3 = None
    for p in sorted(sdir.glob("crf*.json"), key=lambda x: int(x.stem[3:])):
        crf = int(p.stem[3:])
        frames = {
            int(f["frameNum"]): float(f["metrics"]["vmaf"])
            for f in json.loads(p.read_text(encoding="utf-8"))["frames"]
        }
        if min(frames[i] for i in seg1) >= 90.0:
            crf1 = crf
        if min(frames[i] for i in seg2) >= 90.0:
            crf2 = crf
        if min(frames[i] for i in seg3) >= 90.0:
            crf3 = crf

    zones = f"0,{start-1},crf={crf1}/{start},{start+hold-1},crf={crf2}/{start+hold},899,crf={crf3}"
    mp4_path = Path(f"/tmp/zoned_1080p_{cid}.mp4")
    json_path = sdir / "zoned.json"
    ef = pic_filter(easy)
    df = pic_filter(dense)

    graph_enc = (
        f"[0:v]{ef}[e];[1:v]{df}[d];"
        f"[e][d]overlay=format=rgb:enable='between(n,{start},{start + hold - 1})',format=yuv420p"
    )
    t_enc = time.perf_counter()
    subprocess.run(
        [
            str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error",
            "-loop", "1", "-framerate", "30", "-i", str(easy),
            "-loop", "1", "-framerate", "30", "-i", str(dense),
            "-filter_complex", graph_enc,
            "-frames:v", "900", "-fps_mode", "cfr", "-an",
            "-c:v", "libx264", "-preset", "medium", "-crf", str(crf1),
            "-pix_fmt", "yuv420p", "-g", "999", "-keyint_min", "999", "-sc_threshold", "0",
            "-x264-params", f"zones={zones}",
            str(mp4_path),
        ],
        check=True,
    )
    enc_s = time.perf_counter() - t_enc
    z_bytes = mp4_path.stat().st_size

    if not json_path.exists() or "--rebuild" in sys.argv:
        graph_vmaf = (
            f"[1:v]{ef}[e];[2:v]{df}[d];"
            f"[e][d]overlay=format=rgb:enable='between(n,{start},{start + hold - 1})',format=yuv420p,setpts=PTS-STARTPTS[ref];"
            f"[0:v]format=yuv420p,setpts=PTS-STARTPTS[dist];"
            f"[dist][ref]libvmaf=log_fmt=json:log_path={json_path.name}:n_subsample=1:n_threads=4"
        )
        subprocess.run(
            [
                str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(mp4_path),
                "-loop", "1", "-framerate", "30", "-i", str(easy),
                "-loop", "1", "-framerate", "30", "-i", str(dense),
                "-filter_complex", graph_vmaf,
                "-frames:v", "900", "-f", "null", "-",
            ],
            cwd=str(sdir),
            check=True,
        )
    mp4_path.unlink(missing_ok=True)

    scores = [
        float(f["metrics"]["vmaf"])
        for f in sorted(json.loads(json_path.read_text(encoding="utf-8"))["frames"], key=lambda x: x["frameNum"])
    ]
    s_sorted = sorted(enumerate(scores), key=lambda x: x[1])
    ninth_f, ninth_v = s_sorted[8]
    for _repair in range(2):
        if ninth_v >= 90.0:
            break
        # Step down whichever zone(s) actually had frames below 90.0
        if min(scores[0:start]) < 90.0 and crf1 > 28:
            crf1 -= 1
        if min(scores[start : start + hold]) < 90.0 and crf2 > 28:
            crf2 -= 1
        if min(scores[start + hold : 900]) < 90.0 and crf3 > 28:
            crf3 -= 1
        zones = f"0,{start-1},crf={crf1}/{start},{start+hold-1},crf={crf2}/{start+hold},899,crf={crf3}"
        t_enc = time.perf_counter()
        subprocess.run(
            [
                str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error",
                "-loop", "1", "-framerate", "30", "-i", str(easy),
                "-loop", "1", "-framerate", "30", "-i", str(dense),
                "-filter_complex", graph_enc,
                "-frames:v", "900", "-fps_mode", "cfr", "-an",
                "-c:v", "libx264", "-preset", "medium", "-crf", str(crf1),
                "-pix_fmt", "yuv420p", "-g", "999", "-keyint_min", "999", "-sc_threshold", "0",
                "-x264-params", f"zones={zones}",
                str(mp4_path),
            ],
            check=True,
        )
        enc_s = time.perf_counter() - t_enc
        z_bytes = mp4_path.stat().st_size
        graph_vmaf = (
            f"[1:v]{ef}[e];[2:v]{df}[d];"
            f"[e][d]overlay=format=rgb:enable='between(n,{start},{start + hold - 1})',format=yuv420p,setpts=PTS-STARTPTS[ref];"
            f"[0:v]format=yuv420p,setpts=PTS-STARTPTS[dist];"
            f"[dist][ref]libvmaf=log_fmt=json:log_path={json_path.name}:n_subsample=1:n_threads=4"
        )
        subprocess.run(
            [
                str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(mp4_path),
                "-loop", "1", "-framerate", "30", "-i", str(easy),
                "-loop", "1", "-framerate", "30", "-i", str(dense),
                "-filter_complex", graph_vmaf,
                "-frames:v", "900", "-f", "null", "-",
            ],
            cwd=str(sdir),
            check=True,
        )
        mp4_path.unlink(missing_ok=True)
        scores = [
            float(f["metrics"]["vmaf"])
            for f in sorted(json.loads(json_path.read_text(encoding="utf-8"))["frames"], key=lambda x: x["frameNum"])
        ]
        s_sorted = sorted(enumerate(scores), key=lambda x: x[1])
        ninth_f, ninth_v = s_sorted[8]

    shortfall = max(0.0, 90.0 - ninth_v)
    settled_min = min(scores[start + 8 : start + 16])
    print(
        f"  Clip {cid}: zones={crf1}/{crf2}/{crf3} | 9th={ninth_v:.2f} (sf={shortfall:.2f}) | "
        f"POC Global={int(poc_row['settled_bytes'])//1000} KB -> Paper Zoned={z_bytes//1000} KB ({enc_s:.2f}s)",
        flush=True,
    )
    return {
        "clip": cid,
        "group": row["group"],
        "start": start,
        "zones_crf": f"{crf1}/{crf2}/{crf3}",
        "zoned_settled_min": f"{settled_min:.4f}",
        "zoned_ninth": f"{ninth_v:.4f}",
        "zoned_ninth_frame": ninth_f,
        "zoned_shortfall": f"{shortfall:.4f}",
        "zoned_bytes": z_bytes,
        "zoned_encode_s": f"{enc_s:.2f}",
    }


def ensure_zoned_1080p() -> list[dict]:
    existing = {}
    if ZONED_CSV.exists() and "--rebuild" not in sys.argv:
        with ZONED_CSV.open(encoding="utf-8", newline="") as handle:
            for r in csv.DictReader(handle):
                if float(r["zoned_shortfall"]) == 0.0:
                    existing[r["clip"]] = r
        if len(existing) == 18:
            return sorted(existing.values(), key=lambda r: int(r["clip"]))

    log_rows = list(csv.DictReader(LOG_CSV.open(encoding="utf-8")))
    poc_dec = {r["clip"]: r for r in csv.DictReader(DECISIONS_CSV.open(encoding="utf-8"))}
    todo = [r for r in log_rows if r["clip"] not in existing]
    print(f"Encoding and VMAF-scoring {len(todo)} 1080p clips with Cut-Driven Per-Segment Zoning (x264 --zones)...")
    results = list(existing.values())
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = [ex.submit(encode_and_score_zoned_clip, r, poc_dec[r["clip"]]) for r in todo]
        for f in as_completed(futs):
            results.append(f.result())
    results.sort(key=lambda x: int(x["clip"]))
    with ZONED_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    return results


def main():
    zoned_rows = ensure_zoned_1080p()
    zoned_by_clip = {r["clip"]: r for r in zoned_rows}
    with DECISIONS_CSV.open(encoding="utf-8", newline="") as handle:
        poc_rows = sorted(list(csv.DictReader(handle)), key=lambda r: int(r["clip"]))
    log_by_clip = {r["clip"]: r for r in csv.DictReader(LOG_CSV.open(encoding="utf-8"))}

    print("\n" + "=" * 132)
    print("FAIR APPLES-TO-APPLES BENCHMARK ON THE EXACT SAME 18 FULL-HD (1920x1080, 900-FRAME) CLIPS (`01..18`)")
    print("=" * 132)
    print(
        f"{'Clip':>4s} | {'Group':>10s} | {'Start':>5s} || "
        f"{'1. Evenly Spread (Baseline)':28s} || "
        f"{'2. Old Repo (Global Settled)':28s} || "
        f"{'3. Paper Repo (Multi-Cut Zoned)':32s} | {'Saved vs Old':>12s}"
    )
    print(
        f"{'':>4s} | {'':>10s} | {'':>5s} || "
        f"{'CRF | Shortfall |   Size':28s} || "
        f"{'CRF | Shortfall |   Size':28s} || "
        f"{'Zones    | Shortfall |   Size':32s} | {'(Bytes / %)':>12s}"
    )
    print("-" * 132)

    combined_out = []
    for p in poc_rows:
        cid = p["clip"]
        z = zoned_by_clip[cid]
        sp_crf = int(p["spread_crf"])
        sp_sf = float(p["spread_shortfall"])
        sp_kb = int(p["spread_bytes"]) / 1000.0

        gl_crf = int(p["settled_crf"])
        gl_sf = float(p["settled_shortfall"])
        gl_kb = int(p["settled_bytes"]) / 1000.0

        zn_crf = z["zones_crf"]
        zn_sf = float(z["zoned_shortfall"])
        zn_kb = int(z["zoned_bytes"]) / 1000.0
        saved_kb = gl_kb - zn_kb
        saved_pct = 100.0 * (gl_kb - zn_kb) / gl_kb

        print(
            f"{cid:>4s} | {p['group']:>10s} | {p['cuts'].split()[0]:>5s} || "
            f"{sp_crf:3d} | {sp_sf:9.2f} | {sp_kb:6.1f} KB || "
            f"{gl_crf:3d} | {gl_sf:9.2f} | {gl_kb:6.1f} KB || "
            f"{zn_crf:8s} | {zn_sf:9.2f} | {zn_kb:6.1f} KB | {-saved_kb:+6.1f} KB ({-saved_pct:+4.1f}%)"
        )
        combined_out.append(
            {
                "clip": cid,
                "group": p["group"],
                "easy_slide": log_by_clip[cid]["easy"],
                "dense_slide": log_by_clip[cid]["dense"],
                "cuts": p["cuts"],
                "spread_crf": sp_crf,
                "spread_ninth_vmaf": p["spread_ninth"],
                "spread_shortfall_90": f"{sp_sf:.2f}",
                "spread_bytes": p["spread_bytes"],
                "old_repo_settled_crf": gl_crf,
                "old_repo_ninth_vmaf": p["settled_ninth"],
                "old_repo_shortfall_90": f"{gl_sf:.2f}",
                "old_repo_bytes": p["settled_bytes"],
                "paper_zoned_crfs": zn_crf,
                "paper_zoned_ninth_vmaf": z["zoned_ninth"],
                "paper_zoned_shortfall_90": f"{zn_sf:.2f}",
                "paper_zoned_bytes": z["zoned_bytes"],
                "paper_zoned_encode_s": z["zoned_encode_s"],
                "size_change_vs_old_pct": f"{-saved_pct:.2f}",
            }
        )

    print("-" * 132)
    for grp_label, grp_filter in (
        ("12 Comparison Clips (01..12, Simple + Dense)", lambda r: r["group"] == "comparison"),
        (" 6 Boundary Clips   (13..18, Medium + Dense)", lambda r: r["group"] == "boundary"),
        ("ALL 18 Clips Combined (01..18)              ", lambda r: True),
    ):
        sub_p = [r for r in poc_rows if grp_filter(r)]
        sub_z = [zoned_by_clip[r["clip"]] for r in sub_p]
        n = len(sub_p)

        sp_pass = sum(1 for r in sub_p if float(r["spread_shortfall"]) == 0.0)
        sp_sf_m = sum(float(r["spread_shortfall"]) for r in sub_p) / n
        sp_kb_m = sum(int(r["spread_bytes"]) for r in sub_p) / (n * 1000.0)

        gl_pass = sum(1 for r in sub_p if float(r["settled_shortfall"]) == 0.0)
        gl_sf_m = sum(float(r["settled_shortfall"]) for r in sub_p) / n
        gl_kb_m = sum(int(r["settled_bytes"]) for r in sub_p) / (n * 1000.0)

        zn_pass = sum(1 for z in sub_z if float(z["zoned_shortfall"]) == 0.0)
        zn_sf_m = sum(float(z["zoned_shortfall"]) for z in sub_z) / n
        zn_kb_m = sum(int(z["zoned_bytes"]) for z in sub_z) / (n * 1000.0)
        sav_kb = gl_kb_m - zn_kb_m
        sav_pct = 100.0 * sav_kb / gl_kb_m

        print(
            f"{grp_label:44s} || "
            f"Pass {sp_pass:2d}/{n:2d} | SF {sp_sf_m:5.2f} | {sp_kb_m:5.1f} KB || "
            f"Pass {gl_pass:2d}/{n:2d} | SF {gl_sf_m:4.2f} | {gl_kb_m:5.1f} KB || "
            f"Pass {zn_pass:2d}/{n:2d} | SF {zn_sf_m:4.2f} | {zn_kb_m:5.1f} KB | {-sav_kb:+5.1f} KB ({-sav_pct:+4.1f}%)"
        )
    print("=" * 132)

    RESULTS.mkdir(parents=True, exist_ok=True)
    dest = RESULTS / "4_side_by_side_comparison.csv"
    with dest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(combined_out[0].keys()))
        writer.writeheader()
        writer.writerows(combined_out)
    print(f"Saved full 18-clip apples-to-apples comparison to: {dest}")


if __name__ == "__main__":
    main()
