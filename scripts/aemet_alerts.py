"""AEMET's authoritative Gran Canaria CAP snapshot; stdlib, no API key."""
from datetime import datetime, timezone
from io import BytesIO
import hashlib
import tarfile
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

RSS = 'https://www.aemet.es/documentos_d/eltiempo/prediccion/avisos/rss/CAP_AFAP6590_RSS.xml'
PAGE = 'https://www.aemet.es/es/eltiempo/prediccion/avisos?w=hoy&p=6590'
NS = {'c': 'urn:oasis:names:tc:emergency:cap:1.2'}
AREAS = {'659001': 'North of Gran Canaria', '659003': 'Gran Canaria summits',
         '659004': 'East, south and west of Gran Canaria'}
EVENTS = {'PR': 'Rain', 'TO': 'Thunderstorms', 'VI': 'Wind', 'CO': 'Coastal conditions',
          'TA': 'High temperatures', 'TI': 'Low temperatures', 'NE': 'Snow',
          'NI': 'Fog', 'RM': 'Thaw', 'AL': 'Avalanches', 'AC': 'Dust'}
LEVELS = {'amarillo': 'yellow', 'naranja': 'orange', 'rojo': 'red'}


def stamp(text):
    value = datetime.fromisoformat(text)
    if value.tzinfo is None:
        raise ValueError('CAP time has no UTC offset')
    return int(value.timestamp() * 1000)


def trusted(url, suffix):
    p = urlparse(url)
    if p.scheme != 'https' or p.netloc != 'www.aemet.es' or not p.path.startswith('/documentos_d/eltiempo/prediccion/avisos/cap/') or not p.path.endswith(suffix):
        raise ValueError('Unexpected AEMET CAP URL')
    return url


def snapshot_url(raw):
    root = ET.fromstring(raw)
    issued = stamp(root.findtext('./channel/lastBuildDate'))
    links = [i.findtext('link') for i in root.findall('./channel/item')
             if (i.findtext('link') or '').endswith('_AFAP6590.tar.gz')]
    if len(links) != 1:
        raise ValueError('Missing unique complete Gran Canaria warning snapshot')
    return trusted(links[0], '.tar.gz'), issued


def parse_cap(raw, source_url):
    root = ET.fromstring(raw)
    get = lambda node, key: node.findtext('c:' + key, default='', namespaces=NS).strip()
    if root.tag != '{urn:oasis:names:tc:emergency:cap:1.2}alert':
        raise ValueError('Unexpected CAP namespace')
    if get(root, 'status') != 'Actual' or get(root, 'scope') != 'Public':
        return None
    kind = get(root, 'msgType')
    if kind not in ['Alert', 'Update', 'Cancel']:
        return None
    identifier, sent = get(root, 'identifier'), stamp(get(root, 'sent'))
    if not identifier:
        raise ValueError('Missing CAP identifier')
    references = [r.split(',')[1] for r in get(root, 'references').split() if len(r.split(',')) == 3]
    message = {'id': identifier, 'sent': sent, 'type': kind, 'references': references, 'entries': [], 'until': 0}
    if kind == 'Cancel':
        return message
    infos = root.findall('c:info', NS)
    spanish = next((i for i in infos if get(i, 'language') in ['es-ES', 'es']), None)
    english = next((i for i in infos if get(i, 'language').startswith('en')), None)
    if spanish is None:
        raise ValueError('Missing Spanish CAP information')
    info = english if english is not None else spanish
    start, end = stamp(get(spanish, 'onset')), stamp(get(spanish, 'expires'))
    if end <= start:
        raise ValueError('Invalid CAP validity')
    message['until'] = end
    params_es = {get(p, 'valueName'): get(p, 'value') for p in spanish.findall('c:parameter', NS)}
    level_text = params_es.get('AEMET-Meteoalerta nivel')
    if level_text == 'verde':
        return message
    if level_text not in LEVELS:
        raise ValueError('Unknown CAP warning level')
    code = next((get(p, 'value').split(';')[0] for p in spanish.findall('c:eventCode', NS)
                 if get(p, 'valueName') == 'AEMET-Meteoalerta fenomeno'), '')
    parameters = []
    for p in info.findall('c:parameter', NS):
        if get(p, 'valueName') == 'AEMET-Meteoalerta parametro':
            parts = get(p, 'value').split(';', 2)
            if len(parts) == 3:
                parameters.append({'code': parts[0], 'label': parts[1], 'value': parts[2]})
    areas = spanish.findall('c:area', NS)
    if not areas:
        raise ValueError('Missing CAP warning area')
    for area in areas:
        name = get(area, 'areaDesc')
        zone = next((get(g, 'value') for g in area.findall('c:geocode', NS)
                     if get(g, 'valueName') == 'AEMET-Meteoalerta zona'), '')
        if not zone.startswith('6590') and 'Gran Canaria' not in name:
            raise ValueError('Unexpected island in Gran Canaria CAP archive')
        message['entries'].append({'id': identifier + ':' + zone, 'capId': identifier,
            'sent': sent, 'from': start, 'until': end, 'level': LEVELS[level_text],
            'eventCode': code, 'event': EVENTS.get(code, 'Weather warning'),
            'zone': zone, 'area': AREAS.get(zone, name), 'areaOriginal': name,
            'parameters': parameters, 'descriptionOriginal': get(spanish, 'description'),
            'descriptionOfficialEnglish': get(english, 'description') if english is not None else '',
            'instruction': get(english, 'instruction') if english is not None else '',
            'sourceUrl': source_url, 'sourceSha256': hashlib.sha256(raw).hexdigest()})
    return message


