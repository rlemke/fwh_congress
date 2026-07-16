"""Event facet handler for the congress domain — thin layer over ``_lib``."""

from __future__ import annotations

import os
from typing import Any

from .._lib import build_district_party_map

MAPS = "congress.maps"


def handle_build_district_party_map(params: dict[str, Any]) -> dict[str, Any]:
    """Join sitting-rep party onto CD119 district polygons + render the map."""
    step_log = params.get("_step_log")
    try:
        res = build_district_party_map(force=bool(params.get("force")))
        if step_log:
            step_log(
                f"BuildDistrictPartyMap: {res.district_count} districts "
                f"(D {res.dem_count} / R {res.rep_count} / vacant {res.vacant_count}) "
                f"-> {res.html_path}",
                level="success",
            )
        return {
            "html_path": res.html_path,
            "district_count": res.district_count,
            "dem_count": res.dem_count,
            "rep_count": res.rep_count,
            "vacant_count": res.vacant_count,
        }
    except Exception as exc:
        if step_log:
            step_log(f"BuildDistrictPartyMap: {exc}", level="error")
        raise


_DISPATCH: dict[str, Any] = {
    f"{MAPS}.BuildDistrictPartyMap": handle_build_district_party_map,
}


def handle(payload: dict) -> dict:
    return _DISPATCH[payload["_facet_name"]](payload)


def register_handlers(runner) -> None:
    for facet_name in _DISPATCH:
        runner.register_handler(
            facet_name=facet_name,
            module_uri=f"file://{os.path.abspath(__file__)}",
            entrypoint="handle",
            timeout_ms=0,  # blocking download+parse (cached after first run)
        )


def register_poller(poller) -> None:
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
