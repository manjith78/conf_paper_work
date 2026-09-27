#!/usr/bin/env python3
"""
run_all.py -- reproduces the ENTIRE pipeline from a clean checkout, in the
exact dependency order DATA -> PREPROCESSING -> SSM -> CRYPTO -> EXPERIMENT
-> RESULTS -> TABLES/FIGURES -> TESTS.

Usage:
    python run_all.py                 # full run (downloads dataset if missing)
    python run_all.py --skip-download # assumes data/raw/ is already populated
    python run_all.py --tests-only    # just run the two test suites

Every step below shells out to one existing script under src/ or
experiments/ -- this file does not contain any pipeline logic of its own,
only orchestration, so there is exactly one place each stage's logic lives
(the single-source-of-truth rule applies to orchestration too).
"""
import argparse
import subprocess
import sys
import os

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


def run(step_name, cmd, cwd=None):
    print(f"\n{'=' * 70}\n[run_all] {step_name}\n{'=' * 70}")
    result = subprocess.run(cmd, cwd=cwd or REPO_ROOT, shell=False)
    if result.returncode != 0:
        print(f"\n[run_all] STOPPING: '{step_name}' failed (exit code {result.returncode}).")
        sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(description="Run the full SSM rebuild pipeline end to end.")
    parser.add_argument("--skip-download", action="store_true",
                         help="Skip the dataset download/verify step (use existing data/raw/).")
    parser.add_argument("--tests-only", action="store_true",
                         help="Only run the two test suites (fast sanity check).")
    args = parser.parse_args()

    py = sys.executable

    if args.tests_only:
        run("Unit tests: SSM engine (16 boundary tests)",
            [py, os.path.join("tests", "test_ssm_engine.py")])
        run("Unit tests: protocol (7 tests)",
            [py, os.path.join("tests", "test_protocol.py")])
        print("\n[run_all] Tests-only run complete.")
        return

    if not args.skip_download:
        run("1. Download + verify raw dataset (data/raw/)",
            [py, os.path.join("src", "preprocessing", "download_dataset.py")])
    else:
        print("\n[run_all] --skip-download passed: assuming data/raw/ is already populated and verified.")

    run("2. Build sessions (Decisions 1 & 2 applied) + sanity summary",
        [py, os.path.join("src", "preprocessing", "session_builder.py")])

    run("3. Feature extraction -> data/processed/feature_table.csv",
        [py, os.path.join("src", "preprocessing", "feature_extraction.py")])

    run("4. SSM engine unit tests (16 boundary tests, must pass before trusting results)",
        [py, os.path.join("tests", "test_ssm_engine.py")])

    run("5. Cryptographic protocol unit tests (7 tests)",
        [py, os.path.join("tests", "test_protocol.py")])

    run("6. Real crypto benchmark -> results/json/crypto_benchmark.json",
        [py, os.path.join("src", "crypto", "benchmark.py")])

    run("7. Real-dataset SSM experiment -> results/csv, results/json (Table III source)",
        [py, os.path.join("experiments", "experiment_03_ssm", "run_ssm_experiment.py")])

    run("8. 25-event sanity trace (reproducibility check, not a headline claim)",
        [py, os.path.join("experiments", "experiment_03_ssm", "sanity_trace_25event.py")])

    run("9. Sensitivity analysis (T_max / A_th / R_max sweeps) -> results/json/sensitivity_analysis.json",
        [py, os.path.join("experiments", "experiment_07_sensitivity", "run_sensitivity.py")])

    run("10. Generate tables + figures from results/ only",
        [py, os.path.join("src", "analysis", "generate_tables_figures.py")])

    print(f"\n{'=' * 70}\n[run_all] Formal verification (ProVerif) is NOT run automatically here")
    print("because it requires the external `proverif` binary, which may not be")
    print("installed on every machine. To run it manually:")
    print("    cd formal_verification")
    print("    proverif -in pitype protocol_model.pv")
    print("    proverif -in pitype unbounded_attempt.pv")
    print(f"{'=' * 70}")

    print("\n[run_all] PIPELINE COMPLETE. Outputs:")
    print("  data/processed/feature_table.csv")
    print("  results/csv/ssm_event_log.csv, ssm_session_summary.csv")
    print("  results/json/crypto_benchmark.json, ssm_activity_summary.json, sensitivity_analysis.json")
    print("  paper/tables/table_ii_crypto_benchmark.csv, table_iii_ssm_results.csv")
    print("  paper/figures/fig3_compute_cost.png, fig4_sensitivity_tmax.png, fig5_sensitivity_ath.png")


if __name__ == "__main__":
    main()
