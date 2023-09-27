from django_unicorn.components import UnicornView
from radscheduler.core.service import (
    retrieve_fullcalendar_events,
    retrieve_roster_events,
)


class ShiftsTableView(UnicornView):
    start = "2022-01-01"
    end = "2022-12-31"
    events = retrieve_roster_events(start, end).to_json(orient="table", index=False)

    class Meta:
        safe = ("events",)

    def mount(self):
        start = self.component_args[0]
        end = self.component_args[1]

    def refresh(self):
        self.call("table.setData", self.events)
