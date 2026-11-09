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
| `--live-tns` | off | live per-object check on wis-tns.org |
| `--plot` | off | show the LASAIR lightcurve in a plot window |
| `--save` | off | save the lightcurve plot and table to the current directory |
| `--plot-out` | `lsstcheck_<id>_lightcurve.png` | PNG path for `--save` |

## What it reports

| section | contents |
|---|---|
| TNS | catalog date, object name, reporting group, type, redshift, discovery date, separation, alternative names with their groups. Rows verified against the live site are tagged `live` |
| LSST / LASAIR | diaObjectId, `LSST-*-DO-*` names, detection count, clickable object link (OSC 8; raw URL prints too). `--plot` opens the difference-flux lightcurve; `--save` writes the plot and table to the current directory |
| Rubin Schedule | published-window extent, confirmed visit table when covered, coverage history (nights, last date, bands, median revisit), labeled estimate when unscheduled |

The schedule section links to the schedule viewer pre-filtered to
pointings within ~2 deg of the target, and the links section adds the
all-sky pointings skymap.

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
-> No visit scheduled in the published window (reaches ~22 h ahead)
-> Schedule viewer, pointings near this field: https://usdf-rsp.slac.stanford.edu/obsloctap/static/viewer.html?start=now&time=48&predicate=...
Coverage history         : 2 nights in 120 d, last 2026-10-30
Median revisit           : 2.0 d
Bands                    : i, r
[ok] Estimated next coverage ~2026-11-11 (in ~2 d)

========================== Links ==========================
-> LASAIR object: https://lasair.lsst.ac.uk/objects/170587106692825120/
-> LASAIR cone search: https://lasair.lsst.ac.uk/search/338.196074,-9.447009,15
-> TNS object: https://www.wis-tns.org/object/2024lwa
-> Pointings skymap: https://usdf-rsp.slac.stanford.edu/obsloctap/skymap?start=now&time=48
```

## Data sources

- TNS public objects CSV dump, no credentials. Cached as sqlite in
  `~/.cache/lsstcheck/` and rebuilt when the daily file is newer. For
  name and diaObjectId inputs the tool also checks the live object
  page on wis-tns.org when the catalog misses, or always with
  `--live-tns`; live hits show alternative names with their reporting
  groups.
- LASAIR public web search at lasair.lsst.ac.uk, no API token needed.
- Rubin ObsLocTAP at usdf-rsp.slac.stanford.edu/obsloctap:
  `/schedule` for the published window, `/exposures` for history.

## Requirements

The script pins `#!/usr/bin/python3` (system Python) so it works the
same in every conda env. That interpreter needs `requests`, `numpy`,
and `astropy`; install them with pip if they are missing. The
`termprint.py` helper sits beside the script and needs no install.

To put it on your PATH:

```bash
ln -s /path/to/cross_matcher/lsstcheck ~/.local/bin/lsstcheck
```

## Testing

`unit_test/` holds a pytest suite in two parts:

- `test_unit.py` - offline tests for input parsing, coordinate math,
  schedule matching, TNS catalog building (mocked download), and
  LASAIR HTML parsing (fixtures). No network needed.
- `test_integration.py` - end-to-end runs of the CLI against live
  services: the known target `2024lwa`, an LSST object with scheduled
  visits, unobserved coordinates, name forms, and bad input.

```bash
pytest                    # everything
pytest -m "not integration"   # offline tests only, a few seconds
pytest -m integration         # live-service stress tests, ~1 min
```
