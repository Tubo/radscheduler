from ninja import NinjaAPI

from .editor import router as editor_router
from .roster_calendar import router as calendar_router


class Api(NinjaAPI):
    def get_openapi_operation_id(self, operation):
        """
        Name each operation after its view function, in camelCase (add_shift -> addShift), so the Elm client
        generated from the schema reads naturally.
        """
        first, *rest = operation.view_func.__name__.split("_")
        return first + "".join(word.capitalize() for word in rest)


api = Api(title="Radscheduler API", version="1")
api.add_router("calendar/", calendar_router)
api.add_router("editor/", editor_router)
