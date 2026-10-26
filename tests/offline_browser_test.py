"""Cold offline navigation after service-worker caching; actual embedded app assets."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,os
R=Path(__file__).resolve().parents[1];records=[]
with sync_playwright() as p:
 for engine in ['chromium','webkit']:
  browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox']) if engine=='chromium' else p.webkit.launch(headless=True)
  ctx=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
  ctx.add_init_script("Object.defineProperty(navigator,'geolocation',{value:{watchPosition(ok,bad){setTimeout(()=>bad({code:1}),0);return 1;},clearWatch(){}}});")
  page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:8787');page.wait_for_function('window.RACER_APP');page.evaluate('navigator.serviceWorker.ready');page.wait_for_function('navigator.serviceWorker.controller!==null');cs=[]
  def check(name,value):
   assert value,name
   cs.append(name)
  check('self-contained HTML is cached for navigation',page.evaluate("caches.keys().then(keys=>keys.some(k=>k.startsWith('canarias360-offline-')))"))
  ctx.set_offline(True);page.goto('http://127.0.0.1:8787/?offline-cold-reload=1');page.wait_for_function('window.RACER_APP')
  check('roadbook cold-reloads without network',page.evaluate('RACER_APP.DATA.pois.length')==337)
  check('manifest and both install icons remain available offline',page.evaluate("Promise.all(['manifest.webmanifest','icons/icon-192.png','icons/icon-512.png'].map(path=>fetch(path,{cache:'no-store'}).then(r=>r.ok))).then(results=>results.every(Boolean))"))
  page.get_by_role('tab',name='Map',exact=True).click();check('offline Leaflet route still initializes',page.locator('#map .leaflet-map-pane').count()==1)
  page.locator('#openTrailVision').click();page.wait_for_function('RACER_APP.vision()?.active');page.locator('[data-vision=previewOffline]').click();page.locator('[data-vision=mode]').select_option('route');page.wait_for_timeout(300)
  check('Trail Vision renders cached race GPX offline',page.evaluate('RACER_APP.vision().available')==500 and page.evaluate('RACER_APP.vision().frames')>0)
  check('race GPX elevations remain available offline',page.evaluate('RACER_APP.vision().elevationOK'))
  page.locator('[data-vision=exit]').click();check('closing offline preview returns to a working map',page.locator('#map .leaflet-map-pane').count()==1 and not errors)
  ctx.close();browser.close();records.append({'browser':engine,'passed':len(cs),'checks':cs})
result={'passed':sum(r['passed'] for r in records),'results':records,'physical_device_test':False};(R/'docs/offline-browser-tests.json').write_text(json.dumps(result,indent=2));print(json.dumps({'passed':result['passed']},indent=2))
