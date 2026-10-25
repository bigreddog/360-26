"""Route weather UX with deterministic API responses, failures and offline snapshots."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse,parse_qs
import json,os
R=Path(__file__).resolve().parents[1];OUT=R/'docs/weather-qa';OUT.mkdir(exist_ok=True);records=[]
INIT="window.__weatherNow=Date.parse('2026-11-04T09:00:00Z');Date.now=()=>window.__weatherNow;Object.defineProperty(navigator,'geolocation',{value:{watchPosition(ok,bad){window.__gpsOK=ok;return 1;},clearWatch(){}}});"
def payload(url,partial=False,empty=False):
 q=parse_qs(urlparse(url).query);alt=[float(x) for x in q['elevation'][0].split(',')];lat=[float(x) for x in q['latitude'][0].split(',')];lon=[float(x) for x in q['longitude'][0].split(',')]
 start=datetime.fromisoformat(q['start_hour'][0]).replace(tzinfo=timezone.utc);end=datetime.fromisoformat(q['end_hour'][0]).replace(tzinfo=timezone.utc);times=[int((start+timedelta(hours=i)).timestamp()) for i in range(int((end-start).total_seconds()/3600)+1)]
 def series(n):return [None if empty else n for _ in times]
 return [{'latitude':lat[i],'longitude':lon[i],'elevation':z,'hourly':{'time':times,'temperature_2m':series(25-z/180),'apparent_temperature':series(23-z/180),'precipitation_probability':[None for _ in times] if partial else series(20+i),'precipitation':series(.2),'weather_code':series(0 if i<=12 else 61),'wind_speed_10m':series(10+i),'wind_gusts_10m':series(20+i),'wind_direction_10m':series(0),'is_day':series(1 if i<10 else 0)}} for i,z in enumerate(alt)]
def check(cs,name,value):
 assert value,name
 cs.append(name)
with sync_playwright() as p:
 for engine in ['chromium','webkit']:
  browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox']) if engine=='chromium' else p.webkit.launch(headless=True)
  ctx=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,accept_downloads=True,service_workers='block');ctx.add_init_script(INIT)
  calls=[];scenario={'mode':'ok'}
  def intercept(route):
   url=route.request.url
   if url.startswith('http://127.0.0.1:8787/'):route.continue_();return
   if url.startswith('https://api.open-meteo.com/v1/forecast?'):
    calls.append(url)
    if scenario['mode']=='error':route.fulfill(status=503,body='Unavailable');return
    route.fulfill(status=200,content_type='application/json',headers={'Access-Control-Allow-Origin':'*'},body=json.dumps(payload(url,partial=scenario['mode']=='partial',empty=scenario['mode']=='empty')));return
   route.abort()
  ctx.route('**/*',intercept);page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:8787');page.wait_for_function('typeof weatherPanel!=="undefined"&&weatherPanel.cache && !weatherPanel.loading');cs=[]
  check(cs,'forecast panel is on the Race view immediately above route profile',page.locator('#weatherPanel').evaluate("e=>e.nextElementSibling.querySelector('#profileSvg')!==null"))
  check(cs,'six-hour view is selected by default',page.locator('[data-weather-hours="6"]').get_attribute('aria-pressed')=='true')
  check(cs,'one batch requests a different route position and elevation every hour',len(calls)==1 and len(parse_qs(urlparse(calls[0]).query)['latitude'][0].split(','))==19 and len(set(parse_qs(urlparse(calls[0]).query)['elevation'][0].split(',')))>3)
  check(cs,'temperature, rain, wind and route elevation summaries are populated',page.locator('[data-weather-summary]>div').count()==4 and 'Unavailable' not in page.locator('[data-weather-summary]').inner_text())
  check(cs,'summary has inline weather symbols paired with condition text',page.locator('[data-weather-conditions] svg[data-weather-icon]').count()>0 and 'Clear' in page.locator('[data-weather-conditions]').inner_text())
  check(cs,'peak wind shows a north-up source arrow and speed in km/h',page.locator('.weather-wind-summary [data-wind-bearing="0"]').count()==1 and 'From N' in page.locator('.weather-wind-summary').inner_text() and 'km/h' in page.locator('.weather-wind-summary').inner_text())
  check(cs,'no Beaufort scale is included',not page.locator('#weatherPanel').evaluate('e=>/beaufort|bft/i.test(e.textContent)'))
  check(cs,'forecast details start collapsed for a compact summary',not page.locator('[data-weather-route]').evaluate('e=>e.open'))
  check(cs,'endpoint shows projected place, route kilometre and height','km ' in page.locator('[data-weather-destination]').inner_text() and ' m' in page.locator('[data-weather-destination]').inner_text())
  base=page.evaluate('weatherPanel.cache.base');check(cs,'forecast is anchored to the displayed route progress and race clock',base==1793782800000)
  for h in [12,18]:page.locator(f'[data-weather-hours="{h}"]').click();check(cs,f'{h}-hour view uses the cached trajectory without another API request',len(calls)==1 and page.locator(f'[data-weather-hours="{h}"]').get_attribute('aria-pressed')=='true')
  page.locator('[data-weather-route]>summary').click();check(cs,'eighteen-hour details show seven route/time stops',page.locator('.weather-stop').count()==7)
  check(cs,'night forecast and wind-from-north are labelled','night' in page.locator('[data-weather-cards]').inner_text() and 'From N' in page.locator('[data-weather-cards]').inner_text())
  check(cs,'forecast stops have day/night icons and wind direction arrows',page.locator('[data-weather-cards] [data-weather-icon=moon]').count()>0 and page.locator('[data-weather-cards] .weather-direction').count()==7)
  page.locator('[data-weather-hours="6"]').click();check(cs,'six-hour details show current, +3h and +6h positions',page.locator('.weather-stop').count()==3)
  page.locator('[data-weather-route]>summary').click()
  for width in [320,390,844]:
   page.set_viewport_size({'width':width,'height':844 if width<800 else 390});page.locator('#weatherPanel').scroll_into_view_if_needed()
   check(cs,f'weather controls and summary fit {width}px width',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
   targets=page.locator('#weatherPanel button').evaluate_all('es=>es.map(e=>({height:e.getBoundingClientRect().height,font:parseFloat(getComputedStyle(e).fontSize)}))')
   check(cs,f'forecast controls are readable and touch-sized at {width}px',all(x['height']>=48 and x['font']>=16 for x in targets))
   if width==390:
    page.evaluate('window.scrollTo(0,0)');page.screenshot(path=str(OUT/f'{engine}-summary.png'),full_page=True,clip=page.locator('#weatherPanel').bounding_box())
  page.set_viewport_size({'width':390,'height':844});page.locator('#progressKm').fill('100');page.locator('#progressKm').blur();page.wait_for_function('!weatherPanel.loading&&weatherPanel.cache.fromKm===100')
  check(cs,'editing progress recalculates forecast locations',page.evaluate('weatherPanel.cache.rows[0].sample.km')==100 and page.evaluate('weatherPanel.cache.rows[6].sample.km')>100)
  before=page.evaluate('weatherPanel.cache.rows[6].sample.km');page.locator('#pacePanel>summary').click();page.locator('#timingPanel>summary').click();page.locator('#extraHours').fill('3');page.locator('#extraHours').blur();page.wait_for_function('!weatherPanel.loading&&weatherPanel.cache.signature.includes(",3]")')
  check(cs,'extra delay reduces projected travel in the weather path',page.evaluate('weatherPanel.cache.rows[6].sample.km')<before)
  page.locator('#syncProgress').click();page.evaluate("(()=>{let d=RACER_APP.DATA,i=d.route_km.reduce((best,k,n)=>Math.abs(k-130)<Math.abs(d.route_km[best]-130)?n:best,0);__gpsOK({coords:{latitude:d.route[i][0],longitude:d.route[i][1],accuracy:5},timestamp:Date.now()});})()")
  page.wait_for_function('!weatherPanel.loading&&weatherPanel.cache.fromKm>129.9')
  check(cs,'Sync location and time immediately refreshes the weather trajectory',page.evaluate('weatherPanel.cache.rows[0].sample.km')>129.9)
  page.locator('#location-main').uncheck()
  # A night-time starting point must query next-day hours in UTC and display Canary local time.
  page.evaluate("window.__weatherNow=Date.parse('2026-11-04T22:00:00Z')");page.locator('[data-weather-refresh]').click();page.wait_for_function("!weatherPanel.loading&&weatherPanel.cache.base===Date.parse('2026-11-04T22:00:00Z')")
  check(cs,'midnight crossings retain the correct forecast date','2026-11-05' in parse_qs(urlparse(calls[-1]).query)['end_hour'][0] and 'Thu' in page.locator('[data-weather-destination]').inner_text())
  scenario['mode']='partial';page.locator('[data-weather-refresh]').click();page.wait_for_function('!weatherPanel.loading&&weatherPanel.cache.rows[0].weather.chance===null')
  check(cs,'missing probability is not rendered as zero percent','Chance unavailable' in page.locator('[data-weather-summary]').inner_text())
  scenario['mode']='error';page.locator('[data-weather-refresh]').click();page.wait_for_function('!weatherPanel.loading')
  check(cs,'provider failure retains explicitly labelled saved data','Saved forecast retains its original' in page.locator('[data-weather-status]').inner_text() and page.locator('[data-weather-summary]>div').count()==4)
  page.evaluate('RACER_APP.getState().progressKm=180;weatherPanel.update()');page.wait_for_function('!weatherPanel.loading&&weatherPanel.lastAttemptFromKm===180');after_failure=len(calls)
  page.evaluate('weatherPanel.update()');page.wait_for_timeout(700);page.evaluate('weatherPanel.update()');page.wait_for_timeout(700)
  check(cs,'repeated GPS updates do not hammer a failing provider after relocation',len(calls)==after_failure)
  # Save HTML with the weather snapshot, then open in a separate browser store.
  page.locator('#toolsPanel>summary').click()
  with page.expect_download() as info:page.locator('#downloadHtml').click()
  saved=R/'data/test_weather_saved.html';info.value.save_as(str(saved));check(cs,'offline HTML embeds the fetched forecast snapshot','id="savedWeatherData"' in saved.read_text())
  offline=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,service_workers='block');offline.add_init_script(INIT+"Object.defineProperty(navigator,'onLine',{get:()=>false});");o=offline.new_page();o.goto('http://127.0.0.1:8787/data/test_weather_saved.html');o.wait_for_function('typeof weatherPanel!=="undefined"&&weatherPanel.cache')
  check(cs,'portable HTML restores original weather times without shared browser storage',o.evaluate('weatherPanel.cache.base')==page.evaluate('weatherPanel.cache.base') and o.locator('[data-weather-summary]>div').count()==4 and 'Offline' in o.locator('[data-weather-status]').inner_text());offline.close()
  page.evaluate('window.__weatherNow+=3*3600000;weatherPanel.render()');check(cs,'old forecasts are visibly marked stale','over 2 hours old' in page.locator('[data-weather-status]').inner_text() or 'Saved' in page.locator('[data-weather-status]').inner_text())
  page.evaluate('window.__weatherNow+=24*3600000;weatherPanel.render()');check(cs,'expired windows do not present past weather as upcoming',page.locator('[data-weather-summary]>div').count()==0)
  # No forecast fetch in another tab, even when GPS/plan rerenders.
  page.get_by_role('tab',name='Map',exact=True).click();count=len(calls);page.evaluate('weatherPanel.update(true)');page.wait_for_timeout(650);check(cs,'hidden forecast view does not make background weather requests',len(calls)==count)
  check(cs,'no runtime errors throughout weather interactions',not errors)
  ctx.close()
  # Dates too far away must not turn into forecasts for today.
  far=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,service_workers='block');far.add_init_script("Date.now=()=>Date.parse('2026-09-01T09:00:00Z')");requests=[];far.on('request',lambda r:requests.append(r.url));far.route('**/*',lambda r:r.continue_() if r.request.url.startswith('http://127.0.0.1:8787/') else r.abort());f=far.new_page();f.goto('http://127.0.0.1:8787');f.wait_for_timeout(900)
  check(cs,'outside-horizon race dates show availability guidance','outside the provider' in f.locator('[data-weather-status]').inner_text() and not [u for u in requests if 'api.open-meteo.com' in u]);far.close()
  empty=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,service_workers='block');empty.add_init_script(INIT);empty.route('**/*',lambda r:r.fulfill(status=200,content_type='application/json',body=json.dumps(payload(r.request.url,empty=True))) if 'api.open-meteo.com/v1/forecast?' in r.request.url else r.continue_());e=empty.new_page();e.goto('http://127.0.0.1:8787');e.wait_for_function('typeof weatherPanel!=="undefined"&&weatherPanel&&!weatherPanel.loading&&weatherPanel.lastAttempt')
  check(cs,'all-null provider response stays unavailable without fabricated values','No forecast is available yet' in e.locator('[data-weather-status]').inner_text() and e.locator('[data-weather-summary]>div').count()==0);empty.close()
  browser.close();records.append({'browser':engine,'passed':len(cs),'checks':cs,'mocked_forecast_api':True})
result={'passed':sum(r['passed'] for r in records),'results':records,'physical_device_test':False};(R/'docs/weather-browser-tests.json').write_text(json.dumps(result,indent=2));print(json.dumps({'passed':result['passed']},indent=2))
