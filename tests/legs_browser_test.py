"""Leg progress, near-route resupply and mobile GPS journeys with real roadbook data."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json
R=Path(__file__).resolve().parents[1];results=[]
def check(checks,name,value):
 assert value,name
 checks.append(name)
with sync_playwright() as p:
 for engine in ['chromium','webkit']:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']) if engine=='chromium' else p.webkit.launch(headless=True)
  for width in [320,390]:
   ctx=browser.new_context(viewport={'width':width,'height':844},is_mobile=True,has_touch=True,service_workers='block',permissions=['geolocation'],geolocation={'latitude':28,'longitude':-15.6,'accuracy':8})
   ctx.route('**/*',lambda r:r.continue_() if r.request.url.startswith('http://127.0.0.1:8787/') else r.abort())
   page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:8787');page.wait_for_function('window.RACER_APP');checks=[]
   def progress(km):
    page.locator('#progressKm').fill(str(km));page.locator('#progressKm').blur()
   page.get_by_role('tab',name='Legs',exact=True).click()
   check(checks,'all legs retained, exactly one current at the start',page.locator('.leg-card').count()==47 and page.locator('.leg-card[aria-current=step]').get_attribute('data-leg-id')=='0')
   check(checks,'no completed legs at start',page.locator('.leg-card.past').count()==0)
   check(checks,'discreet SVG icons have visible type labels',page.locator('.leg-supply-icons svg').count()>0 and all(label in page.locator('#sectionRows').inner_text() for label in ['Shops','Cafés / meals','Water']))
   check(checks,'resupply details are initially folded',page.locator('.leg-supplies[open]').count()==0)
   first=page.locator('[data-leg-supplies="0"]');first.locator('summary').click()
   check(checks,'details show names, detours, hours and map actions',first.locator('.leg-stops li').count()>0 and 'walk each way' in first.inner_text() and 'Hours unknown' in first.inner_text() and first.locator('[data-action=map]').count()>0)
   check(checks,'stop details have readable text and touch targets',first.locator('button').evaluate_all('es=>es.every(e=>e.getBoundingClientRect().height>=48)') and first.locator('strong').first.evaluate('e=>parseFloat(getComputedStyle(e).fontSize)>=18'))
   progress(5)
   check(checks,'manual progress updates current-leg distance and bar','4.1 km left' in page.locator('.leg-card.current').inner_text() and page.locator('.leg-progress progress').evaluate('e=>e.value>0.54&&e.value<0.56'))
   check(checks,'expanded list survives progress updates',first.evaluate('e=>e.open'))
   check(checks,'passed stops get a route-pass tick without claiming a visit',first.locator('.stop-passed').count()>0 and '✓ Passed on route' in first.inner_text() and 'visited' not in first.inner_text().lower())
   first.locator('summary').focus();page.evaluate('renderSections()')
   check(checks,'focused resupply disclosure survives refresh',page.evaluate('document.activeElement.closest("[data-leg-supplies]")?.dataset.legSupplies')=='0')
   progress(page.evaluate('RACER_APP.DATA.sections[0].to_km'))
   check(checks,'exact leg boundary ticks first and activates second',page.locator('.leg-card.past').count()==1 and page.locator('.leg-card.current').get_attribute('data-leg-id')=='1' and '✓ Complete' in page.locator('.leg-card.past').inner_text())
   progress(140)
   check(checks,'summary completion count agrees with ticks',str(page.locator('.leg-card.past').count())+' / 47 legs complete' in page.locator('#legsProgress').inner_text())
   page.locator('#currentLeg').click()
   check(checks,'jump button reveals the current leg below sticky navigation',75<=page.locator('.leg-card.current').bounding_box()['y']<=90)
   check(checks,'narrow phone layout has no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
   current=page.locator('.leg-card.current');details=current.locator('.leg-supplies')
   if details.count():details.locator('summary').click()
   check(checks,'expanded phone layout fits screen',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
   if width==390:
    page.locator('#currentLeg').click();page.screenshot(path=str(R/'docs/screenshots'/f'legs-{engine}.png'))
   # A real route coordinate delivered through the browser API must update the same leg state.
   target=page.evaluate('''()=>{const d=RACER_APP.DATA,i=d.route_km.reduce((best,k,n)=>Math.abs(k-140.4)<Math.abs(d.route_km[best]-140.4)?n:best,0);return {km:d.route_km[i],lat:d.route[i][0],lon:d.route[i][1]};}''')
   ctx.set_geolocation({'latitude':target['lat'],'longitude':target['lon'],'accuracy':8});page.locator('#location-main').check();page.wait_for_function('RACER_APP.location().usable')
   check(checks,'GPS automatically updates current leg and remaining distance',abs(page.evaluate('RACER_APP.getState().progressKm')-target['km'])<.02 and page.locator('.leg-card.current').count()==1 and page.locator('.leg-progress').is_visible())
   page.locator('#location-main').uncheck();progress(5)
   check(checks,'correcting progress backwards clears later completion ticks',page.locator('.leg-card.past').count()==0 and page.locator('.leg-card.current').get_attribute('data-leg-id')=='0')
   progress(page.evaluate('RACER_APP.DATA.distance_km'))
   check(checks,'finish ticks all legs and removes active leg',page.locator('.leg-card.past').count()==47 and page.locator('.leg-card.current').count()==0 and 'Race finished' in page.locator('#legsProgress').inner_text())
   page.locator('#currentLeg').click()
   check(checks,'finish jump button reveals final leg',75<=page.locator('.leg-card').last.bounding_box()['y']<700)
   progress(5);page.reload();page.wait_for_function('window.RACER_APP');page.get_by_role('tab',name='Legs',exact=True).click()
   check(checks,'progress state survives reload without starting GPS',page.locator('.leg-card.current').get_attribute('data-leg-id')=='0' and '4.1 km left' in page.locator('.leg-card.current').inner_text() and not page.locator('#location-main').is_checked())
   page.locator('[data-leg-supplies="0"]>summary').click();page.locator('[data-leg-supplies="0"] [data-action=map]').first.click()
   check(checks,'leg resupply map action selects its real POI',page.locator('#nav-map').get_attribute('aria-selected')=='true' and page.locator('#mapSelection .poi-card').count()==1)
   check(checks,'no runtime errors during leg journeys',not errors)
   results.append({'browser':engine,'width':width,'passed':len(checks),'checks':checks});ctx.close()
  browser.close()
report={'passed':sum(r['passed'] for r in results),'results':results};(R/'docs/legs-browser-tests.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
