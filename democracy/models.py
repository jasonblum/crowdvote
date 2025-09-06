"""
Democracy models for the CrowdVote application.

This module contains all models related to democratic decision-making, including
communities, decisions, voting, and results. These models implement the core
functionality of CrowdVote's STAR voting system with delegative democracy.

Key concepts:
- Communities: Groups of users who make decisions together
- Decisions: Questions or proposals that communities vote on
- STAR Voting: Score Then Automatic Runoff voting system
- Delegative Democracy: Users can delegate votes or vote directly
- Ballot Inheritance: Votes can be calculated from delegation chains
"""

import uuid
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from taggit.managers import TaggableManager

from shared.models import BaseModel

User = get_user_model()


class Community(BaseModel):
    """
    Represents a community of users who make decisions together.
    
    CrowdVote supports multiple communities, allowing users to participate in
    different groups (e.g., condo association, town council, student government).
    Each community operates independently with its own decisions and membership.
    
    Features:
    - Multi-community membership (users can belong to multiple communities)
    - Rich membership model with roles and permissions
    - Independent decision-making processes per community
    - Flexible membership management
    
    Attributes:
        name (CharField): Display name of the community
        description (TextField): Detailed description of the community's purpose
        members (ManyToManyField): Users who belong to this community (through Membership)
    """
    name = models.CharField(
        max_length=255,
        help_text="Display name of the community"
    )
    description = models.TextField(
        help_text="Detailed description of the community's purpose and scope"
    )
    members = models.ManyToManyField(
        User, 
        through="Membership",
        help_text="Users who belong to this community"
    )

    class Meta:
        verbose_name_plural = "Communities"
        ordering = ["name"]

    def __str__(self):
        """Return string representation of the community."""
        return self.name
    
    def get_voting_members(self):
        """
        Get all members who have voting rights in this community.
        
        Returns:
            QuerySet: Users who are voting members (not just lobbyists)
        """
        return self.members.filter(
            memberships__community=self,
            memberships__is_voting_community_member=True
        )
    
    def get_managers(self):
        """
        Get all members who can manage this community.
        
        Returns:
            QuerySet: Users who are community managers
        """
        return self.members.filter(
            memberships__community=self,
            memberships__is_community_manager=True
        )


class Membership(BaseModel):
    """
    Through-model for Community-User relationship with additional membership details.
    
    This model defines the relationship between users and communities, including
    their roles, permissions, and preferences within each community. It enables
    fine-grained control over who can vote, manage the community, and how their
    participation is handled.
    
    Membership Types:
    - Voting Members: Can cast ballots that count toward decision results
    - Lobbyists: Can participate in discussions but votes don't count
    - Managers: Can manage community membership and settings
    
    Privacy Features:
    - Anonymous voting: Members can choose to hide their identity in votes
    - Flexible privacy controls per community
    
    Attributes:
        member (ForeignKey): The user who is a member of the community
        community (ForeignKey): The community the user belongs to
        is_anonymous_by_default (BooleanField): Whether member prefers anonymous voting
        is_community_manager (BooleanField): Whether member can manage the community
        is_voting_community_member (BooleanField): Whether member's votes count
        dt_joined (DateTimeField): When the member joined this community
    """
    member = models.ForeignKey(
        User, 
        related_name="memberships", 
        on_delete=models.PROTECT,
        help_text="The user who is a member of this community"
    )
    community = models.ForeignKey(
        Community, 
        related_name="memberships", 
        on_delete=models.PROTECT,
        help_text="The community this membership belongs to"
    )
    is_anonymous_by_default = models.BooleanField(
        default=True, 
        help_text="Whether this member prefers anonymous voting by default"
    )
    is_community_manager = models.BooleanField(
        default=False, 
        help_text="Whether this member can manage community membership and settings"
    )
    is_voting_community_member = models.BooleanField(
        default=False, 
        help_text="Whether this member's votes count (vs. being just a lobbyist)"
    )
    dt_joined = models.DateTimeField(
        auto_now_add=True,
        editable=False,
        help_text="Timestamp when this member joined the community"
    )

    class Meta:
        ordering = ["community__name", "member__username"]
        verbose_name = "Community Membership"
        verbose_name_plural = "Community Memberships"
        # Ensure a user can only have one membership per community
        unique_together = ["member", "community"]

    def __str__(self):
        """Return string representation of the membership."""
        return f"{self.member.username} in {self.community.name}"
    
    @property
    def role_display(self):
        """
        Get a human-readable description of the member's role.
        
        Returns:
            str: Description of the member's role and permissions
        """
        roles = []
        if self.is_community_manager:
            roles.append("Manager")
        if self.is_voting_community_member:
            roles.append("Voter")
        else:
            roles.append("Lobbyist")
        
        return ", ".join(roles)


