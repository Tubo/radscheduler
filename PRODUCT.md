# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Radiology registrars** (trainees in the Diagnostic Radiology programme) in one Canterbury, NZ hospital department. Their jobs: check upcoming shifts, subscribe to their shifts and leave through iCal, request leave, and put their names down for extra-duty shifts. They mostly use it **on a phone, in short bursts between cases**.
- **Chief registrar** (staff editor). Builds and edits the on-call roster, gives the first leave approval, enters approved leave into Microster, sets the published date range, and allocates extra duties. Works **on a desktop with a wide screen**, often for long editing sessions.
- **Director of Training (DoT)**. Gives the second leave approval.

Scope: one department today. Other departments or hospitals are a realistic future audience, so department-specific facts (supervisor name, holiday calendar, shift types) should not harden into assumptions that apply everywhere.

## Product Purpose

Radscheduler replaces an Excel roster plus emailed or paper leave requests. It gives the department one live record of who is working when, who is on leave, and who wants extra work. It checks the roster against the registrars' employment contract (the STONZ MECA) as it is built.

Success means the following:

- Registrars trust the calendar as the source of truth and never have to ask "am I on this weekend?"
- The chief registrar can produce a fair, contract-compliant roster without hand-checking the rules.
- Leave moves from request to two approvals to Microster entry without anything getting lost.

## Positioning

A spreadsheet can store a roster. It cannot tell you that a roster breaks the STONZ MECA. Radscheduler encodes the contract rules, for example:

- no more than 2 long days in 7
- no back-to-back long days
- no long day before nights
- RDOs (rostered days off) after nights
- every second weekend free
- no weekends next to leave
- notice periods for lieu days

It also weights on-call load, so fairness can be measured rather than argued about. Registrar status (pre-oncall, reliever, part time, pre-exam, buddy required, not available) and leave feed straight into who is eligible for a shift.

## Operating Context

- **Ordinary hours:** while on the roster, a registrar works 8am–5pm on weekdays unless on leave, on a public holiday, or rostered otherwise. These days aren't stored; the contract checks infer them. A weekday long day is the ordinary day followed by on call until 11pm, and a weekend long day is on call from 8am to 11pm, both counted as time on duty; help desk is the morning, followed by ordinary work until 5pm; someone on nights doesn't work the day. Half-day leave takes the morning or the afternoon, and the registrar works the other half. A Friday afternoon or Monday morning off counts as leave next to the weekend; a swing day (12pm–10pm) has no morning work.
- **Shift types:** Long day (8am–11pm), Night (10pm–8am), Swing (12pm–10pm), Help desk (8am–12pm), RDO, Sleep. Weekend variants of long days and nights carry different workload weights. Public holidays become stat days, using the Canterbury holiday calendar.
- **Variances:** where the department, the registrars and their union have agreed to go past a contract limit, the checks still report the break but mark it as agreed, and the editor shows it as a note rather than a problem. The one in force: a full week next to a weekend of long days is 75 hours, over the 72-hour limit in 7 days (STONZ 17.1.2, RDA 13.4.1), in exchange for both RDOs in the following week instead of one in each week. Moving the RDOs into the weekend's own week is allowed; putting them off to a later week is frowned upon and shows as a real break. The rule lives in `DEPARTMENT_VARIANCES` in `roster/rules.py`.
- **Cover:** every weekday needs a swing day and a night; every weekend day and public holiday needs a swing or a long day, and a night. The rule lives in `COVER` in `core/service.py`.
- **Workload:** each registrar's on-call load over the last 26 weeks, weighted per shift (`WORKLOAD_WEIGHTS` in `core/service.py`). Extra duties don't count.
- **Leave types:** Annual, Education, Conference, Lieu day, Sick, Parental, Bereavement. A leave can cover all day, AM or PM. It moves through registrar request, chief registrar approval, DoT approval, printed, entered into Microster, and can be cancelled. The chief registrar may record the DoT's approval on their behalf when the DoT is busy; each decision records who made it.
- **Paper forms:** the hospital still needs signed PDF leave forms (usual leave, and MEL/conference leave). Radscheduler fills them in from leave records.
- **Microster:** the hospital's official rostering system. Leave is copied into it manually, and Radscheduler tracks whether that has happened.
- **Extra duties:** extra-duty shifts are posted, registrars register interest (with a comment), and the chief registrar allocates them, with an option to pick at random among interested registrars. Extra duties do not count towards workload.
- **Publishing:** a global date range controls which shifts and leave registrars can see.
- **Calendar feeds:** iCal feeds for shifts and leave, polled by phone calendar apps.

## Capabilities and Constraints

- **Stack:**
  - Server-rendered Django templates, using django-template-partials, progressively enhanced with Unpoly and Alpine.js.
  - Bootstrap 5 with Bootstrap Icons, plus FullCalendar for the registrar calendar.
  - Django Ninja for the JSON API.
  - Deployed on Fly.io.
  - Not a SPA: the baseline must work without JavaScript. The exception is the roster editor, a staff-only Elm app; staff can still edit shifts and leave in the Django admin without JavaScript.
