"""Offline unit tests for lsstcheck. No network access required."""

import io
import json
import zipfile
from unittest import mock

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# input parsing
# ---------------------------------------------------------------------------

class TestParseTarget:
    def test_decimal_coords_two_tokens(self, lsc):
        t = lsc.parse_target(["338.196", "-9.447"])
        assert t["kind"] == "coords"
        assert t["ra"] == pytest.approx(338.196)
        assert t["dec"] == pytest.approx(-9.447)
        assert t["radius"] is None

    def test_decimal_coords_with_radius(self, lsc):
        t = lsc.parse_target(["338.196,-9.447,60"])
        assert t["kind"] == "coords"
        assert t["radius"] == pytest.approx(60.0)

    def test_coords_radius_three_tokens(self, lsc):
        t = lsc.parse_target(["10", "-20", "30"])
        assert t["kind"] == "coords"
        assert t["radius"] == pytest.approx(30.0)

    def test_sexagesimal(self, lsc):
        t = lsc.parse_target(["13:32:47.04", "-09:26:49.0"])
        assert t["kind"] == "coords"
        assert t["ra"] == pytest.approx(203.196, abs=1e-3)
        assert t["dec"] == pytest.approx(-9.4469, abs=1e-3)

    def test_tns_name(self, lsc):
        t = lsc.parse_target(["2024lwa"])
        assert t["kind"] == "name"
        assert t["raw"] == "2024lwa"

    def test_prefixed_name(self, lsc):
        t = lsc.parse_target(["AT2024lwa"])
        assert t["kind"] == "name"
        assert t["raw"] == "AT2024lwa"

    def test_survey_name(self, lsc):
        t = lsc.parse_target(["ZTF26abfwokm"])
        assert t["kind"] == "name"

    def test_dia_object_id(self, lsc):
        t = lsc.parse_target(["170587106692825120"])
        assert t["kind"] == "dia_id"
        assert t["dia_id"] == "170587106692825120"

    def test_lsst_name(self, lsc):
        t = lsc.parse_target(["LSST-AP-DO-170587106692825120"])
        assert t["kind"] == "lsst_name"
        assert t["dia_id"] == "170587106692825120"

    def test_short_number_is_name_not_id(self, lsc):
        t = lsc.parse_target(["2024lwa"])
        assert t["kind"] == "name"

    def test_garbage(self, lsc):
        # not coords, not a name pattern - still classified as a name
        # lookup miss rather than a crash
        t = lsc.parse_target(["!!!"])
        assert t["kind"] == "name"


class TestHelpers:
    def test_tns_key(self, lsc):
        assert lsc.tns_key("2024lwa") == "2024lwa"
        assert lsc.tns_key("AT2024lwa") == "2024lwa"
        assert lsc.tns_key("SN 2024lwa") == "2024lwa"
        assert lsc.tns_key("ZTF26abfwokm") is None

    def test_internal_names_list(self, lsc):
        assert lsc.internal_names_list(None) == []
        assert lsc.internal_names_list("") == []
        assert lsc.internal_names_list("a, b ,c") == ["a", "b", "c"]

    def test_coord_value_decimal(self, lsc):
        assert lsc.coord_value("12.5", is_ra=True) == 12.5

    def test_coord_value_sexa_ra(self, lsc):
        assert lsc.coord_value("1h30m", is_ra=True) == pytest.approx(22.5)


# ---------------------------------------------------------------------------
# math and formatting
# ---------------------------------------------------------------------------

