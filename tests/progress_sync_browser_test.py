"""Test opt-in GPS + race-clock synchronization with deterministic API callbacks."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,os
R=Path(__file__).resolve().parents[1];records=[]
def check(cs,name,ok):
 assert ok,name
 cs.append(name)
with sync_playwright() as p:
 for engine in ['chromium','webkit']:
  browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox']) if engine=='chromium' else p.webkit.launch(headless=True)
  ctx=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
  ctx.route('**/*',lambda r:r.continue_() if r.request.url.startswith('http://127.0.0.1:8787/') else r.abort())
  ctx.add_init_script('''window.__raceNow=Date.parse('2026-11-04T08:00:00Z');Date.now=()=>window.__raceNow;window.__watches=0;window.__clears=0;
  Object.defineProperty(navigator,'geolocation',{value:{watchPosition(ok,bad){window.__watches++;window.__ok=ok;window.__bad=bad;return 123;},clearWatch(){window.__clears++;}}});
  window.__emitFix=(km,accuracy=8)=>{const d=RACER_APP.DATA,i=d.route_km.reduce((best,k,n)=>Math.abs(k-km)<Math.abs(d.route_km[best]-km)?n:best,0);window.__ok({coords:{latitude:d.route[i][0],longitude:d.route[i][1],accuracy},timestamp:Date.now()});};''')
  page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:8787');page.wait_for_function('window.RACER_APP');cs=[]
  check(cs,'clock and GPS do not auto-start',page.evaluate('window.__watches')==0 and not page.evaluate('RACER_APP.getState().anchorLive'))
  page.locator('#syncProgress').click()
  check(cs,'one tap requests GPS and explains pending sync',page.evaluate('window.__watches')==1 and 'Waiting for an accurate' in page.locator('#syncStatus').inner_text())
  check(cs,'waiting for GPS does not change manual progress or elapsed time',page.evaluate('RACER_APP.getState().progressKm===0&&RACER_APP.getState().elapsedHours===0'))
  page.evaluate('__emitFix(140)');page.wait_for_function('RACER_APP.location().usable')
  check(cs,'pre-race sync preserves Wednesday start with a clear explanation',not page.evaluate('RACER_APP.getState().anchorLive') and page.evaluate('RACER_APP.getState().elapsedHours')==0 and 'Race has not started' in page.locator('#syncStatus').inner_text())
  # Race time is 36 hours after Wednesday 09:00, independent of local device timezone.
  page.evaluate("window.__raceNow=Date.parse('2026-11-05T21:00:00Z');__emitFix(140)")
  st=page.evaluate('RACER_APP.getState()')
  check(cs,'live sync sets actual elapsed race hours',st['elapsedHours']==36 and st['anchorLive'])
  check(cs,'live sync uses the real ordered route position',abs(st['progressKm']-140)<.1)
  check(cs,'ETA at current route position equals the current clock',page.evaluate('RACER_APP.E.timing(RACER_APP.DATA,RACER_APP.getState().progressKm,RACER_APP.getState())')==36)
  check(cs,'live status confirms linked location and time','Location & time linked' in page.locator('#syncStatus').inner_text())
  page.get_by_role('tab',name='Resupply',exact=True).click();first=page.evaluate('RACER_APP.filtered()[0]')
  check(cs,'resupply only includes positions ahead of live progress',first['km']>=st['progressKm']-.03)
  check(cs,'resupply arrivals use current clock rather than original schedule',page.evaluate('''()=>{const d=RACER_APP.DATA,s=RACER_APP.getState(),p=RACER_APP.filtered()[0];return RACER_APP.E.arrival(d,p,s).h>=s.elapsedHours;}'''))
  detail=page.locator('#poiCards details').first;detail.locator('summary').click();place=detail.locator('xpath=..').get_attribute('data-place')
  page.evaluate("window.__raceNow+=3600000;__emitFix(140.02)")
  check(cs,'next fix keeps clock synchronized without another click',page.evaluate('RACER_APP.getState().elapsedHours')==37)
  check(cs,'live refresh preserves expanded stop details',page.locator('#poiCards [data-place="'+place+'"] details').evaluate('e=>e.open'))
  prev=page.evaluate('RACER_APP.getState().elapsedHours');page.evaluate('window.__raceNow+=3600000;__emitFix(141,600)')
  check(cs,'poor GPS cannot overwrite elapsed-time and position anchor',page.evaluate('RACER_APP.getState().elapsedHours')==prev and page.evaluate('RACER_APP.location().status')=='weak')
  page.evaluate('__emitFix(141)')
  check(cs,'accurate recovery updates progress and clock together',page.evaluate('RACER_APP.getState().elapsedHours')==38 and abs(page.evaluate('RACER_APP.getState().progressKm')-141)<.1)
  page.locator('#location-main').uncheck();prev=page.evaluate('RACER_APP.getState()');page.evaluate('window.__raceNow+=3600000;__emitFix(142)')
  check(cs,'switching GPS off freezes the last verified time and km',page.evaluate('RACER_APP.getState()')==prev and page.evaluate('window.__clears')==1)
  check(cs,'frozen anchor is explained','last progress' in page.locator('#syncStatus').inner_text())
  page.locator('#syncProgress').click();page.evaluate('__bad({code:1})')
  check(cs,'permission denial cancels pending sync and restores button',page.locator('#syncProgress').is_enabled() and not page.locator('#location-main').is_checked() and 'permission was denied' in page.locator('[data-location-status]').inner_text())
  page.locator('#syncProgress').click();page.evaluate('__emitFix(142)')
  check(cs,'one-tap retry recovers from permission failure',page.evaluate('RACER_APP.getState().elapsedHours')==39)
  page.locator('#pacePanel>summary').click();page.locator('#timingPanel>summary').click();page.locator('#elapsedHours').fill('40.5');page.locator('#elapsedHours').blur();page.evaluate('window.__raceNow+=3600000;__emitFix(142)')
  check(cs,'manual elapsed-time edit ends automatic clock linkage',page.evaluate('RACER_APP.getState().elapsedHours')==40.5)
  page.locator('#syncProgress').click();check(cs,'sync button restores automatic anchoring',page.evaluate('RACER_APP.getState().elapsedHours')==40)
  page.evaluate('window.__raceNow+=180000');page.locator('#syncProgress').click()
  check(cs,'sync checks freshness after a suspended tab instead of reusing an old fix',page.evaluate('RACER_APP.location().status')=='stale' and page.evaluate('RACER_APP.getState().elapsedHours')==40 and 'Waiting for an accurate' in page.locator('#syncStatus').inner_text())
  page.evaluate('__emitFix(142)')
  check(cs,'fresh position completes a pending sync after stale data',abs(page.evaluate('RACER_APP.getState().elapsedHours')-40.05)<.0001)
  # After the 101-hour cutoff, do not reset the race clock or suggest a new start.
  page.evaluate("window.__raceNow=Date.parse('2026-11-08T15:00:00Z');__emitFix(253)")
  check(cs,'post-cutoff progress shows actual elapsed time and a late finish',page.evaluate('RACER_APP.getState().elapsedHours')==102 and 'late' in page.locator('#finishMargin').inner_text())
  page.evaluate("window.__raceNow=Date.parse('2026-11-10T15:00:00Z');__emitFix(253)")
  check(cs,'race clock is not silently capped at the old 130-hour input limit',page.evaluate('RACER_APP.getState().elapsedHours')==150)
  stored=page.evaluate("JSON.parse(localStorage.getItem('canarias360-roadbook-v2'))")
  check(cs,'only plan fields are persisted, never raw fixes or an auto-start flag',set(stored)=={'quotas','progressKm','elapsedHours','anchorLive','extraHours','terrainWeight','vision'})
  page.reload();page.wait_for_function('window.RACER_APP')
  check(cs,'reopening keeps last anchor without restarting tracking',not page.locator('#location-main').is_checked() and page.evaluate('window.__watches')==0 and page.evaluate('RACER_APP.getState().elapsedHours')==150)
  check(cs,'sync flows have no script errors',not errors)
  ctx.close();browser.close();records.append({'browser':engine,'passed':len(cs),'checks':cs,'simulated_time_and_gps':True})
result={'passed':sum(x['passed'] for x in records),'physical_device_test':False,'results':records};(R/'docs/progress-sync-browser-tests.json').write_text(json.dumps(result,indent=2));print(json.dumps({'passed':result['passed']},indent=2))
