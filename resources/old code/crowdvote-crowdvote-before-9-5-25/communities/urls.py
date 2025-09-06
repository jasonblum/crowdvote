from django.urls import path

from . import views

app_name = "communities"

urlpatterns = [
    path("calculate_ballots/", views.calculate_ballots, name="calculate_ballots"),
    path("tally/", views.tally, name="tally"),
]
