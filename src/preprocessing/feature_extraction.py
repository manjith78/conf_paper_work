"""
Feature extraction -- builds the per-window feature table the SSM engine
consumes, from the canonical sessions produced by session_builder.py.

For each session (a subject's one continuous physiological recording for
one activity, per the frozen Decision 1/2 data-handling rules):

  1. Read real ACC x/y/z samples per segment (Decision 2 truncation already
     applied by session_builder for STRESS/S02).
  2. Compute accelerometer magnitude = sqrt(x^2+y^2+z^2).
  3. Split into non-overlapping 20-second windows (640 samples at the
     dataset's real 32 Hz ACC rate) -- WINDOW_SEC matches the SSM's own
     connectivity-check cadence. A trailing partial window (< 640 samples)
     at the end of a segment is dropped, exactly as with any other
     subject's session.
  4. For each window, compute mean/std of the magnitude, and a CAUSAL
     z-score of std against the window's own session history (mean/std of
     all PRIOR windows in the SAME session -- continuing across a segment
     boundary for split sessions, per Decision 1: the physiological
     baseline is not reset just because the recording file changed).
  5. Compute each window's REAL UTC start time directly from its segment's
     header timestamp + sample offset, and from that the REAL elapsed-time
     delta (seconds) since the previous window in the same session. Within
     a segment this is always exactly WINDOW_SEC (fixed sample rate, no
     drops). Across a split-session boundary, this delta is derived
     directly from real timestamps and therefore automatically includes
     both the measured disconnection gap AND any leftover sub-window
     remainder at the end of the prior segment -- nothing is assumed or
     rounded to a constant.

Output: data/processed/feature_table.csv, one row per window, columns:
  activity, subject, session_window_index, segment_dir, mean_mag, std_mag,
  z_score, elapsed_delta_sec, is_first_window_of_session,
  is_first_window_after_gap
"""
import os
import csv
import math
import datetime as dt

from session_builder import build_all_sessions, WEARABLE_DIR

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT_PATH = os.path.join(REPO_ROOT, "data", "processed", "feature_table.csv")

WINDOW_SEC = 20  # matches the SSM's periodic connectivity-check cadence
WARMUP_WINDOWS = 3  # matches the paper's original Algorithm-2 grounding script: first 3 windows of a session have no history yet, z=0 by definition


def read_acc_magnitude(segment):
    """Reads real x,y,z samples for one segment (respecting session_builder's
    truncation, i.e. only reading up to segment.n_samples rows) and returns
    the per-sample magnitude array."""
    path = segment.path
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    data_lines = lines[2:2 + segment.n_samples]
    mags = []
    for line in data_lines:
        parts = line.strip().split(",")
        if len(parts) < 3:
            continue
        try:
            x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError:
            continue
        mags.append(math.sqrt(x * x + y * y + z * z))
    return mags


def window_segment(mags, window_len):
    """Non-overlapping windows; trailing partial window dropped."""
    n_windows = len(mags) // window_len
    out = []
    for i in range(n_windows):
        seg = mags[i * window_len:(i + 1) * window_len]
        mean = sum(seg) / len(seg)
        var = sum((v - mean) ** 2 for v in seg) / len(seg)
        std = math.sqrt(var)
        out.append((mean, std))
    return out


def extract_session_features(session):
    """Returns list of row-dicts for one session, in real chronological
    order, with causal z-score and real elapsed-time deltas computed
    across segment boundaries."""
    rows = []
    stds_history = []  # running list of std_mag for all prior windows in this session
    window_start_utc_prev = None

    for seg_idx, segment in enumerate(session.segments):
        window_len = int(WINDOW_SEC * segment.sample_rate)
        mags = read_acc_magnitude(segment)
        windows = window_segment(mags, window_len)
        seg_name = os.path.basename(os.path.dirname(segment.path))

        for w_idx, (mean_mag, std_mag) in enumerate(windows):
            window_start_utc = segment.start_time + dt.timedelta(seconds=w_idx * WINDOW_SEC)

            is_first_of_session = (seg_idx == 0 and w_idx == 0)
            is_first_after_gap = (seg_idx > 0 and w_idx == 0)

            if is_first_of_session:
                elapsed_delta = 0.0  # reference point t=0 for this session; consumed as the mandatory first-auth event, not a real gap
            else:
                elapsed_delta = (window_start_utc - window_start_utc_prev).total_seconds()

            if len(stds_history) < WARMUP_WINDOWS:
                z = 0.0
            else:
                hist_mean = sum(stds_history) / len(stds_history)
                hist_var = sum((v - hist_mean) ** 2 for v in stds_history) / len(stds_history)
                hist_std = math.sqrt(hist_var)
                z = abs(std_mag - hist_mean) / max(hist_std, 1e-6)

            rows.append({
                "activity": session.activity,
                "subject": session.subject,
                "session_window_index": len(rows),
                "segment_dir": seg_name,
                "window_start_utc": window_start_utc.isoformat(),
                "mean_mag": round(mean_mag, 6),
                "std_mag": round(std_mag, 6),
                "z_score": round(z, 6),
                "elapsed_delta_sec": round(elapsed_delta, 3),
                "is_first_window_of_session": is_first_of_session,
                "is_first_window_after_gap": is_first_after_gap,
            })

            stds_history.append(std_mag)
            window_start_utc_prev = window_start_utc

    return rows


def main():
    sessions = build_all_sessions()
    all_rows = []
    for s in sessions:
        all_rows.extend(extract_session_features(s))

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    fieldnames = list(all_rows[0].keys())
    with open(OUT_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in all_rows:
            w.writerow(row)

    print(f"Extracted {len(all_rows)} real windows across {len(sessions)} sessions.")
    print(f"Wrote {OUT_PATH}")

    # sanity checks, printed for the record
    n_first = sum(1 for r in all_rows if r["is_first_window_of_session"])
    n_after_gap = sum(1 for r in all_rows if r["is_first_window_after_gap"])
    print(f"Windows flagged as first-of-session: {n_first} (should equal session count = {len(sessions)})")
    print(f"Windows flagged as first-after-gap: {n_after_gap} (should equal number of split sessions = 3)")
    gap_rows = [r for r in all_rows if r["is_first_window_after_gap"]]
    for r in gap_rows:
        print(f"  {r['activity']}/{r['subject']}: real elapsed_delta at reconnection = {r['elapsed_delta_sec']}s")


if __name__ == "__main__":
    main()
