"""Real AEMET CAP archive, cancellations and failed updates; no network."""
from datetime import datetime, timezone
from io import BytesIO
import importlib.util
from pathlib import Path
import tarfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('alerts', ROOT/'scripts/aemet_alerts.py')
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)
NOW = datetime(2026, 11, 3, 11, 52, tzinfo=timezone.utc)
URL = 'https://www.aemet.es/documentos_d/eltiempo/prediccion/avisos/cap/snapshot_AFAP6590.tar.gz'


def cap(ident='one', kind='Alert', ref='', sent='2026-11-03T10:00:00Z', level='amarillo', status='Actual', onset='2026-11-04T11:00:00Z', until='2026-11-04T19:59:59Z', zone='659001'):
    return f'''<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2"><identifier>{ident}</identifier><sender>http://www.aemet.es</sender><sent>{sent}</sent><status>{status}</status><scope>Public</scope><msgType>{kind}</msgType><references>{ref}</references><info><language>es-ES</language><onset>{onset}</onset><expires>{until}</expires><eventCode><valueName>AEMET-Meteoalerta fenomeno</valueName><value>PR;Lluvias</value></eventCode><parameter><valueName>AEMET-Meteoalerta nivel</valueName><value>{level}</value></parameter><area><areaDesc>Test area</areaDesc><geocode><valueName>AEMET-Meteoalerta zona</valueName><value>{zone}</value></geocode></area></info></alert>'''.encode()


def archive(*items):
    stream = BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as t:
        for name, raw in items:
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            t.addfile(info, BytesIO(raw))
    return stream.getvalue()


class Alerts(unittest.TestCase):
    def parse(self, *items):
        return A.parse_archive(archive(*items), URL, int(NOW.timestamp()*1000), NOW)

    def test_real_archive_thresholds_areas_and_source_coverage(self):
        url, issued = A.snapshot_url((ROOT/'tests/fixtures/aemet-alerts-20261103-rss.xml').read_bytes())
        a = A.parse_archive((ROOT/'tests/fixtures/aemet-alerts-20261103.tar.gz').read_bytes(), url, issued, NOW)
        self.assertEqual(len(a['entries']),9)
        self.assertEqual({e['zone'] for e in a['entries']},set(A.AREAS))
        tomorrow=[e for e in a['entries'] if e['from']==A.stamp('2026-11-04T11:00:00Z')]
        self.assertEqual(len(tomorrow),3)
        self.assertTrue(all(e['parameters'][0]['value']=='15 mm' for e in tomorrow))
        self.assertEqual(a['coverageUntil'],A.stamp('2026-11-05T23:59:59Z'))
        self.assertEqual(a['fetchedAt'],int(NOW.timestamp()*1000))
        self.assertTrue(all(e['instruction'].startswith('Be aware') for e in a['entries']))

    def test_green_snapshot_is_successful_empty(self):
        self.assertEqual(self.parse(('green.xml',cap(level='verde')))['entries'],[])

    def test_update_removes_referenced_warning_with_changed_validity(self):
        a=self.parse(('old.xml',cap(ident='old')),('new.xml',cap(ident='new',kind='Update',ref='sender,old,2026-11-03T10:00:00Z',sent='2026-11-03T11:00:00Z',until='2026-11-04T18:00:00Z')))
        self.assertEqual([e['capId'] for e in a['entries']],['new'])

    def test_cancel_removes_referenced_warning(self):
        a=self.parse(('old.xml',cap(ident='old')),('cancel.xml',cap(kind='Cancel',ref='sender,old,2026-11-03T10:00:00Z')))
        self.assertEqual(a['entries'],[])

    def test_green_update_withdraws_only_its_referenced_warning(self):
        a=self.parse(('old.xml',cap(ident='old')),('other.xml',cap(ident='other',zone='659003')),('green.xml',cap(ident='green',kind='Update',level='verde',ref='sender,old,2026-11-03T10:00:00Z')))
        self.assertEqual([e['capId'] for e in a['entries']],['other'])

    def test_duplicate_logical_warning_uses_latest_issue(self):
        a=self.parse(('old.xml',cap()),('new.xml',cap(ident='new',sent='2026-11-03T11:00:00Z')))
        self.assertEqual([e['capId'] for e in a['entries']],['new'])

    def test_test_messages_cannot_establish_an_all_clear(self):
        with self.assertRaises(ValueError):self.parse(('test.xml',cap(status='Test')))

    def test_wrong_zone_level_and_missing_time_offset_fail(self):
        for raw in [cap(zone='999999'),cap(level='unknown'),cap(onset='2026-11-04T11:00:00')]:
            with self.assertRaises(ValueError):self.parse(('bad.xml',raw))

    def test_archive_members_never_extract_paths(self):
        for name in ['../bad.xml','/bad.xml','nested/bad.xml','bad.txt']:
            with self.assertRaises(ValueError):self.parse((name,cap()))

    def test_oversized_and_empty_archive_are_rejected(self):
        for raw in [archive(),archive(('huge.xml',b'x'*200001))]:
            with self.assertRaises(ValueError):A.parse_archive(raw,URL,0,NOW)

    def test_snapshot_must_be_complete_and_from_official_host(self):
        for url in ['https://evil.example/test_AFAP6590.tar.gz','http://www.aemet.es/documentos_d/eltiempo/prediccion/avisos/cap/test_AFAP6590.tar.gz']:
            with self.assertRaises(ValueError):A.trusted(url,'.tar.gz')
        with self.assertRaises(ValueError):A.snapshot_url(b'<rss><channel><lastBuildDate>2026-11-03T10:00:00Z</lastBuildDate></channel></rss>')

    def test_failed_refresh_retains_original_warning_age(self):
        old=self.parse(('one.xml',cap()))
        with patch.object(A,'urlopen',side_effect=OSError):a=A.download_alerts(old)
        self.assertEqual(a['fetchedAt'],old['fetchedAt'])
        self.assertEqual(a['entries'],old['entries'])
        self.assertEqual(a['error'],'OSError')

    def test_failure_without_snapshot_is_unavailable(self):
        with patch.object(A,'urlopen',side_effect=OSError):a=A.download_alerts()
        self.assertIsNone(a['fetchedAt'])
        self.assertIn('error',a)


if __name__=='__main__':unittest.main()
