"""Translation provenance, reuse and failure behaviour without downloading a model."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('translation', ROOT / 'scripts/translate_bulletins.py')
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)
ORIGINAL = json.loads((ROOT / 'tests/fixtures/aemet-island-outlook-20261102.json').read_text())['entries']


class FakeTranslator:
    calls = []

    def translate(self, text):
        self.calls.append(text)
        return 'Updated English forecast.'


class TranslationTests(unittest.TestCase):
    def test_all_current_bulletins_have_curated_english(self):
        rows = deepcopy(ORIGINAL)
        def unavailable():
            raise AssertionError('Known text should not need a model')
        self.assertEqual(T.translate_outlook(rows, translator_factory=unavailable), [])
        self.assertEqual(len(rows), 4)
        for row in rows:
            self.assertTrue(T.valid_english(row['english'], row))
            self.assertEqual(row['english']['method'], 'curated')

    def test_likelihood_and_mountain_wind_are_preserved_in_current_translations(self):
        rows = deepcopy(ORIGINAL)
        T.translate_outlook(rows)
        self.assertIn('low chance', rows[0]['english']['paragraphs'][0])
        self.assertIn('possibly accompanied by thunderstorms', rows[1]['english']['paragraphs'][0])
        self.assertIn('stronger on the summits', rows[2]['english']['paragraphs'][0])
        self.assertIn('cannot be ruled out', rows[3]['english']['paragraphs'][0])

    def test_source_text_and_download_times_are_unchanged(self):
        rows = deepcopy(ORIGINAL)
        T.translate_outlook(rows)
        for before, after in zip(ORIGINAL, rows):
            for key in before:
                self.assertEqual(before[key], after[key])

    def test_exact_previous_translation_reused(self):
        old = deepcopy(ORIGINAL[:1])
        T.translate_outlook(old)
        current = deepcopy(ORIGINAL[:1])
        current[0]['issuedLocal'] = '2026-11-02T12:00:00'
        self.assertEqual(T.translate_outlook(current, old, curated=[]), [])
        self.assertEqual(current[0]['english'], old[0]['english'])

    def test_changed_forecast_does_not_inherit_old_english(self):
        old = deepcopy(ORIGINAL[:1])
        T.translate_outlook(old)
        current = deepcopy(old)
        current[0]['paragraphs'] = ['Predicción nueva.']
        FakeTranslator.calls = []
        errors = T.translate_outlook(current, old, FakeTranslator, curated=[])
        self.assertEqual(errors, [])
        self.assertEqual(FakeTranslator.calls, ['Predicción nueva.'])
        self.assertEqual(current[0]['english']['paragraphs'], ['Updated English forecast.'])

    def test_new_significant_phenomena_also_invalidate_reuse(self):
        old = deepcopy(ORIGINAL[:1])
        T.translate_outlook(old)
        current = deepcopy(old)
        current[0]['significant'] = ['Lluvias fuertes.']
        FakeTranslator.calls = []
        self.assertEqual(T.translate_outlook(current, old, FakeTranslator, curated=[]), [])
        self.assertIn('Lluvias fuertes.', FakeTranslator.calls)
        self.assertEqual(len(current[0]['english']['significant']), 1)

    def test_failure_retains_fresh_spanish_without_stale_english(self):
        rows = deepcopy(ORIGINAL[:1])
        T.translate_outlook(rows)
        rows[0]['paragraphs'] = ['Otra predicción.']
        def failed():
            raise RuntimeError('Model unavailable')
        errors = T.translate_outlook(rows, translator_factory=failed, curated=[])
        self.assertEqual(len(errors), 1)
        self.assertNotIn('english', rows[0])
        self.assertEqual(rows[0]['paragraphs'], ['Otra predicción.'])

    def test_missing_or_mismatched_fields_rejected(self):
        row = deepcopy(ORIGINAL[0])
        self.assertFalse(T.valid_english(None, row))
        T.translate_outlook([row])
        e = deepcopy(row['english'])
        e['paragraphs'] = []
        self.assertFalse(T.valid_english(e, row))
        e = deepcopy(row['english'])
        e['sourceSignificant'] = ['Other warning']
        self.assertFalse(T.valid_english(e, row))

    def test_model_outage_does_not_repeat_large_download_for_each_day(self):
        rows = deepcopy(ORIGINAL[:2])
        calls = []
        def failed():
            calls.append(True)
            raise RuntimeError('Model unavailable')
        errors = T.translate_outlook(rows, translator_factory=failed, curated=[])
        self.assertEqual(len(errors), 2)
        self.assertEqual(len(calls), 1)

    def test_semantic_checks_reject_lost_qualifier_or_numbers(self):
        for source, bad in [('Baja probabilidad de lluvia.', 'Rain is certain.'),
                            ('No se descartan lluvias.', 'Rain will fall.'),
                            ('Rachas de 70 km/h.', 'Gusts of 7 km/h.'),
                            ('Calima ligera.', 'Light rain.')]:
            with self.assertRaises(ValueError):
                T.validate_text(source, bad)

    def test_empty_or_degenerate_output_rejected(self):
        for bad in ['', 'rain' * 60]:
            with self.assertRaises(ValueError):
                T.validate_text('Lluvia.', bad)

    def test_splitting_preserves_decimal_numbers(self):
        self.assertEqual(T.SENTENCE.split('Lluvia de 0.5 mm. Viento flojo.'),
                         ['Lluvia de 0.5 mm.', 'Viento flojo.'])

    def test_glossary_does_not_merge_dust_haze_into_previous_sentence(self):
        original = 'No se descarta granizo menudo. Calima ligera. Temperaturas sin cambios.'
        source, prepared = T.prepare_sentences(original)
        self.assertEqual(len(source), 3)
        self.assertEqual(len(prepared), 3)
        self.assertEqual(source[1], 'Calima ligera.')
        self.assertIn('polvo atmosférico en suspensión', prepared[1])
        self.assertIn('granizo de pequeño tamaño', prepared[0])

    def test_valid_literal_without_discarding_is_not_a_lost_qualifier(self):
        T.validate_text('Sin descartar precipitaciones dispersas.',
                        'Without discarding scattered precipitation.')
        with self.assertRaises(ValueError):
            T.validate_text('Sin descartar precipitaciones dispersas.',
                            'Scattered precipitation will occur.')

    def test_finished_padded_sentence_is_not_mistaken_for_truncation(self):
        T.validate_completion([99, 23, 0] + [99] * 254, eos_token_id=0)

    def test_forced_eos_at_limit_and_unfinished_translation_are_rejected(self):
        for tokens in [[99] + [23] * 255 + [0], [99, 23, 23]]:
            with self.assertRaisesRegex(ValueError, 'output limit'):
                T.validate_completion(tokens, eos_token_id=0)

    def test_rejected_schedule_has_faithful_curated_recovery(self):
        rows = json.loads((ROOT / 'tests/fixtures/aemet-island-outlook-rejected-20261102.json').read_text())['entries']
        self.assertEqual(T.translate_outlook(rows), [])
        for row in rows:
            self.assertTrue(T.valid_english(row['english'], row))
        self.assertIn('small hail cannot be ruled out', rows[1]['english']['paragraphs'][0])
        self.assertIn('north and east', rows[2]['english']['paragraphs'][0])

    def test_translation_failures_include_diagnostic_reason(self):
        def broken():
            raise ValueError('Translation reached output limit')
        rows = deepcopy(ORIGINAL[:1])
        errors = T.translate_outlook(rows, translator_factory=broken, curated=[])
        self.assertEqual(errors[0]['reason'], 'Translation reached output limit')

    def test_old_machine_recipe_is_regenerated(self):
        old = deepcopy(ORIGINAL[:1])
        T.translate_outlook(old)
        old[0]['english']['method'] = 'machine'
        old[0]['english']['recipe'] = 1
        current = deepcopy(ORIGINAL[:1])
        FakeTranslator.calls = []
        self.assertEqual(T.translate_outlook(current, old, FakeTranslator, curated=[]), [])
        self.assertEqual(len(FakeTranslator.calls), 1)
        self.assertEqual(current[0]['english']['recipe'], 2)


if __name__ == '__main__':
    unittest.main()
