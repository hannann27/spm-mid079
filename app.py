"""Smart Healthcare Project Management System - GUI (Tkinter).  Run:  python app.py
Author: Hannan Razzaq (Project Manager) | CSE-494 Software Project Management, Mid-term Fall-2026"""
import re, sys, os, datetime as dt
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from spms_core import *

COL = {"red": "#e74c3c", "green": "#27ae60", "blue": "#2e86de", "amber": "#f39c12", "grey": "#95a5a6", "navy": "#1b2a49"}
TAGS = {"bad": "#fadbd8", "warn": "#fdebd0", "ok": "#d5f5e3"}


def ids(rows, label):
    return [""] + [f"{r['id']} - {r[label]}" for r in rows]


class Crud(ttk.Frame):
    """Generic table + form + Add/Update/Delete. fields: (key,label,kind,opts) kind: e|t|c|r(ref combo)."""

    def __init__(s, master, app, table, cols, fields, order="id", tag=None, extra=(), height=8):
        super().__init__(master)
        s.app, s.pm, s.table, s.fields, s.order, s.tag, s.cols, s.sel = app, app.pm, table, fields, order, tag, cols, None
        wrap = ttk.Frame(s); wrap.pack(fill="both", expand=True)
        s.tree = ttk.Treeview(wrap, columns=[c[0] for c in cols], show="headings", height=height, selectmode="browse")
        for k, h, w in cols:
            s.tree.heading(k, text=h); s.tree.column(k, width=w, anchor="w")
        sb = ttk.Scrollbar(wrap, command=s.tree.yview); s.tree.configure(yscrollcommand=sb.set)
        s.tree.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        for k, v in TAGS.items():
            s.tree.tag_configure(k, background=v)
        s.tree.bind("<<TreeviewSelect>>", s.pick)
        form = ttk.LabelFrame(s, text=" Record "); form.pack(fill="x", padx=4, pady=4)
        s.w = {}
        for n, (k, lab, kind, opts) in enumerate(fields):
            r, c = divmod(n, 3)
            ttk.Label(form, text=lab).grid(row=r * 2, column=c, sticky="w", padx=6)
            if kind == "t":
                w = tk.Text(form, height=3, width=34, wrap="word")
            elif kind in "cr":
                w = ttk.Combobox(form, width=32, state="normal", values=opts if isinstance(opts, list) else [])
            else:
                w = ttk.Entry(form, width=35)
            w.grid(row=r * 2 + 1, column=c, padx=6, pady=(0, 4), sticky="w"); s.w[k] = (w, kind, opts)
        bf = ttk.Frame(s); bf.pack(fill="x", padx=4, pady=(0, 4))
        for t, f in (("Add", s.add), ("Update selected", s.upd), ("Delete selected", s.dele), ("Clear form", s.clear), *extra):
            ttk.Button(bf, text=t, command=(f if t in ("Add", "Update selected", "Delete selected", "Clear form") else (lambda f=f: f(s)))).pack(side="left", padx=3)

    def val(s, k):
        w, kind, opts = s.w[k]
        v = w.get("1.0", "end").strip() if kind == "t" else w.get().strip()
        if kind == "r":
            m = re.match(r"^(\d+) - ", v)
            v = m.group(1) if m else v
        return v

    def put(s, k, v):
        w, kind, opts = s.w[k]
        v = "" if v is None else str(v)
        if kind == "t":
            w.delete("1.0", "end"); w.insert("1.0", v)
        elif kind == "r":
            m = [o for o in w["values"] if o.startswith(v + " - ")]
            w.set(m[0] if m else v)
        elif kind == "c":
            w.set(v)
        else:
            w.delete(0, "end"); w.insert(0, v)

    def clear(s):
        s.sel = None
        for k in s.w:
            s.put(k, "")
        for k, (w, kind, opts) in s.w.items():
            if kind == "c" and opts:
                w.set(opts[0] if not callable(opts) else "")

    def pick(s, _=None):
        it = s.tree.selection()
        if not it:
            return
        s.sel = int(it[0])
        r = s.pm.get(s.table, s.sel)
        for k in s.w:
            s.put(k, r.get(k))

    def data(s):
        return {k: s.val(k) for k in s.w}

    def run(s, fn, ok=None):
        try:
            r = fn()
            s.app.refresh()
            if ok:
                messagebox.showinfo("Done", ok)
            return r
        except VE as e:
            messagebox.showerror("Validation error", str(e))
        except Exception as e:
            messagebox.showerror("Unexpected error", f"{type(e).__name__}: {e}")

    def add(s):
        s.run(lambda: s.pm.save(s.table, s.data()))

    def upd(s):
        if s.sel is None:
            return messagebox.showwarning("Select", "Select a row to update.")
        s.run(lambda: s.pm.save(s.table, s.data(), s.sel))

    def dele(s):
        if s.sel is None:
            return messagebox.showwarning("Select", "Select a row to delete.")
        if messagebox.askyesno("Confirm", "Delete the selected record?"):
            if s.run(lambda: (s.pm.delete(s.table, s.sel), True)[1]):
                s.sel = None

    def refresh(s):
        for k, (w, kind, opts) in s.w.items():
            if kind in "cr" and callable(opts):
                w["values"] = opts()
        keep = s.sel
        s.tree.delete(*s.tree.get_children())
        for r in s.pm.rows(s.table, s.order):
            tg = s.tag(r) if s.tag else ""
            s.tree.insert("", "end", iid=str(r["id"]), values=[("" if r.get(c[0]) is None else (f"{r[c[0]]:,.0f}" if isinstance(r.get(c[0]), float) and c[0].endswith(("cost", "budget", "impact")) else r[c[0]])) if c[0] in r else "" for c in s.cols], tags=(tg,) if tg else ())
        if keep and s.tree.exists(str(keep)):
            s.tree.selection_set(str(keep))


