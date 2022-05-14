from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

from taggit.managers import TaggableManager

from shared.models import BaseModel


User = get_user_model()


class Community(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField()
    members = models.ManyToManyField(User, through="Membership")

    class Meta:
        verbose_name_plural = "Communities"


class Membership(BaseModel):
    member = models.ForeignKey(
        User, related_name="memberships", on_delete=models.PROTECT
    )
    community = models.ForeignKey(
        Community, related_name="memberships", on_delete=models.PROTECT
    )
    is_public = models.BooleanField(
        default=False, help_text="Members are anonymous by default."
    )
    is_community_legislator = models.BooleanField(
        default=False, help_text="Can publish Ballots."
    )
    is_community_administrator = models.BooleanField(
        default=False, help_text="Can manage Community membership."
    )
    is_voting_community_member = models.BooleanField(
        default=False, help_text="Can vote (not just a lobbyist.)"
    )
    datetime_joined = models.DateTimeField(auto_now_add=True, editable=False)


class MembershipProxy(Membership):
    class Meta:
        proxy = True
        verbose_name = "Public Membership"
        verbose_name_plural = "Public Memberships"


class Election(BaseModel):
    title = models.CharField(max_length=255)
    description = models.TextField()
    datetime_close = models.DateTimeField()
    community = models.ForeignKey(
        Community, related_name="elections", on_delete=models.PROTECT
    )
    # TODO: Make these JSON fields:
    ballot_tree = models.TextField()
    tally_report = models.TextField()

    @property
    def winning_candidates(self):
        raise
        # We need a preference matrix or something like this: https://www.starvoting.us/ties
        return self.candidates.filter(is_winning_candidate=True)[:2]


class Candidate(BaseModel):
    title = models.CharField(max_length=255)
    description = models.TextField()
    election = models.ForeignKey(
        Election, related_name="candidates", on_delete=models.PROTECT
    )
    is_winning_candidate = models.BooleanField(default=False)
    stars = models.PositiveSmallIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(5)]
    )

    def get_id_display(self):
        return f"Ca-{self.id}"


class Ballot(BaseModel):
    election = models.ForeignKey(
        Election, related_name="ballots", on_delete=models.PROTECT
    )
    voter = models.ForeignKey(User, related_name="ballots", on_delete=models.PROTECT)
    calculated = models.BooleanField(default=False)
    tags = TaggableManager()

    def get_preferred_candidate(self):
        pass
        # https://www.starvoting.us/ties
        # For Automatic Runoff, which candidate, if any, is preferred?
        # Get the


class Vote(BaseModel):
    candidate = models.ForeignKey(Candidate, related_name="votes", on_delete=models.PROTECT)
    stars = models.PositiveSmallIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    ballot = models.ForeignKey(Ballot, related_name="votes", on_delete=models.PROTECT)

    class Meta:
        ordering = ["candidate"]
