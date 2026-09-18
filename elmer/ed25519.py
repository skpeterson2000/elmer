"""Ed25519 signatures in plain Python, for the signed supporter roster.

ELMER has no dependencies beyond Flask, Pillow and reportlab, and none of
those signs anything. The roster of issued supporter keys has to be
signed by the developer and checked on a unit that may never have seen a
network, so the check has to be here, in the standard library's terms:
``hashlib`` for SHA-512 and Python's own big integers for the curve. This
is the arithmetic from RFC 8032 written out plainly - affine points and a
modular inverse a step - which is slow by the standards of a real
library (a verification takes the better part of a second on a Pi) and
exactly fast enough for checking one roster once. It is not for anything
that signs or verifies in a loop.

``keypair()`` makes a new signing key and its public key; ``sign()`` and
``verify()`` are the two operations. Test vectors from RFC 8032 are in
tests/test_ed25519.py.
"""
import hashlib
import secrets

Q = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493
D = (-121665 * pow(121666, Q - 2, Q)) % Q
SQRT_M1 = pow(2, (Q - 1) // 4, Q)


def _h(m):
    return hashlib.sha512(m).digest()


def _inv(x):
    return pow(x, Q - 2, Q)


def _xrecover(y):
    xx = (y * y - 1) * _inv(D * y * y + 1)
    x = pow(xx, (Q + 3) // 8, Q)
    if (x * x - xx) % Q != 0:
        x = (x * SQRT_M1) % Q
    if x % 2 != 0:
        x = Q - x
    return x


_BY = (4 * _inv(5)) % Q
_BX = _xrecover(_BY)
B = (_BX % Q, _BY % Q)


def _edwards(p, q):
    x1, y1 = p
    x2, y2 = q
    x3 = (x1 * y2 + x2 * y1) * _inv(1 + D * x1 * x2 * y1 * y2)
    y3 = (y1 * y2 + x1 * x2) * _inv(1 - D * x1 * x2 * y1 * y2)
    return (x3 % Q, y3 % Q)


def _scalarmult(p, e):
    """e times p, by doubling from the top bit down."""
    result = (0, 1)
    for i in range(e.bit_length() - 1, -1, -1):
        result = _edwards(result, result)
        if (e >> i) & 1:
            result = _edwards(result, p)
    return result


def _encodepoint(p):
    x, y = p
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _isoncurve(p):
    x, y = p
    return (-x * x + y * y - 1 - D * x * x * y * y) % Q == 0


def _decodepoint(s):
    bits = int.from_bytes(s, "little")
    y = bits & ((1 << 255) - 1)
    if y >= Q:
        raise ValueError("not a point")
    x = _xrecover(y)
    if x & 1 != (bits >> 255):
        x = Q - x
    p = (x, y)
    if not _isoncurve(p):
        raise ValueError("not a point")
    return p


def _clamp(h):
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a


def public_key(seed):
    """The 32-byte public key for a 32-byte signing seed."""
    if len(seed) != 32:
        raise ValueError("a signing seed is 32 bytes")
    return _encodepoint(_scalarmult(B, _clamp(_h(seed))))


def keypair():
    """A fresh (seed, public key), both 32 bytes."""
    seed = secrets.token_bytes(32)
    return seed, public_key(seed)


def sign(message, seed):
    """The 64-byte signature of a message under a signing seed."""
    if len(seed) != 32:
        raise ValueError("a signing seed is 32 bytes")
    h = _h(seed)
    a = _clamp(h)
    pk = _encodepoint(_scalarmult(B, a))
    r = int.from_bytes(_h(h[32:] + message), "little") % L
    rp = _encodepoint(_scalarmult(B, r))
    k = int.from_bytes(_h(rp + pk + message), "little") % L
    s = (r + k * a) % L
    return rp + s.to_bytes(32, "little")


def verify(message, signature, pk):
    """True when the signature is the public key's signature of the message.
    Never raises on a malformed signature or key: that is simply False."""
    try:
        if len(signature) != 64 or len(pk) != 32:
            return False
        r = _decodepoint(signature[:32])
        a = _decodepoint(pk)
        s = int.from_bytes(signature[32:], "little")
        if s >= L:
            return False
        k = int.from_bytes(_h(signature[:32] + pk + message), "little") % L
        return _scalarmult(B, s) == _edwards(r, _scalarmult(a, k))
    except (ValueError, TypeError):
        return False
