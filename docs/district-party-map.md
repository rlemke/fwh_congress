# District Party Map

**Namespace(s):** `congress.maps` · `congress.workflows` ·
**FFL:** `src/congress/ffl/congress.ffl` ·
**Handlers:** `src/congress/handlers/congress_handlers.py` ·
**Lib:** `src/congress/_lib.py` (`build_district_party_map`) ·
**Tests:** `tests/test_congress.py`

## Overview

This is the domain's **one and only** capability: a national MapLibre choropleth of
US congressional (House) districts colored by the party of the **sitting
representative**. It answers "which party holds each seat, drawn on a map you can
pan, search, and click." Everything else in the repo — the two data sources, the
FIPS+district join, the HTML renderer, the storage backend — exists to serve this
single facet.

The whole pipeline is one event facet, `congress.maps.BuildDistrictPartyMap`,
wrapped by the `congress.workflows.BuildCongressPartyMap` workflow so it is a
dashboard-runnable entry point. There is no fan-out and no source-adapter split;
the national dataset is small enough (≈436 district polygons + ≈540 roster
entries) to build in one task.

## How it works

Driven by `build_district_party_map(force=False)` in `_lib.py`, five stages:

1. **Fetch shapes** — `download_shapes()` downloads the Census cartographic-boundary
   congressional-districts ZIP (`cb_2024_us_cd119_500k.zip`), extracts the
   `.shp`/`.dbf` pair to a temp dir, and reads it with `pyshp`
   (`shapefile.Reader`), yielding `{state_fips, cd, geometry}` per district. See
   [data-sources](data-sources.md).
2. **Fetch members** — `download_members()` downloads the public-domain
   `legislators-current.json` and builds `(state_abbr, district) -> {name, party}`
   for every sitting House rep (last term, `type == "rep"`). See
   [data-sources](data-sources.md).
3. **Join** — for each district polygon, `district_key(state_fips, cd)` resolves
   `(abbr, district_number, is_delegate)`; the member lookup attaches
   `name`/`party`, folding third parties into `Independent` and marking seats with
   no member `Vacant`. See [party-join](party-join.md).
4. **Assemble GeoJSON** — geometry is simplified (`shapely` `simplify`,
   `SIMPLIFY_DEG = 0.004`, topology-preserving) and each district becomes a Feature
   with `LABEL / STATE / MEMBER / PARTY / DELEGATE` properties.
5. **Render + write** — `_render_html(fc, counts)` builds a self-contained MapLibre
   page; both `districts.geojson` and `index.html` are written to the storage
   backend's `output_root()`. See [rendering](rendering.md).

Data shape: `CD119 shapefile + legislators JSON → joined FeatureCollection →
index.html`.

## Fan-out

**Single-task — no fan-out.** There is no `foreach` anywhere in the FFL; the
workflow calls `BuildDistrictPartyMap` exactly once and yields its counts. The
input is a single national shapefile and a single national roster, both cached
after the first fetch, so per-state parallelism would add coordination overhead for
no wall-clock win. The one facet does download → parse → join → render inline.

## Data & fields

- **Geometry** — Census CD119 shapefile fields: `STATEFP` (state FIPS) and the
  district code field auto-detected as the first `CD*FP` field (e.g. `CD119FP`).
- **Members** — the sitting term is `terms[-1]`; only `type == "rep"` entries with a
  non-`None` `district` are kept. Name is `name.official_full` (falling back to
  `first + last`); party is `terms[-1].party`.
- **Join key** — `(USPS state abbr, district number)`, with `00` = at-large and
  `98` = non-voting delegate both mapping to district `0`. Full mechanics in
  [party-join](party-join.md).

## External libraries / binaries

All **pip**, no binaries:

- **`requests`** — HTTP download of both sources (`_fetch_cached`, 300 s timeout).
- **`pyshp`** (imported as `shapefile`, `>=2.3`) — reads the ESRI shapefile inside
  the Census ZIP.
- **`shapely`** (`>=2.0`) — `simplify` + `mapping`/`shape` for the inline GeoJSON.
- **MapLibre GL JS `4.7.1`** — client-side only, loaded from the unpkg CDN by the
  output HTML (not a pip dep); OpenStreetMap raster basemap tiles.

## Facets & workflows

| Facet / Workflow | Kind | Effect/Cost/Timeout | Purpose |
|---|---|---|---|
| `congress.maps.BuildDistrictPartyMap(force=false) => (html_path, district_count, dem_count, rep_count, vacant_count)` | **event** | `Effect(external)` · `Cost(expensive)` · `Timeout(20 min)` | Join sitting-rep party onto CD119 polygons and render the categorical choropleth. |
| `congress.workflows.BuildCongressPartyMap(force=false) => (status, html_path, district_count, dem_count, rep_count, vacant_count)` | workflow | — | Thin entry-point wrapper: calls the facet, yields `status="completed"` + the counts. |

Only `BuildDistrictPartyMap` needs a handler; `congress_handlers.py` registers it
with `timeout_ms=0` (blocking download+parse, so it relies on the global execution
timeout — `runner_env` in `__init__.py` sets `FW_TASK_EXECUTION_TIMEOUT_MS`
= 20 min, matching the FFL `Timeout`). `force=true` re-fetches both sources;
otherwise they are cache-once.

## Cache / output

- **Cache** — `download_shapes` / `download_members` land under `cache_root()`
  (`cache/congress/cache/` on a remote backend). See
  [storage-and-cache](storage-and-cache.md).
- **Output** — `output_root()` (`cache/congress/output/`) gets `index.html` and
  `districts.geojson`. On the fleet (`FW_STORAGE=s3`) this is MinIO/S3; locally it
  is a plain directory (README default `congress-output/`).

## Gotchas & notes

- **Scope: "voting districts" = House districts, not precincts.** The map is CD119
  seats. Census VTDs (precinct polygons, ~180k) have no single open national party
  source and are explicitly out of scope — disclosed in the map's "About this data"
  modal (see [rendering](rendering.md)).
- **`force` is all-or-nothing.** It re-fetches *both* the shapes ZIP and the roster;
  there is no per-source refresh.
- **Counts are a by-product of the join, not a separate query.** `dem_count` /
  `rep_count` / `vacant_count` come straight from the join loop's `counts` dict — a
  seat folded into `Independent` is not in any of the three returned counts (only
  Dem/Rep/Vacant are surfaced on the workflow return).

## Related specs

- [data-sources](data-sources.md) — the two open, keyless sources and their caching.
- [party-join](party-join.md) — FIPS+district join, at-large/delegate/vacant/third-party rules.
- [rendering](rendering.md) — the MapLibre categorical choropleth HTML.
- [storage-and-cache](storage-and-cache.md) — backend-aware cache/output paths.
