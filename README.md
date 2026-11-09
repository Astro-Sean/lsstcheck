# lsstcheck

Cross-match a transient against LSST, the TNS public catalog, and the
Rubin schedule. Takes a TNS name, a survey name, an LSST diaObjectId,
or sky coordinates.

## Usage

```bash
lsstcheck 2024lwa                  # TNS name (AT/SN prefix optional)
lsstcheck ZTF26abfwokm             # survey / internal name
lsstcheck 170587106692825120       # LSST diaObjectId
lsstcheck LSST-AP-DO-170587106692825120
lsstcheck 338.196 -9.447           # RA Dec, decimal degrees
lsstcheck "338.196,-9.447,60"      # ra,dec,radius(arcsec)
lsstcheck 13:32:47.04 -09:26:49.0   # sexagesimal
```

Options:

| option | default | meaning |
|---|---|---|
| `--radius` | 15 | LASAIR cone radius, arcsec |
| `--tns-radius` | 5 | TNS cone radius, arcsec |
| `--days` | 120 | exposure history window for the cadence estimate |
| `--sched-hours` | 48 | schedule look-ahead, clamped to 1-48 h |
| `--refresh-tns` | off | rebuild the TNS index |

## What it reports

- **TNS** - catalog date, object name, reporting group, type,
  redshift, discovery date, separation, and alternative names.
- **LSST / LASAIR** - diaObjectId, `LSST-*-DO-*` names, LASAIR
  detection count, and a clickable object link (OSC 8 hyperlink; the
  raw URL prints too).
- **Rubin schedule** - the tool queries the published schedule first
  and says how far ahead it reaches. Confirmed visits print as a
  table. Past coverage always prints as history (nights covered, last
  covered date, bands, median revisit). When nothing is scheduled, an
  estimate of the next coverage date is built from that history and
  labeled as an estimate - it is not a forecast. The schedule section
  links to the schedule viewer pre-filtered to pointings within ~2 deg
  of the target, and the links section adds the all-sky pointings
  skymap.

## Example

```
========================== target ==========================
-> name: 2024lwa
-> position: 338.196074, -9.447009  (TNS)
=========================== TNS ===========================
-> catalog date: 2026-11-09
SN2024lwa | Pan-STARRS | SN II | z=0.05689 | disc 2024-06-16
-> alternative names:
    PS24emd
    LSST-AP-DO-170587106692825120
    ZTF26abfwokm
    GOTO26hsm
    ATLAS26jpe
====================== LSST / LASAIR ======================
       diaObjectId  LSST name                      Sep [arcsec]
------------------  -----------------------------  ------------
170587106692825120  LSST-AP-DO-170587106692825120          10.4
-> LASAIR: https://lasair.lsst.ac.uk/objects/170587106692825120/
-> detections in LASAIR: 9
====================== Rubin schedule ======================
-> no visit scheduled in the published window (reaches ~22 h ahead)
-> schedule viewer, pointings near this field: https://usdf-rsp.slac.stanford.edu/obsloctap/static/viewer.html?start=now&time=48&predicate=...
Coverage history         : 2 nights in 120 d, last 2026-10-30
Median revisit           : 2.0 d
Bands                    : i, r
estimated next coverage ~2026-11-11 (in ~2 d)
========================== links ==========================
-> LASAIR object: https://lasair.lsst.ac.uk/objects/170587106692825120/
-> LASAIR cone search: https://lasair.lsst.ac.uk/search/338.196074,-9.447009,15
-> pointings skymap: https://usdf-rsp.slac.stanford.edu/obsloctap/skymap?start=now&time=48
```

## Data sources

- TNS public objects CSV dump, no credentials. Cached as sqlite in
  `~/.cache/lsstcheck/` and rebuilt when the daily file is newer.
- LASAIR public web search at lasair.lsst.ac.uk, no API token needed.
- Rubin ObsLocTAP at usdf-rsp.slac.stanford.edu/obsloctap:
  `/schedule` for the published window, `/exposures` for history.

## Requirements

The script pins `#!/usr/bin/python3` (system Python) so it works the
same in every conda env. That interpreter needs `requests`, `numpy`,
and `astropy` - all present in `~/.local/lib/python3.12/site-packages`.
The `termprint.py` helper sits beside the script and needs no install.

To put it on your PATH:

```bash
ln -s /home/sbrennan/Desktop/RISOTTO/cross_matcher/lsstcheck ~/.local/bin/lsstcheck
```