class Single(ttk.Frame):
    """Single-record form (charter, plan)."""

    def __init__(s, master, app, table, fields, extra=()):
        super().__init__(master)
        s.app, s.pm, s.table, s.fields = app, app.pm, table, fields
        s.w = {}
        for n, (k, lab, kind) in enumerate(fields):
            ttk.Label(s, text=lab).grid(row=n, column=0, sticky="nw", padx=6, pady=3)
            w = tk.Text(s, height=3, width=90, wrap="word") if kind == "t" else ttk.Entry(s, width=40)
            w.grid(row=n, column=1, sticky="w", pady=3); s.w[k] = (w, kind)
        bf = ttk.Frame(s); bf.grid(row=len(fields), column=1, sticky="w", pady=6)
        ttk.Button(bf, text="Save", command=s.save).pack(side="left", padx=3)
        for t, f in extra:
            ttk.Button(bf, text=t, command=lambda f=f: f(s)).pack(side="left", padx=3)
        s.note = ttk.Label(s, foreground=COL["red"], wraplength=800); s.note.grid(row=len(fields) + 1, column=1, sticky="w")

    def save(s):
        d = {k: (w.get("1.0", "end").strip() if kind == "t" else w.get().strip()) for k, (w, kind) in s.w.items()}
        try:
            s.pm.save(s.table, d, 1 if s.pm.get(s.table, 1) else None)
            s.app.refresh(); messagebox.showinfo("Saved", "Saved successfully.")
        except VE as e:
            messagebox.showerror("Validation error", str(e))

    def refresh(s):
        r = s.pm.get(s.table, 1) or {}
        for k, (w, kind) in s.w.items():
            v = "" if r.get(k) is None else (f"{r[k]:.0f}" if k == "budget" else str(r[k]))
            if kind == "t":
                w.delete("1.0", "end"); w.insert("1.0", v)
            else:
                w.delete(0, "end"); w.insert(0, v)
        if s.table == "charter" and r.get("approved"):
            s.note.config(text=f"Baseline approved: budget and deadline are locked (baseline {r['base_budget']:,.0f} PKR / {r['base_deadline']}). Use Change Requests to change them.")


