"""Cache AEMET's public numerical hourly XML. No API key or browser proxy required.

Capital coordinates/altitudes come from AEMET's linked official town pages.
No colour-map inversion, altitude correction, probability disaggregation or gap fill.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import time
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc
HOUR = 3600
SKY = {11: 0, 12: 1, 13: 2, 14: 3, 15: 3, 16: 3, 17: 2,
       23: 61, 24: 61, 25: 61, 26: 61, 33: 71, 34: 71, 35: 71, 36: 71,
       43: 61, 44: 61, 45: 61, 46: 61, 51: 95, 52: 95, 53: 95, 54: 95,
       61: 95, 62: 95, 63: 95, 64: 95, 71: 71, 72: 71, 73: 71, 74: 71,
       81: 45, 82: 45}
DIRECTIONS = {'N': 0, 'NNE': 22.5, 'NE': 45, 'ENE': 67.5, 'E': 90,
              'ESE': 112.5, 'SE': 135, 'SSE': 157.5, 'S': 180,
              'SSO': 202.5, 'SO': 225, 'OSO': 247.5, 'O': 270,
              'ONO': 292.5, 'NO': 315, 'NNO': 337.5}


def number(text):
    try:
        n = float(text)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def parse_xml(raw: bytes, town: dict, fetched: datetime) -> dict:
    root = ET.fromstring(raw)
    if root.get('id') != town['id']:
        raise ValueError('AEMET returned a different municipality')
    rows, probabilities = {}, []
    zone = ZoneInfo(town['timezone'])
    for day in root.findall('./prediccion/dia'):
        date = day.attrib['fecha']
        # Instantaneous variables use the capital's local time. Multi-hour
        # precipitation probabilities use UTC per AEMET's interpretation guide.
        local_midnight = datetime.fromisoformat(date).replace(tzinfo=zone)
        utc_midnight = datetime.fromisoformat(date).replace(tzinfo=UTC)
        for child in day:
            period = child.get('periodo', '')
            if child.tag == 'prob_precipitacion' and len(period) == 4 and period.isdigit():
                a, b = int(period[:2]), int(period[2:])
                if a > 23 or b > 24:
                    continue
                if b <= a:
                    b += 24
                value = number(child.text)
                if value is not None and 0 <= value <= 100:
                    probabilities.append({'start': int((utc_midnight + timedelta(hours=a)).timestamp()),
                                          'end': int((utc_midnight + timedelta(hours=b)).timestamp()),
                                          'value': value, 'hours': b - a})
                continue
            if len(period) != 2 or not period.isdigit() or int(period) > 23:
                continue
            when = int((local_midnight + timedelta(hours=int(period))).timestamp())
            row = rows.setdefault(when, {'time': when})
            if child.tag == 'estado_cielo':
                code = (child.text or '').strip()
                row['code'] = SKY.get(int(code.removesuffix('n'))) if code.removesuffix('n').isdigit() else None
                row['day'] = 0 if code.endswith('n') else 1 if code else None
            elif child.tag == 'viento':
                row['wind'] = number(child.findtext('velocidad'))
                row['direction'] = DIRECTIONS.get(child.findtext('direccion'))
            else:
                key = {'temperatura': 'temperature', 'sens_termica': 'feels',
                       'precipitacion': 'rain', 'racha_max': 'gust'}.get(child.tag)
                if key:
                    # Rain and gusts describe the following hour; keep this
                    # explicit rather than confusing them with instantaneous data.
                    row[key] = number(child.text)
    hourly = sorted(rows.values(), key=lambda r: r['time'])
    if not any(number(r.get('temperature')) is not None for r in hourly):
        raise ValueError('No numerical hourly temperatures in AEMET response')
    if hourly[-1]['time'] < fetched.timestamp() - HOUR:
        raise ValueError('AEMET response has no current or future forecast')
    return {**town, 'issuedLocal': root.findtext('elaborado'),
            'fetchedAt': int(fetched.timestamp() * 1000),
            'sourceSha256': hashlib.sha256(raw).hexdigest(),
            'hourly': hourly, 'probabilities': probabilities}


def download(town):
    for attempt in range(3):
        try:
            request = Request(town['xml_url'], headers={'User-Agent': 'Canarias360-Roadbook/1.0'})
            with urlopen(request, timeout=25) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError('Oversized weather response')
            return parse_xml(raw, town, datetime.now(UTC))
        except Exception as error:
            if attempt == 2:
                return {'id': town['id'], 'error': type(error).__name__}
            time.sleep(attempt + 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'data/weather/aemet.json')
    args = parser.parse_args()
    towns = json.loads((ROOT / 'data/weather/aemet-towns.json').read_text())['towns']
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(download, towns))
    usable = [r for r in results if 'hourly' in r]
    errors = [r for r in results if 'error' in r]
    if not usable:
        raise RuntimeError('All AEMET feeds failed; leaving the previous snapshot untouched')
    # Preserve a failed town's last snapshot with its ORIGINAL fetch timestamp.
    # Browser eligibility rejects old data rather than refreshing its age.
    old = json.loads(args.output.read_text()) if args.output.exists() else {}
    usable += [t for t in old.get('towns', []) if t['id'] in {e['id'] for e in errors}]
    result = {'version': 1, 'provider': 'aemet', 'product': 'municipal-hourly',
              'generatedAt': int(datetime.now(UTC).timestamp() * 1000),
              'attribution': 'Weather data © AEMET. Reused with attribution.',
              'source': 'https://www.aemet.es/es/eltiempo/prediccion/municipios/',
              'units': {'temperature': '°C', 'wind': 'km/h', 'rain': 'mm'},
              'rainInterval': 'following hour', 'probabilityPeriods': 'UTC',
              'towns': sorted(usable, key=lambda t: t['id']), 'errors': errors}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n')
    temporary.replace(args.output)
    print(f'AEMET: {len(usable)} town forecasts, {len(errors)} fetch failures; {args.output.stat().st_size:,} bytes')


if __name__ == '__main__':
    main()
