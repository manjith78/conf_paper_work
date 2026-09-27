"""
Canonical session builder — implements the FROZEN data-handling decisions
from DECISION_REPORT_PHASE_2.md (approved 2026-09-24):

  Decision 1: STRESS/f14, AEROBIC/S11, ANAEROBIC/S16 are each ONE continuous
  physiological session split across two recording files by a Bluetooth
  disconnection. They are modeled as one session with the REAL measured
  gap preserved (not concatenated as if no time passed, and no artificial
  "first authentication" injected at the file boundary).

  Decision 2: STRESS/S02 has an exact, verified duplicate of its own first
  ~1548s appended starting at a documented row. Only the genuine (first)
  copy is used. Truncation boundaries below are the exact values verified
  in DECISION_REPORT_PHASE_2.md (byte-exact match confirmed over the full
  genuine length, all 4 affected sensor files).

This module builds the canonical, deduplicated list of (activity, subject)
sessions the entire pipeline uses, and is the ONLY place session grouping
logic lives -- feature extraction, the SSM engine driver, and the baseline
must all consume its output rather than re-deriving session boundaries.
"""
import os
import re
import csv
import datetime as dt
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
DATASET_DIR = os.path.join(
    REPO_ROOT, "data", "raw", "extracted",
    "wearable-device-dataset-from-induced-stress-and-structured-exercise-sessions-1.0.0",
)
WEARABLE_DIR = os.path.join(DATASET_DIR, "Wearable_Dataset")
SUBJECT_INFO_PATH = os.path.join(DATASET_DIR, "subject-info.csv")

ACTIVITIES = ["STRESS", "AEROBIC", "ANAEROBIC"]
SUBJECT_ID_RE = re.compile(r"^[Sf]\d{2}$")

# Decision 1 -- confirmed split-session pairs and their exact measured
# real disconnection gaps (seconds), computed from the raw ACC.csv headers
# in DECISION_REPORT_PHASE_2.md. These are DATA, not assumptions.
SPLIT_SESSIONS = {
    ("STRESS", "f14"): {"segments": ["f14_a", "f14_b"], "measured_gap_sec": 91.3},
    ("AEROBIC", "S11"): {"segments": ["S11_a", "S11_b"], "measured_gap_sec": 219.1},
    ("ANAEROBIC", "S16"): {"segments": ["S16_a", "S16_b"], "measured_gap_sec": 51.4},
}

# Decision 2 -- confirmed genuine (pre-duplication) row counts for
# STRESS/S02, verified byte-exact against the duplicate second half in
# DECISION_REPORT_PHASE_2.md. Only ACC is consumed by this pipeline
# (feature extraction uses accelerometer magnitude only), so only ACC's
# truncation actually affects downstream results; the others are recorded
# for completeness / any future sensor use.
S02_TRUNCATION = {
    ("STRESS", "S02"): {
        "ACC.csv": 49542,
        "BVP.csv": 99088,
        "EDA.csv": 6192,
        "TEMP.csv": 6192,
    }
}


@dataclass
class Segment:
    path: str
    start_time: dt.datetime = None
    n_samples: int = 0
    sample_rate: float = 0.0

    @property
    def duration_sec(self):
        return self.n_samples / self.sample_rate if self.sample_rate else 0.0

    @property
    def end_time(self):
        return self.start_time + dt.timedelta(seconds=self.duration_sec)


@dataclass
class Session:
    activity: str
    subject: str
    segments: list = field(default_factory=list)     # list[Segment], in order
    gap_before_segment: list = field(default_factory=list)  # gap_before_segment[i] = real gap (sec) before segments[i]; 0.0 for i=0
    is_split: bool = False


