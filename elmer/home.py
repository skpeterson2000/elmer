"""The way home: which door a report leaves this unit by.

There are two:

- **The drop** (drop.py), the project's public address that takes a report
  in and mails it on. Nothing to type, nothing of the operator's on the
  report's envelope. This is the door every unit goes by.
- **By hand**, when the drop is not set (a club that has pointed its units
  nowhere, the tests): the report is written where the operator can find it
  and the page says where to mail it.

There used to be a third, the operator's own mail server, and filling in
its settings was the choice of it over the drop. It is gone - see mail.py.

Whichever door, the report is the same text, written to a file first and
shown before it goes, and it goes only by a press or a switch turned on
knowing what it carries. That rule lives with the callers; this module only
answers "which door, and did it open".
"""
from . import drop, mail

CONTACT = mail.CONTACT


def way():
    """The door reports leave by, in words the page can show, or None."""
    if drop.configured():
        return {"via": "drop", "to": mail.CONTACT_NAME,
                "detail": "by the project's drop - nothing of yours on it"}
    return None


def configured():
    return way() is not None


def deliver(subject, body, kind="report"):
    """Send one report by the door that is set. Returns (sent, detail)."""
    if way() is None:
        return False, ("no way home is set on this unit - the report is "
                       f"written here, and {CONTACT} is where to send it")
    return drop.send(subject, body, kind=kind)


def test():
    """One line by the door that is set, so the operator knows it opens."""
    if way() is None:
        return False, "nothing is set to send with"
    return drop.test()
