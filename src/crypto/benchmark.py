"""
Real, measured micro-benchmarks for every cryptographic operation used by
THE authoritative protocol implementation (src/protocol/protocol.py). No
literature numbers, no estimates -- every figure here comes from timing real
executions on whatever machine actually runs this script.

This is the ONLY benchmark script in the project; every downstream
compute-time number (the real-dataset experiment, the always-full baseline,
Table-II/III-equivalents) is computed from results/json/crypto_benchmark.json,
produced here.
"""
import time
import os
import sys
import json
import platform
import statistics as stats

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "protocol"))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from kyber_py.ml_kem import ML_KEM_512

from protocol import hkdf_derive, hmac_tag, run_full_handshake, run_resumption, WearableDevice, Gateway  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT_PATH = os.path.join(REPO_ROOT, "results", "json", "crypto_benchmark.json")

N_WARMUP = 50
N_REPS = 2000
N_REPS_KEM = 500
N_REPS_E2E_FULL = 300


def cpu_info():
    info = {"platform": platform.platform(), "processor": platform.processor(), "python": sys.version}
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    info["model_name"] = line.split(":", 1)[1].strip()
                    break
        with open("/proc/cpuinfo") as f:
            info["logical_cpus"] = sum(1 for l in f if l.startswith("processor"))
    except FileNotFoundError:
        pass
    return info


def time_it(fn, n_reps=N_REPS, n_warmup=N_WARMUP):
    for _ in range(n_warmup):
        fn()
    samples_ms = []
    for _ in range(n_reps):
        t0 = time.perf_counter_ns()
        fn()
        t1 = time.perf_counter_ns()
        samples_ms.append((t1 - t0) / 1e6)
    return {
        "mean_ms": stats.mean(samples_ms), "std_ms": stats.pstdev(samples_ms),
        "min_ms": min(samples_ms), "max_ms": max(samples_ms), "n": n_reps,
    }


def bench_ed25519():
    sk = Ed25519PrivateKey.generate()
    pk = sk.public_key()
    msg = os.urandom(48)
    sig = sk.sign(msg)
    return {"sign": time_it(lambda: sk.sign(msg)), "verify": time_it(lambda: pk.verify(sig, msg))}


def bench_mlkem512():
    ek, dk = ML_KEM_512.keygen()
    ss, ct = ML_KEM_512.encaps(ek)
    return {
        "encaps": time_it(lambda: ML_KEM_512.encaps(ek), n_reps=N_REPS_KEM, n_warmup=10),
        "decaps": time_it(lambda: ML_KEM_512.decaps(dk, ct), n_reps=N_REPS_KEM, n_warmup=10),
        "keygen": time_it(lambda: ML_KEM_512.keygen(), n_reps=N_REPS_KEM, n_warmup=10),
    }


def bench_hmac():
    key = os.urandom(32)
    msg = os.urandom(20)
    return {"hmac_verify_pair": time_it(lambda: (hmac_tag(key, msg), hmac_tag(key, msg)))}


def bench_aesgcm():
    key = os.urandom(16)
    aes = AESGCM(key)
    iv = os.urandom(12)
    pt = os.urandom(64)
    ct = aes.encrypt(iv, pt, None)
    return {
        "encrypt_64B": time_it(lambda: aes.encrypt(os.urandom(12), pt, None)),
        "decrypt_64B": time_it(lambda: aes.decrypt(iv, ct, None)),
    }


def bench_hkdf():
    ss = os.urandom(32)
    return {"derive": time_it(lambda: hkdf_derive(ss, b"n1", b"n2", b"session"))}


def bench_classical_ecdsa_ecdh():
    sk_a = ec.generate_private_key(ec.SECP256R1())
    pk_a = sk_a.public_key()
    sk_b = ec.generate_private_key(ec.SECP256R1())
    pk_b = sk_b.public_key()
    msg = os.urandom(48)
    sig = sk_a.sign(msg, ec.ECDSA(hashes.SHA256()))
    return {
        "ecdsa_sign": time_it(lambda: sk_a.sign(msg, ec.ECDSA(hashes.SHA256()))),
        "ecdsa_verify": time_it(lambda: pk_a.verify(sig, msg, ec.ECDSA(hashes.SHA256()))),
        "ecdh_exchange": time_it(lambda: sk_a.exchange(ec.ECDH(), pk_b)),
        "ecdsa_pubkey_bytes": len(pk_a.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)),
        "ecdsa_sig_bytes": len(sig),
    }


def bench_end_to_end():
    r = {"full_handshake": time_it(lambda: run_full_handshake(), n_reps=N_REPS_E2E_FULL, n_warmup=10)}

    gw = Gateway()
    wd = WearableDevice("bench-wd")
    gw.register(wd)
    n1 = gw.issue_challenge()
    msg1, _ = wd.start_full_auth(n1)
    reply, _, gw_ks = gw.process_full_auth(wd.device_id, msg1, n1)
    wd_ks, wd_kr = wd.finish_full_auth(gw.ed_pub_bytes(), reply[:64], reply[64:])

    counter = {"c": 0}

    def do_resume():
        run_resumption(wd, gw, wd_kr, counter["c"])
        counter["c"] += 1

    r["resumption"] = time_it(do_resume, n_reps=N_REPS, n_warmup=50)
    return r


def measure_message_sizes():
    """Real serialized byte sizes, from actually running the protocol --
    not a field-width formula."""
    _, _, full_bytes = run_full_handshake()
    gw = Gateway()
    wd = WearableDevice("size-check")
    gw.register(wd)
    n1 = gw.issue_challenge()
    msg1, len1 = wd.start_full_auth(n1)
    reply, len2, gw_ks = gw.process_full_auth(wd.device_id, msg1, n1)
    wd_ks, wd_kr = wd.finish_full_auth(gw.ed_pub_bytes(), reply[:64], reply[64:])
    _, resume_bytes = run_resumption(wd, gw, wd_kr, 0)
    return {"full_handshake_bytes": full_bytes, "resumption_bytes": resume_bytes}


def main():
    results = {
        "cpu": cpu_info(),
        "note": ("Software-only wall-clock latency measured on THIS machine (a cloud sandbox "
                 "CPU, not an embedded ARM Cortex-M4). Real, reproducible measurements from the "
                 "accompanying open-source reference implementation; no energy figures are "
                 "asserted from this data."),
        "ed25519": bench_ed25519(),
        "ml_kem_512": bench_mlkem512(),
        "hmac": bench_hmac(),
        "aes_gcm": bench_aesgcm(),
        "hkdf": bench_hkdf(),
        "classical_ecdsa_ecdh": bench_classical_ecdsa_ecdh(),
        "end_to_end": bench_end_to_end(),
        "message_sizes": measure_message_sizes(),
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Wrote {OUT_PATH}")
    print(json.dumps({
        "full_handshake_ms": results["end_to_end"]["full_handshake"]["mean_ms"],
        "resumption_ms": results["end_to_end"]["resumption"]["mean_ms"],
        "full_handshake_bytes": results["message_sizes"]["full_handshake_bytes"],
        "resumption_bytes": results["message_sizes"]["resumption_bytes"],
    }, indent=2))


if __name__ == "__main__":
    main()
