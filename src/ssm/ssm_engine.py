"""
THE authoritative SSM (Adaptive Session Security Manager) decision engine.

This is the ONLY implementation of Algorithm 1 (decision logic) and
Algorithm 2 (anomaly scoring) in this project. Every consumer -- the real
PhysioNet trace-driven experiment, the always-full baseline, the 25-event
sanity/reproducibility trace, the T_max/A_th sensitivity sweep, and the test
suite -- imports and uses THIS module. There is no second copy of this
decision logic anywhere else in the repository.

See SSM_ALGORITHM_DECISION.md (repo root) for why the constants below are
what they are, in particular:
  - A_TH = 0.5, not the old paper's 1.5 (which was outside S's own [0,1]
    range and could mathematically never fire).
  - The explicit first-session rule (rule 0 below), decided and documented
    before this engine was ever run against real data.
  - failed_resumptions is a real input to this engine's math, but the real
    PhysioNet trace-driven experiment has no data source for it and always
    passes 0 -- disclosed as a limitation, not hidden.
"""
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------- constants
# Frozen per SSM_ALGORITHM_DECISION.md. Do not change these to alter a
# result after the fact; a genuine change requires a new dated decision
# entry in that file explaining the mathematical or evidentiary basis.
T_MAX_SEC = 900
R_MAX = 10
A_TH = 0.5
W1 = 0.7
W2 = 0.3
WINDOW_SEC = 20
Z_NORM_CAP = 3.0  # z-scores >= this many sigma saturate norm(z) at 1.0, per Algorithm 2's own "norm(z)" term


def anomaly_score(z: float, failed_resumptions: int) -> dict:
    """Algorithm 2 -- Anomaly Scoring. Returns a dict with the score and its
    two components, for full traceability in logs (never just the final
    number)."""
    z_norm = min(abs(z) / Z_NORM_CAP, 1.0)
    f = failed_resumptions / R_MAX
    raw = W1 * z_norm + W2 * f
    S = max(0.0, min(1.0, raw))
    return {"S": S, "z_norm": z_norm, "f": f, "raw_before_clamp": raw}


def decide(elapsed_sec: float, resumption_count: int, S: float, has_prior_ticket: bool) -> dict:
    """Algorithm 1 -- SSM Decision Logic, with the explicit first-session
    rule (rule 0) added per SSM_ALGORITHM_DECISION.md Sec. 4."""
    if not has_prior_ticket:
        return {"decision": "FULL_AUTH", "reason": "first-session (no prior ticket)"}
    if elapsed_sec > T_MAX_SEC:
        return {"decision": "FULL_AUTH", "reason": "elapsed>T_max"}
    if resumption_count >= R_MAX:
        return {"decision": "FULL_AUTH", "reason": "resumption_count>=R_max"}
    if S >= A_TH:
        return {"decision": "FULL_AUTH", "reason": "S>=A_th"}
    return {"decision": "RESUME", "reason": "within bounds"}


@dataclass
class SSMState:
    """Mutable state the engine tracks across a session's event stream."""
    elapsed_sec: float = 0.0
    resumption_count: int = 0
    has_prior_ticket: bool = False
    failed_resumptions: int = 0  # real input slot; always 0 for the trace-driven PhysioNet experiment (see module docstring)


@dataclass
class DecisionEvent:
    """One fully-traceable SSM decision, emitted per input event."""
    index: int
    elapsed_sec: float
    resumption_count: int
    z: float
    S: float
    z_norm: float
    f: float
    decision: str
    reason: str


def run_session(elapsed_deltas, z_scores, failed_resumptions=None):
    """Runs the engine over one session's real, ordered event stream.

    elapsed_deltas[i]: real elapsed time (seconds) since the previous event
      in THIS session (elapsed_deltas[0] is ignored -- the first event is
      always the mandatory first-session full auth, per rule 0).
    z_scores[i]: the real, data-derived anomaly z-score feature for event i.
    failed_resumptions[i]: optional per-event failed-resumption count; if
      omitted, 0 for every event (the real PhysioNet trace has no such
      data -- see SSM_ALGORITHM_DECISION.md Sec. 3).

    Returns list[DecisionEvent], one per input event, and never mutates
    module-level state (safe to call once per session, in any order).
    """
    n = len(elapsed_deltas)
    assert len(z_scores) == n, "elapsed_deltas and z_scores must be the same length"
    if failed_resumptions is None:
        failed_resumptions = [0] * n
    assert len(failed_resumptions) == n

    state = SSMState()
    events = []

    for i in range(n):
        if i > 0:
            state.elapsed_sec += elapsed_deltas[i]

        score = anomaly_score(z_scores[i], failed_resumptions[i])
        outcome = decide(state.elapsed_sec, state.resumption_count, score["S"], state.has_prior_ticket)

        events.append(DecisionEvent(
            index=i,
            elapsed_sec=round(state.elapsed_sec, 3),
            resumption_count=state.resumption_count,
            z=z_scores[i],
            S=round(score["S"], 6),
            z_norm=round(score["z_norm"], 6),
            f=round(score["f"], 6),
            decision=outcome["decision"],
            reason=outcome["reason"],
        ))

        if outcome["decision"] == "FULL_AUTH":
            state.elapsed_sec = 0.0
            state.resumption_count = 0
            state.has_prior_ticket = True
        else:
            state.resumption_count += 1

    return events


def run_always_full(n_events):
    """The always-full baseline: every event is a full authentication,
    regardless of elapsed time, resumption count, or anomaly score. Uses
    the same DecisionEvent shape for uniform downstream aggregation."""
    events = []
    for i in range(n_events):
        events.append(DecisionEvent(
            index=i, elapsed_sec=0.0, resumption_count=0, z=0.0, S=0.0, z_norm=0.0, f=0.0,
            decision="FULL_AUTH", reason="always-full-baseline",
        ))
    return events
