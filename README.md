# lsstcheck

Cross-match a transient against LSST, the TNS public catalog, and the
Rubin schedule. Give it a TNS name, survey name, LSST diaObjectId, or
sky coordinates.

## Install

Keep `termprint.py` in the same directory as `lsstcheck`. Then:

```bash
/usr/bin/python3 -m pip install --user -r requirements.txt
ln -sf "$PWD/lsstcheck" ~/.local/bin/lsstcheck
```

If pip refuses with `externally-managed-environment` (common on
Debian/Ubuntu), add `--break-system-packages`. With `--user` it only
writes to `~/.local`, not the system directories.

The shebang is pinned to `/usr/bin/python3`, so the command behaves
the same inside conda environments. The `--user` install lands in
`~/.local`, where that interpreter always looks. To run under a
different interpreter, change the first line of `lsstcheck` to
`#!/usr/bin/env python3` and install the requirements into that
environment instead.

Needs Python 3.9+. matplotlib is only used for `--plot` and
`--save`; leave it out of `requirements.txt` if you never plot.

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
| `--days` | 120 | exposure history window |
| `--sched-hours` | 48 | schedule look-ahead, clamped to 1-48 h |
| `--refresh-tns` | off | rebuild the TNS index |
| `--live-tns` | off | live per-object check on wis-tns.org |
| `--plot` | off | show the LASAIR lightcurve in a plot window |
| `--save` | off | save the lightcurve plot and table to the current directory |
| `--plot-out` | `lsstcheck_<id>_lightcurve.png` | PNG path for `--save` |
| `--open-links` | off | open the LASAIR object page in a browser |

## What it reports

| section | contents |
|---|---|
| TNS | catalog date, object name, type, redshift, discovery date, alternative names with their groups |
| LSST / LASAIR | diaObjectId, `LSST-*-DO-*` names, detection count, clickable object link |
| Rubin Schedule | published-window extent, confirmed visit table or "No scheduled observation", region pointing stats (bands, closest approach), coverage history |

`--plot` opens the AB-mag lightcurve (nightly bins over faded raw
points) and `--save` writes the plot and table to the current
directory. The schedule section links
to the schedule viewer filtered to pointings near the target.

## Example

```

========================== Target ==========================
-> Name: 2024lwa
-> Position: 338.196074, -9.447009  (TNS)

=========================== TNS ============================
-> Catalog date: 2026-11-09
SN2024lwa | Pan-STARRS | SN II | z=0.05689 | disc 2024-06-16
-> Alternative names:
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
-> Detections in LASAIR: 9

===================== Rubin Schedule ======================
-> No scheduled observation in the published window (reaches ~20 h ahead)
-> No pointings within ~3 deg planned in the window
-> Schedule viewer, pointings near this field: https://usdf-rsp.slac.stanford.edu/obsloctap/static/viewer.html?start=now&time=48&predicate=...
Coverage history         : 2 nights in 120 d, last 2026-10-30
Bands                    : i, r

========================== Links ==========================
-> LASAIR object: https://lasair.lsst.ac.uk/objects/170587106692825120/
-> LASAIR cone search: https://lasair.lsst.ac.uk/search/338.196074,-9.447009,15
-> TNS object: https://www.wis-tns.org/object/2024lwa
-> Pointings skymap: https://usdf-rsp.slac.stanford.edu/obsloctap/skymap?start=now&time=48
```

## Data sources

- TNS public objects CSV, cached as sqlite in `~/.cache/lsstcheck/`.
  Name and diaObjectId inputs also check the live page on
  wis-tns.org when the catalog misses, or always with `--live-tns`.
- LASAIR public web search at lasair.lsst.ac.uk, no API token needed.
- Rubin ObsLocTAP at usdf-rsp.slac.stanford.edu/obsloctap for the
  published schedule and exposure history.
