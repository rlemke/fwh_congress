# FFL Examples — `congress`

Every numbered scenario is a **complete, compilable FFL file**. Copy one into
`my.ffl` and run it:

```bash
fw ffl run --primary my.ffl \
  --library ~/fw_handlers/fwh_congress/src/congress/ffl/congress.ffl \
  --workflow my.congress.<WorkflowName>
```

A runner serving the `congress` namespace must be up
(`fw runner start --domain congress`). Every block below is compile-checked
against `src/congress/ffl/congress.ffl`.

New to the language? Start with the
[FFL grammar](https://github.com/rlemke/facetwork/blob/main/docs/reference/language/grammar.md)
and the [canonical examples](https://github.com/rlemke/facetwork/tree/main/examples/canonical).

---

## The facets at a glance

This domain is deliberately small — one event facet and the workflow that wraps
it. That makes it a good place to learn the language without the noise of a
20-facet pipeline.

| Declaration | Signature | Does |
|---|---|---|
| `congress.maps.BuildDistrictPartyMap` | `(force: Boolean = false) => (html_path, district_count, dem_count, rep_count, vacant_count)` | Fetch CD119 shapes + roster, join sitting-rep party, render the choropleth |
| `congress.workflows.BuildCongressPartyMap` | `(force: Boolean = false) => (status, html_path, district_count, dem_count, rep_count, vacant_count)` | The shipped entry point |

`BuildDistrictPartyMap` is an `event facet`: it runs in a handler on a runner, not
in the compiler. Its `with Effect(kind = "external")` / `with Cost(tier =
"expensive")` mixins are what `fw_capabilities(effect=…, max_cost=…)` filters on.

---

## 1. Run what ships — no FFL to write

```bash
fw ffl seed --include congress

fw ffl run --primary ~/fw_handlers/fwh_congress/src/congress/ffl/congress.ffl \
  --workflow congress.workflows.BuildCongressPartyMap \
  --inputs '{"force": false}'
```

`force = true` re-fetches both sources; otherwise they are cache-once. Write FFL
when you want a different shape of run — your own error handling, a guard on the
result, or composition with another domain.

## 2. The smallest workflow you can write

Every FFL workflow needs a `namespace`, a `use` per namespace it calls into, and a
`yield` back to itself.

```ffl
namespace my.congress {

    use congress.maps

    /** Render the district-party map. */
    workflow MyPartyMap() => (html_path: String, districts: Int) andThen {

        map = congress.maps.BuildDistrictPartyMap(force = false)

        yield MyPartyMap(html_path = map.html_path, districts = map.district_count)
    }
}
```

Three rules visible above: `=>` sits on the **same line** as the closing `)` of the
parameter list; references are always `step.field` (never a bare step name); and
every workflow ends by yielding to itself.

## 3. Parameters and `$`

`$` means "my immediate container" — inside a workflow body that's the workflow, so
`$.force` is its parameter. `$$` walks one level out (into an enclosing block).

```ffl
namespace my.congress {

    use congress.maps

    /** Rebuild, optionally bypassing the cached Census + roster downloads. */
    workflow RefreshPartyMap(force: Boolean = false) => (status: String, html_path: String, seats: Int) andThen {

        map = congress.maps.BuildDistrictPartyMap(force = $.force)

        yield RefreshPartyMap(
            status = "completed",
            html_path = map.html_path,
            seats = map.district_count)
    }
}
```

Run with `--inputs '{"force": true}'`.

## 4. Build a headline from several results — expressions

`++` concatenates. Results of a step are read by step name; there is no truthy
coercion, so comparisons must produce a real `Boolean`.

```ffl
namespace my.congress {

    use congress.maps

    /** Render, then compose a one-line summary of the chamber. */
    workflow PartyMapSummary() => (headline: String, html_path: String) andThen {

        map = congress.maps.BuildDistrictPartyMap()

        yield PartyMapSummary(
            headline = "CD119 map: " ++ map.html_path,
            html_path = map.html_path)
    }
}
```

## 5. Call-time mixins — timeouts and retries

The facet declares its own defaults (`with Timeout(minutes = 20)`); the **call
site** can add or override mixins for one particular use without forking the facet.

```ffl
namespace my.congress {

    use congress.maps

    /** Census downloads can be slow — give this call more room and retry it. */
    workflow ResilientPartyMap() => (html_path: String) andThen {

        map = congress.maps.BuildDistrictPartyMap(force = true) with Timeout(minutes = 45) with Retry(maxAttempts = 3, backoffSeconds = 60)

        yield ResilientPartyMap(html_path = map.html_path)
    }
}
```

## 6. Survive a failed fetch — `catch`

`catch` runs when its step errors after retries are exhausted. Yielding from the
catch block ends the run with a partial result instead of a hard failure.

```ffl
namespace my.congress {

    use congress.maps

    /** Report a partial result rather than failing the run. */
    workflow BestEffortPartyMap() => (status: String, html_path: String) andThen {

        map = congress.maps.BuildDistrictPartyMap(force = true) catch {
            yield BestEffortPartyMap(status = "fetch_failed", html_path = "")
        }

        yield BestEffortPartyMap(status = "completed", html_path = map.html_path)
    }
}
```

## 7. Branch on a result — `when`

A `when` block hangs off the step it inspects: inside a case `$` is that step, and
`$$` reaches the workflow's parameters. Every `when` needs a default case, last.

```ffl
namespace my.congress {

    use congress.maps

    /** Sanity-check the join: a full House is 435 voting seats. */
    workflow VerifiedPartyMap(expected: Int = 435) => (status: String, html_path: String) andThen {

        map = congress.maps.BuildDistrictPartyMap() andThen when {
            case $.district_count >= $$.expected => {
                yield VerifiedPartyMap(status = "complete_chamber", html_path = $.html_path)
            }
            case _ => {
                yield VerifiedPartyMap(status = "incomplete_join", html_path = $.html_path)
            }
        }
    }
}
```

## 8. Reuse the shipped workflow

Workflows compose like facets — wrap `BuildCongressPartyMap` rather than forking it.

```ffl
namespace my.congress {

    use congress.workflows

    /** Wrap the shipped workflow and reshape its result. */
    workflow PartyMapWithStatus() => (headline: String) andThen {

        built = congress.workflows.BuildCongressPartyMap(force = false)

        yield PartyMapWithStatus(headline = "congress map: " ++ built.status)
    }
}
```

## 9. Compose across domains — publish the map

Facets from different domains compose in one workflow as long as some runner in
the fleet serves each namespace. `census.Publish` is the generic publisher the map
domains share.

```ffl
namespace my.congress {

    use congress.maps
    use census.Publish

    /** Render, then push to the public maps site. */
    workflow PartyMapPublish(repo: String = "rlemke/facetwork-maps") => (pages_url: String) andThen {

        map = congress.maps.BuildDistrictPartyMap()

        published = census.Publish.PublishWebBundle(
            repo = $.repo,
            prefixes = ["congress/output"],
            dests = ["us/congress-party"],
            labels = ["US congressional districts by party"],
            landing_title = "Facetwork maps") after map

        yield PartyMapPublish(pages_url = published.pages_url)
    }
}
```

No value flows from `map` into the publish (it reads the store), so
`after map` is what orders the publish behind the build.

Compile that one with the census publisher's FFL as well:
`--library ~/fw_handlers/fwh_census_us/src/census_us/handlers/publish/ffl/census_publish.ffl
--library ~/fw_handlers/fwh_census_us/src/census_us/handlers/downloads/ffl/census_operations.ffl`
(the second supplies the `census.types` it uses).

---

## Cheat sheet

| You want to… | Write |
|---|---|
| Read a workflow/step parameter | `$.name` (`$$.name` one level out) |
| Read a previous step's result | `stepname.field` |
| Order two independent steps | reference a field of the first from the second |
| More time / retries for one call | `… with Timeout(minutes = 45) with Retry(maxAttempts = 3, backoffSeconds = 60)` |
| Handle a step failure | `step = Facet(…) catch { yield … }` |
| Branch | `step = Facet(…) andThen when { case <bool> => { … } case _ => { … } }` |
| Fan out over a list | `workflow W(items: Json) … andThen foreach i in $.items { … }` |
| Concatenate strings | `a ++ b` |

**Validate before you run:** `afl my.ffl --check` or MCP `fw_validate`. Every error
carries a `rule_id` — fetch `fw://docs/rules/{rule_id}` for a wrong/right pair.

## See also

- [`docs/README.md`](README.md) — per-feature specs for this domain
- [`docs/district-party-map.md`](district-party-map.md) — what the single facet actually does
- [FFL grammar](https://github.com/rlemke/facetwork/blob/main/docs/reference/language/grammar.md) ·
  [canonical examples](https://github.com/rlemke/facetwork/tree/main/examples/canonical) ·
  [relative `$`-scoping](https://github.com/rlemke/facetwork/blob/main/docs/architecture/ffl-relative-scoping.md)
- `src/congress/ffl/congress.ffl` — the source of truth for every signature above
