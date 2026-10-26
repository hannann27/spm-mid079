"""Test cases with expected vs actual results.  Run: python test_spms.py  (writes test_results.txt)"""
import os, tempfile
from spms_core import *

def fresh():
    p = os.path.join(tempfile.mkdtemp(), "t.db"); m = PM(p); seed(m); return m

def err(fn):
    try: fn(); return "no error"
    except VE as e: return "VE"

R = []
def check(id_, desc, exp, act):
    R.append((id_, desc, str(exp), str(act), "PASS" if str(exp) == str(act) else "FAIL"))

m = fresh()
ev = m.evm()
check("TC01", "Total planned cost (BAC) of sample project", 4950000, int(ev["BAC"]))
check("TC02", "PV at status date 2026-10-26", 2831667, round(ev["PV"]))
check("TC03", "EV = sum(cost x %complete)", 2542500, round(ev["EV"]))
check("TC04", "AC = sum of actual costs", 2715000, round(ev["AC"]))
check("TC05", "CPI = EV/AC", 0.94, round(ev["CPI"], 2))
check("TC06", "SPI = EV/PV", 0.90, round(ev["SPI"], 2))
check("TC07", "Warnings raised for CPI & SPI below 0.95", 2, sum(1 for l, t in ev["warnings"] if t.startswith(("CPI", "SPI"))))
sch = {r["id"]: r for r in m.schedule()}
check("TC08", "Task 5 (90% done, overdue) is flagged Delayed by 9 days", "Delayed/9", f"{sch[5]['status']}/{sch[5]['delay']}")
check("TC09", "Dependent task 7 is Impacted (+9 d) caused by task 5", "Impacted/9/[5]", f"{sch[7]['status']}/{sch[7]['delay']}/{sch[7]['caused_by']}")
sm = m.schedule_summary()
check("TC10", "Forecast finish vs deadline 2026-12-20 -> 2 days late", "2026-12-22/2", f"{sm['forecast_finish']}/{sm['slip_days']}")
check("TC11", "Task linked to a Proposed (unapproved) requirement is rejected", "VE", err(lambda: m.save("tasks", dict(name="AI", assignee="Backend Developer 1", start="2026-11-10", duration=5, req_id=8, planned_cost=1000))))
check("TC12", "Requirement from pending CR cannot be approved directly", "VE", err(lambda: m.save("requirements", {"status": "Approved"}, 8)))
check("TC13", "Task that would exceed approved budget is rejected", "VE", err(lambda: m.save("tasks", dict(name="X", assignee="QA Engineer", start="2026-11-10", duration=5, req_id=1, planned_cost=100000))))
check("TC14", "Circular dependency (task 1 depends on 13) rejected", "VE", err(lambda: m.save("tasks", {"preds": "13"}, 1)))
check("TC15", "Self dependency rejected", "VE", err(lambda: m.save("tasks", {"preds": "4"}, 4)))
check("TC16", "Negative cost rejected", "VE", err(lambda: m.save("tasks", {"planned_cost": "-5"}, 4)))
check("TC17", "Invalid date rejected", "VE", err(lambda: m.save("tasks", {"start": "31/13/2026"}, 4)))
check("TC18", "Unknown assignee rejected", "VE", err(lambda: m.save("tasks", {"assignee": "Nobody"}, 4)))
check("TC19", "% complete > 100 rejected", "VE", err(lambda: m.save("tasks", {"pct": 150}, 4)))
check("TC20", "Approved baseline: direct budget edit rejected", "VE", err(lambda: m.save("charter", {"budget": 9000000}, 1)))
check("TC21", "Critical defect without assignee rejected", "VE", err(lambda: m.save("defects", {"title": "t", "severity": "Critical"})))
check("TC22", "Defect cannot be Closed before Resolved", "VE", err(lambda: m.save("defects", {"status": "Closed"}, 1)))
check("TC23", "Quality Pass without inspector/date rejected", "VE", err(lambda: m.save("quality_checks", {"deliverable": "a", "item": "b", "result": "Pass"})))
check("TC24", "Failed inspection auto-creates a defect", 1, m.one("SELECT COUNT(*) c FROM defects WHERE title LIKE 'QC failed:%'")["c"])
check("TC25", "Risk score = likelihood x impact (4x5)", 20, m.get("risks", m.save("risks", dict(description="r", likelihood=4, impact=5, preventive="p", corrective="c")))["score"])
check("TC26", "High risk without corrective action rejected", "VE", err(lambda: m.save("risks", dict(description="r", likelihood=5, impact=5, preventive="p"))))
check("TC27", "Highest-ranked risk is score 20", 20, m.q("SELECT MAX(score) s FROM risks")[0]["s"])
check("TC28", "Project cannot be closed with incomplete work/critical defects", "VE", err(lambda: m.save("closure", dict(date="2026-12-20", signoff="Hannan Razzaq"))))
check("TC29", "Requirement with tasks cannot be deleted", "VE", err(lambda: m.delete("requirements", 2)))
check("TC30", "Task with successors cannot be deleted", "VE", err(lambda: m.delete("tasks", 3)))
# change-request flow
b0, d0 = m.charter()["budget"], m.charter()["deadline"]
prev = m.cr_impact(1)
m.save("change_requests", {"status": "Approved"}, 1); m.save("change_requests", {"status": "Approved"}, 2)
ch = m.charter()
check("TC31", "Approving CR1+CR2 raises budget by 800,000", 5800000, int(ch["budget"]))
check("TC32", "Approving CR1+CR2 extends deadline by 21 days (3 weeks)", "2027-01-10", ch["deadline"])
check("TC33", "Impact preview matched real result for CR1", 5450000, int(prev["budget_after"]))
check("TC34", "CR requirements now Approved (in scope)", 2, m.one("SELECT COUNT(*) c FROM requirements WHERE id IN (8,9) AND status='Approved'")["c"])
check("TC35", "Tasks for the new requirements are now accepted", "no error", err(lambda: m.save("tasks", dict(name="AI diagnosis module", assignee="Backend Developer 1", start="2026-11-10", duration=20, preds="8", req_id=8, planned_cost=450000))))
check("TC36", "Decided change request is locked", "VE", err(lambda: m.save("change_requests", {"title": "changed"}, 1)))
check("TC37", "Baseline log records both approvals", 2, m.one("SELECT COUNT(*) c FROM baseline_log")["c"])
def tc38():
    x = fresh(); c = x.save("change_requests", dict(title="Biometric", justification="j", cost_impact=1, days_impact=1))
    r = x.save("requirements", dict(title="Biometric login", status="Proposed", cr_id=c))
    x.save("change_requests", {"status": "Rejected"}, c)
    return x.get("requirements", r)["status"]
