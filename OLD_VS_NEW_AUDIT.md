# Old Paper vs. New Rebuild — Audit

This document exists so a reader (or the student's guide/examiner) can see
exactly which numbers changed, and why, without suspecting cherry-picking.
**The new pipeline's numbers are authoritative.** At no point in this
rebuild was any new number adjusted, chosen, or re-run to move it closer to
an old number. The old paper's numbers are shown here only for comparison
and are not used anywhere else in the new paper, code, or tests.

## 1. The core bug this rebuild fixes

The old paper defined the anomaly score `S` to be clamped into `[0, 1]`
(Algorithm 2) but set the anomaly-trigger threshold `A_th = 1.5` (Algorithm 1).
Since `S` can never exceed 1.0, the anomaly branch of the decision logic was
**mathematically unreachable** — it could never fire, regardless of how
anomalous the input was. This was found and documented in
`paper/audit/OLD_PAPER_AUDIT.md` (class A/critical) during the
reproducibility investigation, and independently confirmed here in
`SSM_ALGORITHM_DECISION.md` before any new experiment was run.

**Fix**: `A_th` set to `0.5` — the midpoint of `S`'s own declared range —
decided and written down in `SSM_ALGORITHM_DECISION.md` *before* the real
dataset experiment (`experiments/experiment_03_ssm/run_ssm_experiment.py`)
was executed. This is the single largest reason the new numbers differ from
the old ones: this is the first version of this project where the anomaly
branch can actually trigger.

## 2. Headline result comparison

| Activity   | Old paper compute reduction | New pipeline compute reduction | Old paper bandwidth reduction | New pipeline bandwidth reduction |
|------------|-----------------------------:|---------------------------------:|--------------------------------:|-----------------------------------:|
| STRESS     | 74.5%                        | **87.31%**                       | 67.0%                           | **78.55%**                         |
| AEROBIC    | 80.9%                        | **83.67%**                       | 72.8%                           | **75.27%**                         |
| ANAEROBIC  | 85.0%                        | **85.22%**                       | 76.4%                           | **76.67%**                         |

(Compute-time reduction figures carry roughly ±0.5 percentage point run-to-run
timing variance, since they depend on a real wall-clock crypto benchmark;
bandwidth reduction figures are exact and deterministic. See
`DERIVATION_REPORT.md` §4 for the disclosed variance.)

An intermediate reproducibility-investigation estimate (computed by hand
before this rebuild existed, applying Algorithm 2 as literally written but
without a full re-implementation) had suggested numbers around 91%/82%
compute/bandwidth reduction. **The real, fully-implemented, test-verified
pipeline built in this rebuild does not match that estimate either.** This
is expected: the hand-estimate did not account for several effects the real
engine now handles precisely — causal (not lookahead) z-scoring, per-window
resumption-count resets on FULL_AUTH, the real (not assumed) elapsed-time
deltas across the three split sessions, and the exact R_max/T_max boundary
semantics (`>` vs `>=`) verified by the 16 boundary tests in
`tests/test_ssm_engine.py`. None of the three numbers above (old paper,
hand-estimate, or new pipeline) was used as a target for any other — each
is what it is because of the assumptions and code that produced it, and
only the new pipeline's numbers are used in the new paper.

## 3. Methodological differences (why an exact match was never expected)

| Aspect | Old paper | New rebuild |
|---|---|---|
| `A_th` vs. `S` range | `A_th=1.5`, `S∈[0,1]` — unreachable | `A_th=0.5`, `S∈[0,1]` — reachable, fixed pre-registration |
| Split sessions (f14/S11/S16) | Not documented; unclear if concatenated or excluded | Kept as one continuous session, real gap preserved (Decision 1) |
| S02/STRESS duplication | Not documented; unclear if raw duplicate rows were included | Truncated to the documented boundary rows (Decision 2) |
| z-score computation | Not fully specified in old paper text | Causal, computed only from prior windows, continues across segment boundaries |
| Elapsed-time state | Not clear whether assumed-constant or measured | Computed from real UTC timestamps, per-window |
| SSM engine | Possibly multiple/inconsistent implementations across paper text, code, experiment (unverified — old repo not fully available) | ONE authoritative `src/ssm/ssm_engine.py`, imported everywhere, 16/16 boundary tests |
| Formal model | 9-query model, 1 query false due to a backwards-direction correspondence assertion | 8-query model, corrected direction, all 8 true; unbounded attempt run and honestly reported as incomplete |

## 4. What did NOT change

- The three cryptographic primitives (Ed25519, ML-KEM-512, HMAC-SHA256/AES-128-GCM/HKDF-SHA256)
  and the overall two-phase (full-handshake / resumption) protocol structure are the same
  design as the old paper — this rebuild re-implements and re-verifies them, it does not
  redesign the protocol.
- The dataset (PhysioNet E4 wearable stress/exercise dataset) and the three activity
  categories (STRESS/AEROBIC/ANAEROBIC) are the same as the old paper.
- The 24h-equivalent linear extrapolation methodology (real short session → 24h projection)
  is the same disclosed technique the old paper used, now applied to real per-session
  durations that include the measured disconnection gaps.

## 5. Explicit non-goal

This rebuild was never asked to, and did not attempt to, reproduce the old
paper's specific numbers (74.5%, 80.9%, 85.0%, 67.0%, 72.8%, 76.4%, or any
other old-paper figure). Any resemblance or difference between old and new
numbers in the table above is incidental to fixing the underlying
methodology, not a target that was optimized toward or away from.
