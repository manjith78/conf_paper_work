"""
Generates every table and figure the paper uses, reading ONLY from files in
results/ (never hand-typed numbers). Run this after experiments 03/05/07
have produced their JSON/CSV outputs.

Outputs:
  paper/tables/table_ii_crypto_benchmark.csv   (real measured op latencies)
  paper/tables/table_iii_ssm_results.csv       (real trace-driven SSM results)
  paper/figures/fig3_compute_cost.png
  paper/figures/fig4_sensitivity_tmax.png
  paper/figures/fig5_sensitivity_ath.png
"""
import os
import json
import csv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
RESULTS_JSON = os.path.join(REPO_ROOT, "results", "json")
TABLES_DIR = os.path.join(REPO_ROOT, "paper", "tables")
FIGURES_DIR = os.path.join(REPO_ROOT, "paper", "figures")
os.makedirs(TABLES_DIR, exist_ok=True)
os.makedirs(FIGURES_DIR, exist_ok=True)


def generate_table_ii():
    with open(os.path.join(RESULTS_JSON, "crypto_benchmark.json")) as f:
        b = json.load(f)
    rows = [
        ("Ed25519 Sign", f"{b['ed25519']['sign']['mean_ms']:.4f} ± {b['ed25519']['sign']['std_ms']:.4f}", b['ed25519']['sign']['n']),
        ("Ed25519 Verify", f"{b['ed25519']['verify']['mean_ms']:.4f} ± {b['ed25519']['verify']['std_ms']:.4f}", b['ed25519']['verify']['n']),
        ("ML-KEM-512 Encaps", f"{b['ml_kem_512']['encaps']['mean_ms']:.4f} ± {b['ml_kem_512']['encaps']['std_ms']:.4f}", b['ml_kem_512']['encaps']['n']),
        ("ML-KEM-512 Decaps", f"{b['ml_kem_512']['decaps']['mean_ms']:.4f} ± {b['ml_kem_512']['decaps']['std_ms']:.4f}", b['ml_kem_512']['decaps']['n']),
        ("ML-KEM-512 KeyGen", f"{b['ml_kem_512']['keygen']['mean_ms']:.4f} ± {b['ml_kem_512']['keygen']['std_ms']:.4f}", b['ml_kem_512']['keygen']['n']),
        ("HMAC-SHA256 verify pair", f"{b['hmac']['hmac_verify_pair']['mean_ms']:.4f} ± {b['hmac']['hmac_verify_pair']['std_ms']:.4f}", b['hmac']['hmac_verify_pair']['n']),
        ("AES-128-GCM Encrypt (64B)", f"{b['aes_gcm']['encrypt_64B']['mean_ms']:.4f} ± {b['aes_gcm']['encrypt_64B']['std_ms']:.4f}", b['aes_gcm']['encrypt_64B']['n']),
        ("AES-128-GCM Decrypt (64B)", f"{b['aes_gcm']['decrypt_64B']['mean_ms']:.4f} ± {b['aes_gcm']['decrypt_64B']['std_ms']:.4f}", b['aes_gcm']['decrypt_64B']['n']),
        ("HKDF-SHA256 derive", f"{b['hkdf']['derive']['mean_ms']:.4f} ± {b['hkdf']['derive']['std_ms']:.4f}", b['hkdf']['derive']['n']),
        ("ECDSA-P256 Sign (classical)", f"{b['classical_ecdsa_ecdh']['ecdsa_sign']['mean_ms']:.4f} ± {b['classical_ecdsa_ecdh']['ecdsa_sign']['std_ms']:.4f}", b['classical_ecdsa_ecdh']['ecdsa_sign']['n']),
        ("ECDSA-P256 Verify (classical)", f"{b['classical_ecdsa_ecdh']['ecdsa_verify']['mean_ms']:.4f} ± {b['classical_ecdsa_ecdh']['ecdsa_verify']['std_ms']:.4f}", b['classical_ecdsa_ecdh']['ecdsa_verify']['n']),
        ("ECDH-P256 exchange (classical)", f"{b['classical_ecdsa_ecdh']['ecdh_exchange']['mean_ms']:.4f} ± {b['classical_ecdsa_ecdh']['ecdh_exchange']['std_ms']:.4f}", b['classical_ecdsa_ecdh']['ecdh_exchange']['n']),
        ("Full handshake (end-to-end)", f"{b['end_to_end']['full_handshake']['mean_ms']:.4f} ± {b['end_to_end']['full_handshake']['std_ms']:.4f}", b['end_to_end']['full_handshake']['n']),
        ("Resumption (end-to-end)", f"{b['end_to_end']['resumption']['mean_ms']:.4f} ± {b['end_to_end']['resumption']['std_ms']:.4f}", b['end_to_end']['resumption']['n']),
    ]
    path = os.path.join(TABLES_DIR, "table_ii_crypto_benchmark.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Operation", "Latency mean ± SD (ms)", "n"])
        w.writerows(rows)
    print(f"Wrote {path}")
    print(f"  CPU: {b['cpu'].get('model_name', b['cpu'].get('processor'))}")
    print(f"  Full handshake bytes: {b['message_sizes']['full_handshake_bytes']}, "
          f"Resumption bytes: {b['message_sizes']['resumption_bytes']}")
    return b


