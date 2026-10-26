# Smart Healthcare Project Management & Monitoring System
**Student:** Hannan Razzaq | **Course:** CSE-494 Software Project Management | **Mid-term Fall-2026 (CLO-6)**

Working desktop application: Python 3 + Tkinter GUI + SQLite database. No third-party packages needed.
(Linux only: `sudo apt install python3-tk`; Windows/macOS Python already includes Tkinter.)

## Run
    python app.py            # first start asks to load the case-study sample data (or just use the supplied spms.db)
    python test_spms.py      # 44 test cases, expected vs actual -> test_results.txt
    python spms_core.py x.db # rebuild a fresh seeded DB and print the status report

## Files
| File | Purpose |
|---|---|
| app.py | GUI (tabs for all 6 modules, Gantt chart, risk matrix, PDPC) |
| spms_core.py | Database, validation, scheduling, EVM, change control, reports, sample data |
| schema.sql / sample_data.sql | Database schema and sample data |
| spms.db | Ready-made database with the case-study data |
| test_spms.py / test_results.txt | Test cases and results (44/44 pass) |
| screenshots/ | Screenshots of every module (before and after approving the change requests) |

## Requirement -> where implemented
1. **Initiation & Integration** - tab *1 Initiation*: Charter (objectives, stakeholders, scope boundaries, budget, deadline), Management Plan (scope/schedule/cost/quality, auto-generated from live data), Team & responsibilities, Milestones, Status log, Closure (blocked while work is incomplete or critical defects are open).
2. **Scope & WBS** - tab *2*: requirements add/update/prioritize/approve; hierarchical WBS auto-generated from approved scope; change requests with justification, cost impact, schedule impact, status; baseline log. Tasks and WBS can only use *Approved* requirements, so unapproved requirements cannot enter scope.
3. **Schedule & Resources** - tab *3*: activities with assignee, duration, dependencies (circular/self dependency blocked), generated schedule (forward pass), delay detection and propagation to dependants and to the final deadline, Gantt chart (*3b*) with baseline, progress, dependencies, milestones, deadline and status-date lines.
4. **Cost & EVM** - tab *4*: planned/actual cost, PV, EV, AC, CPI, SPI (plus CV, SV, EAC, VAC), configurable status date and warning/critical thresholds, automatic warnings.
5. **Quality & Risk** - tab *5*: defect tracking, quality checklist (a failed inspection auto-creates a defect), risk register, 5x5 Prioritization Matrix with ranking, PDPC (goal -> problem -> preventive -> corrective).
6. **Integration, validation, reporting** - single SQLite database, validation on every form, Dashboard tab and *6 Dashboard & Report* (exportable .txt).

## Demo script (change request effect on scope, schedule and budget)
1. Dashboard shows CPI 0.94 / SPI 0.90 warnings, 6 delayed/impacted tasks, forecast finish 2026-12-22 (2 days late), 2 critical defects, 2 pending CRs.
2. *Activities*: try adding a task for "AI-based preliminary diagnosis module" -> **rejected** (not approved scope).
3. *Change Requests*: select CR 1 -> **Impact preview** -> **APPROVE change**; repeat for CR 2. Budget 5,000,000 -> 5,800,000, deadline 2026-12-20 -> 2027-01-10 (+800,000 PKR, +3 weeks), both requirements become Approved.
4. Add the AI and mobile tasks -> now accepted. See Baseline Log, Gantt, Cost & EVM and Dashboard update.
5. *Cost & EVM*: change the status date or thresholds and press Apply to see warnings change.

## Key rules / formulas
- Scheduled start = max(own earliest start, latest predecessor end + 1); end = start + duration - 1.
- Overdue unfinished task: forecast end = status date + ceil(duration x (1 - %done)); dependants shift; delay = forecast end - scheduled end.
- PV = sum(cost x elapsed fraction of scheduled window); EV = sum(cost x %complete); AC = sum(actual cost); CPI = EV/AC; SPI = EV/PV; EAC = BAC/CPI.
- Risk score = likelihood x impact (>=15 High, >=8 Medium).