class App(tk.Tk):
    def __init__(s, db="spms.db"):
        super().__init__()
        s.pm = PM(db)
        s.title("Smart Healthcare Project Management System - Hannan Razzaq (CSE-494)")
        s.geometry("1280x780")
        st = ttk.Style(s); st.theme_use("clam")
        st.configure("TNotebook.Tab", padding=(10, 4)); st.configure("Treeview", rowheight=22)
        hd = tk.Frame(s, bg=COL["navy"]); hd.pack(fill="x")
        tk.Label(hd, text="Smart Healthcare Project Management & Monitoring System", bg=COL["navy"], fg="white", font=("Arial", 15, "bold")).pack(side="left", padx=10, pady=6)
        tk.Label(hd, text="Project Manager: Hannan Razzaq", bg=COL["navy"], fg="#aed6f1", font=("Arial", 10)).pack(side="right", padx=10)
        s.nb = ttk.Notebook(s); s.nb.pack(fill="both", expand=True)
        s.tabs = []
        team = lambda: [""] + [r["name"] for r in s.pm.rows("team")]
        reqs = lambda: ids(s.pm.rows("requirements"), "title")
        apr = lambda: ids(s.pm.q("SELECT * FROM requirements WHERE status='Approved'"), "title")
        tasks = lambda: ids(s.pm.rows("tasks"), "name")
        crs = lambda: ids(s.pm.rows("change_requests"), "title")
        wbs = lambda: ids(s.pm.rows("wbs"), "name")
        s.build_dashboard()
        # 1 initiation
        init = ttk.Notebook(s.nb); s.add_tab("1 Initiation & Integration", init)
        ch = Single(init, s, "charter", [("name", "Project name", "e"), ("objectives", "Objectives", "t"), ("stakeholders", "Stakeholders", "t"),
                                         ("scope_boundaries", "Scope boundaries", "t"), ("budget", "Approved budget (PKR)", "e"), ("start_date", "Start date (YYYY-MM-DD)", "e"),
                                         ("deadline", "Deadline (YYYY-MM-DD)", "e"), ("manager", "Project manager", "e")])
        init.add(ch, text="Project Charter"); s.tabs.append(ch)
        pl = Single(init, s, "plan", [("scope", "Scope", "t"), ("schedule", "Schedule", "t"), ("cost", "Cost", "t"), ("quality", "Quality", "t")],
                    extra=[("Auto-generate from live project data", lambda f: (s.pm.gen_plan(), s.refresh()))])
        init.add(pl, text="Management Plan"); s.tabs.append(pl)
        for ttl, c in (("Team & Responsibilities", Crud(init, s, "team", [("id", "ID", 40), ("name", "Name", 200), ("role", "Role", 200), ("responsibility", "Responsibility", 400)], [("name", "Name", "e", 0), ("role", "Role", "e", 0), ("responsibility", "Responsibility", "e", 0)])),
                       ("Milestones", Crud(init, s, "milestones", [("id", "ID", 40), ("name", "Milestone", 260), ("due", "Due", 90), ("task_id", "Task", 50), ("owner", "Owner", 160), ("status", "Status", 80)],
                                           [("name", "Milestone", "e", 0), ("due", "Due (YYYY-MM-DD)", "e", 0), ("task_id", "Linked task", "r", tasks), ("owner", "Owner", "c", team), ("status", "Status", "c", MS_ST)], order="due",
                                           tag=lambda r: "bad" if r["status"] == "Missed" else "ok" if r["status"] == "Achieved" else "")),
                       ("Status Log", Crud(init, s, "project_status", [("id", "ID", 40), ("date", "Date", 90), ("status", "Status", 90), ("note", "Note", 600), ("reported_by", "By", 140)],
                                           [("date", "Date", "e", 0), ("status", "Status", "c", PROJ_ST), ("note", "Note", "t", 0), ("reported_by", "Reported by", "c", team)], order="date")),
                       ("Closure", Crud(init, s, "closure", [("id", "ID", 40), ("date", "Date", 90), ("deliverables_accepted", "Deliverables accepted", 300), ("lessons_learned", "Lessons learned", 400), ("signoff", "Sign-off", 140)],
                                        [("date", "Closure date", "e", 0), ("deliverables_accepted", "Deliverables accepted", "t", 0), ("lessons_learned", "Lessons learned", "t", 0), ("signoff", "Sign-off by", "e", 0)]))):
            init.add(c, text=ttl); s.tabs.append(c)
        # 2 scope
        sc = ttk.Notebook(s.nb); s.add_tab("2 Scope & WBS", sc)
        rq = Crud(sc, s, "requirements", [("id", "ID", 40), ("title", "Requirement", 300), ("priority", "Priority", 70), ("status", "Status", 80), ("cr_id", "CR", 40), ("description", "Description", 400)],
                  [("title", "Title", "e", 0), ("priority", "Priority", "c", PRIORITY), ("status", "Status (Approved = in scope)", "c", REQ_ST), ("cr_id", "Raised by change request", "r", crs), ("description", "Description", "t", 0)],
                  tag=lambda r: "ok" if r["status"] == "Approved" else "warn" if r["status"] == "Proposed" else "bad",
                  extra=[("Approve requirement", lambda f: f.run(lambda: f.pm.save("requirements", {"status": "Approved"}, f.sel) if f.sel else (_ for _ in ()).throw(VE("Select a requirement."))))])
        sc.add(rq, text="Requirements"); s.tabs.append(rq)
        wb = ttk.Frame(sc); sc.add(wb, text="WBS")
        bf = ttk.Frame(wb); bf.pack(fill="x", pady=4)
        ttk.Button(bf, text="Generate WBS from approved scope", command=lambda: (s.pm.gen_wbs(), s.refresh())).pack(side="left", padx=4)
        s.wbs = ttk.Treeview(wb, columns=("code", "kind", "req", "tasks"), height=12)
        for k, h, w in (("#0", "WBS element", 420), ("code", "Code", 70), ("kind", "Type", 110), ("req", "Requirement", 300), ("tasks", "Cost (PKR)", 100)):
            s.wbs.heading(k, text=h); s.wbs.column(k, width=w)
        s.wbs.pack(fill="both", expand=True); s.tabs.append(s.wbs_refresher())
        wbm = Crud(sc, s, "wbs", [("id", "ID", 40), ("code", "Code", 60), ("name", "Element", 350), ("kind", "Type", 100), ("parent_id", "Parent", 60), ("req_id", "Req", 50)],
                   [("name", "Name", "e", 0), ("kind", "Type", "c", ["Deliverable", "Work Package"]), ("parent_id", "Parent element", "r", wbs), ("req_id", "Requirement (approved only)", "r", apr)], order="code")
        sc.add(wbm, text="WBS (manual edit)"); s.tabs.append(wbm)
        cr = Crud(sc, s, "change_requests", [("id", "ID", 35), ("title", "Change", 260), ("cost_impact", "Cost impact", 90), ("days_impact", "Days", 45), ("status", "Status", 70), ("requested_by", "By", 120), ("justification", "Justification", 300)],
                  [("title", "Title", "e", 0), ("requested_by", "Requested by", "e", 0), ("cost_impact", "Cost impact (PKR)", "e", 0), ("days_impact", "Schedule impact (days)", "e", 0), ("justification", "Justification", "t", 0)],
                  tag=lambda r: {"Approved": "ok", "Pending": "warn", "Rejected": "bad"}[r["status"]],
                  extra=[("Impact preview", s.cr_preview), ("APPROVE change", lambda f: s.cr_decide(f, "Approved")), ("REJECT change", lambda f: s.cr_decide(f, "Rejected"))])
        sc.add(cr, text="Change Requests"); s.tabs.append(cr)
        bl = ttk.Frame(sc); sc.add(bl, text="Baseline Log")
        s.bl = ttk.Treeview(bl, columns=("cr", "ob", "nb", "od", "nd", "at"), show="headings", height=8)
        for k, h, w in (("cr", "CR", 50), ("ob", "Budget before", 120), ("nb", "Budget after", 120), ("od", "Deadline before", 120), ("nd", "Deadline after", 120), ("at", "Date", 100)):
            s.bl.heading(k, text=h); s.bl.column(k, width=w)
        s.bl.pack(fill="both", expand=True); s.tabs.append(type("R", (), {"refresh": lambda self: s.fill(s.bl, [(r["cr_id"], f"{r['old_budget']:,.0f}", f"{r['new_budget']:,.0f}", r["old_deadline"], r["new_deadline"], r["at"]) for r in s.pm.rows("baseline_log")])})())
        # 3 schedule
        s.build_schedule(team, apr, tasks)
        s.build_gantt()
        s.build_cost()
        # 5 quality & risk
        qn = ttk.Notebook(s.nb); s.add_tab("5 Quality & Risk", qn)
        df = Crud(qn, s, "defects", [("id", "ID", 40), ("title", "Defect", 380), ("severity", "Severity", 70), ("assignee", "Assigned to", 150), ("status", "Status", 90), ("task_id", "Task", 50), ("reported", "Reported", 90)],
                  [("title", "Title", "e", 0), ("severity", "Severity", "c", SEV), ("assignee", "Assigned to", "c", team), ("status", "Status", "c", DEF_ST), ("task_id", "Task", "r", tasks)],
                  tag=lambda r: "bad" if r["severity"] == "Critical" and r["status"] in ("Open", "In Progress") else "ok" if r["status"] in ("Resolved", "Closed") else "warn" if r["severity"] == "High" else "")
        qn.add(df, text="Defect Tracking"); s.tabs.append(df)
        qc = Crud(qn, s, "quality_checks", [("id", "ID", 40), ("deliverable", "Deliverable", 280), ("item", "Checklist item", 260), ("result", "Result", 70), ("inspector", "Inspector", 130), ("test_date", "Date", 90), ("notes", "Notes", 250)],
                  [("deliverable", "Deliverable", "c", lambda: [r["title"] for r in s.pm.q("SELECT title FROM requirements WHERE status='Approved'")]), ("item", "Checklist item", "e", 0), ("result", "Result", "c", QC_ST), ("inspector", "Inspector", "c", team), ("test_date", "Inspection date", "e", 0), ("notes", "Notes", "e", 0)],
                  tag=lambda r: {"Pass": "ok", "Fail": "bad"}.get(r["result"], ""), height=10,
                  extra=[("Generate checklist for approved deliverables", lambda f: messagebox.showinfo("Checklist", f"{f.pm.gen_checklist()} items added.") or s.refresh())])
        qn.add(qc, text="Quality Checklist"); s.tabs.append(qc)
        rk = Crud(qn, s, "risks", [("id", "ID", 40), ("description", "Risk / issue", 330), ("likelihood", "L", 30), ("impact", "I", 30), ("score", "Score", 45), ("owner", "Owner", 130), ("status", "Status", 70), ("preventive", "Preventive", 200), ("corrective", "Corrective", 200)],
                  [("description", "Risk description", "e", 0), ("likelihood", "Likelihood (1-5)", "c", ["1", "2", "3", "4", "5"]), ("impact", "Impact (1-5)", "c", ["1", "2", "3", "4", "5"]), ("owner", "Owner", "c", team), ("status", "Status", "c", RISK_ST),
                   ("preventive", "Preventive action", "t", 0), ("corrective", "Corrective action", "t", 0)], order="score DESC", tag=lambda r: "bad" if r["score"] >= 15 else "warn" if r["score"] >= 8 else "ok", height=7)
        qn.add(rk, text="Risk Register"); s.tabs.append(rk)
        mx = ttk.Frame(qn); qn.add(mx, text="Prioritization Matrix")
        s.mx = tk.Canvas(mx, width=520, height=470, bg="white"); s.mx.pack(side="left", padx=10, pady=10)
        s.rank = ttk.Treeview(mx, columns=("rank", "score", "lvl", "desc"), show="headings", height=16)
        for k, h, w in (("rank", "#", 30), ("score", "Score", 50), ("lvl", "Level", 60), ("desc", "Risk (ranked by Likelihood x Impact)", 430)):
            s.rank.heading(k, text=h); s.rank.column(k, width=w)
        for k, v in (("High", "bad"), ("Medium", "warn"), ("Low", "ok")):
            s.rank.tag_configure(k, background=TAGS[v])
        s.rank.pack(side="left", fill="both", expand=True, padx=6, pady=10)
        pd = ttk.Frame(qn); qn.add(pd, text="PDPC (Risk Response)")
        s.pd = ttk.Treeview(pd, columns=("score",), height=18); s.pd.heading("#0", text="Process Decision Program Chart: Goal -> Potential problem -> Preventive action -> Corrective (contingency) action"); s.pd.column("#0", width=900); s.pd.heading("score", text="Score"); s.pd.column("score", width=60)
        for k, v in (("goal", "#d6eaf8"), ("risk", "#fadbd8"), ("prev", "#d5f5e3"), ("corr", "#fdebd0")):
            s.pd.tag_configure(k, background=v)
        s.pd.pack(fill="both", expand=True, padx=6, pady=6)
        s.tabs.append(type("R", (), {"refresh": lambda self: s.draw_risk()})())
        # 6 report
        rp = ttk.Frame(s.nb); s.add_tab("6 Dashboard & Report", None, rp)
        bf = ttk.Frame(rp); bf.pack(fill="x", pady=4)
        ttk.Button(bf, text="Export report (.txt)", command=s.export).pack(side="left", padx=4)
        ttk.Button(bf, text="Save screenshot-ready refresh", command=s.refresh).pack(side="left", padx=4)
        s.rep = tk.Text(rp, font=("Consolas", 10), wrap="none"); s.rep.pack(fill="both", expand=True)
        s.refresh()

    def add_tab(s, title, w, frame=None):
        s.nb.add(frame or w, text=title)

    def fill(s, tree, rows, tags=None):
        tree.delete(*tree.get_children())
        for n, r in enumerate(rows):
            tree.insert("", "end", values=r, tags=(tags[n],) if tags and tags[n] else ())

    # ---------- dashboard ----------
    def build_dashboard(s):
        f = ttk.Frame(s.nb); s.nb.add(f, text="Dashboard")
        s.cards = {}
        row = ttk.Frame(f); row.pack(fill="x", padx=8, pady=8)
        for k in ("Progress", "Budget used", "CPI", "SPI", "Forecast finish", "Pending CRs", "Delayed tasks", "Critical defects"):
            c = tk.Frame(row, bg="white", highlightbackground="#ccd1d1", highlightthickness=1); c.pack(side="left", expand=True, fill="x", padx=3)
            tk.Label(c, text=k, bg="white", fg="#7f8c8d", font=("Arial", 9)).pack(pady=(6, 0))
            v = tk.Label(c, text="-", bg="white", font=("Arial", 15, "bold")); v.pack(pady=(0, 6)); s.cards[k] = v
        s.pb = ttk.Progressbar(f, maximum=100); s.pb.pack(fill="x", padx=11)
        ttk.Label(f, text="Alerts & warnings", font=("Arial", 11, "bold")).pack(anchor="w", padx=10, pady=(10, 0))
        s.warn = tk.Listbox(f, height=9, font=("Arial", 10)); s.warn.pack(fill="x", padx=10, pady=4)
        ttk.Label(f, text="Delayed / impacted activities", font=("Arial", 11, "bold")).pack(anchor="w", padx=10)
        s.dl = ttk.Treeview(f, columns=("id", "name", "who", "st", "d", "fe", "by"), show="headings", height=7)
        for k, h, w in (("id", "ID", 40), ("name", "Activity", 300), ("who", "Assignee", 150), ("st", "Status", 80), ("d", "Delay (days)", 80), ("fe", "Forecast end", 100), ("by", "Delayed because of task", 160)):
            s.dl.heading(k, text=h); s.dl.column(k, width=w)
        s.dl.pack(fill="both", expand=True, padx=10, pady=4)
        s.tabs = [type("R", (), {"refresh": lambda self: s.refresh_dash()})()]

    def refresh_dash(s):
        d = s.pm.dashboard()
        if not d["charter"]:
            return
        ev, ch = d["evm"], d["charter"]
        fm = lambda v: "n/a" if v is None else f"{v:.2f}"
        vals = {"Progress": f"{d['progress']:.1f}%", "Budget used": f"{ev['AC'] / ch['budget'] * 100:.1f}%", "CPI": fm(ev["CPI"]), "SPI": fm(ev["SPI"]),
                "Forecast finish": d["summary"]["forecast_finish"], "Pending CRs": len(d["pending_cr"]), "Delayed tasks": len(d["delayed"]), "Critical defects": len(d["critical_defects"])}
        bad = {"CPI": (ev["CPI"] or 9) < float(s.pm.setting("warn")), "SPI": (ev["SPI"] or 9) < float(s.pm.setting("warn")), "Forecast finish": d["summary"]["slip_days"] > 0,
               "Pending CRs": len(d["pending_cr"]) > 0, "Delayed tasks": len(d["delayed"]) > 0, "Critical defects": len(d["critical_defects"]) > 0}
        for k, v in vals.items():
            s.cards[k].config(text=v, fg=COL["red"] if bad.get(k) else COL["green"])
        s.pb["value"] = d["progress"]
        s.warn.delete(0, "end")
        for lv, m in d["warnings"]:
            s.warn.insert("end", f"[{lv}] {m}"); s.warn.itemconfig("end", fg={"CRITICAL": COL["red"], "WARNING": "#d68910"}.get(lv, COL["blue"]))
        if not d["warnings"]:
            s.warn.insert("end", "No warnings - project within thresholds.")
        s.fill(s.dl, [(r["id"], r["name"], r["assignee"], r["status"], r["delay"], F(r["fend"]), ", ".join(map(str, r["caused_by"])) or "(own delay)") for r in d["delayed"]])

    # ---------- change request actions ----------
    def cr_preview(s, f):
        if f.sel is None:
            return messagebox.showwarning("Select", "Select a change request.")
        i = s.pm.cr_impact(f.sel)
        messagebox.showinfo("Impact if approved",
                            f"Budget: {i['budget_before']:,.0f} -> {i['budget_after']:,.0f} PKR\nDeadline: {i['deadline_before']} -> {i['deadline_after']}\n"
                            f"Scope added: {', '.join(i['scope_added']) or 'none'}\nCurrent forecast finish: {i['forecast_finish']} "
                            f"({'meets' if i['meets_new_deadline'] else 'misses'} the new deadline)")

    def cr_decide(s, f, st):
        if f.sel is None:
            return messagebox.showwarning("Select", "Select a change request.")
        try:
            i = s.pm.cr_impact(f.sel)
            s.pm.save("change_requests", {"status": st}, f.sel); s.refresh()
            messagebox.showinfo(f"Change request {st}", (f"Baseline updated:\nBudget {i['budget_before']:,.0f} -> {i['budget_after']:,.0f}\nDeadline {i['deadline_before']} -> {i['deadline_after']}\n"
                                                         f"Scope now includes: {', '.join(i['scope_added']) or '-'}\nYou can now add tasks for these requirements.") if st == "Approved" else "Change rejected; related proposed requirements marked Rejected.")
        except VE as e:
            messagebox.showerror("Validation error", str(e))

    # ---------- WBS ----------
    def wbs_refresher(s):
        def r(self):
            s.wbs.delete(*s.wbs.get_children())
            rows = s.pm.rows("wbs", "code")
            cost = {t["req_id"]: 0 for t in s.pm.rows("tasks")}
            for t in s.pm.rows("tasks"):
                cost[t["req_id"]] += t["planned_cost"]
            for w in rows:
                rq = s.pm.get("requirements", w["req_id"]) if w["req_id"] else None
                s.wbs.insert(str(w["parent_id"] or ""), "end", iid=str(w["id"]), text=w["name"], open=True, values=(w["code"], w["kind"], rq["title"] if rq else "", f"{cost.get(w['req_id'], 0):,.0f}" if w["kind"] == "Deliverable" else ""))
        return type("R", (), {"refresh": r})()

    # ---------- schedule ----------
    def build_schedule(s, team, apr, tasks):
        sn = ttk.Notebook(s.nb); s.add_tab("3 Schedule & Resources", sn)
        tk_ = Crud(sn, s, "tasks", [("id", "ID", 35), ("name", "Activity", 250), ("assignee", "Assignee", 140), ("start", "Start", 85), ("duration", "Dur", 35), ("preds", "Pred", 55), ("pstart", "Sched start", 85), ("pend", "Sched end", 85), ("req_id", "Req", 35), ("planned_cost", "Planned cost", 85), ("actual_cost", "Actual", 80), ("pct", "%", 35)],
                   [("name", "Activity name", "e", 0), ("assignee", "Assigned to", "c", team), ("start", "Earliest start (YYYY-MM-DD)", "e", 0), ("duration", "Duration (days)", "e", 0), ("preds", "Predecessor IDs (e.g. 3,4)", "e", 0), ("req_id", "Requirement (approved only)", "r", apr),
                    ("planned_cost", "Planned cost (PKR)", "e", 0), ("actual_cost", "Actual cost (PKR)", "e", 0), ("pct", "% complete", "e", 0)],
                   tag=lambda r: "ok" if r["pct"] >= 100 else "", height=11)
        sn.add(tk_, text="Activities (dependencies, resources, cost)"); s.tabs.append(tk_)
        f = ttk.Frame(sn); sn.add(f, text="Generated Schedule & Delay Impact")
        ttk.Button(f, text="Re-generate schedule", command=s.refresh).pack(anchor="w", padx=6, pady=4)
        s.sch = ttk.Treeview(f, columns=("id", "name", "who", "ps", "pe", "fs", "fe", "d", "st", "by"), show="headings", height=14)
        for k, h, w in (("id", "ID", 35), ("name", "Activity", 260), ("who", "Assignee", 130), ("ps", "Planned start", 90), ("pe", "Planned end", 90), ("fs", "Forecast start", 90), ("fe", "Forecast end", 90), ("d", "Delay", 45), ("st", "Status", 80), ("by", "Caused by", 70)):
            s.sch.heading(k, text=h); s.sch.column(k, width=w)
        for k, v in (("bad", "bad"), ("warn", "warn"), ("ok", "ok")):
            s.sch.tag_configure(k, background=TAGS[v])
        s.sch.pack(fill="both", expand=True, padx=6)
        s.sumlbl = ttk.Label(f, font=("Arial", 11, "bold"), wraplength=1100); s.sumlbl.pack(anchor="w", padx=8, pady=6)
        s.tabs.append(type("R", (), {"refresh": lambda self: s.refresh_sched()})())

    def refresh_sched(s):
        sch = s.pm.schedule()
        s.fill(s.sch, [(r["id"], r["name"], r["assignee"], F(r["pstart"]), F(r["pend"]), F(r["fstart"]), F(r["fend"]), r["delay"], r["status"], ",".join(map(str, r["caused_by"]))) for r in sch],
               [("bad" if r["status"] == "Delayed" else "warn" if r["status"] in ("Impacted", "Late start") else "ok" if r["status"] == "Complete" else "") for r in sch])
        sm, ch = s.pm.schedule_summary(), s.pm.charter()
        if ch:
            s.sumlbl.config(text=f"Deadline {ch['deadline']} | Forecast finish {sm['forecast_finish']} | " + ("ON TIME" if sm["slip_days"] <= 0 else f"PROJECT WILL FINISH {sm['slip_days']} DAY(S) AFTER THE DEADLINE"),
                            foreground=COL["green"] if sm["slip_days"] <= 0 else COL["red"])

    # ---------- gantt ----------
    def build_gantt(s):
        f = ttk.Frame(s.nb); s.add_tab("3b Gantt Chart", None, f)
        s.gc = tk.Canvas(f, bg="white"); hs = ttk.Scrollbar(f, orient="horizontal", command=s.gc.xview); vs = ttk.Scrollbar(f, command=s.gc.yview)
        s.gc.configure(xscrollcommand=hs.set, yscrollcommand=vs.set)
        hs.pack(side="bottom", fill="x"); vs.pack(side="right", fill="y"); s.gc.pack(fill="both", expand=True)
        s.tabs.append(type("R", (), {"refresh": lambda self: s.draw_gantt()})())

    def draw_gantt(s):
        c, ch = s.gc, s.pm.charter()
        c.delete("all")
        sch = s.pm.schedule()
        if not ch or not sch:
            return
        x0, top, rh, px = 230, 50, 26, 7
        d0 = D(ch["start_date"]); d1 = max(max(r["fend"] for r in sch), D(ch["deadline"])) + TD(days=7)
        X = lambda d: x0 + (d - d0).days * px
        W, H = X(d1) + 20, top + rh * (len(sch) + 2) + 20
        c.configure(scrollregion=(0, 0, W, H))
        d = d0
        while d <= d1:
            c.create_line(X(d), top - 10, X(d), H, fill="#ecf0f1"); c.create_text(X(d) + 2, top - 22, text=d.strftime("%d %b"), anchor="w", font=("Arial", 7)); d += TD(days=7)
        for n, r in enumerate(sch):
            y = top + n * rh
            c.create_text(6, y + 10, text=f"{r['id']}. {r['name'][:30]}", anchor="w", font=("Arial", 8))
            c.create_rectangle(X(r["pstart"]), y + 19, X(r["pend"] + ONE), y + 22, fill=COL["grey"], outline="")           # baseline
            col = COL["green"] if r["status"] == "Complete" else COL["red"] if r["status"] == "Delayed" else COL["amber"] if r["status"] in ("Impacted", "Late start") else COL["blue"]
            c.create_rectangle(X(r["fstart"]), y + 4, X(r["fend"] + ONE), y + 17, fill="#d6eaf8" if col == COL["blue"] else col, outline=col, stipple="" if r["pct"] >= 100 else "")
            c.create_rectangle(X(r["fstart"]), y + 4, X(r["fstart"]) + (X(r["fend"] + ONE) - X(r["fstart"])) * r["pct"] / 100, y + 17, fill=COL["navy"], outline="")
            for p in r["preds"]:
                pr = sch[[q["id"] for q in sch].index(p)]
                yy = top + [q["id"] for q in sch].index(p) * rh + 10
                c.create_line(X(pr["fend"] + ONE), yy, X(r["fstart"]), y + 10, fill="#7f8c8d", arrow="last", width=1)
        yb = top + len(sch) * rh + 8
        for mi, m in enumerate(s.pm.rows("milestones", "due")):
            xm = X(D(m["due"]))
            c.create_polygon(xm, yb, xm + 6, yb + 6, xm, yb + 12, xm - 6, yb + 6, fill={"Achieved": COL["green"], "Missed": COL["red"]}.get(m["status"], COL["amber"]), outline="black")
            c.create_text(xm, yb + 20 + 11 * (mi % 2), text=m["name"][:28], font=("Arial", 7), angle=0)
        for dd, col, lab in ((D(ch["deadline"]), COL["red"], "DEADLINE"), (s.pm.asof(), "#e67e22", "STATUS DATE")):
            c.create_line(X(dd), top - 8, X(dd), H, fill=col, dash=(4, 3), width=2); c.create_text(X(dd) + 3, H - 6, text=lab, fill=col, anchor="w", font=("Arial", 8, "bold"))
        c.create_text(6, 8, anchor="w", font=("Arial", 8), text="Legend: grey line = baseline | dark fill = % done | green = complete | blue = on track | amber = impacted | red = delayed | diamonds = milestones")

    # ---------- cost / EVM ----------
    def build_cost(s):
        f = ttk.Frame(s.nb); s.add_tab("4 Cost & EVM", None, f)
        top = ttk.LabelFrame(f, text=" Reporting settings "); top.pack(fill="x", padx=8, pady=6)
        s.ent = {}
        for k, lab in (("asof", "Status date"), ("warn", "Warning threshold (CPI/SPI <)"), ("crit", "Critical threshold (CPI/SPI <)")):
            ttk.Label(top, text=lab).pack(side="left", padx=6); e = ttk.Entry(top, width=12); e.pack(side="left"); s.ent[k] = e
        ttk.Button(top, text="Apply", command=s.apply_settings).pack(side="left", padx=10)
        s.evl = ttk.Label(f, font=("Consolas", 11), justify="left"); s.evl.pack(anchor="w", padx=12, pady=6)
        s.ew = tk.Listbox(f, height=6, font=("Arial", 10)); s.ew.pack(fill="x", padx=10, pady=4)
        s.ct = ttk.Treeview(f, columns=("id", "name", "bac", "pv", "ev", "ac", "cv"), show="headings", height=12)
        for k, h, w in (("id", "ID", 35), ("name", "Activity", 280), ("bac", "Budget (BAC)", 100), ("pv", "PV", 100), ("ev", "EV", 100), ("ac", "AC", 100), ("cv", "CV = EV-AC", 100)):
            s.ct.heading(k, text=h); s.ct.column(k, width=w)
        s.ct.tag_configure("bad", background=TAGS["bad"])
        s.ct.pack(fill="both", expand=True, padx=10, pady=4)
        s.tabs.append(type("R", (), {"refresh": lambda self: s.refresh_cost()})())

    def apply_settings(s):
        try:
            for k, e in s.ent.items():
                s.pm.set_setting(k, e.get())
            s.refresh()
        except VE as e:
            messagebox.showerror("Validation error", str(e))

    def refresh_cost(s):
        ev, ch = s.pm.evm(), s.pm.charter()
        for k, e in s.ent.items():
            e.delete(0, "end"); e.insert(0, s.pm.setting(k))
        if not ch:
            return
        fm = lambda v: "n/a" if v is None else f"{v:.2f}"
        s.evl.config(text=(f"Approved budget : {ch['budget']:>12,.0f}     Planned total (BAC): {ev['BAC']:>12,.0f}     Actual spent: {ev['AC']:>12,.0f}\n"
                           f"PV = {ev['PV']:>12,.0f}   EV = {ev['EV']:>12,.0f}   AC = {ev['AC']:>12,.0f}\n"
                           f"CPI = EV/AC = {fm(ev['CPI'])}    SPI = EV/PV = {fm(ev['SPI'])}    CV = {ev['CV']:,.0f}    SV = {ev['SV']:,.0f}    EAC = {ev['EAC']:,.0f}    VAC = {ev['VAC']:,.0f}"))
        s.ew.delete(0, "end")
        for lv, m in ev["warnings"]:
            s.ew.insert("end", f"[{lv}] {m}"); s.ew.itemconfig("end", fg=COL["red"] if lv == "CRITICAL" else "#d68910")
        if not ev["warnings"]:
            s.ew.insert("end", "Cost and schedule performance within thresholds.")
        s.fill(s.ct, [(r["id"], r["name"], f"{r['bac']:,.0f}", f"{r['pv']:,.0f}", f"{r['ev']:,.0f}", f"{r['ac']:,.0f}", f"{r['cv']:,.0f}") for r in ev["per_task"]], ["bad" if r["cv"] < 0 else "" for r in ev["per_task"]])

    # ---------- risk views ----------
    def draw_risk(s):
        c = s.mx; c.delete("all")
        risks = s.pm.q("SELECT * FROM risks WHERE status<>'Closed'")
        ox, oy, cs = 60, 20, 80
        for L in range(5, 0, -1):
            for I in range(1, 6):
                sc = L * I; col = "#f5b7b1" if sc >= 15 else "#fad7a0" if sc >= 8 else "#abebc6"
                x, y = ox + (I - 1) * cs, oy + (5 - L) * cs
                c.create_rectangle(x, y, x + cs, y + cs, fill=col, outline="white")
                c.create_text(x + cs - 4, y + 4, text=str(sc), anchor="ne", font=("Arial", 7), fill="#7f8c8d")
                ids_ = [str(r["id"]) for r in risks if r["likelihood"] == L and r["impact"] == I]
                if ids_:
                    c.create_text(x + cs / 2, y + cs / 2, text="R" + ",R".join(ids_), font=("Arial", 10, "bold"), width=cs - 8)
        for k in range(1, 6):
            c.create_text(ox + (k - 1) * cs + cs / 2, oy + 5 * cs + 12, text=str(k)); c.create_text(ox - 14, oy + (5 - k) * cs + cs / 2, text=str(k))
        c.create_text(ox + 2.5 * cs, oy + 5 * cs + 32, text="IMPACT ->", font=("Arial", 9, "bold")); c.create_text(14, oy + 2.5 * cs, text="LIKELIHOOD", angle=90, font=("Arial", 9, "bold"))
        rr = s.pm.q("SELECT * FROM risks WHERE status<>'Closed' ORDER BY score DESC")
        s.rank.delete(*s.rank.get_children())
        for n, r in enumerate(rr, 1):
            s.rank.insert("", "end", values=(n, r["score"], s.pm.risk_level(r["score"]), f"R{r['id']}: {r['description']}"), tags=(s.pm.risk_level(r["score"]),))
        s.pd.delete(*s.pd.get_children())
        p = s.pm.pdpc(); g = s.pd.insert("", "end", text="GOAL: " + p["goal"], open=True, tags=("goal",))
        for r in p["risks"]:
            n = s.pd.insert(g, "end", text=f"[{s.pm.risk_level(r['score'])}] POTENTIAL PROBLEM R{r['id']}: {r['description']}", values=(r["score"],), open=True, tags=("risk",))
            s.pd.insert(n, "end", text="PREVENTIVE ACTION: " + (r["preventive"] or "-"), tags=("prev",))
            s.pd.insert(n, "end", text="CORRECTIVE ACTION (if it occurs): " + (r["corrective"] or "-"), tags=("corr",))

    def export(s):
        p = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="project_report.txt")
        if p:
            open(p, "w", encoding="utf-8").write(s.pm.report_text()); messagebox.showinfo("Exported", p)

    def refresh(s):
        try:
            s.pm.sync()
            for t in s.tabs:
                t.refresh()
            s.rep.delete("1.0", "end"); s.rep.insert("1.0", s.pm.report_text())
        except Exception as e:
            messagebox.showerror("Refresh error", f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else "spms.db"
    fresh = not os.path.exists(db)
    app = App(db)
    if fresh and not app.pm.charter():
        if messagebox.askyesno("Sample data", "Load the Smart Healthcare case-study sample data?"):
            seed(app.pm); app.refresh()
    app.mainloop()