def _load_subject_roster():
    roster = []
    with open(SUBJECT_INFO_PATH, "r", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            subj = row.get("Info ", row.get("Info", "")).strip()
            if SUBJECT_ID_RE.match(subj):
                roster.append(subj)
    return roster


def _read_acc_meta(acc_path, truncate_rows=None):
    """Reads ACC.csv's own header (UTC start time, sample rate) and row
    count, applying Decision 2's truncation if this file is S02's affected
    ACC.csv. Returns a Segment. truncate_rows caps n_samples at a maximum
    verified-genuine row count -- never extends it."""
    with open(acc_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    start = lines[0].strip().split(",")[0]
    rate = float(lines[1].strip().split(",")[0])
    n = len(lines) - 2
    if truncate_rows is not None:
        n = min(n, truncate_rows)
    start_dt = dt.datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
    return Segment(path=acc_path, start_time=start_dt, n_samples=n, sample_rate=rate)


def build_all_sessions():
    """Returns list[Session], one per (activity, subject) that actually
    performed that activity, per subject-info.csv's own participation
    columns (AEROBIC/S12 and AEROBIC+ANAEROBIC/f14-f18 are correctly
    absent, not missing)."""
    roster = _load_subject_roster()
    sessions = []

    for activity in ACTIVITIES:
        act_dir = os.path.join(WEARABLE_DIR, activity)
        present_dirs = set(os.listdir(act_dir)) if os.path.isdir(act_dir) else set()

        for subj in roster:
            key = (activity, subj)
            if key in SPLIT_SESSIONS:
                spec = SPLIT_SESSIONS[key]
                seg_dirs = spec["segments"]
                if not all(d in present_dirs for d in seg_dirs):
                    continue
                segs = []
                for d in seg_dirs:
                    acc_path = os.path.join(act_dir, d, "ACC.csv")
                    trunc = S02_TRUNCATION.get(key, {}).get("ACC.csv")
                    segs.append(_read_acc_meta(acc_path, truncate_rows=trunc))
                gaps = [0.0] + [spec["measured_gap_sec"]]
                sessions.append(Session(activity=activity, subject=subj, segments=segs,
                                         gap_before_segment=gaps, is_split=True))
            elif subj in present_dirs:
                acc_path = os.path.join(act_dir, subj, "ACC.csv")
                trunc = S02_TRUNCATION.get(key, {}).get("ACC.csv")
                seg = _read_acc_meta(acc_path, truncate_rows=trunc)
                sessions.append(Session(activity=activity, subject=subj, segments=[seg],
                                         gap_before_segment=[0.0], is_split=False))
            # else: subject did not perform this activity -- correctly absent, skip.

    return sessions


def session_summary_rows():
    """Flat rows suitable for writing to CSV -- one row per session, for
    inspection/audit."""
    rows = []
    for s in build_all_sessions():
        total_samples = sum(seg.n_samples for seg in s.segments)
        total_duration = sum(seg.duration_sec for seg in s.segments)
        rows.append({
            "activity": s.activity,
            "subject": s.subject,
            "is_split": s.is_split,
            "n_segments": len(s.segments),
            "segment_dirs": ";".join(os.path.basename(os.path.dirname(seg.path)) for seg in s.segments),
            "total_acc_samples": total_samples,
            "total_recorded_duration_sec": round(total_duration, 2),
            "real_gap_sec": s.gap_before_segment[1] if s.is_split else 0.0,
            "truncated_for_duplication": (s.activity, s.subject) in S02_TRUNCATION,
        })
    return rows


if __name__ == "__main__":
    sessions = build_all_sessions()
    print(f"Built {len(sessions)} canonical sessions.")
    by_activity = {}
    for s in sessions:
        by_activity.setdefault(s.activity, []).append(s)
    for act, ss in by_activity.items():
        n_split = sum(1 for s in ss if s.is_split)
        print(f"  {act}: {len(ss)} sessions ({n_split} split, real-gap-preserved)")
    for s in sessions:
        if s.is_split:
            print(f"  SPLIT: {s.activity}/{s.subject} -- {len(s.segments)} segments, "
                  f"real gap = {s.gap_before_segment[1]}s, "
                  f"total ACC samples = {sum(seg.n_samples for seg in s.segments)}")
        if (s.activity, s.subject) in S02_TRUNCATION:
            print(f"  TRUNCATED: {s.activity}/{s.subject} -- ACC capped at "
                  f"{s.segments[0].n_samples} samples (duplication removed)")
