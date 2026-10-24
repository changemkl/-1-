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
    code = result.get('ret', result.get('code', result.get('errcode')))
    if code is None and isinstance(result.get('gridData'), dict):
        return result
    if code is None:
        keys = ', '.join(sorted(result)) if isinstance(result, dict) else type(result).__name__
        raise RuntimeError(f'Unexpected Tencent response fields: {keys}; endpoint {path.split(chr(63))[0]}')
    if code != 0:
        # Do not log full responses, which may contain private authentication details.
        raise RuntimeError(f'Tencent API business code {code}; endpoint {path.split(chr(63))[0]}; check token, read permissions and document access')
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


def name_only_rows(rows):
    aliases = ['客户名称','名称','单位名称']
    header_index = next((i for i,row in enumerate(rows) if any(c in aliases for c in row)), None)
    if header_index is None:
        raise RuntimeError('Customer name header missing; previous data retained')
    header = rows[header_index]
    name_index = next(i for i,h in enumerate(header) if h in aliases)
    id_index = next((i for i,h in enumerate(header) if h in ['集团编号','客户编号','ID']), None)
    category_index = next((i for i,h in enumerate(header) if h.strip() in ['板块','所属板块','分类','行业','客户类别','客户分类','行业分类']), None)
    columns = ([id_index] if id_index is not None else []) + [name_index] + ([category_index] if category_index is not None else [])
    result = [[header[i] for i in columns]]
    seen = {}
    for row in rows[header_index+1:]:
        if len(row)>name_index and row[name_index].strip():
            projected=[row[i].strip() if i<len(row) else '' for i in columns]
            identifier=(projected[0] if id_index is not None else '') or 'name:'+row[name_index].strip()
            if identifier in seen:
                if seen[identifier]!=row[name_index].strip():raise RuntimeError('Conflicting customer identifiers; previous data retained')
                continue
            seen[identifier]=row[name_index].strip()
            result.append(projected)
    return result


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
    meta = request_api('/openapi/sheetbook/v2/' + urllib.parse.quote(file_id, safe='') + '/sheets-info', headers)
    sheets = meta.get('sheetData', meta.get('getSheet', []))
    sheet = next((s for s in sheets if s.get('sheetID') == SHEET_ID), None)
    if sheet is None:
        fields = {k: ([sorted(v[0])] if isinstance(v, list) and v and isinstance(v[0], dict) else type(v).__name__) for k,v in meta.items()}
        raise RuntimeError('Target sheet not found; metadata structure: ' + str(fields))
    row_count, column_count = int(sheet['rowCount']), int(sheet['columnCount'])
    if not 0 < row_count <= 6000 or not 0 < column_count <= 200:
        raise RuntimeError('Sheet dimensions exceed safety limits (6000 rows / 200 columns); previous data retained')
    def column_name(number):
        result = ''
        while number:
            number, remainder = divmod(number - 1, 26)
            result = chr(65 + remainder) + result
        return result
    end_column = column_name(column_count)
    page_size = min(1000, 10000 // column_count)
    rows = []
    for start in range(1, row_count + 1, page_size):
        end = min(start + page_size - 1, row_count)
        area = f'A{start}:{end_column}{end}'
        path = '/openapi/spreadsheet/v3/files/' + '/'.join(urllib.parse.quote(v, safe='') for v in (file_id, SHEET_ID, area))
        data = request_api(path, headers)
        grid = data.get('gridData')
        if not isinstance(grid, dict) or not isinstance(grid.get('rows'), list):
            raise RuntimeError('Unexpected gridData response; previous published data retained')
        page = [[cell_text(c) for c in r.get('values', [])] for r in grid['rows']]
        rows.extend(page)
    while rows and not any(v.strip() for v in rows[-1]):
        rows.pop()
    if not rows:
        raise RuntimeError('Empty spreadsheet; previous published data retained')
    rows = name_only_rows(rows)
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
