# ELMER on Windows — quick start

Ten minutes, no programming, nothing installed unless you ask for it. This
walks through the download, what you will see, and where everything else is.

## 1. Get it

**The short way.** On the [Releases page](https://github.com/skpeterson2000/elmer/releases/latest)
download `ELMER-windows-<build>.zip` (about 45 MB). Right-click it, *Extract
All…*, and put the folder anywhere that is not OneDrive — `C:\ELMER` or your
Documents folder are both fine. (OneDrive syncs the database out from under
the program; the installer warns about it too.)

The zip carries its own Python — the official one from python.org, signed by
the Python Software Foundation — so Windows does not put up its "unrecognized
app" screen, and nothing is installed on your machine.

**The other way**, if you would rather have a copy that updates itself: install
[git for Windows](https://git-scm.com/download/win), open PowerShell where you
want it, and

```
git clone https://github.com/skpeterson2000/elmer.git
cd elmer
powershell -ExecutionPolicy Bypass -File install.ps1
```

`install.ps1` checks what is on the machine, says what is missing (Python,
git, poppler), and offers to fetch each with `winget` — it does nothing you
do not say yes to.

## 2. Start it

Double-click **`elmer.cmd`**. The first time takes a few seconds; then ELMER
opens in a window of its own (Edge or Chrome, in app mode — no address bar)
and puts itself on the Start Menu with its icon. The first launch offers to
open maximized; the window remembers its size, place and zoom after that.

A console window stays open behind it. That is the program running; leave
it. **Closing the ELMER window stops ELMER** — that is the Exit, and there is
an *Exit* button in the window's own corner too. If people are playing a game
on it from their phones, it says so before it goes.

If the console flashes and vanishes, or says *not available*: run `elmer.cmd`
from PowerShell instead (`.\elmer.cmd`) so the message stays on screen, and
see *If something is wrong* below.

## 3. What you will see

![The dashboard](screenshots/dashboard.png)

The dashboard opens on a **Start here** panel with three steps:

1. **Answer some questions.** *Start with Technician* puts you in a drill.
   Pick an answer; the explanation, the concept it belongs to and the rule it
   rests on appear beneath it. ELMER schedules what you got wrong.
2. **Add your callsign** (if you have one). The FCC record supplies your
   class, expiry and grid, and the band plan then shows *your* privileges.
3. **Set where you are.** A grid square, a town, or *Locate me*. Band
   conditions, Make Contact and the parks list all turn on it.

Steps 2 and 3 are optional; the panel goes away after your first answered
question. The class cards below it show mastery, exam odds and coverage for
each pool as you go.

![A drill question, answered](screenshots/drill.png)

## 4. Other people, other screens

ELMER is a program on this laptop; the browser is only the screen. Anyone on
the same wifi can open the address the console prints (something like
`http://192.168.1.20:5000`) on a phone or laptop and use it — their progress
is kept apart from yours under their own name (the **who** menu, top right).
A table of players joins a game by pointing phones at the QR code on the
**Gaming Center** screen. Windows may ask, the first time, whether to allow
Python through the firewall on private networks: say yes, or nobody but this
laptop can reach it.

## 5. Keeping it current

The dashboard's **Update** panel checks about once a day and says what is
waiting; nothing is applied until you press *Update now*. The portable zip
cannot update itself — it has no git in it — and the panel says so. To give
it that, run `install.ps1` in the folder once and say yes to git and the
*connect* step; from then on it updates like every other copy.

## If something is wrong

- **Self-check** on the dashboard runs the same checks as `--doctor` and,
  where a line has one known remedy, offers a **Fix** beside it.
- **Report a problem** on the dashboard writes what happened in your words,
  bundles the log with account names taken out, and shows you the report
  before anything is sent.
- The console (or `data\elmer.log`) has the rest.
- Common ones: the window is blank — give it five seconds, it is warming up;
  *port 5000 in use* — another ELMER is running, and the newest one offers
  to tidy the others; *No module named …* — the copy was moved out from
  under its Python, run `install.ps1` again.

## Where the rest is

The [README](../README.md) is one screen; the reasoning is
[DESIGN.md](../DESIGN.md). The parts a Windows user meets first:

- [What's in it](../DESIGN.md#whats-in-it) — the pools, the study modes, the
  mock exams, the ranks.
- [The Gaming Center](../DESIGN.md#the-gaming-center) — Tournament, Shootout,
  CutThroat and Golf, at a table of phones or across a hall.
- [Where the station is](../DESIGN.md#where-the-station-is) — band conditions,
  the band plan, the Lab, the antenna advice.
- [Getting a message out](../DESIGN.md#getting-a-message-out) — Make Contact,
  and reaching somewhere in particular.
- [On Windows](../DESIGN.md#on-windows) — the long version of this page: the
  window, the Start Menu, other copies, the zip and how it is built.
- [Keeping it up to date](../DESIGN.md#keeping-it-up-to-date) and
  [When it goes wrong](../DESIGN.md#when-it-goes-wrong).
- [Sharing one unit](../DESIGN.md#sharing-one-unit) — several people, one
  laptop, and what a password does and does not protect.
