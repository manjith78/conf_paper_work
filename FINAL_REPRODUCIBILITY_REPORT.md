# Final Reproducibility Report and Quality-Gate Audit

This is the final check before declaring the rebuild complete. It runs the
whole pipeline again from a state equivalent to a clean checkout, re-verifies
the formal-verification claims, and audits the paper against the checklist
the rebuild was given at the start.

## 1. Clean-environment full pipeline re-run

`run_all.py --skip-download` was re-run against the already-verified
`data/raw/` (a full `--skip-download`-free run requires re-downloading the
~700-file, multi-hundred-MB PhysioNet archive, which was already
checksum-verified earlier in this project and is unnecessary to repeat for
this gate). Every stage completed with exit code 0, in order:

1. Session builder: 97 sessions (STRESS 36, AEROBIC 30, ANAEROBIC 31),
   3 split sessions with real gaps preserved, S02 truncation applied.
2. Feature extraction: 10,318 real windows; 97 first-of-session windows;
   3 first-after-gap windows with elapsed deltas of exactly 115.0s (f14),
   258.0s (S11), 80.0s (S16) -- matches the values recorded in
   `DERIVATION_REPORT.md`.
3. SSM engine unit tests: **16/16 passed.**
4. Protocol unit tests: **6/6 passed.**
5. Crypto benchmark: real numbers written to `results/json/crypto_benchmark.json`.
6. Real-dataset SSM experiment: STRESS 87.31%/78.55%, AEROBIC 83.67%/75.27%,
   ANAEROBIC 85.22%/76.67% (compute/bandwidth reduction).
7. 25-event sanity trace: 4 FULL_AUTH / 21 RESUME / 5,728 bytes.
8. Sensitivity sweep: T_max/A_th/R_max sweeps all completed.
9. Tables and figures regenerated from `results/` only.

**Compute-time reduction numbers on this specific re-run differ from an
earlier run in this same rebuild by up to 0.05 percentage points** (e.g.
STRESS 87.35% -> 87.31%), because they depend on a real wall-clock crypto
benchmark that has inherent timing noise on shared hardware. Bandwidth
reduction numbers (78.55%, 75.27%, 76.67%) are bit-for-bit identical across
both runs, as expected, since they depend only on fixed serialized message
sizes. This variance is disclosed in `DERIVATION_REPORT.md` §4,
`OLD_VS_NEW_AUDIT.md` §2, and the paper's Results/Limitations sections. The
numbers frozen into the paper (Sec. IX, Table III) are from this final
clean re-run.

## 2. Formal verification re-run

Both ProVerif models were re-run as part of this gate:

- `protocol_model.pv`: **all 8 queries true**, identical to the original run.
- `unbounded_attempt.pv`: **7/8 true, 1 false** (the same
  `gatewayAcceptsResume ==> wearableStartsResume` injective-correspondence
  query), identical diagnosis to the original run. Confirmed reproducible,
  not a one-off fluke.

## 3. Consistency audit against the paper

A grep-based sweep of `paper/source/paper.tex` for every old-paper number
(74.5, 80.9, 85.0, 67.0, 72.8, 76.4, and the old `A_th=1.5`) confirms each
occurrence is inside the explicitly-labeled "Comparison with an Earlier
Iteration of this Work" discussion (Sec. IX-A) or the SSM-fix explanation
(Sec. IV-D) -- i.e., always presented as a superseded prior result, never
as this paper's own claim. `A_TH = 0.5` (not 1.5) is confirmed as the actual
value used in `src/ssm/ssm_engine.py`.

Cross-checked for internal consistency:

- Abstract states "83.7-87.3% ... 75.3-78.6%"; Results (Sec. VIII-A) states
  the same range; Conclusion (Sec. XI) states the same range. Table III's
  three rows (87.31%, 83.67%, 85.22% compute; 78.55%, 75.27%, 76.67%
  bandwidth) are each inside the stated ranges. **Consistent.**
- Abstract states "97 real subject-sessions"; Sec. VII-A derives and states
  97 (36+30+31); Table III's session counts (36, 30, 31) sum to 97.
  **Consistent.**
- Security Analysis (Sec. VI) and Formal Verification (Sec. VII) both state
  "all eight queries...verified true" for the single-session model, and
  both separately, honestly report the unbounded attempt's one open finding
  -- neither section overstates the unbounded case as verified.
  **Consistent.**
- No table or figure is referenced in the paper text that does not exist
  under `paper/tables/` or `paper/figures/` (checked directly). No
  `TBD`/placeholder/`FIXME` markers remain in the paper source (checked
  directly). **Consistent.**
