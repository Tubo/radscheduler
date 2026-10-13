---
name: Radscheduler
description: A live duty board for one radiology department's registrars, checked against their contract as it is built.
colors:
  ink: '#1f2933'
  muted: '#5c6670'
  line: '#dfe3e8'
  line-strong: '#aab3bc'
  panel: '#f6f7f9'
  surface: '#ffffff'
  accent: '#0b5ed7'
  accent-deep: '#0a4bab'
  accent-soft: '#9ec5fe'
  accent-tint: '#e8f0fe'
  shift-long: '#b54708'
  shift-swing: '#8e3a8e'
  shift-night: '#1d2b5c'
  shift-help: '#0b6e6e'
  off-bg: '#eef0f3'
  off-ink: '#3d4650'
  off-line: '#8a949e'
  ok: '#146c43'
  ok-bg: '#edf7f1'
  ok-line: '#9fd3b5'
  wait: '#7a4a00'
  wait-bg: '#fff4d6'
  wait-line: '#d9a63a'
  bad: '#b42318'
  bad-deep: '#8f1c13'
  bad-bg: '#fdf0ee'
  bad-line: '#e4a1a8'
  weekend: '#f0f2f4'
  holiday: '#ece6fa'
  holiday-ink: '#4b2e83'
  heat-1: '#86b6ef'
  heat-2: '#4a8ee0'
  heat-3: '#256abf'
  heat-4: '#104281'
  toast: '#2b2f33'
  navbar: '#212529'
  mark-amber: '#ffc107'
typography:
  headline:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', 'Noto Sans', 'Liberation Sans', Arial, sans-serif"
    fontSize: '1.5rem'
    fontWeight: 600
    lineHeight: 1.2
  title:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', 'Noto Sans', 'Liberation Sans', Arial, sans-serif"
    fontSize: '1.125rem'
    fontWeight: 600
    lineHeight: 1.25
  body:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', 'Noto Sans', 'Liberation Sans', Arial, sans-serif"
    fontSize: '0.875rem'
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: 'tnum'
  label:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', 'Noto Sans', 'Liberation Sans', Arial, sans-serif"
    fontSize: '0.75rem'
    fontWeight: 500
    lineHeight: 1
    fontFeature: 'tnum'
  micro:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', 'Noto Sans', 'Liberation Sans', Arial, sans-serif"
    fontSize: '0.6875rem'
    fontWeight: 600
    lineHeight: 1.3
rounded:
  tag: '3px'
  chip: '4px'
  control: '0.375rem'
  layer: '0.5rem'
  pill: '999px'
spacing:
  xxs: '0.125rem'
  xs: '0.25rem'
  sm: '0.375rem'
  md: '0.5rem'
  lg: '0.75rem'
  xl: '1.25rem'
