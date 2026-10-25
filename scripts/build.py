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
 '/*LOCATION_JS*/':(ROOT/'location.js').read_text(),
 '/*VISION_CSS*/':(ROOT/'vision.css').read_text(),
 '/*VISION_CORE_JS*/':(ROOT/'vision-core.js').read_text(),
 '/*VISION_JS*/':(ROOT/'vision.js').read_text(),
 '/*WEATHER_CSS*/':(ROOT/'weather.css').read_text(),
 '/*WEATHER_JS*/':(ROOT/'weather.js').read_text(),
 '/*INSTALL_JS*/':(ROOT/'install.js').read_text(),
 '/*APP_JS*/':(ROOT/'app.js').read_text(),
}
for marker,value in assets.items():text=text.replace(marker,value)
(ROOT/'index.html').write_text(text)
release=hashlib.sha256(text.encode())
for name in ['manifest.webmanifest','icons/icon-192.png','icons/icon-512.png']:
 release.update((ROOT/name).read_bytes())
revision=release.hexdigest()[:12]
(ROOT/'sw.js').write_text((ROOT/'sw.template.js').read_text().replace('/*BUILD_REVISION*/',revision))
print(f'Built index.html: {len(data["sections"])} sections, {len(data["pois"])} places, {len(text.encode()):,} bytes')
