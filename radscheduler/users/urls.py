from django.urls import path

from radscheduler.users.views import (
    user_contract_view,
    user_detail_view,
    user_redirect_view,
    user_update_view,
)

app_name = "users"
urlpatterns = [
    path("~redirect/", view=user_redirect_view, name="redirect"),
    path("~update/", view=user_update_view, name="update"),
    path("~contract/", view=user_contract_view, name="contract"),
    path("<str:username>/", view=user_detail_view, name="detail"),
]
