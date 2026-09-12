"""Mail from a unit to the project: a problem report, a field report.

The address is KC9SP's arrl.net forwarder. An arrl.net address is made for
exactly this - it forwards to whatever inbox its owner points it at and is
filtered on the way - and its owner chose to put it here, so the earlier
worry about baking an address into a public repository is his to have
weighed, and he did.

What ELMER does not carry is a mail account. A unit sends through its
operator's own outgoing mail server - the SMTP submission host, port and
login they would put into any mail program - kept in one file under the
state directory, readable by the account that runs ELMER and nobody else.
Without that file, nothing is sent: a report is written where the operator
can find it and the page says where to mail it by hand.

Nothing goes out that the operator has not either pressed a button for or
switched on and been told the contents of. See fieldreport.py for the one
that goes out on a clock.
"""
import json
import logging
import os
import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from .paths import STATE

log = logging.getLogger("elmer")

CONTACT = "KC9SP@ARRL.NET"
SETTINGS = STATE / "mail.json"
SECURITIES = ("starttls", "ssl", "none")
DEFAULT_PORT = {"starttls": 587, "ssl": 465, "none": 25}
TIMEOUT = 30
FIELDS = ("host", "port", "user", "password", "sender", "security")


def settings():
    """The outgoing-mail settings on this unit, or an empty dict."""
    try:
        data = json.loads(SETTINGS.read_text())
    except (OSError, ValueError):
        return {}
    return {k: data.get(k) for k in FIELDS if data.get(k) not in (None, "")}


def public_settings():
    """The same, with the password replaced by whether there is one."""
    s = settings()
    out = {k: v for k, v in s.items() if k != "password"}
    out["has_password"] = bool(s.get("password"))
    out["configured"] = configured(s)
    out["contact"] = CONTACT
    return out


def configured(s=None):
    s = settings() if s is None else s
    return bool(s.get("host") and s.get("sender"))


def save(**fields):
    """Keep the operator's settings; an empty password keeps the old one."""
    current = settings()
    for key in FIELDS:
        if key not in fields:
            continue
        value = fields[key]
        if key == "password" and not value:
            continue                    # a blank password field means "unchanged"
        if value in (None, ""):
            current.pop(key, None)
        else:
            current[key] = str(value).strip()
    sec = current.get("security") or "starttls"
    current["security"] = sec if sec in SECURITIES else "starttls"
    try:
        current["port"] = int(current.get("port") or DEFAULT_PORT[current["security"]])
    except (TypeError, ValueError):
        current["port"] = DEFAULT_PORT[current["security"]]
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(current, indent=1))
    try:
        os.chmod(SETTINGS, 0o600)       # a password lives in it
    except OSError:
        pass
    return public_settings()


def forget():
    try:
        SETTINGS.unlink()
    except OSError:
        pass
    return public_settings()


def send(subject, body, to=CONTACT, attachments=(), s=None):
    """Send one message. Returns (sent, detail); never raises.

    `attachments` is a list of (filename, text). The body is plain text -
    a report is a thing to be read, and a mail filter is happier with it.
    """
    s = settings() if s is None else s
    if not configured(s):
        return False, "no outgoing mail server is set on this unit"
    msg = EmailMessage()
    msg["From"] = s["sender"]
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="elmer.local")
    msg["X-ELMER"] = "field"
    msg.set_content(body)
    for name, text in attachments:
        msg.add_attachment(text.encode("utf-8"), maintype="text", subtype="plain",
                           filename=name)
    security = s.get("security") or "starttls"
    port = int(s.get("port") or DEFAULT_PORT[security])
    try:
        if security == "ssl":
            client = smtplib.SMTP_SSL(s["host"], port, timeout=TIMEOUT,
                                      context=ssl.create_default_context())
        else:
            client = smtplib.SMTP(s["host"], port, timeout=TIMEOUT)
        with client:
            client.ehlo()
            if security == "starttls":
                client.starttls(context=ssl.create_default_context())
                client.ehlo()
            if s.get("user"):
                client.login(s["user"], s.get("password") or "")
            client.send_message(msg)
        log.info("mail: sent '%s' to %s via %s", subject[:60], to, s["host"])
        return True, f"sent to {to} via {s['host']}"
    except smtplib.SMTPAuthenticationError:
        detail = "the mail server refused the login - check the user name and password"
    except smtplib.SMTPRecipientsRefused:
        detail = f"the mail server refused the address {to}"
    except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
        detail = f"{type(exc).__name__}: {exc}"
    log.warning("mail: could not send '%s': %s", subject[:60], detail)
    return False, detail


def test():
    """One line to the contact, so the operator knows the path works."""
    stamp = time.strftime("%Y-%m-%d %H:%M %Z")
    return send(f"ELMER test message {stamp}",
                "This is a test from an ELMER unit's outgoing-mail settings. "
                "If you are reading it, the path works.\n")
