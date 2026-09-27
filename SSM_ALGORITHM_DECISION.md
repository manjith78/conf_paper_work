# SSM Algorithm Decision — frozen before running the real experiment

This file records the mathematical fix to Algorithm 2's scoring/threshold
inconsistency, and the first-session rule, BEFORE any real experimental
numbers were generated with them. Per the project's own rule, these choices
were made on structural/mathematical grounds only — no experiment output was
consulted or could have been consulted, since this file was written before
`experiments/experiment_03_ssm` was run.

## 1. The inconsistency being fixed

Algorithm 2 (old paper, Sec. IV-D) defines:

```
S = clamp(w1 * norm(z) + w2 * f, 0, 1)
```

`clamp(..., 0, 1)` makes `S` mathematically bounded to `[0, 1]` by
construction. The old paper's Algorithm 1 then checks `S >= A_th` with
`A_th = 1.5` — a threshold outside the score's own possible range. This
branch can therefore never fire, regardless of input (proven in the prior
discrepancy report and reproducibility investigation). This is not a
tuning choice to revisit; it's a domain/range mismatch that must be
corrected for the branch to be capable of firing at all.

## 2. The fix

`S`'s formula and range are kept EXACTLY as specified (no change to the
`w1`, `w2`, `norm(z) = min(z/3, 1)`, or `f = failed_resumptions/R_max`
terms — these remain the paper's original, disclosed-as-not-fit-to-data
configuration values). Only `A_th` is corrected to lie within `S`'s actual
range, `[0, 1]`.

**Rule used to pick the new `A_th`, decided before looking at any real
experiment output:** `S` is explicitly constructed (via `clamp`) to
represent "how anomalous, as a fraction of the score's own maximum
possible value." For a score deliberately normalized to `[0, 1]` in this
way, the natural, content-free decision boundary is its own midpoint —
exactly the same reasoning that makes 0.5 the default decision threshold
for any `[0,1]`-bounded classifier score in the absence of labeled data to
fit a different threshold (which Sec. IV-D already discloses `A_th` is,
since there is no labeled attack dataset here). This is a property of the
score's own definition, not a value chosen to produce any particular
compute-time or bandwidth outcome — no such outcome had been computed yet
when this choice was made.

**Frozen value: `A_th = 0.5`.**

This will NOT be adjusted after seeing the real experiment's results. If a
future revision wants a different `A_th`, it must be justified the same
way (from the score's own mathematical structure, or from a genuine
labeled-data fit) and re-documented here, never silently changed to move a
percentage.

## 3. `failed_resumptions` / `f` — an honest limitation, not a fabrication

Algorithm 2's `f = failed_resumptions / R_max` term requires a count of
resumption attempts that failed HMAC verification. The real PhysioNet
dataset contains no record of cryptographic resumption attempts (it is
accelerometer/physiological telemetry, not protocol logs) — there is no
real data source for `failed_resumptions` in the trace-driven experiment.

**Decision:** `failed_resumptions = 0` for every window in the trace-driven
real-dataset experiment, making `f = 0` identically, so `S` reduces to
`S = w1 * norm(z)` in practice for that experiment. This is stated
explicitly as a limitation in the paper's Limitations section — it is not
hidden, and it is not the same as claims that "the anomaly score reflects
resumption failures," which are not supported by anything measurable in
this dataset. The `f` term remains fully implemented in `ssm_engine.py`
(so a future experiment WITH real resumption-failure logs, e.g. from a live
protocol deployment, can use it), it simply evaluates to 0 for this
particular data source.

## 4. First-session rule — made explicit, not a hidden per-script hack

The old paper's Algorithm 1 pseudocode does not state what happens on a
device's very first-ever connection, when no resumption ticket exists yet.
The old `ssm_live_simulation.py` handled this with an undocumented
`if decision == "FULL_AUTH" or gw is None` hack; `scenario_simulation.py`
did not handle it at all (its first decision could spuriously come back
RESUME with no ticket to resume).

**Fix:** Algorithm 1 is given an explicit, stated first rule, checked
before the three original conditions:

```
0. if no resumption ticket exists yet for this device: return FULL_AUTH  (reason: "first-session")
1. elif elapsed > T_max: return FULL_AUTH
2. elif resumption_count >= R_max: return FULL_AUTH
3. elif S >= A_th: return FULL_AUTH
4. else: return RESUME
```

This applies uniformly to every session's first window — including the
first window of a split session's first segment (`f14_a`, `S11_a`,
`S16_a`) — and explicitly does NOT apply again at a split session's second
segment boundary (`f14_b`, `S11_b`, `S16_b`), per the frozen Decision 1:
the device is not modeled as losing its ticket just because the recording
file changed.

## 5. Frozen configuration for the real experiment

```
T_MAX_SEC = 900
R_MAX     = 10
A_TH      = 0.5      (corrected; was 1.5 against a [0,1] score in the old paper)
W1        = 0.7      (unchanged)
W2        = 0.3      (unchanged)
WINDOW_SEC = 20       (unchanged)
failed_resumptions = 0 for all real-dataset windows (Sec. 3 above; disclosed limitation)
```

Implemented once, in `src/ssm/ssm_engine.py`, and imported by every
consumer (real-dataset experiment, always-full baseline comparison,
25-event sanity trace, sensitivity analysis, and the test suite) — no
second copy of this decision logic exists anywhere else in the project.
