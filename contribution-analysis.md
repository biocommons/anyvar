## User

Review the commits on main in this repo. Compute the following:

- Timeline: The time between the first commit and the first commit between someone other than Reece
- Timeline: The time between the first commit and someone in the GA4GH group (Kori, James, Kyle, Jennifer Bowser, and Eugene Clark, by any email address)
- The time since first commit at which the GA4GH Group's contributions became the majority relative to other groups in aggregate. Measure contributions as # commits, # lines added, and churn (# lines added+edited+deleted)
`
For the above analyses, exclude vendored code, data files, etc.

## Analysis of `main` (518 commits, 2018‑11‑24 → present)

**Baseline — first commit:** `3b6d86e` by Reece Hart, **2018‑11‑24 20:39 PST**

### Timeline milestones

| Milestone | Commit | When | Time since first commit |
|---|---|---|---|
| First commit by someone other than Reece | `bf3f2b8` — Naomi Fox (Invitae) | 2021‑05‑21 | **908 days (~2.5 years)** |
| First commit by a GA4GH‑group member | `153b737` — Kori Kuzma | 2022‑07‑12 | **1,325 days (~3.6 years)** |

(Kori's first two commits landed within ~1 hour of each other on 2022‑07‑12; `153b737` is earliest in UTC.)

### When GA4GH group became the majority contributor

GA4GH group = Kori Kuzma, James Stevenson, Kyle Ferriter, Jennifer Bowser, Eugene Clark (all email aliases matched). Each metric crossed 50% exactly once and never reverted:

| Metric | Crossing commit | When | Time since first commit | Current GA4GH share |
|---|---|---|---|---|
| **# commits** | `add9edb` (James Stevenson), 125 vs 124 | 2025‑11‑10 | **2,542 days (~7.0 years)** | 75.9% (393 / 518) |
| **# lines added** | `3e0ae8b` (James Stevenson), 6,816 vs 5,867 | 2024‑09‑23 | **2,129 days (~5.8 years)** | 85.9% (41.4K / 48.2K) |
| **Churn (added + deleted)** | `454504f` (Eugene Clark), 9,869 vs 8,989 | 2024‑04‑29 | **1,982 days (~5.4 years)** | 86.6% (65.9K / 76.1K) |

The commit-count crossover is late because your 92 early commits plus other contributors set a high bar of 125 commits; GA4GH only matched it in Nov 2025 — but 2026's surge (238 commits, nearly all GA4GH) pushed them to a decisive 76% majority. The result is robust to excluding merge commits (crossover shifts only one day, to 2025‑11‑11).

### Methodology notes
- Ordered by history order on `origin/main`, using committer dates; line stats from `git log --numstat` (merge commits contribute to commit counts but not line counts).
- **Excluded as data/vendored:** [tests/data/](tests/data) (dominated by two UCSC chain files totaling ~293K lines — Jennifer's, which would have massively skewed her line counts), `demo/*.vcf`, and `*.ipynb` notebooks (JSON output blobs). No third‑party vendored code directories exist in the history.
- Lines "edited" appear in `numstat` as one deletion + one addition, so churn = additions + deletions captures adds, edits, and deletes.

---
*Exported from Claude Code and Codex Assist on 2026-11-05 19:17*
