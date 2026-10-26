"""Smart Healthcare Project Management System - core logic (database, validation, CPM-style
scheduling, EVM, change control, risk/quality).  No GUI code here so it can be unit-tested.
Author: Hannan Razzaq (Project Manager) - CSE-494 Software Project Management, Mid-term Fall-2026"""
import sqlite3, math, datetime as dt

TD = dt.timedelta
D = lambda s: dt.datetime.strptime(str(s).strip(), "%Y-%m-%d").date()
F = lambda d: d.strftime("%Y-%m-%d")
ONE = TD(days=1)


class VE(Exception):
    """Validation / business-rule error shown to the user."""


SCHEMA = """
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
"""
PRIORITY = ["Critical", "High", "Medium", "Low"]
REQ_ST = ["Proposed", "Approved", "Rejected"]
CR_ST = ["Pending", "Approved", "Rejected"]
SEV = ["Critical", "High", "Medium", "Low"]
DEF_ST = ["Open", "In Progress", "Resolved", "Closed"]
QC_ST = ["Pending", "Pass", "Fail"]
MS_ST = ["Pending", "Achieved", "Missed"]
PROJ_ST = ["On Track", "At Risk", "Delayed", "Completed", "Closed"]
RISK_ST = ["Open", "Mitigated", "Closed"]


# ---------------- validation helpers ----------------
def need(v, name):
    v = "" if v is None else str(v).strip()
    if not v:
        raise VE(f"{name} is required.")
    return v


def num(v, name, lo=None, hi=None, integer=False):
    try:
        n = float(str(v).replace(",", "").strip())
    except Exception:
        raise VE(f"{name} must be a number.")
    if math.isnan(n) or math.isinf(n):
        raise VE(f"{name} must be a valid number.")
    if integer:
        if n != int(n):
            raise VE(f"{name} must be a whole number.")
        n = int(n)
    if lo is not None and n < lo:
        raise VE(f"{name} must be at least {lo:,}.")
    if hi is not None and n > hi:
        raise VE(f"{name} must be at most {hi:,}.")
    return n


def dte(v, name):
    try:
        return F(D(v))
    except Exception:
        raise VE(f"{name} must be a valid date in YYYY-MM-DD format.")


def one_of(v, opts, name):
    if v not in opts:
        raise VE(f"{name} must be one of: {', '.join(opts)}.")
    return v


