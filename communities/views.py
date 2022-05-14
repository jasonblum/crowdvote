from collections import defaultdict


from django.shortcuts import render


from .services import CalculateBallots, Tally


def calulate_ballots(request):
    ballot_tree = CalculateBallots.execute({})
    return render(request, "communities/ballot_tree.html", {"ballot_tree": ballot_tree})


def tally(request):
    tally_report = Tally.execute({})
    return render(request, "communities/tally.html", {"tally_report": tally_report})
