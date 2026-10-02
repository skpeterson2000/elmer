#!/usr/bin/env python3
"""The spots on the reach map: POTA activators, and what WSJT-X heard here.

    python3 tests/test_spots.py

POTA: the latest sample of the feed is kept whole, placed and banded, and a
spot past its expiry - or a batch hours old - is not "on the air now".

WSJT-X: the listener reads WSJT-X's own UDP protocol. The packets here are
built byte for byte as NetworkMessage.hpp lays them out (Qt's QDataStream,
big-endian), so the parser is held to the real format, not to itself. A
decode is placed only when its message names a grid; the band comes from
the dial frequency WSJT-X last reported; a packet that is not the protocol
is dropped without stopping anything. Then a real socket: the listener is
started on a free port on 127.0.0.1, sent a Status and a Decode, and the
station appears.
"""
import socket
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import spotlog, wsjtx  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


# --- QDataStream, as WSJT-X writes it ---------------------------------------
def u32(v): return struct.pack(">I", v)          # noqa: E704
def i32(v): return struct.pack(">i", v)          # noqa: E704
def u64(v): return struct.pack(">Q", v)          # noqa: E704
def f64(v): return struct.pack(">d", v)          # noqa: E704
def flag(v): return b"\x01" if v else b"\x00"    # noqa: E704


def utf8(s):
    b = s.encode("utf-8")
    return u32(len(b)) + b


def header(kind, source="WSJT-X"):
    return u32(0xADBCCBDA) + u32(2) + u32(kind) + utf8(source)


def status(dial_hz, mode="FT8", de_call="K0ELM", de_grid="EN34"):
    return (header(1) + u64(dial_hz) + utf8(mode) + utf8("") + utf8("") + utf8(mode) + flag(False) + flag(False)
            + flag(True) + u32(1500) + u32(1500) + utf8(de_call) + utf8(de_grid) + utf8("") + flag(False)
            + utf8("") + flag(False) + b"\x00" + u32(0) + u32(15) + utf8("Default") + utf8(""))


def decode(message, snr=-12, df=1234, mode="~", off_air=False):
    return (header(2) + flag(True) + u32(3_600_000) + i32(snr) + f64(0.2) + u32(df) + utf8(mode)
            + utf8(message) + flag(False) + flag(off_air))


def wspr(call, grid, hz=14_097_050, snr=-20):
    return (header(10) + flag(True) + u32(0) + i32(snr) + f64(0.5) + u64(hz) + i32(0) + utf8(call)
            + utf8(grid) + i32(37) + flag(False))


