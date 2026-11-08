"""Run and print a side-by-side comparison of `img-proof-of-concept` vs. `CSC612M-Paper`.

Usage:
    /opt/homebrew/bin/python3.13 src/compare_repos.py

Reads:
  1. `/Users/jkabarquez/img-proof-of-concept/clips/decisions.csv` (or fallback `data/poc_1080p_decisions.csv`)
  2. Runs `src/run_study.py` and `src/run_timing.py` to refresh `CSC612M-Paper/results/`
Outputs:
  - Formatted side-by-side tables in the terminal (5 selectors, clip-by-clip, kernel speed, zoning)
  - Saves `results/4_side_by_side_comparison.csv`
"""

import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DATA, RESULTS, ROOT
import run_study
import run_timing

POC_REPO_CSV = Path("/Users/jkabarquez/img-proof-of-concept/clips/decisions.csv")
POC_FALLBACK_CSV = DATA / "poc_1080p_decisions.csv"


def load_poc_decisions() -> list[dict]:
    try:
        if POC_REPO_CSV.exists():
            with POC_REPO_CSV.open(encoding="utf-8", newline="") as handle:
                return list(csv.DictReader(handle))
    except PermissionError:
        pass
    with POC_FALLBACK_CSV.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def summarize_poc(rows: list[dict], group: str = "comparison") -> dict[str, dict]:
    sub = [r for r in rows if r["group"] == group]
    out = {}
    for key in ("settled", "spread", "random", "cut", "detail"):
        sf90 = [float(r[f"{key}_shortfall"]) for r in sub if r.get(f"{key}_shortfall", "") != ""]
        sf80 = [float(r[f"{key}_shortfall80"]) for r in sub if r.get(f"{key}_shortfall80", "") != ""]
        sz = [int(r[f"{key}_bytes"]) for r in sub if r.get(f"{key}_bytes", "") != ""]
        crfs = [int(r[f"{key}_crf"]) for r in sub if r.get(f"{key}_crf", "") != ""]
        out[key] = {
            "pass90": f"{sum(1 for x in sf90 if x == 0.0)} / {len(sub)}",
            "failed_rungs": len(sub) - len(sf90),
            "mean_sf90": sum(sf90) / len(sf90) if sf90 else 0.0,
            "mean_sf80": sum(sf80) / len(sf80) if sf80 else 0.0,
            "mean_kb": (sum(sz) / len(sz)) / 1000.0 if sz else 0.0,
            "mean_crf": sum(crfs) / len(crfs) if crfs else 0.0,
        }
    return out


def summarize_paper(rows: list[dict], group: str = "screen") -> dict[str, dict]:
    sub = [r for r in rows if r["group"] == group]
    mapping = [
        ("settled", "text_crf", "text_short", "text_short_80", "text_bytes"),
        ("spread", "spread_crf", "spread_short", "spread_short_80", "spread_bytes"),
        ("random", "random_crf", "random_short", "spread_short_80", "spread_bytes"),
        ("cut", "cut_crf", "cut_short", "text_short_80", "text_bytes"),
        ("detail", "detail_crf", "detail_short", "text_short_80", "text_bytes"),
    ]
    out = {}
    for key, crf_k, sf90_k, sf80_k, sz_k in mapping:
        sf90 = [float(r[sf90_k]) for r in sub if r.get(sf90_k, "") != ""]
        sf80 = [float(r[sf80_k]) for r in sub if r.get(sf80_k, "") != ""]
        sz = [int(r[sz_k]) for r in sub if r.get(sz_k, "") != ""]
        crfs = [int(r[crf_k]) for r in sub if r.get(crf_k, "") != ""]
        out[key] = {
            "pass90": f"{sum(1 for x in sf90 if x == 0.0)} / {len(sub)}",
            "failed_rungs": len(sub) - len(sf90),
            "mean_sf90": sum(sf90) / len(sf90) if sf90 else 0.0,
            "mean_sf80": sum(sf80) / len(sf80) if sf80 else 0.0,
            "mean_kb": (sum(sz) / len(sz)) / 1000.0 if sz else 0.0,
            "mean_crf": sum(crfs) / len(crfs) if crfs else 0.0,
        }
    return out


