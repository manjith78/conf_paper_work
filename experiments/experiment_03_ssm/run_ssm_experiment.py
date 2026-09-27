"""
Experiment 03 -- runs THE authoritative SSM engine (src/ssm/ssm_engine.py)
decision-by-decision over every real session in data/processed/feature_table.csv
(built by src/preprocessing/feature_extraction.py, which already implements
the frozen Decision 1 / Decision 2 data-handling rules).

Produces full event-level logs (every single decision, fully traceable back
to its raw window) plus per-session and per-activity aggregates. This is the
ONLY place SSM decision counts / compute-time / bandwidth numbers for the
real dataset are computed -- nothing here is copied from or steered toward
the old paper's numbers, and nothing here re-implements Algorithm 1/2 --
it only calls ssm_engine.run_session().
"""
import os
import sys
import csv
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "ssm"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "protocol"))
import ssm_engine as E  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
FEATURE_TABLE = os.path.join(REPO_ROOT, "data", "processed", "feature_table.csv")
BENCH_PATH = os.path.join(REPO_ROOT, "results", "json", "crypto_benchmark.json")
EVENT_LOG_OUT = os.path.join(REPO_ROOT, "results", "csv", "ssm_event_log.csv")
SESSION_SUMMARY_OUT = os.path.join(REPO_ROOT, "results", "csv", "ssm_session_summary.csv")
ACTIVITY_SUMMARY_OUT = os.path.join(REPO_ROOT, "results", "json", "ssm_activity_summary.json")


def load_feature_table():
    sessions = {}  # (activity, subject) -> list of rows, ordered by session_window_index
    with open(FEATURE_TABLE) as f:
        for row in csv.DictReader(f):
            key = (row["activity"], row["subject"])
            sessions.setdefault(key, []).append(row)
    for key in sessions:
        sessions[key].sort(key=lambda r: int(r["session_window_index"]))
    return sessions


