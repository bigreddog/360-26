"""Official GPX/waypoint integration, PDF instructions, cut-offs and route migration."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,hashlib
R=Path(__file__).resolve().parents[1];runs=[]
for_print=[]
with sync_playwright() as p:
 for engine in ['chromium','webkit']:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']) if engine=='chromium' else p.webkit.launch(headless=True)
  ctx=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,accept_downloads=True,service_workers='block');ctx.route('**/*',lambda r:r.continue_() if r.request.url.startswith('http://127.0.0.1:8787/') else r.abort())
  ctx.add_init_script("if(!localStorage.getItem('canarias360-roadbook-v2'))localStorage.setItem('canarias360-roadbook-v2',JSON.stringify({progressKm:120,elapsedHours:40,anchorLive:true,extraHours:2,quotas:[85,70,60,50],streetMap:false,vision:{lookAhead:250,exaggeration:1.5,mode:'manual'},routeSha256:'old-candidate'}));")
  page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:8787');page.wait_for_function('window.RACER_APP');cs=[]
  def check(name,condition):
   assert condition,f'{engine}: {name}'
   cs.append(name)
  check('official route uses measured GPX distance without stretching',page.evaluate('RACER_APP.DATA.route_status==="official"&&Math.abs(RACER_APP.DATA.distance_km-249.37268507)<1e-6&&RACER_APP.DATA.published_distance_km===254.11'))
  check('incompatible legacy progress and timing are reset explicitly',page.evaluate('state.progressKm===0&&state.elapsedHours===0&&!state.anchorLive&&state.extraHours===0') and page.locator('#routeUpdateNotice').is_visible())
  check('migration retains pacing, map and view preferences',page.evaluate('state.quotas[0]===85&&state.streetMap===false&&state.vision.lookAhead===250'))
  check('Artenara is the next aid checkpoint, not a sleeping lifebase','Artenara' in page.locator('#nextCheckpoint').inner_text() and 'Aid station · no sleeping lifebase' in page.locator('#nextCheckpoint').inner_text())
  check('official Artenara cut-off and predicted margin are visible','Cut-off Wed 19:55' in page.locator('.checkpoint-cutoff').inner_text() and '0h 43m' in page.locator('.checkpoint-cutoff').inner_text())
  check('upcoming instruction is tied to the PDF waypoint number','WP 2' in page.locator('#nextCheckpoint').inner_text() and 'next 700 m' in page.locator('#nextCheckpoint').inner_text())
  page.locator('[data-instruction-fold=all]>summary').click()
  check('all twenty-nine numbered organiser instructions are available',page.locator('[data-instruction-fold=all] li').count()==29)
  for term in ['high seas','pedestrian footbridge','Close the gate','Trail washout','Slippery ground','Alternative passage']:
   check('official instruction retained: '+term,term in page.locator('[data-instruction-fold=all]').inner_text())
  check('PDF provenance and page references are exposed',page.locator('[data-instruction-fold=all] a').get_attribute('href').endswith('ROAD_BOOK_2026_-ESP_ENG_FRA.pdf') and 'page 5' in page.locator('[data-instruction-fold=all]').inner_text())
  page.locator('#progressKm').fill('110.5');page.locator('#progressKm').blur()
  check('explicit coastal instruction remains active throughout its 3.5km span','Coastal conditions' in page.locator('#nextCheckpoint').inner_text() and 'Active' in page.locator('.checkpoint-instructions').inner_text())
  check('open instructions survive progress updates',page.locator('[data-instruction-fold=all]').evaluate('e=>e.open'))
  page.locator('[data-instruction-fold=all]>summary').click();page.locator('#progressKm').fill('34.3');page.locator('#progressKm').blur()
  check('next checkpoint advances from aid station to official control','Aserrador' in page.locator('.next-name').inner_text() and 'food / sleep not confirmed' in page.locator('.checkpoint-service').inner_text())
  page.locator('#pacePanel>summary').click();page.locator('#timingPanel>summary').click();page.locator('#elapsedHours').fill('25');page.locator('#elapsedHours').blur();page.locator('#anchorLive').check()
  check('a late checkpoint plan is visibly flagged',page.locator('.checkpoint-cutoff.late').count()==1 and 'after cut-off' in page.locator('.checkpoint-cutoff').inner_text())
  page.locator('#progressKm').fill('77.7');page.locator('#progressKm').blur()
  check('next lifebase retains distinct sleeping-service label','Parque Sur' in page.locator('.next-name').inner_text() and 'sleeping lifebase' in page.locator('.checkpoint-service').inner_text())
  page.get_by_role('tab',name='Map',exact=True).click();check('official map includes checkpoint and navigation waypoint layers',page.evaluate('baseMarkers.length')==10 and page.evaluate('Object.values(map._layers).filter(layer=>layer instanceof L.CircleMarker).length>20'))
  page.locator('#toolsPanel>summary').click()
  with page.expect_download() as event:page.locator('#downloadGpx').click()
  downloaded=Path(event.value.path());check('download combines full track and official waypoint instructions',event.value.suggested_filename=='canarias360_official_2026.gpx' and hashlib.sha256(downloaded.read_bytes()).hexdigest()==page.evaluate('DATA.gpx_sha256'))
  with page.expect_download() as event:page.locator('#downloadHtml').click()
  path=R/'data/test_official_saved.html';event.value.save_as(str(path));portable=ctx.new_page();portable.goto('http://127.0.0.1:8787/data/test_official_saved.html');portable.wait_for_function('window.RACER_APP')
  check('portable HTML retains same-route progress without a stale migration notice',portable.evaluate('state.progressKm===77.7&&state.routeSha256===DATA.gpx_sha256') and not portable.locator('#routeUpdateNotice').is_visible());portable.close()
  page.reload();page.wait_for_function('window.RACER_APP');check('new route progress survives reload without recurring reset',page.evaluate('state.progressKm===77.7') and not page.locator('#routeUpdateNotice').is_visible())
  page.locator('#progressKm').fill('0');page.locator('#progressKm').blur();page.locator('#pacePanel>summary').click();page.locator('#timingPanel>summary').click();page.locator('#elapsedHours').fill('0');page.locator('#elapsedHours').blur();page.locator('#anchorLive').uncheck();page.locator('#pacePanel>summary').click();page.get_by_role('tab',name='Race',exact=True).click()
  for width in [320,390,844]:
   page.set_viewport_size({'width':width,'height':844 if width<800 else 390});check(f'official panel and instructions fit {width}px',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
  page.set_viewport_size({'width':390,'height':844});page.locator('#nextCheckpoint').screenshot(path=str(R/'docs/official-qa'/f'{engine}-checkpoint.png'));check('no runtime errors throughout official course journeys',not errors)
  runs.append({'browser':engine,'passed':len(cs),'checks':cs});browser.close()
report={'passed':sum(r['passed'] for r in runs),'results':runs,'physical_device_test':False};(R/'docs/official-route-browser-tests.json').write_text(json.dumps(report,indent=2));print(json.dumps({'passed':report['passed']},indent=2))