def main():
    print("-- POTA: the latest batch, placed and banded --")
    feed = [
        {"spotId": 1, "activator": "k1abc", "frequency": "14062.0", "mode": "CW", "reference": "US-1234",
         "name": "Some State Park", "latitude": 44.5, "longitude": -93.2, "grid6": "EN34ll",
         "spotTime": "2026-10-02T14:00:00", "expire": 1800, "comments": "QRP"},
        {"spotId": 2, "activator": "W9XYZ", "frequency": "7074", "mode": "FT8", "reference": "US-5678",
         "name": "No Position", "latitude": None, "longitude": None, "expire": 900},
        {"spotId": 3, "activator": "N0BAD", "frequency": "14074", "mode": "FT8", "reference": "US-9999",
         "latitude": 40.0, "longitude": -100.0, "invalid": True},
        {"spotId": 4, "activator": "BA4RTS", "frequency": "14074.0", "mode": "FT8", "reference": "CN-1476",
         "name": "æ±Ÿè‹\u008f Mountain Park".replace("\u008f", ""),
         "latitude": 31.3174, "longitude": 120.504, "expire": 60},
    ]
    now = 1_000_000.0
    batch = spotlog.live_batch(feed, now=now)
    check("a spot with no position, or marked invalid, is left out", [s["ref"] for s in batch],
          ["US-1234", "CN-1476"])
    check("  placed, banded, called in capitals", (batch[0]["lat"], batch[0]["band"], batch[0]["call"], batch[0]["mhz"]),
          (44.5, "20 m", "K1ABC", 14.062))
    check("  with when it was spotted, in UTC", batch[0]["spotted"], "2026-10-02T14:00:00Z")
    check("  and when it expires", batch[0]["expires"], now + 1800)
    check("a name sent as UTF-8 read as Windows-1252 is read back", spotlog._repair("cafÃ©"), "café")
    check("  and a name that is not mangled is left alone", spotlog._repair("Lake Park"), "Lake Park")
    with spotlog._live_lock:
        spotlog._live.update(taken=now, spots=batch, as_of="2026-10-02T14:05:00+00:00")
    check("on the air now: the spot whose minute is up is gone", [s["ref"] for s in spotlog.live(now=now + 120)["spots"]],
          ["US-1234"])
    check("a batch an hour and a half old is none at all",
          (spotlog.live(now=now + 2 * 3600)["spots"], spotlog.live(now=now + 2 * 3600)["stale"]), ([], True))

    print("\n-- WSJT-X: who sent it, and from where --")
    for msg, want in (("CQ K1ABC FN42", ("K1ABC", "FN42")),
                      ("CQ POTA K1ABC FN42", ("K1ABC", "FN42")),
                      ("CQ DX JA1XYZ PM95", ("JA1XYZ", "PM95")),
                      ("W1AW K1ABC FN42", ("K1ABC", "FN42")),
                      ("W1AW <PJ4/K1ABC> FK52", ("PJ4/K1ABC", "FK52")),
                      ("W1AW K1ABC R FN42", ("K1ABC", "FN42")),
                      ("W1AW K1ABC -12", (None, None)),
                      ("W1AW K1ABC RR73", (None, None)),
                      ("W1AW K1ABC 73", (None, None)),
                      ("TNX BOB 73 GL", (None, None)),
                      ("CQ FN42", (None, None))):
        check(f"  {msg!r}", wsjtx.sender_and_grid(msg), want)

    print("\n-- WSJT-X: the protocol, byte for byte --")
    st = wsjtx.parse(status(14_074_000))
    check("Status: the dial frequency, mode, and who is operating",
          (st["type"], st["dial_hz"], st["mode"], st["de_call"], st["de_grid"]), (1, 14_074_000, "FT8", "K0ELM", "EN34"))
    old_status = header(1) + u64(7_074_000) + utf8("FT8")
    check("  an older WSJT-X's shorter Status still gives the band", wsjtx.parse(old_status)["dial_hz"], 7_074_000)
    dc = wsjtx.parse(decode("CQ K1ABC FN42", snr=-7))
    check("Decode: the message and its SNR", (dc["type"], dc["message"], dc["snr"], dc["df"]),
          (2, "CQ K1ABC FN42", -7, 1234))
    wp = wsjtx.parse(wspr("G4ABC", "IO91"))
    check("WSPR: the call and grid outright", (wp["call"], wp["grid"], wp["hz"]), ("G4ABC", "IO91", 14_097_050))
    check("a message type ELMER does not read is passed over", wsjtx.parse(header(0) + u32(3) + utf8("2.7")), None)
    for label, data in (("not WSJT-X's magic", b"\x00\x01\x02\x03" + b"\x00" * 20),
                        ("cut short", decode("CQ K1ABC FN42")[:30]),
                        ("a string longer than any packet", header(2) + flag(True) + u32(0) + i32(0) + f64(0) + u32(0)
                         + u32(0x7FFFFFF0))):
        try:
            wsjtx.parse(data)
            check(f"  {label}: refused", "parsed", "Malformed")
        except wsjtx.Malformed:
            check(f"  {label}: refused", "Malformed", "Malformed")

    print("\n-- WSJT-X: heard, placed, banded --")
    heard = wsjtx.Heard()
    t0 = 2_000_000.0
    check("a decode before any Status is placed but has no band yet",
          heard.take(wsjtx.parse(decode("CQ K1ABC FN42")), now=t0)["band"], None)
    heard.take(wsjtx.parse(status(14_074_000)), now=t0)
    e = heard.take(wsjtx.parse(decode("CQ K1ABC FN42", snr=-3, df=1500)), now=t0 + 5)
    check("after a Status, the band and the frequency on the air", (e["band"], e["mhz"], e["mode"]), ("20 m", 14.0755, "FT8"))
    check("  at the middle of its grid square", (e["lat"], e["lon"]), (42.5, -71.0))
    check("one entry per station and band, the latest kept",
          [(s["call"], s["band"], s["snr"]) for s in heard.recent(now=t0 + 10) if s["band"] == "20 m"],
          [("K1ABC", "20 m", -3)])
    check("a decode replayed from a file is not the air now",
          heard.take(wsjtx.parse(decode("CQ W2OFF FN30", off_air=True)), now=t0), None)
    check("a report carries no place", heard.take(wsjtx.parse(decode("K0ELM K1ABC -05")), now=t0), None)
    heard.take(wsjtx.parse(wspr("G4ABC", "IO91")), now=t0)
    check("a WSPR spot is placed on its own frequency's band",
          [(s["call"], s["band"], s["mode"]) for s in heard.recent(now=t0 + 10) if s["call"] == "G4ABC"],
          [("G4ABC", "20 m", "WSPR")])
    check("half an hour on, they have aged off the map", heard.recent(now=t0 + 31 * 60), [])

    print("\n-- the reach map's frame for 6 m and 2 m: no forecast, nothing made up --")
    from elmer import app as A
    real_qth = A.qth_for
    A.qth_for = lambda connection, profile: {"lat": 45.0, "lon": -93.0, "short": "EN35"}
    try:
        client = A.app.test_client()
        local = {"REMOTE_ADDR": "127.0.0.1"}
        six = client.get("/api/bandplan/reach?band=6m", environ_base=local).get_json()
        check("6 m: a frame, flagged as spots alone", (six["ok"], six["spots_only"]), (True, True))
        check("  with no forecast in it - every cell zero", set(six["cells"]), {0})
        check("  and what the map needs to place the spots: the QTH and the sun",
              (six["qth"]["lat"], "dec" in six["sun"] and "gha" in six["sun"]), (45.0, True))
        check("2 m too", client.get("/api/bandplan/reach?band=2m", environ_base=local).get_json()["spots_only"], True)
        check("70 cm has no map", client.get("/api/bandplan/reach?band=70cm", environ_base=local).status_code, 404)
        A.qth_for = lambda connection, profile: {}
        check("no QTH, no map - said, as for HF",
              client.get("/api/bandplan/reach?band=6m", environ_base=local).status_code, 409)
    finally:
        A.qth_for = real_qth

    print("\n-- the listener's settings are checked before anything binds --")
    check("an address that is not one", wsjtx.check_config("pi.local", 2237, "") is not None, True)
    check("a port below 1024", wsjtx.check_config("127.0.0.1", 80, "") is not None, True)
    check("a group that is not multicast", "not a multicast" in (wsjtx.check_config("0.0.0.0", 2237, "10.0.0.1") or ""),
          True)
    check("WSJT-X's own defaults are fine", wsjtx.check_config("127.0.0.1", 2237, ""), None)
    check("  and so is a multicast group", wsjtx.check_config("0.0.0.0", 2237, "224.0.0.73"), None)

    print("\n-- a real socket: started, sent a Status and a Decode, the station appears --")
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    lis = wsjtx.Listener()
    lis.config = {"enabled": True, "host": "127.0.0.1", "port": port, "multicast": ""}
    lis.start()
    for _ in range(50):
        if lis.state["listening"]:
            break
        time.sleep(0.05)
    check("it is listening on the port it was given", (lis.state["listening"], lis.where()), (True, "127.0.0.1:%d" % port))
    out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for data in (status(7_074_000), b"rubbish that is no protocol at all", decode("CQ VK2ABC QF56", snr=-18)):
        out.sendto(data, ("127.0.0.1", port))
    out.close()
    snap = None
    for _ in range(60):
        snap = lis.snapshot()
        if snap["spots"]:
            break
        time.sleep(0.05)
    check("VK2ABC is heard, on 40 m, after a bad packet in between",
          [(s["call"], s["band"], s["snr"]) for s in snap["spots"]], [("VK2ABC", "40 m", -18)])
    check("  the bad packet was counted, not fatal", (snap["dropped"], snap["listening"]), (1, True))
    check("  and WSJT-X's own dial is reported", snap["dial"], [{"mhz": 7.074, "mode": "FT8"}])

    taken = wsjtx.Listener()
    taken.config = dict(lis.config)
    taken.start()
    for _ in range(50):
        if taken.state["error"] or taken.state["listening"]:
            break
        time.sleep(0.05)
    check("a second listener on the same port stands aside and says why, rather than crashing",
          (taken.state["listening"], bool(taken.state["error"]), taken._thread.is_alive()), (False, True, True))
    taken.stop()
    lis.stop()

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