class Decision(BaseModel):
    """
    Represents a question or proposal that a community votes on.
    
    Decisions are the core of CrowdVote's democratic process. Each decision
    presents a question to the community with multiple choices that members
    can vote on using the STAR voting system (Score Then Automatic Runoff).
    
    Decision Lifecycle:
    1. Created by community members or managers
    2. Open for voting until dt_close
    3. Votes are tallied using STAR voting algorithm
    4. Results are calculated and stored
    5. Decision is closed and results are final
    
    Features:
    - Flexible voting periods with configurable close dates
    - Automatic result calculation triggers
    - Support for multiple choices per decision
    - Integration with delegative democracy system
    
    Attributes:
        title (CharField): Short, descriptive title of the decision
        description (TextField): Detailed description of what's being decided
        dt_close (DateTimeField): When voting closes and results are finalized
        community (ForeignKey): Which community this decision belongs to
        results_need_updating (BooleanField): Whether results need recalculation
    """
    title = models.CharField(
        max_length=255,
        help_text="Short, descriptive title of the decision"
    )
    description = models.TextField(
        help_text="Detailed description of what's being decided, including context and implications"
    )
    dt_close = models.DateTimeField(
        help_text="When voting closes and results are finalized (no more votes accepted)"
    )
    community = models.ForeignKey(
        Community, 
        related_name="decisions", 
        on_delete=models.PROTECT,
        help_text="The community this decision belongs to"
    )
    results_need_updating = models.BooleanField(
        default=True,
        help_text="Whether results need recalculation (set when new votes are cast)"
    )

    class Meta:
        ordering = ["-dt_close", "title"]

    def __str__(self):
        """Return string representation of the decision."""
        return self.title

    @property
    def result(self):
        """
        Get the most recent result for this decision.
        
        Returns:
            Result or None: The latest calculated result, or None if no results exist
        """
        return self.results.first()
    
    @property
    def is_open(self):
        """
        Check if voting is still open for this decision.
        
        Returns:
            bool: True if voting is open, False if closed
        """
        from django.utils import timezone
        return timezone.now() < self.dt_close
    
    def get_total_ballots(self):
        """
        Get the total number of ballots cast for this decision.
        
        Returns:
            int: Number of ballots (both manual and calculated)
        """
        return self.ballots.count()
    
    def get_voting_member_ballots(self):
        """
        Get ballots from members who have voting rights.
        
        Returns:
            QuerySet: Ballots from voting community members only
        """
        return self.ballots.filter(
            voter__memberships__community=self.community,
            voter__memberships__is_voting_community_member=True
        )


class Choice(BaseModel):
    """
    Represents an individual option/choice within a Decision.
    
    Each Decision can have multiple choices that community members vote on
    using the STAR voting system. Choices are the specific options that
    voters can score from 0-5 stars.
    
    STAR Voting Process:
    1. Score Phase: Voters give each choice 0-5 stars
    2. Automatic Runoff: Top 2 choices compete based on voter preferences
    
    The score and runoff_score fields store the calculated results from
    the STAR voting algorithm.
    
    Attributes:
        title (CharField): Short name/title of this choice
        description (TextField): Detailed description of what this choice means
        decision (ForeignKey): The decision this choice belongs to
        score (DecimalField): Average star score from all votes (0.0000-5.0000)
        runoff_score (DecimalField): Score in automatic runoff phase
    """
    title = models.CharField(
        max_length=255,
        help_text="Short, descriptive name for this choice"
    )
    description = models.TextField(
        help_text="Detailed description of what this choice represents"
    )
    decision = models.ForeignKey(
        Decision, 
        related_name="choices", 
        on_delete=models.PROTECT,
        help_text="The decision this choice belongs to"
    )
    
    # Score tracking fields (calculated by STAR voting algorithm)
    score = models.DecimalField(
        null=True,
        blank=True,
        max_digits=5,
        decimal_places=4,
        help_text="Average star score from all votes (0.0000-5.0000)"
    )
    runoff_score = models.DecimalField(
        null=True,
        blank=True,
        max_digits=5,
        decimal_places=4,
        help_text="Score in the automatic runoff phase of STAR voting"
    )

    class Meta:
        ordering = ["decision__title", "title"]

    def __str__(self):
        """Return string representation of the choice."""
        return f"{self.title} ({self.decision.title})"

    def get_id_display(self):
        """Get a short display ID for this choice."""
        return f"Ch-{self.id}"
    
    def get_vote_count(self):
        """
        Get the total number of votes cast for this choice.
        
        Returns:
            int: Number of votes (from all ballots)
        """
        return self.votes.count()
    
    def get_average_stars(self):
        """
        Calculate the average star rating for this choice.
        
        Returns:
            float or None: Average stars (0.0-5.0) or None if no votes
        """
        from django.db.models import Avg
        result = self.votes.aggregate(avg_stars=Avg('stars'))
        return result['avg_stars']


