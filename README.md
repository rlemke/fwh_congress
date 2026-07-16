# fwh_congress

Facetwork domain: **US congressional (voting) districts colored by the party of
the sitting House representative** — a MapLibre categorical choropleth built
entirely from open, keyless sources.

- **Geometry**: US Census cartographic-boundary congressional districts
  (119th Congress, 1:500k simplified) — `cb_2024_us_cd119_500k.zip`.
- **Members & party**: the public-domain
  [unitedstates/congress-legislators](https://github.com/unitedstates/congress-legislators)
  `legislators-current.json`.
- **Join**: state FIPS + district number (`00` = at-large, `98` = non-voting
  delegate seat; both map to district 0 in the legislators data). Vacant seats
  render grey; delegate seats (DC + territories) render at reduced opacity and
  are labeled non-voting.

Output: `cache/congress/output/index.html` (+ `districts.geojson`) on the
configured storage backend (MinIO/S3 on the fleet, local dir otherwise).
Colors: Democrat `#2166ac`, Republican `#b2182b`, Independent `#6a3d9a`,
vacant `#9e9e9e`.

## Scope note

"Voting districts" here means **House congressional districts**. The Census
term VTD (voting tabulation district, i.e. election precincts, ~180k polygons)
is a far larger dataset with no single open national party-results source —
out of scope for this domain, and disclosed in the map's "About this data"
popup.

## Run

```bash
pip install -e .
fw runner start --domain congress -- --log-format text
fw ffl run --primary src/congress/ffl/congress.ffl \
    --workflow congress.workflows.BuildCongressPartyMap
```

Facets: `congress.maps.BuildDistrictPartyMap` (event) wrapped by
`congress.workflows.BuildCongressPartyMap`. `force=true` re-fetches both
sources; otherwise they are cache-once.

## Layout

Standard Facetwork domain package (`facetwork.domains` entry point named
`congress`): `src/congress/{ffl,handlers,_lib.py,storage.py}` + offline tests
under `tests/` (no network needed).
