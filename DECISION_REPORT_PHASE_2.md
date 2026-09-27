# DECISION REPORT — PHASE 2

Scope of this report: pure raw-data forensics on the already-downloaded, checksum-verified
PhysioNet v1.0.0 dataset. Nothing in `data/processed/` was created, no feature extraction ran, the
SSM algorithm was not touched, and the paper was not touched. Every number below was computed
directly from the raw files during this pass (commands available on request); nothing is
estimated or recalled from the old project.

---

## DECISION 1 — Split sessions (f14 / S11 / S16)

### 1. Exact subject/session/file IDs affected

| Activity | Subject | Files |
|---|---|---|
| STRESS | f14 | `Wearable_Dataset/STRESS/f14_a/{ACC,BVP,EDA,HR,IBI,TEMP,tags}.csv` and `f14_b/{...}` |
| AEROBIC | S11 | `Wearable_Dataset/AEROBIC/S11_a/{...}.csv` and `S11_b/{...}` |
| ANAEROBIC | S16 | `Wearable_Dataset/ANAEROBIC/S16_a/{...}.csv` and `S16_b/{...}` |

No other subject/activity combination in the dataset is split into `_a`/`_b` files.

### 2. What the official documentation says, verbatim

From `data_constraints.txt` (transcribed exactly, cp1252-decoded):

> **STRESS**
> • f14: Bluetooth connection was lost during registration. The baseline is in file f14_a, and
> the rest of the protocol is in file f14_b.
>
> **AEROBIC**
> • S11: Bluetooth connection was lost during registration. File S11_a includes data up to 105
> rpm, and S11_b includes the last 110 rpm block.
>
> **ANAEROBIC**
> • S16: Bluetooth connection was lost during registration. File S16_a includes two sprints, and
> S16_b includes two more sprints.

Note the word "registration" here is the Empatica E4 device's own session-registration handshake
with the recording app — i.e., a technical Bluetooth/software event — not a reference to this
project's cryptographic registration protocol. It is the reason the E4 app opened a brand-new
recording *file* on reconnection, which is why the data physically arrives as two files. It says
nothing about the physiological protocol itself restarting.

### 3. What the raw timestamps and files actually show (measured directly)

All figures below were read from each file's own header (UTC start time, sample rate) and row
count — not estimated.

**STRESS / f14** — real measured gap (ACC): **91.3 s**

| File | Start (UTC) | Rows | Rate | Duration | End (UTC) |
|---|---|---|---|---|---|
| f14_a/ACC.csv | 2013-07-12 22:46:39 | 22,518 | 32 Hz | 703.7 s | 2013-07-12 22:58:22.6875 |
| f14_b/ACC.csv | 2013-07-12 22:59:54 | 69,402 | 32 Hz | 2168.8 s | 2013-07-12 23:36:02.8125 |

