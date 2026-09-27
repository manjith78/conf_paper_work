"""
Experiment 07 -- sensitivity analysis. Re-runs THE authoritative SSM engine
(src/ssm/ssm_engine.py) over the same real AEROBIC sessions used in
experiment_03, sweeping T_max (R_max, A_th held at their frozen defaults)
and separately sweeping A_th (T_max, R_max held at their frozen defaults),
to characterize how the corrected algorithm behaves away from its default
operating point. This does not change the frozen defaults used for the
headline Table III-equivalent result in experiment_03 -- it is a real
re-execution of the same engine and same data under different settings, not
a hypothetical.
"""
import os
import sys
import csv
import json
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "ssm"))
import ssm_engine as E  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
FEATURE_TABLE = os.path.join(REPO_ROOT, "data", "processed", "feature_table.csv")
BENCH_PATH = os.path.join(REPO_ROOT, "results", "json", "crypto_benchmark.json")
OUT_JSON = os.path.join(REPO_ROOT, "results", "json", "sensitivity_analysis.json")


def load_aerobic_sessions():
    rows_by_subject = {}
    with open(FEATURE_TABLE) as f:
        for row in csv.DictReader(f):
            if row["activity"] != "AEROBIC":
                continue
            rows_by_subject.setdefault(row["subject"], []).append(row)
    for subj in rows_by_subject:
        rows_by_subject[subj].sort(key=lambda r: int(r["session_window_index"]))
    return rows_by_subject


def run_with_overrides(sessions, full_ms, resume_ms, full_bytes, resume_bytes,
                        t_max=None, a_th=None, r_max=None):
    """Runs ssm_engine with temporarily overridden module-level constants,
    restoring them afterward -- this project has exactly one engine, so a
    sweep temporarily patches its constants rather than forking the logic."""
    orig = (E.T_MAX_SEC, E.A_TH, E.R_MAX)
    if t_max is not None:
        E.T_MAX_SEC = t_max
    if a_th is not None:
        E.A_TH = a_th
    if r_max is not None:
        E.R_MAX = r_max
    try:
        full_counts, resume_counts, durations_h = [], [], []
        for subj, rows in sessions.items():
            elapsed_deltas = [float(r["elapsed_delta_sec"]) for r in rows]
            z_scores = [float(r["z_score"]) for r in rows]
            events = E.run_session(elapsed_deltas, z_scores)
            full_counts.append(sum(1 for e in events if e.decision == "FULL_AUTH"))
            resume_counts.append(sum(1 for e in events if e.decision == "RESUME"))
            durations_h.append(len(rows) * E.WINDOW_SEC / 3600.0)
        n = len(sessions)
        mean_full = sum(full_counts) / n
        mean_resume = sum(resume_counts) / n
        mean_dur_h = sum(durations_h) / n
        scale = 24.0 / mean_dur_h
        full_24h = mean_full * scale
        resume_24h = mean_resume * scale
        proposed = full_24h * full_ms + resume_24h * resume_ms
        always_full = (full_24h + resume_24h) * full_ms
        savings_pct = 100 * (1 - proposed / always_full)
        return round(float(savings_pct), 2), round(float(mean_full), 3), round(float(mean_resume), 3)
    finally:
        E.T_MAX_SEC, E.A_TH, E.R_MAX = orig


def main():
    with open(BENCH_PATH) as f:
        bench = json.load(f)
    full_ms = bench["end_to_end"]["full_handshake"]["mean_ms"]
    resume_ms = bench["end_to_end"]["resumption"]["mean_ms"]
    full_bytes = bench["message_sizes"]["full_handshake_bytes"]
    resume_bytes = bench["message_sizes"]["resumption_bytes"]

    sessions = load_aerobic_sessions()

    t_max_sweep = []
    for t_max_min in [1, 3, 5, 10, 15, 30, 60]:
        savings, mf, mr = run_with_overrides(sessions, full_ms, resume_ms, full_bytes, resume_bytes,
                                              t_max=t_max_min * 60)
        t_max_sweep.append({"T_max_min": t_max_min, "savings_pct_vs_always_full": savings,
                             "mean_full_per_session": mf, "mean_resume_per_session": mr})

    a_th_sweep = []
    for a_th in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        savings, mf, mr = run_with_overrides(sessions, full_ms, resume_ms, full_bytes, resume_bytes,
                                              a_th=a_th)
        a_th_sweep.append({"A_th": a_th, "savings_pct_vs_always_full": savings,
                            "mean_full_per_session": mf, "mean_resume_per_session": mr})

    r_max_sweep = []
    for r_max in [2, 5, 10, 15, 20, 30]:
        savings, mf, mr = run_with_overrides(sessions, full_ms, resume_ms, full_bytes, resume_bytes,
                                              r_max=r_max)
        r_max_sweep.append({"R_max": r_max, "savings_pct_vs_always_full": savings,
                             "mean_full_per_session": mf, "mean_resume_per_session": mr})

    out = {
        "methodology": ("Real re-execution of src/ssm/ssm_engine.py over the same 30 real AEROBIC "
                         "sessions used in experiment_03, sweeping one parameter at a time with the "
                         "other two held at their frozen defaults (T_max=900s, R_max=10, A_th=0.5). "
                         "Not a hypothetical -- every point below is a real run of the same engine "
                         "against the same real data."),
        "defaults_held_when_not_swept": {"T_MAX_SEC": 900, "R_MAX": 10, "A_TH": 0.5},
        "t_max_sweep_minutes": t_max_sweep,
        "a_th_sweep": a_th_sweep,
        "r_max_sweep": r_max_sweep,
    }
    with open(OUT_JSON, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {OUT_JSON}")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
