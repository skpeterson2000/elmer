"""Mail from a unit to the project: a problem report, a field report.

The address is KC9SP's arrl.net forwarder. An arrl.net address is made for
exactly this - it forwards to whatever inbox its owner points it at and is
filtered on the way - and its owner chose to put it here, so the earlier
worry about baking an address into a public repository is his to have
weighed, and he did.

Every subject a unit sends is tagged [ELMER], put on here rather than left
to each caller, so that one mail filter at the far end catches all of them
- the first reports arrived in a spam folder, and a filter needs a token
that cannot be mistaken for a word in somebody else's subject.

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

CONTACT = "KC9SP@arrl.net"
SETTINGS = STATE / "mail.json"
TAG = "[ELMER]"
SECURITIES = ("starttls", "ssl", "none")
DEFAULT_PORT = {"starttls": 587, "ssl": 465, "none": 25}
TIMEOUT = 30
FIELDS = ("host", "port", "user", "password", "sender", "security")

# The big providers stopped taking an account's own password from a mail
# program years ago; each hands out an "app password" instead, from the
# account's security page, and refuses the login otherwise - with a 535 that
# reads exactly like a typo. Named here so the refusal can say so. Yahoo is
# the one that also insists on 465/ssl in practice, and all of them send
# only as the account's own address.
APP_PASSWORD_HOSTS = {
    "yahoo": "Yahoo (Account Security - Generate app password)",
    "gmail": "Gmail (Google Account - Security - App passwords)",
    "googlemail": "Gmail (Google Account - Security - App passwords)",
    "outlook": "Outlook (Microsoft account - Security - App passwords)",
    "office365": "Outlook (Microsoft account - Security - App passwords)",
    "hotmail": "Outlook (Microsoft account - Security - App passwords)",
    "live": "Outlook (Microsoft account - Security - App passwords)",
    "icloud": "iCloud (Apple ID - Sign-In and Security - App-Specific Passwords)",
    "me": "iCloud (Apple ID - Sign-In and Security - App-Specific Passwords)",
    "aol": "AOL (Account Security - Generate app password)",
}


def provider(host):
    """Which of the app-password providers this host belongs to, or None."""
    for part in str(host or "").lower().split("."):
        if part in APP_PASSWORD_HOSTS:
            return APP_PASSWORD_HOSTS[part]
    return None


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


def subject_line(subject):
    """The subject as sent: tagged, once, whatever the caller wrote."""
    subject = str(subject or "").strip()
    return subject if subject.startswith(TAG) else f"{TAG} {subject}".strip()


def send(subject, body, to=CONTACT, attachments=(), s=None):
    """Send one message. Returns (sent, detail); never raises.

    `attachments` is a list of (filename, text). The body is plain text -
    a report is a thing to be read, and a mail filter is happier with it.
    """
    s = settings() if s is None else s
    if not configured(s):
        return False, "no outgoing mail server is set on this unit"
    subject = subject_line(subject)
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
        known = provider(s["host"])
        if known:
            detail = (f"the mail server refused the login. {known.split(' (')[0]} "
                      "does not take the account's own password from a program "
                      f"- it wants an app password, made under {known.split(' (')[1][:-1]}, "
                      "with the full address as the user name")
        else:
            detail = "the mail server refused the login - check the user name and password"
    except smtplib.SMTPSenderRefused:
        detail = (f"the mail server refused to send as {s['sender']}"
                  + (" - the big providers only send as the account's own "
                     "address, so From has to be the mailbox you log in to"
                     if provider(s["host"]) else ""))
    except smtplib.SMTPRecipientsRefused:
        detail = f"the mail server refused the address {to}"
    except smtplib.SMTPServerDisconnected as exc:
        # The big providers do not always refuse a bad login with a clean 535;
        # Yahoo in particular drops the socket mid-login, which smtplib reports
        # as "Connection unexpectedly closed" - a message that sends an
        # operator looking at the network when the answer is the password. If
        # the connection got as far as the login it is almost never the wire.
        known = provider(s["host"])
        if known and s.get("user"):
            detail = (f"{known.split(' (')[0]} closed the connection during "
                      "login. That is how it refuses a wrong or not-yet-active "
                      "app password, and how it answers once there have been "
                      "too many tries in a row. Wait about fifteen minutes for "
                      "the lockout to clear, then re-enter the 16-character app "
                      f"password with no spaces, made under "
                      f"{known.split(' (')[1][:-1]}, with the full address "
                      f"({s.get('user')}) as the user name")
        else:
            detail = (f"the mail server closed the connection ({exc}) - if this "
                      "keeps happening the login was refused rather than the "
                      "network lost")
    except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
        detail = f"{type(exc).__name__}: {exc}"
        if provider(s["host"]) and security != "ssl":
            detail += (" - with this provider try port 465 and ssl, which is "
                       "the door they keep open for mail programs")
    log.warning("mail: could not send '%s': %s", subject[:60], detail)
    return False, detail


def test():
    """One line to the contact, so the operator knows the path works."""
    stamp = time.strftime("%Y-%m-%d %H:%M %Z")
    return send(f"test message {stamp}",
                "This is a test from an ELMER unit's outgoing-mail settings. "
                "If you are reading it, the path works.\n")
