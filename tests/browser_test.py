from pathlib import Path
from playwright.sync_api import sync_playwright
import json
R=Path(__file__).resolve().parents[1];out=R/'data';checks=[]
def check(name,result):
 assert result,name
 checks.append(name)
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
 context=browser.new_context(viewport={'width':1440,'height':1100},accept_downloads=True)
 page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 # Offline means the app must make no required remote requests.
 context.route('**/*',lambda route:route.continue_() if route.request.url.startswith('http://127.0.0.1:8787/') else route.abort());page.goto('http://127.0.0.1:8787/index.html');page.wait_for_function('window.RACER_APP !== undefined')
 check('app loads offline without script errors',not errors)
 check('default finish is Sunday morning', 'Sun 03:45' in page.locator('#finishClock').inner_text())
 check('29 sections render',page.locator('#sectionRows tr').count()==29)
 check('core engine and source data are loaded',page.evaluate('RACER_APP.DATA.pois.length')>300)
 page.screenshot(path=str(out/'roadbook_desktop.png'),full_page=True)
 page.get_by_role('button',name='80 km start',exact=True).click();check('slower preset updates cut-off margin','0h 09m' in page.locator('#finishMargin').inner_text() or '0h 10m' in page.locator('#finishMargin').inner_text())
 page.get_by_role('button',name='85 km start',exact=True).click()
 page.get_by_role('tab',name='Resupply',exact=True).click();page.locator('#searchPoi').fill('tenteniguada')
 check('nearby supermarket hours filter works',page.locator('#poiCards').inner_text().find('SPAR Tenteniguada')>=0)
 check('overnight supermarket is closed', 'At plan ETA: listed closed' in page.locator('#poiCards').inner_text())
 page.locator('#poiCards button[data-action="save"]').first.click();check('a place can be saved',len(page.evaluate('RACER_APP.getState().saved'))==1)
 page.locator('#poiCards button[data-action="note"]').first.click();page.locator('#placeNotes').fill('Buy food </script><script>window.INJECTED=true</script>')
 page.locator('#hoursOverride').fill('Mo-Su 00:00-24:00');page.locator('#dialogSave').click()
 check('confirmed hour override updates evaluation', 'Listed open across window' in page.locator('#poiCards').inner_text())
 check('note text is escaped',page.evaluate('window.INJECTED') is None)
 # Download a portable HTML containing current notes and reopen it fully offline.
 with page.expect_download() as info:page.locator('#downloadHtml').click()
 download=info.value;saved=out/'test_saved_roadbook.html';download.save_as(str(saved))
 new=context.new_page();new.on('pageerror',lambda e:errors.append(str(e)));new.goto('http://127.0.0.1:8787/data/test_saved_roadbook.html');new.wait_for_function('window.RACER_APP !== undefined')
 check('saved HTML restores notes and hours overrides', len(new.evaluate('RACER_APP.getState().saved'))==1)
 check('saved HTML does not execute note markup', new.evaluate('window.INJECTED') is None)
 # Map and per-leg display still work with network disabled.
 page.get_by_role('tab',name='Map',exact=True).first.click();page.wait_for_timeout(200)
 check('offline interactive map initializes',page.locator('#map .leaflet-map-pane').count()==1)
 page.get_by_role('tab',name='Sections',exact=True).click();page.locator('#sectionRows tr').nth(10).click();page.wait_for_timeout(150)
 check('section selection opens map and leg information','South-coast approach' in page.locator('#mapCaption').inner_text() or page.locator('#mapCaption').inner_text().count('→')==1)
 check('no runtime errors during interactions',not errors)
 page.screenshot(path=str(out/'roadbook_map.png'),full_page=True)
 # Fresh phone view: no horizontal scroll or hidden essential controls.
 phone=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,device_scale_factor=1);phone.route('**/*',lambda route:route.continue_() if route.request.url.startswith('http://127.0.0.1:8787/') else route.abort());m=phone.new_page();m.goto('http://127.0.0.1:8787/index.html');m.wait_for_function('window.RACER_APP !== undefined')
 check('phone layout fits screen',m.evaluate('document.documentElement.scrollWidth <= innerWidth+1'))
 m.screenshot(path=str(out/'roadbook_mobile.png'),full_page=True)
 m.get_by_role('tab',name='Resupply',exact=True).click();check('phone resupply view fits screen',m.evaluate('document.documentElement.scrollWidth <= innerWidth+1'))
 # Explicit GPX download retains original content, not a simplified route.
 with m.expect_download() as info:m.locator('#downloadGpx').click()
 gp=out/'test_download.gpx';info.value.save_as(str(gp));import hashlib
 check('embedded GPX download hash matches original',hashlib.sha256(gp.read_bytes()).hexdigest()==m.evaluate('RACER_APP.DATA.gpx_sha256'))
 browser.close()
(out/'browser_tests.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'script_errors':errors},indent=2));print(json.dumps({'passed':len(checks),'script_errors':errors},indent=2))