class PM:
    def __init__(s, path="spms.db"):
        s.path = path
        s.c = sqlite3.connect(path)
        s.c.row_factory = sqlite3.Row
        s.c.execute("PRAGMA foreign_keys=ON")
        s.c.executescript(SCHEMA)
        for k, v in (("asof", F(dt.date.today())), ("warn", "0.95"), ("crit", "0.85")):
            s.c.execute("INSERT OR IGNORE INTO settings VALUES(?,?)", (k, v))
        s.c.commit()

    # ---------- generic DB ----------
    def q(s, sql, a=()):
        return [dict(r) for r in s.c.execute(sql, a)]

    def one(s, sql, a=()):
        r = s.q(sql, a)
        return r[0] if r else None

    def x(s, sql, a=()):
        cur = s.c.execute(sql, a)
        s.c.commit()
        return cur.lastrowid

    def cols(s, t):
        return [r["name"] for r in s.c.execute(f"PRAGMA table_info({t})") if r["name"] != "id"]

    def rows(s, t, order="id"):
        return s.q(f"SELECT * FROM {t} ORDER BY {order}")

    def get(s, t, i):
        return s.one(f"SELECT * FROM {t} WHERE id=?", (i,))

    def setting(s, k):
        return s.one("SELECT value FROM settings WHERE key=?", (k,))["value"]

    def set_setting(s, k, v):
        if k == "asof":
            v = dte(v, "Status date")
        else:
            v = str(num(v, "Threshold", 0.01, 5))
        s.x("INSERT OR REPLACE INTO settings VALUES(?,?)", (k, v))

    def charter(s):
        return s.one("SELECT * FROM charter WHERE id=1")

    def asof(s):
        return D(s.setting("asof"))

    def save(s, t, data, id=None):
        """Validate then insert/update. Returns row id. Raises VE on any rule violation."""
        cols = s.cols(t)
        old = s.get(t, id) if id else None
        if id and not old:
            raise VE("Record not found.")
        full = dict(old or {})
        for k, v in data.items():
            if k in cols:
                full[k] = (v.strip() or None) if isinstance(v, str) else v
        full.pop("id", None)
        chk = getattr(s, "v_" + t, None)
        if chk:
            full = chk(full, id, old) or full
        try:
            if id:
                s.x(f"UPDATE {t} SET " + ",".join(f"{k}=?" for k in full) + " WHERE id=?", (*full.values(), id))
                rid = id
            else:
                ks = [k for k in full if k in cols]
                rid = s.x(f"INSERT INTO {t}({','.join(ks)}) VALUES({','.join('?' * len(ks))})", [full[k] for k in ks])
        except sqlite3.IntegrityError as e:
            raise VE(f"Database constraint violated: {e}")
        post = getattr(s, "p_" + t, None)
        if post:
            post(s.get(t, rid), rid, old)
        if t in ("tasks", "charter"):
            s.sync()
        return rid

    def delete(s, t, id):
        r = s.get(t, id)
        if not r:
            raise VE("Select a record first.")
        if t == "charter":
            raise VE("The project charter cannot be deleted.")
        if t == "requirements":
            if s.one("SELECT 1 FROM tasks WHERE req_id=?", (id,)) or s.one("SELECT 1 FROM wbs WHERE req_id=?", (id,)):
                raise VE("Requirement is used by tasks/WBS items; remove them first.")
        if t == "tasks":
            if any(str(id) in [p.strip() for p in x["preds"].split(",")] for x in s.rows("tasks")):
                raise VE("Other tasks depend on this task; remove the dependency first.")
            if s.one("SELECT 1 FROM defects WHERE task_id=?", (id,)) or s.one("SELECT 1 FROM milestones WHERE task_id=?", (id,)):
                raise VE("Defects/milestones reference this task.")
        if t == "team" and s.one("SELECT 1 FROM tasks WHERE assignee=?", (r["name"],)):
            raise VE("Team member has assigned tasks.")
        if t == "change_requests" and r["status"] != "Pending":
            raise VE("Decided change requests are part of the audit trail and cannot be deleted.")
        try:
            s.x(f"DELETE FROM {t} WHERE id=?", (id,))
        except sqlite3.IntegrityError as e:
            raise VE(f"Cannot delete: {e}")
        if t == "tasks":
            s.sync()

    # ---------- validators ----------
    def v_charter(s, d, i, old):
        for k, n in (("name", "Project name"), ("objectives", "Objectives"), ("stakeholders", "Stakeholders"),
                     ("scope_boundaries", "Scope boundaries"), ("manager", "Project manager")):
            d[k] = need(d.get(k), n)
        d["budget"] = num(d.get("budget"), "Approved budget", 1)
        d["start_date"] = dte(d.get("start_date"), "Start date")
        d["deadline"] = dte(d.get("deadline"), "Deadline")
        if D(d["deadline"]) <= D(d["start_date"]):
            raise VE("Deadline must be after the start date.")
        if old and old.get("approved") and (d["budget"] != old["budget"] or d["deadline"] != old["deadline"]):
            raise VE("The approved budget/deadline are locked. Submit and approve a Change Request to change them.")
        if not old:
            d["base_budget"], d["base_deadline"] = d["budget"], d["deadline"]
        return d

    def v_requirements(s, d, i, old):
        d["title"] = need(d.get("title"), "Requirement title")
        d["priority"] = one_of(d.get("priority") or "Medium", PRIORITY, "Priority")
        d["status"] = one_of(d.get("status") or "Proposed", REQ_ST, "Status")
        if d["status"] == "Approved" and d.get("cr_id"):
            cr = s.get("change_requests", d["cr_id"])
            if not cr or cr["status"] != "Approved":
                raise VE("This requirement was raised by a change request that is not approved yet; "
                         "approve the change request to bring it into scope.")
        if old and old["status"] == "Approved" and d["status"] != "Approved" and \
                (s.one("SELECT 1 FROM tasks WHERE req_id=?", (i,))):
            raise VE("Cannot un-approve a requirement that already has tasks in the schedule.")
        return d

    def v_change_requests(s, d, i, old):
        d["title"] = need(d.get("title"), "Change title")
        d["justification"] = need(d.get("justification"), "Justification")
        d["cost_impact"] = num(d.get("cost_impact") or 0, "Cost impact", 0)
        d["days_impact"] = num(d.get("days_impact") or 0, "Schedule impact (days)", 0, 3650, True)
        d["status"] = one_of(d.get("status") or "Pending", CR_ST, "Status")
        if old and old["status"] != "Pending":
            raise VE("A decided change request is locked (audit trail).")
        if d["status"] != "Pending":
            d["decided_date"] = F(dt.date.today())
        return d

    def p_change_requests(s, r, rid, old):
        if r["status"] == "Approved" and (not old or old["status"] != "Approved"):
            ch = s.charter()
            if ch:
                nb = ch["budget"] + r["cost_impact"]
                nd = F(D(ch["deadline"]) + TD(days=r["days_impact"]))
                s.x("INSERT INTO baseline_log(cr_id,old_budget,new_budget,old_deadline,new_deadline,at) VALUES(?,?,?,?,?,?)",
                    (rid, ch["budget"], nb, ch["deadline"], nd, F(dt.date.today())))
                s.x("UPDATE charter SET budget=?,deadline=? WHERE id=1", (nb, nd))
            s.x("UPDATE requirements SET status='Approved' WHERE cr_id=? AND status='Proposed'", (rid,))
        if r["status"] == "Rejected":
            s.x("UPDATE requirements SET status='Rejected' WHERE cr_id=? AND status='Proposed'", (rid,))

    def cr_impact(s, i):
        cr = s.get("change_requests", i)
        ch = s.charter()
        nb = ch["budget"] + cr["cost_impact"]
        nd = D(ch["deadline"]) + TD(days=cr["days_impact"])
        reqs = s.q("SELECT title FROM requirements WHERE cr_id=?", (i,))
        sc = s.schedule_summary()
        return {"budget_before": ch["budget"], "budget_after": nb, "deadline_before": ch["deadline"], "deadline_after": F(nd),
                "scope_added": [r["title"] for r in reqs],
                "forecast_finish": sc["forecast_finish"],
                "meets_new_deadline": D(sc["forecast_finish"]) <= nd}

    def _preds(s, txt):
        out = []
        for p in str(txt or "").replace(";", ",").split(","):
            if p.strip():
                out.append(int(num(p, "Predecessor id", 1, integer=True)))
        return out

    def v_tasks(s, d, i, old):
        ch = s.charter()
        if not ch:
            raise VE("Create the project charter first.")
        d["name"] = need(d.get("name"), "Activity name")
        if not s.one("SELECT 1 FROM team WHERE name=?", (need(d.get("assignee"), "Assignee"),)):
            raise VE("Assignee must be a registered team member.")
        d["start"] = dte(d.get("start"), "Start date")
        if D(d["start"]) < D(ch["start_date"]):
            raise VE("Activity cannot start before the project start date.")
        d["duration"] = num(d.get("duration"), "Duration (days)", 1, 3650, True)
        d["planned_cost"] = num(d.get("planned_cost"), "Planned cost", 0)
        d["actual_cost"] = num(d.get("actual_cost") or 0, "Actual cost", 0)
        d["pct"] = num(d.get("pct") or 0, "% complete", 0, 100)
        rq = s.get("requirements", d.get("req_id")) if d.get("req_id") not in (None, "") else None
        if not rq:
            raise VE("Every activity must be linked to a requirement.")
        if rq["status"] != "Approved":
            raise VE(f"Requirement '{rq['title']}' is {rq['status']}, not Approved - it is outside the approved project scope.")
        ps = s._preds(d.get("preds"))
        for p in ps:
            if not s.get("tasks", p):
                raise VE(f"Predecessor task {p} does not exist.")
            if i and p == i:
                raise VE("A task cannot depend on itself.")
        if i:   # circular dependency check: is i an ancestor of any new predecessor?
            seen, st = set(), list(ps)
            while st:
                n = st.pop()
                if n == i:
                    raise VE("Circular dependency detected.")
                if n not in seen:
                    seen.add(n)
                    st += s._preds(s.get("tasks", n)["preds"])
        d["preds"] = ",".join(map(str, ps))
        others = s.one("SELECT COALESCE(SUM(planned_cost),0) c FROM tasks WHERE id<>?", (i or -1,))["c"]
        if others + d["planned_cost"] > ch["budget"]:
            raise VE(f"Total planned cost {others + d['planned_cost']:,.0f} would exceed the approved budget "
                     f"{ch['budget']:,.0f}. Submit a change request first.")
        return d

    def p_tasks(s, r, rid, old):
        pass

    def v_team(s, d, i, old):
        d["name"] = need(d.get("name"), "Name")
        d["role"] = need(d.get("role"), "Role")
        return d

    def v_milestones(s, d, i, old):
        d["name"] = need(d.get("name"), "Milestone")
        d["due"] = dte(d.get("due"), "Due date")
        d["status"] = one_of(d.get("status") or "Pending", MS_ST, "Status")
        if d.get("task_id") in ("", None):
            d["task_id"] = None
        elif not s.get("tasks", d["task_id"]):
            raise VE("Linked task does not exist.")
        return d

    def v_project_status(s, d, i, old):
        d["date"] = dte(d.get("date"), "Date")
        d["status"] = one_of(d.get("status"), PROJ_ST, "Status")
        return d

    def v_closure(s, d, i, old):
        d["date"] = dte(d.get("date"), "Closure date")
        d["signoff"] = need(d.get("signoff"), "Sign-off by")
        notdone = s.one("SELECT COUNT(*) c FROM tasks WHERE pct<100")["c"]
        crit = s.one("SELECT COUNT(*) c FROM defects WHERE severity='Critical' AND status IN ('Open','In Progress')")["c"]
        if notdone or crit:
            raise VE(f"Project cannot be closed: {notdone} activities are incomplete and {crit} critical defects are unresolved.")
        return d

    def v_wbs(s, d, i, old):
        d["name"] = need(d.get("name"), "WBS element name")
        d["kind"] = one_of(d.get("kind"), ["Deliverable", "Work Package"], "Type")
        if d.get("req_id") in ("", None):
            d["req_id"] = None
        else:
            r = s.get("requirements", d["req_id"])
            if not r or r["status"] != "Approved":
                raise VE("Only approved requirements can appear in the WBS (approved scope).")
        if d.get("parent_id") in ("", None):
            d["parent_id"] = None
        if not i:
            par = s.get("wbs", d["parent_id"]) if d["parent_id"] else None
            n = s.one("SELECT COUNT(*) c FROM wbs WHERE parent_id IS ?", (d["parent_id"],))["c"] + 1
            d["code"] = f"{par['code']}.{n}" if par else str(n)
        return d

    def gen_wbs(s):
        s.x("DELETE FROM wbs WHERE auto=1")
        for r in s.q("SELECT * FROM requirements WHERE status='Approved' ORDER BY id"):
            p = s.save("wbs", {"name": r["title"], "kind": "Deliverable", "req_id": r["id"], "auto": 1})
            for t in s.q("SELECT * FROM tasks WHERE req_id=? ORDER BY id", (r["id"],)):
                s.save("wbs", {"name": t["name"], "kind": "Work Package", "req_id": r["id"], "parent_id": p, "auto": 1})

    def v_defects(s, d, i, old):
        d["title"] = need(d.get("title"), "Defect title")
        d["severity"] = one_of(d.get("severity"), SEV, "Severity")
        d["status"] = one_of(d.get("status") or "Open", DEF_ST, "Status")
        if d.get("task_id") in ("", None):
            d["task_id"] = None
        elif not s.get("tasks", d["task_id"]):
            raise VE("Linked task does not exist.")
        if d["severity"] in ("Critical", "High") and not (d.get("assignee") or "").strip():
            raise VE("Critical/High defects must be assigned to a person.")
        if d["status"] == "Closed" and (not old or old["status"] not in ("Resolved", "Closed")):
            raise VE("A defect must be Resolved before it can be Closed.")
        if not d.get("reported"):
            d["reported"] = F(dt.date.today())
        return d

    def v_quality_checks(s, d, i, old):
        d["deliverable"] = need(d.get("deliverable"), "Deliverable")
        d["item"] = need(d.get("item"), "Checklist item")
        d["result"] = one_of(d.get("result") or "Pending", QC_ST, "Result")
        if d["result"] != "Pending":
            need(d.get("inspector"), "Inspector")
            d["test_date"] = dte(d.get("test_date"), "Test date")
        return d

    def p_quality_checks(s, r, rid, old):
        t = f"QC failed: {r['deliverable']} - {r['item']}"
        if r["result"] == "Fail" and not s.one("SELECT 1 FROM defects WHERE title=? AND status IN ('Open','In Progress')", (t,)):
            s.save("defects", {"title": t, "severity": "High", "assignee": r["inspector"], "status": "Open"})

    def gen_checklist(s):
        n = 0
        for r in s.q("SELECT title FROM requirements WHERE status='Approved'"):
            if s.one("SELECT 1 FROM quality_checks WHERE deliverable=?", (r["title"],)):
                continue
            for it in ("Requirements traced and met", "Code review completed", "Unit/integration tests passed", "User acceptance test passed"):
                s.save("quality_checks", {"deliverable": r["title"], "item": it}); n += 1
        return n

    def v_risks(s, d, i, old):
        d["description"] = need(d.get("description"), "Risk description")
        d["likelihood"] = num(d.get("likelihood"), "Likelihood", 1, 5, True)
        d["impact"] = num(d.get("impact"), "Impact", 1, 5, True)
        d["score"] = d["likelihood"] * d["impact"]
        d["status"] = one_of(d.get("status") or "Open", RISK_ST, "Status")
        need(d.get("preventive"), "Preventive action")
        if d["score"] >= 10:
            need(d.get("corrective"), "Corrective action (required for risks scoring 10+)")
        return d

    @staticmethod
    def risk_level(sc):
        return "High" if sc >= 15 else "Medium" if sc >= 8 else "Low"

    def v_plan(s, d, i, old):
        return d

    # ---------- scheduling ----------
    def schedule(s):
        T = {t["id"]: t for t in s.rows("tasks")}
        a, memo = s.asof(), {}

        def calc(i):
            if i in memo:
                return memo[i]
            t = T[i]
            ps = [calc(p) for p in s._preds(t["preds"]) if p in T]
            st, dur, pct = D(t["start"]), t["duration"], t["pct"]
            pst = max([st] + [p["pend"] + ONE for p in ps])
            pend = pst + TD(days=dur - 1)
            if pct >= 100:
                fst, fend = pst, pend
            elif pct > 0:
                fst, fend = pst, pend
                if a > pend:                      # overdue: remaining work starts from status date
                    fend = a + TD(days=math.ceil(dur * (1 - pct / 100)))
            else:
                fst = max([st] + [p["fend"] + ONE for p in ps])
                if a > fst:
                    fst = a                       # not started although it should have
                fend = fst + TD(days=dur - 1)
            delay = max(0, (fend - pend).days)
            own = pct < 100 and a > pend
            late_start = pct == 0 and a > pst
            if pct >= 100:
                stt = "Complete"
            elif own:
                stt = "Delayed"
            elif delay > 0:
                stt = "Impacted"
            elif late_start:
                stt = "Late start"
            elif pct == 0:
                stt = "Not started"
            else:
                stt = "On track"
            memo[i] = dict(id=i, name=t["name"], assignee=t["assignee"], pct=pct, pstart=pst, pend=pend, fstart=fst,
                           fend=fend, delay=delay, status=stt, preds=[p["id"] for p in ps],
                           caused_by=[p["id"] for p in ps if p["delay"] > 0] if stt == "Impacted" else [])
            return memo[i]

        return [calc(i) for i in sorted(T)]

    def schedule_summary(s):
        sch, ch = s.schedule(), s.charter()
        if not sch:
            return {"forecast_finish": ch["deadline"] if ch else F(dt.date.today()), "slip_days": 0, "planned_finish": None}
        ff = max(r["fend"] for r in sch)
        pf = max(r["pend"] for r in sch)
        dl = D(ch["deadline"])
        return {"forecast_finish": F(ff), "planned_finish": F(pf), "slip_days": (ff - dl).days,
                "delayed": [r for r in sch if r["delay"] > 0]}

    def sync(s):
        """Persist computed planned start/end of every task (generated project schedule)."""
        for r in s.schedule():
            s.c.execute("UPDATE tasks SET pstart=?,pend=? WHERE id=?", (F(r["pstart"]), F(r["pend"]), r["id"]))
        s.c.commit()

    # ---------- EVM ----------
    def evm(s):
        a, ch = s.asof(), s.charter()
        sch = {r["id"]: r for r in s.schedule()}
        PV = EV = AC = BAC = 0.0
        per = []
        for t in s.rows("tasks"):
            c = t["planned_cost"]
            BAC += c
            fr = min(1.0, max(0.0, ((a - sch[t["id"]]["pstart"]).days + 1) / t["duration"]))
            pv, ev = c * fr, c * t["pct"] / 100
            PV += pv; EV += ev; AC += t["actual_cost"]
            per.append(dict(id=t["id"], name=t["name"], bac=c, pv=pv, ev=ev, ac=t["actual_cost"], cv=ev - t["actual_cost"]))
        CPI = EV / AC if AC else None
        SPI = EV / PV if PV else None
        EAC = BAC / CPI if CPI else BAC
        w, cr = float(s.setting("warn")), float(s.setting("crit"))
        warns = []
        budget = ch["budget"] if ch else 0
        for nm, v, what in (("CPI", CPI, "cost overrun"), ("SPI", SPI, "schedule delay")):
            if v is not None and v < cr:
                warns.append(("CRITICAL", f"{nm} = {v:.2f} is below the critical threshold {cr:.2f}: serious {what}."))
            elif v is not None and v < w:
                warns.append(("WARNING", f"{nm} = {v:.2f} is below the warning threshold {w:.2f}: {what} detected."))
        if budget and BAC > budget:
            warns.append(("CRITICAL", f"Planned cost {BAC:,.0f} exceeds approved budget {budget:,.0f}."))
        if budget and AC > budget:
            warns.append(("CRITICAL", f"Actual cost {AC:,.0f} exceeds approved budget {budget:,.0f}."))
        elif budget and EAC > budget:
            warns.append(("WARNING", f"Forecast at completion (EAC) {EAC:,.0f} exceeds approved budget {budget:,.0f} by {EAC - budget:,.0f}."))
        ss = s.schedule_summary()
        if ss["slip_days"] > 0:
            warns.append(("CRITICAL", f"Forecast finish {ss['forecast_finish']} is {ss['slip_days']} day(s) after the deadline {ch['deadline']}."))
        return dict(BAC=BAC, PV=PV, EV=EV, AC=AC, CPI=CPI, SPI=SPI, CV=EV - AC, SV=EV - PV, EAC=EAC, VAC=BAC - EAC,
                    budget=budget, warnings=warns, per_task=per)

    # ---------- dashboard / report ----------
    def dashboard(s):
        ch, ev, sm = s.charter(), s.evm(), s.schedule_summary()
        crit = s.q("SELECT * FROM defects WHERE severity='Critical' AND status IN ('Open','In Progress')")
        pend = s.q("SELECT * FROM change_requests WHERE status='Pending'")
        done_crit = s.q("""SELECT DISTINCT t.name FROM defects d JOIN tasks t ON t.id=d.task_id
                           WHERE t.pct>=100 AND d.status IN ('Open','In Progress') AND d.severity='Critical'""")
        warns = list(ev["warnings"])
        if crit:
            warns.append(("CRITICAL", f"{len(crit)} unresolved critical defect(s)."))
        for r in done_crit:
            warns.append(("WARNING", f"Task '{r['name']}' is marked 100% but has an open critical defect."))
        if pend:
            warns.append(("INFO", f"{len(pend)} change request(s) awaiting a decision."))
        return dict(charter=ch, progress=(ev["EV"] / ev["BAC"] * 100 if ev["BAC"] else 0), evm=ev, summary=sm,
                    delayed=sm.get("delayed", []), pending_cr=pend, critical_defects=crit, warnings=warns,
                    reqs={r["status"]: r["c"] for r in s.q("SELECT status,COUNT(*) c FROM requirements GROUP BY status")},
                    defects={r["status"]: r["c"] for r in s.q("SELECT status,COUNT(*) c FROM defects GROUP BY status")})

    def report_text(s):
        d = s.dashboard(); ch, ev = d["charter"], d["evm"]
        if not ch:
            return "No project charter defined yet."
        f = lambda v: "n/a" if v is None else f"{v:.2f}"
        L = ["=" * 78, f"PROJECT STATUS REPORT - {ch['name']}", f"Project Manager: {ch['manager']}    Status date: {s.setting('asof')}",
             "=" * 78, "",
             f"Overall progress (earned-value based): {d['progress']:.1f}%",
             f"Schedule : start {ch['start_date']}  deadline {ch['deadline']} (baseline {ch['base_deadline']})  forecast finish {d['summary']['forecast_finish']}  "
             f"({'ON TIME' if d['summary']['slip_days'] <= 0 else str(d['summary']['slip_days']) + ' day(s) LATE'})",
             f"Budget   : approved {ch['budget']:,.0f} (baseline {ch['base_budget']:,.0f})  planned {ev['BAC']:,.0f}  actual spent {ev['AC']:,.0f}  EAC {ev['EAC']:,.0f}",
             f"EVM      : PV {ev['PV']:,.0f}  EV {ev['EV']:,.0f}  AC {ev['AC']:,.0f}  CPI {f(ev['CPI'])}  SPI {f(ev['SPI'])}  CV {ev['CV']:,.0f}  SV {ev['SV']:,.0f}",
             "", f"WARNINGS ({len(d['warnings'])})"]
        L += [f"  [{lv}] {m}" for lv, m in d["warnings"]] or ["  none"]
        L += ["", f"DELAYED / IMPACTED ACTIVITIES ({len(d['delayed'])})"]
        L += [f"  #{r['id']} {r['name']} ({r['assignee']}): {r['status']}, +{r['delay']} day(s), forecast end {F(r['fend'])}"
              + (f", caused by task(s) {r['caused_by']}" if r["caused_by"] else "") for r in d["delayed"]] or ["  none"]
        L += ["", f"PENDING CHANGE REQUESTS ({len(d['pending_cr'])})"]
        L += [f"  CR#{c['id']} {c['title']}: +{c['cost_impact']:,.0f} PKR, +{c['days_impact']} days" for c in d["pending_cr"]] or ["  none"]
        L += ["", f"UNRESOLVED CRITICAL DEFECTS ({len(d['critical_defects'])})"]
        L += [f"  D#{x['id']} {x['title']} [{x['status']}] assigned to {x['assignee']}" for x in d["critical_defects"]] or ["  none"]
        L += ["", "SCOPE: " + ", ".join(f"{k}={v}" for k, v in d["reqs"].items()),
              "DEFECTS: " + ", ".join(f"{k}={v}" for k, v in d["defects"].items()),
              "MILESTONES:"]
        for m in s.rows("milestones", "due"):
            L.append(f"  {m['due']}  {m['name']}  [{m['status']}]  owner: {m['owner']}")
        top = s.q("SELECT * FROM risks WHERE status='Open' ORDER BY score DESC LIMIT 3")
        L += ["", "TOP RISKS:"] + [f"  score {r['score']:>2} ({s.risk_level(r['score'])}) {r['description']}" for r in top]
        return "\n".join(L)

    def gen_plan(s):
        ch, ev = s.charter(), s.evm()
        sc = ", ".join(r["title"] for r in s.q("SELECT title FROM requirements WHERE status='Approved'"))
        qc = s.one("SELECT SUM(result='Pass') p, COUNT(*) n FROM quality_checks")
        d = {"scope": f"Approved scope ({ch['scope_boundaries']}). Approved requirements: {sc}.",
             "schedule": f"{ch['start_date']} to {ch['deadline']}; {len(s.rows('tasks'))} activities; forecast finish {s.schedule_summary()['forecast_finish']}.",
             "cost": f"Approved budget PKR {ch['budget']:,.0f}; planned cost PKR {ev['BAC']:,.0f}; EVM thresholds warn<{s.setting('warn')} crit<{s.setting('crit')}.",
             "quality": f"{qc['n']} checklist items ({qc['p'] or 0} passed); defects tracked by severity; critical defects must be resolved before closure."}
        s.save("plan", d, 1 if s.get("plan", 1) else None)
        return d

    # ---------- risk views ----------
    def pdpc(s):
        ch = s.charter()
        return {"goal": ch["name"] if ch else "Project",
                "risks": s.q("SELECT * FROM risks WHERE status<>'Closed' ORDER BY score DESC")}


