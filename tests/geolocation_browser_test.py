"""Exercise live-location controls with browser-provided, simulated GPS fixes."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,os
R=Path(__file__).resolve().parents[1];records=[]
def check(checks,name,value):
 assert value,name
 checks.append(name)
with sync_playwright() as p:
 for engine in ['chromium','webkit']:
  browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox']) if engine=='chromium' else p.webkit.launch(headless=True)
  ctx=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,geolocation={'latitude':28,'longitude':-15.6,'accuracy':8},permissions=['geolocation'])
  requests=[];ctx.on('request',lambda req:requests.append(req.url));ctx.route('**/*',lambda r:r.continue_() if r.request.url.startswith('http://127.0.0.1:8787/') else r.abort())
  ctx.add_init_script('''window.__gpsWatches=0;window.__gpsClears=0;const g=navigator.geolocation,w=g.watchPosition.bind(g),c=g.clearWatch.bind(g);g.watchPosition=(...args)=>{window.__gpsWatches++;return w(...args);};g.clearWatch=(id)=>{window.__gpsClears++;return c(id);};''')
  page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:8787/index.html');page.wait_for_function('window.RACER_APP');checks=[]
  check(checks,'no automatic location request on page load',page.evaluate('window.__gpsWatches')==0)
  page.get_by_role('tab',name='Resupply',exact=True).click()
  check(checks,'resupply offers an opt-in GPS toggle',not page.locator('#location-main').is_checked())
  target=page.evaluate('''()=>{let d=RACER_APP.DATA,i=d.route_km.reduce((best,k,n)=>Math.abs(k-140)<Math.abs(d.route_km[best]-140)?n:best,0);return {km:d.route_km[i],lat:d.route[i][0],lon:d.route[i][1]};}''')
  ctx.set_geolocation({'latitude':target['lat'],'longitude':target['lon'],'accuracy':8})
  page.locator('#location-main').check();page.wait_for_function('RACER_APP.location().usable')
  check(checks,'GPS updates Current km to the projected race position',abs(page.evaluate('RACER_APP.getState().progressKm')-target['km'])<.02)
  check(checks,'global GPS control remains linked in resupply',page.locator('#location-main').is_checked())
  check(checks,'automatic GPS progress is visibly linked',page.locator('#progressKm').get_attribute('readonly') is not None)
  visible=page.evaluate('RACER_APP.filtered().map(p=>p.km)')
  check(checks,'ahead filter removes already-passed resupply points',bool(visible) and min(visible)>=target['km']-.031)
  page.locator('#poiCards details>summary').first.click();text=page.locator('#poiCards').inner_text()
  check(checks,'cards distinguish along-route and straight-line distances','ahead on route' in text and 'straight-line from GPS' in text and 'including the shop approach' in text)
  check(checks,'raw GPS coordinates are not saved in plan storage',page.evaluate('''()=>{let s=JSON.parse(localStorage.getItem('canarias360-roadbook-v2'));return !('fix' in s)&&!('location' in s)&&!('latitude' in s)&&!('longitude' in s);}'''))
  page.get_by_role('tab',name='Map',exact=True).click();page.wait_for_timeout(100)
  check(checks,'actual location marker appears on the map',page.locator('.location-marker').count()==1)
  check(checks,'map can centre on the GPS fix',page.locator('#mapLocateMe').is_enabled());page.locator('#mapLocateMe').click()
  check(checks,'centring uses the actual GPS coordinate',page.evaluate('Math.abs(map.getCenter().lat-'+str(target['lat'])+')<.0001'))
  page.screenshot(path=str(R/'data'/f'location-{engine}-map.png'),full_page=True)
  page.locator('#location-main').uncheck();page.wait_for_function('!RACER_APP.location().enabled')
  check(checks,'off clears the browser watch and global toggle',page.evaluate('window.__gpsClears')>=1 and not page.locator('#location-main').is_checked())
  check(checks,'off removes GPS overlays and restores manual input',page.locator('.location-marker').count()==0 and page.locator('#progressKm').get_attribute('readonly') is None)
  previous=page.evaluate('RACER_APP.getState().progressKm');ctx.set_geolocation({'latitude':target['lat'],'longitude':target['lon'],'accuracy':600});page.locator('#location-main').check();page.wait_for_function('RACER_APP.location().status==="weak"')
  check(checks,'weak accuracy leaves existing route progress unchanged',page.evaluate('RACER_APP.getState().progressKm')==previous)
  ctx.set_geolocation({'latitude':51.5,'longitude':-.1,'accuracy':8});page.wait_for_function('RACER_APP.location().status==="offroute"')
  check(checks,'off-route fixes keep actual GPS position without inventing progress',page.evaluate('RACER_APP.getState().progressKm')==previous and page.evaluate('RACER_APP.location().fix.lat')==51.5)
  check(checks,'off-route resupply explains the manual progress fallback','Resupply uses Current km' in page.locator('[data-location-status]').first.inner_text())
  page.locator('#mapLocateMe').click()
  check(checks,'off-route centring uses the GPS fix rather than the snapped track',page.evaluate('Math.abs(map.getCenter().lat-51.5)<.0001'))
  page.locator('#location-main').uncheck()
  check(checks,'GPS makes no requests beyond forecast and street-map tiles',not [u for u in requests if not u.startswith('http://127.0.0.1:8787/') and not u.startswith('https://api.open-meteo.com/v1/forecast?') and not any(u.startswith('https://'+host+'.tile.openstreetmap.org/') for host in ['a','b','c'])])
  check(checks,'GPS interactions have no runtime errors',not errors)
  ctx.close()
  # Permission-denied UI, with a deterministic asynchronous browser API failure.
  denied=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
  denied.add_init_script('''Object.defineProperty(navigator,'geolocation',{value:{watchPosition(ok,bad){setTimeout(()=>bad({code:1}),0);return 99;},clearWatch(){}}});''')
  d=denied.new_page();d.goto('http://127.0.0.1:8787/index.html');d.wait_for_function('window.RACER_APP');d.get_by_role('tab',name='Resupply',exact=True).click();d.locator('#location-main').click();d.wait_for_function('RACER_APP.location().status==="error"')
  check(checks,'permission denial turns the switch off with an actionable explanation',not d.locator('#location-main').is_checked() and 'permission was denied' in d.locator('[data-location-status]').first.inner_text())
  check(checks,'permission failure preserves the working manual planner',d.evaluate('RACER_APP.getState().progressKm')==0 and d.locator('#poiCards article').count()>0)
  check(checks,'GPS controls fit a phone viewport',d.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
  denied.close();browser.close();records.append({'browser':engine,'passed':len(checks),'checks':checks,'mocked_browser_geolocation':True})
result={'passed':sum(x['passed'] for x in records),'results':records,'physical_device_test':False};(R/'docs/geolocation-browser-tests.json').write_text(json.dumps(result,indent=2));print(json.dumps({'passed':result['passed']},indent=2))
