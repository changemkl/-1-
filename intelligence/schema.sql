PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS customers (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
 id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id),
 url TEXT NOT NULL, title TEXT NOT NULL, excerpt TEXT NOT NULL,
 published_at TEXT, fetched_at TEXT NOT NULL, content_hash TEXT NOT NULL,
 UNIQUE(customer_id,url)
);
CREATE INDEX IF NOT EXISTS documents_customer ON documents(customer_id,fetched_at);
CREATE TABLE IF NOT EXISTS document_versions (
 document_id TEXT NOT NULL REFERENCES documents(id), content_hash TEXT NOT NULL,
 title TEXT NOT NULL, excerpt TEXT NOT NULL, fetched_at TEXT NOT NULL,
 PRIMARY KEY(document_id,content_hash)
);
CREATE TABLE IF NOT EXISTS signals (
 id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id),
 document_id TEXT NOT NULL REFERENCES documents(id), category TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','verified','rejected')),
 created_at TEXT NOT NULL, UNIQUE(customer_id,document_id,category)
);
CREATE INDEX IF NOT EXISTS signals_customer ON signals(customer_id,status);
CREATE TABLE IF NOT EXISTS profile_attributes (
 customer_id TEXT NOT NULL REFERENCES customers(id), field TEXT NOT NULL,
 value TEXT NOT NULL, origin TEXT NOT NULL CHECK(origin IN ('manual','reviewed')),
 updated_at TEXT NOT NULL, PRIMARY KEY(customer_id,field)
);
CREATE TABLE IF NOT EXISTS crawl_runs (
 id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id),
 source_url TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('success','blocked','failed')),
 documents_found INTEGER NOT NULL, error TEXT
);
CREATE INDEX IF NOT EXISTS crawl_runs_customer ON crawl_runs(customer_id,finished_at);