- The paper's Limitations section (Sec. X) and the abstract both state "no
  energy claim anywhere"; grepping `paper/source/paper.tex` and
  `src/crypto/benchmark.py` confirms no energy figure is computed or
  asserted anywhere in the codebase or the paper. **Consistent.**
- Every equation, algorithm, and protocol invariant stated in the paper
  (ciphertext-bound signature, verification-gates-state-update) is backed
  by a unit test in `tests/test_protocol.py` that specifically exercises
  that invariant and is currently passing. **Consistent.**

## 4. What is explicitly marked incomplete (not silently omitted)

- The unbounded/replicated ProVerif finding (`formal_verification/README.md`,
  paper Sec. VII/Limitations): open, not confirmed as a real vulnerability,
  not confirmed as a modeling artifact either -- explicitly unresolved.
- `failed_resumptions` is fixed at 0 throughout the real-dataset experiment;
  this term of Algorithm 2 is untested against real authentication-failure
  data (paper Limitations, `SSM_ALGORITHM_DECISION.md` §3).
- HR/IBI ambiguity for subject S02/STRESS remains unresolved; does not
  affect this project's results (uses accelerometer only), stated plainly
  rather than silently ignored (`DECISION_REPORT_PHASE_2.md` Decision 2,
  paper Sec. VII-A and Limitations).
- The `experiments/experiment_01_dataset_validation/` exploratory inventory
  script from the earliest phase of this rebuild (used to establish the
  36-real-subject roster before `session_builder.py` existed) was not
  carried forward into the final repository state under that name; its
  function is fully superseded by `session_builder.py`'s own roster
  loading and validation (`_load_subject_roster()`), which is exercised
  every time the pipeline runs and printed at build time. No dataset-
  validation capability was lost, but the specific standalone script and
  its CSV outputs from that early phase are not present in the final
  deliverable tree. Noted here for completeness rather than silently
  passed over.

## 5. Final deliverable checklist

| Deliverable | Status |
|---|---|
| Complete source code | Done (`src/`, `experiments/`, `tests/`) |
| Reproducible dataset downloader | Done (`src/preprocessing/download_dataset.py`) |
| Processed data | Done (`data/processed/feature_table.csv`, regenerable) |
| Feature derivation code | Done (`src/preprocessing/feature_extraction.py`) |
| SSM implementation (single source of truth) | Done (`src/ssm/ssm_engine.py`) |
| Crypto implementation | Done (`src/crypto/benchmark.py`, uses `src/protocol/protocol.py`) |
| Protocol implementation (single source of truth) | Done (`src/protocol/protocol.py`) |
| Baseline (always-full) | Done (`ssm_engine.run_always_full`, used in experiment/sensitivity) |
| Experiments | Done (`experiments/experiment_03_ssm`, `experiments/experiment_07_sensitivity`) |
| Event-level results | Done (`results/csv/ssm_event_log.csv`, 10,318 rows) |
| Benchmark results | Done (`results/json/crypto_benchmark.json`) |
| Sensitivity analysis | Done (`results/json/sensitivity_analysis.json`) |
| Figures | Done (`paper/figures/fig3-5*.png`, generated from results only) |
| Tables | Done (`paper/tables/table_ii*.csv`, `table_iii*.csv`, generated from results only) |
| Formal verification | Done, with one honestly-open finding (`formal_verification/`) |
| Tests | Done, 22/22 passing (`tests/`) |
| requirements.txt / lock file | Done (`requirements.txt`, `requirements-lock.txt`) |
| run_all.py / run_all.bat | Done, verified end-to-end on this machine |
| README.md | Done, rewritten to reflect final pipeline and Windows workflow |
| DERIVATION_REPORT.md | Done |
| OLD_VS_NEW_AUDIT.md | Done |
| FINAL_REPRODUCIBILITY_REPORT.md | This document |
| Final paper | Done (`paper/source/paper.tex`, compiles cleanly to `paper/final/paper_final.pdf`, 8 pages, IEEEtran conference format, no LaTeX errors, no undefined references, no overfull/underfull warnings after fixes) |

## 6. Overall verdict

Every quantitative claim in the paper traces to a file under `results/` or
`paper/tables/`, which trace to code that was actually run on this machine
against the actual, checksum-verified PhysioNet dataset, per
`DERIVATION_REPORT.md`. Both frozen data-handling decisions and the SSM
threshold correction were made and documented before the experiments that
depended on them were run, not adjusted afterward to fit a desired outcome.
Every disclosed limitation, every honestly-incomplete finding (the unbounded
ProVerif result), and every piece of run-to-run measurement variance is
stated plainly in at least one of: the paper's own Limitations section,
`DERIVATION_REPORT.md`, `OLD_VS_NEW_AUDIT.md`, or `formal_verification/README.md`
-- none is hidden or silently smoothed over. The project is complete and
ready for review.
