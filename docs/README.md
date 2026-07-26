# fwh_congress — Feature Specifications

This directory holds one **spec per feature** of the congress domain. Each document
follows a common shape ([`SPEC_TEMPLATE.md`](SPEC_TEMPLATE.md)) and states, for that
feature: how it works, whether and how it **fans out** (spoiler: it doesn't — this
is a single-task national map), what **data & fields** it keys on, the **external
libraries** it relies on, its **facets & workflows**, and its **cache/output**.
Claims are grounded in the FFL `/** … */` docstrings, the handler + `_lib.py` code,
and the offline tests — the source of truth for the facet remains its FFL docstring;
these specs are the feature-level narrative over them.

The domain is small: **one event facet** (`congress.maps.BuildDistrictPartyMap`)
wrapped by **one workflow** (`congress.workflows.BuildCongressPartyMap`). The five
specs below decompose that single pipeline into its distinct capabilities.

**Start here:** [**District Party Map**](district-party-map.md) — the flagship spec,
the end-to-end pipeline that every other spec feeds.

## Pipeline

| Spec | What it covers |
|------|----------------|
| [district-party-map.md](district-party-map.md) | **Flagship.** The one facet + workflow: fetch CD119 shapes + roster → join sitting-rep party → render the MapLibre choropleth. Single-task, no fan-out. |

## Data ingest & join

| Spec | What it covers |
|------|----------------|
| [data-sources.md](data-sources.md) | The two open, keyless sources — Census CD119 cartographic-boundary shapefile (via `pyshp`) and the public-domain `congress-legislators` roster — plus the cache-once `_fetch_cached` flow. |
| [party-join.md](party-join.md) | The `district_key` FIPS+district join: at-large (`00`), non-voting delegate (`98`), vacant, and third-party→Independent handling; the party color table. |

## Rendering & storage

| Spec | What it covers |
|------|----------------|
| [rendering.md](rendering.md) | The self-contained MapLibre GL choropleth HTML: categorical fill, delegate opacity, legend with seat counts, search box, About modal, attribution. |
| [storage-and-cache.md](storage-and-cache.md) | The backend-aware storage shim (`storage.py`): local dir vs MinIO/S3 layout, `localize`, stage-local finalize-on-close writes, cache/output paths, env overrides. |

---

*See also the repo [`README.md`](../README.md) (run instructions, sources, scope
note). The live/queryable interface is the MCP `fw_capabilities` /
`fw_describe_handler` tools — `fw_capabilities` finds `congress.maps.BuildDistrictPartyMap`
by intent, `fw_describe_handler` describes its handler.*
