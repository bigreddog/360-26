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
INIT = f'Date.now=()=>{NOW * 1000};'


def feed(mode='ok'):
    towns = [{**town, 'fetchedAt': (NOW - (7 * 3600 if mode == 'stale' else 3600)) * 1000,
              'issuedLocal': '2026-11-04T08:00:00',
              'hourly': [{'time': NOW + i * 3600, 'temperature': 12, 'feels': 10,
                          'wind': 22, 'gust': 35, 'direction': 0, 'rain': .5,
                          'code': 1, 'day': 1} for i in range(-2, 71)],
              'probabilities': [{'start': NOW - 10800 + i * 21600,
                                 'end': NOW - 10800 + (i + 1) * 21600,
                                 'value': 70, 'hours': 6} for i in range(13)]} for town in TOWNS]
    return {'version': 1, 'provider': 'aemet', 'generatedAt': NOW * 1000, 'towns': towns}


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
        before = len(calls)
        page.locator('[data-weather-hours="24"]').click()
        check(checks, 'horizon switch uses the same mixed forecast without new requests', len(calls) == before)
        page.locator('[data-weather-route]>summary').click()
        text = page.locator('[data-weather-cards]').inner_text()
        check(checks, 'stop cards name the town, mismatch and uncorrected altitude', 'Gáldar' in text and 'vs town' in text and 'no altitude correction' in text)
        check(checks, 'AEMET six-hour chance is labelled at the stop', '6-h rain chance' in text)
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
        # Export preserves the selected AEMET source without new requests offline.
        page.locator('#toolsPanel>summary').click()
        with page.expect_download() as info:
            page.locator('#downloadHtml').click()
        file = ROOT / 'data/test_aemet_saved.html'
        info.value.save_as(str(file))
        offline = browser.new_context(service_workers='block', viewport={'width': 390, 'height': 844})
        offline.add_init_script(INIT + "Object.defineProperty(navigator,'onLine',{get:()=>false});")
        offline.route('**/*', lambda r: r.continue_() if r.request.url.startswith('http://127.0.0.1:8787/') else r.abort())
        o = offline.new_page()
        o.goto('http://127.0.0.1:8787/data/test_aemet_saved.html')
        o.wait_for_function('typeof weatherPanel!=="undefined"&&weatherPanel.cache')
        check(checks, 'portable offline HTML retains mixed source provenance and original forecasts', 'AEMET' in o.locator('[data-weather-provider]').inner_text() and 'Offline' in o.locator('[data-weather-status]').inner_text())
        offline.close()
        page.get_by_role('tab', name='Map', exact=True).click()
        before = len(calls)
        page.evaluate('weatherPanel.update(true)')
        page.wait_for_timeout(800)
        check(checks, 'hidden panel does not poll providers', len(calls) == before)
        check(checks, 'no JavaScript errors during AEMET journeys', not errors)
        ctx.close()
        browser.close()
        records.append({'browser': engine, 'passed': len(checks), 'checks': checks})
result = {'passed': sum(r['passed'] for r in records), 'results': records,
          'mocked_forecasts': True, 'physical_device_test': False}
(ROOT / 'docs/aemet-browser-tests.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
