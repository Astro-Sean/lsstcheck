"""End-to-end tests: run the lsstcheck CLI against live services.

These hit TNS, LASAIR, and Rubin ObsLocTAP, so they are slow and need
network. Run only them with:  pytest -m integration
Skip them with:              pytest -m "not integration"
"""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LSSTCHECK = ROOT / "lsstcheck"

pytestmark = pytest.mark.integration


def run_cli(*args, timeout=240):
    # Agg keeps --plot's plt.show() from opening a window in tests
    env = dict(os.environ, MPLBACKEND="Agg")
    return subprocess.run(
        [str(LSSTCHECK), *args],
        capture_output=True, text=True, timeout=timeout, env=env,
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
        assert "Detections in LASAIR" in out
        # schedule section always reports something honest
        assert "Rubin Schedule" in out
        assert ("No scheduled observation" in out
                or "Scheduled visits" in out)

    def test_coordinates_resolve_same_object(self):
        r = run_cli("338.196", "-9.447")
        assert r.returncode == 0, r.stderr
        assert "SN2024lwa" in r.stdout
        assert "170587106692825120" in r.stdout

    def test_internal_name_input(self):
        r = run_cli("ZTF26abfwokm")
        assert r.returncode == 0, r.stderr
        assert "SN2024lwa" in r.stdout

    def test_save_flag(self, tmp_path):
        png = tmp_path / "lc.png"
        r = run_cli("--save", "--plot-out", str(png), "2024lwa")
        assert r.returncode == 0, r.stderr
        assert "Lightcurve plot saved" in r.stdout
        assert "Lightcurve table saved" in r.stdout
        assert png.exists() and png.stat().st_size > 0
        csv = tmp_path / "lc.csv"
        assert csv.exists()
        assert csv.read_text().splitlines()[0] == \
            "mjd,utc,band,flux,flux_err,mag,mag_err"

    def test_plot_flag_runs(self):
        # headless: plt.show() is a no-op under Agg, just check rc
        r = run_cli("--plot", "2024lwa")
        assert r.returncode == 0, r.stderr


class TestScheduledTarget:
    """313761042329501776: LSST object with no TNS entry, visits scheduled."""

    def test_dia_object_id(self):
        r = run_cli("313761042329501776")
        assert r.returncode == 0, r.stderr
        out = r.stdout
        assert "313761042329501776" in out
        assert "No TNS entry" in out
        assert "Detections in LASAIR" in out
        # this field is in the current published window
        assert "Scheduled visits" in out or "No scheduled observation" in out

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
        assert "No LSST alerts" in out
        assert "northern edge" in out  # dec>15 footprint warning
        assert "No scheduled observation" in out or "Scheduled visits" in out

    def test_remote_south_coords(self):
        # far south field, likely no TNS object and sparse coverage
        r = run_cli("150.0", "-75.0")
        assert r.returncode == 0, r.stderr
        assert "Rubin Schedule" in r.stdout


class TestLiveTns:
    """Live wis-tns.org checks: --live-tns flag and catalog-miss path."""

    def test_live_flag_marks_row(self):
        r = run_cli("--live-tns", "2024lwa")
        assert r.returncode == 0, r.stderr
        assert "| live" in r.stdout
        # live page reports alternative names with their groups
        assert "ZTF26abfwokm (ZTF)" in r.stdout
        assert "wis-tns.org/object/2024lwa" in r.stdout

    def test_catalog_miss_falls_back_to_live(self):
        # fake name: catalog misses, live 404s, tool reports both
        r = run_cli("AT1999zzz")
        assert r.returncode != 0
        assert "No TNS entry" in r.stdout
        assert "not found on wis-tns.org" in r.stdout


class TestBadInput:
    def test_no_args_exits_nonzero(self):
        r = run_cli()
        assert r.returncode != 0

    def test_help_exits_zero(self):
        r = run_cli("--help")
        assert r.returncode == 0
        assert "usage" in r.stdout