components:
  button:
    backgroundColor: '{colors.surface}'
    textColor: '{colors.ink}'
    rounded: '{rounded.control}'
    padding: '0.25rem 0.625rem'
    height: '2rem'
  button-hover:
    backgroundColor: '{colors.panel}'
  button-primary:
    backgroundColor: '{colors.accent}'
    textColor: '{colors.surface}'
    rounded: '{rounded.control}'
    padding: '0.25rem 0.625rem'
    height: '2rem'
  button-primary-hover:
    backgroundColor: '{colors.accent-deep}'
  button-danger:
    backgroundColor: '{colors.bad}'
    textColor: '{colors.surface}'
    rounded: '{rounded.control}'
    padding: '0.25rem 0.625rem'
    height: '2rem'
  button-danger-hover:
    backgroundColor: '{colors.bad-deep}'
  button-danger-quiet:
    backgroundColor: '{colors.surface}'
    textColor: '{colors.bad}'
    rounded: '{rounded.control}'
    padding: '0.25rem 0.625rem'
    height: '2rem'
  button-quiet:
    textColor: '{colors.accent}'
    padding: '0.125rem 0'
  input:
    backgroundColor: '{colors.surface}'
    textColor: '{colors.ink}'
    rounded: '{rounded.control}'
    padding: '0.25rem 0.5rem'
    height: '2rem'
  chip-shift-long:
    backgroundColor: '{colors.shift-long}'
    textColor: '{colors.surface}'
    typography: '{typography.label}'
    rounded: '{rounded.chip}'
    padding: '3px 4px'
  chip-shift-off:
    backgroundColor: '{colors.off-bg}'
    textColor: '{colors.off-ink}'
    typography: '{typography.label}'
    rounded: '{rounded.chip}'
    padding: '3px 4px'
  chip-leave-pending:
    backgroundColor: '{colors.wait-bg}'
    textColor: '{colors.wait}'
    typography: '{typography.label}'
    rounded: '{rounded.chip}'
    padding: '3px 3px'
  chip-leave-approved:
    backgroundColor: '{colors.ok-bg}'
    textColor: '{colors.ok}'
    typography: '{typography.label}'
    rounded: '{rounded.chip}'
    padding: '3px 3px'
  clause-tag:
    textColor: '{colors.bad}'
    typography: '{typography.micro}'
    rounded: '{rounded.tag}'
    padding: '0 4px'
  tab:
    textColor: '{colors.muted}'
    rounded: '{rounded.control}'
    padding: '0.3125rem 0.75rem'
  tab-on:
    backgroundColor: '{colors.surface}'
    textColor: '{colors.ink}'
  popover:
    backgroundColor: '{colors.surface}'
    textColor: '{colors.ink}'
    rounded: '{rounded.layer}'
    padding: '0.625rem 0.75rem'
  toast:
    backgroundColor: '{colors.toast}'
    textColor: '{colors.surface}'
    rounded: '{rounded.layer}'
    padding: '0.5rem 0.625rem 0.5rem 0.875rem'
  navbar:
    backgroundColor: '{colors.navbar}'
    textColor: '{colors.surface}'
---

# Design System: Radscheduler

## Overview

**Creative North Star: "The Duty Board"**

Radscheduler is the department's whiteboard made trustworthy. The board's job is to be read at a glance by someone between cases, and to be rewritten all day by the senior registrar. Every mark on it means something: a filled chip is a shift, an outlined chip is leave, a red outline is a gap or a rule break with its clause beside it. Nothing on the board is decoration, and nothing that matters relies on colour alone.

It is dense but friendly. The roster editor packs three weeks of registrars onto one wide screen, so type is small (13–14px body, 11–12px chips) and controls share one compact size. Long editing sessions shouldn't feel harsh, though, so corners stay softly rounded, lines are hairline greys rather than black rules, hover feedback is a quiet tint, and popovers rise gently over 120ms. Registrars use the same pages on a phone, where the same chips and states read at full width.

The system lives in the Elm pages (`static/css/editor_elm.scss` and `leave_requests.scss`, all `--re-*` tokens). The roster page that opens the app (`static/css/roster.scss`) is a server-rendered page on the same tokens and chips. The older Bootstrap templates (leave, extra duties, admin-adjacent pages) are legacy and should move toward these tokens rather than the other way round. The app rejects the generic SaaS dashboard (card grids, big KPI numbers, gradients, soft shadows on everything) and hospital IT (grey enterprise forms, tiny controls, cramped dialogs, a colour soup of status codes).

**Key Characteristics:**

- One light, neutral working surface; colour is reserved for shifts and for three states (ok, waiting, bad).
- Shapes and line styles carry meaning as well as colour: fill, outline, dash, strike-through, folded corner.
- One compact control size (2rem) everywhere; tabular numerals throughout.
- Flat at rest; only floating layers cast a shadow.
- The dark navbar and its amber mark frame every page; amber appears nowhere else.

## Colors

A cool, near-neutral ground with four saturated shift hues and a strict three-state palette for decisions and rules.

### Primary

