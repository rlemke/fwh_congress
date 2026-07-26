# Party Join

**Namespace(s):** `congress.maps` (inside `build_district_party_map`) ·
**Lib:** `src/congress/_lib.py` (`district_key`, `STATE_FIPS`, `PARTY_COLORS`, the join loop) ·
**Tests:** `tests/test_congress.py` (`test_district_key`, `test_party_colors_include_vacant_grey`)

## Overview

The join is the domain's real logic: turning a Census district polygon (keyed by
numeric state FIPS + a district *code*) and a legislators roster (keyed by USPS
abbreviation + district *number*) into one colored feature. The subtlety is entirely
in reconciling the two keying schemes and handling the seats that are not a plain
numbered district — at-large states, non-voting delegate seats, vacancies, and
third-party members.

## How it works

Per district polygon, inside `build_district_party_map`:

1. **`district_key(state_fips, cd)`** resolves the join key. Returns
   `None` (→ skip the polygon) if the FIPS is unknown, or the CD code is blank or
   non-numeric (e.g. `ZZ`). Otherwise, with `n = int(cd)`:
   - `n == 98` → `(abbr, 0, is_delegate=True)` — non-voting delegate seat.
   - `n == 0` → `(abbr, 0, is_delegate=False)` — at-large district.
   - else → `(abbr, n, False)` — a numbered district.
2. **Member lookup** — `members.get((abbr, dist))`. A hit gives `{name, party}`; a
   miss means the seat is `Vacant`.
3. **Party normalization** — if the member's party is not one of the known
   `PARTY_COLORS` keys (`Democrat`, `Republican`, `Independent`, `Vacant`), it is
   folded to `Independent` (small third parties render with the Independent color).
4. **Counting** — `counts[party if m else "Vacant"] += 1`; only Democrat / Republican
   / Independent / Vacant buckets exist.
5. **Label** — `f"{abbr} delegate"` for delegate seats, `f"{abbr} at-large"` for
   at-large, else `f"{abbr}-{dist:02d}"` (e.g. `CA-12`).
6. **Feature properties** — `LABEL`, `STATE` (full name from `STATE_FIPS`), `MEMBER`
   (`name` or `"(vacant)"`), `PARTY` (`party` if a member, else `"Vacant"`),
   `DELEGATE` (bool).

## Fan-out

**Single-task — no fan-out.** The join is an in-memory loop over the ~436 district
polygons within the one facet.

## Data & fields

| Concept | Source key | Join key |
|---|---|---|
| District polygon | `STATEFP` + `CD*FP` code | `(USPS abbr, district number, is_delegate)` via `district_key` |
| Member | `terms[-1].state` + `terms[-1].district` | `(state_abbr, int(district))` |

Special CD codes: `00` = at-large (district 0), `98` = non-voting delegate (also
district 0), blank / `ZZ` = undefined → skipped. `district_key`'s five cases are
pinned by `test_district_key` (numbered, at-large, delegate, `ZZ`→None, unknown
FIPS→None).

`PARTY_COLORS`: `Democrat #2166ac` (blue), `Republican #b2182b` (red),
`Independent #6a3d9a` (purple), `Vacant #9e9e9e` (grey — asserted by
`test_party_colors_include_vacant_grey`).

## External libraries / binaries

- **`shapely`** (pip) — `shape(...).simplify(SIMPLIFY_DEG, preserve_topology=True)`
  then `mapping(...)` produces the per-feature GeoJSON geometry inside the join
  loop. `SIMPLIFY_DEG = 0.004` degrees.
- Otherwise pure Python (dict lookups + string formatting); no binaries.

## Facets & workflows

No facet of its own — the join is the body of `build_district_party_map`, called by
`congress.maps.BuildDistrictPartyMap` (see [district-party-map](district-party-map.md)).
`district_key` and the color/FIPS tables are unit-tested directly.

## Cache / output

No cache of its own. The join's output — the joined `FeatureCollection` — is written
by the render step as `districts.geojson` alongside `index.html`
(see [rendering](rendering.md) and [storage-and-cache](storage-and-cache.md)).

## Gotchas & notes

- **At-large and delegate seats collide on district 0.** Both `00` and `98` map to
  district `0`; they are told apart only by the `is_delegate` flag, which drives the
  label and the reduced map opacity — not by the join key. A state cannot have both
  a delegate and an at-large seat, so this is safe.
- **Third parties are invisible in the returned counts.** Folding non-standard
  parties to `Independent` means an Independent-held seat colors correctly but is
  *not* in `dem_count` / `rep_count` / `vacant_count` (the three surfaced on the
  workflow return). Independent seats are only reflected in the legend's per-party
  count in the HTML.
- **Vacant vs Independent color reuse.** A member whose party is unknown becomes
  `Independent` (purple); a seat with *no* member becomes `Vacant` (grey). The
  distinction is member-presence, not party string.
- **A renamed/missing FIPS silently drops a district.** `district_key` returns
  `None` for any FIPS not in `STATE_FIPS`, so a new territory code would vanish from
  the map rather than error.

## Related specs

- [data-sources](data-sources.md) — the two keying schemes being reconciled.
- [district-party-map](district-party-map.md) — the facet the join lives inside.
- [rendering](rendering.md) — how the joined `PARTY`/`DELEGATE` properties drive color/opacity.
