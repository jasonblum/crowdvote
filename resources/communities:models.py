import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

from taggit.managers import TaggableManager
from taggit.models import GenericUUIDTaggedItemBase, TaggedItemBase

from shared.models import BaseModel


User = get_user_model()


class Community(BaseModel):
    """
    CrowdVote can host multiple Communities, so members can belong to more than one.
    """

    name = models.CharField(max_length=255)
    description = models.TextField()
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
    is_anonymous_by_default = models.BooleanField(
        default=True, help_text="Members' ballots are anonymous by default."
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

    # @property
    # def username(self):
    #     """
    #     Community Members' identites and memberships must be transparent and verifiable, but their
    #     actual usernames do not need to be revealed, allowing them to remain anonymous,  if they prefer.
    #     """
    #     return self.member.username if self.is_public else "Anonymous"


class Results(BaseModel):
    """
    Just a container for all the Referendum results...

    TODO: note I started doing another Result below, with the Referendum as a foreign key.
    Not sure what I was thinking here, but need to figure out which was the better approach...
    """

    ballot_inheritance_tree = models.TextField(
        help_text="TODO: JSON snapshot of the ballot inheritance"
    )
    choice_scores = models.TextField(
        help_text="Not sure how to store this, but need array of choices ordered by and including scores"
    )
    choice_runoff = models.TextField(
        help_text="Not sure how to store this, but need array of choices ordered by and including their runoff scores"
    )
    report = models.TextField(
        help_text="User-friendly presentation of all of the above."
    )


class Referendum(BaseModel):
    """
    The actual question posted to the community (e.g.
    "Should we extend the Bush-era tax cuts for the rich?" or
    "Which landscape proposal should we accept?")
    """

    title = models.CharField(max_length=255)
    description = models.TextField()
    dt_close = models.DateTimeField(
        help_text="DateTime this Referendum closes, no longer tallied, and no longer allowing votes."
    )
    community = models.ForeignKey(
        Community, related_name="referendums", on_delete=models.PROTECT
    )
    results_need_updating = models.BooleanField(
        default=True,
        help_text="The Referendum was just published, or someone voted, and tally() needs to run.",
    )

    @property
    def result(self):
        # Result will just be the last saved result.
        return self.results[0]


class Result(BaseModel):
    """
    Container for all of a referendum's results, calculations, etc.
    """

    referendum = models.ForeignKey(
        Referendum, related_name="results", on_delete=models.PROTECT
    )
    report = models.TextField()
    stats = models.JSONField()


class Choice(BaseModel):
    title = models.CharField(max_length=255)
    description = models.TextField()
    referendum = models.ForeignKey(
        Referendum, related_name="choices", on_delete=models.PROTECT
    )

    # TODO I stopped here not sure how to work this out.  Need some place for Referendum.Results to show candidates ORDERED BY their scores AND BY their runoff position
    score = models.DecimalField(
        null=True,
        max_digits=5,
        decimal_places=4,
        help_text="Average number of Stars",
    )
    runoff_score = models.DecimalField(
        null=True,
        max_digits=5,
        decimal_places=4,
        help_text="Average number of Stars",
    )

    def get_id_display(self):
        return f"Ca-{self.id}"


class UUIDTaggedItem(GenericUUIDTaggedItemBase, TaggedItemBase):
    # If you only inherit GenericUUIDTaggedItemBase, you need to define
    # a tag field. e.g.
    # tag = models.ForeignKey(Tag, related_name="uuid_tagged_items", on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Tag"
        verbose_name_plural = "Tags"


class Ballot(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referendum = models.ForeignKey(
        Referendum, related_name="ballots", on_delete=models.PROTECT
    )
    voter = models.ForeignKey(User, related_name="ballots", on_delete=models.PROTECT)
    is_calculated = models.BooleanField(
        default=False,
        help_text="False by default, or when manually cast - True, if calculated by the system.",
    )
    is_anonymous = models.BooleanField(
        # default=membership.is_anonymous_by_default,
        default=True,
        help_text="Defaults to Membership.is_anonymous_by_default",
    )
    tags = TaggableManager(through=UUIDTaggedItem)
    comments = models.TextField(
        help_text="Any additional context the voter might like to share behind their vote."
    )

    def get_preferred_choice(self):
        pass
        # https://www.starvoting.us/ties
        # For Automatic Runoff, which choice, if any, is preferred?
        # Get the

    # TODO constraint or save method to automatically set self.referendum.needs_new_results = True, so that a new tally runs


class Vote(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    choice = models.ForeignKey(Choice, related_name="votes", on_delete=models.PROTECT)
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
        ordering = ["choice"]
