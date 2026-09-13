"""The way home: which door a report leaves this unit by.

There are three, and the operator's choice is expressed by what they set
up rather than by a switch beside it:

- **The drop** (drop.py), when the project has one deployed and the
  operator has set nothing. Nothing to type, nothing of theirs on the
  report's envelope. This is the door a Pi in a club hall goes by.
- **Their own mail server** (mail.py), when they have filled in the mail
  settings. Filling them in is the choice: a report then goes that way and
  not by the drop, because somebody who typed an app password in wanted
  their reports to leave by their own account. Forgetting the settings
  goes back to the drop.
- **By hand**, when neither is set: the report is written where they can
  find it and the page says where to mail it.

Whichever door, the report is the same text, written to a file first and
shown before it goes, and it goes only by a press or a switch turned on
knowing what it carries. That rule lives with the callers; this module only
answers "which door, and did it open".
"""
from . import drop, mail

CONTACT = mail.CONTACT


def way():
    """The door reports leave by, in words the page can show, or None."""
    if mail.configured():
        s = mail.settings()
        return {"via": "mail", "to": CONTACT,
                "detail": f"through your own mail server, {s.get('host')}"}
    if drop.configured():
        return {"via": "drop", "to": CONTACT,
                "detail": "by the project's drop - nothing of yours on it"}
    return None


def configured():
    return way() is not None


def deliver(subject, body, kind="report"):
    """Send one report by the door that is set. Returns (sent, detail)."""
    w = way()
    if w is None:
        return False, ("no way home is set on this unit - the report is "
                       f"written here, and {CONTACT} is where to send it")
    if w["via"] == "mail":
        return mail.send(subject, body)
    return drop.send(subject, body, kind=kind)


def test():
    """One line by the door that is set, so the operator knows it opens."""
    w = way()
    if w is None:
        return False, "nothing is set to send with"
    return mail.test() if w["via"] == "mail" else drop.test()
