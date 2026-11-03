"""Integrated AEMET/fallback, mobile, stale and offline journeys; deterministic forecasts."""
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import json
import os
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/aemet-qa'
OUT.mkdir(exist_ok=True)
NOW = int(datetime(2026, 11, 4, 9, tzinfo=timezone.utc).timestamp())
TOWNS = json.loads((ROOT / 'data/weather/aemet-towns.json').read_text())['towns']
WARNINGS = json.loads((ROOT / 'tests/fixtures/aemet-alerts-20261103.json').read_text())
INIT = f'Date.now=()=>{NOW * 1000};'


def feed(mode='ok'):
    towns = [{**town, 'fetchedAt': (NOW - (13 * 3600 if mode == 'stale' else 8 * 3600 if mode == 'delayed' else 3600)) * 1000,
              'issuedLocal': '2026-11-04T08:00:00',
              'hourly': [{'time': NOW + i * 3600, 'temperature': 12, 'feels': 10,
                          'wind': 22, 'gust': 35, 'direction': 0, 'rain': .5,
                          'code': 1, 'day': 1} for i in range(-2, 71)],
              'probabilities': [{'start': NOW - 10800 + i * 21600,
                                 'end': NOW - 10800 + (i + 1) * 21600,
                                 'value': 70, 'hours': 6} for i in range(13)]} for town in TOWNS]
    if mode in ['trace', 'trace_missing']:
        for town in towns:
            for row in town['hourly']:
                if row['time'] == NOW + 3600:
                    row.update(rain=None, rainTrace=True)
                elif mode == 'trace_missing' and row['time'] == NOW + 3 * 3600:
                    row['rain'] = None
    day = NOW - 9 * 3600
    entries = [{'date': f'2026-11-{4+i:02}', 'area': 'Gran Canaria' if i < 2 else 'Canary Islands',
                'language': 'es', 'from': (day + i * 86400) * 1000,
                'until': (day + (i + 1) * 86400) * 1000, 'fetchedAt': (NOW - 3600) * 1000,
                'issuedLocal': '2026-11-04T08:00:00',
                'paragraphs': ['Intervalos nubosos. Temperaturas sin cambios.'],
                'significant': ['Lluvias localmente fuertes.'] if i == 1 else []} for i in range(4)]
    for b in entries:
        b['english'] = {'version': 1, 'language': 'en', 'method': 'machine',
                        'sourceParagraphs': b['paragraphs'][:], 'sourceSignificant': b['significant'][:],
                        'paragraphs': ['Cloudy intervals. Temperatures unchanged.'],
                        'significant': ['Locally heavy rain.'] if b['significant'] else []}
    warnings = json.loads(json.dumps(WARNINGS))
    warnings['fetchedAt'] = (NOW - (7 * 3600 if mode == 'alerts_stale' else 3600)) * 1000
    if mode == 'alerts_none':
        warnings['entries'] = []
    if mode == 'alerts_missing':
        warnings = None
    if mode == 'alerts_only':
        towns = []
    return {'version': 1, 'provider': 'aemet', 'generatedAt': NOW * 1000, 'towns': towns, 'alerts': warnings,
            'outlook': {'version': 1, 'entries': entries}}


def fallback(url):
    q = parse_qs(urlparse(url).query)
    start = int(datetime.fromisoformat(q['start_hour'][0]).replace(tzinfo=timezone.utc).timestamp())
    end = int(datetime.fromisoformat(q['end_hour'][0]).replace(tzinfo=timezone.utc).timestamp())
    time = list(range(start, end + 1, 3600))
    return [{'hourly': {'time': time, **{key: [value] * len(time) for key, value in {
        'temperature_2m': 19, 'apparent_temperature': 17, 'precipitation_probability': 20,
        'precipitation': .2, 'weather_code': 0, 'wind_speed_10m': 10,
        'wind_gusts_10m': 18, 'wind_direction_10m': 270, 'is_day': 1}.items()}}}
        for _ in q['latitude'][0].split(',')]


def check(checks, name, condition):
    assert condition, name
    checks.append(name)