- **Roles:** registrar (signed in), and staff (`is_staff`) for roster and extra-duty editing. Accounts use django-allauth. Leave decisions follow groups: the **Director of Training** group makes only the Director's decision, **Office Staff** see leave but decide none, and other staff (the chief registrars, in **Roster master**) make both, recording the Director's for them when asked.
- **Roster editor:** a dense grid of dates by registrars for three weeks, with shift and leave cells, statuses and workload beside each name, contract and department rule breaks marked on the cells they touch (with the clause), a cover strip that shows only gaps (each opens a list of who is free, least loaded first), a problems list, unpublished days marked, a keyboard grid, undo, leave approved a request at a time with who decided and when, and publishing in a dialog that previews what registrars will gain or lose and the gaps and rule breaks in the days they would start seeing. Edits always save; rule breaks are flagged, not blocked.
- **Leave requests** (`/roster/leave/`): where the chief registrar and the Director of Training decide leave. Days of leave are grouped into the requests registrars made (same type and half of the day, added together, on working days with only weekends or holidays between). The page opens on an overview of every request of the registrars in training, a row each (who, what and when, when asked, each approver's decision, and for one still waiting, its verdict in a few words), filtered by where they stand (waiting on you, waiting on anyone, approved, declined, cancelled, any), leave dates, registrar year, leave type and registrar, and sorted by leave date, when asked or decided, registrar or length; the filters live in the address. Requests waiting on you with nothing against them (no rule break, no cover lost, no busy day; not yet rostered is fine, as leave is mostly given before the roster is built) can be ticked and approved together, with undo. A row opens in place, on a shelf under it, with the request as approval mode draws it (verdict, buttons, roster strip, leave by year), one at a time; Escape closes it. "Review these" opens approval mode on what the filters match, the first 50, listed by month when sorted by leave date. Leave loaded in bulk from the old system (50 or more rows in the same second) has no recorded asking time, and says so rather than counting days from the load. Each request leads with a one-line verdict (how many would be on leave out of the roster, the cover it would lose, the rule breaks it would cause; green only when every day was rostered and checked, and saying so when days aren't rostered yet) beside a strip of roster from two days before to two days after: the registrar's own shifts and other leave, a row of decisions per approver, how many are on leave each day shaded by their share of the roster (click for names), and the cover lost, with cover that was already short shown apart. Rule breaks the leave causes are listed apart from those already on the roster. Below them, the leave the registrar has had in the leave year the request falls in (from the first Monday of February), by type: approved, still waiting, this request and the total, with earlier years behind a disclosure. The request's Approve and Decline only change days still waiting for you; approving leave that breaks a rule or loses cover says so on the button ("Approve despite 1 rule break"), and every decision, a single day's too, can be undone for a few seconds; single days are decided in their column, and each approver row can decide every waiting day. Settled requests are read-only until "Change decision". The Director of Training sees verdicts first, with the roster on request, and their waiting list split by whether the chief registrar has approved. Keys in approval mode: j/k between requests, a/d to approve or decline with focus in a request (moving on to the next one waiting), arrows within a roster, Esc back to the overview.
- **Undecided:** how department-specific configuration (supervisor, holidays, shift definitions) will work once multiple departments are supported.

## Brand Commitments

- Name: **Radscheduler**. The current mark is the Bootstrap Icons `calendar-heart` glyph shown next to the name in the navbar.
- Author attribution in page metadata: Dr Tubo Shi, MBChB, FRANZCR.
- No other binding brand assets or voice guidelines exist.

## Evidence on Hand

- Real roster, leave and registrar data lives in the production database. Local backups can be pulled with `db:pull` / `db:restore`. It is personal staff data: never use it in public-facing material.
- Hospital leave form templates: `radscheduler/paper_forms/forms/usual_leaves.pdf` and `mel_and_conf_leaves.pdf`.
- There are no testimonials, usage metrics, or adoption claims. Do not invent any.

## Product Principles

1. **The roster is the source of truth.** What the app shows must match what the hospital will pay and staff. If data is unpublished, stale or pending, say so explicitly; never imply it is final.
2. **The contract is enforced, not remembered.** Rule violations show up at the point of editing, with the clause behind them, rather than leaving people to recall the rules.
3. **Fairness is visible.** Workload is measurable and shown openly, so allocation decisions can be defended.
4. **Fit each role's moment.** Registrars get fast answers on a phone in under a minute. The chief registrar gets density and speed on a wide screen.
5. **Generalise carefully.** Build for one department's reality without hardcoding it, because other departments are a likely next audience.

## Accessibility & Inclusion

WCAG 2.2 AA is the baseline. Shift and leave states must not be shown by colour alone, because the calendar and editor rely heavily on colour-coded cells.
