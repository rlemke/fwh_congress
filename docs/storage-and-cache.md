# Storage & Cache

**Namespace(s):** cross-cutting (all of `congress.maps`) ·
**Storage:** `src/congress/storage.py` ·
**Lib:** `src/congress/_lib.py` (`_fetch_cached`, output writes) ·
**Config:** `src/congress/__init__.py` (`runner_env`)

## Overview

A thin backend-aware storage shim — the same shape h1b / census-us / conflict use —
so terminal runs and fleet runs share one cache and write outputs to the configured
durable backend without the handler code caring whether that is a local directory or
MinIO/S3. It wraps `facetwork.runtime.storage`.

## How it works

Paths are computed from `_data_root()` = `FW_DATA_ROOT` or
`facetwork.config.get_output_base()`. `is_remote(path)` is a simple `"://" in path`
test, which selects the local vs object-store layout:

- **`cache_root()`** — `FW_CONGRESS_CACHE_DIR` override, else
  `join(root, "cache", "congress", "cache")` when remote, else
  `join(root, "congress-cache")` locally.
- **`output_root()`** — `FW_CONGRESS_OUTPUT_DIR` override, else
  `join(root, "cache", "congress", "output")` when remote, else
  `join(root, "congress-output")` locally.

I/O helpers hide the backend:

- **`exists(path)`** → `get_storage_backend(path).exists(path)`.
- **`localize(path)`** → returns the path unchanged if local; otherwise pulls the
  remote object to a local temp file (used by `download_shapes` because `pyshp` needs
  files on disk).
- **`open_read`** → `open(localize(path), …)`.
- **`open_write`** (context manager) → for local paths, `makedirs` the parent and
  `open` directly; for remote paths, write to a `mkstemp` temp file, then on close
  stream it into `get_storage_backend(path).open(path, "wb")`. This **stage-local,
  finalize-on-close** pattern is required because object stores do not do partial
  writes.

## Fan-out

Not applicable — this is infrastructure, not a workflow step. It serves the single
`BuildDistrictPartyMap` task.

## Data & fields

No domain data of its own; it moves the ZIP / JSON (cache) and `index.html` /
`districts.geojson` (output) bytes. `join(*parts)` normalizes path/URL segments
(strips slashes, preserves the scheme on the first part).

## External libraries / binaries

- **`facetwork.config.get_output_base`** and **`facetwork.runtime.storage`**
  (`get_storage_backend`, `localize`, `open`) — the framework storage layer; the
  only non-stdlib imports. No boto3/pip S3 client is imported directly here (the
  backend abstraction owns that).
- Python stdlib `os` / `tempfile` / `contextlib`.

## Facets & workflows

None — pure support module. Every congress facet's downloads and outputs route
through it.

## Cache / output

The canonical layout rooted at `$FW_DATA_ROOT/cache/congress/` (remote):

| Path | Contents |
|---|---|
| `cache/congress/cache/cb_2024_us_cd119_500k.zip` | Census CD119 shapes (input) |
| `cache/congress/cache/legislators-current.json` | member roster (input) |
| `cache/congress/output/index.html` | the rendered map (primary artifact) |
| `cache/congress/output/districts.geojson` | the joined FeatureCollection |

Locally the same files sit under `congress-cache/` and `congress-output/`. On the
fleet (`FW_STORAGE=s3`, `FW_DATA_ROOT=s3://afl-cache`) they live in shared MinIO, so
any runner on any host resolves the same cache.

## Gotchas & notes

- **Keep scratch local.** The remote `open_write` stages through `mkstemp`; the temp
  dir must be a real local filesystem (object stores can't be partially written).
- **`FW_DATA_ROOT` decides the layout, not just the location.** Because `is_remote`
  keys off `://`, switching between a local path and an `s3://` root also switches
  the directory nesting (`congress-cache/` vs `cache/congress/cache/`); don't assume
  one layout across environments.
- **`runner_env` bumps the timeouts.** `__init__.py` sets
  `FW_TASK_EXECUTION_TIMEOUT_MS=1200000` (20 min) and `FW_STUCK_TIMEOUT_MS=1500000`
  so the blocking shape-ZIP download+parse isn't reaped mid-flight on a cold cache.
- **Env overrides bypass the root.** `FW_CONGRESS_CACHE_DIR` /
  `FW_CONGRESS_OUTPUT_DIR` short-circuit `_data_root()` entirely — handy for tests
  or one-off local runs.

## Related specs

- [data-sources](data-sources.md) — what lands in the cache and how `_fetch_cached` uses it.
- [rendering](rendering.md) — what lands in the output dir.
- [district-party-map](district-party-map.md) — the facet whose I/O this module carries.
