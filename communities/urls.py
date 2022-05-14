from django.urls import path

from . import views

app_name = "communities"

urlpatterns = [
    path("calculate_ballots", views.calulate_ballots, name="calulate_ballots"),
    path("tally/", views.tally, name="tally"),
]
