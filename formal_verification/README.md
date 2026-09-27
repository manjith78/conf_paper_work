# Formal verification — ProVerif

`protocol_model.pv` is the ONE authoritative model for this rebuild (single-
session scope, no replication). Run it with:

```
proverif -in pitype protocol_model.pv
```

## Result (this run, recorded in `protocol_model_output.txt`)

All 8 queries verified **true**:

- Secrecy: `skW`, `skG`, `ticketKey`, `healthcareData` — all true.
- `inj-event(wearableAcceptsGateway) ==> inj-event(gatewayInitiatesFull)` — true (WD authenticates GW).
- `inj-event(gatewayAcceptsWearable) ==> inj-event(wearableAcceptsGateway)` — true (GW authenticates WD, full-auth path).
- `inj-event(gatewayAcceptsResume) ==> inj-event(wearableStartsResume)` — true (GW authenticates WD, resumption path).
- `inj-event(wearableReceivesHealthcareData) ==> inj-event(gatewaySendsHealthcareData)` — true.

**This corrects the old project's false query.** The old, more thorough
model (`protocol_v2.pv`–`v4.pv`, audited in `paper/audit/OLD_PAPER_AUDIT.md`
Sec. 1) asserted `wearableAcceptsGateway ==> gatewayAcceptsWearable` and
found it false. Root cause: in the real message order, `gatewayAcceptsWearable`
(which depends on the gateway verifying WD's finish-MAC) can only happen
*after* `wearableAcceptsGateway` already fired — the old query asked the
implication backwards. This model states the correct direction
(`gatewayAcceptsWearable ==> wearableAcceptsGateway`) and it verifies true.
This was a specification bug in the old model, not a protocol vulnerability.

## Unbounded (replicated) attempt — honestly incomplete, not swept under the rug

`unbounded_attempt.pv` is `protocol_model.pv` with every role replicated
(`!WearableFull`, etc.), attempting the unbounded-session case the old
paper disclosed as future work. Unlike the old paper's claim that this
never terminates, **it terminated in under 90 seconds in this environment**
(`unbounded_attempt_output.txt`), and found ONE query false:

```
inj-event(gatewayAcceptsResume(sid_1)) ==> inj-event(wearableStartsResume(sid_1)) is false.
```

**Diagnosis (best current assessment, not fully confirmed):** the trace
shows the SAME resumption message (identical ticket, nonce, and MAC proof)
being accepted by the gateway role in TWO DIFFERENT replicated instances.
The real implementation (`src/protocol/protocol.py`) prevents this by
storing a single, shared, monotonically-incrementing `count` per device in
`Gateway.tickets[device_id]` — a replayed resumption message would be
checked against the *already-advanced* counter and rejected. This model
does not encode that shared mutable counter: ProVerif's replicated (`!`)
processes each get independent fresh values and do not automatically share
mutable server-side state across replicas without an explicit construct
(e.g. a `table`). The most likely explanation is therefore that **this
model under-approximates the real implementation's replay protection** —
the same class of finding as the old project's false query (a modeling
gap), not a newly discovered protocol flaw. This has NOT been confirmed by
re-modeling the counter explicitly (e.g. with ProVerif `table`s), which is
out of scope for the time available in this rebuild.

**This is reported as an open, honestly-incomplete item, not resolved and
not hidden.** See `FINAL_REPRODUCIBILITY_REPORT.md` and the paper's
Limitations section. Do not cite the unbounded case as verified in either
direction until a model with explicit counter state has been built and
checked.

## Files

- `protocol_model.pv` — the authoritative single-session model (all 8 queries true).
- `protocol_model_output.txt` — its full raw ProVerif output.
- `unbounded_attempt.pv` — the replicated variant (1 of 8 queries false; see diagnosis above).
- `unbounded_attempt_output.txt` — its full raw ProVerif output.
