# Rendering

**Namespace(s):** `congress.maps` (inside `build_district_party_map`) ·
**Lib:** `src/congress/_lib.py` (`_render_html`, `_attribution`) ·
**Tests:** `tests/test_congress.py` (`test_render_html_contains_parties_counts_and_features`)

## Overview

The render step turns the joined `FeatureCollection` into a **self-contained,
single-file MapLibre GL choropleth** — one `index.html` with the GeoJSON inlined,
no server or tile pipeline required. It is the artifact a user actually opens: a
pan/zoom US map, categorical party fill, a legend with live seat counts, a
district/state/member search box, member popups, and an "About this data" modal.

## How it works

`_render_html(fc, counts)` string-formats one HTML document:

1. **Inlined data** — the `FeatureCollection` (`FC`), `PARTY_COLORS` (`COLORS`), and
   the seat `counts` (`COUNTS`) are JSON-dumped into `<script>` consts. No external
   data fetch at view time.
2. **Basemap** — a MapLibre style v8 with a single keyless OpenStreetMap raster
   source (`tile.openstreetmap.org`; CARTO was dropped after it began watermarking
   unauthenticated tiles in Aug 2026), centered `[-96, 38]`, zoom
   `3.4`, plus a `NavigationControl`.
3. **Fill layer** — `fill-color` is a MapLibre `['match', ['get','PARTY'], …]`
   expression mapping `Democrat`/`Republican`/`Independent` to their colors with the
   `Vacant` grey as the fallback. `fill-opacity` is `['case', ['get','DELEGATE'],
   0.45, 0.75]` — delegate seats render fainter. A white `line` layer outlines
   districts.
4. **Popups** — click a district → a popup with `LABEL · STATE`, `MEMBER`, the
   `PARTY` in its color, and a "non-voting delegate seat" note when `DELEGATE`.
5. **Legend** — bottom-right panel, one row per party with a color swatch and the
   live count (`Democrat (218)` etc.).
6. **Search** — a top-center box filters features client-side by
   `LABEL + STATE + MEMBER` substring (min 2 chars, top 12), and `fitBounds` to the
   picked district using an inline bbox walk over the geometry.
7. **About modal** — an ℹ️ button opens the `desc` text (scope disclosure); the same
   text also sits in the top-left control panel.
8. **Attribution** — `_attribution()` appends a fixed-position credit box linking the
   generating workflow (`congress.workflows.BuildCongressPartyMap`), the FFL file
   (`FFL_URL`), and the source repo, with a UTC generation timestamp.

## Fan-out

**Single-task — no fan-out.** One HTML document is rendered per run, in the same
facet as the join.

## Data & fields

Reads the per-feature properties produced by the join
([party-join](party-join.md)): `LABEL`, `STATE`, `MEMBER`, `PARTY`, `DELEGATE`.
`PARTY` drives fill color, `DELEGATE` drives opacity and the popup note, the other
three feed popups + search. The legend reads the `counts` dict.

## External libraries / binaries

- **MapLibre GL JS `4.7.1`** — loaded from the unpkg CDN by the page (JS + CSS);
  **client-side only**, not a pip dependency. The map will not render offline.
- **OpenStreetMap raster tiles** — the basemap, fetched by the browser at view time.
- No server-side rendering libraries: the HTML is built with plain Python
  f-strings + `json.dumps`; only the inline GeoJSON geometry came from `shapely`
  upstream in the join.

## Facets & workflows

No facet of its own — `_render_html` / `_attribution` are called by
`build_district_party_map` behind `congress.maps.BuildDistrictPartyMap`
(see [district-party-map](district-party-map.md)). The renderer is unit-tested
directly (`test_render_html_contains_parties_counts_and_features` asserts the
doctype, every party color, a feature label + member, the `maplibre-gl` include, and
that the embedded `FC` is valid JSON).

## Cache / output

- **`index.html`** and **`districts.geojson`** are written to `output_root()`
  (`cache/congress/output/` on a remote backend; `congress-output/` locally) —
  see [storage-and-cache](storage-and-cache.md).
- `html_path` (the `index.html` path) is the facet's primary return value.
- On the fleet these land in MinIO/S3; the HTML is self-contained so it can be served
  or downloaded as-is.

## Gotchas & notes

- **Needs internet at *view* time.** MapLibre JS/CSS and the OpenStreetMap tiles are CDN
  links; an air-gapped viewer sees a blank map even though the GeoJSON is inlined.
- **Scope disclosure is baked into `desc`.** The "About this data" text states that
  "voting districts" = House districts and that precinct-level (VTD) results are out
  of scope — keep it in sync if scope ever changes.
- **Delegate opacity, not a separate layer.** DC + territory delegate seats are the
  same fill layer at 0.45 opacity; there is no toggle to hide them.
- **All f-string braces are doubled.** `_render_html` is one big Python f-string, so
  every literal `{`/`}` in the CSS/JS is escaped `{{`/`}}` — a subtle edit hazard.

## Related specs

- [party-join](party-join.md) — produces the `PARTY`/`DELEGATE` properties the renderer keys on.
- [district-party-map](district-party-map.md) — the facet that calls the renderer.
- [storage-and-cache](storage-and-cache.md) — where the HTML + GeoJSON are written.
