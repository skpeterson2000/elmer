# What TowerWitch's position should say about itself

ELMER takes the station's position from TowerWitch in two ways: the UDP broadcast on port 12345, and the state file `~/TowerWitch/towerwitch_state.json`. Today neither says whether the position came from a receiver with a fix. When TowerWitch has no receiver it falls back to Minneapolis. ELMER could not tell that from a fix, and it put a station whose operator had set Pequot Lakes in Minneapolis.

ELMER now ranks positions by what they can vouch for (`elmer/provenance.py`). A receiver's fix beats the typed QTH, and the typed QTH beats anything unvouched. A TowerWitch position that says nothing about its fix is **unvouched**. It is labelled "TowerWitch – no fix quality given" and never outranks the QTH the operator typed. When the fields below arrive, ELMER reads them and a real fix ranks as a fix. Nothing breaks on either side before then: every field is optional, and a packet without them is read as it is today.

## The broadcast packet

Add these beside the existing `gps_lat` and `gps_lon`:

| Field | Type | Meaning |
|---|---|---|
| `fix_mode` | integer 0–3 | gpsd's TPV `mode`: 0 unknown, 1 no fix, 2 2D, 3 3D. What the receiver says now, not what it last had. |
| `sats` | integer | Satellites used in the fix (gpsd SKY, `uSat`, or the count of `used: true`). |
| `hdop` | number | Horizontal dilution of precision (gpsd SKY `hdop`). |
| `eph` | number, metres | Horizontal error estimate, where gpsd gives one (TPV `eph`, or the larger of `epx` and `epy`). |
| `fallback` | boolean | **true whenever `gps_lat`/`gps_lon` are not from a receiver fix**: the configured default (Minneapolis), a last known position, an IP lookup, or anything else. false only when they come from a fix. |
| `fallback_reason` | string, optional | What the fallback is: `"default"`, `"last_known"`, `"ip"`, `"elmer"`, or your own word. |
| `fix_time` | ISO 8601 UTC string | When the fix was taken. This is distinct from `timestamp`, which is when the packet was sent. |

An example with a fix:

```json
{"timestamp": "2026-09-28T07:15:02Z", "source": "TowerWitch",
 "gps_lat": 46.5983, "gps_lon": -94.3154,
 "fix_mode": 3, "sats": 9, "hdop": 1.1, "eph": 5.8,
 "fallback": false, "fix_time": "2026-09-28T07:15:01Z",
 "speed_mps": 0.05, "is_vehicle_speed": false, "closest_armer_towers": []}
```

An example with no receiver:

```json
{"timestamp": "2026-09-28T07:15:02Z", "source": "TowerWitch",
 "gps_lat": 44.9778, "gps_lon": -93.2650,
 "fix_mode": 1, "fallback": true, "fallback_reason": "default",
 "closest_armer_towers": []}
```

How ELMER reads them:

- `fallback: true` makes the position unvouched whatever else the packet says.
- `fix_mode` of 2 or 3 makes it a fix. Its accuracy is `eph` if present, else `hdop` × 5 m, else 10 m for 3D or 30 m for 2D.
- `fix_mode` of 0 or 1 makes it unvouched: "its receiver has no fix".
- No `fix_mode` at all: unvouched, "no fix quality given". This is today's packet.

## The state file

The same, for the last known position:

| Field | Meaning |
|---|---|
| `last_fix_mode` | The mode behind `last_lat`/`last_lon` when they were written. |
| `last_fallback` | true if `last_lat`/`last_lon` were not a receiver fix. |
| `last_fix_time` | When that fix was taken. `timestamp` is when the file was written, and ELMER currently has to use it as the fix's age. |

ELMER treats the state file as unvouched in any case, since it is the last known position, not a live one. With these fields its label can also say whether that position was ever a fix: "TowerWitch's last known position – its fallback, not a fix".

## One more thing worth checking in TowerWitch

TowerWitch reads ELMER's `/api/gps`. That answer now carries `vouch` (`fix`, `typed`, `unvouched`), `accuracy_m` and `label` beside the position. If TowerWitch takes a position from ELMER and broadcasts it, it should send `fallback: true` with `fallback_reason: "elmer"` unless ELMER's `vouch` was `fix`. Otherwise a phone's coarse position or ELMER's typed QTH would come back round as TowerWitch's own.