class Ballot(BaseModel):
    """
    Represents a user's complete vote on a Decision.
    
    A ballot contains all of a user's votes (star ratings) for the choices
    in a decision. Ballots can be either:
    1. Manually cast: User directly votes on each choice
    2. Calculated: System calculates votes based on delegation chains
    
    Delegation System:
    - If a user doesn't vote directly, the system can calculate their ballot
    - Calculation follows the user's Following relationships
    - Multiple levels of delegation are supported (A follows B, B follows C)
    - Users can always override calculated ballots by voting directly
    
    Privacy Features:
    - Anonymous voting: Ballot can be marked as anonymous
    - Comments: Users can explain their reasoning (optional)
    
    Attributes:
        id (UUIDField): Unique identifier for this ballot
        decision (ForeignKey): The decision this ballot is for
        voter (ForeignKey): The user who cast (or will have calculated) this ballot
        is_calculated (BooleanField): Whether this ballot was calculated vs. manual
        is_anonymous (BooleanField): Whether this ballot should be anonymous
        comments (TextField): Optional explanation of voting reasoning
    """
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        help_text="Unique identifier for this ballot"
    )
    decision = models.ForeignKey(
        Decision, 
        related_name="ballots", 
        on_delete=models.PROTECT,
        help_text="The decision this ballot is voting on"
    )
    voter = models.ForeignKey(
        User, 
        related_name="ballots", 
        on_delete=models.PROTECT,
        help_text="The user who cast this ballot (or had it calculated)"
    )
    is_calculated = models.BooleanField(
        default=False,
        help_text="True if calculated by delegation system, False if manually cast"
    )
    is_anonymous = models.BooleanField(
        default=True,
        help_text="Whether this ballot should be kept anonymous"
    )
    tags = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated tags this voter applied to characterize this decision (e.g., 'environmental,fiscal')"
    )
    comments = models.TextField(
        blank=True,
        help_text="Optional explanation of voting reasoning or context"
    )

    class Meta:
        ordering = ["decision__title", "voter__username"]
        # Ensure one ballot per user per decision
        unique_together = ["decision", "voter"]

    def __str__(self):
        """Return string representation of the ballot."""
        return f"{self.voter.username}'s ballot on {self.decision.title}"

    def get_preferred_choice(self):
        """
        Determine the voter's preferred choice for STAR voting runoff.
        
        In STAR voting, after the scoring phase, the top 2 choices go to
        an automatic runoff where each voter's preference determines the winner.
        
        Returns:
            Choice or None: The choice this voter prefers, or None if tied/no preference
            
        References:
            https://www.starvoting.us/ties - STAR voting tie-breaking rules
        """
        # TODO: Implement STAR voting preferred choice logic
        # This should:
        # 1. Get the voter's star ratings for all choices
        # 2. Determine which choice they gave the highest rating to
        # 3. Handle ties according to STAR voting rules
        pass
    
    def get_total_stars_cast(self):
        """
        Get the total number of stars this voter cast across all choices.
        
        Returns:
            int: Sum of all star ratings in this ballot
        """
        from django.db.models import Sum
        result = self.votes.aggregate(total_stars=Sum('stars'))
        return result['total_stars'] or 0
    
    def is_complete(self):
        """
        Check if this ballot has votes for all choices in the decision.
        
        Returns:
            bool: True if voter has rated all choices, False otherwise
        """
        choice_count = self.decision.choices.count()
        vote_count = self.votes.count()
        return choice_count == vote_count


