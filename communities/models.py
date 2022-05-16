from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

from taggit.managers import TaggableManager

from shared.models import BaseModel


User = get_user_model()


class Community(BaseModel):
    """
    CrowdVote can host multiple Communities, so members can belong to more than one.
    """

    name = models.CharField(max_length=255)
    description = models.TextField()  # TODO Convert to RichTextField
    members = models.ManyToManyField(User, through="Membership")

    class Meta:
        verbose_name_plural = "Communities"


class Membership(BaseModel):
    """
    This is a "through-model", where we can add details about a person's membership in a community,
    such as whether their vote actually counts, or they are just a "lobbyist"
    """

    member = models.ForeignKey(
        User, related_name="memberships", on_delete=models.PROTECT
    )
    community = models.ForeignKey(
        Community, related_name="memberships", on_delete=models.PROTECT
    )
    is_anonymous = models.BooleanField(
        default=True, help_text="Members vote anonymously by default."
    )
    is_community_legislator = models.BooleanField(
        default=False, help_text="Can author and publish Elections."
    )
    is_community_manager = models.BooleanField(
        default=False, help_text="Can manage Community membership."
    )
    is_voting_community_member = models.BooleanField(
        default=False, help_text="Can vote (not just a lobbyist.)"
    )
    dt_joined = models.DateTimeField(
        auto_now_add=True,
        editable=False,
        help_text="DateTime member joined this community",
    )

    @property
    def username(self):
        """
        Community Members' identites and memberships must be transparent and verifiable, but their
        actual usernames do not need to be revealed, allowing them to remain anonymous,  if the like.
        """
        return self.member.username if self.is_public else "Anonymous"


class Election(BaseModel):
    """
    The actual question posted to the community (e.g.
    "Should we extend the Bush-era tax cuts for the rich?" or
    "Which landscape proposal should we accept?")
    """

    title = models.CharField(max_length=255)
    description = models.TextField()
    dt_close = models.DateTimeField(
        help_text="DateTime this Election closes, no longer tallied, and no longer allowing votes."
    )
    community = models.ForeignKey(
        Community, related_name="elections", on_delete=models.PROTECT
    )
    # TODO: Make these JSON fields?:
    ballot_tree = models.TextField(help_text="JSON data representation of the tally")
    tally_report = models.TextField(
        help_text="User-friendly presentation of the ballot_tree"
    )

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
    is_winning_candidate = models.BooleanField(
        default=False, help_text="Set by tally (and note: there might be a tie)"
    )
    stars = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        help_text="Score Then Automatic Runoff",
    )

    def get_id_display(self):
        return f"Ca-{self.id}"


class Ballot(BaseModel):
    election = models.ForeignKey(
        Election, related_name="ballots", on_delete=models.PROTECT
    )
    membership = models.ForeignKey(
        Membership, related_name="ballots", on_delete=models.PROTECT
    )
    is_calculated = models.BooleanField(
        default=False,
        help_text="False by default, or when manually cast - True, if calculated by the system.",
    )
    tags = TaggableManager()

    def get_preferred_candidate(self):
        pass
        # https://www.starvoting.us/ties
        # For Automatic Runoff, which candidate, if any, is preferred?
        # Get the

    @property
    def voter(self):
        return self.membership.member


class Vote(BaseModel):
    candidate = models.ForeignKey(
        Candidate, related_name="votes", on_delete=models.PROTECT
    )
    stars = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        help_text="Score Then Automatic Runoff",
    )
    ballot = models.ForeignKey(
        Ballot,
        related_name="votes",
        on_delete=models.PROTECT,
    )

    class Meta:
        ordering = ["candidate"]
