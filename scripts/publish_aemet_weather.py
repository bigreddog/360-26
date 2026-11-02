"""Publish the weather-only branch, keeping automated refreshes out of app history.

Uses the workflow's built-in GH_TOKEN; no AEMET key. Never puts credentials in JSON.
"""
import argparse
import base64
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO = 'bigreddog/360-26'
BRANCH = 'weather-data'


def api(path, data=None, method=None):
    request = Request('https://api.github.com/repos/' + REPO + '/' + path,
                      data=json.dumps(data).encode() if data is not None else None, method=method,
                      headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                               'Accept': 'application/vnd.github+json',
                               'Content-Type': 'application/json', 'User-Agent': 'Canarias360-weather-cache'})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--download-only', action='store_true')
    p.add_argument('--file', type=Path, default=Path('data/weather/aemet.json'))
    args = p.parse_args()
    try:
        old = api('contents/aemet.json?ref=' + BRANCH)
    except HTTPError as error:
        if error.code != 404:
            raise
        old = None
    if args.download_only:
        if old:
            args.file.parent.mkdir(parents=True, exist_ok=True)
            args.file.write_bytes(base64.b64decode(old['content']))
        return
    data = json.loads(args.file.read_text())
    assert data['version'] == 1 and data['provider'] == 'aemet' and (data['towns'] or data.get('outlook', {}).get('entries'))
    if not old:
        try:
            api('git/ref/heads/' + BRANCH)
        except HTTPError as error:
            if error.code != 404:
                raise
            head = api('git/ref/heads/main')['object']['sha']
            api('git/refs', {'ref': 'refs/heads/' + BRANCH, 'sha': head})
    body = {'message': 'Refresh AEMET hourly weather cache', 'branch': BRANCH,
            'content': base64.b64encode(args.file.read_bytes()).decode()}
    if old:
        body['sha'] = old['sha']
    result = api('contents/aemet.json', body, method='PUT')
    print('Published AEMET cache: ' + result['commit']['sha'])


if __name__ == '__main__':
    main()