- **Roster Blue** (`accent`): the one interactive accent on light surfaces. Primary buttons, quiet text actions, focus outlines, checked switches, the today marker and the "Today"/"Unpublished" tags. **Pressed Blue** (`accent-deep`) is its hover and the text colour on blue tints; **Soft Blue** (`accent-soft`) is the text selection and the buddy badge border; **Blue Wash** (`accent-tint`) is the selected-count and buddy-badge ground.

### Secondary

- **Shift hues**, one per shift type and always with white text: **Long-Day Rust** (`shift-long`), **Swing Plum** (`shift-swing`), **Night Navy** (`shift-night`), **Help-Desk Teal** (`shift-help`). RDOs and sleep days are not work, so they take **Off-Duty Grey** (`off-bg` with `off-ink` text and a dashed `off-line` border) instead of a hue.

### Tertiary

- **State triads**, each a text colour, a ground and a line: **Approved Green** (`ok`, `ok-bg`, `ok-line`), **Waiting Ochre** (`wait`, `wait-bg`, `wait-line`) and **Breach Red** (`bad`, `bad-bg`, `bad-line`). They mean approved/covered, pending/partial, and declined/gap/rule break, and nothing else.
- **Leave Heat** (`heat-1` to `heat-4`): the leave requests page's share of the roster on leave, one blue from light to dark, drawn as a thin bar under each day's count that grows a quarter of its track per step. The count stays ink, so the bar is never the only signal and the row stays quieter than the shifts.

### Neutral

- **Board Ink** (`ink`): all body text.
- **Slate Muted** (`muted`): secondary text, weekday names, inactive tabs, hover borders.
- **Hairline** (`line`) and **Rule** (`line-strong`): cell borders and dividers; control borders and the edges of sticky panes.
- **Panel Grey** (`panel`): toolbars, the cover strip, the tab well, button hover.
- **Weekend Grey** (`weekend`) and **Holiday Lilac** (`holiday`, labelled in `holiday-ink`): day columns that aren't ordinary weekdays.
- **Toast Charcoal** (`toast`): the undo and error toasts.
- **Navbar Charcoal** (`navbar`) with **Mark Amber** (`mark-amber`): the global navbar, the logo glyph, the current-page underline and the navbar's focus ring.

### Named Rules

**The Three States Rule.** Decisions and checks have exactly three colours: green for approved or covered, ochre for waiting, red for declined, gaps and breaches. A new status takes one of these with a distinct shape or icon. Never add a fourth state colour.

**The Amber Is the Mark Rule.** Amber belongs to the logo and the dark navbar. On light surfaces the accent is Roster Blue, always.

**The Contrast Floor Rule.** Every text pair meets WCAG AA, and every mark that carries meaning on its own (markers, edges, outlines) meets 3:1 against its ground. Check any new pair before shipping it.

## Typography

**Display Font:** none. The app has no display voice; the roster is the hero.
**Body Font:** the platform's system UI stack (Bootstrap's native font stack).
**Label/Mono Font:** the same stack with tabular numerals; `kbd` uses it too.

**Character:** Native, legible, and quiet, so dates, names and counts line up and nothing competes with the grid. Hierarchy comes from weight (400 / 500 / 600) and a few size steps, never from a second family.

### Hierarchy

- **Headline** (600, 1.5rem): page titles such as "Leave requests"; the editor's toolbar title runs slightly smaller (1.375rem).
- **Title** (600, 1.125rem): a registrar's name heading a leave request; popover titles at 1.0625rem.
- **Body** (400, 0.875rem, 1.5): controls, popover text, toasts, help text (kept to 68ch). Dense lists and tables step down to 0.8125rem.
- **Label** (500, 0.75rem, line-height 1): chips, weekday names, counts.
- **Micro** (600, 0.6875rem, 1.3): clause tags, cover gaps, day tags (Today, holiday, unpublished), status badges at 0.625rem.

### Named Rules

**The Tabular Rule.** Every Elm surface sets `font-variant-numeric: tabular-nums`. Dates, hours and loads must line up in columns.

**The Full Name Rule.** A chip keeps its full label where it can (busy days stack chips one per line and the row grows); when space truly runs out, it ends in an ellipsis rather than wrapping.

