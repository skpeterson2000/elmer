"""The drop: a report leaves the unit with nothing of the operator's on it.

The mail path in mail.py asks the operator for an outgoing mail server and
an app password before a single report can go, and a Pi in a club hall has
nobody to type those in. The drop asks for nothing. A unit posts the report
to one public address - a Google Apps Script that its owner deployed from
their own account - and the script mails it on, or files it in a GitHub
folder, or both, with every credential for that held on the script's side
and none on any unit. See tools/report_drop.gs for the script and the
one-time setup.

An address like that can be public because it only takes things in. The
worst anyone can do with it is send junk, which is why the script wants a
tag in the payload and caps what it accepts, and why nothing here can read
back what was sent. A GitHub token in this file would not have that
property: it would be scraped and revoked within the hour, and until it was
it could write to the repository.

What goes, and when, is unchanged. A report is written to a file first,
shown so it can be read, and sent only by a press or a switch the operator
turned on knowing what it carries. The drop is only which door it leaves by.
"""
import json
import logging
import os
import time
import urllib.error
import urllib.request

from . import mail
from .paths import STATE

log = logging.getLogger("elmer")

# The project's drop, once the script is deployed: the web-app URL from
# script.google.com, ending in /exec. Empty until then, and with it empty a
# unit with no mail settings keeps its reports and says where to send them.
URL = "https://script.google.com/macros/s/AKfycbze82Hhh1Yk_EbwXJnvh8go557K8nh01y6gklkX5bwWwSJ7XkL6q-GwiPGOwqGyhjZ6/exec"

# A club running its own script points its units at it here, without
# editing the program: {"url": "https://script.google.com/.../exec"}.
SETTINGS = STATE / "drop.json"
TAG = "ELMER"
TIMEOUT = 30
MOST = 400_000          # characters of body; the script refuses more
VERSION = 1


def url():
    """Where this unit's reports are dropped, or an empty string.

    The unit's own drop.json first; then ELMER_DROP_URL if it is in the
    environment at all - the tests set it empty, so nothing a test writes
    can reach the project's real drop; then the address built in.
    """
    try:
        own = json.loads(SETTINGS.read_text()).get("url")
    except (OSError, ValueError, AttributeError):
        own = None
    if own:
        return str(own).strip()
    if "ELMER_DROP_URL" in os.environ:
        return os.environ["ELMER_DROP_URL"].strip()
    return str(URL or "").strip()


def configured():
    return bool(url())


def payload(subject, body, kind="report"):
    """What is sent: the tag the script looks for, the report, and a mark
    for the file name that is this machine and not its operator."""
    from . import bugreport, cohort
    return {
        "tag": TAG,
        "version": VERSION,
        "kind": kind,
        "subject": mail.subject_line(subject),
        "body": str(body or "")[:MOST],
        "unit": cohort.machine_mark(),
        "build": bugreport.build_stamp().get("commit") or "unknown",
        "made_at": int(time.time()),
    }


def send(subject, body, kind="report"):
    """Post one report. Returns (sent, detail); never raises.

    Apps Script answers a POST with a redirect to the page holding the
    script's reply; urllib follows it as a GET, which is what the redirect
    is for, and the reply comes back as JSON saying what the script did
    with the report - mailed it, filed it, or refused it.
    """
    where = url()
    if not where:
        return False, "no drop is set for this unit"
    data = payload(subject, body, kind)
    subject = data["subject"]
    req = urllib.request.Request(
        where, data=json.dumps(data).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "ELMER"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read(10_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        detail = f"the drop answered {exc.code} {exc.reason}"
    except (urllib.error.URLError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", None) or exc
        detail = f"could not reach the drop: {type(reason).__name__}: {reason}"
    else:
        try:
            said = json.loads(raw)
        except ValueError:
            said = {}
        if said.get("ok"):
            done = [f"mailed to {said['mailed']}" if said.get("mailed") else "",
                    f"filed as {said['github']}" if said.get("github") else ""]
            detail = "dropped: " + (", ".join(d for d in done if d) or "taken")
            log.info("drop: sent '%s' - %s", subject[:60], detail)
            mail.remember(True, detail, subject, mail.CONTACT, via="drop")
            return True, detail
        detail = ("the drop refused it: " + str(said.get("detail") or raw[:200]
                  or "no reply").strip())
    log.warning("drop: could not send '%s': %s", subject[:60], detail)
    mail.remember(False, detail, subject, mail.CONTACT, via="drop")
    return False, detail


def test():
    """One line through the drop, so the operator knows the path works."""
    stamp = time.strftime("%Y-%m-%d %H:%M %Z")
    return send(f"test message {stamp}",
                "This is a test from an ELMER unit, by the drop. "
                "If you are reading it, the path works.\n", kind="test")