def parse_archive(raw, archive_url, issued, fetched):
    messages, total = [], 0
    with tarfile.open(fileobj=BytesIO(raw), mode='r:gz') as archive:
        members = archive.getmembers()
        if not members or len(members) > 300:
            raise ValueError('Empty or oversized CAP archive')
        for member in members:
            if not member.isfile() or not member.name.endswith('.xml') or '/' in member.name or member.size > 200_000:
                raise ValueError('Unexpected CAP archive member')
            total += member.size
            if total > 12_000_000:
                raise ValueError('Oversized uncompressed CAP archive')
            # Read in memory. Never extract archive-supplied filesystem paths.
            message = parse_cap(archive.extractfile(member).read(), trusted(archive_url.rsplit('/', 1)[0] + '/' + member.name, '.xml'))
            if message:
                messages.append(message)
    if not messages:
        raise ValueError('No actual public messages in warning snapshot')
    removed = {ref for m in messages if m['type'] in ['Update', 'Cancel'] for ref in m['references']}
    entries = {}
    for message in sorted(messages, key=lambda m: m['sent']):
        if message['id'] in removed or message['type'] == 'Cancel':
            continue
        for e in message['entries']:
            entries[(e['zone'], e['eventCode'], e['from'], e['until'])] = e
    return {'version': 1, 'provider': 'aemet', 'scope': 'Gran Canaria',
            'fetchedAt': int(fetched.timestamp() * 1000), 'issuedAt': issued,
            'coverageUntil': max(m['until'] for m in messages),
            'sourceUrl': RSS, 'pageUrl': PAGE, 'archiveUrl': archive_url,
            'sourceSha256': hashlib.sha256(raw).hexdigest(),
            'entries': sorted(entries.values(), key=lambda e: (e['from'], e['eventCode'], e['zone']))}


def download_alerts(previous=None):
    try:
        request = lambda url: Request(url, headers={'User-Agent': 'Canarias360-Roadbook/1.0'})
        with urlopen(request(RSS), timeout=25) as response:
            rss = response.read(1_000_001)
        if len(rss) > 1_000_000:
            raise ValueError('Oversized warning RSS')
        url, issued = snapshot_url(rss)
        with urlopen(request(url), timeout=25) as response:
            raw = response.read(4_000_001)
        if len(raw) > 4_000_000:
            raise ValueError('Oversized compressed CAP archive')
        return parse_archive(raw, url, issued, datetime.now(timezone.utc))
    except Exception as error:
        # Original download age remains intact; failure is never an all-clear.
        result = dict(previous) if isinstance(previous, dict) and previous.get('version') == 1 else {'version': 1, 'provider': 'aemet', 'scope': 'Gran Canaria', 'entries': [], 'fetchedAt': None}
        result['error'] = type(error).__name__
        return result
