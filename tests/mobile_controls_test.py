"""Check individual phone controls and expanded states, not just page overflow.

Serve the repository on 127.0.0.1:8787. Requires Playwright browsers selected by
--browsers (default: Chromium + WebKit). This is browser emulation, not hardware QA.
"""
import argparse,json,os
from pathlib import Path
from playwright.sync_api import sync_playwright
R=Path(__file__).resolve().parents[1];OUT=R/'docs/mobile-qa';OUT.mkdir(exist_ok=True)
ap=argparse.ArgumentParser();ap.add_argument('--browsers',nargs='+',default=['chromium','webkit'],choices=['chromium','webkit']);args=ap.parse_args()
results=[]
def verify(name,ok,details=None):
 assert ok,f'{name}: {details}'
 return name
with sync_playwright() as p:
 for engine in args.browsers:
  browser=(p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox']) if engine=='chromium' else p.webkit.launch(headless=True))
  for width,height in [(320,740),(360,800),(390,844),(430,932),(844,390),(932,430)]:
   ctx=browser.new_context(viewport={'width':width,'height':height},is_mobile=True,has_touch=True,device_scale_factor=1)
   ctx.route('**/*',lambda r:r.continue_() if r.request.url.startswith('http://127.0.0.1:8787/') else r.abort())
   page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:8787/index.html');page.wait_for_function('window.RACER_APP');checks=[]
   page.locator('.sidebar details').first.evaluate('(e)=>e.open=true')
   metrics=page.locator('.sidebar input[type=number]').evaluate_all('''es=>es.map(e=>{let r=e.getBoundingClientRect(),p=e.parentElement.getBoundingClientRect(),s=getComputedStyle(e);return {id:e.id,x:r.x,y:r.y,width:r.width,height:r.height,font:parseFloat(s.fontSize),parentLeft:p.left,parentRight:p.right,inputMode:e.inputMode}})''')
   checks.append(verify('all eight numeric controls inspected',len(metrics)==8))
   checks.append(verify('numeric controls are wide enough for long values',all(m['width']>=110 for m in metrics),metrics))
   checks.append(verify('numeric controls have 44px touch targets',all(m['height']>=44 for m in metrics),metrics))
   checks.append(verify('numeric text is at least 16px',all(m['font']>=16 for m in metrics),metrics))
   checks.append(verify('controls stay inside their grid cells',all(m['x']>=m['parentLeft']-.5 and m['x']+m['width']<=m['parentRight']+.5 for m in metrics),metrics))
   byid={m['id']:m for m in metrics}
   checks.append(verify('paired fields align in both pacing and timing rows',all(abs(byid[a]['y']-byid[b]['y'])<=1 for a,b in [('day1','day2'),('day3','day4'),('progressKm','elapsedHours'),('extraHours','terrainWeight')]),metrics))
   checks.append(verify('numeric keyboards are explicitly requested',all(m['inputMode'] in ['numeric','decimal'] for m in metrics)))
   preset=page.locator('[data-preset]').evaluate_all('es=>es.map(e=>{let r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}})')
   checks.append(verify('preset buttons use a separate full-width row',len(preset)==3 and all(x['h']>=44 for x in preset) and max(x['y'] for x in preset)-min(x['y'] for x in preset)<1,preset))
   for id,value in [('day1','88'),('day2','68'),('day3','58'),('day4','48'),('progressKm','123.4'),('elapsedHours','42.25'),('extraHours','1.25'),('terrainWeight','0.75')]:
    page.locator('#'+id).fill(value);page.locator('#'+id).blur()
   st=page.evaluate('RACER_APP.getState()')
   checks.append(verify('typing into every numeric control updates the plan',st['quotas']==[88,68,58,48] and st['progressKm']==123.4 and st['elapsedHours']==42.25 and st['extraHours']==1.25 and st['terrainWeight']==.75,st))
   page.locator('#anchorLive').check();checks.append(verify('touch checkbox updates live ETA anchoring',page.evaluate('RACER_APP.getState().anchorLive')))
   page.locator('#progressKm').fill('0');page.locator('#progressKm').blur()
   if width==390:page.locator('.sidebar').screenshot(path=str(OUT/f'{engine}-controls.png'))
   page.get_by_role('tab',name='Resupply',exact=True).click();page.locator('#statusFilter').select_option('open');page.locator('#typeFilter').select_option('retail')
   selects=page.locator('#tab-resupply select,#searchPoi').evaluate_all('''es=>es.map(e=>{let r=e.getBoundingClientRect(),s=getComputedStyle(e),c=document.createElement('canvas').getContext('2d');c.font=s.font;let t=e.tagName==='SELECT'?e.options[e.selectedIndex].text:'';return {id:e.id,x:r.x,right:r.right,w:r.width,h:r.height,font:parseFloat(s.fontSize),textWidth:c.measureText(t).width,available:r.width-parseFloat(s.paddingLeft)-parseFloat(s.paddingRight)-2}})''')
   checks.append(verify('search and select controls are readable and touch-sized',all(m['font']>=16 and m['h']>=44 for m in selects),selects))
   checks.append(verify('selected filter labels fit without clipping',all(m['textWidth']<=m['available']+1 for m in selects),selects))
   checks.append(verify('filter controls stay inside the phone viewport',all(m['x']>=0 and m['right']<=width+1 for m in selects),selects))
   page.locator('#statusFilter').select_option('all');page.locator('#searchPoi').fill('tenteniguada')
   if width==390:page.locator('#tab-resupply').screenshot(path=str(OUT/f'{engine}-resupply.png'))
   page.locator('#poiCards button[data-action=note]').first.click()
   controls=page.locator('#hoursOverride,#placeNotes').evaluate_all('es=>es.map(e=>{let r=e.getBoundingClientRect();return {w:r.width,h:r.height,x:r.x,right:r.right,font:parseFloat(getComputedStyle(e).fontSize)}})')
   checks.append(verify('dialog text controls use 16px readable text and fit',all(m['font']>=16 and m['w']>=200 and m['h']>=44 and m['x']>=0 and m['right']<=width for m in controls),controls))
   page.locator('#placeNotes').fill('Phone check: food and water');page.locator('#hoursOverride').fill('Mo-Su 08:00-21:00')
   reduced_height=min(height,500);page.set_viewport_size({'width':width,'height':reduced_height});page.wait_for_timeout(80)
   dialog=page.locator('#placeDialog').bounding_box();save=page.locator('#dialogSave').bounding_box()
   checks.append(verify('dialog fits a reduced viewport with usable actions',dialog['height']<=reduced_height-20 and dialog['y']>=0 and save['height']>=44 and save['y']+save['height']<=reduced_height,{'dialog':dialog,'save':save}))
   if width==390:page.screenshot(path=str(OUT/f'{engine}-dialog.png'))
   page.locator('#dialogSave').click()
   checks.append(verify('editing hours and notes on a phone persists',page.evaluate('RACER_APP.getState().notes["owner/spar-tenteniguada"]')=='Phone check: food and water'))
   checks.append(verify('no page-wide horizontal overflow',page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')))
   checks.append(verify('no script errors in expanded phone states',not errors,errors))
   results.append({'browser':engine,'viewport':[width,height],'passed':len(checks),'checks':checks,'numeric_controls':metrics,'filter_controls':selects})
   ctx.close()
  browser.close()
summary={'test':'Mobile form controls and expanded states','hardware_test':False,'browser_runs':len(results),'checks_passed':sum(x['passed'] for x in results),'results':results}
(R/'docs/mobile-controls-tests.json').write_text(json.dumps(summary,indent=2));print(json.dumps({k:v for k,v in summary.items() if k!='results'},indent=2))
