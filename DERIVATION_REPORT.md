# Derivation Report — where every headline number comes from

This report traces each number that appears in the paper back through the
pipeline stage that produced it: **RAW DATA → PROCESSING → EVENT → SSM
DECISION → AGGREGATION → TABLE/FIGURE → PAPER**. No number in the paper is
hand-typed; every one is read out of a file under `results/` or
`paper/tables/`, which are themselves produced by running the scripts named
below. To regenerate everything from scratch: `python run_all.py` (or
`run_all.bat` on Windows) from a clean checkout with `data/raw/` populated
(see `README.md`).

## 1. Dataset → sessions (Decisions 1 & 2)

**RAW DATA**: `data/raw/extracted/.../*.csv` (PhysioNet E4 wearable dataset,
708 files, SHA-256 verified against
`data/checksums/PHYSIONET_OFFICIAL_SHA256SUMS.txt`).

**PROCESSING**: `src/preprocessing/session_builder.py::build_all_sessions()`
implements the two frozen decisions from `DECISION_REPORT_PHASE_2.md`:

- Split sessions (STRESS/f14, AEROBIC/S11, ANAEROBIC/S16): kept as ONE
  continuous session per Decision 1 Option A, with the real Bluetooth-gap
  preserved rather than concatenated away. The three measured gaps
  (`SPLIT_SESSIONS` dict) are read directly from each segment's own ACC.csv
  header timestamp + sample count, not assumed:
  - STRESS/f14: gap = 91.3 s
  - AEROBIC/S11: gap = 219.1 s
  - ANAEROBIC/S16: gap = 51.4 s
- S02/STRESS truncation (Decision 2 Option A): ACC/BVP/EDA/TEMP each
  truncated to the exact row counts documented in `DECISION_REPORT_PHASE_2.md`
  (`S02_TRUNCATION` dict: ACC 49542, BVP 99088, EDA 6192, TEMP 6192 rows),
  applied by `_read_acc_meta(..., truncate_rows=...)` so the duplicated
  second copy of the recording is never read.

**Output**: 97 sessions (STRESS=36, AEROBIC=30, ANAEROBIC=31), verified by
`session_summary_rows()` and printed at build time.

## 2. Sessions → windows → events

**PROCESSING**: `src/preprocessing/feature_extraction.py::extract_session_features()`
reads each session's accelerometer magnitude (respecting the Decision-2
truncation), splits it into non-overlapping 20 s windows
(`WINDOW_SEC=20`, trailing partial window dropped), and computes:

- `mean_mag`, `std_mag` per window.
- `z_score`: causal — computed only from the **prior** windows' `std_mag`
  history (a window is never scored against its own or future data), and
  the history **continues across the segment boundary** for the three split
  sessions rather than resetting.
- `elapsed_delta_sec`: `(window_start_utc − previous_window_start_utc)`,
  computed directly from real UTC timestamps in the source CSVs. This is
  what makes Decision 1 concrete: for the three split sessions, the window
  immediately after the reconnection automatically carries the real
  measured gap (leftover partial-window remainder + actual gap length) with
  no manual constant ever entered.

**Output**: `data/processed/feature_table.csv`, 10,318 rows (one row per
window, across all 97 sessions).

**Verification performed**: the `elapsed_delta_sec` for the first
post-reconnection window of each split session was checked by hand against
the raw timestamps and matches exactly: f14 = 115.0 s, S11 = 258.0 s,
S16 = 80.0 s (each = truncated final-window remainder + measured gap).

## 3. Windows → SSM decisions

**SSM DECISION**: `src/ssm/ssm_engine.py::run_session()` — THE one
authoritative engine (also the only engine imported by the sanity trace, the
real experiment, and the sensitivity sweep) — consumes each session's
`elapsed_delta_sec` and `z_score` sequence in order and applies Algorithm 1
(decision rule) governed by Algorithm 2 (anomaly score), with the frozen,
pre-registered constants recorded in `SSM_ALGORITHM_DECISION.md`:
`T_MAX_SEC=900, R_MAX=10, A_TH=0.5, W1=0.7, W2=0.3, Z_NORM_CAP=3.0`.
`A_TH=0.5` was fixed **before** this experiment was run (see
`SSM_ALGORITHM_DECISION.md` §1) specifically to correct the old paper's
mathematically-unreachable `A_th=1.5` against `S∈[0,1]`; it was never tuned
against these results.

**Verification performed**: `tests/test_ssm_engine.py`, 16/16 pass,
including an explicit test that `A_th=0.5` is reachable and a test that the
split-session reconnection is NOT treated as a forced first-authentication.

**Output**: `results/csv/ssm_event_log.csv` (10,318 rows: one row per window
with its `decision` ∈ {FULL_AUTH, RESUME}) and
`results/csv/ssm_session_summary.csv` (97 rows: one row per session with its
FULL_AUTH/RESUME counts and real wallclock duration).

## 4. Decisions → aggregated 24h-equivalent statistics

