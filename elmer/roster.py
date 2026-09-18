"""The signed roster of issued supporter keys.

A supporter key is eight characters, and eight characters cannot carry a
signature. What can is a list: every key the developer has issued, as a
hash of the key and the name it was cut for, signed with the developer's
private key. The private key never leaves the developer's machine; the
public key is in this file; the roster ships with ELMER as
``supporters.roster`` beside the README, and a unit will accept a typed
key only if it is on a roster whose signature checks. A counterfeit key
cannot get onto the roster without the private key, and a key that was
issued can be taken off it, which is a revocation for free.

The roster holds hashes, not names: it says how many keys exist and lets
a unit check the one in front of it, and nothing else. Who chose to be
named is SUPPORTERS.md, a different list, kept by hand.

A key cut tonight is on tonight's roster, which a unit has after its next
update. A unit that has not updated fetches the current roster from the
repository once, when a key is typed in and not found - the one network
request in ELMER that is not the propagation page - and keeps the copy
under its state directory. A unit with no network accepts the key after
its next update. Verification is :mod:`elmer.ed25519`, plain Python.

The developer's side: ``elmer.py --issuer-init`` makes the signing key,
kept at ``~/.elmer/issuer.key`` (or ``ELMER_ISSUER_KEY``), and prints the
public key to paste below; ``elmer.py --supporter-key "John Doe"`` cuts a
key, adds it to the roster, re-signs and writes the file, which is then
committed and pushed like any other change.
"""
import hashlib
import json
import logging
import os
import re
import urllib.request
from datetime import date
from pathlib import Path

from . import ed25519, paths

log = logging.getLogger("elmer")

# The developer's public key. Only the matching private key can sign a
# roster this file will accept.
PUBLIC_KEY_HEX = "34bcb9c9e996e6d76e42111fb9c744658b80197279a0066b671582a4bbbce74a"
PRODUCT = "elmer-supporter"
FILE = paths.ROOT / "supporters.roster"           # ships with the program
CACHE = paths.STATE / "supporters.roster"         # fetched, kept on the unit
URL = "https://raw.githubusercontent.com/skpeterson2000/elmer/main/supporters.roster"
FETCH_TIMEOUT = 8
ISSUER_KEY = Path(os.environ.get("ELMER_ISSUER_KEY") or (Path.home() / ".elmer" / "issuer.key"))


def public_key():
    return bytes.fromhex(PUBLIC_KEY_HEX)


def _clean_key(key):
    return re.sub(r"[\s-]+", "", str(key or "").upper())


def _clean_holder(holder):
    return re.sub(r"[^A-Z0-9]", "", str(holder or "").upper())


def entry(key, holder):
    """What the roster holds for one issued key: a hash of the key and the
    name it was cut for, so the file names nobody."""
    text = f"{PRODUCT}:{_clean_key(key)}:{_clean_holder(holder)}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _message(issued, entries):
    """What is signed: the date and the sorted entries, one a line."""
    return ("\n".join([f"{PRODUCT}-roster", str(issued)] + sorted(entries)) + "\n").encode("utf-8")


# ------------------------------------------------------------- reading

def parse(text, key=None):
    """(roster, None) for a roster whose signature checks, else (None, reason).
    A roster is {"issued", "entries": set, "count"}."""
    try:
        data = json.loads(text or "")
    except ValueError:
        return None, "not a roster"
    if not isinstance(data, dict):
        return None, "not a roster"
    issued = str(data.get("issued") or "")
    entries = data.get("entries")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", issued) or not isinstance(entries, list) \
            or not all(isinstance(e, str) and re.fullmatch(r"[0-9a-f]{64}", e) for e in entries):
        return None, "not a roster"
    try:
        signature = bytes.fromhex(str(data.get("signature") or ""))
    except ValueError:
        return None, "the roster's signature is not one"
    if not ed25519.verify(_message(issued, entries), signature, key or public_key()):
        return None, "the roster's signature does not check"
    return {"issued": issued, "entries": set(entries), "count": len(set(entries))}, None


_cache = {}


def _read(path, key=None):
    """A roster from a file, verified once per version of the file."""
    try:
        stamp = (str(path), path.stat().st_mtime_ns, path.stat().st_size, key)
    except OSError:
        return None
    if _cache.get(str(path), (None,))[0] == stamp:
        return _cache[str(path)][1]
    try:
        roster, why = parse(path.read_text(encoding="utf-8"), key)
    except OSError:
        roster = None
    if roster is None and why:
        log.warning("roster: %s is ignored: %s", path.name, why)
    _cache[str(path)] = (stamp, roster)
    return roster


