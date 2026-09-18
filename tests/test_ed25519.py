#!/usr/bin/env python3
"""Ed25519 in plain Python, against the RFC's own numbers.

    python3 tests/test_ed25519.py

The signed supporter roster stands or falls on this: the public key
derived from a seed, the signature of a message, and a verification that
says yes to the real thing and no to everything else. The first three
checks are RFC 8032 section 7.1 test vectors.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import ed25519  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    shown = got.hex()[:24] if isinstance(got, bytes) else repr(got)
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {shown}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


# RFC 8032, 7.1, TEST 1 and TEST 2.
T1_SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
T1_PK = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
T1_SIG = bytes.fromhex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
                       "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
T2_SEED = bytes.fromhex("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb")
T2_PK = bytes.fromhex("3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c")
T2_MSG = bytes.fromhex("72")
T2_SIG = bytes.fromhex("92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da"
                       "085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00")


def main():
    print("\n-- the RFC's numbers --")
    check("test 1: the public key from the seed", ed25519.public_key(T1_SEED) == T1_PK, True)
    check("  the signature of the empty message", ed25519.sign(b"", T1_SEED) == T1_SIG, True)
    check("  and it verifies", ed25519.verify(b"", T1_SIG, T1_PK), True)
    check("test 2: the public key", ed25519.public_key(T2_SEED) == T2_PK, True)
    check("  the signature of one byte", ed25519.sign(T2_MSG, T2_SEED) == T2_SIG, True)
    check("  and it verifies", ed25519.verify(T2_MSG, T2_SIG, T2_PK), True)

    print("\n-- no to everything else --")
    check("another message", ed25519.verify(b"x", T1_SIG, T1_PK), False)
    check("another key", ed25519.verify(b"", T1_SIG, T2_PK), False)
    bad = bytearray(T1_SIG)
    bad[5] ^= 1
    check("one bit of the signature flipped", ed25519.verify(b"", bytes(bad), T1_PK), False)
    check("a short signature", ed25519.verify(b"", T1_SIG[:63], T1_PK), False)
    check("a key that is not a point", ed25519.verify(b"", T1_SIG, b"\xff" * 32), False)
    check("garbage, without raising", ed25519.verify(b"", b"nonsense", b"nope"), False)

    print("\n-- a fresh pair --")
    seed, pk = ed25519.keypair()
    check("32 and 32 bytes", (len(seed), len(pk)), (32, 32))
    msg = b"supporters roster 2026-09-17 " + b"\x00" * 100
    started = time.perf_counter()
    sig = ed25519.sign(msg, seed)
    check("signs", len(sig), 64)
    check("  verifies", ed25519.verify(msg, sig, pk), True)
    check("  not under the RFC's key", ed25519.verify(msg, sig, T1_PK), False)
    took = time.perf_counter() - started
    print(f"  ..    a sign and a verify took {took:.2f} s on this machine")
    check("fast enough for one roster", took < 10.0, True)

    print()
    if FAILS:
        print("FAILURES:", FAILS)
        sys.exit(1)
    print("all ok")


if __name__ == "__main__":
    main()
