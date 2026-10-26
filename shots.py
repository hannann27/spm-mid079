import sys, os, subprocess, time
from app import *
if os.path.exists("spms.db"): os.remove("spms.db")
os.makedirs("screenshots", exist_ok=True)
app = App("spms.db"); seed(app.pm); app.refresh()
app.geometry("1280x780+0+0")
def snap(name):
    app.update_idletasks(); app.update(); time.sleep(0.3); app.update()
    subprocess.run(["import","-window","root",f"screenshots/{name}.png"])
def tab(i, sub=None, name=None):
    app.nb.select(i); app.update()
    if sub is not None:
        nb=[w for w in app.nb.winfo_children() if isinstance(w, ttk.Notebook) and str(w)==app.nb.tabs()[i]][0]; nb.select(sub); app.update()
    snap(name)
names=[(0,None,"01_dashboard"),(1,0,"02_charter"),(1,1,"03_mgmt_plan"),(1,3,"04_milestones"),(1,4,"05_status_log"),(2,0,"06_requirements"),(2,1,"07_wbs"),(2,3,"08_change_requests"),(3,0,"09_activities"),(3,1,"10_schedule_delay_impact"),(4,None,"11_gantt"),(5,None,"12_cost_evm"),(6,0,"13_defects"),(6,1,"14_quality_checklist"),(6,2,"15_risk_register"),(6,3,"16_prioritization_matrix"),(6,4,"17_pdpc"),(7,None,"18_report")]
for i,sub,n in names: tab(i,sub,n)
# demonstrate change request approval
app.pm.save("change_requests",{"status":"Approved"},1); app.pm.save("change_requests",{"status":"Approved"},2)
app.pm.save("tasks",{"name":"AI diagnosis module","assignee":"Backend Developer 1","start":"2026-11-10","duration":20,"preds":"8","req_id":8,"planned_cost":450000}); 
app.pm.save("tasks",{"name":"Mobile application","assignee":"Frontend Developer 2","start":"2026-11-14","duration":21,"preds":"10","req_id":9,"planned_cost":350000})
app.refresh()
tab(2,3,"19_change_approved"); tab(2,4,"20_baseline_log"); tab(4,None,"21_gantt_after_change"); tab(0,None,"22_dashboard_after_change")
