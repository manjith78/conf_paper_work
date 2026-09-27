"""
THE authoritative reference implementation of the hybrid Ed25519 + ML-KEM-512
protocol: registration, full authentication, HMAC-based lightweight
resumption, and AES-128-GCM data transport.

Real, running cryptography -- nothing mocked:
  - Ed25519: `cryptography` library (OpenSSL backend)
  - ML-KEM-512 (FIPS 203): `kyber-py` (pure-Python, spec-conformant)
  - HKDF / HMAC / AES-128-GCM: `cryptography` library / stdlib `hmac`

Every message is actually serialized to bytes, so every byte-count this
project reports (Table II-equivalent, Table III-equivalent) is computed from
this module's real serialization, not estimated. This is the ONLY protocol
implementation in the project -- the crypto benchmark, the real-dataset
experiment's bandwidth accounting, and the always-full baseline all derive
their byte/latency numbers from running this module, never from a second,
parallel implementation.

Preserves both ProVerif-driven design invariants confirmed sound in the old
paper's audit (paper/audit/OLD_PAPER_AUDIT.md, Sec. 1):
  1. The gateway's second signature binds the KEM ciphertext into what it
     signs (`sign(n2 + ct)`), not just the nonce -- prevents ciphertext
     substitution.
  2. A failed HMAC tag verification raises before any state update or
     acceptance -- prevents premature acceptance.
"""
import os
import hmac
import hashlib
import struct

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from kyber_py.ml_kem import ML_KEM_512

NONCE_LEN = 16


def hkdf_derive(shared_secret: bytes, *label_parts: bytes, length: int = 32) -> bytes:
    salt = b"".join(label_parts)
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=b"ssm-protocol").derive(shared_secret)


def hmac_tag(key: bytes, *parts: bytes) -> bytes:
    h = hmac.new(key, digestmod=hashlib.sha256)
    for p in parts:
        h.update(p)
    return h.digest()


class WearableDevice:
    def __init__(self, device_id: str):
        self.device_id = device_id
        self.ed_sk = Ed25519PrivateKey.generate()
        self.ed_pk = self.ed_sk.public_key()
        self.kem_ek, self.kem_dk = ML_KEM_512.keygen()
        self._pending = {}

    def public_bundle(self):
        return {
            "device_id": self.device_id,
            "ed_pk": self.ed_pk.public_bytes(Encoding.Raw, PublicFormat.Raw),
            "kem_ek": self.kem_ek,
        }

    def start_full_auth(self, n1: bytes):
        n2 = os.urandom(NONCE_LEN)
        sigma1 = self.ed_sk.sign(n1)
        self._pending["n1"], self._pending["n2"] = n1, n2
        msg = sigma1 + n2
        return msg, len(msg)

    def finish_full_auth(self, gw_ed_pk: bytes, sigma2: bytes, ct: bytes):
        n1, n2 = self._pending["n1"], self._pending["n2"]
        pk = Ed25519PublicKey.from_public_bytes(gw_ed_pk)
        pk.verify(sigma2, n2 + ct)  # raises on failure -> ciphertext-substitution rejected
        ss = ML_KEM_512.decaps(self.kem_dk, ct)
        k_s = hkdf_derive(ss, n1, n2, b"session")
        k_r = hkdf_derive(ss, b"resumption", n1, n2)
        return k_s, k_r

    def start_resume(self, k_r: bytes, count: int):
        n3 = os.urandom(NONCE_LEN)
        self._pending["n3"], self._pending["count"] = n3, count
        return n3, len(n3)

    def verify_tag1_and_reply(self, k_r: bytes, tag1: bytes):
        n3, count = self._pending["n3"], self._pending["count"]
        expect = hmac_tag(k_r, n3, struct.pack(">I", count))
        if not hmac.compare_digest(tag1, expect):
            raise ValueError("tag1 mismatch")  # gate: no state update before this point
        n4 = os.urandom(NONCE_LEN)
        tag2 = hmac_tag(k_r, n4, struct.pack(">I", count + 1))
        k_s_prime = hkdf_derive(k_r, n3, n4, struct.pack(">I", count))
        msg = n4 + tag2
        return msg, len(msg), k_s_prime


