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

It also balances on-call load by fatigue weighting, so fairness can be measured rather than argued about. Registrar status (pre-oncall, reliever, part time, pre-exam, buddy required, not available) and leave feed straight into who is eligible for a shift.

## Operating Context

- **Shift types:** Long day (8am–10pm), Night (10pm–8am), Swing (12pm–10pm), Help desk (8am–12pm), RDO, Sleep. Weekend variants of long days and nights carry different fatigue weights. Public holidays become stat days, using the Canterbury holiday calendar.
- **Leave types:** Annual, Education, Conference, Lieu day, Sick, Parental, Bereavement. A leave can cover all day, AM or PM. It moves through registrar request, chief registrar approval, DoT approval, printed, entered into Microster, and can be cancelled.
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
  - Not a SPA: the baseline must work without JavaScript.
- **Roles:** registrar (signed in), and staff (`is_staff`) for roster and extra-duty editing. Accounts use django-allauth.
- **Roster editor:** a dense grid of dates by registrars, with shift and leave cells, a workload/fatigue breakdown, and settings shown in a modal layer.
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
3. **Fairness is visible.** Workload and fatigue are measurable and shown openly, so allocation decisions can be defended.
4. **Fit each role's moment.** Registrars get fast answers on a phone in under a minute. The chief registrar gets density and speed on a wide screen.
5. **Generalise carefully.** Build for one department's reality without hardcoding it, because other departments are a likely next audience.

## Accessibility & Inclusion

WCAG 2.2 AA is the baseline. Shift and leave states must not be shown by colour alone, because the calendar and editor rely heavily on colour-coded cells.