# ---------------- sample data (case study) ----------------
def seed(pm):
    S = pm.save
    team = [("Hannan Razzaq", "Project Manager", "Planning, monitoring, change control"), ("Backend Developer 1", "Backend Developer", "Core modules"),
            ("Backend Developer 2", "Backend Developer", "Scheduling & lab modules"), ("Frontend Developer 1", "Frontend Developer", "Web UI"),
            ("Frontend Developer 2", "Frontend Developer", "Web UI"), ("Database Developer", "Database Developer", "Schema, data migration"),
            ("QA Engineer", "Quality Assurance Engineer", "Testing & inspections")]
    for n, r, c in team:
        S("team", {"name": n, "role": r, "responsibility": c})
    S("charter", {"name": "Smart Healthcare Project Management and Monitoring System",
                  "objectives": "Deliver an integrated system for appointments, laboratory reports, doctor schedules, online consultations and billing for five hospitals within 16 weeks and PKR 5,000,000.",
                  "stakeholders": "Hospital management (sponsor), doctors, patients, lab staff, billing staff, development company, QA team",
                  "scope_boundaries": "IN: appointments, lab reports, doctor schedules, online consultation, billing, patient records. OUT (unless approved by change request): AI diagnosis, mobile app.",
                  "budget": 5000000, "start_date": "2026-08-31", "deadline": "2026-12-20", "manager": "Hannan Razzaq"})
    reqs = [("Core platform, architecture & project management", "Architecture, SRS, integration, deployment", "Critical"),
            ("Patient appointment management", "Book, reschedule, cancel; conflict detection", "Critical"),
            ("Laboratory reports", "Order and publish lab results", "High"), ("Doctor schedules", "Shift & availability management", "High"),
            ("Online consultations", "Video/chat consultation", "Medium"), ("Hospital billing", "Invoices, payments, insurance", "High"),
            ("Patient record management", "Electronic patient records", "Critical")]
    for t, d, p in reqs:
        S("requirements", {"title": t, "description": d, "priority": p, "status": "Approved"})
    T = [  # name, assignee, start, dur, preds, req, cost, pct, actual
        ("Requirement analysis & SRS", "Hannan Razzaq", "2026-08-31", 10, "", 1, 250000, 100, 260000),
        ("System architecture & DB design", "Database Developer", "2026-09-10", 10, "1", 1, 300000, 100, 310000),
        ("Database implementation", "Database Developer", "2026-09-20", 10, "2", 7, 350000, 100, 340000),
        ("Patient record module", "Backend Developer 1", "2026-09-30", 15, "3", 7, 450000, 100, 470000),
        ("Appointment scheduling module", "Backend Developer 2", "2026-09-30", 20, "3", 2, 500000, 90, 600000),
        ("Doctor schedule module", "Backend Developer 1", "2026-10-15", 10, "4", 4, 300000, 100, 300000),
        ("Laboratory reports module", "Backend Developer 2", "2026-10-20", 15, "5", 3, 400000, 0, 0),
        ("Billing module", "Backend Developer 1", "2026-10-25", 15, "6", 6, 450000, 10, 40000),
        ("Frontend: appointments & records", "Frontend Developer 1", "2026-09-20", 25, "2", 2, 400000, 95, 380000),
        ("Frontend: doctor, lab & billing", "Frontend Developer 2", "2026-10-25", 20, "6", 4, 350000, 5, 15000),
        ("Online consultation module", "Backend Developer 2", "2026-11-04", 15, "7", 5, 450000, 0, 0),
        ("System integration & testing", "QA Engineer", "2026-11-19", 15, "8,9,10,11", 1, 500000, 0, 0),
        ("UAT, deployment & training", "Hannan Razzaq", "2026-12-04", 10, "12", 1, 250000, 0, 0)]
    pm.set_setting("asof", "2026-10-26")
    for n, a, st, du, pr, rq, c, p, ac in T:
        S("tasks", {"name": n, "assignee": a, "start": st, "duration": du, "preds": pr, "req_id": rq, "planned_cost": c, "pct": p, "actual_cost": ac})
    c1 = S("change_requests", {"title": "Add AI-based preliminary diagnosis module", "requested_by": "Hospital management",
           "justification": "Reduce doctor workload by pre-screening symptoms", "cost_impact": 450000, "days_impact": 10})
    c2 = S("change_requests", {"title": "Add mobile application", "requested_by": "Hospital management",
           "justification": "Patients need mobile access to appointments and reports", "cost_impact": 350000, "days_impact": 11})
    S("change_requests", {"title": "Add biometric login", "requested_by": "Hospital IT", "justification": "Nice-to-have security feature",
                          "cost_impact": 200000, "days_impact": 5, "status": "Rejected"})
    S("requirements", {"title": "AI-based preliminary diagnosis module", "description": "Symptom checker (via CR)", "priority": "Medium", "status": "Proposed", "cr_id": c1})
    S("requirements", {"title": "Mobile application", "description": "Android/iOS patient app (via CR)", "priority": "High", "status": "Proposed", "cr_id": c2})
    S("plan", {"scope": "", "schedule": "", "cost": "", "quality": ""})
    for n, du, tk, ow, st in (("M1 Requirements baselined", "2026-09-09", 1, "Hannan Razzaq", "Achieved"), ("M2 Database ready", "2026-09-29", 3, "Database Developer", "Achieved"),
                              ("M3 Core modules complete", "2026-10-24", 6, "Backend Developer 1", "Missed"), ("M4 Integration & testing complete", "2026-12-03", 12, "QA Engineer", "Pending"),
                              ("M5 Go-live / deadline", "2026-12-13", 13, "Hannan Razzaq", "Pending")):
        S("milestones", {"name": n, "due": du, "task_id": tk, "owner": ow, "status": st})
    for dd, st, nt in (("2026-09-15", "On Track", "Planning complete"), ("2026-10-26", "At Risk", "Appointment module late; 2 critical defects; CPI/SPI below threshold")):
        S("project_status", {"date": dd, "status": st, "note": nt, "reported_by": "Hannan Razzaq"})
    S("defects", {"title": "Double booking possible in appointment scheduling", "severity": "Critical", "assignee": "Backend Developer 2", "status": "Open", "task_id": 5})
    S("defects", {"title": "Patient record update overwrites older data", "severity": "Critical", "assignee": "Backend Developer 1", "status": "In Progress", "task_id": 4})
    S("defects", {"title": "Date picker accepts past dates", "severity": "Medium", "assignee": "Frontend Developer 1", "status": "Resolved", "task_id": 9})
    S("defects", {"title": "Typo on billing screen label", "severity": "Low", "assignee": "Frontend Developer 2", "status": "Resolved", "task_id": 10})
    pm.gen_checklist()
    for it, res in (("Requirements traced and met", "Pass"), ("Code review completed", "Pass"), ("Unit/integration tests passed", "Fail")):
        r = pm.one("SELECT id FROM quality_checks WHERE deliverable='Patient appointment management' AND item=?", (it,))
        S("quality_checks", {"result": res, "inspector": "QA Engineer", "test_date": "2026-10-22", "notes": "Conflict check fails under concurrent booking" if res == "Fail" else ""}, r["id"])
    for ds, l, i, ow, pv, co in (
            ("Appointment scheduling defects delay downstream modules", 5, 4, "Backend Developer 2", "Daily defect triage; pair programming", "Add temporary developer; re-plan dependent tasks"),
            ("Patient record data loss / corruption", 3, 5, "Database Developer", "Transactions, audit logs, nightly backups", "Restore from backup; hotfix release"),
            ("Scope creep from hospital management", 4, 4, "Hannan Razzaq", "Strict change control; baseline lock", "Re-baseline via approved CR; negotiate budget"),
            ("Budget overrun (CPI < 1)", 4, 4, "Hannan Razzaq", "Weekly EVM review", "Cut low-priority scope; request contingency"),
            ("Key developer unavailable", 2, 4, "Hannan Razzaq", "Cross-training; documentation", "Reassign tasks; hire contractor"),
            ("Integration problems between five hospital systems", 3, 4, "QA Engineer", "Early integration tests; API contracts", "Dedicated integration sprint"),
            ("Data privacy / security breach", 2, 5, "Backend Developer 1", "Role-based access; encryption", "Incident response; notify stakeholders"),
            ("Training of hospital staff insufficient", 2, 2, "Hannan Razzaq", "Training plan & manuals", "Extra sessions")):
        S("risks", {"description": ds, "likelihood": l, "impact": i, "owner": ow, "preventive": pv, "corrective": co})
    pm.x("UPDATE charter SET approved=1 WHERE id=1")
    pm.gen_wbs()
    pm.gen_plan()


if __name__ == "__main__":
    import os, sys
    p = sys.argv[1] if len(sys.argv) > 1 else "spms.db"
    if os.path.exists(p):
        os.remove(p)
    m = PM(p); seed(m); print(m.report_text())