class TestMath:
    def test_ang_sep_zero(self, lsc):
        assert lsc.ang_sep_deg(10.0, -20.0, 10.0, -20.0) == pytest.approx(0.0)

    def test_ang_sep_one_degree(self, lsc):
        # 1 deg in RA at the equator
        assert lsc.ang_sep_deg(0.0, 0.0, 1.0, 0.0) == pytest.approx(1.0)

    def test_ang_sep_poles(self, lsc):
        assert lsc.ang_sep_deg(0.0, 89.0, 180.0, 89.0) == pytest.approx(2.0,
                                                                   abs=0.01)

    def test_ang_sep_antipodal(self, lsc):
        assert lsc.ang_sep_deg(0.0, 0.0, 180.0, 0.0) == pytest.approx(180.0)

    def test_ang_sep_array(self, lsc):
        sep = lsc.ang_sep_deg(10.0, -20.0, [10.0, 11.0], [-20.0, -20.0])
        assert sep[0] == pytest.approx(0.0)
        assert sep[1] > 0.9

    def test_band_name(self, lsc):
        # em ranges in meters around each band's effective wavelength
        assert lsc.band_name(0.3e-6, 0.4e-6) == "u"
        assert lsc.band_name(0.4e-6, 0.55e-6) == "g"
        assert lsc.band_name(0.55e-6, 0.7e-6) == "r"
        assert lsc.band_name(0.7e-6, 0.85e-6) == "i"
        assert lsc.band_name(0.8e-6, 0.95e-6) == "z"
        assert lsc.band_name(0.95e-6, 1.1e-6) == "y"

    def test_fmt_mjd_iso(self, lsc):
        # MJD 60000.0 = 2023-02-25 00:00 UTC
        assert lsc.fmt_mjd_iso(60000.0) == "2023-02-25 00:00 UTC"

    def test_iso_date(self, lsc):
        assert lsc.iso_date(60000.0) == "2023-02-25"


class TestRaBoxRanges:
    def test_no_wrap(self, lsc):
        assert lsc.ra_box_ranges(100.0, 2.0) == [(98.0, 102.0)]

    def test_wrap_low(self, lsc):
        assert lsc.ra_box_ranges(1.0, 2.0) == [(0.0, 3.0), (359.0, 360.0)]

    def test_wrap_high(self, lsc):
        assert lsc.ra_box_ranges(359.0, 2.0) == [(357.0, 360.0),
                                               (0.0, 1.0)]


# ---------------------------------------------------------------------------
# schedule logic
# ---------------------------------------------------------------------------

def _visit(ra, dec, t_min, band="r", status="Scheduled", fov=3.5,
           priority=0, target="test"):
    em = {"u": (0.3e-6, 0.4e-6), "g": (0.4e-6, 0.55e-6),
          "r": (0.55e-6, 0.7e-6), "i": (0.7e-6, 0.85e-6),
          "z": (0.8e-6, 0.95e-6), "y": (0.95e-6, 1.1e-6)}[band]
    return {
        "s_ra": ra, "s_dec": dec, "s_fov": fov,
        "t_min": t_min, "t_max": t_min + 0.001,
        "em_min": em[0], "em_max": em[1],
        "priority": priority, "execution_status": status,
        "target_name": target,
    }


class TestUpcomingVisits:
    NOW = 60000.0

    def test_hit_within_fov(self, lsc):
        visits = [_visit(10.5, -20.0, self.NOW + 0.5)]
        hits = lsc.upcoming_visits(visits, 10.0, -20.0, self.NOW)
        assert len(hits) == 1
        assert hits[0][2]["target_name"] == "test"

    def test_miss_outside_fov(self, lsc):
        # ~5 deg away, outside the 1.75 deg radius
        visits = [_visit(15.0, -20.0, self.NOW + 0.5)]
        assert lsc.upcoming_visits(visits, 10.0, -20.0, self.NOW) == []

    def test_aborted_skipped(self, lsc):
        visits = [_visit(10.5, -20.0, self.NOW + 0.5, status="Aborted")]
        assert lsc.upcoming_visits(visits, 10.0, -20.0, self.NOW) == []

    def test_past_visit_skipped(self, lsc):
        visits = [_visit(10.5, -20.0, self.NOW - 0.1)]
        assert lsc.upcoming_visits(visits, 10.0, -20.0, self.NOW) == []

    def test_dedupes_close_visits(self, lsc):
        # three pointings 5 min apart -> one row
        visits = [_visit(10.5, -20.0, self.NOW + 0.5 + i * 5 / 1440.0)
                  for i in range(3)]
        hits = lsc.upcoming_visits(visits, 10.0, -20.0, self.NOW)
        assert len(hits) == 1

    def test_separate_epochs_kept(self, lsc):
        visits = [_visit(10.5, -20.0, self.NOW + 0.5),
                  _visit(10.5, -20.0, self.NOW + 0.5 + 2.0)]
        hits = lsc.upcoming_visits(visits, 10.0, -20.0, self.NOW)
        assert len(hits) == 2

    def test_sorted_by_time(self, lsc):
        visits = [_visit(10.5, -20.0, self.NOW + 1.0),
                  _visit(10.5, -20.0, self.NOW + 0.5)]
        hits = lsc.upcoming_visits(visits, 10.0, -20.0, self.NOW)
        assert hits[0][0] < hits[1][0]