class Gateway:
    def __init__(self):
        self.ed_sk = Ed25519PrivateKey.generate()
        self.ed_pk = self.ed_sk.public_key()
        self.registry = {}
        self.tickets = {}
        self._pending_n3 = {}

    def register(self, wd: WearableDevice):
        self.registry[wd.device_id] = wd.public_bundle()

    def ed_pub_bytes(self):
        return self.ed_pk.public_bytes(Encoding.Raw, PublicFormat.Raw)

    def issue_challenge(self):
        return os.urandom(NONCE_LEN)

    def process_full_auth(self, device_id: str, msg: bytes, n1: bytes):
        sigma1, n2 = msg[:64], msg[64:64 + NONCE_LEN]
        bundle = self.registry[device_id]
        pk = Ed25519PublicKey.from_public_bytes(bundle["ed_pk"])
        pk.verify(sigma1, n1)  # raises on failure -> impersonation rejected
        ss, ct = ML_KEM_512.encaps(bundle["kem_ek"])
        sigma2 = self.ed_sk.sign(n2 + ct)  # ct bound into signature -- invariant #1
        reply = sigma2 + ct
        k_s = hkdf_derive(ss, n1, n2, b"session")
        k_r = hkdf_derive(ss, b"resumption", n1, n2)
        self.tickets[device_id] = {"k_r": k_r, "count": 0}
        return reply, len(reply), k_s

    def process_resume_step1(self, device_id: str, n3: bytes):
        t = self.tickets[device_id]
        tag1 = hmac_tag(t["k_r"], n3, struct.pack(">I", t["count"]))
        self._pending_n3[device_id] = n3
        return tag1, len(tag1)

    def process_resume_step2(self, device_id: str, msg: bytes):
        n4, tag2 = msg[:NONCE_LEN], msg[NONCE_LEN:]
        t = self.tickets[device_id]
        expect = hmac_tag(t["k_r"], n4, struct.pack(">I", t["count"] + 1))
        if not hmac.compare_digest(tag2, expect):
            raise ValueError("tag2 mismatch")  # gate: no state update / acceptance before this point -- invariant #2
        k_s_prime = hkdf_derive(t["k_r"], self._pending_n3[device_id], n4, struct.pack(">I", t["count"]))
        t["count"] += 1
        return k_s_prime


def aes_gcm_encrypt(key32: bytes, plaintext: bytes):
    aes = AESGCM(key32)
    iv = os.urandom(12)
    ct = aes.encrypt(iv, plaintext, None)
    return iv + ct


def aes_gcm_decrypt(key32: bytes, blob: bytes):
    aes = AESGCM(key32)
    iv, ct = blob[:12], blob[12:]
    return aes.decrypt(iv, ct, None)


def run_full_handshake():
    """Executes one complete, real full-authentication handshake. Returns
    (wd_key, gw_key, total_bytes_on_wire) -- total_bytes is computed from
    ACTUAL serialized message lengths, not a formula."""
    gw = Gateway()
    wd = WearableDevice("wd-bench")
    gw.register(wd)

    n1 = gw.issue_challenge()
    msg1, len1 = wd.start_full_auth(n1)
    reply, len2, gw_k_s = gw.process_full_auth(wd.device_id, msg1, n1)
    wd_k_s, wd_k_r = wd.finish_full_auth(gw.ed_pub_bytes(), reply[:64], reply[64:])

    total_bytes = len(n1) + len1 + len2
    assert wd_k_s == gw_k_s
    return wd_k_s, wd_k_r, total_bytes


def run_resumption(wd: WearableDevice, gw: Gateway, k_r: bytes, count: int):
    n3, len_n3 = wd.start_resume(k_r, count)
    tag1, len_tag1 = gw.process_resume_step1(wd.device_id, n3)
    msg2, len_msg2, wd_k_s_prime = wd.verify_tag1_and_reply(k_r, tag1)
    gw_k_s_prime = gw.process_resume_step2(wd.device_id, msg2)
    assert wd_k_s_prime == gw_k_s_prime
    total_bytes = len_n3 + len_tag1 + len_msg2
    return wd_k_s_prime, total_bytes


def measure_full_handshake_bytes():
    """Real serialized byte count for one full handshake -- computed by
    actually running the protocol, not derived from a field-width formula."""
    _, _, nbytes = run_full_handshake()
    return nbytes


def measure_resumption_bytes():
    """Real serialized byte count for one resumption round."""
    gw = Gateway()
    wd = WearableDevice("wd-bench2")
    gw.register(wd)
    n1 = gw.issue_challenge()
    msg1, _ = wd.start_full_auth(n1)
    reply, _, gw_ks = gw.process_full_auth(wd.device_id, msg1, n1)
    wd_ks, wd_kr = wd.finish_full_auth(gw.ed_pub_bytes(), reply[:64], reply[64:])
    _, nbytes = run_resumption(wd, gw, wd_kr, 0)
    return nbytes


if __name__ == "__main__":
    k_s, k_r, nbytes = run_full_handshake()
    print(f"full handshake OK, {nbytes} bytes on wire")
    gw = Gateway()
    wd = WearableDevice("wd-demo")
    gw.register(wd)
    n1 = gw.issue_challenge()
    msg1, _ = wd.start_full_auth(n1)
    reply, _, gw_ks = gw.process_full_auth(wd.device_id, msg1, n1)
    wd_ks, wd_kr = wd.finish_full_auth(gw.ed_pub_bytes(), reply[:64], reply[64:])
    k_s2, nbytes2 = run_resumption(wd, gw, wd_kr, 0)
    print(f"resumption OK, {nbytes2} bytes on wire")
    ct = aes_gcm_encrypt(k_s2, b"heart_rate=72bpm;spo2=98")
    pt = aes_gcm_decrypt(k_s2, ct)
    print(f"AES-GCM roundtrip OK: {pt}")
