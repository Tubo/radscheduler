from datetime import date
from urllib.parse import urlencode

from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from radscheduler.core import roster_weeks
from radscheduler.core.leave_requests import in_training
from radscheduler.core.models import Registrar

VIEWS = ("mine", "dept")


def own_registrar(user) -> Registrar | None:
    """The signed-in user's registrar record while they are in training, for their own roster."""
    if not user.is_authenticated:
        return None
    return in_training().filter(user=user).select_related("user").first()


def parse_month(value: str | None) -> date | None:
    """A month as "2026-10", or the month of a day as "2026-10-14"."""
    if not value:
        return None
    try:
        return date.fromisoformat(value if len(value) > 7 else f"{value}-01").replace(day=1)
    except ValueError:
        return None


def follow_css(follow: int | None) -> str:
    """
    The style that follows a registrar: every other chip a plain outline, theirs in a ring, and their days off
    and leave out of their days' folded lines. static/js/roster.js writes the same rules as following changes.
    """
    if not follow:
        return ""
    chip = f'.rb-chip[data-r="{follow}"]'
    return (
        f'#rb .rb-chip[data-r]:not([data-r="{follow}"]){{border-color:var(--re-line);'
        "background-color:#fff;color:var(--re-muted)}"
        f"#rb {chip}{{box-shadow:0 0 0 1.5px #fff,0 0 0 3px var(--re-ink)}}"
        f"#rb {chip}.is-folded{{display:var(--rb-chip-display)}}"
    )


def counted(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def follow_summary(roster: dict, follow: int) -> str:
    """What of the followed registrar the month holds: "13 on call, 1 day off and 2 days of leave in October"."""
    kinds = [
        chip.kind
        for week in roster["weeks"]
        for day in week.days
        if not day.outside
        for chip in day.chips
        if chip.registrar == follow
    ]
    parts = []
    if kinds.count("oncall"):
        parts.append(f"{kinds.count('oncall')} on call")
    if kinds.count("off"):
        parts.append(counted(kinds.count("off"), "day off", "days off"))
    if kinds.count("leave"):
        parts.append(counted(kinds.count("leave"), "day of leave", "days of leave"))
    what = " and ".join([", ".join(parts[:-1]), parts[-1]] if len(parts) > 1 else parts) or "nothing"
    return f"{what} in {roster['month']:%B}"


@require_GET
def page(request):
    """
    The roster, a month at a time: a calendar on a wide screen, and on a phone a list of days that runs on into
    the next month as it scrolls. Registrars in training open on their own roster ("mine"), with who is on call
    with them; everyone else, and anyone who asks, gets the department's, where one registrar can be followed
    across the month and the rest narrowed by year and type. The choice of the two is remembered for the session.
    """
    registrar = own_registrar(request.user)
    view = request.GET.get("view")
    if view in VIEWS:
        request.session["roster_view"] = view
    else:
        view = request.session.get("roster_view") or ("mine" if registrar else "dept")
    if view == "mine" and registrar is None:
        view = "dept"
    mine = registrar if view == "mine" else None

    today = timezone.localdate()
    # "from" is what the page's addresses used before it went by month.
    month = parse_month(request.GET.get("month")) or parse_month(request.GET.get("from")) or today.replace(day=1)
    follow = request.GET.get("follow", "")
    follow = int(follow) if follow.isdigit() and not mine else None
    year = request.GET.get("year", "")
    year = int(year) if year.isdigit() and not mine else None
    show = request.GET.get("show", "")
    if mine or show not in roster_weeks.SHOW_CHOICES:
        show = ""
    filters = roster_weeks.Filters(years=(year,) if year else (), show=roster_weeks.SHOW_CHOICES[show][1])

    roster = roster_weeks.build(month, today, mine=mine, filters=filters)

    # The query that keeps this page's choices, for links that change one of them.
    kept = {"view": view, "year": year, "show": show, "follow": follow, "month": f"{month:%Y-%m}"}

    def query(**changes) -> str:
        params = kept | changes
        return urlencode({k: v for k, v in params.items() if v not in (None, "")})

    def month_query(other: date | None) -> str | None:
        return other and query(month=f"{other:%Y-%m}")

    people = [] if mine else roster_weeks.people()
    followed = next((p for p in people if p["id"] == follow), None)
    if follow and followed is None:
        followed = next(
            (
                {"id": chip.registrar, "name": chip.full_name}
                for week in roster["weeks"]
                for day in week.days
                for chip in day.chips
                if chip.registrar == follow
            ),
            None,
        )
    next_shift = roster_weeks.next_on_call(mine, today) if mine else None

    return render(
        request,
        "roster/page.html",
        {
            "view": view,
            "registrar": registrar,
            "roster": roster,
            "today": today,
            "this_month": today.replace(day=1),
            "filters": filters,
            "year": year,
            "show": show,
            "show_choices": [(value, label) for value, (label, _) in roster_weeks.SHOW_CHOICES.items()],
            "follow": follow,
            "followed": followed,
            "follow_summary": followed and follow_summary(roster, follow),
            "follow_css": follow_css(follow),
            "people": people,
            "years": sorted({p["year"] for p in people if p["year"]}),
            "next_on_call": next_shift,
            "days_to_next": next_shift and (next_shift.date - today).days,
            "key": roster_weeks.shift_key(),
            "prev_query": month_query(roster["prev"]),
            "next_query": month_query(roster["next_page"]),
            # On a phone the next month runs on under this one while it has published days.
            "append_query": month_query(roster["next"]),
            "today_query": query(month=None),
            # A chip's link follows its registrar, or stops following them if they already are.
            "follow_query": query(follow=None),
            "mine_query": urlencode({"view": "mine", "month": f"{month:%Y-%m}"}),
            "dept_query": urlencode({"view": "dept", "month": f"{month:%Y-%m}"}),
            "filter_count": bool(year) + bool(show),
            "clear_query": query(year=None, show=None),
        },
    )