class TestCoveredNights:
    def _exp(self, ra, dec, mjd, band="r"):
        return {"s_ra": ra, "s_dec": dec, "obs_start_mjd": mjd,
                "band": band}

    def test_groups_by_night(self, lsc):
        rows = [self._exp(10.5, -20.0, 60000.1),
                self._exp(10.5, -20.0, 60000.3),
                self._exp(10.5, -20.0, 60001.1)]
        nights = lsc.covered_nights(rows, 10.0, -20.0)
        assert len(nights) == 2

    def test_outside_fov_ignored(self, lsc):
        rows = [self._exp(20.0, -20.0, 60000.1)]
        assert lsc.covered_nights(rows, 10.0, -20.0) == {}

    def test_missing_fields_skipped(self, lsc):
        rows = [{"s_ra": 10.5}, {"obs_start_mjd": 60000.1}]
        assert lsc.covered_nights(rows, 10.0, -20.0) == {}


class TestScheduleUrls:
    def test_viewer_url_normal(self, lsc):
        url = lsc.schedule_viewer_url(100.0, -30.0, 48)
        assert url.startswith(lsc.SCHEDULE_VIEWER + "?")
        assert "time=48" in url
        assert "predicate=" in url
        # box should be ra 98-102, dec -32 to -28
        assert "s_ra%3E98.00" in url
        assert "s_dec%3E-32.00" in url

    def test_viewer_url_wrap_ra(self, lsc):
        url = lsc.schedule_viewer_url(359.5, -30.0, 48)
        assert "OR" in url  # wrap needs the OR clause
        assert "357.50" in url and "1.50" in url

    def test_viewer_url_dec_clipped(self, lsc):
        url = lsc.schedule_viewer_url(100.0, 89.5, 48)
        assert "s_dec%3C90.00" in url

    def test_skymap_url(self, lsc):
        url = lsc.skymap_url(48)
        assert url.endswith("/skymap?start=now&time=48")


class TestScheduleHorizon:
    def test_horizon_hours(self, lsc):
        visits = [{"t_max": 100.5}, {"t_max": 101.0}, {"bad": 1}]
        assert lsc.schedule_horizon_h(visits, 100.0) == pytest.approx(24.0)

    def test_horizon_empty(self, lsc):
        assert lsc.schedule_horizon_h([], 100.0) is None
        assert lsc.schedule_horizon_h([{"x": 1}], 100.0) is None


# ---------------------------------------------------------------------------
# name helpers
# ---------------------------------------------------------------------------

class TestNameHelpers:
    def _row(self, **kw):
        base = {"prefix": "SN", "name": "2024lwa", "objid": 1,
                "internal_names": ""}
        base.update(kw)
        return base

    def test_tns_display_name(self, lsc):
        assert lsc.tns_display_name(self._row()) == "SN2024lwa"
        assert lsc.tns_display_name(
            self._row(prefix="", name="")) == "1"

    def test_lsst_names_from_tns(self, lsc):
        rows = [self._row(internal_names="PS24emd, LSST-AP-DO-123, "
                                            "LSST-AP-DO-123, other")]
        names = lsc.lsst_names_from_tns(rows)
        assert names == ["LSST-AP-DO-123"]

    def test_lsst_names_ignores_non_lsst(self, lsc):
        rows = [self._row(internal_names="ZTF26abc, GOTO26x")]
        assert lsc.lsst_names_from_tns(rows) == []


# ---------------------------------------------------------------------------
# TNS catalog (mocked download)
# ---------------------------------------------------------------------------

CSV_HEADER = (
    "objid,name_prefix,name,ra,declination,redshift,type,"
    "discoverydate,discoverymag,discmagfilter,reporting_group,"
    "source_group,internal_names"
)