## Layout

The editor is a full-height app frame: it fills the window below the navbar (`100dvh` minus the measured navbar height) and scrolls inside. Its grid has a sticky date header (64px), a sticky cover strip (44px), and sticky registrar name (156px) and load (48px) columns, with 80px day columns. The leave requests page is an app frame like the editor: it fills the window below the navbar with a toolbar (the 1.375rem title, the status tabs or, in review, the way back and the colour key, and a "How it works" menu floating over the page), then a 16rem filter rail on the panel grey beside a pane of requests that scrolls by itself; below 80rem the rail opens over the pane from a Filters button, with a Done. The page itself never scrolls. The overview is a dense table of requests beside its filters (from and to dates, year and type chips that take a Roster Blue edge and wash when on, a registrar select), with a bar stuck to the top of the pane holding the count, the sort and the one primary action (Review these, or Approve the ticked); a row is a card on a phone. A row opens in place: its cells take the panel grey, its chevron turns down, and a shelf under it, panel grey around a white, 0.5rem-cornered body, holds the request as approval mode draws it, the row's own who-what-when hidden from sight. In approval mode and on a shelf each request is two columns: down the side the decision (the verdict, in approval mode only, and the buttons), then under a hairline what to weigh it against (the rule breaks, then one leave-by-year table, years across), always in that order; beside them a roster strip of fixed 4.75rem day columns. Narrow, they stack: decision, roster, then the rest; with the roster hidden, the rest takes the roster's place. Nothing opens into a request: day names and rule breaks already on the roster open as popovers anchored to their control, so the request keeps its size.

