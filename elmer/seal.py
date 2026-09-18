"""Sealing a person's private data with their password.

An account with a password may have its private data - the QTH, a token,
the notes - sealed, so that the database file gives it to nobody: not to
somebody with the disk, not to a backup, not to the next person at the
controls. The key is the password's, and only the password's. ELMER holds
the key in memory while the person is signed in and never writes it down,
so the data is readable exactly when they are here and at no other time.
That is the point, and it is also the cost: this runs unattended, and what
is sealed is unavailable until its owner signs in again.

The shape is the ordinary one:

    a data key       32 random bytes, made once when the account is sealed
    wrapped          encrypted under a key derived from the password by
                     scrypt with a per-account salt - the same scrypt the
                     password hash already uses
    a recovery code  a second wrap of the same data key, under a code shown
                     once when the seal is made, for the day the password
                     is forgotten; the moderator key opens the account but
                     cannot open the seal, and the code is the only other
                     way in
    the data         each private field encrypted under the data key on its
                     own, so one field can be read without the rest

Changing the password re-wraps the key; nothing is re-encrypted. Taking the
password off unseals everything back to plain.

The cipher is built from what the standard library has - which is HMAC and
SHA-256 and not AES, and a dependency for the sake of a cipher would be a
dependency on every Pi in a shack. So the stream is HMAC-SHA256 in counter
mode - a keystream block is HMAC(key, "stream" || nonce || counter), the
text is XORed with it - and the tag over the nonce and the ciphertext is
HMAC(key, "tag" || nonce || ciphertext), checked before anything is
decrypted. HMAC-SHA256 is a pseudorandom function, which is all a counter
mode asks of its block; the construction is sound as long as a nonce is
never reused under one key, and the nonce is sixteen random bytes drawn
fresh for every sealing. It is not fast, and it does not need to be: what
is sealed is a few hundred bytes a person.
"""
import base64
import hashlib
import hmac
import os
import secrets

KEY_BYTES = 32
NONCE_BYTES = 16
TAG_BYTES = 32
PREFIX = "sealed:"

# scrypt at the cost the password hash already pays - about 45 ms on a Pi.
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1


class Broken(Exception):
    """The sealed data did not check: the wrong key, or a changed blob."""


def derive(password, salt):
    """The key a password makes, with this salt."""
    return hashlib.scrypt(str(password).encode("utf-8"), salt=salt,
                          n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=KEY_BYTES)


def new_key():
    return os.urandom(KEY_BYTES)


def _stream(key, nonce, length):
    out = bytearray()
    counter = 0
    while len(out) < length:
        out += hmac.new(key, b"stream" + nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest()
        counter += 1
    return bytes(out[:length])


def encrypt(key, data):
    """nonce || ciphertext || tag, as bytes."""
    if len(key) != KEY_BYTES:
        raise ValueError("a key is 32 bytes")
    nonce = os.urandom(NONCE_BYTES)
    data = bytes(data)
    text = bytes(a ^ b for a, b in zip(data, _stream(key, nonce, len(data))))
    tag = hmac.new(key, b"tag" + nonce + text, hashlib.sha256).digest()
    return nonce + text + tag


def decrypt(key, blob):
    """The data back, or Broken if the key is wrong or the blob was touched."""
    blob = bytes(blob)
    if len(key) != KEY_BYTES or len(blob) < NONCE_BYTES + TAG_BYTES:
        raise Broken("not a sealed blob")
    nonce, text, tag = blob[:NONCE_BYTES], blob[NONCE_BYTES:-TAG_BYTES], blob[-TAG_BYTES:]
    want = hmac.new(key, b"tag" + nonce + text, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, want):
        raise Broken("the seal does not check")
    return bytes(a ^ b for a, b in zip(text, _stream(key, nonce, len(text))))


# ---- fields: a string in, a string out --------------------------------------

def seal_text(key, text):
    return PREFIX + base64.b64encode(encrypt(key, str(text).encode("utf-8"))).decode("ascii")


def unseal_text(key, sealed):
    if not is_sealed(sealed):
        return sealed
    return decrypt(key, base64.b64decode(sealed[len(PREFIX):])).decode("utf-8")


def is_sealed(value):
    return isinstance(value, str) and value.startswith(PREFIX)


# ---- the key itself, wrapped -------------------------------------------------

def wrap(key, password, salt=None):
    """(salt, wrapped) - the data key under a key the password makes."""
    salt = salt or os.urandom(16)
    return salt, encrypt(derive(password, salt), key)


def unwrap(password, salt, wrapped):
    """The data key, or Broken."""
    return decrypt(derive(password, salt), wrapped)


# ---- the recovery code -------------------------------------------------------
# Twenty letters and digits from an alphabet with no 0/O or 1/I to mistake,
# in groups of four, about a hundred bits: written on a card in the shack, it
# is the one way back in when the password is gone and the moderator cannot
# help - the moderator opens the account, not the seal.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def recovery_code():
    raw = "".join(secrets.choice(ALPHABET) for _ in range(20))
    return "-".join(raw[i:i + 4] for i in range(0, 20, 4))


def normalise_code(code):
    """A code as typed - any case, with or without the dashes."""
    return "".join(c for c in str(code or "").upper() if c in ALPHABET)