def _tns_zip_bytes():
    """Build a minimal TNS dump: timestamp line, header, two rows."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        rows = [
            "2026-11-09 00:00:00",
            CSV_HEADER,
            '1,SN,2024lwa,338.196,-9.447,0.056,SN II,2024-06-16,17.5,r,'
            'PS,internal,"PS24emd,LSST-AP-DO-170587106692825120"',
            "2,,2020abc,10.0,-20.0,,CV,2020-01-01,18.0,g,ZTF,internal,",
        ]
        zf.writestr("tns_public_objects.csv",
                    "\n".join(rows).encode())
    return buf.getvalue()


class _FakeResp:
    def __init__(self, content):
        self._content = content

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, n):
        yield self._content


class TestTnsCatalog:
    @pytest.fixture
    def catalog(self, lsc, tmp_path, monkeypatch):
        monkeypatch.setattr(lsc, "TNS_DB", tmp_path / "tns.db")
        monkeypatch.setattr(lsc, "CACHE_DIR", tmp_path)
        monkeypatch.setattr(lsc.requests, "get",
                            lambda *a, **k: _FakeResp(_tns_zip_bytes()))
        return lsc.TnsCatalog(refresh=True)

    def test_csv_date(self, catalog):
        assert catalog.csv_date == "2026-11-09"

    def test_by_name(self, catalog):
        rows = catalog.by_name("2024lwa")
        assert len(rows) == 1
        assert rows[0]["type"] == "SN II"
        assert rows[0]["redshift"] == pytest.approx(0.056)

    def test_by_name_case_insensitive(self, catalog):
        # index is on lower(name); lookup uses the lowered key
        assert catalog.by_name("2024LWA") == []
        assert catalog.by_name("2024lwa")

    def test_cone_finds_target(self, catalog):
        rows = catalog.cone(338.196, -9.447, 5.0)
        assert len(rows) == 1
        assert rows[0]["_sep"] < 1.0

    def test_cone_misses_far(self, catalog):
        assert catalog.cone(0.0, 0.0, 5.0) == []

    def test_find_name_internal(self, catalog):
        rows = catalog.find_name("LSST-AP-DO-170587106692825120")
        assert len(rows) == 1
        assert rows[0]["name"] == "2024lwa"

    def test_by_dia_id(self, catalog):
        rows = catalog.by_dia_id("170587106692825120")
        assert len(rows) == 1

    def test_cached_second_open(self, catalog, lsc, tmp_path,
                                monkeypatch):
        # second catalog on same db must not re-download
        monkeypatch.setattr(lsc.requests, "get",
                            mock.Mock(side_effect=AssertionError("net")))
        cat2 = lsc.TnsCatalog(refresh=False)
        assert cat2.csv_date == "2026-11-09"


# ---------------------------------------------------------------------------
# live TNS lookup (mocked session)
# ---------------------------------------------------------------------------

TNS_OBJ_HTML = """
<html><body>
<h1 class="title" id="page-title"> SN 2024lwa </h1>
<div class="field field-radec"><span class="name">RA/DEC</span><b>
<div class="value">22:32:47 -09:26:49</b></div>
<div class="alter-value">338.1960739 -9.4470094</div></div>
<div class="field field-type"><span class="name">Type</span>
<div class="value"><b>SN II</b></div></div>
<div class="field field-redshift"><span class="name">Redshift</span>
<div class="value"><b>0.05689</b></div></div>
<div class="field field-reporting_group_name"><span class="name">RG</span>
<div class="value"><b>Pan-STARRS</b></div></div>
<div class="field field-source_group_name"><span class="name">SG</span>
<div class="value"><b>Pan-STARRS</b></div></div>
<div class="field field-discoverydate"><span class="name">DD</span>
<div class="value"><b>2024-06-16 13:23:40</b></div></div>
<div class="field field-discoverymag"><span class="name">DM</span>
<div class="value"><b>21.24</b></div></div>
<div class="field field-filter_name"><span class="name">F</span>
<div class="value"><b>w-P1</b></div></div>
<table><tbody>
<tr><td class="cell-hostName"></td><td class="cell-internal_name">
ZTF26abfwokm</td> <td class="cell-groups">ZTF</td></tr>
<tr><td class="cell-hostName"></td><td class="cell-internal_name">
LSST-AP-DO-170587106692825120</td> <td class="cell-groups">Rubin</td></tr>
<tr><td class="cell-hostName"></td><td class="cell-internal_name">
PS24emd</td> <td class="cell-groups">Pan-STARRS</td></tr>
<tr><td class="cell-hostName"></td><td class="cell-internal_name">
LSST-AP-DO-170587106692825120</td> <td class="cell-groups">Rubin</td></tr>
</tbody></table>
</body></html>
"""


class _Resp:
    def __init__(self, status, text=""):
        self.status_code = status
        self.text = text


class TestTnsLive:
    def _web(self, lsc, resp):
        web = lsc.TnsLive()
        web.s = mock.Mock()
        web.s.get.return_value = resp
        return web

    def test_parse_full(self, lsc):
        web = self._web(lsc, _Resp(200))
        row = web._parse("2024lwa", TNS_OBJ_HTML)
        assert row["_live"] is True
        assert row["prefix"] + row["name"] == "SN2024lwa"
        assert row["type"] == "SN II"
        assert row["redshift"] == pytest.approx(0.05689)
        assert row["ra"] == pytest.approx(338.1960739)
        assert row["dec"] == pytest.approx(-9.4470094)
        assert row["reporting_group"] == "Pan-STARRS"
        assert row["discoverymag"] == pytest.approx(21.24)
        assert row["discmagfilter"] == "w-P1"
        # duplicate internal name collapsed, groups attached
        assert row["internal_names"].count("LSST-AP-DO") == 1
        assert "ZTF26abfwokm (ZTF)" in row["_live_names"]
        assert "PS24emd (Pan-STARRS)" in row["_live_names"]

    def test_parse_missing_fields(self, lsc):
        web = self._web(lsc, _Resp(200))
        row = web._parse("x", "<html>nothing</html>")
        assert row["ra"] is None and row["type"] is None
        assert row["internal_names"] == ""
        assert row["_live_names"] == []

    def test_lookup_200(self, lsc):
        web = self._web(lsc, _Resp(200, TNS_OBJ_HTML))
        row = web.lookup("2024lwa")
        assert row is not None and row["name"] == "2024lwa"

    def test_lookup_404(self, lsc):
        web = self._web(lsc, _Resp(404))
        assert web.lookup("nope") is None

    def test_lookup_redirect_rejected(self, lsc):
        # unknown numeric slugs 302 to the homepage, which is a 200
        # without an object title once redirects are not followed
        web = self._web(lsc, _Resp(302))
        assert web.lookup("123") is None

    def test_lookup_soft404_rejected(self, lsc):
        web = self._web(lsc, _Resp(200, "<html>homepage</html>"))
        assert web.lookup("123") is None

    def test_lookup_network_error(self, lsc):
        import requests as rq
        web = lsc.TnsLive()
        web.s = mock.Mock()
        web.s.get.side_effect = rq.ConnectionError("down")
        assert web.lookup("2024lwa") is None


class TestLiveSlugs:
    def test_tns_name(self, lsc):
        assert lsc.live_tns_slugs("AT2024lwa", []) == [
            "2024lwa", "at2024lwa"]

    def test_catalog_row_name_first(self, lsc):
        rows = [{"name": "2024lwa"}]
        assert lsc.live_tns_slugs("ZTF26abfwokm", rows) == [
            "2024lwa", "ztf26abfwokm"]

    def test_sanitizes_garbage(self, lsc):
        assert lsc.live_tns_slugs("!!!", []) == []

    def test_dedupes(self, lsc):
        rows = [{"name": "2024lwa"}]
        assert lsc.live_tns_slugs("2024lwa", rows) == ["2024lwa"]


# ---------------------------------------------------------------------------
# LASAIR web parsing (fixtures, no network)
# ---------------------------------------------------------------------------

SEARCH_HTML = """
<html><body><table><tbody>
<tr><td><a href="/objects/12345/">x</a></td><td>338.19</td>
<td>-9.44</td><td>10.4</td></tr>
<tr><td><a href="/objects/67890/">y</a></td><td>10.0</td>
<td>-20.0</td><td>0.5</td></tr>
<tr><td>no link here</td><td>1</td><td>2</td><td>3</td></tr>
</tbody></table></body></html>
"""

OBJECT_HTML = """
<html><body>
<a href="/search/?lon=338.196073d&lat=-9.447009d">map</a>
<table><tr><td>Detection Count</td><td>9</td></tr></table>
<table id="exportLightcurve">
<thead><tr><th>MJD</th><th>UTC</th><th>band</th>
<th>target diff flux</th></tr></thead>
<tbody>
<tr><td>61343.025657</td><td>2026-10-30 00:36:56</td><td>r</td>
<td>-4498 &plusmn; 210</td><td>0.67</td></tr>
<tr><td>61217.398292</td><td>2026-06-26 09:33:32</td><td>i</td>
<td>6782 &plusmn; 233</td><td>0.91</td></tr>
<tr><td>not-a-row</td></tr>
</tbody></table>
</body></html>
"""


class TestLasairParse:
    def test_search_parse(self, lsc):
        objs = lsc.LasairWeb._parse(SEARCH_HTML)
        assert [o["id"] for o in objs] == ["12345", "67890"]
        assert objs[0]["ra"] == pytest.approx(338.19)
        assert objs[0]["dec"] == pytest.approx(-9.44)
        assert objs[0]["sep"] == pytest.approx(10.4)

    def test_search_parse_empty(self, lsc):
        assert lsc.LasairWeb._parse("<html>no table</html>") == []

    def test_object_page(self, lsc):
        web = lsc.LasairWeb()
        fake = mock.Mock()
        fake.status_code = 200
        fake.text = OBJECT_HTML
        web.s = mock.Mock()
        web.s.get.return_value = fake
        coords, ndet, phot = web.object_page("12345")
        assert coords == (338.196073, -9.447009)
        assert ndet == 9
        assert len(phot) == 2
        assert phot[0]["band"] == "r"
        assert phot[0]["mjd"] == pytest.approx(61343.025657)
        assert phot[0]["flux"] == pytest.approx(-4498.0)
        assert phot[0]["flux_err"] == pytest.approx(210.0)
        assert phot[1]["band"] == "i"
        assert phot[1]["flux"] == pytest.approx(6782.0)

    def test_object_page_404(self, lsc):
        web = lsc.LasairWeb()
        fake = mock.Mock()
        fake.status_code = 404
        web.s = mock.Mock()
        web.s.get.return_value = fake
        assert web.object_page("999") is None

    def test_photometry_no_table(self, lsc):
        assert lsc.LasairWeb._photometry("<html>none</html>") == []


class TestLightcurve:
    PHOT = [
        {"mjd": 61343.0, "utc": "2026-10-30", "band": "r",
         "flux": 100.0, "flux_err": 10.0},
        {"mjd": 61344.0, "utc": "2026-10-31", "band": "i",
         "flux": -50.0, "flux_err": 12.0},
        {"mjd": 61345.0, "utc": "2026-11-01", "band": "r",
         "flux": 300.0, "flux_err": 15.0},
    ]

    def test_lightcurve_fig(self, lsc, tmp_path):
        fig = lsc.lightcurve_fig(self.PHOT, "test")
        out = tmp_path / "lc.png"
        fig.savefig(out, dpi=100)
        assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

    def test_write_csv(self, lsc, tmp_path):
        out = tmp_path / "lc.csv"
        lsc.write_lightcurve_csv(str(out), self.PHOT)
        lines = out.read_text().strip().splitlines()
        assert lines[0] == "mjd,utc,band,flux,flux_err"
        assert len(lines) == 4
        assert lines[1].startswith("61343.0,2026-10-30,r,100.0")


# ---------------------------------------------------------------------------
# network wrappers (mocked requests)
# ---------------------------------------------------------------------------

class TestScheduleVisits:
    def test_params_and_parse(self, lsc):
        payload = [{"s_ra": 1.0, "t_min": 2.0}]
        fake = mock.Mock()
        fake.raise_for_status = lambda: None
        fake.json = lambda: payload
        with mock.patch.object(lsc.requests, "get",
                               return_value=fake) as get:
            out = lsc.schedule_visits(48)
        assert out == payload
        params = get.call_args.kwargs["params"]
        assert params["time"] == 48
        assert "s_ra" in params["columns"]


class TestExposureRows:
    def test_ok_flag_and_rows(self, lsc):
        fake = mock.Mock()
        fake.raise_for_status = lambda: None
        fake.json = lambda: [{"obs_start_mjd": 59999.0,
                              "s_ra": 10.0, "s_dec": -20.0}]
        with mock.patch.object(lsc.requests, "get",
                               return_value=fake) as get:
            rows, ok = lsc.exposure_rows(10.0, -20.0, days=30)
        assert ok is True
        assert len(rows) == 1
        pred = get.call_args.kwargs["params"]["predicate"]
        assert "obs_start_mjd" in pred

    def test_failure_flag(self, lsc):
        import requests as rq
        with mock.patch.object(lsc.requests, "get",
                               side_effect=rq.ConnectionError("down")):
            rows, ok = lsc.exposure_rows(10.0, -20.0, days=30)
        assert ok is False
        assert rows == []

    def test_polar_dec_no_ranges(self, lsc):
        rows, ok = lsc.exposure_rows(10.0, 89.9, days=30)
        assert rows == [] and ok is True