**AGGREGATION**: `experiments/experiment_03_ssm/run_ssm_experiment.py`
groups the 97 sessions' event counts by activity (STRESS/AEROBIC/ANAEROBIC),
computes each session's real wallclock duration (including any real gap),
and linearly extrapolates the mean per-session event rate to a 24h-equivalent
— the same disclosed extrapolation practice as the audited old paper
(`paper/audit/OLD_PAPER_AUDIT.md`), now applied to the corrected engine and
the real per-session durations. Per-event compute (ms) and bandwidth (bytes)
costs are the **measured** values from `results/json/crypto_benchmark.json`
(itself produced by `src/crypto/benchmark.py`, 2000 reps for cheap ops,
500 for KEM ops, 300 for full end-to-end handshake) and `src/protocol/protocol.py`'s
real serialized message sizes (928 B full handshake, 96 B resumption) — not
literature numbers.

**Output**: `results/json/ssm_activity_summary.json`, `results/json/crypto_benchmark.json`.

Headline numbers appearing in this file (verbatim, machine-computed, from the
canonical clean re-run of `run_all.py --skip-download` used to freeze the
paper's numbers):

| Activity   | n sessions | Compute-time reduction | Bandwidth reduction |
|------------|-----------:|------------------------:|----------------------:|
| STRESS     | 36         | 87.31%                  | 78.55%                |
| AEROBIC    | 30         | 83.67%                  | 75.27%                |
| ANAEROBIC  | 31         | 85.22%                  | 76.67%                |

**Reproducibility note on compute-time percentages**: the bandwidth-reduction
percentages above are exact and bit-for-bit reproducible on any machine,
because they come from fixed serialized message sizes (928 B / 96 B), not
timing. The compute-time-reduction percentages depend on
`results/json/crypto_benchmark.json`, which is a **real wall-clock
benchmark** of this machine's cryptographic operations; re-running
`src/crypto/benchmark.py` on different hardware, or even a different run on
the same shared cloud CPU, will shift the full-handshake mean latency by
roughly ±0.3 ms (observed across two clean runs in this rebuild: 8.89 ms and
8.57 ms), which moves the compute-time-reduction percentage by a few tenths
of a percentage point (e.g. STRESS 87.35% vs. 87.31%). This is expected,
disclosed timing variance, not an inconsistency — the ratio of full-handshake
to resumption cost is what drives the savings percentage, and that ratio is
stable to within this margin across runs. The numbers in the table above are
the specific run frozen for the paper; a reader re-running `run_all.py` on
their own machine should expect the same figures to within roughly ±0.5
percentage points.

These are honestly different from both the old paper (74.5/80.9/85.0% compute,
67.0/72.8/76.4% bandwidth) and the intermediate reproducibility-investigation
estimate (~91%/~82%) — see `OLD_VS_NEW_AUDIT.md`. The difference versus both
is expected and correct: this is the first run in the project's history where
`A_th` is inside `S`'s reachable range, so the anomaly branch of Algorithm 1
can actually fire.

## 5. Aggregation → tables and figures

**TABLE/FIGURE**: `src/analysis/generate_tables_figures.py` reads
**exclusively** from `results/json/crypto_benchmark.json`,
`results/json/ssm_activity_summary.json`, and
`results/json/sensitivity_analysis.json` (never from a hand-typed constant)
and writes:

- `paper/tables/table_ii_crypto_benchmark.csv` — Table II equivalent (14 real
  measured operation latencies + message sizes).
- `paper/tables/table_iii_ssm_results.csv` — Table III equivalent (the three
  rows above, plus raw full/resume 24h-equivalent event counts).
- `paper/figures/fig3_compute_cost.png` — grouped bar chart, classical vs.
  always-full-hybrid vs. proposed SSM, per activity, log scale, with real
  cross-session standard deviation error bars on the proposed bars.
- `paper/figures/fig4_sensitivity_tmax.png`, `fig5_sensitivity_ath.png` — real
  re-executions of `ssm_engine.py` over the 30 real AEROBIC sessions, sweeping
  `T_max` and `A_th` one at a time (`experiments/experiment_07_sensitivity/run_sensitivity.py`),
  not hypothetical curves.

## 6. Tables/figures → paper

The paper's Results section (`paper/source/`) embeds Table II, Table III,
and Figures 3–5 by reference to the generated files above, and states the
methodology paragraphs from §§1–4 of this report (split-session handling,
S02 truncation, causal z-score, real elapsed-time deltas, the `A_th=0.5`
fix, the 24h-equivalent extrapolation) in prose. No number in the Results
section, Abstract, or Conclusion was typed independently of these files —
the final consistency audit (`FINAL_REPRODUCIBILITY_REPORT.md`) greps the
paper source against these files' values to confirm this.

## 7. Formal verification (independent of the numeric pipeline above)

**PROCESSING**: `formal_verification/protocol_model.pv`, run with
`proverif -in pitype protocol_model.pv`, verifies all 8 queries true
(4 secrecy + 4 correspondence, single-session scope), correcting the old
project's backwards-direction correspondence query
(`paper/audit/OLD_PAPER_AUDIT.md` class F). The unbounded/replicated attempt
(`formal_verification/unbounded_attempt.pv`) is reported as honestly
incomplete — 7/8 true, 1 false, diagnosed as a likely modeling gap (missing
shared mutable resumption counter), not confirmed as a real vulnerability —
per `formal_verification/README.md`. The paper's Security Analysis section
states this exact scope and does not claim more than these two files
support.