def main():
    t0 = time.perf_counter()
    # Run timing and study silently to ensure results/ is fresh
    import io
    from contextlib import redirect_stdout

    with redirect_stdout(io.StringIO()):
        run_timing.main()
        run_study.main()
    elapsed = time.perf_counter() - t0

    poc_rows = load_poc_decisions()
    with (RESULTS / "2_selector_decisions.csv").open(encoding="utf-8", newline="") as handle:
        paper_rows = list(csv.DictReader(handle))

    poc_stats = summarize_poc(poc_rows, "comparison")
    paper_stats = summarize_paper(paper_rows, "screen")

    labels = {
        "settled": "1. Settled (cut+8..cut+15) [Ours]",
        "spread": "2. Evenly Spread (8 bin centers)",
        "random": "3. Random (8 seeded frames)",
        "cut": "4. On-the-Cut (cut..cut+7)",
        "detail": "5. High-Detail (luma variance)",
    }

    print("=" * 116)
    print(f"SIDE-BY-SIDE COMPARISON: img-proof-of-concept (1080p) vs. CSC612M-Paper (576p + Zoning)  [Recomputed in {elapsed:.2f}s]")
    print("=" * 116)
    print("\nTABLE A: All 5 Eight-Frame Selectors at Target VMAF 90")
    print("-" * 116)
    header = (
        f"{'Selector Rule':34s} | {'POC Pass':>9s} | {'POC Shortfall':>13s} | {'POC Size (CRF)':>16s} || "
        f"{'Paper Pass':>10s} | {'Paper Shortfall':>15s} | {'Paper Size (CRF)':>16s}"
    )
    print(header)
    print("-" * 116)

    csv_out = []
    for key in ("settled", "spread", "random", "cut", "detail"):
        p = poc_stats[key]
        q = paper_stats[key]
        p_size = f"{p['mean_kb']:5.1f} KB ({p['mean_crf']:.1f})"
        q_size = f"{q['mean_kb']:5.1f} KB ({q['mean_crf']:.1f})"
        print(
            f"{labels[key]:34s} | {p['pass90']:>9s} | {p['mean_sf90']:13.2f} | {p_size:>16s} || "
            f"{q['pass90']:>10s} | {q['mean_sf90']:15.2f} | {q_size:>16s}"
        )
        csv_out.append(
            {
                "selector": labels[key],
                "poc_pass_90": p["pass90"],
                "poc_missing_rungs": p["failed_rungs"],
                "poc_mean_shortfall_90": f"{p['mean_sf90']:.2f}",
                "poc_mean_kb": f"{p['mean_kb']:.1f}",
                "poc_mean_crf": f"{p['mean_crf']:.1f}",
                "paper_pass_90": q["pass90"],
                "paper_mean_shortfall_90": f"{q['mean_sf90']:.2f}",
                "paper_mean_kb": f"{q['mean_kb']:.1f}",
                "paper_mean_crf": f"{q['mean_crf']:.1f}",
            }
        )
    print("-" * 116)

    print("\nTABLE B: Clip-by-Clip Comparison on the 12 Shared Seeded Draws (Seed 20261010)")
    print("-" * 116)
    print(
        f"{'#':>2s} | {'Start':>5s} | {'POC Clip':>8s} | {'POC Spread->Settled CRF':>23s} | {'POC Shortfall':>14s} | {'POC Size (KB)':>15s} || "
        f"{'Paper Clip':>10s} | {'Paper CRF':>10s} | {'Paper Shortfall':>15s} | {'Paper Size (KB)':>15s}"
    )
    print("-" * 116)
    poc_by_num = {int(r["clip"]): r for r in poc_rows if r["group"] == "comparison"}
    paper_slides = [r for r in paper_rows if r["group"] == "screen" and r["name"] not in ("blank", "chart", "news")]
    for idx, q_row in enumerate(paper_slides, start=1):
        p_row = poc_by_num[idx]
        p_crf = f"CRF {p_row['spread_crf']} -> {p_row['settled_crf']}"
        p_sf = f"{float(p_row['spread_shortfall']):5.2f} -> {float(p_row['settled_shortfall']):4.2f}"
        p_kb = f"{int(p_row['spread_bytes'])//1000:3d} -> {int(p_row['settled_bytes'])//1000:3d} KB"
        q_crf = f"{q_row['spread_crf']} -> {q_row['text_crf']}"
        q_sf = f"{float(q_row['spread_short']):5.2f} -> {float(q_row['text_short']):4.2f}"
        q_kb = f"{int(q_row['spread_bytes'])//1000:3d} -> {int(q_row['text_bytes'])//1000:3d} KB"
        print(
            f"{idx:2d} | {q_row['start']:>5s} | {'clip ' + p_row['clip']:>8s} | {p_crf:>23s} | {p_sf:>14s} | {p_kb:>15s} || "
            f"{q_row['name']:>10s} | {q_crf:>10s} | {q_sf:>15s} | {q_kb:>15s}"
        )
    print("-" * 116)

    dest = RESULTS / "4_side_by_side_comparison.csv"
    with dest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(csv_out[0].keys()))
        writer.writeheader()
        writer.writerows(csv_out)
    print(f"\nSaved side-by-side table to: {dest}")


if __name__ == "__main__":
    main()
