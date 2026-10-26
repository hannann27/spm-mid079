-- Database schema (SQLite) - Smart Healthcare PM System
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS charter(id INTEGER PRIMARY KEY, name TEXT NOT NULL, objectives TEXT NOT NULL,
  stakeholders TEXT NOT NULL, scope_boundaries TEXT NOT NULL, budget REAL NOT NULL CHECK(budget>0),
  start_date TEXT NOT NULL, deadline TEXT NOT NULL, manager TEXT NOT NULL,
  base_budget REAL, base_deadline TEXT, approved INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS plan(id INTEGER PRIMARY KEY, scope TEXT, schedule TEXT, cost TEXT, quality TEXT);
CREATE TABLE IF NOT EXISTS team(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, role TEXT NOT NULL, responsibility TEXT);
CREATE TABLE IF NOT EXISTS milestones(id INTEGER PRIMARY KEY, name TEXT NOT NULL, due TEXT NOT NULL,
  task_id INTEGER REFERENCES tasks(id), owner TEXT, status TEXT DEFAULT 'Pending');
CREATE TABLE IF NOT EXISTS project_status(id INTEGER PRIMARY KEY, date TEXT NOT NULL, status TEXT NOT NULL, note TEXT, reported_by TEXT);
CREATE TABLE IF NOT EXISTS closure(id INTEGER PRIMARY KEY, date TEXT NOT NULL, deliverables_accepted TEXT, lessons_learned TEXT, signoff TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS change_requests(id INTEGER PRIMARY KEY, title TEXT NOT NULL, justification TEXT NOT NULL,
  cost_impact REAL NOT NULL DEFAULT 0, days_impact INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'Pending',
  requested_by TEXT, decided_date TEXT);
CREATE TABLE IF NOT EXISTS requirements(id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT,
  priority TEXT NOT NULL DEFAULT 'Medium', status TEXT NOT NULL DEFAULT 'Proposed',
  cr_id INTEGER REFERENCES change_requests(id));
CREATE TABLE IF NOT EXISTS wbs(id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES wbs(id), code TEXT, name TEXT NOT NULL,
  kind TEXT NOT NULL, req_id INTEGER REFERENCES requirements(id), auto INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY, name TEXT NOT NULL, assignee TEXT NOT NULL REFERENCES team(name),
  start TEXT NOT NULL, duration INTEGER NOT NULL CHECK(duration>0), preds TEXT DEFAULT '',
  req_id INTEGER NOT NULL REFERENCES requirements(id), planned_cost REAL NOT NULL CHECK(planned_cost>=0),
  actual_cost REAL NOT NULL DEFAULT 0 CHECK(actual_cost>=0), pct REAL NOT NULL DEFAULT 0 CHECK(pct BETWEEN 0 AND 100),
  pstart TEXT, pend TEXT);
CREATE TABLE IF NOT EXISTS baseline_log(id INTEGER PRIMARY KEY, cr_id INTEGER, old_budget REAL, new_budget REAL,
  old_deadline TEXT, new_deadline TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS defects(id INTEGER PRIMARY KEY, title TEXT NOT NULL, severity TEXT NOT NULL, assignee TEXT,
  status TEXT NOT NULL DEFAULT 'Open', task_id INTEGER REFERENCES tasks(id), reported TEXT);
CREATE TABLE IF NOT EXISTS quality_checks(id INTEGER PRIMARY KEY, deliverable TEXT NOT NULL, item TEXT NOT NULL,
  result TEXT NOT NULL DEFAULT 'Pending', inspector TEXT, test_date TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS risks(id INTEGER PRIMARY KEY, description TEXT NOT NULL, likelihood INTEGER NOT NULL CHECK(likelihood BETWEEN 1 AND 5),
  impact INTEGER NOT NULL CHECK(impact BETWEEN 1 AND 5), score INTEGER, owner TEXT, preventive TEXT, corrective TEXT,
  status TEXT NOT NULL DEFAULT 'Open');
