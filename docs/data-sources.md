# Data Sources

**Namespace(s):** `congress.maps` (consumed by `BuildDistrictPartyMap`) ·
**Lib:** `src/congress/_lib.py` (`download_shapes`, `download_members`, `_fetch_cached`) ·
**Tests:** `tests/test_congress.py` (`test_state_fips_covers_50_states_dc_and_territories`)

## Overview

Two **open, keyless** sources feed the map. Both are fetched once and cached; there
is no API key, no token, and no authenticated endpoint — a deliberate design choice
so the domain runs anywhere with plain outbound HTTPS.

1. **District geometry** — US Census cartographic-boundary congressional districts,
   119th Congress, 1:500k simplified.
2. **Members & party** — the public-domain `unitedstates/congress-legislators`
   `legislators-current.json` roster.

## How it works

Both downloads go through `_fetch_cached(url, cache_name, force=, binary=)`:

- Computes the cache path `join(cache_root(), cache_name)`.
- If `not force and exists(path)`, returns the cached path immediately (cache-once).
- Otherwise `requests.get(url, timeout=300)`, `raise_for_status()`, and writes the
  body via `storage.open_write` (binary for the ZIP, text for the JSON).

**`download_shapes(force=)`** — fetches `cb_2024_us_cd119_500k.zip`, `localize()`s
it (pulls it to a local temp file if the cache is remote), then extracts the
`.shp`/`.dbf`/etc. into a `TemporaryDirectory` because `pyshp` needs the file set on
disk. It reads the shapefile with `shapefile.Reader`, auto-detects the district-code
field as the first field starting `CD` and ending `FP` (e.g. `CD119FP`), and emits
`{state_fips, cd, geometry}` per record (`geometry` from `shape.__geo_interface__`).
Raises `RuntimeError` if no `.shp` is found, no `CD*FP` field exists, or the parse
yields zero features.

**`download_members(force=)`** — fetches `legislators-current.json`, walks each
person, takes `terms[-1]` (in `legislators-current` the last term is the sitting
one), keeps only `type == "rep"` with a non-`None` `district`, and builds
`(state_abbr, int(district)) -> {name, party}`. Name is `name.official_full` with a
`first + last` fallback; party is the term's `party`. Raises `RuntimeError` if zero
House members parse.

## Fan-out

**Single-task — no fan-out.** Both are single national files fetched by the one
`BuildDistrictPartyMap` facet. Caching (not parallelism) is what keeps repeat runs
fast.

## Data & fields

| Source | URL (constant) | Format | Keyed fields |
|---|---|---|---|
| CD119 shapes | `SHAPES_URL` = `www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_cd119_500k.zip` | ESRI shapefile in a ZIP | `STATEFP`, `CD*FP` (district code), shape geometry |
| Members | `MEMBERS_URL` = `unitedstates.github.io/congress-legislators/legislators-current.json` | JSON array of people | `terms[-1].{type,state,district,party}`, `name.official_full` |

The `STATE_FIPS` table (56 entries) maps state FIPS → `(USPS abbr, name)` and covers
the 50 states + DC + the five delegate territories (AS, GU, MP, PR, VI) that appear
in the CD file — asserted by `test_state_fips_covers_50_states_dc_and_territories`.

## External libraries / binaries

- **`requests`** (pip) — both fetches.
- **`pyshp`** (pip, imported `shapefile`) — reads the shapefile; requires the file
  on local disk, hence the `localize()` + `TemporaryDirectory` extract.
- Python stdlib `zipfile` / `tempfile` / `json` for unpacking and parsing.
- No binary dependencies; no osmium / GDAL.

## Facets & workflows

No facet of its own — these are library functions called inline by
`BuildDistrictPartyMap` (see [district-party-map](district-party-map.md)). They are
exercised directly by the offline tests via mock data, not through a facet.

## Cache / output

Both cached files live under `cache_root()`:

- `cb_2024_us_cd119_500k.zip`
- `legislators-current.json`

On the fleet this is `s3://…/cache/congress/cache/`; locally a `congress-cache/`
directory (see [storage-and-cache](storage-and-cache.md)). These sources are inputs
only — the rendered artifacts go to `output_root()`.

## Gotchas & notes

- **Cache-once, `force`-to-refresh.** A stale roster (e.g. after a special election)
  will persist until a run with `force=true`; there is no TTL.
- **`terms[-1]` assumes chronological terms.** The sitting term is taken as the last
  element; `legislators-current.json` is ordered that way, but a reordered roster
  would mis-key members.
- **Field auto-detection is intentional.** Hardcoding `CD119FP` would break when
  Census bumps the boundary vintage; the `CD*FP` prefix/suffix match survives a
  vintage change as long as the URL is updated.
- **Delegates need the delegate territories in `STATE_FIPS`.** DC/PR/GU/etc. FIPS
  must be present or their district polygons are silently skipped by `district_key`.

## Related specs

- [district-party-map](district-party-map.md) — the facet that consumes both sources.
- [party-join](party-join.md) — how the two are joined on FIPS + district.
- [storage-and-cache](storage-and-cache.md) — where the cached files land.
