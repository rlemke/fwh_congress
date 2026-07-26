<!-- SPEC TEMPLATE — every docs/<feature>.md follows this shape so the set reads
consistently. Delete this comment in real specs. Keep sections in this order;
omit a section only if it genuinely does not apply (say so in one line rather
than dropping the heading silently). Ground every claim in the actual FFL
docstrings / handler code / lib — do not invent behaviour. -->

# <Feature Name>

**Namespace(s):** `congress.<ns>` · **FFL:** `src/congress/ffl/congress.ffl` ·
**Handlers:** `src/congress/handlers/congress_handlers.py` ·
**Lib:** `src/congress/_lib.py` · **Storage:** `src/congress/storage.py` (if relevant)

## Overview
One or two paragraphs: what this feature is for, the request it answers, and where
it sits in the pipeline (fetch source → parse → join → render).

## How it works
The algorithm / data flow, step by step. Name the concrete functions and the shape
of the data at each stage (CD119 shapefile → features → joined FeatureCollection →
HTML map, etc.).

## Fan-out
Does it fan out across the fleet? If yes: what is the fan-out unit and which facet
drives it (a `foreach` over what list). If it is single-task, say "single-task — no
fan-out" and why (small national dataset, cached-once downloads, atomic render).

## Data & fields
What data it reads and which fields it keys on — be specific (state FIPS,
`CD*FP` district code, `admin_level`, USPS abbreviation, the legislators
`terms[-1].type == "rep"` sitting-term rule, party string). Name the parse/join
mechanism (pyshp reader, JSON roster walk, the `district_key` FIPS+district join).
If the feature does no data selection, say so.

## External libraries / binaries
Every non-stdlib dependency this feature relies on and what for — e.g. `requests`
(HTTP fetch), `pyshp` (`shapefile` — ESRI shapefile reader), `shapely` (geometry
simplify / GeoJSON mapping), MapLibre GL JS (client-side, CDN). Distinguish a
**binary** dependency from a **pip** one; note CDN-loaded browser libraries.

## Facets & workflows
The key event facets and workflows, with signatures and a one-line purpose taken
from the FFL docstrings. Mark event facets (need a handler) vs pure facets, and
note `Effect`/`Cost`/`Timeout` mixins where present.

## Cache / output
The cache namespace under the storage backend (`cache/congress/cache/` +
`cache/congress/output/`) and the cache type, plus the output artifact(s) and
format (GeoJSON / HTML map / ZIP / JSON roster). Note whether outputs go to local
disk or MinIO/S3, and the env overrides (`FW_CONGRESS_CACHE_DIR`,
`FW_CONGRESS_OUTPUT_DIR`, `FW_DATA_ROOT`).

## Gotchas & notes
Known pitfalls, rate limits, sensitivity/scope caveats, or non-obvious constraints
(worth capturing anything a future maintainer would trip on).

## Related specs
Links to the specs this feature composes with or depends on.
