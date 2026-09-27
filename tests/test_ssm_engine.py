"""
Boundary-condition test suite for the ONE authoritative SSM engine
(src/ssm/ssm_engine.py). These tests must pass before the engine is
trusted with the real experiment, and must keep passing afterward -- a
failing test here means the engine, not the experiment, is wrong.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "ssm"))
import ssm_engine as E  # noqa: E402


def test_first_session_forces_full_auth_regardless_of_inputs():
    # Even with elapsed=0, resumption_count=0, S=0 -- no prior ticket must force FULL_AUTH.
    out = E.decide(elapsed_sec=0, resumption_count=0, S=0.0, has_prior_ticket=False)
    assert out["decision"] == "FULL_AUTH"
    assert out["reason"] == "first-session (no prior ticket)"


def test_elapsed_exactly_at_t_max_does_not_trigger():
    # Algorithm 1 uses a strict '>' : elapsed == T_max must NOT force full auth.
    out = E.decide(elapsed_sec=E.T_MAX_SEC, resumption_count=0, S=0.0, has_prior_ticket=True)
    assert out["decision"] == "RESUME", "elapsed == T_max must not trigger (strict > only)"


def test_elapsed_just_over_t_max_triggers():
    out = E.decide(elapsed_sec=E.T_MAX_SEC + 0.001, resumption_count=0, S=0.0, has_prior_ticket=True)
    assert out["decision"] == "FULL_AUTH"
    assert out["reason"] == "elapsed>T_max"


def test_resumption_count_exactly_at_r_max_triggers():
    # Algorithm 1 uses '>=' for R_max: count == R_max MUST trigger.
    out = E.decide(elapsed_sec=0, resumption_count=E.R_MAX, S=0.0, has_prior_ticket=True)
    assert out["decision"] == "FULL_AUTH"
    assert out["reason"] == "resumption_count>=R_max"


def test_resumption_count_just_below_r_max_does_not_trigger():
    out = E.decide(elapsed_sec=0, resumption_count=E.R_MAX - 1, S=0.0, has_prior_ticket=True)
    assert out["decision"] == "RESUME"


def test_anomaly_score_exactly_at_a_th_triggers():
    out = E.decide(elapsed_sec=0, resumption_count=0, S=E.A_TH, has_prior_ticket=True)
    assert out["decision"] == "FULL_AUTH"
    assert out["reason"] == "S>=A_th"


def test_anomaly_score_just_below_a_th_does_not_trigger():
    out = E.decide(elapsed_sec=0, resumption_count=0, S=E.A_TH - 1e-9, has_prior_ticket=True)
    assert out["decision"] == "RESUME"


def test_anomaly_score_is_mathematically_reachable():
    # The whole point of the A_th fix: S must be able to reach A_TH for
    # some real, non-extreme z. With z_norm capped at 1.0 and f in [0,1],
    # max possible S is W1+W2 == 1.0, and A_TH=0.5 sits well inside [0,1].
    max_possible_S = E.W1 * 1.0 + E.W2 * 1.0
    assert max_possible_S >= E.A_TH, "A_th must be reachable given S's own formula -- this is the bug being fixed"
    # a z of exactly Z_NORM_CAP * (A_TH / W1) should produce S == A_TH with f=0
    z_needed = E.Z_NORM_CAP * (E.A_TH / E.W1)
    score = E.anomaly_score(z=z_needed, failed_resumptions=0)
    assert abs(score["S"] - E.A_TH) < 1e-9


def test_anomaly_score_clamped_at_one_for_extreme_z():
    score = E.anomaly_score(z=1000.0, failed_resumptions=0)
    assert score["S"] <= 1.0
    assert score["z_norm"] == 1.0


def test_anomaly_score_never_negative():
    score = E.anomaly_score(z=-5.0, failed_resumptions=0)  # abs() must be applied
    assert score["S"] >= 0.0
    assert score["z_norm"] >= 0.0


def test_full_auth_resets_elapsed_and_resumption_count():
    # elapsed just over T_max on event 2 should force FULL_AUTH and reset
    # both elapsed and resumption_count for event 3.
    elapsed_deltas = [0, E.T_MAX_SEC + 1, 5]
    z_scores = [0.0, 0.0, 0.0]
    events = E.run_session(elapsed_deltas, z_scores)
    assert events[0].decision == "FULL_AUTH" and events[0].reason == "first-session (no prior ticket)"
    assert events[1].decision == "FULL_AUTH" and events[1].reason == "elapsed>T_max"
    assert events[2].elapsed_sec == 5.0, "elapsed must reset to 0 then accumulate only the new delta"
    assert events[2].resumption_count == 0


def test_resumption_count_increments_on_resume_only():
    # 3 consecutive low-z, low-elapsed events after the mandatory first auth
    # should show resumption_count incrementing 0,1,2 on events 2,3,4.
    elapsed_deltas = [0, 20, 20, 20]
    z_scores = [0.0, 0.0, 0.0, 0.0]
    events = E.run_session(elapsed_deltas, z_scores)
    assert events[0].decision == "FULL_AUTH"
    assert [e.resumption_count for e in events[1:]] == [0, 1, 2]
    assert all(e.decision == "RESUME" for e in events[1:])


def test_r_max_forces_full_auth_after_ten_resumptions():
    # 1 first-auth + 10 low-anomaly resumptions -> the 11th event (index 10)
    # must be forced FULL_AUTH via R_max (resumption_count reaches R_MAX=10
    # on the event immediately after 10 RESUMEs).
    n = 12
    elapsed_deltas = [0] + [20] * (n - 1)
    z_scores = [0.0] * n
    events = E.run_session(elapsed_deltas, z_scores)
    decisions = [e.decision for e in events]
    assert decisions[0] == "FULL_AUTH"
    assert decisions[1:11] == ["RESUME"] * 10
    assert decisions[11] == "FULL_AUTH"
    assert events[11].reason == "resumption_count>=R_max"


def test_split_session_reconnection_is_not_a_forced_first_auth():
    # Simulates a Decision-1-style split session: first event is the
    # mandatory first auth, then several ordinary resumes, then a
    # reconnection with a real, non-trivial elapsed delta (like the real
    # 115.0s / 258.0s / 80.0s reconnection deltas measured from the raw
    # dataset) that is still comfortably under T_max -- this must be
    # decided by ordinary Algorithm 1 rules, not treated as a new first
    # session.
    elapsed_deltas = [0, 20, 20, 115.0]  # last delta mimics the real f14 reconnection gap
    z_scores = [0.0, 0.0, 0.0, 0.0]
    events = E.run_session(elapsed_deltas, z_scores)
    assert events[0].decision == "FULL_AUTH" and events[0].reason == "first-session (no prior ticket)"
    assert events[3].reason != "first-session (no prior ticket)", (
        "a reconnection after a real gap must never be treated as a fresh first-session event"
    )
    assert events[3].elapsed_sec == 20 + 20 + 115.0
    assert events[3].decision == "RESUME", "115s is well under T_max=900s and resumption_count=2 < R_max=10"


def test_always_full_baseline_is_always_full_auth():
    events = E.run_always_full(50)
    assert len(events) == 50
    assert all(e.decision == "FULL_AUTH" for e in events)


def test_failed_resumptions_feed_into_score_when_present():
    # f term should be able to push S over A_th even with z=0, since the
    # engine's f-term is a real, usable input (even though the real
    # PhysioNet experiment always passes 0 for it -- this tests the ENGINE,
    # not that experiment's data availability).
    score_no_failures = E.anomaly_score(z=0.0, failed_resumptions=0)
    score_all_failures = E.anomaly_score(z=0.0, failed_resumptions=E.R_MAX)
    assert score_no_failures["S"] == 0.0
    assert score_all_failures["S"] == E.W2  # f=1.0, z_norm=0 -> S = W2*1.0
    assert score_all_failures["S"] > score_no_failures["S"]


if __name__ == "__main__":
    import inspect
    fails = 0
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_") and inspect.isfunction(obj)]
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            fails += 1
            print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(tests) - fails}/{len(tests)} passed")
    if fails:
        raise SystemExit(1)
