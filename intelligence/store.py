"""SQLite locally; Cloudflare D1 via authenticated REST in GitHub Actions."""
import json
import os
import sqlite3
import urllib.request
from pathlib import Path

class Store:
    def __init__(self, path=None):
        self.local = sqlite3.connect(path) if path else None
        if self.local:
            self.local.row_factory = sqlite3.Row
        else:
            required = ['CLOUDFLARE_ACCOUNT_ID','CLOUDFLARE_D1_DATABASE_ID','CLOUDFLARE_API_TOKEN']
            if any(not os.environ.get(k) for k in required):
                raise RuntimeError('Configure Cloudflare D1 secrets, or use --sqlite for local validation')
            self.url = 'https://api.cloudflare.com/client/v4/accounts/' + os.environ[required[0]] + '/d1/database/' + os.environ[required[1]] + '/query'
            self.token = os.environ[required[2]]

    def batch(self, statements):
        if self.local:
            with self.local:
                return [[dict(r) for r in self.local.execute(sql, params).fetchall()] for sql, params in statements]
        results = []
        for sql,params in statements:
            request = urllib.request.Request(self.url, data=json.dumps({'sql':sql,'params':params}).encode(), headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'},method='POST')
            with urllib.request.urlopen(request,timeout=40) as response:
                body = json.load(response)
            if not body.get('success') or any(not r.get('success') for r in body.get('result',[])):
                raise RuntimeError('D1 query failed; inspect database schema and token scope')
            results.append(body['result'][0].get('results',[]))
        return results

    def query(self, sql, params=()):
        return self.batch([(sql,list(params))])[0]

    def initialize(self):
        sql = Path(__file__).with_name('schema.sql').read_text()
        self.batch([(s.strip(),[]) for s in sql.split(';') if s.strip()])
