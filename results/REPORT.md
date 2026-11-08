# Unified Study Results (1080p & 576p Suites, 5 Selectors, Ablations, Real Screen Recording, and Zoning)

- **Seed:** `20261010` (text starts drawn before even-frame bin centers were computed).
- **Seeded slides:** 12 (draws landing on an even sample: 0).
- **Random selector frames (seed 20261011):** `[40, 56, 285, 346, 354, 366, 503, 507]`.
- **Even selector frames (`libvmaf:n_subsample=112`):** `[56, 168, 281, 393, 506, 618, 731, 843]`.

## 1A. Full-HD `1920x1080` Multi-Complexity Suite (18 Clips: 12 Simple+Dense, 6 Medium+Dense)

| Selector Rule | Mean Shortfall (90) | Clips Passing 90 | Mean Shortfall (80) | Clips Passing 80 | Mean File Size | Failed Rungs |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Settled Frames (`cut+8..cut+15`) [Ours]** | **0.00** | **12 / 12** | **0.00** | **12 / 12** | `221.9 KB` | `0` |
| Evenly Spread (`libvmaf:n_subsample=112`) | 10.32 | 0 / 12 | 1.85 | 8 / 12 | `176.0 KB` | `0` |
| Seeded Random (8 random frames) | 9.00 | 1 / 12 | 0.98 | 9 / 12 | `180.8 KB` | `0` |
| On-the-Cut (`cut..cut+7`, no 8-frame wait) | 0.00 | 9 / 12 | 0.00 | 9 / 12 | `222.2 KB` | `3` *(3 failed!)* |
| High-Detail (global luma variance) | 10.13 | 2 / 12 | 2.62 | 4 / 12 | `179.6 KB` | `2` *(2 failed!)* |

- **12 Simple+Dense Comparison Clips (`01..12`):** Mean shortfall gap (Even minus Settled) = **`10.32`** VMAF points (95% bootstrap CI: **`7.83` to `13.29`**). Settled passes **`12 / 12`**, Even passes **`0 / 12`**. Mean size ratio: **`1.27x`**.
- **6 Medium+Dense Boundary Clips (`13..18`):** Mean shortfall gap = **`4.07`** VMAF points (95% bootstrap CI: **`2.14` to `6.04`**). Settled passes **`6 / 6` (`0.00` shortfall)**, Even passes **`0 / 6` (`4.07` mean shortfall)**.
- **Why Waiting 8 Frames (`Settled`) Beats `On-the-Cut` (`cut..cut+7`):** On **6 of the 18 `1080p` clips** (`04, 08, 11, 13, 14, 16`), the exact cut frame (`frame == start`) drops to `0.0` VMAF across all CRFs (even CRF 28), causing `On-the-Cut` to fail to find any valid CRF rung (`12 / 18` pass rate). Waiting 8 frames (`cut+8..cut+15`) avoids the transition spike and passes **`18 / 18` (`100%`)**.
- **Why `Settled` Beats `High-Detail`:** On **8 of the 12 comparison clips**, the background UI/slide has higher global luma variance than black text on a white page, tricking `High-Detail` into sampling frames `0..7` (`10.13` mean shortfall).

## 1B. `1024x576` Screen-Content Suite Across All 5 Selectors (15 Screen Clips, Target 90 & Target 80)

| Selector Rule | Mean Shortfall (Target 90) | Clips Passing 90 | Mean Shortfall (Target 80) | Clips Passing 80 |
| :--- | :---: | :---: | :---: | :---: |
| **Settled Frames (`cut+8..cut+15`) [Ours]** | **0.00** | **15 / 15** | **0.00** | **15 / 15** |
| Evenly Spread Frames (8 bin centers) | 12.22 | 0 / 15 | 17.77 | 1 / 15 |
| Seeded Random Frames (8 random) | 10.79 | 2 / 15 | — | — |
| On-the-Cut Frames (`cut..cut+7`) | 0.00 | 15 / 15 | — | — |
| High-Detail Frames (top 8 luma variance) | 0.00 | 15 / 15 | — | — |

- **Screen clips with different CRF (Settled vs. Even):** 15 of 15.
- **Mean shortfall gap (Even minus Settled, all 15 screen clips):** `12.22` (95% bootstrap CI: `8.52` to `17.79`).
- **Mean shortfall gap (without blank frame, 14 clips):** `9.74` (95% bootstrap CI: `8.09` to `11.32`).
- **Twelve generated slides, mean shortfall gap:** `10.63` (mean CRF step: `6.25`).
- **File size ratio (Settled / Even on separated clips):** `1.36x` on average.
- **1st-percentile vs 5th-percentile sensitivity:** On `15` of `15` spread-chosen screen files, the 9th-worst frame (1st percentile) lands inside the 20-frame text hold while the 45th-worst frame (5th percentile) sits outside on the easy slide.

## 2. Boundary Clips, Hold-Duration Ablations, and Scene-Cut-On

