"""Where a unit's reports go, what they are tagged, and how the last one went.

Reports leave a unit by the drop (drop.py), and only by the drop: a public
address that takes a report in and mails it on, with every credential on the
script's side and nothing of the operator's on the report. A unit used to
offer a second door as well - the operator's own outgoing mail server, its
host, port, login and app password typed into a panel and kept in
data/mail.json - from before the drop was deployed. With the drop working it
was an obstacle and nothing else: a form that asked for an account and a
password, beside the report, that nothing needed and nobody should have to
fill in to be heard. So it is gone, and a unit keeps no mail password.
Where the drop cannot be reached, the report is written where the operator
can find it and the page says where to mail it by hand.

CONTACT is that by-hand address, and CONTACT_NAME is who it reaches - what
the Send button says, since the drop, not the page, decides the mailbox.
The address is the project's own reports mailbox, set up for this and
nothing else; it was KC9SP's arrl.net forwarder, which filtered each report
through enough layers that it arrived late. The drop's script mails the
same box (its MAIL_TO), so a report sent and a report mailed by hand land
together.

Every subject a unit sends is tagged [ELMER], put on here rather than left
to each caller, so that one mail filter at the far end catches all of them
- the first reports arrived in a spam folder, and a filter needs a token
that cannot be mistaken for a word in somebody else's subject.

Nothing goes out that the operator has not either pressed a button for or
switched on and been told the contents of. See fieldreport.py for the one
that goes out on a clock.
"""
import json
import logging
import time

from .paths import STATE

log = logging.getLogger("elmer")

CONTACT = "elmeramateurradio@gmail.com"
CONTACT_NAME = "KC9SP"
# The outcome of the last send, so the self-check and the problem report can
# say "the last send failed, and why". This is the line that was missing the
# night three Pis could not mail home: the failure was in the log and
# scrolled past the report's tail.
LAST = STATE / "mail_last.json"
TAG = "[ELMER]"
# Where the retired mail settings lived. Nothing reads it; the doctor says
# when one is still on a unit, because it holds a mail password.
OLD_SETTINGS = STATE / "mail.json"


def subject_line(subject):
    """The subject as sent: tagged, once, whatever the caller wrote."""
    subject = str(subject or "").strip()
    return subject if subject.startswith(TAG) else f"{TAG} {subject}".strip()


def remember(ok, detail, subject, to, via="drop"):
    """Keep the last send outcome where the report and the doctor can read it."""
    try:
        LAST.parent.mkdir(parents=True, exist_ok=True)
        LAST.write_text(json.dumps({"at": time.time(), "ok": bool(ok),
                                    "detail": detail, "subject": subject[:80],
                                    "to": to, "via": via}))
    except OSError as exc:
        # The send itself is done either way; only its record is lost.
        log.warning("mail: the last send's outcome could not be kept at %s: %s", LAST, exc)


def last_result():
    """The last send this unit attempted, or None."""
    try:
        return json.loads(LAST.read_text())
    except (OSError, ValueError):
        return None


def old_settings():
    """The retired mail settings file, if one is still on this unit."""
    return OLD_SETTINGS if OLD_SETTINGS.is_file() else None