records = []
with sync_playwright() as p:
    for engine in ['chromium', 'webkit']:
        browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox']) if engine == 'chromium' else p.webkit.launch()
        ctx = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True,
                                  has_touch=True, accept_downloads=True, service_workers='block')
        ctx.add_init_script(INIT)
        calls, errors, checks = [], [], []
        scenario = {'aemet': 'ok', 'fallback': 'ok'}

        def intercept(route):
            url = route.request.url
            if 'raw.githubusercontent.com/bigreddog/360-26/weather-data/aemet.json' in url:
                calls.append('aemet')
                if scenario['aemet'] == 'error':
                    route.fulfill(status=503, body='Unavailable')
                else:
                    route.fulfill(status=200, content_type='application/json', body=json.dumps(feed(scenario['aemet'])))
            elif url.startswith('https://api.open-meteo.com/'):
                calls.append('fallback')
                route.fulfill(status=503, body='Unavailable') if scenario['fallback'] == 'error' else route.fulfill(status=200, content_type='application/json', body=json.dumps(fallback(url)))
            elif url.startswith('http://127.0.0.1:8787/'):
                route.continue_()
            else:
                route.abort()

        ctx.route('**/*', intercept)
        page = ctx.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto('http://127.0.0.1:8787')
        page.wait_for_function('typeof weatherPanel!=="undefined"&&weatherPanel.cache&&!weatherPanel.loading')
        counts = page.evaluate('AemetWeather.counts(weatherPanel.cache.rows)')
        check(checks, 'AEMET is used alongside explicitly identified remote/high-route fallback', counts['aemet'] > 0 and counts['openMeteo'] > 0)
        check(checks, 'visible provider badge identifies both sources', 'AEMET town forecasts' in page.locator('[data-weather-provider]').inner_text() and 'Open-Meteo' in page.locator('[data-weather-provider]').inner_text())
        check(checks, 'six-hour AEMET probabilities are not labelled hourly', 'AEMET 6-h' in page.locator('[data-weather-summary]').inner_text())
        check(checks, 'AEMET northerly wind arrow points south', page.locator('.weather-wind-summary [data-wind-bearing="0"] g').get_attribute('transform') == 'rotate(180 24 26)')
        check(checks, 'only near-height near-distance towns supply the preview', page.evaluate('weatherPanel.cache.rows.filter(r=>r.weather?.source?.provider==="aemet").every(r=>Math.abs(r.weather.source.heightDelta)<=250&&r.weather.source.separation<=8000)'))
        check(checks, 'new cache schema preserves source attribution', page.evaluate('JSON.parse(localStorage.getItem(RouteWeather.CACHE_KEY)).version') == 3)
        warning = page.locator('[data-weather-alerts]')
        check(checks, 'official warnings appear above the numerical weather controls', warning.bounding_box()['y'] < page.locator('.weather-views').bounding_box()['y'])
        check(checks, 'expired warnings disappear while tomorrow warnings group across three zones', page.locator('.weather-alert').count() == 1 and '15 mm in 1 hour' in warning.inner_text() and '20 mm in 1 hour' not in warning.inner_text())
        check(checks, 'warning area, local validity and forecast overlap are explicit', all(t in warning.inner_text() for t in ['Summits', '11:00', '19:59', 'Overlaps your forecast window']))
        for width in [320, 390, 844]:
            page.set_viewport_size({'width': width, 'height': 844 if width < 800 else 390})
            check(checks, f'warning cards fit {width}px phone width', page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
        page.set_viewport_size({'width': 390, 'height': 844})
        warning.scroll_into_view_if_needed()
        page.screenshot(path=str(OUT / f'{engine}-official-warnings.png'))
        warning.locator('details>summary').first.click()
        page.evaluate('weatherPanel.alerts.entries.find(e=>e.from>Date.now()).descriptionOriginal+=" Updated source.";weatherPanel.render()')
        check(checks, 'warning source disclosure stays open through rerenders', warning.locator('details').first.evaluate('e=>e.open'))
        scenario['aemet'] = 'alerts_missing'
        page.evaluate('weatherPanel.refresh(true)')
        page.wait_for_function('!weatherPanel.loading')
        check(checks, 'failed warning update retains dated warnings with a recheck message', page.locator('.weather-alert').count() == 1 and 'Could not update warnings' in warning.inner_text())
        scenario['aemet'] = 'alerts_none'
        page.evaluate('weatherPanel.refresh(true)')
        page.wait_for_function('!weatherPanel.loading')
        check(checks, 'fresh authoritative empty snapshot clears superseded warnings', page.locator('.weather-alert').count() == 0 and 'No active or upcoming warnings in this downloaded snapshot' in warning.inner_text())
        scenario['aemet'] = 'alerts_missing'
        page.evaluate('weatherPanel.refresh(true)')
        page.wait_for_function('!weatherPanel.loading')
        check(checks, 'failed empty snapshot update does not imply an all-clear', 'No active or upcoming warnings' not in warning.inner_text() and 'status unavailable' in warning.inner_text())
        scenario['aemet'] = 'alerts_stale'
        page.evaluate('weatherPanel.refresh(true)')
        page.wait_for_function('!weatherPanel.loading')
        check(checks, 'old warnings remain labelled saved and stale', 'over 6 hours old' in warning.inner_text() and 'Saved' in warning.inner_text())
        scenario['aemet'] = 'ok'
        page.evaluate('weatherPanel.refresh(true)')
        page.wait_for_function('!weatherPanel.loading')
        page.evaluate('weatherPanel.cache.aemetPolicyVersion=1;weatherPanel.lastAttempt=0;weatherPanel.update()')
        page.wait_for_function('weatherPanel.cache.aemetPolicyVersion===AemetWeather.POLICY_VERSION&&!weatherPanel.loading')
        check(checks, 'recent snapshots refresh after a source-selection policy upgrade', page.evaluate('weatherPanel.cache.aemetPolicyVersion') == 4)
        outlook_text = page.locator('[data-weather-outlook]').inner_text()
        check(checks, 'island outlook shows four dated daily bulletins overlapping the next 72 hours', page.locator('.island-day').count() == 4 and 'next 72 hours' in outlook_text)
        check(checks, 'regional later days are labelled and original Spanish is explicit', 'Gran Canaria' in outlook_text and 'Canary Islands' in outlook_text and 'Spanish' in outlook_text)
        check(checks, 'significant bulletin text is translated and remains visible', 'Locally heavy rain' in outlook_text)
        check(checks, 'English paragraphs are shown by default on every day', page.locator('.island-day>p[lang=en]:not(.island-significant)').count() == 4)
        check(checks, 'Spanish originals start folded', page.locator('.island-day details').evaluate_all('es=>es.every(e=>!e.open)'))
        original = page.locator('.island-day details').first
        original.locator('summary').click()
        check(checks, 'Spanish source can be opened for comparison', 'Intervalos nubosos' in original.inner_text())
        page.evaluate('weatherPanel.now=()=>Date.now()+60000;weatherPanel.render()')
        check(checks, 'source disclosure stays open when forecast UI rerenders', page.locator('.island-day details').first.evaluate('e=>e.open'))
        page.evaluate('weatherPanel.now=()=>Date.now();weatherPanel.render()')
        page.locator('.island-day details').first.locator('summary').click()
        page.evaluate('weatherPanel.outlook.entries[0].paragraphs=["Predicción nueva."];weatherPanel.render()')
        check(checks, 'changed Spanish cannot retain an English translation of older weather', 'English translation unavailable' in page.locator('.island-day').first.inner_text() and 'Cloudy intervals' not in page.locator('.island-day').first.inner_text())
        page.evaluate('weatherPanel.outlook=JSON.parse(localStorage.getItem(RouteWeather.OUTLOOK_KEY));weatherPanel.render()')
        before = len(calls)
        page.locator('[data-weather-hours="24"]').click()
        check(checks, 'horizon switch uses the same mixed forecast without new requests', len(calls) == before)
        check(checks, '12/24-hour route control does not change 72-hour island outlook', page.locator('[data-weather-outlook]').inner_text() == outlook_text)
        page.locator('[data-weather-route]>summary').click()
        text = page.locator('[data-weather-cards]').inner_text()
        check(checks, 'stop cards name the town, mismatch and uncorrected altitude', 'Gáldar' in text and 'vs town' in text and 'no altitude correction' in text)
        check(checks, 'AEMET six-hour chance is labelled at the stop', '6-h rain chance' in text)
        check(checks, 'every forecast point shows a one-hour rain amount and time range', page.locator('.weather-stop-rain').count() == page.locator('.weather-stop').count() and '/ hour' in page.locator('.weather-stop-rain').first.inner_text() and '08:00' in page.locator('.weather-stop-rain').first.inner_text())
        check(checks, 'pre-outlook rainfall is explicitly excluded from the total', 'before outlook; not in total' in page.locator('.weather-stop-rain').first.inner_text())
        page.locator('.weather-hourly-rain>summary').click()
        check(checks, 'complete hourly rain audit shows all 24 contributing intervals', page.locator('.weather-rain-hours li').count() == 24 and 'not a single town' in page.locator('.weather-hourly-rain').inner_text())
        page.evaluate('weatherPanel.render()')
        check(checks, 'hourly rain breakdown remains open through forecast UI updates', page.locator('.weather-hourly-rain').evaluate('e=>e.open'))
        page.locator('.weather-stop-rain').first.scroll_into_view_if_needed()
        page.screenshot(path=str(OUT / f'{engine}-rain-point.png'))
        for width in [320, 390, 844]:
            page.set_viewport_size({'width': width, 'height': 844 if width < 800 else 390})
            check(checks, f'source badges and detailed cards fit {width}px', page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
        page.set_viewport_size({'width': 390, 'height': 844})
        page.locator('[data-weather-route]>summary').click()
        page.locator('#weatherPanel').scroll_into_view_if_needed()
        page.screenshot(path=str(OUT / f'{engine}-mixed.png'))
        # Last 500 m is near Tejeda at a similar height: no fallback request needed.
        before = calls.count('fallback')
        page.evaluate('state.progressKm=DATA.distance_km-.5;weatherPanel.update(true)')
        page.wait_for_function('!weatherPanel.loading&&weatherPanel.cache.fromKm>248')
        check(checks, 'fully covered short outlook skips Open-Meteo', calls.count('fallback') == before and page.evaluate('weatherPanel.cache.rows.every(r=>r.weather?.source?.provider==="aemet")'))
        scenario['aemet'] = 'trace'
        page.evaluate('state.progressKm=0;weatherPanel.refresh(true)')
        page.wait_for_function('!weatherPanel.loading&&weatherPanel.cache.fromKm===0')
        check(checks, 'AEMET trace rain keeps the mixed-provider total usable and explicit', 'mm + trace' in page.locator('.weather-rainfall').inner_text() and 'less than 0.1 mm' in page.locator('.weather-rainfall').inner_text() and 'Unavailable' not in page.locator('.weather-rainfall').inner_text())
        check(checks, 'hourly audit keeps trace and numeric zero distinct', 'Trace (&lt;0.1 mm)' in page.locator('.weather-hourly-rain').inner_html() and '0.5 mm' in page.locator('.weather-hourly-rain').inner_html())
        page.locator('.weather-rainfall').scroll_into_view_if_needed()
        page.screenshot(path=str(OUT / f'{engine}-trace-rain.png'))
        check(checks, 'trace rain summary fits phone width', page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
        scenario['aemet'] = 'trace_missing'
        page.evaluate('weatherPanel.refresh(true)')
        page.wait_for_function('!weatherPanel.loading')
        check(checks, 'genuinely missing rain is not disguised as trace or zero', 'Unavailable' in page.locator('.weather-rainfall').inner_text() and 'amounts are missing' in page.locator('.weather-rainfall').inner_text())
        scenario['aemet'] = 'delayed'
        page.evaluate('state.progressKm=0;weatherPanel.refresh(true)')
        page.wait_for_function('!weatherPanel.loading&&weatherPanel.cache.fromKm===0')
        check(checks, 'eight-hour saved AEMET remains usable with a visible update-delay warning', page.evaluate('AemetWeather.counts(weatherPanel.cache.rows).aemet') > 0 and 'AEMET update delayed' in page.locator('[data-weather-status]').inner_text())
        page.locator('[data-weather-route]>summary').click()
        check(checks, 'AEMET source cards preserve issue time and delayed download age', 'Issued 2026-11-04T08:00:00' in page.locator('[data-weather-cards]').inner_text() and 'Update delayed' in page.locator('[data-weather-cards]').inner_text())
        page.locator('[data-weather-status]').scroll_into_view_if_needed()
        page.screenshot(path=str(OUT / f'{engine}-delayed-update.png'))
        page.locator('[data-weather-route]>summary').click()
        # Stale AEMET snapshots must not gain a new age through reprojection.
        scenario['aemet'] = 'stale'
        page.evaluate('state.progressKm=0;weatherPanel.refresh(true)')
        page.wait_for_function('!weatherPanel.loading&&weatherPanel.cache.fromKm===0')
        check(checks, 'old AEMET downloads are rejected and fallback is visible', page.evaluate('AemetWeather.counts(weatherPanel.cache.rows).aemet') == 0 and 'Open-Meteo route forecast' in page.locator('[data-weather-provider]').inner_text())
        scenario['aemet'] = 'error'
        page.evaluate('weatherPanel.feed=null;weatherPanel.refresh(true)')
        page.wait_for_function('!weatherPanel.loading')
        check(checks, 'unavailable AEMET feed leaves a usable labelled fallback', page.evaluate('weatherPanel.cache.rows.every(r=>r.weather?.source?.provider==="open-meteo")'))
        scenario.update(aemet='ok', fallback='error')
        page.evaluate('weatherPanel.refresh(true)')
        page.wait_for_function('!weatherPanel.loading')
        check(checks, 'fallback outage retains AEMET while leaving remote hours missing', page.evaluate('AemetWeather.counts(weatherPanel.cache.rows).aemet>0&&AemetWeather.counts(weatherPanel.cache.rows).missing>0'))
        check(checks, 'partial-provider outage is explained', 'fallback unavailable' in page.locator('[data-weather-status]').inner_text())
        check(checks, 'missing rain samples stay unavailable', 'Unavailable' in page.locator('.weather-rainfall').inner_text())
        scenario['aemet'] = 'alerts_only'
        page.evaluate('weatherPanel.cache=null;weatherPanel.refresh(true)')
        page.wait_for_function('!weatherPanel.loading')
        check(checks, 'warnings remain visible when every numerical forecast is unavailable', page.evaluate('weatherPanel.cache===null') and page.locator('.weather-alert').count() == 1)
        scenario.update(aemet='trace', fallback='ok')
        page.evaluate('weatherPanel.refresh(true)')
        page.wait_for_function('!weatherPanel.loading')
        # Export preserves the selected AEMET source without new requests offline.
        page.locator('#toolsPanel>summary').click()
        with page.expect_download() as info:
            page.locator('#downloadHtml').click()
        file = ROOT / 'data/test_aemet_saved.html'
        info.value.save_as(str(file))
        check(checks, 'portable HTML embeds separately dated official outlook text', 'id="savedOutlookData"' in file.read_text())
        check(checks, 'portable HTML embeds the independently dated warning snapshot', 'id="savedAlertsData"' in file.read_text())
        offline = browser.new_context(service_workers='block', viewport={'width': 390, 'height': 844})
        offline.add_init_script(INIT + "Object.defineProperty(navigator,'onLine',{get:()=>false});")
        offline.route('**/*', lambda r: r.continue_() if r.request.url.startswith('http://127.0.0.1:8787/') else r.abort())
        o = offline.new_page()
        o.goto('http://127.0.0.1:8787/data/test_aemet_saved.html')
        o.wait_for_function('typeof weatherPanel!=="undefined"&&weatherPanel.cache')
        check(checks, 'portable offline HTML retains mixed source provenance and original forecasts', 'AEMET' in o.locator('[data-weather-provider]').inner_text() and 'Offline' in o.locator('[data-weather-status]').inner_text())
        check(checks, 'trace rain survives portable offline export without becoming unavailable', 'mm + trace' in o.locator('.weather-rainfall').inner_text())
        check(checks, 'hourly rain amounts and all forecast-point rain survive offline export', o.locator('.weather-stop-rain').count() > 0 and o.locator('.weather-rain-hours li').count() == 12)
        check(checks, 'offline HTML restores the warning, source times and offline label', o.locator('.weather-alert').count() == 1 and 'Offline' in o.locator('[data-weather-alerts]').inner_text() and '15 mm in 1 hour' in o.locator('[data-weather-alerts]').inner_text())
        check(checks, 'offline HTML also restores original regional text and its scope', o.locator('.island-day').count() == 4 and 'Offline' in o.locator('[data-weather-outlook]').inner_text())
        check(checks, 'English translations are available offline without a translation service', o.locator('.island-day>p[lang=en]:not(.island-significant)').count() == 4 and 'Cloudy intervals' in o.locator('[data-weather-outlook]').inner_text())
        o.locator('[data-outlook-sources]>summary').click()
        o.evaluate('weatherPanel.now=()=>Date.now()+5*24*3600000;weatherPanel.render()')
        check(checks, 'expired island bulletins are hidden rather than relabelled', o.locator('.island-day').count() == 0 and 'No current AEMET' in o.locator('[data-weather-outlook]').inner_text())
        check(checks, 'expired warnings never reappear as current or imply future safety', o.locator('.weather-alert').count() == 0 and 'status unavailable' in o.locator('[data-weather-alerts]').inner_text())
        offline.close()
        cached = browser.new_context(service_workers='block', storage_state=ctx.storage_state(), viewport={'width': 390, 'height': 844})
        cached.add_init_script(INIT + "Object.defineProperty(navigator,'onLine',{get:()=>false});")
        cached.route('**/*', lambda r: r.continue_() if r.request.url.startswith('http://127.0.0.1:8787/') else r.abort())
        c = cached.new_page()
        c.goto('http://127.0.0.1:8787')
        c.wait_for_function('typeof weatherPanel!=="undefined"&&weatherPanel.alerts')
        check(checks, 'ordinary offline app reload restores warnings from local storage with their original age', c.locator('.weather-alert').count() == 1 and 'Offline' in c.locator('[data-weather-alerts]').inner_text() and c.evaluate('weatherPanel.alerts.fetchedAt') == (NOW - 3600) * 1000)
        cached.close()
        page.get_by_role('tab', name='Map', exact=True).click()
        before = len(calls)
        page.evaluate('weatherPanel.update(true)')
        page.wait_for_timeout(800)
        check(checks, 'hidden panel does not poll providers', len(calls) == before)
        # Real captured 2 Nov feed: fresh but its fixed model run ends at 05:00
        # on 4 Nov, before the 09:00 start despite <48 clock hours remaining.
        pre = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True,
                                  has_touch=True, service_workers='block')
        pre.add_init_script("Date.now=()=>Date.parse('2026-11-02T10:53:00Z');")
        legacy = page.evaluate('weatherPanel.cache')
        legacy.pop('aemetStartAvailability', None)
        legacy['fetchedAt'] = int(datetime(2026, 11, 2, 10, 53, tzinfo=timezone.utc).timestamp() * 1000)
        pre.add_init_script("localStorage.setItem('canarias360-weather-v3'," + json.dumps(json.dumps(legacy)) + ');')
        fixture = json.loads((ROOT / 'tests/fixtures/aemet-galdar-20261102.json').read_text())
        def pre_intercept(route):
            url = route.request.url
            if 'raw.githubusercontent.com/bigreddog/360-26/weather-data/aemet.json' in url:
                route.fulfill(status=200, content_type='application/json', body=json.dumps(fixture))
            elif url.startswith('https://api.open-meteo.com/'):
                route.fulfill(status=200, content_type='application/json', body=json.dumps(fallback(url)))
            elif url.startswith('http://127.0.0.1:8787/'):
                route.continue_()
            else:
                route.abort()
        pre.route('**/*', pre_intercept)
        f = pre.new_page()
        f.on('pageerror', lambda e: errors.append(str(e)))
        f.goto('http://127.0.0.1:8787')
        f.wait_for_function('typeof weatherPanel!=="undefined"&&weatherPanel.cache?.aemetStartAvailability&&!weatherPanel.loading')
        check(checks, 'recent legacy v3 cache is refreshed once to add actual coverage diagnostics', f.evaluate('weatherPanel.cache.aemetStartAvailability.kind') == 'after')
        status = f.locator('[data-weather-status]').inner_text()
        check(checks, 'fresh short model horizon visibly explains 05:00 coverage vs 09:00 start', 'Gáldar' in status and '05:00' in status and '09:00' in status and 'Open-Meteo' in status)
        check(checks, 'out-of-coverage start retains valid fallback rather than extending AEMET', f.evaluate('weatherPanel.cache.rows[0].weather.source.provider') == 'open-meteo')
        check(checks, 'coverage explanation fits phone width', f.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
        f.locator('#weatherPanel').evaluate('e=>window.scrollTo(0,e.offsetTop-75)')
        f.screenshot(path=str(OUT / f'{engine}-start-coverage.png'))
        # Simulate the next published run, not invented production weather.
        last = fixture['towns'][0]['hourly'][-1]
        fixture['towns'][0]['hourly'].extend([{**last, 'time': last['time'] + i * 3600} for i in range(1, 7)])
        f.locator('[data-weather-refresh]').click()
        f.wait_for_function('!weatherPanel.loading&&weatherPanel.cache.rows[0].weather.source.provider==="aemet"')
        check(checks, 'next run automatically supplies AEMET when its actual coverage reaches the start', f.evaluate('weatherPanel.cache.aemetStartAvailability.kind') == 'covered' and '05:00' not in f.locator('[data-weather-status]').inner_text())
        pre.close()
        check(checks, 'no JavaScript errors during AEMET journeys', not errors)
        ctx.close()
        browser.close()
        records.append({'browser': engine, 'passed': len(checks), 'checks': checks})
result = {'passed': sum(r['passed'] for r in records), 'results': records,
          'mocked_forecasts': True, 'physical_device_test': False}
(ROOT / 'docs/aemet-browser-tests.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