def generate_table_iii():
    with open(os.path.join(RESULTS_JSON, "ssm_activity_summary.json")) as f:
        s = json.load(f)
    rows = []
    for act in ["STRESS", "AEROBIC", "ANAEROBIC"]:
        a = s["per_activity"][act]
        rows.append((
            act, a["n_real_sessions"],
            a["extrapolated_full_events_per_24h"], a["extrapolated_resume_events_per_24h"],
            a["proposed_compute_ms_per_24h"], a["always_full_baseline_compute_ms_per_24h"],
            a["compute_time_reduction_pct"], a["bandwidth_reduction_pct"],
        ))
    path = os.path.join(TABLES_DIR, "table_iii_ssm_results.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Activity", "n_sessions", "Full/24h", "Resume/24h",
                     "Proposed(ms/24h)", "AlwaysFull(ms/24h)", "ComputeReduction%", "BandwidthReduction%"])
        w.writerows(rows)
    print(f"Wrote {path}")
    return s


def generate_fig3(bench, activity_summary):
    acts = ["STRESS", "AEROBIC", "ANAEROBIC"]
    labels = ["STRESS\n(sedentary)", "AEROBIC\n(steady motion)", "ANAEROBIC\n(interval bursts)"]
    always_full = [activity_summary["per_activity"][a]["always_full_baseline_compute_ms_per_24h"] for a in acts]
    proposed = [activity_summary["per_activity"][a]["proposed_compute_ms_per_24h"] for a in acts]
    proposed_err = [activity_summary["per_activity"][a]["proposed_compute_ms_per_24h_std_across_sessions"] for a in acts]

    cc = bench["classical_ecdsa_ecdh"]
    classical_per_op_ms = 2 * cc["ecdsa_sign"]["mean_ms"] + 2 * cc["ecdsa_verify"]["mean_ms"] + 2 * cc["ecdh_exchange"]["mean_ms"]
    classical = []
    for a in acts:
        full24 = activity_summary["per_activity"][a]["extrapolated_full_events_per_24h"]
        resume24 = activity_summary["per_activity"][a]["extrapolated_resume_events_per_24h"]
        classical.append((full24 + resume24) * classical_per_op_ms)

    x = np.arange(len(acts))
    w = 0.25
    fig, ax = plt.subplots(figsize=(9.8, 3.8))
    ax.bar(x - w, classical, width=w, label="Classical (ECDSA/ECDH)", color="#d97706")
    ax.bar(x, always_full, width=w, label="Always-Full Hybrid", color="#2563eb")
    ax.bar(x + w, proposed, width=w, yerr=proposed_err, capsize=4, label="Proposed SSM (fixed A_th)", color="#16a34a")
    ax.set_yscale("log")
    ax.set_ylabel("Compute time / 24h-eq.\n(ms, log, real measured)", fontsize=9.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9.5)
    ax.set_title("Real, trace-driven authentication compute cost\n"
                 "(97 real sessions, PhysioNet E4 dataset, corrected Algorithm 2)", fontsize=10)
    ax.legend(loc="upper center", ncol=3, frameon=False, fontsize=8.5)
    ax.grid(axis="y", which="both", alpha=0.3)
    fig.tight_layout()
    path = os.path.join(FIGURES_DIR, "fig3_compute_cost.png")
    fig.savefig(path, dpi=300)
    print(f"Wrote {path}")


def generate_sensitivity_figs():
    with open(os.path.join(RESULTS_JSON, "sensitivity_analysis.json")) as f:
        s = json.load(f)

    tvals = [p["T_max_min"] for p in s["t_max_sweep_minutes"]]
    svals = [p["savings_pct_vs_always_full"] for p in s["t_max_sweep_minutes"]]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot(tvals, svals, "o-", color="#16a34a", linewidth=2, markersize=7)
    ax.axvline(15, color="gray", linestyle="--", label="Frozen default (T_max = 15 min)")
    ax.set_xlabel("T_max (minutes)")
    ax.set_ylabel("Compute-time savings vs. Always-Full Hybrid (%)")
    ax.set_title("Real T_max sensitivity (AEROBIC regime, R_max=10, A_th=0.5)\nre-run on real accelerometer-derived event traces")
    ax.legend(loc="lower right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    path = os.path.join(FIGURES_DIR, "fig4_sensitivity_tmax.png")
    fig.savefig(path, dpi=280)
    print(f"Wrote {path}")

    avals = [p["A_th"] for p in s["a_th_sweep"]]
    svals2 = [p["savings_pct_vs_always_full"] for p in s["a_th_sweep"]]
    fig2, ax2 = plt.subplots(figsize=(7, 4.2))
    ax2.plot(avals, svals2, "o-", color="#7c3aed", linewidth=2, markersize=7)
    ax2.axvline(0.5, color="gray", linestyle="--", label="Frozen default (A_th = 0.5)")
    ax2.set_xlabel("A_th")
    ax2.set_ylabel("Compute-time savings vs. Always-Full Hybrid (%)")
    ax2.set_title("Real A_th sensitivity (AEROBIC regime, T_max=900s, R_max=10)\nre-run on real accelerometer-derived event traces")
    ax2.legend(loc="lower right")
    ax2.grid(alpha=0.3)
    fig2.tight_layout()
    path2 = os.path.join(FIGURES_DIR, "fig5_sensitivity_ath.png")
    fig2.savefig(path2, dpi=280)
    print(f"Wrote {path2}")


def main():
    bench = generate_table_ii()
    activity_summary = generate_table_iii()
    generate_fig3(bench, activity_summary)
    generate_sensitivity_figs()


if __name__ == "__main__":
    main()
