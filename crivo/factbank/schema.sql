CREATE TABLE IF NOT EXISTS publications (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  source_url TEXT,
  captured_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  publication_id TEXT NOT NULL REFERENCES publications(id),
  text TEXT NOT NULL,
  weight INTEGER NOT NULL DEFAULT 1,
  central INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'sem_evidencia',
  CHECK (status IN ('confirmada', 'contraditada', 'sem_evidencia'))
);

CREATE TABLE IF NOT EXISTS evidences (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  claim_id INTEGER NOT NULL REFERENCES claims(id),
  source_name TEXT NOT NULL,
  source_url TEXT,
  excerpt TEXT
);

CREATE TABLE IF NOT EXISTS verdicts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  publication_id TEXT NOT NULL REFERENCES publications(id),
  label TEXT NOT NULL,
  index_value REAL,
  rule TEXT NOT NULL,
  created_at TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1
);
