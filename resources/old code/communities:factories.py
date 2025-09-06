from datetime import timedelta
import factory

from django.utils import timezone
from factory import fuzzy

from factory.django import DjangoModelFactory

from .models import Community, Membership, Referendum, Ballot, Choice, Vote


class CommunityFactory(DjangoModelFactory):
    class Meta:
        model = Community

    name = factory.Faker("company")
    description = factory.Faker("paragraph")


class MembershipFactory(DjangoModelFactory):
    class Meta:
        model = Membership

    is_voting_community_member = fuzzy.FuzzyChoice([True] * 10 + [False])
    is_community_manager = fuzzy.FuzzyChoice([True] + [False] * 6)
    is_anonymous_by_default = fuzzy.FuzzyChoice([False] * 3 + [True])


class ReferendumFactory(DjangoModelFactory):
    class Meta:
        model = Referendum

    title = factory.Faker("sentence")
    description = factory.Faker("paragraph")
    dt_close = fuzzy.FuzzyDateTime(timezone.now(), timezone.now() + timedelta(days=365))


class ChoiceFactory(DjangoModelFactory):
    class Meta:
        model = Choice

    title = factory.Faker("sentence")
    description = factory.Faker("paragraph")


class BallotFactory(DjangoModelFactory):
    class Meta:
        model = Ballot

    # I cant recall where I found this or why but I think it's broken.
    # @factory.post_generation
    # def tags(self, create, extracted, **kwargs):
    #     if not create:
    #         # Simple build, do nothing.
    #         return

    #     if extracted:
    #         # A list of tags were passed in, use them.
    #         for tag in extracted:
    #             self.tags.add(tag)


class VoteFactory(DjangoModelFactory):
    class Meta:
        model = Vote

    stars = fuzzy.FuzzyInteger(1, 5)