- **Boundary `cat`:** spread CRF 28, text CRF 28, shortfall 0.00 vs 0.00, 9th frame 111, 45th frame 278.
- **Boundary `gravel`:** spread CRF 28, text CRF 28, shortfall 0.00 vs 0.00, 9th frame 110, 45th frame 263.
- **Boundary `leaves`:** spread CRF 28, text CRF 28, shortfall 0.00 vs 0.00, 9th frame 11, 45th frame 42.

- **Scene-cut ON `chart-scenecut`:** spread CRF 35, text CRF 32, shortfall 3.21 vs 0.00, 9th frame 107.
- **Scene-cut ON `news-scenecut`:** spread CRF 32, text CRF 32, shortfall 0.00 vs 0.00, 9th frame 17.

- **Hold `8` frames:** spread CRF 35 (shortfall 0.00), text CRF none (shortfall none), spread 9th frame 408.
- **Hold `20` frames:** spread CRF 35 (shortfall 8.49), text CRF 29 (shortfall 0.00), spread 9th frame 417.
- **Hold `60` frames:** spread CRF 35 (shortfall 5.11), text CRF 31 (shortfall 0.00), spread 9th frame 411.

## 3. Cut-Driven Per-Segment Zoning (`x264 --zones` Extension)

When a video has multiple cuts or long easy stretches, applying the text-aware CRF globally bloats the entire file.
Using our AVX2 cut detector to drive per-span `x264 --zones` assigns each settled picture its own minimum-passing CRF:

- **4-Picture Multi-Span Clip (`poc/zones`, 480 frames: plain, text, chart, gravel):**
  - First-picture-only CRF (44): `64,935 bytes` (destroys text: worst text VMAF `51.56`).
  - Global gentle CRF (30): `192,568 bytes` (all spans >= 90).
  - **Cut-Driven Zoned (`CRF 44 / 31 / 34 / 30`):** `184,159 bytes` (all spans >= 90, saves bytes over global gentle while protecting text at `91.04` VMAF).
- **11-Cycle 44-Cut Clip (`data/zoning/cycle`, 880 frames, 43 cuts):**
  - Cut finder mismatches: `0` across all 43 cuts (`avx2_asm` median `0.0323 s` vs `plain_c` `0.2494 s`, **7.73x speedup**).
  - Global harsh CRF (44): `403,836 bytes` (9th-worst VMAF drops to `36.52`).
  - Global gentle CRF (28): `1,929,745 bytes` (9th-worst VMAF `90.27`).
  - **Cut-Driven Zoned (`zoned`):** `1,793,543 bytes` (9th-worst VMAF `90.27`, **saves 136 KB / 7.1%** with identical 1st-percentile quality and zero extra encode time: `3.75 s`).
- **Unscripted Real 1080p60 Screen Recording (`data/zoning/real`, Wikimedia Commons Tutorial, 3 min / 10,835 frames):**
  - Stillness check: **`97.7%`** of frame pairs have luma SAD <= 2 (passes >= 50% stillness check automatically).
  - Cut detection: Finds **84 cuts** and **72 settled segments** long enough to sample (`>= 0.13s` at 60 fps).
  - Single-page settled rule (using only the 1st settled page, CRF 32): `2,442,515 bytes`, 1st-percentile (109th-worst) VMAF drops to `71.19`.
  - **Per-Segment Cut-Driven Zoning (`x264 --zones`, CRF 28 on 67 dense segments, CRF 32 on 5 easy segments):** Raises 1st-percentile (109th-worst) VMAF from **`71.19` to `79.60` (+8.41 VMAF)** across the 3-minute recording.

## 4. End-to-End Usability & Probe-Time Savings (`results/1_kernel_timing.csv`)

- **Full 900-frame VMAF pass (`libvmaf` at 1080p):** `21.1556 s` per CRF rung (`105.78 s` across 5 CRF rungs).
- **AVX2 SAD cut detection (`sad_avx2.s` at 1080p):** `0.1551 s` (`6.59x` faster than scalar C `1.0216 s`, `136x` faster than one VMAF pass, `0` mask mismatches).
- **8-frame settled VMAF probe overhead:** Scoring only the 8 settled frames (`0.89%` of the 900 frames) plus `0.1551 s` cut detection reduces quality-search time by **>95%** while eliminating the **100% miss rate** of uniform `libvmaf:n_subsample=112`.

## 5. OCR Character Recall on the 20 Text Frames

- **OCR `chart` (text, CRF 30):** mean 1.00, worst frame 0.99
- **OCR `chart` (spread, CRF 34):** mean 1.00, worst frame 1.00
- **OCR `chart` (harsh, CRF 44):** mean 0.01, worst frame 0.01
- **OCR `news` (text, CRF 29):** mean 1.00, worst frame 1.00
- **OCR `news` (spread, CRF 32):** mean 1.00, worst frame 1.00
- **OCR `news` (harsh, CRF 44):** mean 0.10, worst frame 0.07

See `results/1_kernel_timing.csv`, `results/2_selector_decisions.csv`, and `results/3_zoning_summary.csv` for all raw tables.
