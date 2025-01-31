from ninja import NinjaAPI

from .roster_calendar import router as calendar_router

api = NinjaAPI()
api.add_router("calendar/", calendar_router)
