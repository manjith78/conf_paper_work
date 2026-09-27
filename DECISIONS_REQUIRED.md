# DECISIONS REQUIRED

**UPDATE — both decisions below are now RESOLVED and FROZEN.** This file is
kept as the historical record of the investigation (see
`DECISION_REPORT_PHASE_2.md` for the full evidentiary detail behind each
option). The user approved Decision 1 = Option A and Decision 2 = Option A;
both are implemented in `src/preprocessing/session_builder.py`
(`SPLIT_SESSIONS`, `S02_TRUNCATION`) and used throughout every experiment in
this project. Do not re-open either decision without an explicit new
instruction — re-litigating a frozen decision after results have been
generated from it is exactly the kind of after-the-fact tuning this project
was told never to do.

This file originally listed every ambiguity found during the Phase 0-2
investigation that required a human (scientific) decision rather than a
silent default. Status legend below reflects that original investigation;
read top-to-bottom as history, not as an open task list.

Status legend: `OPEN` = waiting on your decision. `DEFAULT-APPLIED` = a
provisional choice was made so the pipeline can keep running, clearly logged
as provisional, and trivially reversible once you decide.

---

## DECISION 1 — How to treat the three Bluetooth-disconnection split sessions

**Status:** OPEN (a provisional default is applied so the pipeline is not
blocked — see "Recommended choice" below — but this is reversible and must be
confirmed).

### What is ambiguous

The dataset physically splits three real recording sessions into two files
each, because the Empatica E4's Bluetooth link to the phone dropped mid-session
and had to reconnect under a new file name:

| Activity  | Subject | File A ends (UTC)         | File B starts (UTC)       | **Measured real gap** |
|-----------|---------|----------------------------|-----------------------------|----------------------|
| STRESS    | f14     | 2013-07-12 22:58:22.6875   | 2013-07-12 22:59:54         | **91.3 s**           |
| AEROBIC   | S11     | 2013-03-08 13:07:27.875    | 2013-03-08 13:11:07         | **219.1 s**          |
| ANAEROBIC | S16     | 2013-02-25 15:13:27.5625   | 2013-02-25 15:14:19         | **51.4 s**           |

(Gaps computed directly from each file's own ACC.csv header start-timestamp
and its measured sample count / sample rate — not estimated. Script:
`experiments/experiment_01_dataset_validation/build_inventory.py`.)

The question: when the new pipeline builds "sessions" for SSM simulation and
per-subject statistics, should `f14_a`+`f14_b` (and the S11, S16 pairs) be
modeled as:

- **(A) one continuous session** with the measured gap inserted as a real
  elapsed-time event in the SSM's timeline, or
- **(B) two independent sessions**, exactly as the OLD pipeline (`wearable_data.py`)
  actually did it (confirmed in the old `feature_table.csv`: `S11_a` and
  `S11_b` appear as two separate `subject` values)?

### Evidence

- The paper's own Sec. VII-A explicitly describes using real Bluetooth
  disconnection incidents to sanity-check the SSM's `T_max` and anomaly
  behavior against genuine connectivity gaps — which only makes sense if the
  gap is actually fed into the SSM as elapsed time. Treating the two halves
  as unrelated sessions (option B) discards exactly the information Sec.
  VII-A says it is testing.
- The OLD implementation used option B (each half is its own independent
  "subject" row in the per-session-mean aggregation feeding Table III's
  extrapolation), which double-counts one human subject in that statistic
  for these three cases and does not exercise the SSM's elapsed-time logic
  against a real disconnection at all.
- All three real gaps (51–219 s) are far below `T_max` = 900 s, so under
  option A none of them would trigger a forced full re-authentication by
  T_max alone — but they are still meaningful test cases for whether the
  anomaly-score / R_max path behaves sanely across a genuine idle gap, which
  is the sanity-check the paper claims to perform.

### Recommended choice

**Option A (one continuous session, real gap inserted).** It is more
faithful to what Sec. VII-A says these three incidents are for, it does not
double-count a subject, and the gap durations are real measured values (not
estimated), so there is no fabrication involved in implementing it — only in
*not* implementing it. This will need `src/preprocessing` to compute each
pair's real gap (already done once for inventory purposes; will be
generalized into a reusable function) and insert it into that subject's
elapsed-time trace as a genuine "idle" interval before resuming feature
extraction on the `_b` file.

### Effect of each choice on the experiment