def load(key=None):
    """The best roster this unit has: the shipped one or the fetched one,
    whichever was issued later. None when neither checks."""
    found = [r for r in (_read(FILE, key), _read(CACHE, key)) if r]
    if not found:
        return None
    return max(found, key=lambda r: (r["issued"], r["count"]))


def contains(key, holder, fetch=False, pubkey=None):
    """Whether this key was issued for this name. With `fetch`, a key not
    on the roster here is looked for on the current roster first."""
    wanted = entry(key, holder)
    roster = load(pubkey)
    if roster and wanted in roster["entries"]:
        return True
    if fetch:
        fetched, why = fetch_current(pubkey)
        if fetched and wanted in fetched["entries"]:
            return True
    return False


def fetch_current(pubkey=None, url=None, timeout=FETCH_TIMEOUT):
    """The roster as the repository has it now, kept on the unit when it
    is newer than what is here. (roster, None) or (None, reason)."""
    url = url or URL
    if not url:
        return None, "no roster to fetch from"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ELMER"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read(1 << 20).decode("utf-8")
    except Exception as err:            # noqa: BLE001 - any failure is "no network"
        return None, f"could not fetch the roster: {err.__class__.__name__}"
    roster, why = parse(text, pubkey)
    if roster is None:
        return None, why
    have = load(pubkey)
    if have is None or (roster["issued"], roster["count"]) > (have["issued"], have["count"]):
        try:
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(text, encoding="utf-8")
        except OSError as err:
            log.warning("roster: could not keep the fetched roster: %s", err)
    return roster, None


# ------------------------------------------------------------- issuing

def _seed(path=None):
    path = Path(path or ISSUER_KEY)
    try:
        seed = bytes.fromhex(path.read_text(encoding="utf-8").strip())
    except OSError:
        raise FileNotFoundError(f"no issuer key at {path} - elmer.py --issuer-init makes one")
    except ValueError:
        raise ValueError(f"the issuer key at {path} is not one")
    if len(seed) != 32:
        raise ValueError(f"the issuer key at {path} is not one")
    return seed


def init_issuer(path=None):
    """Make the signing key, keep it, and return the public key's hex for
    PUBLIC_KEY_HEX. Refuses to overwrite one that exists."""
    path = Path(path or ISSUER_KEY)
    if path.exists():
        raise FileExistsError(f"an issuer key already exists at {path}")
    seed, pk = ed25519.keypair()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(seed.hex() + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return pk.hex()


def write(entries, seed, path=None, issued=None):
    """Sign a set of entries and write the roster. Returns the text."""
    issued = issued or date.today().isoformat()
    entries = sorted(set(entries))
    signature = ed25519.sign(_message(issued, entries), seed)
    text = json.dumps({"issued": issued, "count": len(entries),
                       "public_key": ed25519.public_key(seed).hex(),
                       "entries": entries, "signature": signature.hex()},
                      indent=1) + "\n"
    Path(path or FILE).write_text(text, encoding="utf-8")
    _cache.clear()
    return text


def issue(key, holder, seed_path=None, path=None, issued=None):
    """Put an issued key on the roster and re-sign it. Returns the count."""
    seed = _seed(seed_path)
    path = Path(path or FILE)
    pk = ed25519.public_key(seed)
    have, why = (parse(path.read_text(encoding="utf-8"), pk) if path.exists() else (None, None))
    if path.exists() and have is None:
        raise ValueError(f"the roster at {path} does not check under this issuer key: {why}")
    entries = set(have["entries"]) if have else set()
    entries.add(entry(key, holder))
    write(entries, seed, path, issued)
    return len(entries)


def revoke(key, holder, seed_path=None, path=None, issued=None):
    """Take an issued key off the roster. Returns whether it was there."""
    seed = _seed(seed_path)
    path = Path(path or FILE)
    have, why = parse(path.read_text(encoding="utf-8"), ed25519.public_key(seed))
    if have is None:
        raise ValueError(f"the roster at {path} does not check under this issuer key: {why}")
    entries = set(have["entries"])
    was = entry(key, holder) in entries
    entries.discard(entry(key, holder))
    write(entries, seed, path, issued)
    return was
