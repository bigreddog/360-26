"""PWA metadata, optional install prompt, portable HTML and remembered map tiles."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,struct
R=Path(__file__).resolve().parents[1];records=[]
with sync_playwright() as p:
 for engine in ['chromium','webkit']:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']) if engine=='chromium' else p.webkit.launch(headless=True)
  ctx=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,service_workers='block',accept_downloads=True)
  requests=[];ctx.on('request',lambda req:requests.append(req.url));ctx.route('**/*',lambda r:r.continue_() if r.request.url.startswith('http://127.0.0.1:8787/') else r.abort())
  page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:8787');page.wait_for_function('window.RACER_APP');cs=[]
  def check(name,value):
   assert value,f'{name} ({engine})'
   cs.append(name)
  check('weather offers only twelve and twenty-four hours',page.locator('[data-weather-hours]').evaluate_all('es=>es.map(e=>e.dataset.weatherHours)')==['12','24'])
  check('street tiles are enabled in new settings before map is opened',page.evaluate('RACER_APP.getState().streetMap') is True)
  check('tiles are lazy and not requested in Race view',not any('.tile.openstreetmap.org/' in u for u in requests))
  page.get_by_role('tab',name='Map',exact=True).click();page.wait_for_timeout(200)
  check('opening Map enables the street layer and requests tiles',page.evaluate('baseTiles!==null&&map.hasLayer(baseTiles)') and any('.tile.openstreetmap.org/' in u for u in requests))
  page.locator('#tab-map details>summary').click();page.locator('#toggleTiles').click()
  check('street-map off is immediately reflected and persisted',page.locator('#toggleTiles').get_attribute('aria-pressed')=='false' and page.evaluate('baseTiles===null&&JSON.parse(localStorage.getItem("canarias360-roadbook-v2")).streetMap===false'))
  page.reload();page.wait_for_function('window.RACER_APP');page.get_by_role('tab',name='Map',exact=True).click()
  check('off survives page reload and map initialization',page.evaluate('baseTiles===null&&RACER_APP.getState().streetMap===false') and page.locator('#toggleTiles').text_content()=='Street map: off')
  page.locator('#tab-map details>summary').click();page.locator('#toggleTiles').click();page.reload();page.wait_for_function('window.RACER_APP');page.get_by_role('tab',name='Map',exact=True).click()
  check('on also survives page reload',page.evaluate('baseTiles!==null&&map.hasLayer(baseTiles)&&RACER_APP.getState().streetMap'))
  response=ctx.request.get('http://127.0.0.1:8787/manifest.webmanifest');manifest=response.json()
  check('valid scoped standalone manifest supplies a stable app identity',response.ok and manifest['id']=='./' and manifest['start_url']=='./' and manifest['scope']=='./' and manifest['display']=='standalone' and bool(manifest['name']))
  for size in [192,512]:
   png=(R/'icons'/f'icon-{size}.png').read_bytes()
   check(f'{size}px app icon has valid PNG dimensions',png[:8]==b'\x89PNG\r\n\x1a\n' and struct.unpack('>II',png[16:24])==(size,size))
  check('manifest has maskable icon for Android',any('maskable' in i.get('purpose','') for i in manifest['icons']))
  if engine=='chromium':
   session=ctx.new_cdp_session(page);app_manifest=session.send('Page.getAppManifest')
   check('Chrome parses manifest without errors',not app_manifest.get('errors') and json.loads(app_manifest['data'])['display']=='standalone');session.detach()
  page.locator('#toolsPanel>summary').click();page.locator('#installApp').click()
  check('browser without a native prompt receives usable install guidance','Add to home screen' in page.locator('#installStatus').inner_text() or 'Add to Home Screen' in page.locator('#installStatus').inner_text())
  page.screenshot(path=str(R/'docs/screenshots'/f'install-{engine}.png'))
  def prompt(outcome):
   page.evaluate('''outcome=>{window.__promptCalls=0;const event=new Event('beforeinstallprompt',{cancelable:true});event.prompt=async()=>{window.__promptCalls++;};event.userChoice=Promise.resolve({outcome});window.__installEvent=event;window.dispatchEvent(event);}''',outcome)
  prompt('dismissed');check('browser prompt is deferred until a user tap',page.evaluate('__installEvent.defaultPrevented&&__promptCalls===0'))
  page.locator('#installApp').click();check('dismissal is non-blocking with no repeated automatic prompt',page.evaluate('__promptCalls===1') and 'dismissed' in page.locator('#installStatus').inner_text() and page.locator('#installApp').is_enabled())
  prompt('accepted');page.locator('#installApp').click();check('accepted prompt hides the install action',page.evaluate('__promptCalls===1') and not page.locator('#installApp').is_visible() and 'accepted' in page.locator('#installStatus').inner_text())
  page.evaluate("window.dispatchEvent(new Event('appinstalled'))");check('appinstalled event acknowledges installation','App installed' in page.locator('#installStatus').inner_text())
  with page.expect_download() as info:page.locator('#downloadHtml').click()
  saved=R/'data/test_install_saved.html';info.value.save_as(str(saved));raw=saved.read_text()
  check('portable file has no external manifest or icon dependencies',page.evaluate('html=>!new DOMParser().parseFromString(html,"text/html").querySelector("link[rel=manifest],link[rel=icon],link[rel=apple-touch-icon]")',raw))
  check('portable file retains the saved street-map preference','"streetMap":true' in raw)
  installed=browser.new_context(viewport={'width':320,'height':740},is_mobile=True,service_workers='block')
  installed.add_init_script('''const media=window.matchMedia.bind(window);window.matchMedia=q=>q==='(display-mode: standalone)'?{matches:true,addEventListener(){}}:media(q);''')
  installed.route('**/*',lambda r:r.continue_() if r.request.url.startswith('http://127.0.0.1:8787/') else r.abort());app=installed.new_page();app.goto('http://127.0.0.1:8787');app.wait_for_function('window.RACER_APP');app.locator('#toolsPanel>summary').click()
  check('standalone mode hides redundant install controls',not app.locator('#installApp').is_visible() and 'App installed' in app.locator('#installStatus').inner_text())
  check('installed layout fits a narrow phone',app.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
  installed.close()
  check('no application errors through install and map journeys',not errors)
  records.append({'browser':engine,'passed':len(cs),'checks':cs});ctx.close();browser.close()
report={'passed':sum(r['passed'] for r in records),'physical_device_test':False,'native_prompt_simulated':True,'results':records};(R/'docs/install-browser-tests.json').write_text(json.dumps(report,indent=2));print(json.dumps({'passed':report['passed']},indent=2))