def main():
    with open(BENCH_PATH) as f:
        bench = json.load(f)
    full_ms = bench["end_to_end"]["full_handshake"]["mean_ms"]
    resume_ms = bench["end_to_end"]["resumption"]["mean_ms"]
    full_bytes = bench["message_sizes"]["full_handshake_bytes"]
    resume_bytes = bench["message_sizes"]["resumption_bytes"]

    sessions = load_feature_table()

    event_rows = []
    session_rows = []
    activity_events = {}

    for (activity, subject), rows in sessions.items():
        elapsed_deltas = [float(r["elapsed_delta_sec"]) for r in rows]
        z_scores = [float(r["z_score"]) for r in rows]

        ssm_events = E.run_session(elapsed_deltas, z_scores)
        baseline_events = E.run_always_full(len(rows))

        n_full = sum(1 for e in ssm_events if e.decision == "FULL_AUTH")
        n_resume = sum(1 for e in ssm_events if e.decision == "RESUME")
        proposed_bytes = n_full * full_bytes + n_resume * resume_bytes
        proposed_ms = n_full * full_ms + n_resume * resume_ms
        baseline_bytes = len(rows) * full_bytes
        baseline_ms = len(rows) * full_ms

        first_start = __import__("datetime").datetime.fromisoformat(rows[0]["window_start_utc"])
        last_start = __import__("datetime").datetime.fromisoformat(rows[-1]["window_start_utc"])
        real_wallclock_duration_sec = (last_start - first_start).total_seconds() + E.WINDOW_SEC

        for r, ev in zip(rows, ssm_events):
            event_rows.append({
                "activity": activity, "subject": subject,
                "session_window_index": r["session_window_index"],
                "segment_dir": r["segment_dir"],
                "window_start_utc": r["window_start_utc"],
                "z_score": r["z_score"],
                "elapsed_delta_sec": r["elapsed_delta_sec"],
                "ssm_elapsed_sec": ev.elapsed_sec,
                "ssm_resumption_count": ev.resumption_count,
                "ssm_S": ev.S,
                "ssm_z_norm": ev.z_norm,
                "ssm_f": ev.f,
                "ssm_decision": ev.decision,
                "ssm_reason": ev.reason,
                "is_first_window_after_gap": r["is_first_window_after_gap"],
            })

        session_rows.append({
            "activity": activity, "subject": subject,
            "n_windows": len(rows),
            "n_full_auth": n_full, "n_resume": n_resume,
            "real_wallclock_duration_sec": round(real_wallclock_duration_sec, 1),
            "proposed_compute_ms": round(proposed_ms, 4),
            "proposed_bytes": proposed_bytes,
            "always_full_baseline_compute_ms": round(baseline_ms, 4),
            "always_full_baseline_bytes": baseline_bytes,
        })

        activity_events.setdefault(activity, []).append(session_rows[-1])

    os.makedirs(os.path.dirname(EVENT_LOG_OUT), exist_ok=True)
    with open(EVENT_LOG_OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(event_rows[0].keys()))
        w.writeheader()
        w.writerows(event_rows)

    with open(SESSION_SUMMARY_OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(session_rows[0].keys()))
        w.writeheader()
        w.writerows(session_rows)

    activity_summary = {}
    for activity, srows in activity_events.items():
        n_sessions = len(srows)
        mean_duration_h = sum(r["real_wallclock_duration_sec"] for r in srows) / n_sessions / 3600.0
        mean_full = sum(r["n_full_auth"] for r in srows) / n_sessions
        mean_resume = sum(r["n_resume"] for r in srows) / n_sessions
        scale_to_24h = 24.0 / mean_duration_h

        full_24h = mean_full * scale_to_24h
        resume_24h = mean_resume * scale_to_24h
        proposed_ms_24h = full_24h * full_ms + resume_24h * resume_ms
        always_full_ms_24h = (full_24h + resume_24h) * full_ms
        proposed_bytes_24h = full_24h * full_bytes + resume_24h * resume_bytes
        always_full_bytes_24h = (full_24h + resume_24h) * full_bytes

        # real cross-session variability (not simulated) for error bars
        per_session_ms_24h = [
            (r["n_full_auth"] * (24.0 / (r["real_wallclock_duration_sec"] / 3600.0)) * full_ms
             + r["n_resume"] * (24.0 / (r["real_wallclock_duration_sec"] / 3600.0)) * resume_ms)
            for r in srows
        ]
        mean_ms24 = sum(per_session_ms_24h) / n_sessions
        var_ms24 = sum((v - mean_ms24) ** 2 for v in per_session_ms_24h) / n_sessions
        std_ms24 = var_ms24 ** 0.5

        activity_summary[activity] = {
            "n_real_sessions": n_sessions,
            "mean_session_wallclock_duration_min": round(mean_duration_h * 60, 2),
            "mean_full_events_per_session": round(mean_full, 4),
            "mean_resume_events_per_session": round(mean_resume, 4),
            "extrapolated_full_events_per_24h": round(full_24h, 2),
            "extrapolated_resume_events_per_24h": round(resume_24h, 2),
            "proposed_compute_ms_per_24h": round(proposed_ms_24h, 2),
            "proposed_compute_ms_per_24h_std_across_sessions": round(std_ms24, 2),
            "always_full_baseline_compute_ms_per_24h": round(always_full_ms_24h, 2),
            "compute_time_reduction_pct": round(100 * (1 - proposed_ms_24h / always_full_ms_24h), 2),
            "proposed_bytes_per_24h": round(proposed_bytes_24h, 1),
            "always_full_baseline_bytes_per_24h": round(always_full_bytes_24h, 1),
            "bandwidth_reduction_pct": round(100 * (1 - proposed_bytes_24h / always_full_bytes_24h), 2),
        }

    with open(ACTIVITY_SUMMARY_OUT, "w") as f:
        json.dump({
            "methodology": (
                "Full/resume decisions are produced by src/ssm/ssm_engine.py's run_session(), "
                "the ONE authoritative SSM implementation, called decision-by-decision over each "
                "real session's real elapsed-time deltas and accelerometer-derived z-scores "
                "(data/processed/feature_table.csv). Per-event compute cost and bandwidth come "
                "from results/json/crypto_benchmark.json (real measured latencies) and "
                "src/protocol/protocol.py's real serialized message sizes -- not literature "
                "figures. 'real_wallclock_duration_sec' per session includes any real measured "
                "disconnection gap (per the frozen split-session decision) since that time really "
                "elapsed for the device. Real per-session rates are linearly extrapolated to a "
                "24h-equivalent for comparability with an always-on deployment; this is the one "
                "disclosed modelling step, exactly as in the audited old paper (Sec. VIII)."
            ),
            "config": {
                "T_MAX_SEC": E.T_MAX_SEC, "R_MAX": E.R_MAX, "A_TH": E.A_TH,
                "W1": E.W1, "W2": E.W2, "WINDOW_SEC": E.WINDOW_SEC,
                "failed_resumptions": "0 for all real-dataset windows (no real data source; see SSM_ALGORITHM_DECISION.md Sec. 3)",
            },
            "crypto_costs_used": {
                "full_handshake_ms": full_ms, "resumption_ms": resume_ms,
                "full_handshake_bytes": full_bytes, "resumption_bytes": resume_bytes,
                "source": "results/json/crypto_benchmark.json (measured this run)",
            },
            "per_activity": activity_summary,
        }, f, indent=2)

    print(f"Wrote {EVENT_LOG_OUT} ({len(event_rows)} events)")
    print(f"Wrote {SESSION_SUMMARY_OUT} ({len(session_rows)} sessions)")
    print(f"Wrote {ACTIVITY_SUMMARY_OUT}")
    print(json.dumps(activity_summary, indent=2))


if __name__ == "__main__":
    main()