check("TC38", "Rejected CR marks its proposed requirement Rejected", "Rejected", tc38())
def tc39():
    x = fresh(); x.set_setting("asof", "2026-08-31"); x.x("UPDATE tasks SET actual_cost=0")
    return x.evm()["CPI"]
check("TC39", "No actual cost yet -> CPI is undefined (None), no crash", "None", tc39())
d = fresh().dashboard()
check("TC40", "Dashboard: pending CRs / delayed / critical defects", "2/6/2", f"{len(d['pending_cr'])}/{len(d['delayed'])}/{len(d['critical_defects'])}")
m3 = fresh(); m3.set_setting("asof", "2026-12-21")
check("TC41", "Late status date: more tasks flagged Delayed", True, sum(1 for r in m3.schedule() if r["status"] == "Delayed") > 6)
check("TC42", "Invalid status date rejected", "VE", err(lambda: m.set_setting("asof", "tomorrow")))
check("TC43", "WBS generated hierarchically (deliverables + work packages)", True, len(m.q("SELECT 1 FROM wbs WHERE parent_id IS NULL")) >= 7 and len(m.q("SELECT 1 FROM wbs WHERE parent_id IS NOT NULL")) >= 13)
check("TC44", "WBS rejects non-approved requirement", "VE", err(lambda: fresh().save("wbs", dict(name="x", kind="Deliverable", req_id=9))))

w = [38, 62, 24, 24, 6]
lines = ["Test cases - Smart Healthcare Project Management System (Hannan Razzaq)", ""] + [f"{'ID':6}{'Description':64}{'Expected':26}{'Actual':26}Result"]
for r in R:
    lines.append(f"{r[0]:6}{r[1][:62]:64}{r[2][:24]:26}{r[3][:24]:26}{r[4]}")
lines.append(f"\n{sum(r[4]=='PASS' for r in R)}/{len(R)} passed")
open("test_results.txt", "w").write("\n".join(lines)); print("\n".join(lines))
