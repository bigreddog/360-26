"""Translate public AEMET text locally in the scheduled job, never on the phone.

Original text and issue/validity times stay unchanged. Reuse requires exact
paragraph equality; changed text cannot inherit an older English translation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SENTENCE = re.compile(r'(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÜÑ¿¡0-9])')


def source_key(bulletin):
    text = json.dumps([bulletin['paragraphs'], bulletin['significant']],
                      ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(text.encode()).hexdigest()


def valid_english(english, bulletin):
    if not isinstance(english, dict):
        return False
    return (english.get('version') == 1 and english.get('language') == 'en'
            and english.get('method') in ('curated', 'machine')
            and english.get('sourceParagraphs') == bulletin['paragraphs']
            and english.get('sourceSignificant') == bulletin['significant']
            and all(isinstance(english.get(key), list)
                    and len(english[key]) == len(bulletin[key])
                    and all(isinstance(p, str) and 0 < len(p.strip()) <= 12000 for p in english[key])
                    for key in ['paragraphs', 'significant']))


def validate_text(source, english):
    """Basic failure checks, not a claim of certified translation accuracy."""
    if not english.strip() or len(english) > max(300, len(source) * 4):
        raise ValueError('Empty or implausibly long translation')
    if re.search(r'(.{4,30})\1{3}', english):
        raise ValueError('Repetitive translation')
    numbers = lambda text: Counter(n.replace(',', '.') for n in re.findall(r'\d+(?:[.,]\d+)?', text))
    if numbers(source) != numbers(english):
        raise ValueError('Translation changed numerical values')
    if re.search(r'baja probabilidad', source, re.I) and not re.search(r'low (?:chance|probability)|small chance', english, re.I):
        raise ValueError('Translation lost low-probability qualifier')
    if re.search(r'no se descarta|sin descartar', source, re.I) and not re.search(r'ruled out|cannot|can.not|could|possible|may|might|not excluded', english, re.I):
        raise ValueError('Translation lost possibility qualifier')
    if re.search(r'calima', source, re.I) and not re.search(r'haze|dust', english, re.I):
        raise ValueError('Dust-haze terminology lost')
    if re.search(r'rachas', source, re.I) and not re.search(r'gust', english, re.I):
        raise ValueError('Wind-gust terminology lost')


def ensure_model():
    manifest = json.loads((ROOT / 'data/weather/translation-model.json').read_text())
    folder = Path(os.environ.get('CANARIAS360_TRANSLATION_MODEL_DIR',
                                str(Path.home() / '.cache/canarias360/marian-es-en')))
    folder.mkdir(parents=True, exist_ok=True)
    for record in manifest['files']:
        target = folder / record['name']
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == record['sha256']:
            continue
        url = f"https://huggingface.co/{manifest['name']}/resolve/{manifest['revision']}/{record['name']}"
        temporary = target.with_suffix('.download')
        try:
            with urlopen(Request(url, headers={'User-Agent': 'Canarias360-weather-translation/1.0'}), timeout=180) as response, temporary.open('wb') as out:
                count = 0
                while chunk := response.read(1024 * 1024):
                    count += len(chunk)
                    if count > record['bytes']:
                        raise ValueError('Oversized model download')
                    out.write(chunk)
            if hashlib.sha256(temporary.read_bytes()).hexdigest() != record['sha256']:
                raise ValueError('Translation model checksum mismatch')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    return folder, manifest


class Translator:
    def __init__(self):
        import torch
        from transformers import MarianMTModel, MarianTokenizer
        folder, self.manifest = ensure_model()
        torch.set_num_threads(2)
        self.torch = torch
        self.tokenizer = MarianTokenizer.from_pretrained(folder, local_files_only=True)
        self.model = MarianMTModel.from_pretrained(folder, local_files_only=True,
                                                   use_safetensors=False, weights_only=True).eval()

    def translate(self, text):
        # Explain regional weather terms to the general translation model. These
        # are equivalent Spanish phrases; the stored source stays untouched.
        normalized = re.sub(r'\bcalima\b', 'polvo atmosférico en suspensión', text, flags=re.I)
        normalized = re.sub(r'\bmedianías\b', 'zonas de altitud media', normalized, flags=re.I)
        normalized = re.sub(r'\brachas\b', 'ráfagas de viento', normalized, flags=re.I)
        sentences = SENTENCE.split(normalized)
        # Do not truncate a long source or silently accept an output token cap.
        for sentence in sentences:
            if len(self.tokenizer.encode(sentence)) > 400:
                raise ValueError('Source sentence exceeds translation input limit')
        inputs = self.tokenizer(sentences, return_tensors='pt', padding=True, truncation=False)
        with self.torch.inference_mode():
            result = self.model.generate(**inputs, num_beams=4, max_new_tokens=256)
        if any(len(tokens) >= 257 and int(tokens[-1]) != self.tokenizer.eos_token_id for tokens in result):
            raise ValueError('Translation reached output limit')
        english = ' '.join(self.tokenizer.batch_decode(result, skip_special_tokens=True))
        # Resolve literal dictionary senses in weather context, preserving
        # intensity, direction and all numerical values from the translation.
        if re.search(r'viento flojo', text, re.I):
            english = re.sub(r'\b(?:loose|weak|slack|soft|gentle) wind(s?)\b', r'light wind\1', english, flags=re.I)
        if re.search(r'cumbres', text, re.I):
            english = re.sub(r'\bin summits\b', 'on the summits', english, flags=re.I)
        english = re.sub(r'\btemperatures in ascent\b', 'temperatures rising', english, flags=re.I)
        english = re.sub(r'\btemperatures in decline\b', 'temperatures falling', english, flags=re.I)
        english = english[:1].upper() + english[1:]
        validate_text(text, english)
        return english


def translate_outlook(entries, previous=(), translator_factory=Translator, curated=None):
    if curated is None:
        curated = json.loads((ROOT / 'data/weather/curated-english-bulletins.json').read_text())['entries']
    known = {source_key({'paragraphs': e['sourceParagraphs'], 'significant': e['sourceSignificant']}): e for e in curated}
    reusable = {source_key(b): b['english'] for b in previous if valid_english(b.get('english'), b)}
    translator, model_error, errors = None, None, []
    for bulletin in entries:
        bulletin.pop('english', None)
        key = source_key(bulletin)
        try:
            if key in known:
                translated = known[key]
                english = {'method': 'curated', 'paragraphs': translated['paragraphs'],
                           'significant': translated['significant']}
            elif key in reusable:
                bulletin['english'] = reusable[key]
                continue
            else:
                if translator is None:
                    if model_error is not None:
                        raise model_error
                    try:
                        translator = translator_factory()
                    except Exception as error:
                        model_error = error
                        raise
                english = {'method': 'machine', 'paragraphs': [translator.translate(p) for p in bulletin['paragraphs']],
                           'significant': [translator.translate(p) for p in bulletin['significant']]}
                english['model'] = 'Helsinki-NLP/opus-mt-es-en'
                english['modelRevision'] = json.loads((ROOT / 'data/weather/translation-model.json').read_text())['revision']
            english.update({'version': 1, 'language': 'en', 'sourceTextSha256': key,
                            'sourceParagraphs': bulletin['paragraphs'][:],
                            'sourceSignificant': bulletin['significant'][:],
                            'translatedAt': int(datetime.now(timezone.utc).timestamp() * 1000)})
            if not valid_english(english, bulletin):
                raise ValueError('Incomplete English translation')
            bulletin['english'] = english
        except Exception as error:
            # Fresh Spanish remains publishable; an old English forecast never
            # substitutes for changed source text. Workflow verifies after publish.
            errors.append({'date': bulletin['date'], 'error': type(error).__name__})
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke-test', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if not args.smoke_test:
        parser.error('Use --smoke-test to check the real translator')
    translator = Translator()
    texts = ['No se descartan lluvias localmente fuertes.',
             'Baja probabilidad de lluvias ocasionales, débiles a moderadas.',
             'Calima ligera y disminuyendo.',
             'Viento flojo de componente sur, aumentando a moderado en cumbres.',
             'Temperaturas máximas en ascenso y mínimas en descenso.',
             'Rachas de 70 km/h en cumbres.']
    results = [{'spanish': text, 'english': translator.translate(text)} for text in texts]
    result = {'model': translator.manifest['name'], 'revision': translator.manifest['revision'],
              'checkedAt': datetime.now(timezone.utc).isoformat(), 'results': results}
    if args.report:
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