Every other sensor (BVP, EDA, HR, TEMP) shows the same gap to within its own sample-rate's
quantization (BVP 91.3s, EDA 91.5s, TEMP 91.0s, HR 101.0s — HR's 1 Hz rate rounds coarsely).
`f14_a/tags.csv` has **0** tag lines (an untagged baseline recording); `f14_b/tags.csv` has 9 tag
lines starting at 23:02:16 — consistent with "the baseline is in f14_a, the rest of the protocol
[i.e., the tagged stress-inducing tasks] is in f14_b" exactly as documented.

**AEROBIC / S11** — real measured gap (ACC): **219.1 s**

| File | Start (UTC) | Rows | Rate | Duration | End (UTC) |
|---|---|---|---|---|---|
| S11_a/ACC.csv | 2013-03-08 12:40:29 | 51,804 | 32 Hz | 1618.9 s | 2013-03-08 13:07:27.875 |
| S11_b/ACC.csv | 2013-03-08 13:11:07 | 9,576 | 32 Hz | 299.2 s | 2013-03-08 13:16:06.25 |

`S11_a/tags.csv` has 10 tag lines (12:43:25 onward — consistent with a ramp protocol progressing
through multiple rpm stages up to 105 rpm); `S11_b/tags.csv` has 1 tag line (13:14:06) — consistent
with "S11_b includes the last 110 rpm block," i.e., the ramp simply continued from where it left
off, one stage further, after reconnection.

**ANAEROBIC / S16** — real measured gap (ACC): **51.4 s**

| File | Start (UTC) | Rows | Rate | Duration | End (UTC) |
|---|---|---|---|---|---|
| S16_a/ACC.csv | 2013-02-25 15:03:39 | 18,834 | 32 Hz | 588.6 s | 2013-02-25 15:13:27.5625 |
| S16_b/ACC.csv | 2013-02-25 15:14:19 | 21,624 | 32 Hz | 675.8 s | 2013-02-25 15:25:34.75 |

`S16_a/tags.csv` has 4 tag lines (15:06:48 onward, within "two sprints"); `S16_b/tags.csv` has 5
tag lines (15:15:05 onward, within "two more sprints") — again consistent with one interval
protocol (4 sprints total) continuing seamlessly across the reconnection.

### 4. Why the recordings were split

A Bluetooth disconnection between the Empatica E4 wristband and the recording phone/app, during
what the documentation calls "registration" (the device's own session-handshake with the app).
When Bluetooth reconnected, the E4 app started a new recording file rather than resuming the old
one — a limitation of the recording software/device, not an experimental decision. This is a
purely technical artifact of how the data was captured, not a redesign of the exercise or stress
protocol.

### 5. One physiological session interrupted, or two genuinely separate sessions?

The evidence points consistently to **one physiological session interrupted by a technical
disconnection**, not two separate sessions:

- In all three cases, the documentation itself describes the *same planned protocol* continuing
  across the split with no restart: the AEROBIC ramp continues to its next rpm block (not
  restarted from 0 rpm); the ANAEROBIC intervals continue with the next two sprints (not four new
  sprints); the STRESS protocol's baseline-then-tasks structure continues into its task phase.
- The measured gaps (51–219 seconds) are short relative to the session lengths (5–36 minutes) —
  consistent with a brief technical reconnection, not a scheduled break or a return visit.
- Tag markers in the `_a`/`_b` pairs are sequential and non-overlapping in time and in protocol
  stage (e.g., S16's 4 tags then 5 tags cover two-then-two sprints, not a repeated set), showing
  the protocol clock was never reset.
- There is no independent evidence (no note in `data_constraints.txt`, `subject-info.csv`, or the
  README) that the subject left and returned later, changed equipment, or that the experimenters
  treated the reconnection as a new session in their own protocol design.

### 6/7. Modeling as (A) one continuous session vs. (B) two separate sessions

Window counts below use the SSM's own 20-second check cadence applied to ACC (32 Hz → 640
samples/window); this is a mechanical count of complete windows in the raw data, not a feature-
extraction run.

| Pair | File A windows | File B windows | Total windows (same under A and B) |
|---|---|---|---|
| f14 (STRESS) | 35 | 108 | 143 |
| S11 (AEROBIC) | 80 | 14 | 94 |
| S16 (ANAEROBIC) | 29 | 33 | 62 |

**Key finding: the total window/event count for these three subjects is identical whether
modeled as A or B.** Windowing never spans the disconnection gap either way (there is no
recorded data during the gap to window). What differs between A and B is not how much data
exists, but how it is grouped and what happens at the reconnection boundary:

**Dataset-wide subject/session counts:**

| | Option A (continuous, 1 session per subject) | Option B (separate, old-pipeline behavior) |
|---|---|---|
| STRESS sessions | 36 | 37 |
| AEROBIC sessions | 30 | 31 |
| ANAEROBIC sessions | 31 | 32 |
| **Total sessions** | **97** | **100** |
| Distinct real subjects represented | 36 (each counted once per activity they performed) | 36 (f14, S11, S16 each counted twice within one activity) |

**Elapsed-time behavior at the reconnection boundary:**
- **Option A:** the SSM's `elapsed` clock keeps running through the disconnection. The real gap
  (51.4–219.1 s) is added to whatever `elapsed` had already accumulated before the gap. The
  reconnection is evaluated by Algorithm 1's ordinary rules (`elapsed > T_max`, `resumption_count
  ≥ R_max`, `S ≥ A_th`), exactly like any other reconnection-check inside a session. Since all
  three real gaps are well under `T_max=900s`, none of them alone forces a full re-authentication
  via the T_max rule — the SSM would need its normal R_max/anomaly logic to decide, same as usual.
- **Option B:** `elapsed` and `resumption_count` are reset to zero at the start of the `_b` file,
  as if a brand-new device had just connected for the first time — discarding the real gap
  entirely and replacing it with an implicit assumption of "no time has passed / no prior
  session existed."

**Number of possible first-authentication events:**
- **Option A:** exactly 1 forced first-session full-authentication per subject-activity-session,
  i.e., 97 dataset-wide (same rule applied uniformly to every subject, split or not).
  The reconnection after a real gap is NOT a forced first-auth under this option — it's an
  ordinary decision point.
- **Option B:** 100 dataset-wide — 3 more than Option A, because each `_b` file is treated as its
  own brand-new first connection, mechanically injecting one extra mandatory full-authentication
  per split subject that is not triggered by any of Algorithm 1's actual decision rules.

**Effect on SSM decisions:**
- Option B inserts 3 full-authentication events into the dataset that exist purely because of how
  "session" boundaries were drawn around a file-naming artifact, not because the SSM's own logic
  (elapsed/R_max/anomaly) determined a full auth was warranted. Whatever the eventual per-activity
  cost/bandwidth statistics look like, those 3 events would be counted alongside genuine
  SSM-triggered full auths, without being one.
- Option B also inflates the *statistical* weight of exactly these 3 subjects in any per-session
  mean/SD computed for downstream reporting (e.g., mean session duration, mean full/resume counts
  per session): each contributes 2 (shorter) sessions instead of 1, unlike every other subject.
- Option A is the only one of the two that actually exercises the SSM's decision logic against a
  real, measured disconnection gap — which is what the old paper's own Sec. VII-A already claims
  these three incidents are used for. Under Option B, that claim would not be true of the
  implementation, since the "test" never actually presents the SSM with the real elapsed-time gap.
- Neither option changes the *number* of feature windows/events produced — only how those events
  are grouped into sessions and what happens at exactly one boundary point per pair (3 points
  total, dataset-wide).

### 8. Which interpretation is better supported by the dataset documentation and evidence

**Option A (one continuous session, real gap inserted) is better supported.** The documentation's
own wording ("the rest of the protocol is in file f14_b," "S11_b includes the last 110 rpm
block," "S16_b includes two more sprints") explicitly describes protocol continuation, not
restart, in all three cases, and the tag-timing evidence independently confirms it. Option B is
not supported by any dataset documentation — it reflects the old pipeline's implementation
convenience (treating each file as an independent unit was presumably simpler to code), not a
property of the underlying data.

### 9. Confirmation

This recommendation is based solely on the documentation's own description of protocol
continuity and the independently measured tag-timing evidence above. No SSM decision counts,
compute-time figures, or bandwidth figures were computed or consulted in reaching it, because the
SSM engine has not been built yet in this rebuild (per your explicit instruction not to touch it
this round).

---

## DECISION 2 — S02 (STRESS) signal duplication

### 1. Exact file/session

`Wearable_Dataset/STRESS/S02/` — affects `ACC.csv`, `BVP.csv`, `EDA.csv`, and `TEMP.csv` within
this one subject/activity folder. `HR.csv` and `IBI.csv` are not directly addressed by the
documentation (see item 4).

### 2. Exact documented problem, verbatim

From `data_constraints.txt`:

> S02: Files downloaded from E4 Connect have duplicated signals. Duplicated raw values start in:
> ACC.csv: row 49,545; BVP.csv: row 99,091; EDA.csv and TEMP.csv: row 6,195. As IBI and HR files
> are obtained from the BVP signal through Empatica's algorithm, it is not evident where the
> duplicated data start.

### 3/4/5/6. Exact row range, and what the raw data actually shows (independently verified)

The documented row numbers are **1-indexed counts into the raw file as it appears on disk,
including the file's own 2 header lines** (i.e., "row 49,545" means literal file line 49,545,
same as opening the CSV in a text editor and counting from line 1). This convention was confirmed
empirically, not assumed: interpreting the row numbers this way and then comparing the data
byte-for-byte gives a **100% exact match, for the entire genuine-data length, in all four
files** — not an approximate resemblance, not a partial match:

| File | Total data rows | Genuine (first-copy) rows | Duplicate (second-copy) rows | Genuine duration | Full-length exact byte match? |
|---|---|---|---|---|---|
| ACC.csv | 99,084 | 49,542 | 49,542 | 1548.19 s | **Yes — 100%, every row** |
| BVP.csv | 198,176 | 99,088 | 99,088 | 1548.25 s | **Yes — 100%, every row** |
| EDA.csv | 12,384 | 6,192 | 6,192 | 1548.00 s | **Yes — 100%, every row** |
| TEMP.csv | 12,384 | 6,192 | 6,192 | 1548.00 s | **Yes — 100%, every row** |

All four sensors independently agree on the same genuine-recording duration (~1548.0–1548.25
seconds, ≈25.8 minutes), which is strong cross-sensor confirmation that this is a single real
~25.8-minute recording that was saved twice, back-to-back, inside each file — not four
independently corrupted files, and not new/different data appended. The documentation's own
description ("files downloaded from E4 Connect have duplicated signals") matches this exactly: a
download/export artifact, not a sensor malfunction during recording.

`HR.csv` (3,078 lines) and `IBI.csv` (3,061 lines) were also inspected. Since these are derived
from the BVP signal by Empatica's own proprietary beat-detection algorithm rather than being raw
sensor samples on a fixed clock, there is no reliable independent way to locate an exact
duplication boundary in them from the raw files alone — this matches the documentation's own
admission that "it is not evident where the duplicated data start" for these two files. This
project's SSM pipeline does not use HR or IBI for feature extraction, so this open question does
not block any decision needed here — noted for completeness only.

### 7. Number of samples and windows affected

- **Samples affected (i.e., duplicate, non-independent rows):** ACC 49,542 rows; BVP 99,088 rows;
  EDA 6,192 rows; TEMP 6,192 rows — exactly half of each file's total, in every case.
- **Windows affected**, using the SSM's 20-second/640-sample ACC windowing:
  - Truncating at the documented row leaves **77 genuine windows** (49,542 // 640).
  - Using the file as-is (untruncated) would produce **154 windows total, of which 77 would be
    built entirely from data that is an exact duplicate of another window already in the set.**

### 8. Compare treatments

**(A) Truncate at the documented row.** Keep only the first 49,542 ACC rows (and the
correspondingly verified genuine ranges for BVP/EDA/TEMP, if those signals are ever used).
Uses only independently-verified genuine samples; recording contributes ~1548s (25.8 min) instead
of its nominal full-file duration.

**(B) Exclude S02/STRESS entirely.** Drops this subject from the STRESS cohort. Simpler, but
discards ~25.8 minutes of fully genuine, verified real data for a problem that is precisely
diagnosed and precisely correctable.

**(C) Another scientifically justified treatment — considered and rejected:** using the file
as-is (no truncation, no exclusion). This is not a scientifically defensible option: 77 of the
154 candidate windows would be byte-for-byte identical to 77 other windows already in the
dataset. This is not merely "lower quality" data, it is **literally the same observations
counted twice** — treating them as independent windows would silently double this one subject's
effective sample count and would let two "different" windows agree perfectly with each other for
a reason that has nothing to do with real physiological or motion stability. No variant of
"downweighting" or "flagging" the duplicate half is preferable to simply not including
non-independent duplicate rows at all, so this option is not carried forward as a real
alternative to (A) or (B).

### 9. Effect of each treatment on the eventual feature dataset

- **(A) Truncate:** S02/STRESS contributes 77 genuine windows (~25.8 minutes) instead of the
  154-window figure a naive full-file read would produce. Sample size for STRESS shrinks by 77
  windows relative to a (scientifically invalid) full-file read, but every window included is
  independently verified genuine data.
- **(B) Exclude:** S02/STRESS contributes 0 windows to STRESS. Sample size for STRESS shrinks by
  154 windows relative to a full-file read, and by 77 relative to option A — discarding real,
  usable data that option A would have kept.
- **(C) As-is (rejected):** would silently include 77 duplicate windows, artificially inflating
  STRESS's window count by exactly the number of genuinely duplicate rows, and would corrupt any
  later statistic that assumes each window is an independent observation (e.g., any anomaly-score
  history/variance calculation that spans the duplication boundary would see a perfectly
  self-similar run of data that does not reflect real signal behavior).

### 10. Confirmation

This comparison is based only on the verified structure of the duplication (exact, byte-for-byte,
precisely located) and does not draw on any SSM decision counts or performance figures, which have
not been computed for this project yet.

---

## Data-handling recommendation status

Per your instructions, these are **findings and comparisons only** — no processed dataset,
feature table, SSM code, or paper text has been created or modified based on them. The
`DECISIONS_REQUIRED.md` provisional defaults (Option A for split sessions, Option A/truncate for
S02) are the same ones this deeper investigation continues to point to on the evidence, but they
remain marked OPEN until you confirm them.

---

## Raw dataset reproducibility check (as requested)

`data/raw/` currently holds the downloaded, extracted, checksum-verified copy of the dataset
**in this cloud workspace only** — it has not yet been transferred to your computer (only the
manifest, checksums, and scripts have been committed there so far).

`src/preprocessing/download_dataset.py` was tested just now in verification mode
(`--skip-download --skip-extract`, i.e., skipping the network fetch and re-using the already-
extracted copy) against the existing verified copy: it re-computed the zip's SHA-256, confirmed
it against the recorded reference hash, and re-verified all 708 extracted files against the
dataset's own `SHA256SUMS.txt` — **all checks passed, exit code 0.** This confirms the script's
verification logic is correct and working.

The script's actual *download* step (`curl -L -C -` against the official PhysioNet get-zip URL)
uses the identical command that was run manually, twice, to fetch this exact copy in the first
place (the fetch needed a resume partway through due to a slow connection, which `-C -` handles)
— so the download logic is proven-working command-by-command, but the full script has not yet
been run start-to-finish (download included) in one continuous execution within this session,
since that would mean re-downloading 73MB unnecessarily when the already-downloaded copy is
already verified byte-identical. If you want that full end-to-end run independently re-confirmed
before relying on it, say so and I'll run it here (or you can run it yourself in VS Code once the
project is on your machine, which doubles as your own independent reproduction check).
