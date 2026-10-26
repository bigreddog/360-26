"""Integrated Trail Vision tests: simulated browser APIs, real embedded GPX, no network."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import hashlib,json,os
R=Path(__file__).resolve().parents[1];records=[];OUT=R/'docs/vision-qa';OUT.mkdir(exist_ok=True)
INIT=r'''
window.__watches=0;window.__clears=0;window.__orientationPermissions=0;window.__cameraRequests=0;
Object.defineProperty(navigator,'geolocation',{value:{watchPosition(ok,bad){window.__watches++;window.__gpsOK=ok;window.__gpsBad=bad;return window.__watches;},clearWatch(){window.__clears++;}}});
if(window.DeviceOrientationEvent)Object.defineProperty(DeviceOrientationEvent,'requestPermission',{configurable:true,value:()=>{window.__orientationPermissions++;window.__gesture=navigator.userActivation?.isActive??true;return Promise.resolve(window.__denyOrientation?'denied':'granted');}});
if(window.DeviceMotionEvent)Object.defineProperty(DeviceMotionEvent,'requestPermission',{configurable:true,value:()=>Promise.resolve('granted')});
if(navigator.mediaDevices)navigator.mediaDevices.getUserMedia=()=>{window.__cameraRequests++;throw Error('Camera must never be requested');};
const getContext=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){if(type.includes('webgl'))return null;return getContext.call(this,type,...args);};
window.__sendGPS=(km,accuracy=8)=>{const d=RACER_APP.DATA,j=Math.max(1,d.route_km.findIndex(k=>k>=km)),i=j-1,f=(km-d.route_km[i])/(d.route_km[j]-d.route_km[i]);window.__gpsOK({coords:{latitude:d.route[i][0]+f*(d.route[j][0]-d.route[i][0]),longitude:d.route[i][1]+f*(d.route[j][1]-d.route[i][1]),accuracy},timestamp:Date.now()});};
window.__pose=(heading,pitch=0,accuracy=null,ios=false)=>{const e=new Event(ios?'deviceorientation':'deviceorientationabsolute');Object.assign(e,{alpha:(360-heading)%360,beta:90+pitch,gamma:0,absolute:!ios});if(ios){e.webkitCompassHeading=heading;e.webkitCompassAccuracy=accuracy;}window.dispatchEvent(e);};
'''
def check(cs,name,ok):
 assert ok,name
 cs.append(name)
def setup(browser,width=390,extra=''):
 ctx=browser.new_context(viewport={'width':width,'height':844},is_mobile=True,has_touch=True,accept_downloads=True)
 requests=[];ctx.on('request',lambda r:requests.append(r.url));ctx.route('**/*',lambda r:r.continue_() if r.request.url.startswith('http://127.0.0.1:8787/') else r.abort());ctx.add_init_script(INIT+extra)
 page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:8787');page.wait_for_function('window.RACER_APP');return ctx,page,errors,requests
def open_vision(page):
 page.get_by_role('tab',name='Map',exact=True).click();page.locator('#openTrailVision').click();page.wait_for_function('RACER_APP.vision()?.active')
with sync_playwright() as p:
 for engine in ['chromium','webkit']:
  browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox']) if engine=='chromium' else p.webkit.launch(headless=True)
  ctx,page,errors,requests=setup(browser);cs=[]
  check(cs,'Trail Vision never starts sensors on page load',page.evaluate('__watches')==0)
  page.locator('#progressKm').fill('140');page.locator('#progressKm').blur();open_vision(page)
  check(cs,'map action opens integrated fullscreen dialog',page.locator('#trailVision').is_visible() and page.locator('#trailVision').bounding_box()['width']==390)
  check(cs,'compass is default with 500m and 1x true scale',page.evaluate('RACER_APP.vision().preferences')=={'lookAhead':500,'exaggeration':1,'mode':'compass','manualHeading':0})
  page.wait_for_function('__orientationPermissions===1')
  check(cs,'orientation permission is requested within a user gesture',page.evaluate('__gesture'))
  check(cs,'location permission/watch is requested once',page.evaluate('__watches')==1)
  page.evaluate('__sendGPS(140)');page.wait_for_function('RACER_APP.vision().match!==null')
  check(cs,'real GPX and GPS determine start and exact 500m preview',abs(page.evaluate('RACER_APP.vision().match.distance')-140000)<30 and page.evaluate('RACER_APP.vision().available')==500)
  check(cs,'only the local route window is resampled for rendering',len(page.evaluate('RACER_APP.vision().geometry'))<=102)
  check(cs,'actual GPX elevations are used',page.evaluate('RACER_APP.vision().elevationOK') and page.evaluate('RACER_APP.vision().stats.ascent')>0)
  bearing=page.evaluate('TrailVisionCore.bearing(trailVision.window.origin,trailVision.window.points[6])')
  page.evaluate('h=>{for(let i=0;i<6;i++)__pose(h);}',bearing);page.wait_for_timeout(500)
  check(cs,'stable absolute readings become Good',page.evaluate('RACER_APP.vision().quality')=='Good')
  check(cs,'unverified north is labelled without claiming true north','unverified' in page.locator('[data-vision=heading]').inner_text())
  geometry=page.evaluate('JSON.stringify(RACER_APP.vision().geometry)');image1=page.locator('[data-vision=canvas]').evaluate('c=>c.toDataURL()')
  page.screenshot(path=str(OUT/f'{engine}-compass.png'))
  page.set_viewport_size({'width':844,'height':390});page.wait_for_timeout(100);page.evaluate('h=>{for(let i=0;i<6;i++)__pose(h);}',bearing);page.wait_for_timeout(200)
  check(cs,'landscape layout keeps the view and controls within the screen',page.locator('#trailVision').evaluate('e=>e.scrollWidth<=innerWidth+1') and page.locator('[data-vision=canvas]').bounding_box()['width']>800)
  page.screenshot(path=str(OUT/f'{engine}-landscape.png'));page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(100);page.evaluate('h=>{for(let i=0;i<6;i++)__pose(h);}',bearing);page.wait_for_timeout(200)
  page.evaluate('__pose('+str((bearing+90)%360)+')');page.wait_for_timeout(700)
  check(cs,'turning the simulated phone changes the projected image',page.locator('[data-vision=canvas]').evaluate('c=>c.toDataURL()')!=image1)
  check(cs,'turning the phone leaves world route geometry unchanged',page.evaluate('JSON.stringify(RACER_APP.vision().geometry)')==geometry)
  check(cs,'outside-field-of-view direction is indicated','right' in page.locator('[data-vision=direction]').inner_text() or 'left' in page.locator('[data-vision=direction]').inner_text())
  page.evaluate('__pose('+str((bearing+180)%360)+')');page.wait_for_timeout(700)
  check(cs,'looking away indicates the route is behind','behind' in page.locator('[data-vision=direction]').inner_text())
  page.evaluate('__pose('+str(bearing)+',30)');page.wait_for_timeout(700)
  check(cs,'physical phone tilt changes world pitch',abs(page.evaluate('trailVision.cameraPose().pitch')-30)<1)
  page.evaluate('__pose(123,0,60,true)');page.wait_for_timeout(300)
  check(cs,'iOS compass heading is explicitly labelled magnetic','Magnetic north' in page.locator('[data-vision=heading]').inner_text())
  check(cs,'reported poor sensor quality suggests calibration',page.evaluate('RACER_APP.vision().quality')=='Calibration suggested' and page.locator('[data-vision=compassWarning]').is_visible())
  page.locator('[data-vision=options]>summary').click();page.locator('[data-vision=help]').click()
  check(cs,'help explains figure-eight and inability to calibrate sensors','figure-eight' in page.locator('[data-vision=helpText]').inner_text() and 'cannot calibrate' in page.locator('[data-vision=helpText]').inner_text())
  page.locator('[data-vision=mode]').select_option('manual');page.locator('[data-vision=manualHeading]').fill('220');page.locator('[data-vision=manualHeading]').dispatch_event('change')
  check(cs,'manual fallback is an explicit labelled choice',page.evaluate('RACER_APP.vision().mode')=='manual' and page.locator('[data-vision=modeLabel]').inner_text()=='Manual heading' and '220°' in page.locator('[data-vision=heading]').inner_text())
  page.locator('[data-vision=lookAhead]').select_option('1000');page.locator('[data-vision=exaggeration]').select_option('2')
  check(cs,'lookahead and vertical scale controls update preview and label',page.evaluate('RACER_APP.vision().available')==1000 and '2×' in page.locator('[data-vision=ahead]').inner_text())
  check(cs,'vertical exaggeration does not multiply reported ascent',abs(page.evaluate('RACER_APP.vision().stats.ascent')-page.evaluate('TrailVisionCore.windowRoute(trailVision.route,trailVision.match.s,1000,trailVision.match.segment).stats.ascent'))<.001)
  page.locator('[data-vision=mode]').select_option('route');check(cs,'route-following is explicit and labelled','Follow route' in page.locator('[data-vision=modeLabel]').inner_text())
  page.evaluate('trailVision.offsetYaw=40;trailVision.offsetPitch=10');page.locator('[data-vision=recenter]').click()
  check(cs,'Recenter clears offsets without altering compass reading',page.evaluate('trailVision.offsetYaw===0&&trailVision.offsetPitch===0&&RACER_APP.vision().heading===123'))
  before=page.evaluate('RACER_APP.vision().match.distance');page.evaluate('__sendGPS(140,600)')
  check(cs,'weak GPS preserves last matched progress',page.evaluate('RACER_APP.vision().match.distance')==before and 'too poor' in page.locator('[data-vision=gpsStatus]').inner_text())
  page.evaluate('__gpsOK({coords:{latitude:51.5,longitude:-.1,accuracy:8},timestamp:Date.now()})')
  check(cs,'off-route warning preserves route origin',page.evaluate('RACER_APP.vision().match.distance')==before and 'Off route' in page.locator('[data-vision=gpsStatus]').inner_text())
  page.evaluate('__sendGPS(140.02)');check(cs,'fresh plausible GPS moves virtual viewpoint',page.evaluate('RACER_APP.vision().match.distance')!=before)
  previous=page.evaluate('RACER_APP.vision().match.distance');page.evaluate('__gpsBad({code:3})')
  check(cs,'temporary GPS loss is explained without resetting progress','timed out' in page.locator('[data-vision=gpsStatus]').inner_text() and page.evaluate('RACER_APP.vision().match.distance')==previous)
  page.locator('[data-vision=options]>summary').click();page.wait_for_timeout(700);frames=page.evaluate('RACER_APP.vision().frames');page.wait_for_timeout(250)
  check(cs,'rendering goes idle when pose and GPS stop changing',page.evaluate('RACER_APP.vision().frames')==frames)
  page.locator('[data-vision=exit]').click();frames=page.evaluate('RACER_APP.vision().frames');page.evaluate('__pose(0)');page.wait_for_timeout(150)
  check(cs,'exit stops view-owned GPS watch and orientation listeners',page.evaluate('__clears')==1 and not page.evaluate('RACER_APP.vision().sensorAttached') and not page.evaluate('RACER_APP.location().enabled'))
  check(cs,'exit cancels animation work',page.evaluate('RACER_APP.vision().frames')==frames and not page.evaluate('RACER_APP.vision().active'))
  check(cs,'normal offline map remains available',page.locator('#map .leaflet-map-pane').count()==1)
  # Preference persistence and a pre-existing GPS watch are separate from feature ownership.
  page.locator('#location-main').check();clears=page.evaluate('__clears');watches=page.evaluate('__watches');page.locator('#openTrailVision').click()
  check(cs,'opening reuses an already enabled GPS watch',page.evaluate('__watches')==watches and not page.evaluate('RACER_APP.vision().ownsGPS'))
  check(cs,'view preferences persist through the existing plan settings',page.evaluate('RACER_APP.vision().preferences.exaggeration')==2 and page.evaluate('RACER_APP.vision().preferences.lookAhead')==1000)
  page.locator('[data-vision=exit]').click();check(cs,'closing preserves GPS independently enabled by the racer',page.evaluate('RACER_APP.location().enabled') and page.evaluate('__clears')==clears)
  page.locator('#location-main').uncheck();page.locator('#openTrailVision').click();page.locator('[data-vision=previewOffline]').click()
  page.locator('[data-vision=options]>summary').click();page.locator('[data-vision=file]').set_input_files(str(R/'tests/fixtures/trail-vision-synthetic.gpx'));page.wait_for_function('trailVision.uploaded')
  check(cs,'GPX import uses the actual synthetic fixture for preview',page.evaluate('trailVision.route.distance')<2000 and page.evaluate('RACER_APP.vision().elevationOK'))
  check(cs,'simulation is unmistakably labelled and releases live sensors','SIMULATION' in page.locator('[data-vision=modeLabel]').inner_text() and not page.evaluate('RACER_APP.vision().sensorAttached'))
  check(cs,'synthetic sharp bends and sustained climb are present',page.evaluate('RACER_APP.vision().stats.ascent')>20 and max(p[0] for p in page.evaluate('RACER_APP.vision().geometry'))>60)
  page.locator('[data-vision=lookAhead]').select_option('500');page.locator('[data-vision=exaggeration]').select_option('1');page.locator('[data-vision=mode]').select_option('compass');page.evaluate('trailVision.simulate({heading:0,pitch:0,distance:0})');page.locator('[data-vision=options]>summary').click();page.wait_for_timeout(500);page.screenshot(path=str(OUT/f'{engine}-synthetic.png'))
  # Local XML uploads are parsed with DOMParser; segment boundaries and missing elevation are preserved.
  multi=b'<gpx version="1.1"><trk><trkseg><trkpt lat="28" lon="-15.6"/><trkpt lat="28.0009" lon="-15.6"/></trkseg><trkseg><trkpt lat="28.01" lon="-15.6"/><trkpt lat="28.011" lon="-15.6"/></trkseg></trk></gpx>'
  page.locator('[data-vision=options]>summary').click();page.locator('[data-vision=file]').set_input_files({'name':'missing-elevation-and-gap.gpx','mimeType':'application/gpx+xml','buffer':multi});page.wait_for_function('trailVision.route.segments.length===2')
  check(cs,'uploaded segment gaps stop the preview rather than being joined',page.evaluate('RACER_APP.vision().available')<110 and 'No gap is bridged' in page.locator('[data-vision=segmentWarning]').inner_text())
  check(cs,'missing GPX elevation is clearly flat','Flat preview' in page.locator('[data-vision=elevationWarning]').inner_text() and not page.evaluate('RACER_APP.vision().elevationOK'))
  page.locator('[data-vision=file]').set_input_files({'name':'invalid.gpx','mimeType':'application/gpx+xml','buffer':b'not XML'})
  check(cs,'invalid GPX produces an understandable error', 'not valid GPX' in page.locator('[data-vision=fileStatus]').inner_text())
  page.locator('[data-vision=raceRoute]').click();check(cs,'race GPX can be restored unchanged',page.evaluate('trailVision.route.points.length===RACER_APP.DATA.track_km.length') and page.evaluate('RACER_APP.vision().available')==500)
  page.locator('[data-vision=exit]').click();page.locator('#toolsPanel>summary').click()
  with page.expect_download() as dl:page.locator('#downloadGpx').click()
  gpx=dl.value.path();check(cs,'preview imports do not change the race GPX download',hashlib.sha256(Path(gpx).read_bytes()).hexdigest()==page.evaluate('RACER_APP.DATA.gpx_sha256'))
  check(cs,'no camera or external requests beyond forecast and map tiles',page.evaluate('__cameraRequests')==0 and not [u for u in requests if not u.startswith('http://127.0.0.1:8787/') and not u.startswith('https://api.open-meteo.com/v1/forecast?') and not any(u.startswith('https://'+host+'.tile.openstreetmap.org/') for host in ['a','b','c'])])
  check(cs,'all integrated interactions are free of script errors',not errors)
  ctx.close()
  # Denied sensors and absent GPX must leave an actionable UI.
  ctx,d,errs,_=setup(browser,320,'window.__denyOrientation=true;');open_vision(d);d.wait_for_timeout(100);d.evaluate('__gpsBad({code:1})')
  check(cs,'permission denial offers explicit usable fallback choices','denied' in d.locator('[data-vision=sensorStatus]').inner_text() and d.locator('[data-vision-mode=manual]').is_visible() and d.locator('[data-vision=previewOffline]').is_visible())
  d.locator('[data-vision=previewOffline]').click();d.locator('[data-vision=mode]').select_option('manual');d.locator('[data-vision=options]>summary').click()
  metrics=d.locator('#trailVision select,#trailVision input:not([type=file]):not([type=range])').evaluate_all('es=>es.filter(e=>e.getBoundingClientRect().width).map(e=>{const r=e.getBoundingClientRect();return {x:r.x,right:r.right,h:r.height,font:parseFloat(getComputedStyle(e).fontSize)}})')
  check(cs,'320px controls remain legible and inside the viewport',all(x['x']>=0 and x['right']<=321 and x['font']>=16 for x in metrics))
  d.locator('[data-vision=exit]').click();d.evaluate("document.getElementById('gpxData').textContent='';trailVision.route=null;trailVision.uploaded=false");d.locator('#openTrailVision').click()
  check(cs,'missing GPX is handled without a crash','GPX' in d.locator('[data-vision=gpsStatus]').inner_text() and not errs)
  d.locator('[data-vision=options]>summary').click();d.locator('[data-vision=simulate]').click();check(cs,'simulation without GPX is rejected with useful guidance','Load a GPX' in d.locator('[data-vision=fileStatus]').inner_text())
  d.locator('[data-vision=exit]').click();ctx.close()
  ctx,u,errs,_=setup(browser,390,"Object.defineProperty(window,'DeviceOrientationEvent',{value:undefined,configurable:true});Object.defineProperty(window,'DeviceMotionEvent',{value:undefined,configurable:true});")
  open_vision(u);u.wait_for_timeout(100)
  check(cs,'unsupported sensors are unavailable without invented calibration advice','unavailable' in u.locator('[data-vision=sensorStatus]').inner_text() and not u.locator('[data-vision=compassWarning]').is_visible())
  u.locator('[data-vision=previewOffline]').click();u.locator('[data-vision=mode]').select_option('route');check(cs,'sensor-free route-following preview remains usable',u.evaluate('RACER_APP.vision().available')==500)
  u.keyboard.press('Escape');check(cs,'Escape releases the fullscreen view',not u.evaluate('RACER_APP.vision().active') and not errs)
  ctx.close();browser.close();records.append({'browser':engine,'passed':len(cs),'checks':cs,'simulated_sensors':True})
result={'passed':sum(x['passed'] for x in records),'physical_device_test':False,'results':records};(R/'docs/vision-browser-tests.json').write_text(json.dumps(result,indent=2));print(json.dumps({'passed':result['passed']},indent=2))