The roster that opens the app is a page that scrolls, not a frame. Its head holds the 1.5rem title, the Mine/Department tabs (the leave requests page's tabs) and "Published to Tue 2 Feb" at the far end; under it one quiet row: the registrar's next shift, or the filters (Follow select, a Year well of tabs with All, a Show select), then a quiet Key at the far end. The filters are grey at rest; a choice that narrows the roster takes a Roster Blue edge and wash, with a quiet Clear. Then the month bar: joined ‹ › buttons, the month's name at 1.25rem/600, Today, and a month picker at the far end. From 48rem the month is a calendar of seven equal columns with hairline rules under a weekday header that sticks to the top, the days either side of the month on the panel grey with muted dates, sized so a whole month fits a 900px screen: a day shows its on-call chips one to a line, then, past two, its days off and leave folded into a muted dotted-underlined line ("3 off · 9 on leave", an ochre hourglass when some wait) that opens their chips in a Layer popover. Below 48rem each day is a row, the date down a 3rem side column and the chips wrapping beside it; the month's name sticks to the top as its days pass; a day with nothing on it is one slim muted line; a folded line opens in place; the filters fold behind a Filter button with a count pill, and the key opens as a sheet along the bottom. Today takes the editor's 3px blue rule along its top and a "Today" tag; weekends the weekend grey, holidays Holiday Lilac with their name; unpublished days the hatch and a "Not published" tag. Pointing at a chip rings its registrar's chips in Roster Blue (3px with a 1.5px white gap) and changes nothing else; following them rings them in ink and turns every other chip to a plain white outline with muted text, so the hues mark only the person followed, and on a phone puts a white bar along the bottom saying who, with Stop following. Chips never transition. On a registrar's own on-call day, who else is on call follows the chip in 0.75rem muted type, each name after a small square of its shift's hue.

Spacing steps are small and rem-based: 0.125, 0.25, 0.375, 0.5, 0.75 and 1.25rem. Groups inside a control or chip sit 2–6px apart; sections inside a popover 0.75rem; page regions 1.25rem.

The navbar is one 45px row on a wide screen. A registrar's own pages (Roster, My leave, Extra duties) are always in view: beside the name from 768px, and below it on a phone as a full-width row of 44px tabs. The rest (the admin links, the published date, the account) folds into a menu below 768px for registrars and below 1200px for staff, who have more of it; between 1200px and 1400px staff lose only the published date, which the editor and the roster show themselves (the navbar leaves it out on those pages). Folded links get full-size tap targets and rules between the groups; without JavaScript the menu shows open. Full-height pages (the editor) drop the 4px gap under the navbar.

**The Wide Screen, Short Burst Rule.** Design the editor for a wide desktop and long sessions; design registrar pages for a phone and a glance. The same tokens serve both; density changes, meaning doesn't.

## Elevation & Depth

Flat by default. Depth comes from tone and hairlines: the panel grey for toolbars and sticky strips, a `line-strong` edge where a sticky pane meets the scrolling grid, and inset lines for markers (a 3px top line for today or the focus week, a 2px bottom line for the selected column). Shadows are reserved for things that float above the board.

### Shadow Vocabulary

- **Layer** (`box-shadow: 0 8px 20px rgba(15, 23, 42, 0.14), 0 1px 3px rgba(15, 23, 42, 0.08)`): popovers and dialogs.
- **Toast** (`box-shadow: 0 8px 20px rgba(15, 23, 42, 0.25)`): the undo and error toasts, which sit over anything.
- **Lift** (`box-shadow: 0 1px 2px rgba(31, 41, 51, 0.12)`): the selected tab, raised just off its well.

### Named Rules

**The Floating Only Rule.** A shadow means "this is above the board and will go away". Resting surfaces, chips, cells and buttons never cast one.

## Shapes

Softly rounded, never pill-shaped except for counts. Radius grows with the size of the thing: 2–3px for tags, clause marks and cover chips; 4px for roster chips; 6px (0.375rem) for buttons, inputs and tabs; 8px (0.5rem) for popovers, toasts and the tab well; a full pill only for numeric counts. Joined controls (the week picker, decision segments) round only their outer corners.

Line style is part of the shape language: solid for real things, dashed for "not quite" (off-duty days, partially decided leave, open cover, cancelled leave), strike-through for declined or cancelled, and a folded top-right corner for an extra duty.

## Components

Dense but friendly: one compact size, crisp 1px edges, 6px corners, and a quiet tint on hover rather than a jump.

### Buttons

- **Shape:** gently rounded (0.375rem), min height 2rem, padding 0.25rem 0.625rem, 0.875rem/500 text, icon and label 0.375rem apart.
- **Neutral:** white with a `line-strong` border and ink text. The default.
- **Primary:** Roster Blue fill, white text. Only the one action a surface exists for (Publish, Approve).
- **Danger:** Breach Red fill when it confirms a destructive act; **danger-quiet** (red text, `bad-line` border) when it only asks.
- **Quiet:** an underlined blue text action that reveals more ("See everything waiting").
- **On dark:** a translucent white outline, for actions inside toasts.
- **Hover / Active / Disabled:** border darkens to `muted` with a panel tint, then `line` when pressed (fills deepen instead); 120ms ease-out on colour only. Disabled keeps the shape with muted text. Focus is a 2px Roster Blue outline offset 1px.

### Chips

- **Shifts:** filled with their hue, white 0.75rem/500 text, 4px corners, 3px 4px padding. RDO and sleep take the dashed off-duty style. An extra duty adds a folded corner.
- **Leave:** outlined, never filled with a hue. White with a `line-strong` edge by default; waiting is ochre on wash, partial is dashed ochre, approved is green on wash, declined is red and struck through, cancelled is dashed grey and struck through. A half day shades its half (left for AM, right for PM) in the state's own colour.
- **Cover gaps:** outlined in Breach Red on white, never filled, so a gap can't be read as a shift. Open cover is a dashed ochre outline; on the leave requests page that is cover already short without the leave. Days not rostered yet take the unpublished hatch, a run of them one cell. A day a leave would break a rule on is outlined in Breach Red with its clause inside.
- **Clause tag:** the contract clause beside a rule break, small red text in a `bad-line` outline.
- **On the roster page:** the same chips (3px 5px padding; 5px 7px on a phone) and named in full ("Swing Rachel B.", "Annual·am Kate I."); leave carries its state icon (tick, question mark, hourglass). On a registrar's own roster they name the type in full ("Long day").
- **Status badge:** tiny ochre-on-wash tags for a registrar's statuses; buddy-required in blue.

### Cards / Containers

There are no cards. The roster is a table, a leave request is a row of the list beside its strip, and grouping is done with headings, hairlines and panel tints. A leave request ends in a small tally of the registrar's leave by year: one table, types down the side and leave years across under micro column heads, the request's year set apart by a Rule line, ink heads and full-weight numbers, 0.8125rem tabular numbers, hairline rows, an ochre hourglass where days still wait, the request's own days in blue with a + and its type's row on Blue Wash.

### Inputs / Fields

- **Style:** white, 1px `line-strong` border, 0.375rem corners, 2rem min height, 0.875rem text.
- **Focus:** the shared 2px Roster Blue outline. Hover darkens the border to `muted`.
- **Switches and checkboxes:** Bootstrap's controls in Roster Blue, with no glow on focus.

### Navigation

- **Global navbar:** Navbar Charcoal (`--re-navbar`) with the Mark Amber (`--re-mark-amber`) calendar-heart and the name at 1.0625rem/600; links at 0.875rem/500, white at 68% (6.9:1), the current page full white with a 2px amber underline, server-rendered, with Unpoly keeping the link lists (not the brand) in step. Admin links are named for the pages they open (Roster editor, Leave requests, Extra-duty editor, Admin site) and sit in their own group behind a 3:1 rule, led by the `bi-tools` icon (set into the rule when folded); the Director of Training and office staff see only Leave requests and Admin site. Leave requests carries an amber pill counting the requests waiting on you, read as "16 waiting on you". "Roster published to Tue 2 Feb" and the account links sit at the far end, a long username ending in an ellipsis. Signed out, the bar holds only the name and a "Sign in" outline button. A "Skip to content" link, white with an amber outline, appears over the navbar's corner when it takes keyboard focus and lands on `<main>`. The navbar doesn't print. Focus is a 2px amber outline with 6px corners.
- **Tabs (leave requests):** a panel-grey well with 8px corners holding 6px-cornered tabs; the selected tab is white with the Lift shadow and ink text, the rest muted. A pill count follows each label.

### Popovers

The editor's menus and dialogs open only when asked: white, `line-strong` border, 8px corners, the Layer shadow, a 120ms rise from 4px below (none with reduced motion). A hairline separates a head (title at 1.0625rem/600) and a foot (actions right, a secondary action left). Publishing uses a centred dialog that also dims the page.

### Toasts

Charcoal, bottom left, 8px corners, white 0.875rem text with on-dark buttons. They carry undo for a few seconds after a decision; errors add a pink-red icon.

## Do's and Don'ts

### Do:

- **Do** give every state a cue beyond colour: an icon, a dash, a strike-through, a fold, an underline or a word.
- **Do** fill shifts and outline everything else: leave, gaps, clause tags and badges.
- **Do** use the `--re-*` tokens on any new page, and bring legacy Bootstrap pages toward them when you touch them.
- **Do** keep controls at the one 2rem size, with a 2px Roster Blue focus outline (amber on the dark navbar).
- **Do** mark unpublished, pending or stale data explicitly, with the unpublished hatch or a tag, never by omission.
- **Do** keep motion to colour transitions and the 120ms popover rise, and turn it off under `prefers-reduced-motion`.

### Don't:

- **Don't** build card grids, hero metrics, gradients or soft shadows on resting surfaces; this is not a SaaS dashboard.
- **Don't** shrink controls below 2rem, cram dialogs, or add status colours beyond the three states; this is not hospital IT.
- **Don't** use amber anywhere but the logo and the navbar.
- **Don't** use Bootstrap's default blue (#0d6efd) or its glow focus shadow on Elm pages.
- **Don't** fill a gap or a leave chip with a hue, or it will read as a shift.
- **Don't** add a second typeface or a display face.
