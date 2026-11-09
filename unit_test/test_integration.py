"""End-to-end tests: run the lsstcheck CLI against live services.

These hit TNS, LASAIR, and Rubin ObsLocTAP, so they are slow and need
network. Run only them with:  pytest -m integration
Skip them with:              pytest -m "not integration"
"""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LSSTCHECK = ROOT / "lsstcheck"

pytestmark = pytest.mark.integration


def run_cli(*args, timeout=240):
    return subprocess.run(
        [str(LSSTCHECK), *args],
        capture_output=True, text=True, timeout=timeout,
    )


class TestKnownTarget:
    """2024lwa: TNS supernova with LSST coverage but nothing scheduled."""

    def test_full_report(self):
        r = run_cli("2024lwa")
        assert r.returncode == 0, r.stderr
        out = r.stdout
        assert "SN2024lwa" in out
        assert "170587106692825120" in out
        assert "LSST-AP-DO-170587106692825120" in out
        # alternative names from TNS
        assert "ZTF26abfwokm" in out
        assert "PS24emd" in out
        # LASAIR identity + link
        assert "lasair.lsst.ac.uk/objects/170587106692825120" in out
        assert "detections in LASAIR" in out
        # schedule section always reports something honest
        assert "Rubin schedule" in out
        assert ("no visit scheduled" in out
                or "scheduled visits" in out)

    def test_coordinates_resolve_same_object(self):
        r = run_cli("338.196", "-9.447")
        assert r.returncode == 0, r.stderr
        assert "SN2024lwa" in r.stdout
        assert "170587106692825120" in r.stdout

    def test_internal_name_input(self):
        r = run_cli("ZTF26abfwokm")
        assert r.returncode == 0, r.stderr
        assert "SN2024lwa" in r.stdout


class TestScheduledTarget:
    """313761042329501776: LSST object with no TNS entry, visits scheduled."""

    def test_dia_object_id(self):
        r = run_cli("313761042329501776")
        assert r.returncode == 0, r.stderr
        out = r.stdout
        assert "313761042329501776" in out
        assert "no TNS entry" in out
        assert "detections in LASAIR" in out
        # this field is in the current published window
        assert "scheduled visits" in out or "no visit scheduled" in out

    def test_lsst_name_form(self):
        # LSST-*-DO-<id> parses to the same diaObjectId path
        r = run_cli("LSST-AP-DO-313761042329501776")
        assert r.returncode == 0, r.stderr
        assert "313761042329501776" in r.stdout


class TestUnobservedTarget:
    """A position outside the LSST footprint: nothing anywhere."""

    def test_high_dec_coords(self):
        r = run_cli("10.0", "60.0")
        assert r.returncode == 0, r.stderr
        out = r.stdout
        assert "no LSST alerts" in out
        assert "northern edge" in out  # dec>15 footprint warning
        assert "no visit scheduled" in out or "scheduled visits" in out

    def test_remote_south_coords(self):
        # far south field, likely no TNS object and sparse coverage
        r = run_cli("150.0", "-75.0")
        assert r.returncode == 0, r.stderr
        assert "Rubin schedule" in r.stdout


class TestBadInput:
    def test_no_args_exits_nonzero(self):
        r = run_cli()
        assert r.returncode != 0

    def test_help_exits_zero(self):
        r = run_cli("--help")
        assert r.returncode == 0
        assert "usage" in r.stdout
