"""
The 25-event S01/AEROBIC trace, explicitly labeled a SANITY /
REPRODUCIBILITY TRACE -- NOT a real-world evaluation claim. Its purpose is
to give a small, human-readable, exactly-reproducible worked example of the
SAME authoritative ssm_engine.py that produced the full real-dataset
experiment (experiment_03_ssm/run_ssm_experiment.py), using real data. It is
not a substitute for, and must never be cited as, the real-world evaluation
in Table III -- that role belongs to the full 97-session experiment.

Per the old-paper audit (paper/audit/OLD_PAPER_AUDIT.md, Sec. 4): the old
"3 full auths / 22 resumes / 4896 bytes" version of this trace depended on
an undocumented per-script hack. This version uses the SAME first-session
rule and A_th fix as everywhere else in this project (SSM_ALGORITHM_DECISION.md)
-- whatever counts come out, come out; nothing here is special-cased to
reproduce the old numbers or any other target.
"""
import os
import sys
import csv
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "ssm"))
import ssm_engine as E  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
FEATURE_TABLE = os.path.join(REPO_ROOT, "data", "processed", "feature_table.csv")
BENCH_PATH = os.path.join(REPO_ROOT, "results", "json", "crypto_benchmark.json")
OUT_CSV = os.path.join(REPO_ROOT, "results", "csv", "sanity_trace_25event_S01_AEROBIC.csv")


def main():
    with open(BENCH_PATH) as f:
        bench = json.load(f)
    full_ms = bench["end_to_end"]["full_handshake"]["mean_ms"]
    resume_ms = bench["end_to_end"]["resumption"]["mean_ms"]
    full_bytes = bench["message_sizes"]["full_handshake_bytes"]
    resume_bytes = bench["message_sizes"]["resumption_bytes"]

    rows = []
    with open(FEATURE_TABLE) as f:
        for row in csv.DictReader(f):
            if row["activity"] == "AEROBIC" and row["subject"] == "S01":
                rows.append(row)
    rows.sort(key=lambda r: int(r["session_window_index"]))
    rows = rows[:25]

    elapsed_deltas = [float(r["elapsed_delta_sec"]) for r in rows]
    z_scores = [float(r["z_score"]) for r in rows]
    events = E.run_session(elapsed_deltas, z_scores)

    out_rows = []
    cumulative_bytes = 0
    cumulative_ms = 0.0
    for r, ev in zip(rows, events):
        nbytes = full_bytes if ev.decision == "FULL_AUTH" else resume_bytes
        nms = full_ms if ev.decision == "FULL_AUTH" else resume_ms
        cumulative_bytes += nbytes
        cumulative_ms += nms
        out_rows.append({
            "event": ev.index + 1, "z_score": round(ev.z, 4), "S": ev.S,
            "elapsed_sec": ev.elapsed_sec, "resumption_count": ev.resumption_count,
            "decision": ev.decision, "reason": ev.reason,
            "bytes": nbytes, "cumulative_bytes": cumulative_bytes,
            "cumulative_ms": round(cumulative_ms, 4),
        })

    n_full = sum(1 for r in out_rows if r["decision"] == "FULL_AUTH")
    n_resume = 25 - n_full

    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)

    print("SANITY / REPRODUCIBILITY TRACE (NOT a real-world evaluation claim)")
    print(f"Subject S01, activity AEROBIC, first 25 real windows, via ssm_engine.py:\n")
    for r in out_rows:
        print(f"  event {r['event']:>2}  z={r['z_score']:>7}  S={r['S']:>6}  "
              f"elapsed={r['elapsed_sec']:>6}  count={r['resumption_count']:>2}  "
              f"-> {r['decision']:<9} ({r['reason']})")
    print(f"\nFULL_AUTH = {n_full}, RESUME = {n_resume}, total bytes = {cumulative_bytes}, "
          f"total compute = {cumulative_ms:.3f} ms")
    print(f"\nWrote {OUT_CSV}")


if __name__ == "__main__":
    main()