class Vote(BaseModel):
    """
    Represents an individual star rating for a specific Choice within a Ballot.
    
    In STAR voting, voters rate each choice from 0-5 stars. Each Vote record
    represents one voter's rating for one choice. A complete Ballot contains
    multiple Vote records (one for each Choice in the Decision).
    
    STAR Voting Scale:
    - 0 stars: Strongly oppose or worst option
    - 1 star: Oppose or poor option  
    - 2 stars: Neutral or acceptable option
    - 3 stars: Support or good option
    - 4 stars: Strongly support or very good option
    - 5 stars: Enthusiastic support or best option
    
    Attributes:
        id (UUIDField): Unique identifier for this vote
        choice (ForeignKey): The choice being rated
        stars (PositiveSmallIntegerField): Star rating from 0-5
        ballot (ForeignKey): The ballot this vote belongs to
    """
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        help_text="Unique identifier for this vote"
    )
    choice = models.ForeignKey(
        Choice, 
        related_name="votes", 
        on_delete=models.PROTECT,
        help_text="The choice being rated in this vote"
    )
    stars = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        help_text="Star rating from 0 (worst) to 5 (best) for this choice"
    )
    ballot = models.ForeignKey(
        Ballot,
        related_name="votes",
        on_delete=models.PROTECT,
        help_text="The ballot this vote belongs to"
    )

    class Meta:
        ordering = ["choice"]
        # Ensure one vote per choice per ballot
        unique_together = ["choice", "ballot"]

    def __str__(self):
        """Return string representation of the vote."""
        return f"{self.stars} stars for {self.choice.title}"
    
    def clean(self):
        """
        Validate the vote.
        
        Raises:
            ValidationError: If choice doesn't belong to ballot's decision
        """
        from django.core.exceptions import ValidationError
        
        if self.choice.decision != self.ballot.decision:
            raise ValidationError(
                "Vote choice must belong to the same decision as the ballot."
            )
    
    def save(self, *args, **kwargs):
        """Override save to run validation."""
        self.clean()
        super().save(*args, **kwargs)


class Result(BaseModel):
    """
    Stores the calculated results and statistics for a Decision.
    
    After voting closes (or when results need updating), the STAR voting
    algorithm calculates the results and stores them in this model. This
    provides both human-readable reports and detailed statistics for
    transparency and auditability.
    
    STAR Voting Results Include:
    - Score phase: Average star ratings for each choice
    - Runoff phase: Head-to-head comparison of top 2 choices
    - Winner determination and margin of victory
    - Detailed vote breakdowns and statistics
    - Ballot inheritance tree (showing delegation chains)
    
    Features:
    - Multiple result snapshots (results are recalculated when votes change)
    - Comprehensive audit trail with detailed statistics
    - Human-readable reports for community members
    - Machine-readable data for API access and analysis
    
    Attributes:
        decision (ForeignKey): The decision these results are for
        report (TextField): Human-readable summary of results
        stats (JSONField): Detailed statistics and calculation data
    """
    decision = models.ForeignKey(
        Decision, 
        related_name="results", 
        on_delete=models.PROTECT,
        help_text="The decision these results are for"
    )
    report = models.TextField(
        help_text="Human-readable summary of the voting results and winner"
    )
    stats = models.JSONField(
        help_text="Detailed statistics including vote counts, averages, delegation chains, and audit data"
    )

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        """Return string representation of the result."""
        return f"Results for {self.decision.title}"
    
    def get_winner(self):
        """
        Extract the winning choice from the results.
        
        Returns:
            dict or None: Winner information from stats, or None if no winner
        """
        if 'winner' in self.stats:
            return self.stats['winner']
        return None
    
    def get_score_phase_results(self):
        """
        Get the score phase results (average star ratings).
        
        Returns:
            list: Choices ordered by average star rating
        """
        if 'score_phase' in self.stats:
            return self.stats['score_phase']
        return []
    
    def get_runoff_results(self):
        """
        Get the automatic runoff results (top 2 choices head-to-head).
        
        Returns:
            dict or None: Runoff results, or None if no runoff occurred
        """
        if 'runoff_phase' in self.stats:
            return self.stats['runoff_phase']
        return None
    
    def get_participation_stats(self):
        """
        Get participation statistics (total ballots, delegation info, etc.).
        
        Returns:
            dict: Participation and delegation statistics
        """
        if 'participation' in self.stats:
            return self.stats['participation']
        return {}


