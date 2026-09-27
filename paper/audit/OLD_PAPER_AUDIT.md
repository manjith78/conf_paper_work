# OLD PAPER AUDIT

Source paper audited: the verified-correct final version transcribed in full
in the project's `project-handoff-0-to-hero.md` (title: "Adaptive Session
Resumption for Hybrid Post-Quantum Authentication in Wearable Healthcare
IoT"), cross-checked against `discrepancy-report.md` and
`reproducibility-investigation.md`.

This audit does not modify the old paper or old implementation. It exists so
the new rebuild can (a) know exactly which old claims are trustworthy load-
bearing facts to reproduce, and (b) know exactly which old claims must NOT be
carried forward unchanged into the new paper.

## Classification scheme

- **A** — Directly reproducible from raw data by the new pipeline (a protocol
  parameter, a dataset fact, a code-computable quantity).
- **B** — Derivable mathematically from protocol/message-format specification
  (e.g., byte sizes from field widths) — reproducible without running code,
  but still must be re-verified against the new implementation, not assumed.
- **C** — An experimentally measured quantity (a benchmark, a trace-driven
  result) that must be RE-MEASURED by the new pipeline, not copied from the
  old paper.
- **D** — Dependent on an external, cited source (a NIST standard, a related
  work's own reported numbers) — carried forward as citation, not as
  something this project measures itself.
- **E** — A claim whose support is currently unclear / needs the new
  pipeline's own investigation before it can be asserted again.
- **F** — Inconsistent with the implementation that actually produced it, or
  otherwise proven wrong by the discrepancy report / reproducibility
  investigation. Must NOT be carried forward without being fixed or
  re-derived; if fixed, becomes a new A/B/C claim in the new project.

---

## 1. Protocol design claims (Sec. III–VI)

| Claim | Class | Notes |
|---|---|---|
| Three-entity model (WD, GW, HS); Dolev-Yao threat model | A | Design choice, not a measurement; reproducible as specification text. |
| Ed25519 for identity, ML-KEM-512 (FIPS 203) for KEM, HMAC-SHA256 for resumption, AES-128-GCM for transport, HKDF-SHA256 for derivation | A | Concrete algorithm choices; the new implementation must actually use these real libraries (per Phase 5), not merely state them. |
| Full-auth message sequence (Sec. IV-A, 6 messages) and resumption sequence (Sec. IV-B, 3 messages) | A | Reproducible directly from a real running implementation; new `src/protocol/` must match this exactly or the paper must be updated to match the new code — never left silently mismatched (12-goal #7). |
| Binding `ct` into `sigma2` (`sign(N2 \|\| ct)`) fixes a ciphertext-substitution flaw found by ProVerif | A | Confirmed present correctly in old `protocol.py`; carry the requirement forward as a **design invariant** the new implementation must also satisfy, re-verified by the new ProVerif model, not assumed from the old paper's narrative alone. |
| Verification-gates-progress fix (tag check happens strictly before any accept event / state update) | A | Same as above — a design invariant to re-verify in the new model, not a fact to just restate. |
| "All seven ProVerif queries verified true" (Sec. VI) | **F** | True only for the simpler `protocol_model.pv` (7 queries). A separate, more thorough model on the student's machine (`protocol_v2.pv`–`v4.pv`, 9 queries, including explicit `wearableAcceptsGateway ==> gatewayAcceptsWearable`) returns **one query false**. Reproducibility investigation's root-cause diagnosis: this is a backwards-direction correspondence property (asserts gateway-authenticates-first when the protocol's actual message order authenticates wearable-first), not a real exploitable vulnerability — but the paper's blanket "all verified true" statement is not defensible until the new project (a) builds ONE authoritative model with the correct property directions and (b) explicitly states its scope. See Phase 20 (formal verification rebuild). |
| Formal verification scope is single-session only, unbounded case is future work | A | Honestly disclosed already in Sec. VI; carry forward, and keep disclosing it unless the new model actually achieves unbounded verification. |
| Security-analysis narrative (replay, MITM, impersonation, confidentiality/integrity, Sec. V-E on K_r lifetime) | A/B | Qualitative protocol-logic argument, not a measured number; reproducible as long as the new implementation preserves the same message structure and key-derivation. Must be re-reviewed against whatever the new SSM redesign (Phase 4) changes about elapsed/reset semantics, since Sec. V-E's own argument ("T_max...bounds how long a compromised K_r could be used") is the textual basis for Finding #2 below. |

## 2. SSM algorithm design claims (Sec. IV-C, IV-D)

| Claim | Class | Notes |
|---|---|---|
| Algorithm 1 pseudocode (elapsed/R_max/S checks, in that priority order) | A | Reproducible as specification. First-connection ("no ticket yet") case is undefined in the printed pseudocode — reproducibility investigation confirms this gap; the new project must state and implement an explicit first-session rule rather than relying on an undocumented script-specific hack (Finding #3 in the discrepancy report). |
| Algorithm 2 pseudocode (`S = clamp(w1*norm(z) + w2*f, 0, 1)`) | A | Reproducible as specification. |
| "The anomaly-score branch of Algorithm 1 can never fire on its own" (Sec. VII-C), because `S` is capped at 1.0 but `A_th = 1.5` | A (true of Algorithm 2 as specified) / **F** (false of what actually generated Table III) | This is the discrepancy report's Finding #1, the single most severe finding in the whole audit. The statement is mathematically correct for Algorithm 2 exactly as written. It is **false** as a description of `scenario_simulation.py`, which compares the RAW z-score directly against `A_th`, bypassing Algorithm 2's formula entirely — and that raw-z branch drives 56–85% of all full-authentication events across the three activities. The new rebuild's SSM engine (Phase 4/5, `src/ssm/ssm_engine.py`) must implement ONE mathematically consistent thresholding mechanism and the paper must describe exactly that mechanism — not a mechanism that differs from the code that generates the numbers. |
| Default constants T_max=900s, R_max=10, A_th=1.5, w1=0.7, w2=0.3, 20s check cadence | A | Configuration values; reproducible as-is, but the new project must independently judge (not merely inherit) whether `A_th=1.5` remains defensible once `S` and `A_th` operate on a mathematically consistent scale — this is exactly the "S∈[0,1] vs A_th=1.5 inconsistency" the user has already flagged as needing a scientifically defensible redesign, not a copy-forward. |
| Algorithm 2's weights/threshold are "configuration parameters rather than values fit to labeled attack data" (Sec. IV-D, VIII) | A | Honest disclosure already present; carry forward. |

## 3. Cryptographic benchmark claims (Table II, Sec. VII-A)

| Claim | Class | Notes |
|---|---|---|
| All Table II latency figures (Ed25519 sign/verify, ML-KEM-512 encaps/decaps/keygen, HMAC, AES-GCM, HKDF, ECDSA/ECDH baseline, full handshake, resumption) | **C** | Every one of these is a real hardware/software-dependent measurement. They MUST be re-measured by the new project's own `experiments/experiment_05_crypto` on whatever machine actually runs the new pipeline — never copied from the old paper's numbers, which are specific to the old measurement environment (2026, "commodity x86-64 CPU, Intel Xeon, 2.8GHz, 2 vCPU"). Expect the new numbers to differ; that is correct behavior, not an error. |
| ML-KEM-512 measured via unoptimized pure-Python reference implementation, disclosed as inflating its absolute cost vs. optimized embedded C/assembly | A | Honest methodological disclosure; carry forward as a disclosed limitation as long as the new implementation also uses a comparable (non-embedded-optimized) library — re-state explicitly whatever library the new project actually uses. |
| 928 bytes (full handshake) / 96 bytes (resumption) on the wire | B | Derivable directly from the real serialized message sizes of whatever implementation exists — the new project must compute these from its OWN actual serialization (Phase 6, bandwidth derivation), not assume the old byte counts carry over, since library/format choices can change exact sizes. |
| "On this desktop platform, classical ECDSA/ECDH measures cheaper... because ML-KEM-512 runs through an unoptimized pure-Python implementation... the reverse of optimized embedded PQC studies" | A | Honest, self-aware disclosure; the underlying comparison must be re-measured (class C) but the disclosure PATTERN (don't claim PQC is intrinsically cheaper/costlier from a software-only, non-embedded-optimized measurement) should be preserved in the new paper regardless of which way the new numbers fall. |

## 4. Dataset and trace-driven evaluation claims (Sec. VII-A/B/C, Table III, Fig. 3/4)

| Claim | Class | Notes |
|---|---|---|
| PhysioNet "Wearable Device Dataset..." v1.0.0, Empatica E4, DOI 10.13026/zzf8-xv61 | A/D | Correct citation (D); the new project has independently re-downloaded and checksum-verified this exact dataset (Phase 2, already complete — see `dataset_manifest.json`). |
| "41 real subject-sessions" across STRESS(n=37)/AEROBIC(n=31)/ANAEROBIC(n=32) | **E → now A**, partially **F** | The new inventory (this audit's own `experiments/experiment_01_dataset_validation` output) finds **36 real distinct subjects**, not 41 — the old counts (37/31/32) appear to come from counting Bluetooth-disconnection split files (`_a`/`_b`) as separate "sessions"/"subjects" (confirmed: old `feature_table.csv` lists `S11_a`/`S11_b` as distinct subject values), which double-counts real humans. This is not merely an old-vs-new discrepancy to shrug off — it directly affects Table III's per-session-mean statistic. The new project's `DECISIONS_REQUIRED.md` Decision 1 addresses this: the recommended fix treats each split pair as ONE continuous session with the real measured gap inserted (91.3s f14, 219.1s S11, 51.4s S16), yielding correct, non-duplicated subject counts. |
| Three documented real Bluetooth disconnection incidents with measured gaps 91.3s/219.1s/51.4s | A | Independently re-confirmed by the new project's own inventory script from the raw files' own UTC header timestamps — matches the old paper's numbers exactly. Genuinely reproducible, keep. |
| "Anomaly signal elevated before disconnections: mean 1.40 vs 0.89, median 0.38 vs 0.62, inconclusive at n=3" (Sec. VII-A) | **C** | Must be re-derived by the new feature-extraction pipeline once the SSM anomaly score and feature windows are rebuilt (Phase 3/4/7) — the exact numbers depend on the new pipeline's own feature computation and are not guaranteed to match the old figures, especially given Decision 1's change to how split sessions are modeled. |
| Table III (74.5–85.0% compute reduction, 67–76% bandwidth reduction; full/resume event counts per activity) | **F** | Confirmed by the reproducibility investigation to be generated by `scenario_simulation.py`'s raw-z-vs-A_th branch (Finding #1), NOT by Algorithm 2 as specified in the same paper's Sec. IV-D. When Algorithm 2 is applied correctly, the reproducibility investigation's Experiment B found **~90.1–91.3% compute / ~81.0–82.1% bandwidth reduction** instead — a materially different, better-looking result, but arrived at via a DIFFERENT algorithm than the one the paper claims to be evaluating. Per the user's "most important scientific rule," the new project must use whichever thresholding mechanism it independently, defensibly designs (Phase 4) and report whatever number that mechanism actually produces on the new pipeline — it must not target either the old 74.5–85.0% range or the investigation's ~91%/~82% range as a goal. |
| "R_max, not T_max, is the binding constraint at these settings" (Sec. VII-C, Fig. 4 sensitivity) | **E** | Plausible and mechanistically sound (R_max=10 at 20s cadence bounds any resumption chain to 200s regardless of T_max once T_max>200s), but was derived from the same raw-z pipeline as Table III (Finding #1) — must be re-derived from the new, corrected SSM engine before being restated as a finding. |
| 24-hour-equivalent extrapolation from ~25-40 minute real sessions, "disclosed linear extrapolation... not a genuine day-long recording" (Sec. VIII) | A | Honest methodological disclosure; the extrapolation ITSELF (class B/C, must be recomputed) but the disclosure obligation carries forward unconditionally — the new paper must make the same disclosure about its own extrapolation, whatever the new numbers are. |
| 25-event S01/AEROBIC trace reproducing "3 full auths / 22 resumes / 4896 bytes" | **F** (as a "real-world evaluation" claim) / A (as a labeled sanity trace) | Reproducibility investigation confirms this specific result depends on `ssm_live_simulation.py`'s undocumented first-event-forced-FULL_AUTH override layered on the (correct) Algorithm-2-compliant formula — not from Algorithm 1/2 exactly as printed, and not from the code that produced Table III either. Per the user's Phase-14 instruction, the new project must keep this exact 25-event trace but explicitly relabel it a "sanity/reproducibility trace," never "real-world evaluation," and must implement the first-session rule as an explicit, documented part of Algorithm 1 (Phase 4) rather than a silent script-only hack. |

## 5. Related-work and literature claims (Sec. II, Table I, References)

| Claim | Class | Notes |
|---|---|---|
| All 18 references, including previously-broken [15] now resolved | D | External citations; verify each is still accurate/live at final submission time (venue-dependent, out of scope for this technical rebuild), but not something this project measures. |
| Table I comparison grid (Hybrid IoT / Med-Sec-IoT / Proposed feature checkmarks) | D | Qualitative comparison against cited related work's own reported features; carry forward as long as the cited papers' claims haven't been independently re-verified to be wrong (out of scope here). |
| "To the best of our knowledge, this adaptive-resumption gap is not addressed elsewhere in the surveyed literature" | E | A literature-completeness claim that can only be as strong as the survey itself; not re-verified by this technical audit (would require a fresh literature search, out of scope for Phases 0-2). Flagged for the paper-rewrite phase to either re-confirm via a fresh search or soften appropriately. |

## 6. Claims about "post-quantum security" — explicit scrutiny per user's rebuild instructions

| Claim | Class | Notes |
|---|---|---|
| Paper title says "Hybrid Post-Quantum Authentication" (not "the protocol is fully post-quantum secure") | A | The title and abstract are careful: ML-KEM-512 supplies "the quantum-resistant guarantee for session-key establishment," while Ed25519 is explicitly described as classical, used "only for lightweight device identity verification." This framing is technically defensible and must be preserved. |
| Any future/rebuilt paper text must NOT claim the WHOLE protocol is post-quantum secure | **E, flagged preventively** | Not currently a violation in the audited text, but explicitly called out by the user as a trap to avoid in the rebuild (Ed25519 remains classical and a quantum adversary who can break Ed25519 can still impersonate a device's identity even if ML-KEM-512 itself is quantum-resistant). The final paper-quality audit (Phase 27) must specifically re-check this. |

## 7. Limitations section (Sec. VIII) — already largely honest, carry forward the pattern

| Claim | Class | Notes |
|---|---|---|
| Software-only, non-embedded, non-energy-measuring, single-session-formal-verification, small-sample (n=3) anomaly-signal-check, configuration-not-fit-to-attack-data disclosures | A | This section is the strongest part of the old paper from a scientific-honesty standpoint and should be used as the STYLE template for the new paper's limitations section (Phase 27) — updated with whatever new limitations the new pipeline actually has (e.g., the split-session handling decision, the truncation of S02, any new dataset-completeness caveats), not merely copied verbatim, since the new pipeline is a different implementation with potentially different limitations. |
| "No energy claim anywhere... must be clearly and prominently labeled as an estimate/illustration" | A | Hard constraint, explicitly reinforced by the user's own project rules; carry forward unconditionally into the new project. |

---

## Summary: what the new rebuild inherits unchanged vs. what it must independently re-derive

**Inherit as specification/design (class A/B, reproducible without new measurement):**
protocol entity model, threat model, message sequences, the two ProVerif-driven design invariants (ct-bound signature, verification-gates-progress), Algorithm 1/2 pseudocode *structure*, the honest-disclosure PATTERN from Sec. VIII, dataset citation, the three real disconnection-gap measurements (91.3/219.1/51.4s, independently re-confirmed), the "Ed25519 is classical" framing discipline.

**Must be re-measured/re-derived from scratch by the new pipeline (class C), and may legitimately come out different from the old paper:**
every Table II benchmark number, every Table III/Fig.3/Fig.4 number, the byte-size constants (if the new implementation's serialization differs at all), the anomaly-signal-vs-disconnection empirical check, the R_max-vs-T_max sensitivity conclusion, the 24h-extrapolation figures.

**Must NOT be carried forward as-is because they are proven inconsistent with their own supporting code (class F) — must be fixed at the design level first, then re-derived:**
the "anomaly branch can never fire" claim as a description of what generated Table III; Table III/Fig.3/Fig.4 themselves; the "all seven ProVerif queries true" blanket claim; the 41-subject-session count (should be 36 real subjects, with split sessions handled per Decision 1); the "3/22/4896" 25-event result if presented as anything other than an explicitly labeled sanity trace with a documented first-session rule.

**Needs fresh investigation before being asserted again (class E):**
the literature-completeness claim in Sec. II/IX; the R_max-binding-constraint sensitivity conclusion (mechanistically plausible but derived from the flawed pipeline); any post-quantum-security framing in the new paper text (preventive re-check only, not currently violated).
