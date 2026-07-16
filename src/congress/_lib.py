"""congress domain internals.

1. ``download_shapes`` — Census cartographic-boundary congressional districts
   (119th Congress, 1:500k simplified) ZIP -> parsed features. Cached.
2. ``download_members`` — unitedstates/congress-legislators
   ``legislators-current.json`` (public domain) -> (state, district) -> member.
   Cached.
3. ``build_district_party_map`` — join party onto district polygons and render
   a MapLibre choropleth (Democrat blue / Republican red / Independent purple /
   vacant grey), popup with member + district, search box, about modal.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import zipfile
from dataclasses import dataclass

import requests

from . import storage as cstore

logger = logging.getLogger(__name__)

SHAPES_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_cd119_500k.zip"
MEMBERS_URL = "https://unitedstates.github.io/congress-legislators/legislators-current.json"
FFL_URL = "https://github.com/rlemke/fwh_congress/blob/main/src/congress/ffl/congress.ffl"

SIMPLIFY_DEG = 0.004  # shapely simplify tolerance for the inline GeoJSON

# State FIPS -> (USPS abbr, name). Includes DC + the delegate territories that
# appear in the CD file.
STATE_FIPS: dict[str, tuple[str, str]] = {
    "01": ("AL", "Alabama"), "02": ("AK", "Alaska"), "04": ("AZ", "Arizona"),
    "05": ("AR", "Arkansas"), "06": ("CA", "California"), "08": ("CO", "Colorado"),
    "09": ("CT", "Connecticut"), "10": ("DE", "Delaware"), "11": ("DC", "District of Columbia"),
    "12": ("FL", "Florida"), "13": ("GA", "Georgia"), "15": ("HI", "Hawaii"),
    "16": ("ID", "Idaho"), "17": ("IL", "Illinois"), "18": ("IN", "Indiana"),
    "19": ("IA", "Iowa"), "20": ("KS", "Kansas"), "21": ("KY", "Kentucky"),
    "22": ("LA", "Louisiana"), "23": ("ME", "Maine"), "24": ("MD", "Maryland"),
    "25": ("MA", "Massachusetts"), "26": ("MI", "Michigan"), "27": ("MN", "Minnesota"),
    "28": ("MS", "Mississippi"), "29": ("MO", "Missouri"), "30": ("MT", "Montana"),
    "31": ("NE", "Nebraska"), "32": ("NV", "Nevada"), "33": ("NH", "New Hampshire"),
    "34": ("NJ", "New Jersey"), "35": ("NM", "New Mexico"), "36": ("NY", "New York"),
    "37": ("NC", "North Carolina"), "38": ("ND", "North Dakota"), "39": ("OH", "Ohio"),
    "40": ("OK", "Oklahoma"), "41": ("OR", "Oregon"), "42": ("PA", "Pennsylvania"),
    "44": ("RI", "Rhode Island"), "45": ("SC", "South Carolina"), "46": ("SD", "South Dakota"),
    "47": ("TN", "Tennessee"), "48": ("TX", "Texas"), "49": ("UT", "Utah"),
    "50": ("VT", "Vermont"), "51": ("VA", "Virginia"), "53": ("WA", "Washington"),
    "54": ("WV", "West Virginia"), "55": ("WI", "Wisconsin"), "56": ("WY", "Wyoming"),
    "60": ("AS", "American Samoa"), "66": ("GU", "Guam"),
    "69": ("MP", "Northern Mariana Islands"), "72": ("PR", "Puerto Rico"),
    "78": ("VI", "U.S. Virgin Islands"),
}

PARTY_COLORS = {
    "Democrat": "#2166ac",
    "Republican": "#b2182b",
    "Independent": "#6a3d9a",
    "Vacant": "#9e9e9e",
}


@dataclass
class CongressMapResult:
    html_path: str
    district_count: int
    dem_count: int
    rep_count: int
    vacant_count: int


# ---------------------------------------------------------------------------
# Downloads (cache-aware).
# ---------------------------------------------------------------------------


def _fetch_cached(url: str, cache_name: str, *, force: bool = False, binary: bool = True) -> str:
    """Download ``url`` into the congress cache once; return the cache path."""
    path = cstore.join(cstore.cache_root(), cache_name)
    if not force and cstore.exists(path):
        return path
    logger.info("downloading %s -> %s", url, path)
    resp = requests.get(url, timeout=300)
    resp.raise_for_status()
    mode = "wb" if binary else "w"
    with cstore.open_write(path, mode) as f:
        f.write(resp.content if binary else resp.text)
    return path


def download_shapes(*, force: bool = False) -> list[dict]:
    """CD (119th) cartographic-boundary shapes -> [{state_fips, cd, geometry}]."""
    import shapefile  # pyshp

    zip_path = _fetch_cached(SHAPES_URL, "cb_2024_us_cd119_500k.zip", force=force)
    local_zip = cstore.localize(zip_path)

    # pyshp needs the .shp/.dbf pair; extract the ZIP to a temp dir.
    feats: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="congress_shp_") as td:
        with zipfile.ZipFile(local_zip) as zf:
            zf.extractall(td)
        shp = next((os.path.join(td, n) for n in os.listdir(td) if n.endswith(".shp")), None)
        if not shp:
            raise RuntimeError(f"no .shp inside {SHAPES_URL}")
        reader = shapefile.Reader(shp)
        fields = [f[0] for f in reader.fields[1:]]
        cd_field = next((f for f in fields if f.startswith("CD") and f.endswith("FP")), None)
        if not cd_field:
            raise RuntimeError(f"no CD*FP field in {fields}")
        for sr in reader.iterShapeRecords():
            rec = dict(zip(fields, sr.record))
            feats.append(
                {
                    "state_fips": str(rec.get("STATEFP", "")),
                    "cd": str(rec.get(cd_field, "")),
                    "geometry": sr.shape.__geo_interface__,
                }
            )
    if not feats:
        raise RuntimeError("CD shapefile parsed to zero features")
    return feats


def download_members(*, force: bool = False) -> dict[tuple[str, int], dict]:
    """(state_abbr, district) -> {name, party} for sitting House members."""
    path = _fetch_cached(MEMBERS_URL, "legislators-current.json", force=force)
    with cstore.open_read(path, "r", encoding="utf-8") as f:
        people = json.load(f)
    members: dict[tuple[str, int], dict] = {}
    for p in people:
        terms = p.get("terms") or []
        if not terms:
            continue
        t = terms[-1]  # legislators-current: the last term is the sitting one
        if t.get("type") != "rep":
            continue
        state = str(t.get("state", ""))
        district = t.get("district")
        if district is None:
            continue
        name = (p.get("name") or {}).get("official_full") or "{} {}".format(
            (p.get("name") or {}).get("first", ""), (p.get("name") or {}).get("last", "")
        ).strip()
        members[(state, int(district))] = {
            "name": name,
            "party": str(t.get("party", "Unknown")),
        }
    if not members:
        raise RuntimeError("legislators-current.json parsed to zero House members")
    return members


# ---------------------------------------------------------------------------
# Join + build.
# ---------------------------------------------------------------------------


def district_key(state_fips: str, cd: str) -> tuple[str, int, bool] | None:
    """CD code -> (state_abbr, district_number, is_delegate). None -> skip.

    ``00`` = at-large district, ``98`` = non-voting delegate seat (both are
    district 0 in the legislators data); ``ZZ``/blank = undefined -> skipped.
    """
    st = STATE_FIPS.get(state_fips)
    if not st or not cd or not cd.isdigit():
        return None
    n = int(cd)
    if n == 98:
        return (st[0], 0, True)
    if n == 0:
        return (st[0], 0, False)
    return (st[0], n, False)


def build_district_party_map(*, force: bool = False) -> CongressMapResult:
    from shapely.geometry import mapping, shape

    shapes = download_shapes(force=force)
    members = download_members(force=force)

    feats, counts = [], {"Democrat": 0, "Republican": 0, "Independent": 0, "Vacant": 0}
    for s in shapes:
        key = district_key(s["state_fips"], s["cd"])
        if key is None:
            continue
        abbr, dist, is_delegate = key
        st_name = STATE_FIPS[s["state_fips"]][1]
        m = members.get((abbr, dist))
        party = (m or {}).get("party", "Vacant")
        if party not in PARTY_COLORS:
            party = "Independent"  # small third parties render with the I color
        counts[party if m else "Vacant"] = counts.get(party if m else "Vacant", 0) + 1
        label = (
            f"{abbr} delegate" if is_delegate
            else (f"{abbr} at-large" if dist == 0 else f"{abbr}-{dist:02d}")
        )
        geom = shape(s["geometry"]).simplify(SIMPLIFY_DEG, preserve_topology=True)
        feats.append(
            {
                "type": "Feature",
                "geometry": mapping(geom),
                "properties": {
                    "LABEL": label,
                    "STATE": st_name,
                    "MEMBER": (m or {}).get("name", "(vacant)"),
                    "PARTY": party if m else "Vacant",
                    "DELEGATE": bool(is_delegate),
                },
            }
        )

    fc = {"type": "FeatureCollection", "features": feats}
    html = _render_html(fc, counts)

    out_dir = cstore.output_root()
    html_path = cstore.join(out_dir, "index.html")
    with cstore.open_write(cstore.join(out_dir, "districts.geojson"), "w") as f:
        json.dump(fc, f, separators=(",", ":"))
    with cstore.open_write(html_path, "w") as f:
        f.write(html)
    return CongressMapResult(
        html_path,
        len(feats),
        counts.get("Democrat", 0),
        counts.get("Republican", 0),
        counts.get("Vacant", 0),
    )


# ---------------------------------------------------------------------------
# Render — categorical party choropleth.
# ---------------------------------------------------------------------------


def _attribution() -> str:
    from datetime import UTC, datetime
    from html import escape

    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    call = "congress.workflows.BuildCongressPartyMap"
    repo = FFL_URL.split("/blob/")[0]
    return (
        '<div style="position:fixed;bottom:10px;left:10px;z-index:9999;'
        "background:rgba(255,255,255,0.92);border-radius:6px;padding:6px 10px;"
        "box-shadow:0 1px 4px rgba(0,0,0,0.2);font:11px system-ui,sans-serif;color:#444;"
        'max-width:470px">Generated by Facetwork workflow '
        '<code style="background:#f0f0f0;padding:0 3px;border-radius:3px">'
        f"{escape(call)}</code> &middot; "
        f'<a href="{escape(FFL_URL)}" target="_blank" rel="noopener" '
        'style="color:#1565c0;text-decoration:none">view FFL</a>'
        f' &middot; <a href="{escape(repo)}" target="_blank" rel="noopener" '
        'style="color:#1565c0;text-decoration:none">source repo</a>'
        f" &middot; generated {ts}</div>"
    )


def _render_html(fc: dict, counts: dict[str, int]) -> str:
    fc_js = json.dumps(fc, separators=(",", ":"))
    colors_js = json.dumps(PARTY_COLORS)
    counts_js = json.dumps(counts)
    desc = (
        "US congressional districts (119th Congress, 2025-2027) colored by the "
        "party of the sitting House representative. Grey = vacant seat. "
        "Districts marked &ldquo;delegate&rdquo; (DC + territories) elect "
        "non-voting members. &ldquo;Voting districts&rdquo; here means House "
        "districts; precinct-level (VTD) results are a much larger dataset with "
        "no single open national party source. Geometry: US Census "
        "cartographic boundaries (1:500k). Members &amp; party: the public-domain "
        "unitedstates/congress-legislators dataset."
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>US congressional districts by party</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet">
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<style>
  html,body,#map{{margin:0;height:100%;width:100%;font-family:system-ui,sans-serif}}
  .panel{{position:absolute;z-index:1;background:rgba(255,255,255,.94);padding:10px 12px;
    border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.3);font-size:12px}}
  #ctl{{top:10px;left:10px;max-width:340px}}
  #ctl h3{{margin:0 0 6px;font-size:14px}}
  #legend{{bottom:18px;right:10px}} #legend .row{{display:flex;align-items:center;margin-top:3px}}
  #legend .row span{{width:16px;height:12px;margin-right:6px;border-radius:2px}}
  .maplibregl-popup-content{{max-width:300px;font-size:12px}}
  .maplibregl-popup-content h4{{margin:0 0 4px;font-size:13px}}
  .rsearch{{position:absolute;top:10px;left:50%;transform:translateX(-50%);z-index:6;width:300px;max-width:70%}}
  .rsearch input{{width:100%;box-sizing:border-box;padding:7px 11px;border:1px solid #aaa;border-radius:6px;font-size:13px;box-shadow:0 2px 6px rgba(0,0,0,.2)}}
  .rsearch .res{{background:#fff;border-radius:0 0 6px 6px;box-shadow:0 2px 6px rgba(0,0,0,.2);max-height:240px;overflow:auto}}
  .rsearch .res div{{padding:6px 11px;cursor:pointer;font-size:12px;border-top:1px solid #f0f0f0}}
  .rsearch .res div:hover{{background:#f3f3f3}}
  .infobtn{{margin-top:8px;width:100%;padding:7px;font-size:13px;cursor:pointer;background:#fff8e1;border:1px solid #f6c343;border-radius:4px;color:#5d4b00}}
  .infobtn:hover{{background:#fff2c4}}
  .modal{{position:absolute;inset:0;z-index:5;background:rgba(0,0,0,.45);display:none;align-items:center;justify-content:center}}
  .modalcard{{background:#fff;max-width:460px;margin:16px;padding:18px 20px 20px;border-radius:10px;box-shadow:0 4px 24px rgba(0,0,0,.4);position:relative;font:13px/1.5 system-ui,sans-serif;max-height:80vh;overflow:auto}}
  .modalcard h2{{margin:0 0 8px;font-size:16px}} .modalbody{{color:#333}} .modalbody b{{color:#111}}
  .modalclose{{position:absolute;top:6px;right:10px;border:none;background:none;font-size:24px;line-height:1;cursor:pointer;color:#999}} .modalclose:hover{{color:#444}}
</style></head>
<body>
<div id="map"></div>
<div class="rsearch"><input id="rsin" placeholder="Find a district, state, or member..." autocomplete="off"><div class="res" id="rsres"></div></div>
<div id="ctl" class="panel">
  <h3>US congressional districts by party</h3>
  <div style="color:#555">{desc}</div>
  <button id="infobtn" class="infobtn">&#8505;&#65039; About this data</button>
</div>
<div id="legend" class="panel"><b>Party (seats)</b><div id="lgrows"></div></div>
<div id="infomodal" class="modal"><div class="modalcard"><button id="infoclose" class="modalclose">&times;</button><h2>About this data</h2><div class="modalbody">{desc}</div></div></div>
{_attribution()}
<script>
const FC={fc_js}, COLORS={colors_js}, COUNTS={counts_js};
const map=new maplibregl.Map({{container:'map',style:{{version:8,
  sources:{{bm:{{type:'raster',tiles:['https://a.basemaps.cartocdn.com/rastertiles/voyager/{{z}}/{{x}}/{{y}}.png','https://b.basemaps.cartocdn.com/rastertiles/voyager/{{z}}/{{x}}/{{y}}.png'],tileSize:256,attribution:'&copy; OpenStreetMap &copy; CARTO &middot; US Census &middot; unitedstates/congress-legislators'}}}},
  layers:[{{id:'bm',type:'raster',source:'bm'}}]}},center:[-96,38],zoom:3.4}});
map.addControl(new maplibregl.NavigationControl());
const lg=document.getElementById('lgrows');
Object.keys(COLORS).forEach(p=>{{const d=document.createElement('div');d.className='row';
  d.innerHTML=`<span style="background:${{COLORS[p]}}"></span>${{p}} (${{COUNTS[p]||0}})`;lg.appendChild(d);}});
map.on('load',()=>{{
  map.addSource('d',{{type:'geojson',data:FC}});
  map.addLayer({{id:'fill',type:'fill',source:'d',paint:{{
    'fill-color':['match',['get','PARTY'],
      'Democrat',COLORS['Democrat'],'Republican',COLORS['Republican'],
      'Independent',COLORS['Independent'],COLORS['Vacant']],
    'fill-opacity':['case',['get','DELEGATE'],0.45,0.75]}}}});
  map.addLayer({{id:'line',type:'line',source:'d',paint:{{'line-color':'#fff','line-width':0.6}}}});
  map.on('click','fill',e=>{{const p=e.features[0].properties||{{}};
    const del=(p.DELEGATE===true||p.DELEGATE==='true')?' &middot; <i>non-voting delegate seat</i>':'';
    new maplibregl.Popup({{closeButton:true,maxWidth:'280px'}}).setLngLat(e.lngLat)
      .setHTML(`<h4>${{p.LABEL}} &middot; ${{p.STATE}}</h4>${{p.MEMBER}}<br><b style="color:${{COLORS[p.PARTY]||'#666'}}">${{p.PARTY}}</b>${{del}}`).addTo(map);}});
  map.on('mouseenter','fill',()=>map.getCanvas().style.cursor='pointer');
  map.on('mouseleave','fill',()=>map.getCanvas().style.cursor='');
  const inp=document.getElementById('rsin'),res=document.getElementById('rsres');
  function bbox(g){{let a=[180,90,-180,-90];const w=c=>{{if(typeof c[0]==='number'){{a[0]=Math.min(a[0],c[0]);a[1]=Math.min(a[1],c[1]);a[2]=Math.max(a[2],c[0]);a[3]=Math.max(a[3],c[1]);}}else c.forEach(w);}};w(g.coordinates);return a;}}
  inp.addEventListener('input',()=>{{const q=inp.value.trim().toLowerCase();res.innerHTML='';if(q.length<2)return;
    FC.features.map(f=>({{n:`${{f.properties.LABEL}} ${{f.properties.STATE}} ${{f.properties.MEMBER}}`,f}}))
      .filter(x=>x.n.toLowerCase().includes(q)).slice(0,12).forEach(x=>{{
      const d=document.createElement('div');d.textContent=`${{x.f.properties.LABEL}} — ${{x.f.properties.MEMBER}}`;
      d.addEventListener('click',()=>{{const b=bbox(x.f.geometry);
        map.fitBounds([[b[0],b[1]],[b[2],b[3]]],{{padding:40,maxZoom:9,duration:700}});res.innerHTML='';inp.value=x.f.properties.LABEL;}});
      res.appendChild(d);}});}});
  document.addEventListener('click',e=>{{if(!e.target.closest('.rsearch'))res.innerHTML='';}});
}});
const _im=document.getElementById('infomodal');
if(_im){{const ib=document.getElementById('infobtn'),ic=document.getElementById('infoclose');
 if(ib)ib.onclick=()=>{{_im.style.display='flex';}};
 if(ic)ic.onclick=()=>{{_im.style.display='none';}};
 _im.onclick=e=>{{if(e.target===_im)_im.style.display='none';}};}}
</script></body></html>"""
