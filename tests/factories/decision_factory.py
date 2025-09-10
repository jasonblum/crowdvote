"""
Factory classes for Decision-related models.

Provides factories for Decision, Choice, Ballot, and Vote models
with realistic test data generation.
"""

import factory
from factory.django import DjangoModelFactory
from faker import Faker
from django.utils import timezone
from datetime import timedelta

from democracy.models import Decision, Choice, Ballot, Vote
# Import handled in methods to avoid circular imports

fake = Faker()


class DecisionFactory(DjangoModelFactory):
    """Factory for creating Decision instances."""
    
    class Meta:
        model = Decision
    
    community = factory.SubFactory('tests.factories.CommunityFactory')
    title = factory.Faker('sentence', nb_words=6)
    description = factory.Faker('text', max_nb_chars=800)
    dt_close = factory.LazyFunction(lambda: timezone.now() + timedelta(days=7))
    
    @factory.post_generation
    def with_choices(obj, create, extracted, **kwargs):
        """Add choices to the decision."""
        if not create:
            return
        
        if extracted is False:
            return
        
        # Default: create 3-5 choices
        num_choices = extracted if isinstance(extracted, int) else fake.random_int(min=3, max=5)
        
        for i in range(num_choices):
            ChoiceFactory(decision=obj)


class ActiveDecisionFactory(DecisionFactory):
    """Factory for creating active decisions."""
    
    dt_close = factory.LazyFunction(lambda: timezone.now() + timedelta(days=fake.random_int(min=1, max=14)))


class ClosedDecisionFactory(DecisionFactory):
    """Factory for creating closed decisions."""
    
    dt_close = factory.LazyFunction(lambda: timezone.now() - timedelta(days=fake.random_int(min=1, max=30)))


class ChoiceFactory(DjangoModelFactory):
    """Factory for creating Choice instances."""
    
    class Meta:
        model = Choice
    
    decision = factory.SubFactory(DecisionFactory)
    title = factory.Faker('sentence', nb_words=3)
    description = factory.Faker('text', max_nb_chars=300)


class BallotFactory(DjangoModelFactory):
    """Factory for creating Ballot instances."""
    
    class Meta:
        model = Ballot
    
    decision = factory.SubFactory(DecisionFactory)
    voter = factory.SubFactory('tests.factories.UserFactory')
    is_calculated = False
    is_anonymous = factory.Faker('boolean', chance_of_getting_true=30)
    tags = factory.LazyAttribute(lambda obj: ','.join(fake.random_choices(
        ['governance', 'budget', 'environment', 'safety', 'maintenance'], 
        length=fake.random_int(min=1, max=3)
    )))
    
    @factory.post_generation
    def with_votes(obj, create, extracted, **kwargs):
        """Add votes to the ballot for all choices."""
        if not create or extracted is False:
            return
        
        # Only create votes if with_votes is True (default behavior)
        if extracted is not False:
            # Create votes for all choices in the decision
            for choice in obj.decision.choices.all():
                VoteFactory(ballot=obj, choice=choice)


class CalculatedBallotFactory(BallotFactory):
    """Factory for creating calculated (inherited) ballots."""
    
    is_calculated = True
    
    @factory.post_generation
    def set_inheritance_info(obj, create, extracted, **kwargs):
        """Set up inheritance tracking."""
        if create and extracted:
            # extracted should be a dict with inheritance info
            obj.comments = f"Inherited from: {extracted.get('source', 'unknown')}"
            obj.save()


class ManualBallotFactory(BallotFactory):
    """Factory for creating manual ballots."""
    
    is_calculated = False


class VoteFactory(DjangoModelFactory):
    """Factory for creating Vote instances."""
    
    class Meta:
        model = Vote
    
    ballot = factory.SubFactory(BallotFactory)
    choice = factory.SubFactory(ChoiceFactory)
    stars = factory.Faker('random_int', min=0, max=5)


class RealisticVoteFactory(VoteFactory):
    """Factory for creating more realistic vote distributions."""
    
    @factory.lazy_attribute
    def stars(self):
        """Generate more realistic star ratings with preference for middle values."""
        # Weight towards 2-4 stars, less likely to be 0 or 5
        weights = [5, 15, 30, 30, 15, 5]  # 0-5 stars
        return fake.random_choices(list(range(6)), weights)[0]


class TestDecisionWithVotesFactory(DecisionFactory):
    """Factory for creating decisions with full voting scenarios."""
    
    @factory.post_generation
    def create_voting_scenario(obj, create, extracted, **kwargs):
        """Create a complete voting scenario with multiple ballots."""
        if not create:
            return
        
        # Ensure we have choices
        if not obj.choices.exists():
            for i in range(4):  # Create 4 choices
                ChoiceFactory(decision=obj)
        
        # Get community members
        members = obj.community.memberships.filter(is_voting_community_member=True)
        
        if not members.exists():
            # Create some members if none exist
            from .user_factory import MembershipFactory
            for _ in range(10):
                MembershipFactory(community=obj.community)
            members = obj.community.memberships.filter(is_voting_community_member=True)
        
        # Create manual ballots for some members
        manual_voters = members[:len(members)//2]  # Half vote manually
        for membership in manual_voters:
            ballot = ManualBallotFactory(
                decision=obj,
                voter=membership.member,
                tags=fake.random_choices(['governance', 'budget', 'environment'], length=2)
            )
            
            # Create realistic votes for all choices
            for choice in obj.choices.all():
                RealisticVoteFactory(ballot=ballot, choice=choice)
        
        # Create some calculated ballots for delegation testing
        calculated_voters = members[len(members)//2:]
        for membership in calculated_voters:
            CalculatedBallotFactory(
                decision=obj,
                voter=membership.member,
                with_votes=True,
                set_inheritance_info={'source': 'delegation_chain'}
            )
