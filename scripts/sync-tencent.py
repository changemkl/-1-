"""Read public-business spreadsheet via Tencent's authenticated official API."""
import datetime
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

OUTPUT = Path('public/tencent-data.json')
ENCODED_ID = 'DTEhRanNnS3dJV2hm'
SHEET_ID = 'BB08J2'


def request_api(path, headers):
    request = urllib.request.Request('https://docs.qq.com' + path, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'Tencent API HTTP {exc.code}; check credentials, permissions and quota') from None
    code = result.get('ret', result.get('code'))
    if code != 0:
        # Do not log full responses, which may contain private authentication details.
        raise RuntimeError(f'Tencent API business code {code}; check token, read permissions and document access')
    return result.get('data', result)


def cell_text(cell):
    value = cell.get('cellValue') or {}
    for key in ('text', 'number', 'boolean', 'date', 'dateTime'):
        if key in value:
            return str(value[key])
    if 'location' in value:
        return str(value['location'].get('name', ''))
    if value:
        return json.dumps(value, ensure_ascii=False)
    return ''


def main():
    names = {'Access-Token': 'TENCENT_DOCS_ACCESS_TOKEN', 'Client-Id': 'TENCENT_DOCS_CLIENT_ID', 'Open-Id': 'TENCENT_DOCS_OPEN_ID'}
    missing = [v for v in names.values() if not os.environ.get(v)]
    if missing:
        raise RuntimeError('Missing GitHub Secrets: ' + ', '.join(missing))
    headers = {k: os.environ[v] for k, v in names.items()}
    headers['Accept'] = 'application/json'
    old = json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {}
    file_id = old.get('fileId') if old.get('encodedId') == ENCODED_ID else None
    if not file_id:
        data = request_api('/openapi/drive/v2/util/converter?' + urllib.parse.urlencode({'type': 2, 'value': ENCODED_ID}), headers)
        file_id = data['fileID']
    # A:Z, 300 rows per page = 7,800 cells, within the documented 10,000-cell limit.
    # Continue until an empty page; preserve previous data if the safety bound is exceeded.
    rows = []
    for start in range(1, 6001, 300):
        area = f'A{start}:Z{start + 299}'
        path = '/openapi/spreadsheet/v3/files/' + '/'.join(urllib.parse.quote(v, safe='') for v in (file_id, SHEET_ID, area))
        data = request_api(path, headers)
        grid = data.get('gridData')
        if not isinstance(grid, dict) or not isinstance(grid.get('rows'), list):
            raise RuntimeError('Unexpected gridData response; previous published data retained')
        page = [[cell_text(c) for c in r.get('values', [])] for r in grid['rows']]
        if not any(any(v.strip() for v in r) for r in page):
            break
        rows.extend(page)
    else:
        raise RuntimeError('Spreadsheet exceeds 6,000-row safety bound; previous data retained')
    while rows and not any(v.strip() for v in rows[-1]):
        rows.pop()
    if not rows:
        raise RuntimeError('Empty spreadsheet; previous published data retained')
    payload = {'encodedId': ENCODED_ID, 'fileId': file_id, 'sheetId': SHEET_ID, 'rows': rows,
               'source': 'https://docs.qq.com/sheet/' + ENCODED_ID + '?tab=' + SHEET_ID}
    if all(old.get(k) == v for k, v in payload.items()):
        print('No spreadsheet changes; no publication needed')
        return
    payload['updatedAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    temp = OUTPUT.with_suffix('.tmp')
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    temp.replace(OUTPUT)
    print(f'Saved {len(rows)} spreadsheet rows; no credentials included')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Sync failed: {exc}', file=sys.stderr)
        sys.exit(1)
