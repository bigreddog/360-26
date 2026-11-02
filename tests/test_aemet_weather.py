"""Numeric AEMET ingestion and published capital metadata (no live calls)."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('aemet', ROOT / 'scripts/update_aemet_weather.py')
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)
TOWN = {'id': '35025', 'name': 'Tejeda', 'timezone': 'Atlantic/Canary'}
NOW = datetime(2026, 11, 1, 20, tzinfo=timezone.utc)


def xml(day='2026-11-02', body=''):
    return f'<root id="35025"><elaborado>2026-11-01T19:05:12</elaborado><prediccion><dia fecha="{day}">{body}</dia></prediccion></root>'.encode()


class TestAemet(unittest.TestCase):
    def test_live_source_fixture(self):
        raw = (ROOT / 'tests/fixtures/aemet-tejeda-20261101.xml').read_bytes()
        data = A.parse_xml(raw, TOWN, NOW)
        self.assertGreater(len(data['hourly']), 35)
        self.assertEqual(len(data['sourceSha256']), 64)
        self.assertEqual(data['issuedLocal'], '2026-11-01T19:05:12')

    def test_spanish_wind_and_units(self):
        data = A.parse_xml(xml(body='<temperatura periodo="09">10</temperatura><viento periodo="09"><direccion>SO</direccion><velocidad>18</velocidad></viento>'), TOWN, NOW)
        self.assertEqual(data['hourly'][0]['direction'], 225)
        self.assertEqual(data['hourly'][0]['wind'], 18)

    def test_unknown_direction_is_unavailable(self):
        data = A.parse_xml(xml(body='<temperatura periodo="09">10</temperatura><viento periodo="09"><direccion>VRB</direccion><velocidad>8</velocidad></viento>'), TOWN, NOW)
        self.assertIsNone(data['hourly'][0]['direction'])

    def test_missing_empty_and_trace_values_are_not_zero(self):
        self.assertIsNone(A.number(''))
        self.assertIsNone(A.number('Ip'))
        self.assertIsNone(A.number('NaN'))
        self.assertEqual(A.number('0'), 0)

    def test_unknown_sky_code_is_not_clear(self):
        data = A.parse_xml(xml(body='<temperatura periodo="09">10</temperatura><estado_cielo periodo="09">999</estado_cielo>'), TOWN, NOW)
        self.assertIsNone(data['hourly'][0]['code'])

    def test_night_and_light_snow_codes(self):
        data = A.parse_xml(xml(body='<temperatura periodo="09">0</temperatura><estado_cielo periodo="09">71n</estado_cielo>'), TOWN, NOW)
        self.assertEqual(data['hourly'][0]['code'], 71)
        self.assertEqual(data['hourly'][0]['day'], 0)

    def test_summer_instantaneous_hours_use_canary_local_time(self):
        data = A.parse_xml(xml('2027-07-01', '<temperatura periodo="09">20</temperatura>'), TOWN, NOW)
        self.assertEqual(datetime.fromtimestamp(data['hourly'][0]['time'], timezone.utc).hour, 8)

    def test_six_hour_probability_stays_utc_in_summer(self):
        data = A.parse_xml(xml('2027-07-01', '<temperatura periodo="09">20</temperatura><prob_precipitacion periodo="0612">65</prob_precipitacion>'), TOWN, NOW)
        p = data['probabilities'][0]
        self.assertEqual(datetime.fromtimestamp(p['start'], timezone.utc).hour, 6)
        self.assertEqual(p['end'] - p['start'], 6 * 3600)
        self.assertEqual(p['hours'], 6)
        self.assertEqual(p['value'], 65)

    def test_probability_crosses_midnight(self):
        data = A.parse_xml(xml(body='<temperatura periodo="09">20</temperatura><prob_precipitacion periodo="1800">80</prob_precipitacion>'), TOWN, NOW)
        p = data['probabilities'][0]
        self.assertEqual(datetime.fromtimestamp(p['end'], timezone.utc).day, 3)

    def test_invalid_probabilities_not_published(self):
        data = A.parse_xml(xml(body='<temperatura periodo="09">20</temperatura><prob_precipitacion periodo="0612">-999</prob_precipitacion>'), TOWN, NOW)
        self.assertEqual(data['probabilities'], [])

    def test_rain_retains_following_hour_timestamp(self):
        data = A.parse_xml(xml(body='<temperatura periodo="09">20</temperatura><precipitacion periodo="09">1.2</precipitacion>'), TOWN, NOW)
        self.assertEqual(data['hourly'][0]['rain'], 1.2)
        self.assertEqual(datetime.fromtimestamp(data['hourly'][0]['time'], timezone.utc).hour, 9)

    def test_wrong_town_and_empty_forecast_rejected(self):
        with self.assertRaises(ValueError):
            A.parse_xml(xml(), {**TOWN, 'id': '35009'}, NOW)
        with self.assertRaises(ValueError):
            A.parse_xml(xml(), TOWN, NOW)

    def test_old_forecast_rejected(self):
        with self.assertRaises(ValueError):
            A.parse_xml(xml('2026-10-01', '<temperatura periodo="09">20</temperatura>'), TOWN, NOW)

    def test_all_21_capitals_are_on_gran_canaria(self):
        towns = json.loads((ROOT / 'data/weather/aemet-towns.json').read_text())['towns']
        self.assertEqual(len(towns), 21)
        self.assertEqual(len({t['id'] for t in towns}), 21)
        self.assertIn('35020', {t['id'] for t in towns})
        for t in towns:
            self.assertTrue(27.7 < t['lat'] < 28.3 and -15.9 < t['lon'] < -15.3)
            self.assertTrue(0 <= t['elevation'] < 1400)
            self.assertTrue(t['url'].startswith('https://www.aemet.es/'))
            self.assertEqual(len(t['metadata_sha256']), 64)

    def test_island_text_is_parsed_without_city_temperature_table(self):
        raw = (ROOT / 'tests/fixtures/aemet-bulletin-20261102.xml').read_bytes()
        data = A.parse_bulletin(raw, '2026-11-02', 'https://www.aemet.es/source', NOW)
        self.assertEqual(data['area'], 'Gran Canaria')
        self.assertEqual(data['language'], 'es')
        self.assertIn('Nuboso', data['paragraphs'][0])
        self.assertNotIn('6535016', ' '.join(data['paragraphs']))
        self.assertEqual(data['until'] - data['from'], 24 * 3600000)
        self.assertEqual(data['issuedLocal'], '2026-11-01T14:35:18')

    def test_regional_fallback_keeps_its_broader_scope(self):
        raw = (ROOT / 'tests/fixtures/aemet-bulletin-20261104.xml').read_bytes()
        data = A.parse_bulletin(raw, '2026-11-04', 'https://www.aemet.es/source', NOW)
        self.assertEqual(data['area'], 'Canary Islands')

    def test_national_fallback_is_rejected(self):
        raw = (ROOT / 'tests/fixtures/aemet-bulletin-20261104.xml').read_bytes().replace(b'id="coo"', b'id="esp1"')
        with self.assertRaises(ValueError):
            A.parse_bulletin(raw, '2026-11-04', 'https://www.aemet.es/source', NOW)

    def test_wrong_bulletin_date_rejected(self):
        raw = (ROOT / 'tests/fixtures/aemet-bulletin-20261104.xml').read_bytes()
        with self.assertRaises(ValueError):
            A.parse_bulletin(raw, '2026-11-05', 'https://www.aemet.es/source', NOW)

    def test_empty_bulletin_not_invented(self):
        raw = b'<root id="90"><validez_ini>2026-11-02T00:00:00</validez_ini><validez_fin>2026-11-03T00:00:00</validez_fin><prediccion><txt_prediccion/></prediccion></root>'
        with self.assertRaises(ValueError):
            A.parse_bulletin(raw, '2026-11-02', 'https://www.aemet.es/source', NOW)


if __name__ == '__main__':
    unittest.main()
