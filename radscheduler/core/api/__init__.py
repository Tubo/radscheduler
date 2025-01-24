from ninja import NinjaAPI

from .roster_calendar import router as calendar_router
from .roster_editor import router as editor_router

api = NinjaAPI()
api.add_router("calendar/", calendar_router)
api.add_router("editor/", editor_router)
