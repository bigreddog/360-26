"""Phone UX regression checks in browser emulation, including expanded controls."""
import argparse,json,os
from pathlib import Path
from playwright.sync_api import sync_playwright
R=Path(__file__).resolve().parents[1];OUT=R/'docs/mobile-qa';OUT.mkdir(exist_ok=True)
ap=argparse.ArgumentParser();ap.add_argument('--browsers',nargs='+',default=['chromium','webkit'],choices=['chromium','webkit']);args=ap.parse_args();results=[]
def verify(name,ok,details=None):
 assert ok,f'{name}: {details}'
 return name
with sync_playwright() as p:
 for engine in args.browsers:
  browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox']) if engine=='chromium' else p.webkit.launch(headless=True)
  for width,height in [(320,740),(360,800),(390,844),(430,932),(844,390),(932,430)]:
   ctx=browser.new_context(viewport={'width':width,'height':height},is_mobile=True,has_touch=True,device_scale_factor=1)
   ctx.route('**/*',lambda r:r.continue_() if r.request.url.startswith('http://127.0.0.1:8787/') else r.abort())
   page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:8787');page.wait_for_function('window.RACER_APP');checks=[]
   checks.append(verify('pace settings start collapsed',not page.locator('#pacePanel').evaluate('e=>e.open')))
   checks.append(verify('GPS and sync are accessible without expanding settings',page.locator('#syncProgress').is_visible() and page.locator('#location-main').is_visible()))
   page.locator('#pacePanel>summary').click();page.locator('#timingPanel>summary').click()
   metrics=page.locator('.sidebar input[type=number]').evaluate_all('''es=>es.map(e=>{let r=e.getBoundingClientRect(),p=e.parentElement.getBoundingClientRect(),s=getComputedStyle(e);return {id:e.id,x:r.x,y:r.y,width:r.width,height:r.height,font:parseFloat(s.fontSize),parentLeft:p.left,parentRight:p.right,inputMode:e.inputMode}})''')
   checks.append(verify('all eight numeric controls are inspected',len(metrics)==8))
   checks.append(verify('numeric controls fit long values',all(m['width']>=110 for m in metrics),metrics))
   checks.append(verify('numeric targets are at least 48px',all(m['height']>=48 for m in metrics),metrics))
   checks.append(verify('numeric text is at least 18px',all(m['font']>=18 for m in metrics),metrics))
   checks.append(verify('inputs stay inside grid cells',all(m['x']>=m['parentLeft']-.5 and m['x']+m['width']<=m['parentRight']+.5 for m in metrics),metrics))
   byid={m['id']:m for m in metrics}
   checks.append(verify('paired numeric rows align',all(abs(byid[a]['y']-byid[b]['y'])<1 for a,b in [('day1','day2'),('day3','day4'),('elapsedHours','extraHours')]),metrics))
   checks.append(verify('numeric keyboards are requested',all(m['inputMode'] in ['numeric','decimal'] for m in metrics)))
   presets=page.locator('[data-preset]').evaluate_all('es=>es.map(e=>{let r=e.getBoundingClientRect();return {y:r.y,h:r.height}})')
   checks.append(verify('presets are a separate touch-sized row',len(presets)==3 and all(x['h']>=48 for x in presets) and max(x['y'] for x in presets)-min(x['y'] for x in presets)<1,presets))
   for id,value in [('day1','88'),('day2','68'),('day3','58'),('day4','48'),('progressKm','123.4'),('elapsedHours','42.25'),('extraHours','1.25'),('terrainWeight','0.75')]:
    page.locator('#'+id).fill(value);page.locator('#'+id).blur()
   st=page.evaluate('RACER_APP.getState()')
   checks.append(verify('all numeric edits update state',st['quotas']==[88,68,58,48] and st['progressKm']==123.4 and st['elapsedHours']==42.25 and st['extraHours']==1.25 and st['terrainWeight']==.75,st))
   page.locator('#anchorLive').check();checks.append(verify('manual ETA anchoring still works',page.evaluate('RACER_APP.getState().anchorLive')))
   page.locator('#progressKm').fill('0');page.locator('#progressKm').blur()
   if width==390:page.locator('.sidebar').screenshot(path=str(OUT/f'{engine}-controls.png'))
   page.get_by_role('tab',name='Resupply',exact=True).click();page.locator('#filtersPanel>summary').click();page.locator('#statusFilter').select_option('open');page.locator('#typeFilter').select_option('retail')
   selects=page.locator('#tab-resupply select,#searchPoi').evaluate_all('''es=>es.map(e=>{let r=e.getBoundingClientRect(),s=getComputedStyle(e),c=document.createElement('canvas').getContext('2d');c.font=s.font;let t=e.tagName==='SELECT'?e.options[e.selectedIndex].text:'';return {id:e.id,x:r.x,right:r.right,w:r.width,h:r.height,font:parseFloat(s.fontSize),textWidth:c.measureText(t).width,available:r.width-parseFloat(s.paddingLeft)-parseFloat(s.paddingRight)-2}})''')
   checks.append(verify('filters use readable 18px text and 48px targets',all(m['font']>=18 and m['h']>=48 for m in selects),selects))
   checks.append(verify('selected filter labels fit without clipping',all(m['textWidth']<=m['available']+1 for m in selects),selects))
   checks.append(verify('filters stay inside the phone viewport',all(m['x']>=0 and m['right']<=width+1 for m in selects),selects))
   page.locator('#statusFilter').select_option('all');page.locator('#searchPoi').fill('tenteniguada');page.locator('#filtersPanel>summary').click()
   stop=page.locator('#poiCards [data-place="owner/spar-tenteniguada"]');stop.locator('summary').click()
   text=stop.locator('h3,.arrival-line b,.progress-distance strong,.pill').evaluate_all('es=>es.map(e=>parseFloat(getComputedStyle(e).fontSize))')
   checks.append(verify('critical stop information is at least 16px',min(text)>=16,text))
   actions=stop.locator('.actions>*').evaluate_all('es=>es.map(e=>{const r=e.getBoundingClientRect();return {w:r.width,h:r.height,x:r.x,right:r.right}})')
   checks.append(verify('stop actions have 48px targets and stay in bounds',all(m['h']>=48 and m['x']>=0 and m['right']<=width+1 for m in actions),actions))
   checks.append(verify('stop sources are readable inside disclosure',stop.locator('.hours').is_visible()))
   if width==390:
    page.evaluate('window.scrollTo(0,0)');page.screenshot(path=str(OUT/f'{engine}-resupply.png'),full_page=True)
   page.get_by_role('tab',name='Legs',exact=True).click()
   checks.append(verify('legs use cards without a sideways table',page.locator('.leg-card').count()==47 and page.locator('table').count()==0))
   checks.append(verify('leg map buttons remain touch-sized',page.locator('[data-section]').evaluate_all('es=>es.every(e=>e.getBoundingClientRect().height>=48)')))
   checks.append(verify('all views fit without horizontal scrolling',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')))
   # Enlarged browser text: allow wrapping without clipping numeric fields or tabs.
   page.add_style_tag(content='body{font-size:22px} .poi-card p,.help{font-size:20px}')
   page.get_by_role('tab',name='Resupply',exact=True).click()
   checks.append(verify('enlarged body text still fits',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')))
   checks.append(verify('no runtime errors through expanded mobile views',not errors,errors))
   results.append({'browser':engine,'viewport':[width,height],'passed':len(checks),'checks':checks,'numeric_controls':metrics,'filter_controls':selects});ctx.close()
  browser.close()
summary={'test':'Readable phone controls and simplified UX','hardware_test':False,'browser_runs':len(results),'checks_passed':sum(x['passed'] for x in results),'results':results};(R/'docs/mobile-controls-tests.json').write_text(json.dumps(summary,indent=2));print(json.dumps({k:v for k,v in summary.items() if k!='results'},indent=2))