- **Option A:** `S11`, `S16`, `f14` are each counted once (36 real subjects
  total across all three activities where present, not 39 "sessions"
  inflated by splits). The SSM elapsed-time trace for these three subjects
  will show one real ~1–4 minute gap; this is a legitimate, non-fabricated
  test of resumption-vs-idle behavior, and can be reported as such in the
  paper (a genuine field-observed connectivity gap, distinct from the
  25-event sanity trace).
- **Option B:** Matches the OLD pipeline's actual behavior exactly (useful
  only if you want numeric continuity with the old per-session-mean
  statistic for direct comparison in `OLD_VS_NEW_AUDIT.md`), but perpetuates
  the double-count and forfeits the real disconnection-gap test the paper
  claims to run.

**Provisional default until you decide:** the pipeline will implement Option
A (continuous session, real gap inserted) as the primary/authoritative
treatment, and will *also* emit an Option-B-style split accounting in a
clearly labeled secondary output, so a like-for-like comparison against the
old pipeline's numbers remains possible without making Option B the
paper's official methodology.

---

## DECISION 2 — S02/STRESS ACC.csv documented duplication (truncate or exclude?)

**Status:** OPEN.

### What is ambiguous

`data_constraints.txt` documents that `STRESS/S02` has duplicated signal data
starting at specific row numbers (ACC row 49,545; BVP row 99,091; EDA/TEMP
row 6,195). Measured fact: `STRESS/S02/ACC.csv` has 99,086 data rows total —
consistent with a genuine duplication of roughly the back half of the file,
not a labeling error. The question: should the new pipeline (a) truncate
each of S02's affected sensor files at its documented duplication row before
windowing/feature extraction, (b) exclude S02/STRESS entirely from the
experiment, or (c) use the file as-is?

### Evidence

- The dataset's own documentation identifies the exact row at which real
  signal stops and duplicate (non-independent) samples begin. Using the file
  as-is (option c) would treat duplicated samples as if they were
  independent new measurements, artificially inflating the number of
  "distinct" feature windows for one subject and violating the
  no-fabrication/no-silent-corruption rule just as surely as inventing data
  would.
- Truncating at the documented row (option a) uses only verified-real,
  non-duplicated data and is directly supported by the dataset's own
  documentation — no guessing about where the real data ends.

### Recommended choice

**Option A (truncate at the documented row).** This keeps S02 in the STRESS
cohort (preserving sample size) while using only verified-genuine samples.
The truncation point is not something we are inventing — it is copied
verbatim from `data_constraints.txt`.

### Effect of each choice on the experiment

- **Option A:** S02/STRESS contributes a shorter but 100% genuine recording
  (~25.8 minutes of ACC at 32 Hz instead of the nominal ~51.6 minutes implied
  by the full row count). Feature windows computed from the tail past row
  49,545 are dropped.
- **Option B (exclude S02/STRESS entirely):** Simpler, but discards an
  otherwise-usable ~25.8 minutes of real, verified data for no reason beyond
  convenience.
- **Option C (use as-is):** REJECTED — would silently include known-duplicate,
  non-independent samples in the feature/statistics pipeline. This is the
  one option that is scientifically indefensible regardless of what you
  decide on A vs. B, since it directly contradicts documented ground truth
  we already have in hand.

**Provisional default until you decide:** Option A is applied (truncate at
the documented row) since Option C is excluded on scientific grounds and
Option A vs. B is a sample-size/convenience tradeoff, not a validity one.

---

## DECISION 3 — STRESS/f07: BVP and TEMP files present but documented invalid

**Status:** INFORMATIONAL — no action needed, but flagged for completeness.

### What is ambiguous

`data_constraints.txt` documents that for `STRESS/f07`, the protective
wristband dock was never removed, so only EDA and ACC are scientifically
valid; BVP and TEMP readings, though physically present as files (confirmed:
all 7 sensor files exist on disk for f07), do not reflect real physiological
signal.

### Evidence / effect

The SSM pipeline in this project only ever consumes **ACC** data for feature
extraction (accelerometer-derived motion/activity features feed the
anomaly score). Since ACC is documented valid for f07 and BVP/TEMP are never
used downstream, this constraint has **no effect on the SSM experiment
pipeline**. It is recorded here, and will be recorded in the dataset
manifest, purely so this fact is not silently lost — but it does not require
a choice.

---

## Ambiguities NOT yet found requiring a decision

None beyond the above at this stage of the audit (Phase 0–2 groundwork).
Phase 3 onward (feature extraction, SSM redesign) may surface further
decisions; they will be appended to this file, never silently resolved.
