"""Assemble the self-contained racer roadbook. Python standard library only."""
from pathlib import Path
import json,base64,hashlib
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'data/roadbook_data.json').read_text())
gpx=(ROOT/'routes/canarias360_best_candidate.gpx').read_bytes()
assert hashlib.sha256(gpx).hexdigest()==data['gpx_sha256'],'GPX changed: update/recalculate roadbook data before building'
for place in data['pois']:place.pop('osm_tags',None)
text=(ROOT/'index.template.html').read_text()
assets={
 '/*LEAFLET_CSS*/':(ROOT/'vendor/leaflet.css').read_text(),
 '/*LEAFLET_JS*/':(ROOT/'vendor/leaflet.js').read_text(),
 '/*DATA_JSON*/':json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c'),
 '/*GPX_BASE64*/':base64.b64encode(gpx).decode(),
 '/*ENGINE_JS*/':(ROOT/'engine.js').read_text(),
 '/*APP_JS*/':(ROOT/'app.js').read_text(),
}
for marker,value in assets.items():text=text.replace(marker,value)
(ROOT/'index.html').write_text(text)
print(f'Built index.html: {len(data["sections"])} sections, {len(data["pois"])} places, {len(text.encode()):,} bytes')
