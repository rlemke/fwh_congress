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

## FFL at a glance

The domain is driven from [FFL](https://github.com/rlemke/facetwork/blob/main/docs/reference/language/grammar.md),
Facetwork's workflow language. A step is `name = Facet(args)`, and later steps
reference earlier ones as `step.field`:

```ffl
namespace my.congress {

    use congress.maps

    /** Rebuild the district-party map, optionally bypassing the cache. */
    workflow RefreshPartyMap(force: Boolean = false) => (status: String, html_path: String, seats: Int) andThen {

        map = congress.maps.BuildDistrictPartyMap(force = $.force)

        yield RefreshPartyMap(
            status = "completed",
            html_path = map.html_path,
            seats = map.district_count)
    }
}
```

```bash
fw ffl run --primary my.ffl --library src/congress/ffl/congress.ffl \
  --workflow my.congress.RefreshPartyMap --inputs '{"force": true}'
```

📖 **[docs/ffl-examples.md](docs/ffl-examples.md)** — the full example gallery:
call-time mixins (timeout/retry), `catch`, `when` branching, wrapping the shipped
workflow, and cross-domain composition (publishing the map). Every snippet there
is compile-checked. This domain's single facet makes it a good place to learn the
language.

## Feature specifications

Per-feature docs live in [`docs/`](docs/README.md) — one spec per capability of the
single `BuildDistrictPartyMap` pipeline, each grounded in the FFL docstrings +
handler/`_lib` code.

| Spec | What it covers |
|------|----------------|
| [district-party-map](docs/district-party-map.md) | **Flagship.** The one facet + workflow: fetch → join → render the national choropleth (single-task). |
| [data-sources](docs/data-sources.md) | Census CD119 shapefile (`pyshp`) + `congress-legislators` roster; cache-once fetch. |
| [party-join](docs/party-join.md) | `district_key` FIPS+district join: at-large / delegate / vacant / third-party rules + party colors. |
| [rendering](docs/rendering.md) | Self-contained MapLibre choropleth HTML: fill, delegate opacity, legend, search, About modal. |
| [storage-and-cache](docs/storage-and-cache.md) | Backend-aware storage shim: local vs MinIO/S3 layout, cache/output paths, env overrides. |

See [`docs/README.md`](docs/README.md) for the full index.

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
