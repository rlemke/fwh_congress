"""Offline unit tests for the congress domain (no network)."""

from __future__ import annotations

import json

import pytest

from congress._lib import (
    PARTY_COLORS,
    STATE_FIPS,
    _render_html,
    district_key,
)


def test_state_fips_covers_50_states_dc_and_territories():
    abbrs = {v[0] for v in STATE_FIPS.values()}
    assert len(abbrs) == 56  # 50 states + DC + 5 delegate territories
    assert {"CA", "TX", "DC", "PR", "GU"} <= abbrs


@pytest.mark.parametrize(
    ("fips", "cd", "expected"),
    [
        ("06", "12", ("CA", 12, False)),  # numbered district
        ("02", "00", ("AK", 0, False)),  # at-large
        ("11", "98", ("DC", 0, True)),  # non-voting delegate
        ("06", "ZZ", None),  # undefined -> skipped
        ("99", "01", None),  # unknown state fips
    ],
)
def test_district_key(fips, cd, expected):
    assert district_key(fips, cd) == expected


def _feature(label, party, member="Jane Doe", delegate=False):
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
        "properties": {
            "LABEL": label,
            "STATE": "Testland",
            "MEMBER": member,
            "PARTY": party,
            "DELEGATE": delegate,
        },
    }


def test_render_html_contains_parties_counts_and_features():
    fc = {
        "type": "FeatureCollection",
        "features": [
            _feature("TL-01", "Democrat"),
            _feature("TL-02", "Republican"),
            _feature("TL delegate", "Vacant", member="(vacant)", delegate=True),
        ],
    }
    counts = {"Democrat": 1, "Republican": 1, "Independent": 0, "Vacant": 1}
    html = _render_html(fc, counts)
    assert "<!doctype html>" in html
    for color in PARTY_COLORS.values():
        assert color in html
    assert "TL-01" in html and "Jane Doe" in html
    assert "maplibre-gl" in html
    # embedded FeatureCollection is valid JSON
    start = html.index("const FC=") + len("const FC=")
    end = html.index(", COLORS=")
    assert json.loads(html[start:end])["features"][0]["properties"]["LABEL"] == "TL-01"


def test_party_colors_include_vacant_grey():
    assert PARTY_COLORS["Vacant"].lower() == "#9e9e9e"
